from threading import Thread,Event,Timer
from Queue import Queue
from time import sleep
from lxml import etree
from anansi import exit_funcs
from anansi.comms import TCPServer,BaseHandler
from anansi.tcc.coordinates import Coordinates
from anansi.tcc.telescope_controller import TelescopeController
from anansi.logging_db import MolongloLoggingDataBase as LogDB

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
        self.east_arm_active = True
        self.west_arm_active = True
        self.force_east_slow = False
        self.force_west_slow = False
        self.msg = etree.fromstring(xml_string)
        self.parse_server_commands()
        self.parse_tcc_commands()

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
                east = arm_status.find("east")
                west = arm_status.find("west")
                pointing.attrib.get("system","equatorial")
                if east.text.strip() == "disabled":
                    self.east_arm_active = False
                if west.text.strip() == "disabled":
                    self.west_arm_active = False
                self.force_east_slow = east.attrib.get("speed","auto") == "slow"
                self.force_west_slow = west.attrib.get("speed","auto") == "slow"


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
        self.log = LogDB()

    def parse_message(self,msg):
        self.log.log_tcc_status("TCCServer.parse_message","info",msg)
        response = TCCResponse()
        try:
            request = TCCRequest(msg)
            
            if not request.server_command and not request.tcc_command:
                raise Exception("No valid command given")
            
            if request.server_command:
                if request.server_command == "shutdown":
                    self.log.log_tcc_status("TCCServer.parse_message","info",
                                            "Received shutdown message")
                    self.shutdown_requested.set()
                else:
                    raise Exception("Unknown server command")
                
            if request.tcc_command:
                if request.east_arm_active:
                    self.log.log_tcc_status("TCCServer.parse_message","info",
                                            "Enabling east arm")
                    self.controller.enable_east_arm()
                else:
                    self.log.log_tcc_status("TCCServer.parse_message","info",
                                            "Disabling east arm")
                    self.controller.disable_east_arm()
                    
                if request.west_arm_active:
                    self.log.log_tcc_status("TCCServer.parse_message","info",
                                            "Enabling west arm")
                    self.controller.enable_west_arm()
                else:
                    self.log.log_tcc_status("TCCServer.parse_message","info",
                                            "Disabling west arm")
                    self.controller.disable_west_arm()

                if request.tcc_command == "point":
                    info = request.tcc_info
                    self.log.log_tcc_status("TCCServer.parse_message","info",
                                            "Received pointing command: %s"%repr(info))
                    if info["units"] == "counts":
                        if info["system"] != "nsew":
                            raise Exception("Can only point in nsew coordinates when given counts")
                        else:
                            self.controller.ns_drive.set_tilts_from_counts(
                                int(info["x"]),int(info["y"]),
                                force_east_slow=request.force_east_slow,
                                force_west_slow=request.force_west_slow)
                            #MD drive command will go here when MD drive implemented
                    else:
                        coords = Coordinates(info["x"],info["y"],system=info["system"],
                                             units=info["units"],epoch=info["epoch"])
                        if info["tracking"]:
                            self.log.log_tcc_status("TCCServer.parse_message","info",
                                                    "Requesting source track")
                            self.controller.track(coords)
                        else:
                            self.log.log_tcc_status("TCCServer.parse_message","info",
                                                    "Requesting drive to source")
                            self.controller.drive_to(coords)
        
                elif request.tcc_command == "wind_stow":
                    print
                    print "WIND STOW"
                    print
                    self.log.log_tcc_status("TCCServer.parse_message","info",
                                            "Recieved wind stow command")
                    self.controller.wind_stow()
                    
                elif request.tcc_command == "maintenance_stow":
                    self.log.log_tcc_status("TCCServer.parse_message","info",
                                            "Recieved maintenance stow command")
                    self.controller.maintenance_stow()
                    
                elif request.tcc_command == "stop":
                    self.log.log_tcc_status("TCCServer.parse_message","info",
                                            "Recieved stop command")
                    self.controller.stop()
                else:
                    raise Exception("Unknown TCC command")

        except Exception as error:
            self.log.log_tcc_status("TCCServer.parse_message","error",str(error))
            response.error(str(error))
        else:
            response.success("TCC command passed")
        return response
           
if __name__ == "__main__":
    import os
    from ConfigParser import ConfigParser
    config_path = os.environ["ANANSI_CONFIG"]
    config = ConfigParser()
    config.read(os.path.join(config_path,"anansi.cfg"))
    ANANSI_SERVER_IP = config.get("IPAddresses","anansi_ip")
    ANANSI_SERVER_PORT = config.getint("IPAddresses","anansi_port")
    controller = TelescopeController()
    server = TCCServer(ANANSI_SERVER_IP,ANANSI_SERVER_PORT,controller)
    server.start()
    while not server.shutdown_requested.is_set():
        sleep(1.0)
