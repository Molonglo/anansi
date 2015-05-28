import os
from threading import Thread,Event
from anansi.comms import TCPServer
from time import sleep
from lxml import etree
from anansi.utils import gen_xml_element
from ConfigParser import ConfigParser
from anansi.logging_db import MolongloLoggingDataBase as LogDB
from anansi import exit_funcs

config_path = os.environ["ANANSI_CONFIG"]
config = ConfigParser()
config.read(os.path.join(config_path,"anansi.cfg"))
STATUS_IP = config.get("IPAddresses","status_ip")
STATUS_PORT = config.getint("IPAddresses","status_port")

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
    "west_ns_count":0,
    "west_ns_status":"",
    "west_ns_on_target":False,
    "west_ns_at_limit":False,
    "west_md_tilt":"",
    "west_md_count":0,
    "west_md_status":"",
    "west_md_on_target":False,
    "west_md_at_limit":False,
    "east_ns_tilt":"",
    "east_ns_count":0,
    "east_ns_status":"",
    "east_ns_on_target":False,
    "east_ns_at_limit":False,
    "east_md_tilt":"",
    "east_md_count":0,
    "east_md_status":"",
    "east_md_on_target":False,
    "east_md_at_limit":False
    }

class StatusServer(Thread):
    def __init__(self,interval=1.0):
        Thread.__init__(self)
        exit_funcs.register(self.shutdown)
        self.server  = TCPServer(STATUS_IP,STATUS_PORT)
        self.server_thread = Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        self._shutdown = Event()
        self.status_dict = {}
        self.status_dict.update(STATUS_DICT_DEFAULTS)
        self.interval = interval
        self.log = LogDB()

    def shutdown(self):
        self._shutdown.set()
        self.server.shutdown()
        self.server_thread.join()
        del self.status_dict
        exit_funcs.deregister(self.shutdown)

    def update(self,x):
        self.status_dict["RA"] = x

    
    def run(self):
        while not self._shutdown.is_set():
            if self.server.recv_q.empty():
                sleep(1.0)
                continue
            self.server.recv_q.get()
            msg = self.form_status_msg()
            try:
                response = etree.tostring(msg,encoding='ISO-8859-1')
            except Exception as error:
                self.server.send_q.put(str(error))
            else:
                self.server.send_q.put(str(response))

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
            root.append(self._xml_from_key("%s_count"%prefix))
            root.append(self._xml_from_key("%s_status"%prefix))
            root.append(self._xml_from_key("%s_on_target"%prefix))
            root.append(self._xml_from_key("%s_at_limit"%prefix))

        arms = gen_xml_element("arms")
        west_arm = gen_xml_element("west_arm")
        west_arm_ns = gen_xml_element("ns_drive")
        _append(west_arm_ns,"west","ns")
        west_arm.append(west_arm_ns)
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

if __name__ == "__main__":
    server = StatusServer()
    server.start()
    ii = 0
    while not server._shutdown.is_set():
        ii+=1
        server.update(str(ii))
        sleep(1.0)
    server.join()
