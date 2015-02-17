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


class TelescopeControlThread(Thread):
    def __init__(self,event):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("Creating TelescopeControlThread instance")
        self.run = None
        self.event = event
        Thread.__init__(self)

    def get_position(self):
        pass

    def stop(self,command):
        self.run = self._stop
        self.start()

    def _stop(self):
        self.logger.info("Stop requested")
        md_drive = DriveControlThread(MDController,self.event)
        md_drive.stop()
        ns_drive = DriveControlThread(NSController,self.event)
        ns_drive.stop()
        md_drive.join()
        ns_drive.join()
        
    def track(self,coordinates):
        self.run = lambda: self._track(coordinates)
        self.start()

    def _track(self,coordinates):
        self.logger.info("Track requested")
        self._stop()
        
        while not self.event.is_set():
            self.get_current_position()
            coordinates.predict()
            
            if not update_required:
                sleep(1)
                continue

            md_drive = DriveControlThread(MDController,self.event,
                                          self.broadcast_server_queue)
            ns_drive = DriveControlThread(NSController,self.event,
                                          self.broadcast_server_queue)
            md_drive.drive(pos,speed,direction)
            ns_drive.drive(pos,speed,direction)
            md_drive.join()
            ns_drive.join()
            
    def goto(self,coordinates,speed):
        self.run = lambda: self._goto(coordinates,speed)
        self.start()

    def _goto(self,coordinates,speed):
        self.logger.info("Setting drive positions")
        self._stop()
        md_drive = DriveControlThread(MDController,self.event,
                                      self.broadcast_server_queue)
        ns_drive = DriveControlThread(NSController,self.event,
                                      self.broadcast_server_queue)
        md_drive.drive(pos,speed,direction)
        ns_drive.drive(pos,speed,direction)
        md_drive.join()
        ns_drive.join()


class DriveControlThread(Thread):
    def __init__(self,DriveClass,kill_event,server_queue=None):
        self.motor = DriveClass()
        self.event = kill_event
        self.server_queue = server_queue
        
    def drive(self,pos,speed,direction):
        # encode
        # open client
        # connect
        # send
        # loop over receiving
        # send updates to server_queue
        # die if event triggered
        # die if error
        
        
    
