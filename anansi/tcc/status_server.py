from threading import Event
from anansi.comms import TCPServer,BaseHandler
from time import sleep
from lxml import etree
from anansi.utils import gen_xml_element
from anansi.logging_db import MolongloLoggingDataBase as LogDB
from anansi import exit_funcs
import ephem as eph
import copy

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
    "Elat":"",
    "Elon":"",
    "Alt":"",
    "Az":"",
    "NS":"",
    "EW":"",
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


class StatusRequestHandler(BaseHandler):
    def handle(self):
        try:
            self.server.update()
        except Exception as error:
            self.request.send(str(error))
        else:
            xml = self.server.get_xml_status()
            try:
                response = etree.tostring(xml,encoding='ISO-8859-1')
            except Exception as error:
                self.request.send(str(error))
            else:
                self.request.send(response)


class StatusServer(TCPServer):
    def __init__(self,ip,port,controller):
        TCPServer.__init__(self,ip,port,handler_class=StatusRequestHandler)
        self.status_dict = STATUS_DICT_DEFAULTS
        self.controller = controller

    def update(self):
        status = self.controller.ns_drive.get_status()
        for key,val in status.items():
            new_key = "_ns_".join(key.split("_"))
            self.status_dict[new_key] = val
            print new_key,val
        status = self.controller.md_drive.get_status()
        for key,val in status.items():
            new_key = "_md_".join(key.split("_"))
            self.status_dict[new_key] = val
            print new_key,val
        print
        print "Coordinates:",self.controller.coordinates
        print    
        if self.controller.coordinates is not None:
            coords = copy.copy(self.controller.coordinates)
            coords.compute()
            pos_dict = {
                "RA":str(coords.ra),
                "Dec":str(coords.dec),
                "HA":str(coords.ha),
                "Glat":str(coords.glat),
                "Glon":str(coords.glon),
                "Elat":str(coords.elat),
                "Elon":str(coords.elon),
                "Alt":str(coords.alt),
                "Az":str(coords.az),
                "NS":str(coords.ns),
                "EW":str(coords.ew),
                "LMST":str(coords.lst)
                }
            self.status_dict.update(pos_dict)

    def _xml_from_key(self,key):
        return gen_xml_element(key,str(self.status_dict[key]))

    def get_xml_status(self):
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
        request.append(self._xml_from_key("EW"))
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
    import os
    from ConfigParser import ConfigParser
    config_path = os.environ["ANANSI_CONFIG"]
    config = ConfigParser()
    config.read(os.path.join(config_path,"anansi.cfg"))
    STATUS_IP = config.get("IPAddresses","status_ip")
    STATUS_PORT = config.getint("IPAddresses","status_port")
    server = StatusServer(STATUS_IP,STATUS_PORT)
    server.start()
    while True:
        sleep(1.0)
