from threading import Thread,Event
from Queue import Queue
from time import sleep
from lxml import etree
from ConfigParser import ConfigParser
import os
from anansi import exit_funcs
from anansi.comms import TCPServer
from anansi.tcc.coordinates import Coordinates
from anansi.tcc.telescope_controller import TelescopeController
from anansi.logging_db import MolongloLoggingDataBase as LogDB

config_path = os.environ["ANANSI_CONFIG"]
config = ConfigParser()
config.read(os.path.join(config_path,"anansi.cfg"))

ANANSI_SERVER_IP = config.get("IPAddresses","anansi_ip")
ANANSI_SERVER_PORT = config.getint("IPAddresses","anansi_port")

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
        self.msg = etree.fromstring(xml_string)
        self.parse_server_commands()
        self.parse_tcc_commands()

    def parse_arms_status(self):
        arm_status = self.msg.find("server_command")

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
            east_status = arm_status.find("east").text.strip()
            west_status = arm_status.find("west").text.strip()
            if east_status == "disabled":
                self.east_arm_active = False
            if west_status == "disabled":
                self.west_arm_active = False
                            
            
class TCCServer(Thread):
    def __init__(self):
        Thread.__init__(self)
        exit_funcs.register(self.shutdown)
        self.server  = TCPServer(ANANSI_SERVER_IP,ANANSI_SERVER_PORT)
        self.server_thread = Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        self.controller = TelescopeController()
        self._shutdown = Event()
        self.log = LogDB()

    def shutdown(self):
        self._shutdown.set()
        self.server.shutdown()
        exit_funcs.deregister(self.shutdown)
            
    def parse_message(self,msg):
        self.log.log_tcc_status("TCCServer.parse_message","info",msg)

        response = TCCResponse()

        try:
            request = TCCRequest(msg)
        
            if request.server_command == "shutdown":
                self.log.log_tcc_status("TCCServer.parse_message","info",
                                        "Received shutdown message")
                self.shutdown()
        
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
           
if __name__ == "__main__":
    x = TCCServer()
    x.start()
    while True:
        sleep(1.0)
