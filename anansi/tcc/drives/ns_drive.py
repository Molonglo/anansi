from anansi.logging_db import MolongloLoggingDataBase as LogDB
from anansi.tcc.drives.base_drive import BaseDriveInterface

from threading import Thread,Event
from Queue import Queue
from multiprocessing import Manager
from anansi.comms import TCPClient
from struct import pack,unpack
from anansi import codec
from anansi import decorators
from pprint import pprint
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

class eZ80NSError(Exception):
    def __init__(self,code):
        message = "Exception E:%d caught from NS drive eZ80"%(code)
        super(EZ80Error,self).__init__(message)
        LogDB().log_tcc_status("NSDriveInterface","error",message)

class NSCountError(Exception):
    def __init__(self,count):
        message = "Invalid NS count of %d requested"%count
        super(NSCountError,self).__init__(message)
        LogDB().log_tcc_status("NSDriveInterface","error",message)

class NSDriveInterface(BaseDriveInterface):
    _node = NS_NODE_NAME
    _ip = NS_CONTROLLER_IP
    _port = NS_CONTROLLER_PORT
    _west_scaling = NS_WEST_SCALING
    _east_scaling = NS_EAST_SCALING
    _tilt_zero = NS_TILT_ZERO
    _data_decoder = [
        ("east_status" ,lambda x: unpack("B",x)[0],1),
        ("east_count"   ,lambda x: codec.it_unpack(x),3),
        ("west_status" ,lambda x: unpack("B",x)[0],1),
        ("west_count"   ,lambda x: codec.it_unpack(x),3)]
    
    def __init__(self,timeout):
        super(NSDriveInterface,self).__init__(timeout)
        self.active_thread = None
        self.event = Event()

    def _stop_active_drive(self):
        self.event.set()
        while self.active_thread.is_alive():
            sleep(0.2)
        self.active_thread.join()
        self.active_thread = None
        self.event.clear()
        
    def _drive_thread(self):
        while not self.event.is_set():
            try:
                code,response = self._parse_message(*self._receive_message())
            except eZ80NSError:
                break
            if (code == "S") and (response == 0):
                break
        self._close_client()
    
    def _drive(self,drive_code,data):
        self._stop_active_drive()
        self._open_client()
        self._send_message(drive_code,data)
        while True:
            code,response = self._parse_message(*self._receive_message())
            if (code == "S") and (response == 0):
                self.active_thread = Thread(target=self._drive_thread)
                self.active_thread.start()
                break

    def _log_position(self):
        self.log.log_position("ns",
            self.status_dict["west_count"],
            self.status_dict["east_count"])
        
    def _parse_message(self,header,data):
        code = header["Command option"]
        if code in ["E","I","W","V","S","C"]:
            decoded_response = unpack("B",data)[0]
            self.log.log_eZ80_status(code,decoded_response)
        elif code == "U":
            decoded_response = codec.simple_decoder(data,self._data_decoder)
            decoded_response = self._calculate_tilts(decoded_response)
            self.status_dict.update(decoded_response)
            self._log_position()
        else:
            decoded_response = None
        
        if code == "E":
            raise eZ80NSError(decoded_response)

        if (code == "C") and (decoded_response >= 15):
            sleep(0.3)

        return code,decoded_response
    
    def get_status(self):
        if not self.active_drive:
            self._open_client()
            self._send_message("U",None)
            code = None
            while code != "U":
                code,response = self._parse_message(*self._receive_message())
            while code != "S":
                code,_ = self._parse_message(*self._receive_message())
            self._close_client()
        return self.status_dict

    def stop(self):
        self._stop_active_drive()
        self._open_client()
        self._send_message("0",None)
        code = None
        while code != "S":
            code,_ = self._parse_message(*self._receive_message())
        self._close_client()

    def _prepare(self,east_counts=None,west_counts=None,
                 force_east_slow=False,force_west_slow=False):
        status = self.get_status()
        if east_counts is not None:
            east_offset = east_counts - status["east_count"]
            east_dir = NORTH_OR_WEST if east_offset >= 0 else SOUTH_OR_EAST
            if abs(east_offset) <= 40:
                east_speed = None
            elif abs(east_offset) <= 400 or force_east_slow:
                east_speed = SLOW
            else:
                east_speed = FAST
        else:
            east_dir = None
            east_speed = None

        if west_counts is not None:
            west_offset = west_counts - status["west_count"]
            west_dir = NORTH_OR_WEST if west_offset >= 0 else NORTH_OR_WEST
            if abs(west_offset) <= 40:
                west_speed = None
            elif abs(west_offset) <= 400 or force_west_slow:
                west_speed = SLOW
            else:
                west_speed = FAST
        else:
            west_dir = None
            west_speed = None

        return east_dir,west_dir,east_speed,west_speed
    
    def tilts_to_counts(self,east_tilt,west_tilt):
        east_counts = int(self._tilt_zero + self._east_scaling * east_tilt)
        west_counts = int(self._tilt_zero + self._west_scaling * west_tilt)
        return east_counts,west_counts


    def counts_to_tilts(self,east_counts,west_counts):
        east_tilt = (east_counts-self._tilt_zero)/self._east_scaling
        west_tilt = (west_counts-self._tilt_zero)/self._east_scaling
        return east_tilt,west_tilt

    def set_tilts(self,east_tilt,west_tilt,
                  force_east_slow=False,force_west_slow=False):
        east_count,west_count = self.tilts_to_counts(east_tilt,west_tilt)
        self.set_tilts_from_counts(east_count,west_count,force_east_slow,force_west_slow)
        
    def set_tilts_from_counts(self,east_count,west_count,
                              force_east_slow=False,force_west_slow=False):
        drive_code = "1"
        encoded_count = codec.it_pack(east_count) + codec.it_pack(west_count)
        ed,wd,es,ws = self._prepare(east_count,west_count,force_east_slow,force_west_slow)

        if es is None or ws is None:
            # if neither arm will move more than 40 counts                                  
            raise InvalidCounts("E and W arm requested move of less than 40 counts")
        elif ws is None:
            # if only east arm is to move                                                   
            self.set_east_tilt_from_counts(east_count,force_east_slow)
        elif es is None:
            # if only west arm is to move                                                   
            self.set_west_tilt_from_counts(west_count,force_west_slow)
        else:
            e_dir_speed = 2*ed + es
            w_dir_speed = 8*wd + 4*ws
            encoded_dir_speed = pack("B",e_dir_speed + w_dir_speed)
            data = encoded_count+encoded_dir_speed
            self._drive(drive_code,data)
        
    def set_east_tilt(self,east_tilt,force_slow=False):
        east_count,_ = self.tilts_to_counts(east_tilt,0)
        self.set_east_tilt_from_counts(east_count,force_slow)

    def set_east_tilt_from_counts(self,east_count,force_slow=False):
        drive_code = "2"
        encoded_count = codec.it_pack(east_count)
        ed,_,es,_ = self._prepare(east_count,None,force_slow,None)
        if es is None:
            raise InvalidCounts("E arm requested move of less than 40 counts")
        else:
            dir_speed = 2*ed + es
            encoded_dir_speed = pack("B",dir_speed)
            data = encoded_count+encoded_dir_speed
            self._drive(drive_code,data)

    def set_west_tilt(self,west_tilt,force_slow=False):
        _,west_count = self.tilts_to_counts(0,west_tilt)
        self.set_west_tilt_from_counts(west_count,force_slow)

    def set_west_tilt_from_counts(self,west_count,force_slow=False):
        drive_code = "3"
        data = codec.it_pack(west_count)
        _,wd,_,ws = self._prepare(None,west_count,None,force_slow)
        if ws is None:
            raise InvalidCounts("W arm requested move of less than 40 counts")
        else:
            dir_speed = 8*wd + 4*ws
            encoded_dir_speed = pack("B",dir_speed)
            data = encoded_count+encoded_dir_speed
            self._drive(drive_code,data)

    def _calculate_tilts(self,u_dict):
        et,wt = self.counts_to_tilts(u_dict["east_count"],u_dict["west_count"])
        u_dict["east_tilt"] = et
        u_dict["west_tilt"] = wt
        return u_dict
    
