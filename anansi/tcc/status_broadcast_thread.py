import os
import logging
from threading import Thread,Event
from multiprocessing import Manager
from Queue import Queue
from anansi.comms import TCPClient,TCPServer,UDPSender
from time import sleep
from lxml import etree
from anansi.utils import gen_xml_element
from ConfigParser import ConfigParser

#temporary
logging.basicConfig()

config_path = os.environ["ANANSI_CONFIG"]
config = ConfigParser()
config.read(os.path.join(config_path,"anansi.cfg"))

STATUS_BROADCAST_IP = config.get("IPAddresses","status_broadcast_ip")
STATUS_BROADCAST_PORT = config.getint("IPAddresses","status_broadcast_port")

STATUS_DICT_DEFAULTS = {
    "at_limits":False,
    "has_coordinates":False,
    "on_target":False,
    "tracking":False,
    "slewing":False,
    "error_string":"",
    "RA":"", 
    "Dec":"",
    "HA":"",
    "Glat":"",
    "Glon":"",
    "Alt":"",
    "Az":"",
    "NS":"",
    "MD":"",
    "LMST":"",
    "west_ns_tilt":"",
    "west_ns_status":"",
    "west_ns_on_target":False,
    "west_ns_at_limit":False,
    "west_md_tilt":"",
    "west_md_status":"",
    "west_md_on_target":False,
    "west_md_at_limit":False,
    "east_ns_tilt":"",
    "east_ns_status":"",
    "east_ns_on_target":False,
    "east_ns_at_limit":False,
    "east_md_tilt":"",
    "east_md_status":"",
    "east_md_on_target":False,
    "east_md_at_limit":False
    }

class StatusBroadcaster(Thread):
    _ip,_port = STATUS_BROADCAST_IP,STATUS_BROADCAST_PORT
    def __init__(self,status_dict=None,interval=1.0):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.client = UDPSender(self._ip,self._port)
        self.status_dict = Manager().dict()
        self.status_dict.update(STATUS_DICT_DEFAULTS)
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
                    
    def _xml_from_key(self,key):
        return gen_xml_element(key,str(self.status_dict[key]))

    def form_status_msg(self):
        root = gen_xml_element("tcc_status")
        overview = gen_xml_element("overview")
        overview.append(self._xml_from_key("at_limits"))
        overview.append(self._xml_from_key("has_coordinates"))
        overview.append(self._xml_from_key("tracking"))
        overview.append(self._xml_from_key("slewing"))
        overview.append(self._xml_from_key("error_string"))
        root.append(overview)
        
        request = gen_xml_element("coordinates")
        request.append(self._xml_from_key("RA"))
        request.append(self._xml_from_key("Dec"))
        request.append(self._xml_from_key("HA"))
        request.append(self._xml_from_key("Glat"))
        request.append(self._xml_from_key("Glon"))
        request.append(self._xml_from_key("Alt"))
        request.append(self._xml_from_key("Az"))
        request.append(self._xml_from_key("NS"))
        request.append(self._xml_from_key("MD"))
        request.append(self._xml_from_key("LMST"))
        root.append(request)
        
        def _append(root,ew,nsmd):
            prefix = "%s_%s"%(ew,nsmd)
            root.append(self._xml_from_key("%s_tilt"%prefix))
            root.append(self._xml_from_key("%s_status"%prefix))
            root.append(self._xml_from_key("%s_on_target"%prefix))
            root.append(self._xml_from_key("%s_at_limit"%prefix))

        arms = gen_xml_element("arms")
        west_arm = gen_xml_element("west_arm")
        west_arm_ns = gen_xml_element("ns_drive")
        _append(west_arm_ns,"west","ns")
        west_arm_md = gen_xml_element("md_drive")
        _append(west_arm_md,"west","md")
        west_arm.append(west_arm_md)
        arms.append(west_arm)
        east_arm = gen_xml_element("east_arm")
        east_arm_ns = gen_xml_element("ns_drive")
        _append(east_arm_ns,"east","ns")
        east_arm.append(east_arm_ns)
        east_arm_md = gen_xml_element("md_drive")
        _append(east_arm_md,"east","md")
        east_arm.append(east_arm_md)
        arms.append(east_arm)
        root.append(arms)
        return root

