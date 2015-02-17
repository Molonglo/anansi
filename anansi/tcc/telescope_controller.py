from threading import Thread,Event
from Queue import Queue
import anansi.utils
from anansi.comms import TCPClient,TCPServer,UDPSender
from anansi.tcc.coordinates import Coordinates
from anansi.utils import d2r,r2d
from struct import pack,unpack
from time import sleep,time
import ctypes as C
import numpy as np
import logging
from lxml import etree
from anansi.utils import gen_xml_element

class TelescopeController(Thread):
    def __init__(self, coordinates, kill_event, DriveClass):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("Creating TelescopeController instance")
        self.tracking_enabled = False
        self.on_target = False
        self.drive = DriveClass(timeout=0.5)
        self.coordinates = coordinates
        Thread.__init__(self)

    def stop(self):
        self.logger.info("Stop requested")
        
        # request stop
        
        # send updated positions to broadcast server
        
    def track(self):
        self.logger.info("Track requested")

        while not kill_event.is_set():
            
            # predict new nsew position
            
            # request move
            
            # send updated positions to broadcast server
            
            # reloop

    def set_nsew(self):
        self.logger.info("Setting drive positions")
        
        # request move 
        
        # send updated positions to broadcast server
    
