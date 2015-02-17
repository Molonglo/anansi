from threading import Thread,Event
from Queue import Queue
import utils
from comms import TCPClient,TCPServer,UDPSender
from coordinates import Coordinates
from coordinates import d2r,r2d
from struct import pack,unpack
from time import sleep,time
import ctypes as C
import ip_addresses as ips
import numpy as np
import logging
from lxml import etree
from env_daemon import EnvMonitor
from utils import gen_xml_element
from daemon import Daemon
from logging.config import fileConfig
fileConfig("/home/dada/ewan/Soft/anansi_ver2.0/anansi/tcc_logger.cfg")

#Soft limits
MD_UPPER_LIMIT = d2r(64.0)
MD_LOWER_LIMIT = d2r(-64.0)
NS_UPPER_LIMIT = d2r(53.0)
NS_LOWER_LIMIT = d2r(-53.0)

#Hard limits
HARD_MD_UPPER_LIMIT = d2r(65.0)
HARD_MD_LOWER_LIMIT = d2r(-65.0)
HARD_NS_UPPER_LIMIT = d2r(54.0)
HARD_NS_LOWER_LIMIT = d2r(-54.0)

#Drive speeds
NS_SPEED = d2r(5)/60.0 # radians per second
MD_SPEED = d2r(3)/60.0 # radians per second
 
#Pointing tolerance for on_target tests
TOLERANCE_MD = d2r(0.1)
TOLERANCE_NS = d2r(0.4)

#Preset positions
WIND_STOW_NSEW = (0.0,0.0)              # radians
MAINTENANCE_STOW_NSEW = (d2r(45.0),0.0) # radians

#Wind speed
WIND_LIMIT = 70 # km/h

SLEWING_UPDATE = 1 # seconds
TRACKING_UPDATE = 1 # seconds


class BaseHardwareController(object):
    """Abstract base class for control of MOST eZ80 controllers.

    Inheriting classes must define:
    _ip     - the IP address of the board to be accessed
    _port   - the port number of the board to be accessed
    _node   - the MOST communication protocol string (e.g. "TCC_TDC0")
    
    This class is designed only to work with the MOST style communication 
    protocol. Here all "set" commands for telescope parameters are send only
    operations and all "get" commands receive a command specific return message.
    Both "get" and "set" commands are defined by a single character command code
    which in the case of "set" commands may be followed by packed binary data.
    """
    def __init__(self,timeout):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.timeout = timeout
        decoder,size = utils.gen_header_decoder(self._node)
        self.header_decoder = decoder
        self.header_size = size
        
    def set(self,code,data=None,client=None):
        if client is None:
            client = TCPClient(self._ip,self._port,timeout=self.timeout)
        header,msg = utils.simple_encoder(self._node,code,data)
        self.logger.debug("Encoding message. Node: %s, Code: %s, Data: %s"%(repr(self._node),repr(code),repr(data)))
        self.logger.debug("Sending header to drive. Header: %s"%(header))
        client.send(header)
        if len(msg) > 0:
            self.logger.debug("Sending message to drive. Msg: %s"%(repr(msg)))
            client.send(msg)

    def get(self,code,response_decoder):
        client = TCPClient(self._ip,self._port,timeout=self.timeout)
        self.set(code,client=client)
        response = client.receive(self.header_size)
        header = utils.simple_decoder(response,self.header_decoder)
        data_size = header["HOB"]*256+header["LOB"]
        data = client.receive(data_size)
        decoded_response = utils.simple_decoder(data,response_decoder)

        dr = decoded_response
        print_response = "|---- East arm: %.2f deg (%d) ----|---- West arm: %.2f deg (%d) ----|---- Difference (e-w): %.2f deg ----|"%(
            r2d(dr["east_tilt"]),dr["east_status"],r2d(dr["west_tilt"]),dr["west_status"],r2d(dr["east_tilt"])-r2d(dr["west_tilt"]))

        self.logger.info(print_response)
        return decoded_response

    
class BaseTiltController(BaseHardwareController):
    """Abstract base class for control of the MOST tilt drives. 
    
    Tilt values are controlled through sending of the desired number
    of encoder counts (rotations of the drive shaft for either MD or NS).
    To this end inheriting classes define:
    _east_scaling - encoder counts per radian of tilt for east arm
    _west_scaling - encoder counts per radian of tilt for west arm
    _tilt_zero        - encoder counts at zenith
    """
    def __init__(self,timeout):
        self._response_decoder = [
            ("east_status" ,lambda x: unpack("B",x)[0],1),
            ("east_tilt"   ,lambda x: self._decode_tilt(x,self._east_scaling), 3),
            ("west_status" ,lambda x: unpack("B",x)[0],1),
            ("west_tilt"   ,lambda x: self._decode_tilt(x,self._west_scaling), 3)]
        super(BaseTiltController,self).__init__(timeout)
            
    def _decode_tilt(self,x,scaling):
        counts = utils.it_unpack(x)
        tilt = (counts-self._tilt_zero)/scaling
        return tilt

    def set_tilt(self,east_tilt,west_tilt=None):
        if west_tilt is None:
            west_tilt = east_tilt
        east_counts = int(self._tilt_zero + self._east_scaling * east_tilt)
        west_counts = int(self._tilt_zero + self._west_scaling * west_tilt)
        data = utils.it_pack(east_counts) + utils.it_pack(west_counts)
        self.set("1",data)

    def get_state(self):
        return self.get("U",self._response_decoder)

    def stop(self):
        self.set("0")


class NSController(BaseTiltController):
    _node         = "TCC_TDC0"
    _ip,_port     = ips.NS_CONTROLLER
    _west_scaling = 23623.049893243842
    _east_scaling = 23623.049893243842
    _tilt_zero    = 32768.0
    def __init__(self,timeout=5.0):
        super(NSController,self).__init__(timeout)
        
    def _decode_tilt(self,x,scaling):
        return super(NSController,self)._decode_tilt(x,scaling)


class MDController(BaseTiltController):
    _node         = "TCC_MDC0"
    _ip,_port     = ips.MD_CONTROLLER
    _west_scaling = 136450.0
    _east_scaling = 136450.0
    _tilt_zero    = 8388608.0
    def __init__(self,timeout=5.0):
        super(MDController,self).__init__(timeout)
    
    def _decode_tilt(self,x,scaling):
        return np.arcsin(super(MDController,self)._decode_tilt(x,scaling))
    
    def set_tilt(self,east_tilt,west_tilt=None):
        if west_tilt is None:
            west_tilt = east_tilt
        super(MDController,self).set_tilt(np.sin(east_tilt),np.sin(west_tilt))


class StatusBroadcaster(Thread):
    _ip,_port = ips.TCC_STATUS
    def __init__(self,controller,interface,interval=1.0):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.client = UDPSender(self._ip,self._port)
        self.controller = controller
        self.interface = interface
        self.interval = interval
        self._shutdown = Event()
        Thread.__init__(self)

    def shutdown(self):
        self.logger.info("Setting shutdown status")
        self._shutdown.set()

    def run(self):
        while not self._shutdown.is_set():
            sleep(self.interval)
            msg = self.form_status_msg()
            try:
                self.client.send(etree.tostring(msg,encoding='ISO-8859-1'))
            except:
                self.logger.error("Could not send status broadcast.")
                    
    def _gen_element(self,name,text=None,attributes=None):
        root = etree.Element(name)
        if attributes is not None:
            for key,val in attributes.items():
                root.attrib[key] = val
        if text is not None:
            root.text = text
        return root

    def form_status_msg(self):
        root = gen_xml_element("tcc_status")
        coords = self.controller.coordinates
        env = self.controller.env
        overview = gen_xml_element("overview")
        overview.append(gen_xml_element("at_limits",str(self.controller.at_limits)))
        overview.append(gen_xml_element("at_hard_limits",str(self.controller.at_hard_limits)))
        overview.append(gen_xml_element("has_coordinates",str(self.controller.coordinates is not None)))
        overview.append(gen_xml_element("on_target",str(self.controller.on_target)))
        overview.append(gen_xml_element("tracking",str(self.controller.tracking_enabled)))
        overview.append(gen_xml_element("slewing",str(self.controller.slewing)))
        overview.append(gen_xml_element("high_wind",str(self.controller.high_wind)))
        overview.append(gen_xml_element("error_string",str(self.controller.error_message)))
        root.append(overview)
        
        interface = gen_xml_element("interface")
        interface.append(gen_xml_element("controlled_by",str(self.interface.username)))
        interface.append(gen_xml_element("comment",str(self.interface.user_comment)))
        interface.append(gen_xml_element("locked",str(self.interface.lockout)))
        interface.append(gen_xml_element("override_mode",str(self.interface.user_override)))
        interface.append(gen_xml_element("admin_mode",str(self.interface.admin_mode)))
        root.append(interface)
        
        """
        environment = gen_xml_element("environment")
        for key in env.state.keys():
            subnode = gen_xml_element(key)
            subnode.append(gen_xml_element("value",str(env.state[key])))
            ar = env.buffers[key].get()
            subnode.append(gen_xml_element("mean",str(ar.mean())))
            subnode.append(gen_xml_element("std",str(ar.std())))
            subnode.append(gen_xml_element("median",str(np.median(ar))))
            environment.append(subnode)
        root.append(environment)
        """

        if coords is not None:
            request = gen_xml_element("coordinates")
            if coords.system != "nsew":
                request.append(gen_xml_element("RA",text=str(coords.a_ra)))
                request.append(gen_xml_element("Dec",text=str(coords.a_dec)))
                request.append(gen_xml_element("HA",text=str(coords.ha)))
                request.append(gen_xml_element("Glat",text=str(coords.glat)))
                request.append(gen_xml_element("Glon",text=str(coords.glon)))
                request.append(gen_xml_element("Alt",text=str(coords.alt)))
                request.append(gen_xml_element("Az",text=str(coords.az)))
            request.append(gen_xml_element("NS",text=str(r2d(coords.ns))))
            request.append(gen_xml_element("MD",text=str(r2d(coords.ew))))
            request.append(gen_xml_element("LMST",text=str(coords.lst)))
            root.append(request)
    
        ns_state = self.controller.ns_state
        md_state = self.controller.md_state
        ot_state = self.controller._on_target
        lim_state = self.controller._at_limits
        
        arms = gen_xml_element("arms")
        west_arm = gen_xml_element("west_arm")
        west_arm_ns = gen_xml_element("ns_drive")
        west_arm_ns.append(gen_xml_element("tilt",str(r2d(ns_state["west_tilt"]))))
        west_arm_ns.append(gen_xml_element("status",str(ns_state["west_status"])))
        west_arm_ns.append(gen_xml_element("at_limit",str(lim_state["ns_west"])))
        west_arm_ns.append(gen_xml_element("on_target",str(ot_state["ns_west"])))
        west_arm.append(west_arm_ns)
        west_arm_md = gen_xml_element("md_drive")
        west_arm_md.append(gen_xml_element("tilt",str(r2d(md_state["west_tilt"]))))
        west_arm_md.append(gen_xml_element("status",str(md_state["west_status"])))
        west_arm_md.append(gen_xml_element("at_limit",str(lim_state["md_west"])))
        west_arm_md.append(gen_xml_element("on_target",str(ot_state["md_west"])))
        west_arm.append(west_arm_md)
        arms.append(west_arm)
        east_arm = gen_xml_element("east_arm")
        east_arm_ns = gen_xml_element("ns_drive")
        east_arm_ns.append(gen_xml_element("tilt",str(r2d(ns_state["east_tilt"]))))
        east_arm_ns.append(gen_xml_element("status",str(ns_state["east_status"])))
        east_arm_ns.append(gen_xml_element("at_limit",str(lim_state["ns_east"])))
        east_arm_ns.append(gen_xml_element("on_target",str(ot_state["ns_east"])))
        east_arm.append(east_arm_ns)
        east_arm_md = gen_xml_element("md_drive")
        east_arm_md.append(gen_xml_element("tilt",str(r2d(md_state["east_tilt"]))))
        east_arm_md.append(gen_xml_element("status",str(md_state["east_status"])))
        east_arm_md.append(gen_xml_element("at_limit",str(lim_state["md_east"])))
        east_arm_md.append(gen_xml_element("on_target",str(ot_state["md_east"])))
        east_arm.append(east_arm_md)
        arms.append(east_arm)
        root.append(arms)
        return root


class TrackingMonitor(Thread):
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.tracking_enabled = False
        self.slewing = True
        self._shutdown = Event()
        self.on_target = False
        self.at_limits = False
        self.at_hard_limits = False
        self.high_wind = False
        self._last_update_time = 0
        self._at_limits = {            
            "ns_east":False,
            "ns_west":False,
            "md_east":False,
            "md_west":False
            }
        self._at_hard_limits = self._at_limits.copy()
        self._on_target = self._at_limits.copy()
        self.md_drive = MDController(timeout=0.5)
        self.ns_drive = NSController(timeout=2.5)
        self.md_state = self.md_drive.get_state()
        self.ns_state = self.ns_drive.get_state()
        self.last_state_update = time()
        self.env = EnvMonitor(600.0,10.0)
        self.env.start()
        self.coordinates = None
        self.error_message = ""
        Thread.__init__(self)

    def set_coordinates(self,coords):
        self.coordinates = coords
        self.logger.info("Setting coordinates: %s"%(repr(self.coordinates)))
        try:
            self._update_position()
        except Exception as error:
            return error
        else:
            self.logger.info("Setting slewing=True")
            self.slewing = True
            return self.error_message

    def _test_if_beyond_limits(self,value,upper,lower):
        if value < lower:
            return lower,True
        elif value > upper:
            return upper,True
        else:
            return value,False
        
    def _distance_from_source(self):
        self.coordinates._compute()
        ew_offset = abs(self.coordinates.ew-self.md_state["east_tilt"])
        ns_offset = abs(self.coordinates.ns-self.ns_state["east_tilt"])
        return np.sqrt(ew_offset**2 + ns_offset**2)


    def _update_position(self):
        try:
            self.coordinates._compute()
        except:
            self.logger.error("Could not compute new coordinates.")
        
        ew_pos,soft_ew_limit = self._test_if_beyond_limits(self.coordinates.ew,
                                                           MD_UPPER_LIMIT,
                                                           MD_LOWER_LIMIT)
        ns_pos,soft_ns_limit = self._test_if_beyond_limits(self.coordinates.ns,
                                                           NS_UPPER_LIMIT,
                                                           NS_LOWER_LIMIT)
        
        self.logger.info("Desired coordinates (ns,ew) = (%.2f,%.2f)"%(r2d(self.coordinates.ns),r2d(self.coordinates.ew)))
        self.logger.info("Filtered coordinates (ns,ew) = (%.2f,%.2f)"%(r2d(ns_pos),r2d(ew_pos)))
        self.logger.info("Sending coordinates to drive")
        
        try:
            self.md_drive.set_tilt(ew_pos)
            self.ns_drive.set_tilt(ns_pos)
            self.md_drive.set_tilt(ew_pos)
            self.ns_drive.set_tilt(ns_pos)
        except Exception as error:
            self.logger.error("Could not set tilts.")

        if soft_ew_limit and soft_ns_limit:
            self.error_message = "Requested position is beyond NS and EW limits."
        elif soft_ew_limit:
            self.error_message = "Requested position is beyond EW limits."
        elif soft_ns_limit:
            self.error_message = "Requested position is beyond NS limits."
        else:
            self.error_message = ""

        if self.error_message != "":
            self.logger.info("Status: %s"%(self.error_message))

        self._last_update_time = time()

    def stop(self):
        self.logger.info("Stopping telescope drives")
        self.tracking_enabled = False
        self.logger.info("Disabling tracking")
        self.slewing = False
        self.logger.info("Setting slewing=False")
        try:
            self.md_drive.stop()
            self.ns_drive.stop()
            self.md_drive.stop()
            self.ns_drive.stop()
        except:
            self.logger.error("Could not stop the telescope drives.")

    def wind_stow(self):
        self.logger.info("Sending telescope to wind stow.")
        self.tracking_enabled = False
        self.logger.info("Disabling tracking")
        coords = Coordinates(*WIND_STOW_NSEW,system="nsew")
        self.set_coordinates(coords)
        return self.error_message

    def check_at_limits(self):
        self._at_limits = {
            "md_east": not (MD_LOWER_LIMIT < self.md_state["east_tilt"] < MD_UPPER_LIMIT),
            "md_west": not (MD_LOWER_LIMIT < self.md_state["west_tilt"] < MD_UPPER_LIMIT),
            "ns_east": not (NS_LOWER_LIMIT < self.ns_state["east_tilt"] < NS_UPPER_LIMIT),
            "ns_west": not (NS_LOWER_LIMIT < self.ns_state["west_tilt"] < NS_UPPER_LIMIT)
            }
        return any(self._at_limits.values())

    def check_at_hard_limits(self):
        self._at_hard_limits = {
            "md_east": not (HARD_MD_LOWER_LIMIT < self.md_state["east_tilt"] < HARD_MD_UPPER_LIMIT),
            "md_west": not (HARD_MD_LOWER_LIMIT < self.md_state["west_tilt"] < HARD_MD_UPPER_LIMIT),
            "ns_east": not (HARD_NS_LOWER_LIMIT < self.ns_state["east_tilt"] < HARD_NS_UPPER_LIMIT),
            "ns_west": not (HARD_NS_LOWER_LIMIT < self.ns_state["west_tilt"] < HARD_NS_UPPER_LIMIT)
            }
        return any(self._at_hard_limits.values())

    def check_on_target(self):
        self._on_target = { 
            "md_east": abs(self.md_state["east_tilt"] - self.coordinates.ew)<TOLERANCE_MD,
            "md_west": abs(self.md_state["west_tilt"] - self.coordinates.ew)<TOLERANCE_MD,
            "ns_east": abs(self.ns_state["east_tilt"] - self.coordinates.ns)<TOLERANCE_NS,
            "ns_west": abs(self.ns_state["west_tilt"] - self.coordinates.ns)<TOLERANCE_NS
            }
        return all(self._on_target.values())

    def shutdown(self):
        self.logger.info("Shutting down tracking monitor")
        self.stop()
        self._shutdown.set()
        self.env.stop()

    def check_high_wind(self):
        return self.env.state["wind_speed"] > WIND_LIMIT
    
    def _above_jump_limit(self,drive,key):
        if self.last_state_update is None:
            return False
        
        elapsed = time() - self.last_state_update
        if drive == "md":
            diff = abs(self.md_state[key]-self.prev_md_state[key])
            return diff/elapsed > 4*MD_SPEED
        elif drive == "ns":
            diff = abs(self.ns_state[key]-self.prev_ns_state[key])
            return diff/elapsed > 4*NS_SPEED
        else:
            return False
                
    def _check_drive_jumps(self):
        if self.prev_md_state is not None:
            if self._above_jump_limit("md","east_tilt"):
                self.logger.warning("Meridian drive jump on east arm.")
                #self.md_state["east_tilt"] = self.prev_md_state["east_tilt"]
                
            if self._above_jump_limit("md","west_tilt"):
                self.logger.warning("Meridian drive jump on west arm.")
                #self.md_state["west_tilt"] = self.prev_md_state["west_tilt"]
                
            if self._above_jump_limit("ns","east_tilt"):
                self.logger.warning("North-South drive jump on east arm.")
                #self.ns_state["east_tilt"] = self.prev_ns_state["east_tilt"]
                
            if self._above_jump_limit("ns","west_tilt"):
                self.logger.warning("North-South drive jump on west arm.")
                #self.ns_state["west_tilt"] = self.prev_ns_state["west_tilt"]
                
    def _check_jumps(self,new,old,speed,elapsed_time):
        ediff = abs(new["east_tilt"]-old["east_tilt"])
        wdiff = abs(new["west_tilt"]-old["west_tilt"])
        return (ediff/elapsed_time > 4*speed or wdiff/elapsed_time >4*speed)
            
    def get_drive_states(self):
        elapsed = time()-self.last_state_update
        new_md_state = self.md_drive.get_state()
        new_ns_state = self.ns_drive.get_state()
        md_jump = self._check_jumps(new_md_state,self.md_state,MD_SPEED,elapsed)
        ns_jump = self._check_jumps(new_ns_state,self.ns_state,NS_SPEED,elapsed)
        if not md_jump and not ns_jump:
            self.md_state = new_md_state
            self.ns_state = new_ns_state
            self.last_state_update = time()
        elif md_jump:
            self.logger.warning("Registered MD drive jump.")
        elif ns_jump:
            self.logger.warning("Registered NS drive jump.")
                                  
    def run(self):
        while not self._shutdown.is_set():
            sleep(1.0)
            try:
                self.get_drive_states()
            except Exception as error:
                self.logger.error("Could not read drive states.")
                self.stop()
                print error
                continue

            self.at_hard_limits = self.check_at_hard_limits()
            if self.at_hard_limits:
                self.logger.warning("Telescope at hard limits.")
                self.stop()
                self.wind_stow()
                self.logger.warning("Sleeping for 60 seconds.")
                sleep(60.0)
                continue
                
            #self.high_wind = self.check_high_wind()
            if self.high_wind:
                self.wind_stow()
                continue

            self.at_limits = self.check_at_limits()
            if self.coordinates is None:
                self.logger.warning("Telescope at soft limits.")
                continue

            self.on_target =  self.check_on_target()
            if self.on_target:
                self.logger.info("Registered on target, setting slewing=False.")
                self.slewing = False

            time_since_update = time()-self._last_update_time
            self.logger.debug("Time since last drive update: %d seconds."%(int(time_since_update)))

            #distance_from_source = self._distance_from_source()
            #print "Distance:",distance_from_source,TOLERANCE

            if self.slewing and time_since_update > SLEWING_UPDATE:
                self.logger.info("Updating coordinates for slew.")
                try:
                    self._update_position()
                except Exception as error:
                    print error

            elif not self.slewing and self.tracking_enabled and time_since_update > TRACKING_UPDATE:
                self.slewing = False
                self.logger.info("Updating coordinates for track.")
                try:
                    self._update_position()
                except Exception as error:
                    print error
                    

class TCCResponse(object):
    def __init__(self):
        self.msg = etree.Element('tcc_reply')
        
    def __str__(self):
        return etree.tostring(self.msg,encoding='ISO-8859-1').replace("\n","")
    
    def error(self,error_str):
        node = etree.Element("error")
        node.text = error_str
        self.msg.append(node)
        
    def success(self,message):
        node = etree.Element("success")
        node.text = message
        self.msg.append(node)

        
class TCCRequest(object):
    def __init__(self,xml_string):
        self.username = None
        self.user_comment = None
        self.server_command = None
        self.tcc_command = None
        self.tcc_info = None
        self.tracking_mode = None
        self.coordinates = None
        self.msg = etree.fromstring(xml_string)
        self.parse_user_info()
        self.parse_server_commands()
        self.parse_tcc_commands()
    
    def parse_user_info(self):
        user_info = self.msg.find("user_info")
        self.username = user_info.find("name").text.strip()
        try:
            self.user_comment = user_info.find("comment").text.strip()
        except:
            pass

    def parse_server_commands(self):
        server_cmds = self.msg.find("server_command")
        if server_cmds is not None:
            self.server_command = server_cmds.find("command").text.strip()
    
    def parse_tcc_commands(self):
        tcc_cmd = self.msg.find("tcc_command")
        if tcc_cmd is not None:
            self.tcc_command = tcc_cmd.find("command").text.strip()
            if self.tcc_command == "point":
                pointing = tcc_cmd.find("pointing")
                self.tcc_info = {
                    "system":pointing.attrib.get("system","equatorial").strip(),
                    "tracking":pointing.attrib.get("tracking","on").strip(),
                    "units":pointing.attrib.get("units","radians").strip(),
                    "epoch":pointing.attrib.get("epoch","2000").strip(),
                    "x":pointing.find("xcoord").text.strip(),
                    "y":pointing.find("ycoord").text.strip()
                    }
                if self.tcc_info["units"] in ["radians","degrees"]:
                    self.tcc_info["x"] = float(self.tcc_info["x"])
                    self.tcc_info["y"] = float(self.tcc_info["y"])
                self.tcc_info["tracking"] = self.tcc_info["tracking"] == "on"

                    
class UserInterface(Thread):
    """Class to act as interface to the TCC.

    All access to the TCC will be handled through a socket, with users
    having the ability to lockout the TCC from other users. A skeleton
    key mode will allow an override mode of the lockout, but this will 
    be restricted.

    The interface is a simple TCP/IP socket and the message is in XML
    format containing required data. The actual contents of the message
    will be outlined elsewhere.

    While the server thread handles all communication, a separate queue 
    system will be maintainted for control of the telescope.
    """
    _admin_ip = '172.17.227.103'
    
    def __init__(self,controller):
        self.server  = TCPServer(*ips.MPSRTCC)
        self.server_thread = Thread(target=self.server.serve_forever)
        self.server_thread.start()
        self.status_broadcast = StatusBroadcaster(controller,self)
        self.status_broadcast.start()
        self.username = ""
        self.user_comment = ""
        self.lockout  = True
        self.user_override = False
        self.admin_mode = True
        self._shutdown = Event()
        self.telescope_control = controller
        Thread.__init__(self)

    def valid_user(self,username):
        if (self.override or self.username is "" or username == self.username):
            self.username = username
            return True
        else:
            return False

    def shutdown(self):
        self.telescope_control.stop()
        self.telescope_control.shutdown()
        self.status_broadcast.shutdown()
        self.server.shutdown()
        self._shutdown.set()
        response.success("Sent shutdown")
        return response
        
    def parse_message(self,msg):
        request = TCCRequest(msg)
        response = TCCResponse()
        
        self.admin_mode = self.server.client_address[0] == self._admin_ip

        if self.lockout and not self.admin_mode:
            response.error("TCC locked in admin mode")
            return response
                    
        if request.server_command == "unlock" and self.admin_mode:
            self.lockout = False
            self.username = ""
            response.success("Unlocked TCC")
            return response
        
        if request.server_command == "lock" and self.admin_mode:
            self.lockout = True
            response.success("Locked TCC")
            return response

        self.user_override = request.server_command == "override"
        
        if self.user_override or self.admin_mode or self.username == request.username:
            self.username = request.username
            self.user_comment = request.user_comment
        else:
            response.error("TCC under control of %s"%(self.username))
            return response
                    
        if request.server_command == "shutdown":
            self.shutdown()

        tcc_error = ""
        if request.tcc_command == "point":
            info = request.tcc_info
            coords = Coordinates(info["x"],info["y"],system=info["system"],
                                 units=info["units"],epoch=info["epoch"])
            self.telescope_control.tracking_enabled = bool(info["tracking"])
            tcc_error = self.telescope_control.set_coordinates(coords)
            
        elif request.tcc_command == "wind_stow":
            tcc_error = self.telescope_control.wind_stow()
                    
        elif request.tcc_command == "maintenance_stow":
            self.telescope_control.tracking_enabled = False
            coords = Coordinates(*MAINTENANCE_STOW_NSEW,system="nsew")
            tcc_error = self.telescope_control.set_coordinates(coords)

        elif request.tcc_command == "stop":
            self.telescope_control.tracking_enabled = False
            self.telescope_control.stop()
            
        else:
            tcc_error = "Unknown TCC command"
            
        if tcc_error is not "":
            response.error(repr(tcc_error))
        else:
            response.success("TCC command passed")
        
        return response

    def run(self):
        while not self._shutdown.is_set():
            if self.server.recv_q.empty():
                sleep(1.0)
                continue
            msg = self.server.recv_q.get()
            try:
                response = self.parse_message(msg)
            except Exception as error:
                response = TCCResponse()
                response.error(repr(error))
            self.server.send_q.put(str(response))
           
 
def main():
    controller = TrackingMonitor()
    interface = UserInterface(controller)
    controller.start()
    interface.start()

if __name__ == "__main__":
    main()

        
        
