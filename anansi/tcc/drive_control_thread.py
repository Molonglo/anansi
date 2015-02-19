from threading import Thread,Event
from multiprocessing import Manager
from anansi.comms import TCPClient
from struct import pack,unpack
from anansi import codec
import os
import logging
logging.basicConfig()

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

class BaseDriveInterface(Thread):
    def __init__(self,timeout,kevent=None,status_dict=None):
        self.timeout = timeout
        self.client = None
        decoder,size = codec.gen_header_decoder(self._node)
        self.header_decoder = decoder
        self.header_size = size

        if kevent is None:
            self.event = Event()
        else:
            self.event = kevent

        if status_dict is None:
            self.status_dict = Manager().dict()
        else:
            self.status_dict = status_dict

        Thread.__init__(self)

    def __del__(self):
        del self.client
        
    def open_client(self):
        if self.client is None:
            self.client = TCPClient(self._ip,self._port,timeout=self.timeout)
        
    def close_client(self):
        if self.client is not None:
            self.client.close()
            self.client = None
            
    def drive(self,data,arm="both"):
        arms = {"both":"1",
                "east":"2",
                "west":"3"}
        self.open_client()
        self.send_message(arms[arm],data)
        while True:
            code,_ = self.parse_message(*self.receive_message())
            if code == "S":
                self.run = self.drive_thread
                self.start()
                break
        return None

    def drive_thread(self):
        west_reached = False
        east_reached = False
        while not self.event.is_set():
            code,response = self.parse_message(*self.receive_message())
            if not west_reached:
                west_reached = (code == "I") and (response == 13)
            if not east_reached:
                east_reached = (code == "I") and (response == 14)
            if (code == "I") and (response == 0):
                break
        self.close_client()
        
    def parse_message(self,header,data):
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
            raise EZ80Error(self,decoded_response)
        else:
            print "logged %s:%s"%(code,repr(decoded_response))
        return code,decoded_response
    
    def get_status(self):
        self.open_client()
        self.send_message("U",None)
        code = None
        while code != "U":
            code,decoded_response = self.parse_message(*self.receive_message())
        while code != "S":
            code,_ = self.parse_message(*self.receive_message())
        self.close_client()
        return decoded_response
    
    def stop(self):
        self.open_client()
        self.send_message("0",None)
        code = None
        while code != "S":
            code,_ = self.parse_message(*self.receive_message())
        self.close_client()
                
    def receive_message(self):
        response = self.client.receive(self.header_size)
        header = codec.simple_decoder(response,self.header_decoder)
        data_size = header["HOB"]*256+header["LOB"]
        if data_size > 0:
            data = self.client.receive(data_size)
        else:
            data = None
        return header,data
    
    def send_message(self,code,data=None):
        header,msg = codec.simple_encoder(self._node,code,data)
        self.client.send(header)
        if len(msg)>0: 
            self.client.send(msg)
    
        
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

    def __init__(self,timeout=5.0,kevent=None,status_dict=None):
        super(NSDriveInterface,self).__init__(timeout,kevent,status_dict)

    def _calculate_tilts(self,response):
        response["east_ns_tilt"] = (response["east_ns_count"]-self._tilt_zero)/self._east_scaling
        response["west_ns_tilt"] = (response["west_ns_count"]-self._tilt_zero)/self._west_scaling
        return response
        
    def set_tilt(self,tilt,speed="fast"):
        status = self.get_status()
        east_counts = int(self._tilt_zero + self._east_scaling * tilt)
        west_counts = int(self._tilt_zero + self._west_scaling * tilt)

        east_dir = "north" if east_counts > status["east_ns_count"] else "south"
        west_dir = "north" if west_counts > status["west_ns_count"] else "south"
        
        data = codec.it_pack(east_counts) + codec.it_pack(west_counts)
        print east_counts,west_counts
        print repr(data)
        pos_dir = codec.pos_dir_pack(east_dir,speed,"east") + codec.pos_dir_pack(west_dir,speed,"west")  
        print "Pos_dir_val:",pos_dir
        pos_dir = pack("B",pos_dir)
        print repr(pos_dir)
        print repr(data+pos_dir)
        self.drive(data+pos_dir,arm="both")

    def set_east_tilt(self,tilt,speed="fast"):
        status = self.get_status()
        east_counts = int(self._tilt_zero + self._east_scaling * tilt)
        east_dir = "north" if east_counts > status["east_ns_count"] else "south"
        data = codec.it_pack(east_counts)
        pos_dir = pack("B",codec.pos_dir_pack(east_dir,speed,"east"))
        self.drive(data+pos_dir,arm="east")
        
    def set_west_tilt(self,tilt,speed="fast"):
        status = self.get_status()
        west_counts = int(self._tilt_zero + self._west_scaling * tilt)
        west_dir = "north" if west_counts > status["west_ns_count"] else "south"
        data = codec.it_pack(west_counts)
        pos_dir = pack("B",codec.pos_dir_pack(west_dir,speed,"west"))
        self.drive(data+pos_dir,arm="west")


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

    def __init__(self,timeout=5.0,kevent=None,status_dict=None):
        super(MDDriveInterface,self).__init__(timeout,kevent,status_dict)

    def _calculate_tilts(self,response):
        response["east_md_tilt"] = np.arcsin((
                response["east_md_count"]-self._tilt_zero)/self._east_scaling)
        response["west_md_tilt"] = np.arcsin((
                response["west_md_count"]-self._tilt_zero)/self._west_scaling)
        return response

    def set_tilt(self,tilt,speed="fast"):
        status = self.get_status()
        tilt = np.sin(tilt)
        east_counts = int(self._tilt_zero + self._east_scaling * tilt)
        west_counts = int(self._tilt_zero + self._west_scaling * tilt)

        east_dir = "north" if east_counts > status["east_count"] else "south"
        west_dir = "north" if west_counts > status["west_count"] else "south"
        
        data = codec.it_pack(east_counts) + codec.it_pack(west_counts)
        pos_dir = codec.pos_dir_pack(east_dir,speed,"both") 
        self.drive(data+pos_dir,arm="both")
        
    def set_east_tilt(self,tilt,speed="fast"):
        status = self.get_status()
        tilt = np.sin(tilt)
        east_counts = int(self._tilt_zero + self._east_scaling * tilt)
        east_dir = "north" if east_counts > status["east_count"] else "south"
        data = codec.it_pack(east_counts)
        pos_dir = codec.pos_dir_pack(east_dir,speed,"east")
        self.drive(data+pos_dir,arm="east")
