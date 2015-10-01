from threading import Event
from time import sleep
import copy
import logging
from lxml import etree
import ephem as eph
from anansi.comms import TCPServer,BaseHandler
from anansi.utils import gen_xml_element
from anansi import exit_funcs
from anansi import log
logger = logging.getLogger('anansi')

DRIVE_ARM_STATUS = {
    "count":0,
    "tilt":0.0,
    "driving":False,
    "state":"auto",
    "on_target":False,
    "system_status":""
    }

STATUS_DICT_DEFAULTS = {
    "error_string":"",
    "RA":"00:00:00",
    "Dec":"00:00:00",
    "HA":"0.0",
    "Glat":"0.0",
    "Glon":"0.0",
    "Elat":"0.0",
    "Elon":"0.0",
    "Alt":"0.0",
    "Az":"0.0",
    "NS":"0.0",
    "EW":"0.0",
    "LMST":"00:00:00",
    "ns":{
        "error":"",
        "east":copy.copy(DRIVE_ARM_STATUS),
        "west":copy.copy(DRIVE_ARM_STATUS)
        },
    "md":{
        "error":"",
        "east":copy.copy(DRIVE_ARM_STATUS),
        "west":copy.copy(DRIVE_ARM_STATUS)
        },
    }


class StatusRequestHandler(BaseHandler):
    def handle(self):
        try:
            self.server.update()
        except Exception as error:
            logger.error("Could not update status server",extra=log.tcc_status(),exc_info=True)
            self.request.send("Error on status request: %s"%str(error))
            return 
    
        try:
            xml = self.server.get_xml_status()
            response = etree.tostring(xml,encoding='ISO-8859-1')
        except Exception as error:
            logger.error("Could not create XML status message",extra=log.tcc_status(),exc_info=True)
            self.request.send("Error on status request: %s"%str(error))
        else:
            self.request.send(response)


class StatusServer(TCPServer):
    def __init__(self,ip,port,controller):
        TCPServer.__init__(self,ip,port,handler_class=StatusRequestHandler)
        self.status_dict = STATUS_DICT_DEFAULTS
        self.controller = controller

    def _get_drive_info(self,drive,drive_name):
        status = drive.status_dict
        for arm in ['east','west']:
            self.status_dict[drive_name][arm]['count'] = status['%s_count'%arm]
            self.status_dict[drive_name][arm]['system_status'] = status['%s_status'%arm]
            self.status_dict[drive_name][arm]['tilt'] = status.get('%s_tilt'%arm,0.0) + getattr(drive,"%s_offset"%arm)
            self.status_dict[drive_name][arm]['state'] = getattr(drive,"%s_state"%arm)
            if self.controller.current_track is not None:
                self.status_dict[drive_name][arm]['on_target'] = self.controller.current_track.on_target(drive_name,arm)
            self.status_dict[drive_name][arm]['driving'] = getattr(drive,"%s_active"%arm)()


    def update(self):
        if self.controller.coordinates is not None:
            coords = self.controller.coordinates.new_instance()
            coords.compute()
            pos_dict = {
                "RA":str(coords.ra),
                "Dec":str(coords.dec),
                "HA":str(coords.ha),
                "Glat":str(float(coords.glat)),
                "Glon":str(float(coords.glon)),
                "Elat":str(coords.elat),
                "Elon":str(coords.elon),
                "Alt":str(float(coords.alt)),
                "Az":str(float(coords.az)),
                "NS":str(float(coords.ns)),
                "EW":str(float(coords.ew)),
                "LMST":str(coords.lst)
                }
            self.status_dict.update(pos_dict)
        self._get_drive_info(self.controller.ns_drive,"ns")
        self._get_drive_info(self.controller.md_drive,"md")
        self.status_dict['ns']['error'] = str(self.controller.ns_drive.error_state)
        self.status_dict['md']['error'] = str(self.controller.md_drive.error_state)

    def _xml_from_key(self,key):
        return gen_xml_element(key,str(self.status_dict[key]))

    def get_xml_status(self):
        root = gen_xml_element("tcc_status")
        overview = gen_xml_element("overview")
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

        def _append(root,arm,drive):
            root.append(gen_xml_element("tilt",str(self.status_dict[drive][arm]['tilt'])))
            root.append(gen_xml_element("count",str(self.status_dict[drive][arm]['count'])))
            root.append(gen_xml_element("driving",str(self.status_dict[drive][arm]['driving'])))
            root.append(gen_xml_element("state",str(self.status_dict[drive][arm]['state'])))
            root.append(gen_xml_element("on_target",str(self.status_dict[drive][arm]['on_target'])))
            root.append(gen_xml_element("system_status",str(self.status_dict[drive][arm]['system_status'])))
            
        for drive in ["ns","md"]:
            _drive = gen_xml_element(drive)
            _drive.append(gen_xml_element('error',str(self.status_dict[drive]['error'])))
            for arm in ["east","west"]:
                _arm = gen_xml_element(arm)
                _append(_arm,arm,drive)
                _drive.append(_arm)
            root.append(_drive)
        return root

if __name__ == "__main__":
    from anansi.config import update_config_from_args,config
    from anansi import args
    from anansi.tcc.telescope_controller import TelescopeController
    from time import sleep
    update_config_from_args(args.parse_anansi_args())
    s = config.status_server
    controller = TelescopeController()
    server = StatusServer(s.ip,s.port,controller)
    server.start()
    while not server.shutdown_requested.is_set():
        sleep(1.0)
