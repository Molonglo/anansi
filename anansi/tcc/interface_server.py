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
from utils import gen_xml_element
from ConfigParser import ConfigParser

config_path = os.environ["ANANSI_CONFIG"]
config = ConfigParser()
config.read(os.path.join(config_path,"anansi.cfg"))

ANANSI_SERVER_IP = config.get("IPAddresses","anansi_ip")
ANANSI_SERVER_PORT = config.getint("IPAddresses","anansi_port")

WIND_STOW_NS = config.get("Presets","wind_stow_ns")
WIND_STOW_EW = config.get("Presets","wind_stow_ew")

MAINTENANCE_STOW_NS = config.get("Presets","maintenance_stow_ns")
MAINTENANCE_STOW_EW = config.get("Presets","maintenance_stow_ns")
            
class UserInterface(Thread):
    def __init__(self):
        self.server  = TCPServer(ANANSI_SERVER_IP,ANANSI_SERVER_PORT)
        self.server_thread = Thread(target=self.server.serve_forever)
        self.server_thread.start()
        self.username = ""
        self.user_comment = ""
        self.control_thread = None
        self.shutdown = Event()
        Thread.__init__(self)

    def shutdown(self):
        self.status_broadcast.shutdown()
        self.server.shutdown()
        self._shutdown.set()
        return response
        
    def parse_message(self,msg):
        request = TCCRequest(msg)
        response = TCCResponse()
        
        if request.server_command == "shutdown":
            self.shutdown()
        
        tcc_error = ""
        if request.tcc_command == "point":
            info = request.tcc_info
            coords = Coordinates(info["x"],info["y"],system=info["system"],
                                 units=info["units"],epoch=info["epoch"])
            self.control_thread = TelescopeControlThread()
            self.control_thread.track(coords)
            
        elif request.tcc_command == "wind_stow":
            coords = Coordinates(WIND_STOW_NS,WIND_STOW_EW,system="nsew")
            self.control_thread = TelescopeControlThread()
            self.control_thread.goto(coords)
            

        elif request.tcc_command == "maintenance_stow":
            coords = Coordinates(MAINTENANCE_STOW_NS,MAINTENANCE_STOW_EW,
                                 system="nsew")
            self.control_thread = TelescopeControlThread()
            self.control_thread.goto(coords)

        elif request.tcc_command == "stop":
            self.control_thread = TelescopeControlThread()
            self.control_thread.stop()
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
           
         
        
