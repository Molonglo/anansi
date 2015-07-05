from threading import Thread,Event
from Queue import Queue
import anansi.utils
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
from anansi.tcc.drives import NSDriveInterface,MDDriveInterface

WIND_STOW_NSEW = (0.0,0.0)              
MAINTENANCE_STOW_NSEW = (d2r(45.0),0.0) 
NS_RATE = 0.0001
MD_RATE = 0.0001

class BaseTracker(Thread):
    def __init__(self, drive, coords, rate, east_active=True, west_active=True):
        self.drive = drive
        self.coords = coords
        self.rate = rate
        self.east_active = True
        self.west_active = True
        self._stop = Event()
        Thread.__init__(self)

    def _offset(self,tilt):
        #state = self.drive.get_state()
        state = {
        "east_tilt":1.13,
        "west_tilt":1.13
        }
        east_offset = abs(state["east_tilt"]-tilt)
        west_offset = abs(state["west_tilt"]-tilt)
        if self.east_active and self.west_active:
            return max(east_offset,west_offset)
        elif self.east_active:
            return east_offset
        elif self.west_active:
            return west_offset
        else:
            raise Exception("Both arms disabled")

    def _predict_drive_time(self,t):
        date = eph.now() + t*eph.second
        x = self.get_coordinate(date=date)
        offset = abs(self._offset(x) - self.rate*t)
        return offset
        
    def drive_time(self):
        opt_result = minimize(self._predict_drive_time,[0.0,],method="TNC")
        return opt_result["x"]
            
    def get_coordinate(self,date=None):
        #raise NotImplemented("Must use NS or MD tracker")
        self.coords.compute(date)
        return self.coords.ns
        
    def run(self):
        while not self._stop.is_set():
            t = self.drive_time()
            x = self.get_coordinate(eph.now()+t*eph.seconds)
            if self.east_active and self.west_active:
                self.drive.set_tilts(x,x)
            elif self.east_active:
                self.drive.set_east_tilt(x)
            elif self.west_active:
                self.drive.set_west_tilt(x)
            else:
                raise Exception("Both arms disabled")
            sleep(t)
            
    def end(self):
        self._stop.set()
        self.drive.stop()
        

class NSTracker(BaseTracker):
    def __init__(self, drive, coords, rate, east_active=True, west_active=True):
        BaseTracker.__init__(self,drive, coords, rate, east_active, west_active)
        
    def get_coordinate(self,date=None):
        self.coords.compute(date)
        return self.coords.ns
    

class MDTracker(BaseTracker):
    def __init__(self, drive, coords, rate, east_active=True, west_active=True):
        BaseTracker.__init__(self,drive, coords, rate, east_active, west_active)
        
    def get_coordinate(self,date=None):
        self.coords.compute(date)
        return self.coords.ew


class TelescopeController(object):
    def __init__(self,east_disabled=False,west_disabled=False):
        self.log = LogDB()
        self.log.log_tcc_status("TelescopeController", "info",
                                "Spawning telescope controller thread")
        self.current_track = None
        self.ns_drive = NSDriveInterface()
        self.md_drive = MDDriveInterface()

    def clean_up(self):
        self.ns_drive.clean_up()
        self.md_drive.clean_up()

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
        print ns,ew
        print float(ns),float(ew)
        self.log.log_tcc_status("TelescopeController._drive_to",
                                "info", "Sending telescope to NS: %.5f rads EW: %.5f rads"%(ns,ew))
        self.ns_drive.set_tilts(ns,ns)
        self.md_drive.set_tilts(ew,ew)

    def drive_to(self,coordinates):
        self.end_current_track()
        coordinates.get_nsew()
        self.log.log_tcc_status(
            "TelescopeController.drive_to",
            "info", "Sending telescope to coordinates: %s"%repr(coordinates))
        self._drive_to(coordinates.ns,coordinates.ew)

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

    
