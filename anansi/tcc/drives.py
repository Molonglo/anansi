from copy import copy
from threading import Thread,Event
from time import sleep
from struct import pack,unpack
from anansi import codec
from numpy import sin,arcsin
from anansi.anansi_logging import DataBaseLogger as LogDB
from anansi.comms import TCPClient
from anansi import exit_funcs
from anansi.config import config

# eZ80 flags for drive controller
DRIVE_FAST = 0
DRIVE_SLOW = 1
DRIVE_EAST = 0
DRIVE_WEST = 1 
DRIVE_NORTH = 0
DRIVE_SOUTH = 1

# eZ80 arm codes
BOTH_ARMS = "1"
EAST_ARM = "2"
WEST_ARM = "3"

# Drive States
# Drives support three states for each arm: auto, slow and disabled
AUTO = "auto"
SLOW = "slow"
DISABLED = "disabled"
VALID_STATES = [AUTO,SLOW,DISABLED]

DEFAULT_STATUS_DICT = {
    "east_count":0,
    "west_count":0,
    "east_status":"",
    "west_status":"",
    "east_tilt":0.0,
    "west_tilt":0.0
    }

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
        self.west_state = AUTO
        self.east_state = AUTO
        self.active_thread = None
        self._active = Event()
        self.event = Event()
        self.status_dict = copy(DEFAULT_STATUS_DICT)
        self.exit_funcs = exit_funcs
        self.exit_funcs.register(self.clean_up)
        self.log = LogDB()

    def clean_up(self):
        self._stop_active_drive()
        self.stop()
        self.exit_funcs.deregister(self.clean_up)

    def _check_state(self,state):
        if state not in VALID_STATES:
            raise Exception(
                "Invalid state: %s.\nValid states are: %s"%(
                    state,VALID_STATES))
        
    def set_east_state(self,state):
        self._check_state(state)
        self.east_state = state

    def set_west_state(self,state):
        self._check_state(state)
        self.west_state = state

    def get_east_state(self):
        return self.east_state
    
    def get_west_state(self):
        return self.west_state

    def _open_client(self):
        try:
            self.client = TCPClient(self._ip,self._port,timeout=self.timeout)
        except Exception as e:
            self.log.log_tcc_status(
                "BaseDriveInterface._open_client: %s:%d"%(self._ip,self._port),
                "error", str(e))
            raise e

    def _close_client(self):
        try:
            self.client.close()
            self.client = None
        except Exception as e:
            self.log.log_tcc_status(
                "BaseDriveInterface._close_client: %s:%d"%(self._ip,self._port),
                "error", str(e))
        
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

    def active(self):
        return self._active.is_set()
            
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
        except Exception as e:
            self.log.log_tcc_status(
                "BaseDriveInterface._drive_thread: %s:%d"%(self._ip,self._port),
                "error", str(e))
        finally:
            self._close_client()
            self._active.clear()

    def _drive(self,drive_code,data):
        """Send a drive command to the eZ80.                                                       
                                                                                                   
        Notes: This is first kill any active drive thread before                                   
        sending on a new command. Need to determine if any active                                  
        client should first be killed or not. This will spawn a drive                              
        thread to handle the drive loop of the eZ80.                                               
        """
        self._stop_active_drive()
        self._open_client()
        self._active.set()
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
            raise eZ80Error("Received unreconginsed command option from drive",self)
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
        if not self.active():
            self._open_client()
            try:
                self._send_message("U",None)
                code = None
                while code != "U":
                    code,response = self._parse_message(*self._receive_message())
                while code != "S":
                    code,_ = self._parse_message(*self._receive_message())
            except Exception as error:
                self.log.log_tcc_status(self.__class__.__name__,
                                        "warning","Could not get drive status: %s"%str(error))
            finally:
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

    def _prepare(self,east_counts=None,west_counts=None):
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
            elif abs(east_offset) <= self._slow_drive_limit or self.east_state == SLOW:
                east_speed = DRIVE_SLOW
            else:
                east_speed = DRIVE_FAST
        else:
            east_dir = None
            east_speed = None

        if west_counts is not None:
            west_offset = west_counts - status["west_count"]
            west_dir = self._get_direction(west_offset)
            if abs(west_offset) <= self._minimum_count_limit:
                west_speed = None
            elif abs(west_offset) <= self._slow_drive_limit or self.west_state == SLOW:
                west_speed = DRIVE_SLOW
            else:
                west_speed = DRIVE_FAST
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
        west_tilt = (west_counts-self._tilt_zero)/self._west_scaling
        return east_tilt,west_tilt

    def set_tilts(self,east_tilt,west_tilt):
        """Set the tilts of the E and W arm NS drives."""
        east_count,west_count = self.tilts_to_counts(east_tilt,west_tilt)
        self.set_tilts_from_counts(east_count,west_count)

    def set_tilts_from_counts(self,east_count,west_count):
        """Set the tilts of the E and W arm NS drives based on encoder counts."""
        if self.west_state == DISABLED and self.east_state == DISABLED:
            # Should log exception
            return
        elif self.west_state == DISABLED:
            self.set_east_tilt_from_counts(east_count)
        elif self.east_state == DISABLED:
            self.set_west_tilt_from_counts(west_count)
        else:
            encoded_count = codec.it_pack(east_count) + codec.it_pack(west_count)
            ed,wd,es,ws = self._prepare(east_count,west_count)
            if es is None and ws is None:
                # if neither arm will move more than 40 counts                                     
                message = "E and W arm requested move of less than %d counts"%self._minimum_count_limit
                raise CountError(message,self)
            elif ws is None:
                # if only east arm is to move                                                      
                self.set_east_tilt_from_counts(east_count)
            elif es is None:
                # if only west arm is to move                                                      
                self.set_west_tilt_from_counts(west_count)
            else:
                e_dir_speed = 2*ed + es
                w_dir_speed = 8*wd + 4*ws
                encoded_dir_speed = pack("B",e_dir_speed + w_dir_speed)
                data = encoded_count+encoded_dir_speed
                self._drive(BOTH_ARMS,data)

    def set_east_tilt(self,east_tilt):
        """Set tilt of east arm."""
        east_count,_ = self.tilts_to_counts(east_tilt,0)
        self.set_east_tilt_from_counts(east_count)

    def set_east_tilt_from_counts(self,east_count):
        """Set tilt of east arm base on encoder counts."""
        if self.east_state == DISABLED:
            # log an error here
            return
        else:
            encoded_count = codec.it_pack(east_count)
            ed,_,es,_ = self._prepare(east_count,None)
            if es is None:
                message = "E arm requested move of less than %d counts"%self._minimum_count_limit
                raise CountError(message,self)
            else:
                dir_speed = 2*ed + es
                encoded_dir_speed = pack("B",dir_speed)
                data = encoded_count+encoded_dir_speed
                self._drive(EAST_ARM,data)

    def set_west_tilt(self,west_tilt):
        """Set tilt of west arm."""
        _,west_count = self.tilts_to_counts(0,west_tilt)
        self.set_west_tilt_from_counts(west_count)

    def set_west_tilt_from_counts(self,west_count):
        """Set tilt of west arm base on encoder counts."""
        if self.west_state == DISABLED:
            return
        else:
            encoded_count = codec.it_pack(west_count)
            _,wd,_,ws = self._prepare(None,west_count)
            if ws is None:
                message = "W arm requested move of less than %d counts"%self._minimum_count_limit
                raise CountError(message,self)
            else:
                dir_speed = 8*wd + 4*ws
                encoded_dir_speed = pack("B",dir_speed)
                data = encoded_count+encoded_dir_speed
                self._drive(WEST_ARM,data)

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
    def __init__(self,drive_config=None):
        if drive_config is None:
            drive_config = config.ns_drive
        dc = drive_config
        super(NSDriveInterface,self).__init__(
            dc.node_name,dc.ip,dc.port,
            dc.west_scaling,dc.east_scaling,dc.tilt_zero,
            dc.minimum_counts,dc.slow_counts,
            dc.timeout)
        self.east_rate = dc.east_rate
        self.west_rate = dc.west_rate
        self.slow_factor = dc.slow_factor

    def get_east_rate(self):
        if self.east_state == SLOW:
            return self.east_rate * self.slow_factor 
        else:
            return self.east_rate

    def get_west_rate(self):
        if self.west_state == SLOW:
            return self.west_rate * self.slow_factor
        else:
            return self.west_rate

    def _get_direction(self,offset):
        return DRIVE_NORTH if offset >= 0 else DRIVE_SOUTH


class MDDriveInterface(DriveInterface):
    """Interface to eZ80 controlling Molonglo MD drives.                                           
                                                                                                   
    Notes: Key configuration parameters will be found in the                                       
    anansi.cfg configuration file for this interface.                                              
                                                                                                   
    Args:                                                                                          
    timeout -- acceptable timeout on socket connections to the eZ80                                
    """
    def __init__(self,drive_config=None):
        if drive_config is None:
            drive_config = config.md_drive
        dc = drive_config
        super(MDDriveInterface,self).__init__(
            dc.node_name,dc.ip,dc.port,
            dc.west_scaling,dc.east_scaling,dc.tilt_zero,
            dc.minimum_counts,dc.slow_counts,
            dc.timeout)
        self.east_rate = dc.east_rate
        self.west_rate = dc.west_rate
        self.slow_factor = dc.slow_factor

    def get_east_rate(self):
        if self.east_state == SLOW:
            return self.east_rate * self.slow_factor
        else:
            return self.east_rate

    def get_west_rate(self):
        if self.west_state == SLOW:
            return self.west_rate * self.slow_factor
        else:
            return self.west_rate
        
    def tilts_to_counts(self,east_tilt,west_tilt):
        """Convert tilts in radians to encoder counts."""
        east_counts = int(self._tilt_zero + self._east_scaling * sin(east_tilt))
        west_counts = int(self._tilt_zero + self._west_scaling * sin(west_tilt))
        return east_counts,west_counts

    def counts_to_tilts(self,east_counts,west_counts):
        """Convert encoder counts to tilts in radians."""
        east_tilt = arcsin((east_counts-self._tilt_zero)/self._east_scaling)
        west_tilt = arcsin((west_counts-self._tilt_zero)/self._west_scaling)
        return east_tilt,west_tilt

    def _get_direction(self,offset):
        return DRIVE_WEST if offset >= 0 else DRIVE_EAST
    
