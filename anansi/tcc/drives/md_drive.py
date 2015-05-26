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
    

    def __init__(self,timeout=2.0):
        super(MDDriveInterface,self).__init__(timeout)
        self.active_thread = None
        self.event = Event()
        self.status_dict = {}

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
        except eZ80MDError as e:
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
        """Log the position of the MD drives in the logging database.
        """

        self.log.log_position("md",
            self.status_dict["west_count"],
            self.status_dict["east_count"])
        
    def _parse_message(self,header,data):
        """Parse a message returned from the eZ80.

        This function parses all return values from the eZ80 and
        takes appropriate action. Actions taken are:

        Commands: I,W,V or S
        Response: Decode message data and log to DB

        Command: E
        Response: Decode message, log to DB and raise eZ80MDError

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
        if code == "E":
            raise eZ80MDError(decoded_response)
        if (code == "C") and (decoded_response >= 15):
            sleep(0.3)
        return code,decoded_response
    
    def get_status(self):
        """Get status dictionary for MD drive.

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
            west_dir = NORTH_OR_WEST if west_offset >= 0 else SOUTH_OR_EAST
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
        """Set the tilts of the E and W arm MD drives."""
        east_count,west_count = self.tilts_to_counts(east_tilt,west_tilt)
        self.set_tilts_from_counts(east_count,west_count,force_east_slow,force_west_slow)
        
    def set_tilts_from_counts(self,east_count,west_count,
                              force_east_slow=False,force_west_slow=False):
        """Set the tilts of the E and W arm MD drives based on encoder counts."""
        drive_code = "1"
        encoded_count = codec.it_pack(east_count) + codec.it_pack(west_count)
        ed,wd,es,ws = self._prepare(east_count,west_count,force_east_slow,force_west_slow)
        if es is None or ws is None:
            # if neither arm will move more than 40 counts              
            raise MDCountError("E or W arm requested move of less than 40 counts")
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
        """Set tilt of west arm."""
        _,west_count = self.tilts_to_counts(0,west_tilt)
        self.set_west_tilt_from_counts(west_count,force_slow)

    def set_west_tilt_from_counts(self,west_count,force_slow=False):
        """Set tilt of west arm base on encoder counts."""
        drive_code = "3"
        encoded_count = codec.it_pack(west_count)
        _,wd,_,ws = self._prepare(None,west_count,None,force_slow)
        if ws is None:
            raise InvalidCounts("W arm requested move of less than 40 counts")
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
    
