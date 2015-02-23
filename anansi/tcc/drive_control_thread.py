import logging
logging.basicConfig(level=logging.DEBUG)

from threading import Thread,Event
from Queue import Queue
from multiprocessing import Manager
from anansi.comms import TCPClient
from struct import pack,unpack
from anansi import codec
from anansi import decorators
import os


from ConfigParser import ConfigParser
config_path = os.environ["ANANSI_CONFIG"]
config = ConfigParser()
config.read(os.path.join(config_path,"anansi.cfg"))

NS_CONTROLLER_IP = config.get("IPAddresses","ns_controller_ip")
NS_CONTROLLER_PORT = config.getint("IPAddresses","ns_controller_port")
NS_NODE_NAME = config.get("DriveParameters","ns_node_name")
NS_WEST_SCALING = config.getfloat("DriveParameters","ns_west_scaling")
NS_EAST_SCALING = config.getfloat("DriveParameters","ns_east_scaling")
NS_TILT_ZERO = config.getfloat("DriveParameters","ns_tilt_zero")

MD_CONTROLLER_IP = config.get("IPAddresses","md_controller_ip")
MD_CONTROLLER_PORT = config.getint("IPAddresses","md_controller_port")
MD_NODE_NAME = config.get("DriveParameters","md_node_name")
MD_WEST_SCALING = config.getfloat("DriveParameters","md_west_scaling")
MD_EAST_SCALING = config.getfloat("DriveParameters","md_east_scaling")
MD_TILT_ZERO = config.getfloat("DriveParameters","md_tilt_zero")

class EZ80Error(Exception):
    def __init__(self,obj,code):
        message = "Exception %d caught from eZ80 at %s:%d"%(code,obj._ip,obj._port) 
        super(EZ80Error,self).__init__(message)
        logging.getLogger(self.__class__.__name__).error(message)
        obj.client.close()
        obj.event.set()

class BaseDriveInterface(Thread):
    _speeds = {"fast":0,"slow":1}
    @decorators.log_args
    def __init__(self,timeout,kevent=None,status_dict=None):
        self.timeout = timeout
        self.client = None
        decoder,size = codec.gen_header_decoder(self._node)
        self.header_decoder = decoder
        self.header_size = size
        self.error_queue = Queue()

        if kevent is None:
            self.event = Event()
        else:
            self.event = kevent

        if status_dict is None:
            self.status_dict = Manager().dict()
        else:
            self.status_dict = status_dict
        self.status_dict["test"] = 1
        
        Thread.__init__(self)
    
    @decorators.log_args
    def __del__(self):
        del self.client
        
    @decorators.log_args
    def _open_client(self):
        if self.client is None:
            self.client = TCPClient(self._ip,self._port,timeout=self.timeout)
            
    @decorators.log_args
    def _close_client(self):
        if self.client is not None:
            self.client.close()
            self.client = None

    @decorators.log_args
    def _drive(self,drive_code,data):
        self._open_client()
        self._send_message(drive_code,data)
        while True:
            code,respose = self._parse_message(*self._receive_message())
            if (code == "S") and (response == 0):
                self.run = self._drive_thread
                self.start()
                break
        

    @decorators.log_args
    def _drive_thread(self):
        while not self.event.is_set():
            code,response = self._parse_message(*self._receive_message())
            if (code == "S") and (response == 0):
                break
        self._close_client()

    @decorators.log_args
    def _receive_message(self):
        response = self.client.receive(self.header_size)
        print "Received message:",repr(response)
        header = codec.simple_decoder(response,self.header_decoder)
        data_size = header["HOB"]*256+header["LOB"]
        if data_size > 0:
            data = self.client.receive(data_size)
        else:
            data = None
        return header,data

    @decorators.log_args
    def _send_message(self,code,data=None):
        header,msg = codec.simple_encoder(self._node,code,data)
        self.client.send(header)
        if len(msg)>0:
            self.client.send(msg)
        
    @decorators.log_args
    def _parse_message(self,header,data):
        code = header["Command option"]
        if code in ["E","I","W","V","S"]:
            decoded_response = unpack("B",data)[0]
        elif code == "U":
            decoded_response = codec.simple_decoder(data,self._data_decoder)
            decoded_response = self._calculate_tilts(decoded_response)
            self.status_dict.update(decoded_response)
        else:
            decoded_response = None

        if code == "E":
            self.error_queue.put(EZ80Error(self,decoded_response))
            raise EZ80Error(self,decoded_response)
        
        if (code == "C") and (decoded_response >= 15):
            sleep(0.3)

        return code,decoded_response
    
    @decorators.log_args
    def get_status(self):
        self._open_client()
        self._send_message("U",None)
        code = None
        while code != "U":
            code,response = self._parse_message(*self._receive_message())
        while code != "S":
            code,_ = self._parse_message(*self._receive_message())
        self._close_client()
        return response
    
    @decorators.log_args
    def stop(self):
        self._open_client()
        self._send_message("0",None)
        code = None
        while code != "S":
            code,_ = self._parse_message(*self._receive_message())
        self._close_client()

    @decorators.log_args
    def tilts_to_counts(self,east_tilt,west_tilt):
        east_counts = int(self._tilt_zero + self._east_scaling * east_tilt)
        west_counts = int(self._tilt_zero + self._west_scaling * west_tilt)
        return east_counts,west_counts
        
    @decorators.log_args
    def counts_to_tilts(self,east_counts,west_counts):
        east_tilt = (east_counts-self._tilt_zero)/self._east_scaling
        west_tilt = (west_counts-self._tilt_zero)/self._east_scaling
        return east_tilt,west_tilt

    @decorators.log_args
    def set_tilts(self,east_tilt,west_tilt,
                  east_speed="fast",west_speed="fast"):
        east_count,west_count = self.tilts_to_counts(east_tilt,west_tilt)
        self.set_tilts_from_counts(east_count,west_count,east_speed,west_speed)
                
    @decorators.log_args
    def set_tilts_from_counts(self,east_count,west_count,
                              east_speed="fast",west_speed="fast"):
        drive_code = "1"
        encoded_count = codec.it_pack(east_count) + codec.it_pack(west_count)
        ed,wd = self._get_directions(east_count,west_count)
        e_dir_speed = 2*ed + self._speed[east_speed]
        w_dir_speed = 8*wd + 4*self._speed[west_speed]
        encoded_dir_speed = pack("B",e_dir_speed + w_dir_speed)
        data = encoded_count+encoded_dir_speed
        self.drive(drive_code,data)
        
    @decorators.log_args
    def set_east_tilt(self,east_tilt,speed="fast"):
        east_count,_ = tilts_to_counts(east_tilt,0)
        self.set_east_tilt_from_counts(east_count,speed)

    @decorators.log_args
    def set_east_tilt_from_counts(self,east_count,speed="fast"):
        drive_code = "2"
        encoded_count = codec.it_pack(east_count)
        ed,_ = self._get_directions(east_count,None)
        dir_speed = 2*ed + self._speed[speed]
        encoded_dir_speed = pack("B",dir_speed)
        data = encoded_count+encoded_dir_speed
        self.drive(drive_code,data)
     
    @decorators.log_args
    def set_west_tilt(self,west_tilt,speed="fast"):
        _,west_count = tilts_to_counts(0,west_tilt)
        self.set_west_tilt_from_counts(west_count,speed)

    @decorators.log_args
    def set_west_tilt_from_counts(self,west_count,speed="fast"):
        drive_code = "3"
        data = codec.it_pack(west_count)
        _,wd = self._get_directions(west_count,None)
        dir_speed = 8*wd + 4*self._speed[speed]
        encoded_dir_speed = pack("B",dir_speed)
        data = encoded_count+encoded_dir_speed
        self.drive(drive_code,data)
    

class NSDriveInterface(BaseDriveInterface):
    _node = NS_NODE_NAME
    _ip = NS_CONTROLLER_IP
    _port = NS_CONTROLLER_PORT
    _west_scaling = NS_WEST_SCALING
    _east_scaling = NS_EAST_SCALING
    _tilt_zero = NS_TILT_ZERO
    _data_decoder = [
        ("east_ns_status" ,lambda x: unpack("B",x)[0],1),
        ("east_ns_count"   ,lambda x: codec.it_unpack(x),3),
        ("west_ns_status" ,lambda x: unpack("B",x)[0],1),
        ("west_ns_count"   ,lambda x: codec.it_unpack(x),3)]
    _dir = {"north":0,"south":1}

    @decorators.log_args
    def __init__(self,timeout=5.0,kevent=None,status_dict=None):
        super(NSDriveInterface,self).__init__(timeout,kevent,status_dict)

    @decorators.log_args
    def _get_directions(self,east_counts=None,west_counts=None):
        status = self.get_status()
        if east_counts:
            east_dir = "north" if east_counts > status["east_ns_count"] else "south"
        else:
            east_dir = None
        if west_counts:
            west_dir = "north" if west_counts > status["west_ns_count"] else "south"
        else:
            west_dir = None
        return self._dir[east_dir],self._dir[west_dir]
        
    def _calculate_tilts(self,u_dict):
        et,wt = self.counts_to_tilts(self,u_dict["east_ns_count"],
                                     u_dict["west_ns_count"])
        u_dict["east_ns_tilt"] = et
        u_dict["west_ns_tilt"] = wt
        return u_dict


class MDDriveInterface(BaseDriveInterface):
    _node = MD_NODE_NAME
    _ip = MD_CONTROLLER_IP
    _port = MD_CONTROLLER_PORT
    _west_scaling = MD_WEST_SCALING
    _east_scaling = MD_EAST_SCALING
    _tilt_zero = MD_TILT_ZERO
    _data_decoder = [
        ("east_md_status" ,lambda x: unpack("B",x)[0],1),
        ("east_md_count"   ,lambda x: codec.it_unpack(x),3),
        ("west_md_status" ,lambda x: unpack("B",x)[0],1),
        ("west_md_count"   ,lambda x: codec.it_unpack(x),3)]
    _dir = {"west":0,"east":1}
    @decorators.log_args
    def __init__(self,timeout=5.0,kevent=None,status_dict=None):
        super(MDDriveInterface,self).__init__(timeout,kevent,status_dict)

    @decorators.log_args
    def tilts_to_counts(self,east_tilt,west_tilt):
        east_tilt = np.sin(east_tilt)
        west_tilt = np.sin(west_tilt)
        return super(MDDriveInterface,self).tilts_to_counts(east_tilt,west_tilt)

    @decorators.log_args
    def counts_to_tilts(self,east_counts,west_counts):
        east_tilt,west_tilt = super(MDDriveInterface,self).counts_to_tilts(east_counts,west_counts)
        return np.sin(east_tilt),np.sin(west_tilt)

    @decorators.log_args
    def _get_directions(self,east_counts=None,west_counts=None):
        status = self.get_status()
        if east_counts:
            east_dir = "west" if east_counts > status["east_md_count"] else "east"
        else:
            east_dir = None
        if west_counts:
            west_dir = "west" if west_counts > status["west_md_count"] else "east"
        else:
            west_dir = None
        return self._dir[east_dir],self._dir[west_dir]
    
    def _calculate_tilts(self,u_dict):
        et,wt = self.counts_to_tilts(self,u_dict["east_md_count"],
                                     u_dict["west_md_count"])
        u_dict["east_md_tilt"] = et
        u_dict["west_md_tilt"] = wt
        return u_dict

