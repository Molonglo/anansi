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
from anansi.utils import gen_xml_element,nb_sleep
from anansi.logging_db import MolongloLoggingDataBase as LogDB
from anansi.tcc.drives import NSDriveInterface,MDDriveInterface,CountError
from anansi.tcc.coordinates import make_coordinates
from scipy.optimize import fmin
import copy
import ephem as eph

WIND_STOW = make_coordinates(0.0,0.0,system="nsew",units="degrees")
MAINTENANCE_STOW = make_coordinates(45.0,0.0,system="nsew",units="degrees") 
NS_TOLERANCE = 0.0002
EW_TOLERANCE = 0.0001

#
# TODO
#
# 2. implement drive limits and exception handling
# 3. decide on fixed coordinate tracking logic
# (should be slew only,)
#

class Tracker(Thread):
    def __init__(self,coords,drive,tolerance,track=True):
        self.log = LogDB()
        self.drive = drive
        self.tolerance = tolerance
        self.east_tilt = 0.0
        self.west_tilt = 0.0
        self.east_on_target = False
        self.west_on_target = False
        self.on_target = False
        if track:
            self.run = self.track
        else:
            self.run = self.slew

    def update(self):
        state = self.drive.get_status()
        tilt = self.get_coord()
        self.east_tilt = state["east_tilt"]
        self.west_tilt = state["west_tilt"]
        self.east_on_target = abs(self.east_tilt - tilt) <= self.tolerance
        self.west_on_target = abs(self.west_tilt - tilt) <= self.tolerance
        self.east_active = state["east_active"]
        self.west_active = state["west_active"]
        if self.east_active and self.west_active:
            self.on_target = self.east_on_target and self.west_on_target
        elif self.east_active:
            self.on_target = self.east_on_target
        elif self.west_active:
            self.on_target = self.west_on_target
    
    def dt_minfunc(self,dt,*args):
        dt = abs(dt)
        arm_tilt,rate = args
        date = eph.now() + dt*eph.second
        src_tilt = self.get_coord(date=date)
        offset = abs(arm_tilt - src_tilt)
        src_dir = self.get_coord(date=date+10*eph.second) - src_tilt
        src_dir = src_dir/abs(src_dir)
        offset = abs(arm_tilt - (src_tilt+src_dir*self.preemt))
        return abs(offset-dt*rate)

    def drive_time(self):
        e_dt = fmin(self.dt_minfunc,[0.0,],(self.east_tilt,self.drive.get_east_rate()))[0]
        w_dt = fmin(self.dt_minfunc,[0.0,],(self.west_tilt,self.drive.get_west_rate()))[0]
        if self.east_active() and self.west_active():
            return max(e_dt,w_dt)
        elif self.east_active():
            return e_dt
        elif self.west_active():
            return w_dt
        else:
            return 0.0

    def slew(self):
        self.update()
        if isinstance(self.coords,NSEWCoordinates):
            tilt = self.get_coord()
            self.set_tilt(tilt)
        else:
            dt = self.drive_time()
            date = eph.now() + dt*eph.second
            tilt = self.get_coord(date=date)
            self.set_tilt(tilt)
        while self.drive.is_moving() and not self._stop.is_set():
            nb_sleep(1,5,self._stop)
            self.update()

    def preemt_minfunc(self,dt):
        dt = abs(dt)
        x = self.get_coord()
        date = eph.now() + dt*eph.second
        nx = self.get_coord(date=date)
        return abs(abs(nx-x) - self.tolerance)

    def run(self):
        self.update()
        if not self.on_target:
            self.slew()

    def track(self):
        self.slew()
        while not self._stop.is_set():
            if not self.on_target:
                self.slew()
            nb_sleep(1,5,self._stop)

    def set_tilt(self,tilt):
        try:
            self.drive.set_tilts(tilt,tilt)
        except CountError:
            pass
        except BeyondLimits:
            self.end()
        
    def end(self):
        self._stop.set()
        self.drive.stop()


class NSTracker(Tracker):
    def __init__(self, drive, coords):
        BaseTracker.__init__(self, drive, coords, NS_TOLERANCE)

    def get_coord(self,date=None):
        self.coords.compute(date=date)
        return self.coords.ns


class MDTracker(BaseTracker):
    def __init__(self, drive, coords):
        BaseTracker.__init__(self, drive, coords, EW_TOLERANCE)

    def get_coord(self,date=None):
        self.coords.compute(date=date)
        return self.coords.ew


class TelescopeController(object):
    def __init__(self):
        self.log = LogDB()
        self.log.log_tcc_status(
            "TelescopeController", "info",
            "Spawning telescope controller thread")
        self.current_track = None
        self.coordinates = None
        self.ns_drive = NSDriveInterface()
        self.md_drive = MDDriveInterface()
        self.ns_tracker = None
        self.md_tracker = None

    def clean_up(self):
        self.ns_drive.clean_up()
        self.md_drive.clean_up()
        
    def stop(self):
        self.log.log_tcc_status("TelescopeController.stop", "info",
                                "Stop requested for both NS & MD drives")
        self.end_current_track()
        
    def track(self,coordinates):
        self.coordinates = coordinates
        self.md_tracker = MDTracker(self.md_drive,copy.copy(coordinates))
        self.ns_tracker = NSTracker(self.ns_drive,copy.copy(coordinates))
        self.md_tracker.start()
        self.ns_tracker.start()
        
    def end_current_track(self):
        if self.md_tracker:
            self.md_tracker.end()
            self.md_tracker.join()
            self.md_tracker = None
        if self.ns_tracker:
            self.ns_tracker.end()
            self.ns_tracker.join()
            self.md_tracker = None
    
    def wind_stow(self):
        self.end_current_track()
        self.log.log_tcc_status(
            "TelescopeController.wind_stow",
            "info", "Sending telescope to wind stow")
        self.track(WIND_STOW)
        
    def maintenance_stow(self):
        self.end_current_track()
        self.log.log_tcc_status(
            "TelescopeController.maintenance_stow",
            "info", "Sending telescope to maintenance stow")
        self.track(MAINTENANCE_STOW)

    
