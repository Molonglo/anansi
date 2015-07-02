from anansi.logging_db import MolongloLoggingDataBase as LogDB
from anansi.comms import TCPClient
from anansi import exit_funcs
from threading import Thread,Event
from time import sleep
from struct import pack,unpack
from anansi import codec
from os import environ,path
from numpy import sin,arcsin
from ConfigParser import ConfigParser

config_path = environ["ANANSI_CONFIG"]
config = ConfigParser()
config.read(path.join(config_path,"anansi.cfg"))
NS_CONTROLLER_IP = config.get("IPAddresses","ns_controller_ip")
NS_CONTROLLER_PORT = config.getint("IPAddresses","ns_controller_port")
NS_NODE_NAME = config.get("DriveParameters","ns_node_name")
NS_WEST_SCALING = config.getfloat("DriveParameters","ns_west_scaling")
NS_EAST_SCALING = config.getfloat("DriveParameters","ns_east_scaling")
NS_TILT_ZERO = config.getfloat("DriveParameters","ns_tilt_zero")
NS_MIN_COUNTS = config.getfloat("DriveParameters","ns_minimum_counts")
NS_SLOW_COUNTS = config.getfloat("DriveParameters","ns_slow_counts")
MD_CONTROLLER_IP = config.get("IPAddresses","md_controller_ip")
MD_CONTROLLER_PORT = config.getint("IPAddresses","md_controller_port")
MD_NODE_NAME = config.get("DriveParameters","md_node_name")
MD_WEST_SCALING = config.getfloat("DriveParameters","md_west_scaling")
MD_EAST_SCALING = config.getfloat("DriveParameters","md_east_scaling")
MD_TILT_ZERO = config.getfloat("DriveParameters","md_tilt_zero")
MD_MIN_COUNTS = config.getfloat("DriveParameters","md_minimum_counts")
MD_SLOW_COUNTS = config.getfloat("DriveParameters","md_slow_counts")
FAST = 0
SLOW = 1
EAST = 1
WEST = 0 
NORTH = 0
SOUTH = 1

class eZ80Error(Exception):
    """Generic exception returned from eZ80

    Notes: This will automatically send a logging message to the
    logging database.

    Args:
    code -- Error code from eZ80
    """
    def __init__(self,code,drive_obj):
        message = "Exception E:%d caught from drive"%(code)
        super(eZ80Error,self).__init__(message)
        LogDB().log_tcc_status(drive_obj.__class__.__name__,
                               "error",message)


class CountError(Exception):
    """Exception for when number of counts is invalid

    Notes: This will automatically send a logging message to the
    logging database. This should be treated as a warning for mos
    use cases.

    Args:
    count -- the invalid requested coun
    """
    def __init__(self,message,drive_obj):
        super(CountError,self).__init__(message)
        LogDB().log_tcc_status(drive_obj.__class__.__name__,
                               "warning",message)


class DriveInterface(object):
    _data_decoder = [
        ("east_status" ,lambda x: unpack("B",x)[0],1),
        ("east_count"   ,lambda x: codec.it_unpack(x),3),
        ("west_status" ,lambda x: unpack("B",x)[0],1),
        ("west_count"   ,lambda x: codec.it_unpack(x),3)]

    def __init__(self,
                 node,ip,port,
                 west_scaling,east_scaling,tilt_zero,
                 minimum_count_limit,slow_drive_limit,
                 timeout=5.0):
        self._node = node
        self._ip = ip
        self._port = port
        self._west_scaling = west_scaling
        self._east_scaling = east_scaling
        self._tilt_zero= tilt_zero
        self._minimum_count_limit = minimum_count_limit
        self._slow_drive_limit = slow_drive_limit
        self.timeout = timeout
        self.client = None
        decoder,size = codec.gen_header_decoder(self._node)
        self.header_decoder = decoder
        self.header_size = size
        self.west_disabled = False
        self.east_disabled = False
        self.active_thread = None
        self.event = Event()
        self.status_dict = {}
        self.exit_funcs = exit_funcs
        self.exit_funcs.register(self.clean_up)
        self.log = LogDB()

    def clean_up(self):
        self._stop_active_drive()
        self.stop()
        self.exit_funcs.deregister(self.clean_up)

    def disable_east_arm(self):
        self.east_disabled = True

    def disable_west_arm(self):
        self.west_disabled = True

    def enable_east_arm(self):
        self.east_disabled = False

    def enable_west_arm(self):
        self.west_disabled = False

    def _open_client(self):
        if self.client is None:
            try:
                self.client = TCPClient(self._ip,self._port,timeout=self.timeout)
            except Exception as e:
                self.log.log_tcc_status("BaseDriveInterface._open_client",
                                        "error", str(e))
                raise e

    def _close_client(self):
        if self.client is not None:
            self.client.close()
            self.client = None

    def _receive_message(self):
        response = self.client.receive(self.header_size)
        header = codec.simple_decoder(response,self.header_decoder)
        data_size = header["HOB"]*256+header["LOB"]
        if data_size > 0:
            data = self.client.receive(data_size)
        else:
            data = None
        return header,data

    def _send_message(self,code,data=None):
        header,msg = codec.simple_encoder(self._node,code,data)
        self.client.send(header)
        if len(msg)>0:
            self.client.send(msg)

        if data:
            data_repr = unpack("B"*len(data),data)
            self.log.log_eZ80_command(code,str(data_repr))
        else:
            self.log.log_eZ80_command(code,"None")

    def _stop_active_drive(self):
        """Stop active drive thread without requesting telescope stop.                             
                                                                                                   
        Notes: This will kill the active drive thread by setting                                   
        the stop event. It will not try and stop the telescope.                                    
        Need to think about what this means to the eZ80 and if                                     
        this should include and explicit stop command.                                             
        """
        self.event.set()
        if self.active_thread:
            self.active_thread.join()
        self.active_thread = None
        self.event.clear()
        self._close_client()
        
    def _drive_thread(self):
        """A thread to handle the eZ80 status loop while driving.                                  
                                                                                                   
        Notes: Method is intended to be run as a thread. By setting                                
        the event object of this class, the drive thread will be                                   
        stopped.                                                                                   
        """
        try:
            while not self.event.is_set():
                code,response = self._parse_message(*self._receive_message())
                if (code == "I") and (response == 0):
                    break
        except eZ80Error as e:
            raise e
        finally:
            self._close_client()

    def _drive(self,drive_code,data):
        """Send a drive command to the eZ80.                                                       
                                                                                                   
        Notes: This is first kill any active drive thread before                                   
        sending on a new command. Need to determine if any active                                  
        client should first be killed or not. This will spawn a drive                              
        thread to handle the drive loop of the eZ80.                                               
        """
        self._stop_active_drive()
        self._open_client()
        self._send_message(drive_code,data)
        while True:
            code,response = self._parse_message(*self._receive_message())
            if (code == "S") and (response == 0):
                self.active_thread = Thread(target=self._drive_thread)
                self.active_thread.daemon = True
                self.active_thread.start()
                break

    def _log_position(self):
        """Log the position of the drives in the logging database.                              
        """
        self.log.log_position(self.__class__.__name__,
            self.status_dict["west_count"],
            self.status_dict["east_count"])

    def _parse_message(self,header,data):
        """Parse a message returned from the eZ80.                                                 
                                                                                                   
        This function parses all return values from the eZ80 and                                   
        takes appropriate action. Actions taken are:                                               
                                                                                                   
        Commands: I,W,V or S                                                                       
        Response: Decode message data and log to DB                                                
                                                                                                   
        Command: E                                                                                 
        Response: Decode message, log to DB and raise eZ80NSError                                  
                                                                                                   
        Command: U                                                                                 
        Response: Decode message log tilt counts to DB and update status                           
                                                                                                   
        Command: C                                                                                 
        Response: Sleep 300 ms. This is for potential problems with                                
        socket collision on the eZ80.                                                              
                                                                                                   
        Returns: eZ80 error code, decoded message                                                  
        """

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
            self.log.log_eZ80_status(code,decoded_response)
        if code == "E":
            raise eZ80Error(decoded_response,self)
        if (code == "C") and (decoded_response >= 15):
            sleep(0.3)
        return code,decoded_response

    def get_status(self):
        """Get status dictionary for NS drive.                                                     
                                                                                                   
        Notes: If telescope is on an active drive this will not send                               
        a new request, instead returning the current status dictionary.                            
                                                                                                   
        Returns: Status dictionary                                                                 
        """
        if not self.active_thread:
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
        """Send stop command to eZ80.                                                              
                                                                                                   
        Notes: This will first kill any active drive thread before sending.                        
        """

        self._stop_active_drive()
        self._open_client()
        self._send_message("0",None)
        code = None
        while code != "S":
            code,_ = self._parse_message(*self._receive_message())
        self._close_client()

    def _get_direction(self,offset):
        return 1 if offset >= 0 else 0

    def _prepare(self,east_counts=None,west_counts=None,
                 force_east_slow=False,force_west_slow=False):
        """Prepare values for drive message.                                                       
                                                                                                   
        Notes: This method is used to translate counts to directions                               
        and to work out the desired speeds for driving the motors at.                              
                                                                                                   
        Args:                                                                                      
        east_counts -- desired east arm counts                                                     
        west_counts -- desired west arm counts                                                     
        force_east_slow -- boolean flag to east arm to drive slowly                                
        force_west_slow -- boolean flag to west arm to drive slowly                                
                                                                                                   
        Returns: (east arm direction, west arm direction,                                          
                  east arm speed, west arm speed)                                                  
        """

        status = self.get_status()
        if east_counts is not None:
            east_offset = east_counts - status["east_count"]
            east_dir = self._get_direction(east_offset)
            if abs(east_offset) <= self._minimum_count_limit:
                east_speed = None
            elif abs(east_offset) <= self._slow_drive_limit or force_east_slow:
                east_speed = SLOW
            else:
                east_speed = FAST
        else:
            east_dir = None
            east_speed = None

        if west_counts is not None:
            west_offset = west_counts - status["west_count"]
            west_dir = self._get_direction(west_offset)
            if abs(west_offset) <= self._minimum_count_limit:
                west_speed = None
            elif abs(west_offset) <= self._slow_drive_limit or force_west_slow:
                west_speed = SLOW
            else:
                west_speed = FAST
        else:
            west_dir = None
            west_speed = None
    
        return east_dir,west_dir,east_speed,west_speed

    def tilts_to_counts(self,east_tilt,west_tilt):
        """Convert tilts in radians to encoder counts."""
        east_counts = int(self._tilt_zero + self._east_scaling * east_tilt)
        west_counts = int(self._tilt_zero + self._west_scaling * west_tilt)
        return east_counts,west_counts
  
    def counts_to_tilts(self,east_counts,west_counts):
        """Convert encoder counts to tilts in radians."""
        east_tilt = (east_counts-self._tilt_zero)/self._east_scaling
        west_tilt = (west_counts-self._tilt_zero)/self._east_scaling
        return east_tilt,west_tilt

    def set_tilts(self,east_tilt,west_tilt,
                  force_east_slow=False,force_west_slow=False):
        """Set the tilts of the E and W arm NS drives."""
        east_count,west_count = self.tilts_to_counts(east_tilt,west_tilt)
        self.set_tilts_from_counts(east_count,west_count,
                                   force_east_slow,force_west_slow)

    def set_tilts_from_counts(self,east_count,west_count,
                              force_east_slow=False,force_west_slow=False):
        """Set the tilts of the E and W arm NS drives based on encoder counts."""
        drive_code = "1"
        if self.west_disabled and self.east_disabled:
            return
        elif self.west_disabled:
            self.set_east_tilt_from_counts(east_count,force_east_slow)
        elif self.east_disabled:
            self.set_west_tilt_from_counts(west_count,force_west_slow)
        else:
            encoded_count = codec.it_pack(east_count) + codec.it_pack(west_count)
            ed,wd,es,ws = self._prepare(east_count,west_count,force_east_slow,force_west_slow)
            if es is None or ws is None:
                # if neither arm will move more than 40 counts                                     
                message = "E or W arm requested move of less than %d counts"%self._minimum_count_limit
                raise CountError(message,self)
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
        """Set tilt of east arm."""
        east_count,_ = self.tilts_to_counts(east_tilt,0)
        self.set_east_tilt_from_counts(east_count,force_slow)

    def set_east_tilt_from_counts(self,east_count,force_slow=False):
        """Set tilt of east arm base on encoder counts."""
        if self.east_disabled:
            return
        else:
            drive_code = "2"
            encoded_count = codec.it_pack(east_count)
            ed,_,es,_ = self._prepare(east_count,None,force_slow,None)
            if es is None:
                message = "E or W arm requested move of less than %d counts"%self._minimum_count_limit
                raise CountError(message,self)
            else:
                dir_speed = 2*ed + es
                encoded_dir_speed = pack("B",dir_speed)
                data = encoded_count+encoded_dir_speed
                self._drive(drive_code,data)

    def set_west_tilt(self,west_tilt,force_slow=False):
        """Set tilt of west arm."""
        _,west_count = self.tilts_to_counts(0,west_tilt)
        self.set_west_tilt_from_counts(west_count,force_slow)

    def set_west_tilt_from_counts(self,west_count,force_slow=False):
        """Set tilt of west arm base on encoder counts."""
        if self.west_disabled:
            return
        else:
            drive_code = "3"
            encoded_count = codec.it_pack(west_count)
            _,wd,_,ws = self._prepare(None,west_count,None,force_slow)
            if ws is None:
                message = "E or W arm requested move of less than %d counts"%self._minimum_count_limit
                raise CountError(message,self)
            else:
                dir_speed = 8*wd + 4*ws
                encoded_dir_speed = pack("B",dir_speed)
                data = encoded_count+encoded_dir_speed
                self._drive(drive_code,data)

    def _calculate_tilts(self,u_dict):
        """Update status dictionary to converts counts to tilts."""
        et,wt = self.counts_to_tilts(u_dict["east_count"],u_dict["west_count"])
        u_dict["east_tilt"] = et
        u_dict["west_tilt"] = wt
        return u_dict


class NSDriveInterface(DriveInterface):
    """Interface to eZ80 controlling Molonglo NS drives.                                           
                                                                                                   
    Notes: Key configuration parameters will be found in the                                       
    anansi.cfg configuration file for this interface.                                              
                                                                                                   
    Args:                                                                                          
    timeout -- acceptable timeout on socket connections to the eZ80                                
    """
    def __init__(self,
                 node = NS_NODE_NAME,
                 ip = NS_CONTROLLER_IP,
                 port = NS_CONTROLLER_PORT,
                 west_scaling = NS_WEST_SCALING,
                 east_scaling = NS_EAST_SCALING,
                 tilt_zero = NS_TILT_ZERO,
                 minimum_count_limit = NS_MIN_COUNTS,
                 slow_drive_limit = NS_SLOW_COUNTS,
                 timeout = 5.0):
        super(NSDriveInterface,self).__init__(
            node,ip,port,
            west_scaling,east_scaling,tilt_zero,
            minimum_count_limit,slow_drive_limit,
            timeout)

    def _get_direction(self,offset):
        return NORTH if offset >= 0 else SOUTH


class MDDriveInterface(DriveInterface):
    """Interface to eZ80 controlling Molonglo MD drives.                                           
                                                                                                   
    Notes: Key configuration parameters will be found in the                                       
    anansi.cfg configuration file for this interface.                                              
                                                                                                   
    Args:                                                                                          
    timeout -- acceptable timeout on socket connections to the eZ80                                
    """
    def __init__(self,
                 node = MD_NODE_NAME,
                 ip = MD_CONTROLLER_IP,
                 port = MD_CONTROLLER_PORT,
                 west_scaling = MD_WEST_SCALING,
                 east_scaling = MD_EAST_SCALING,
                 tilt_zero = MD_TILT_ZERO,
                 minimum_count_limit = MD_MIN_COUNTS,
                 slow_drive_limit = MD_SLOW_COUNTS,
                 timeout = 5.0):
        super(MDDriveInterface,self).__init__(
            node,ip,port,
            west_scaling,east_scaling,tilt_zero,
            minimum_count_limit,slow_drive_limit,
            timeout)

    def tilts_to_counts(self,east_tilt,west_tilt):
        """Convert tilts in radians to encoder counts."""
        east_counts = int(self._tilt_zero + self._east_scaling * sin(east_tilt))
        west_counts = int(self._tilt_zero + self._west_scaling * sin(west_tilt))
        return east_counts,west_counts

    def counts_to_tilts(self,east_counts,west_counts):
        """Convert encoder counts to tilts in radians."""
        east_tilt = arcsin((east_counts-self._tilt_zero)/self._east_scaling)
        west_tilt = arcsin((west_counts-self._tilt_zero)/self._east_scaling)
        return east_tilt,west_tilt

    def _get_direction(self,offset):
        return EAST if offset >= 0 else WEST

    def zero_meridian_drives(self,arm="B",start=1):
        self._stop_active_drive()
        self._open_client()
        data = arm+pack("B",start)
        self._send_message("R",data)
        code = None
        while code != "S":
            code,_ = self._parse_message(*self._receive_message())
        self._close_client()
