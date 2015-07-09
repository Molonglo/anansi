from threading import Thread,Event
from Queue import Queue
import anansi.utils
from anansi.utils import d2r,r2d
from struct import pack,unpack
from time import sleep,time
import ctypes as C
import numpy as np
import logging
from lxml import etree
from anansi.utils import gen_xml_element
from anansi.logging_db import MolongloLoggingDataBase as LogDB
from anansi.tcc.drives import NSDriveInterface,MDDriveInterface,CountError
from scipy.optimize import fmin
import copy
import ephem as eph

WIND_STOW_NSEW = (0.0,0.0)              
MAINTENANCE_STOW_NSEW = (d2r(45.0),0.0) 
NS_RATE = 0.001454
EW_RATE = 0.000727
NS_TOLERANCE = 0.0002
EW_TOLERANCE = 0.0001

class BaseTracker(Thread):
    def __init__(self, drive, coords, nsew, rate, tolerance, east_active=True, west_active=True):
        self.log = LogDB()
        self._name = "%s Tracker"%(nsew.upper())
        self.drive = drive
        self.coords = coords
        self.rate = rate
        self.nsew = nsew
        self.east_active = True
        self.west_active = True
        self._stop = Event()
        self.tolerance = tolerance
        Thread.__init__(self)

    def _max_tilt_offset(self,tilt):
        state = self.drive.get_status()
        if self.east_active and self.west_active:
            east_offset = abs(state["east_tilt"]-tilt)
            west_offset = abs(state["west_tilt"]-tilt)
            if east_offset >= west_offset:
                return state["east_tilt"]
            else:
                return state["west_tilt"]
        elif self.east_active:
            return state["east_tilt"]
        elif self.west_active:
            return state["west_tilt"]
        else:
            raise Exception("Both arms disabled")
        
    def on_target(self):
        self.coords.compute()
        x = getattr(self.coords,self.nsew)
        tilt = self._max_tilt_offset(x)
        offset = abs(tilt-x)
        print "\n%s drive furthest tilt: %f,   desired: %f,   offset: %f\n"%(self.nsew,tilt,x,offset)
        return offset<=self.tolerance

    def __mdt(self,t,*args):
        t = abs(t)
        telescope_pos = args
        date = eph.now() + t*eph.second
        self.coords.compute(date)
        source_pos = getattr(self.coords,self.nsew)
        offset = abs(telescope_pos - source_pos)
        return abs(offset-t*self.rate)
            
    def drive_time(self):
        self.coords.compute()
        tilt = self._max_tilt_offset(self.coords.ns)
        return fmin(self.__mdt,[0.0,],args=(tilt,))[0]
        
        
    def __mpd(self,t):
        t = abs(t)
        self.coords.compute()
        x = getattr(self.coords,self.nsew)
        date = eph.now() + t*eph.second
        self.coords.compute(date)
        nx = getattr(self.coords,self.nsew)
        return abs(abs(nx-x) - self.tolerance)

    def set_tilts(self,tilt):
        try:
            self.log.log_tcc_status(self._name, "info",
                                    "Setting %s tilt to %.5f"%(self.nsew,tilt))
            if self.east_active and self.west_active:
                self.drive.set_tilts(tilt,tilt)
            elif self.east_active:
                self.drive.set_east_tilt(tilt)
            elif self.west_active:
                self.drive.set_west_tilt(tilt)
            else:
                raise Exception("Both arms disabled")
        except CountError:
            sleep(2)
            pass
    
    def slew(self):
        print "\n%s Slew\n"%(self.nsew)
        dt = self.drive_time()
        date = eph.now() + dt*eph.second
        self.coords.compute(date)
        self.set_tilts(getattr(self.coords,self.nsew))
        while self.drive.active() and not self._stop.is_set():
            sleep(3)
                        
    def track(self):
        while not self._stop.is_set():
            print "\n%s Track\n"%(self.nsew)
            if self.on_target():
                sleep(1)
                continue
            else:
                pt = fmin(self.__mpd,[0.0,])[0]
                date = eph.now() + pt*eph.second
                self.coords.compute(date)
                self.set_tilts(getattr(self.coords,self.nsew))
                sleep(2)
    
    def run(self):
        self.slew()
        self.track()
            
    def end(self):
        self._stop.set()
        sleep(1)
        self.drive.stop()
        

class NSTracker(BaseTracker):
    def __init__(self, drive, coords, east_active=True, west_active=True):
        BaseTracker.__init__(self, drive, coords, "ns", NS_RATE, NS_TOLERANCE, east_active, west_active)

class MDTracker(BaseTracker):
    def __init__(self, drive, coords, east_active=True, west_active=True):
        BaseTracker.__init__(self, drive, coords, "ew", EW_RATE, NS_TOLERANCE, east_active, west_active)

class Tracker(object):
    def __init__(self,ns_drive,md_drive,coords,east_active=True, west_active=True):
        self.md_tracker = MDTracker(md_drive,copy.copy(coords))
        self.ns_tracker = NSTracker(ns_drive,copy.copy(coords))
        self.md_tracker.start()
        self.ns_tracker.start()

    def end(self):
        self.md_tracker.end()
        self.ns_tracker.end()
        

class TelescopeController(object):
    def __init__(self,east_disabled=False,west_disabled=False):
        self.log = LogDB()
        self.log.log_tcc_status("TelescopeController", "info",
                                "Spawning telescope controller thread")
        self.current_track = None
        self.east_disabled = east_disabled
        self.west_disabled = west_disabled
        self.ns_drive = NSDriveInterface()
        self.md_drive = MDDriveInterface()
        self.coordinates = None

    def clean_up(self):
        self.ns_drive.clean_up()
        self.md_drive.clean_up()

    def disable_east_arm(self):
        self.east_disabled = True
        self.ns_drive.disable_east_arm()
        self.md_drive.disable_east_arm()

    def disable_west_arm(self):
        self.west_disabled = True
        self.ns_drive.disable_west_arm()
        self.md_drive.disable_west_arm()
        
    def enable_east_arm(self):
        self.east_disabled = False
        self.ns_drive.enable_east_arm()
        self.md_drive.enable_east_arm()

    def enable_west_arm(self):
        self.west_disabled = False
        self.ns_drive.enable_west_arm()
        self.md_drive.enable_west_arm()
        
    def stop(self):
        self.log.log_tcc_status("TelescopeController.stop", "info",
                                "Stop requested for both NS & MD drives")
        self.end_current_track()
        self.ns_drive.stop()
        self.md_drive.stop()
        
    def track(self,coordinates):
        self.coordinates = coordinates
        self.end_current_track()
        self.current_track = Tracker(self.ns_drive,self.md_drive,coordinates)
        
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
        self.log.log_tcc_status("TelescopeController._drive_to",
                                "info", "Sending telescope to NS: %.5f rads EW: %.5f rads"%(ns,ew))
        self.ns_drive.set_tilts(ns,ns)
        self.md_drive.set_tilts(ew,ew)

    def drive_to(self,coordinates):
        self.coordinates = coordinates
        self.end_current_track()
        coordinates.compute()
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

    
