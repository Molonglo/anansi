from threading import Thread,Event,Timer
from Queue import Queue
from time import sleep
from lxml import etree
import logging
from anansi import exit_funcs
from anansi import log
from anansi.tcc import drives
from anansi.comms import TCPServer,BaseHandler
from anansi.tcc.coordinates import make_coordinates
from anansi.tcc.telescope_controller import TelescopeController
logger = logging.getLogger('anansi')

class InvalidTCCCommand(Exception):
    def __init__(self,xml):
        message = "Invalid command message sent to TCC: %s"%xml
        logger.error(message,extra=log.tcc_status(),exc_info=True)
        super(InvalidTCCMessage,self).__init__(message)

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
        self.server_command = None
        self.tcc_command = None
        self.tcc_info = None
        self.tracking_mode = None
        self.coordinates = None
        self.user = None
        self.comment = None
        self.east_state = drives.DISABLED
        self.west_state = drives.DISABLED
        self.msg = etree.fromstring(xml_string)
        self.parse_user()
        self.parse_server_commands()
        self.parse_tcc_commands()

    def parse_user(self):
        tcc_request = self.msg.find("tcc_request")
        if tcc_request:
            user_info = tcc_request.find("user_info")
            if user_info:
                self.user = user_info.find("name").text
                self.comment = user_info.find("comment").text

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
                arm_status = tcc_cmd.find("arms")
                self.east_state = arm_status.find("east").text
                self.west_state = arm_status.find("west").text
                

class TCCRequestHandler(BaseHandler):
    def handle(self):
        msg = self.request.recv(8192)
        response = self.server.parse_message(msg)
        self.request.send(str(response))
        if self.server.shutdown_requested.is_set():
            self.server.shutdown()
        

class TCCServer(TCPServer):
    def __init__(self,ip,port,controller):
        TCPServer.__init__(self,ip,port,handler_class=TCCRequestHandler)
        self.controller = controller
        self.shutdown_requested = Event()

    def parse_message(self,msg):
        logger.info("Parsing received TCC command: %s"%msg,extra=log.tcc_status())
        _xml_str = msg.replace("'","").replace("\n","")
        response = TCCResponse()
        try:
            request = TCCRequest(msg)

            if not request.server_command and not request.tcc_command:
                raise InvalidTCCCommand(_xml_str)
            
            if request.server_command:
                logger.info("Received server command '%s'"%(request.server_command),
                            extra=log.tcc_command(request.server_command,_xml_str,request.user))
                if request.server_command == "shutdown":
                    self.shutdown_requested.set()
                elif request.server_command == "ping":
                    pass
                else:
                    raise InvalidTCCCommand(_xml_str)
                
            if request.tcc_command:
                logger.info("Received tcc command: %s"%(request.tcc_command),
                            extra=log.tcc_command(request.tcc_command,_xml_str,request.user))
                if request.tcc_command == "point":
                    logger.info("Setting east arm state: %s"%request.east_state,extra=log.tcc_status())
                    self.controller.set_east_state(request.east_state)
                    logger.info("Setting west arm state: %s"%request.west_state,extra=log.tcc_status())
                    self.controller.set_west_state(request.west_state)
                    info = request.tcc_info
                    coords = make_coordinates(info["x"],info["y"],system=info["system"],
                                              units=info["units"],epoch=info["epoch"])
                    logger.info("Generated coordinates object of type %s"%type(coords),extra=log.tcc_status())
                    logger.info("Setting tracking status to %s"%info["tracking"],extra=log.tcc_status())
                    self.controller.observe(coords,track=info['tracking'])
                elif request.tcc_command == "wind_stow":
                    self.controller.wind_stow()
                elif request.tcc_command == "maintenance_stow":
                    self.controller.maintenance_stow()
                elif request.tcc_command == "stop":
                    self.controller.stop()
                else:
                    raise InvalidTCCCommand(_xml_str)
        except Exception as error:
            logger.error("Exception encountered during parsing of TCC command message",
                         extra=log.tcc_status(),exc_info=True)
            response.error("TCC command failed: %s"%str(error))
        else:
            response.success("TCC command passed")
        return response
           
