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

from anansi.logging_db import MolongloLoggingDataBase as LogDB
from anansi.tcc.drives.ns_drive import NSDriveInterface
from anansi.tcc.drives.md_drive_dummy import MDDriveInterface

WIND_STOW_NSEW = (0.0,0.0)              
MAINTENANCE_STOW_NSEW = (d2r(45.0),0.0) 

class Track(Thread):
    def __init__(self, ns_drive, md_drive, coordinates, update=2.0):
        self.ns_drive = ns_drive
        self.md_drive = md_drive
        self.coords = coords
        self._stop = Event()
        self.update_cycle = update
        self.log.log_tcc_status("Track", "info",
                                "Setting up track on object %s"%repr(self.coords))
        Thread.__init__(self)

    def run(self):
        while not self._stop.is_set():
            self.log.log_tcc_status("Track", "info",
                                    "Updating positions for track")
            ns,ew = self.coords.predict()
            self.ns_drive.set_tilts(ns,ns)
            self.md_drive.set_tilts(ew,ew)
            sleep(self.update_cycle)

    def end(self):
        self.log.log_tcc_status("Track", "info",
                                "Ending track and stopping drives")
        self.event.set()
        self.ns_drive.stop()
        self.md_drive.stop()


class TelescopeController(object):
    def __init__(self,east_disabled=False,west_disabled=False):
        self.log = LogDB()
        self.log.log_tcc_status("TelescopeController", "info",
                                "Spawning telescope controller thread")
        self.current_track = None
        self.ns_drive = NSDriveInterface()
        self.md_drive = MDDriveInterface()

    def disable_east_arm(self):
        self.ns_drive.disable_east_arm()
        self.md_drive.disable_east_arm()

    def disable_west_arm(self):
        self.ns_drive.disable_west_arm()
        self.md_drive.disable_west_arm()
        
    def enable_east_arm(self):
        self.ns_drive.enable_east_arm()
        self.md_drive.enable_east_arm()

    def enable_west_arm(self):
        self.ns_drive.enable_west_arm()
        self.md_drive.enable_west_arm()
        
    def stop(self):
        self.log.log_tcc_status("TelescopeController.stop", "info",
                                "Stop requested for both NS & MD drives")
        self.ns_drive.stop()
        self.md_drive.stop()
        
    def track(self,coordinates):
        self.end_current_track()
        self.current_track = Track(self.ns_drive,self.md_drive,coordinates)
        self.current_track.start()
        
    def end_current_track(self):
        if self.current_track:
            self.log.log_tcc_status(
                    "TelescopeController.end_current_track",
                    "info", "Stopping current track")
            try:
                self.current_track.end()
                self.current_track.join()
            except Exception as error:
                self.log.log_tcc_status(
                    "TelescopeController.end_current_track", 
                    "warning", str(error))
            finally:
                self.current_track = None
    
    def _drive_to(self,ns,ew):
        self.log.log_tcc_status(
            "TelescopeController._drive_to",
            "info", "Sending telescope to NS: %.5f rads EW: %.5 rads"%(ns,ew))
        self.ns_drive.set_tilts(ns,ns)
        self.md_drive.set_tilts(ew,ew)

    def drive_to(self,coordinates):
        self.end_current_track()
        ns,ew = coordinates.get_nsew()
        self.log.log_tcc_status(
            "TelescopeController.drive_to",
            "info", "Sending telescope to coordinates: %s"%repr(coordinates))
        self._drive_to(ns,ew)

    def wind_stow(self):
        self.end_current_track()
        self.log.log_tcc_status(
            "TelescopeController.wind_stow",
            "info", "Sending telescope to wind stow")
        self._drive_to(*WIND_STOW_NSEW)
        
    def maintenance_stow(self):
        self.end_current_track()
        self.log.log_tcc_status(
            "TelescopeController.maintenance_stow",
            "info", "Sending telescope to maintenance stow")
        self._drive_to(*MAINTENANCE_STOW_NSEW)

    
