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
from ConfigParser import ConfigParser

config_path = os.environ["ANANSI_CONFIG"]
config = ConfigParser()
config.read(os.path.join(config_path,"anansi.cfg"))

STATUS_BROADCAST_IP = config.get("IPAddresses","status_broadcast_ip")
STATUS_BROADCAST_PORT = config.get("IPAddresses","status_broadcast_port")

class StatusBroadcaster(Thread):
    _ip,_port = STATUS_BROADCAST_IP,STATUS_BROADCAST_PORT
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

