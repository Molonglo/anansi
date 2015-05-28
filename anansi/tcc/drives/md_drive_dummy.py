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
from time import sleep
from ConfigParser import ConfigParser

config_path = os.environ["ANANSI_CONFIG"]
config = ConfigParser()
config.read(os.path.join(config_path,"anansi.cfg"))
MD_CONTROLLER_IP = config.get("IPAddresses","md_controller_ip")
MD_CONTROLLER_PORT = config.getint("IPAddresses","md_controller_port")
MD_NODE_NAME = config.get("DriveParameters","md_node_name")
MD_WEST_SCALING = config.getfloat("DriveParameters","md_west_scaling")
MD_EAST_SCALING = config.getfloat("DriveParameters","md_east_scaling")
MD_TILT_ZERO = config.getfloat("DriveParameters","md_tilt_zero")
FAST = 0
SLOW = 1
NORTH_OR_WEST = 0
SOUTH_OR_EAST = 1

class eZ80MDError(Exception):
    """Generic exception returned from eZ80 
    
    Notes: This will automatically send a logging message to the 
    logging database. 

    Args: 
    code -- Error code from eZ80
    """

    def __init__(self,code):
        message = "Exception E:%d caught from MD drive eZ80"%(code)
        super(eZ80MDError,self).__init__(message)
        LogDB().log_tcc_status("MDDriveInterface","error",message)


class MDCountError(Exception):
    """Exception for when number of counts is invalid

    Notes: This will automatically send a logging message to the
    logging database. This should be treated as a warning for most 
    use cases.

    Args:
    count -- the invalid requested count
    """

    def __init__(self,message):
        super(MDCountError,self).__init__(message)
        LogDB().log_tcc_status("MDDriveInterface","warning",message)



class MDDriveInterface(BaseDriveInterface):
    """Interface to eZ80 controlling Molonglo MD drives.

    Notes: Key configuration parameters will be found in the 
    anansi.cfg configuration file for this interface.

    Args:
    timeout -- acceptable timeout on socket connections to the eZ80
    """
    _node = MD_NODE_NAME
    _ip = MD_CONTROLLER_IP
    _port = MD_CONTROLLER_PORT
    _west_scaling = MD_WEST_SCALING
    _east_scaling = MD_EAST_SCALING
    _tilt_zero = MD_TILT_ZERO
    _data_decoder = [
        ("east_status" ,lambda x: unpack("B",x)[0],1),
        ("east_count"   ,lambda x: codec.it_unpack(x),3),
        ("west_status" ,lambda x: unpack("B",x)[0],1),
        ("west_count"   ,lambda x: codec.it_unpack(x),3)]
    

    def __init__(self,timeout=2.0,east_disabled=False,west_disabled=False):
        super(MDDriveInterface,self).__init__(timeout)
        self.active_thread = None
        self.event = Event()
        self.status_dict = {}
        self.east_disabled = east_disabled
        self.west_disabled = west_disabled


    def get_status(self):
        return self.status_dict

    def stop(self):
        pass

    def set_tilts(self,east_tilt,west_tilt,
                  force_east_slow=False,force_west_slow=False):
        pass

    def set_tilts_from_counts(self,east_count,west_count,
                              force_east_slow=False,force_west_slow=False):
        pass
        
    def set_east_tilt(self,east_tilt,force_slow=False):
        pass

    def set_east_tilt_from_counts(self,east_count,force_slow=False):
        pass

    def set_west_tilt(self,west_tilt,force_slow=False):
        pass

    def set_west_tilt_from_counts(self,west_count,force_slow=False):
        pass

    
