from threading import Thread,Event
from time import sleep,time
import copy
from scipy.optimize import fmin
import ephem as eph
from anansi.utils import gen_xml_element,d2r,r2d
from anansi.anansi_logging import DataBaseLogger as LogDB
from anansi.tcc.drives import NSDriveInterface,MDDriveInterface,CountError
from anansi.tcc import drives
from anansi.config import config

class BaseTracker(Thread):
    def __init__(self, drive, coords, nsew, rate, tolerance):
        self.log = LogDB()
        self._name = "%s Tracker"%(nsew.upper())
        self.drive = drive
        self.coords = coords
        self.rate = rate
        self.nsew = nsew
        self._stop = Event()
        self.tolerance = tolerance
        self.state = None
        self.on_source = False
        Thread.__init__(self)

    def _max_tilt_offset(self,tilt):
        state = self.drive.get_status()
        if self.drive.get_east_state() != drives.DISABLED and self.drive.get_west_state()!=drives.DISABLED:
            east_offset = abs(state["east_tilt"]-tilt)
            west_offset = abs(state["west_tilt"]-tilt)
            if east_offset >= west_offset:
                return state["east_tilt"]
            else:
                return state["west_tilt"]
        elif self.drive.get_east_state() != drives.DISABLED:
            return state["east_tilt"]
        elif self.drive.get_west_state() != drives.DISABLED:
            return state["west_tilt"]
        else:
            raise Exception("Both arms disabled")
        
    def on_target(self,arm=None):
        self.coords.compute()
        x = getattr(self.coords,self.nsew)
        if arm is None:
            tilt = self._max_tilt_offset(x)
        elif arm in ['east','west']:
            tilt = self.drive.get_status()['%s_tilt'%arm]
        else:
            raise Exception("Valid arm names are east and west")
        offset = abs(tilt-x)
        #print "%s drive furthest tilt: %f,   desired: %f,   offset: %f"%(self.nsew,tilt,x,offset)
        self.on_source = offset<=self.tolerance
        return self.on_source

    def __mdt(self,t,*args):
        t = abs(t)
        telescope_pos = args[0]
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
            if self.drive.get_east_state() != drives.DISABLED and self.drive.get_west_state()!=drives.DISABLED:
                self.drive.set_tilts(tilt,tilt)
            elif self.drive.get_east_state() != drives.DISABLED:
                self.drive.set_east_tilt(tilt)
            elif self.drive.get_west_state() != drives.DISABLED:
                self.drive.set_west_tilt(tilt)
            else:
                raise Exception("Both arms disabled")
        except CountError:
            sleep(2)
        except Exception as error:
            msg = "Set tilt failed on %s drive tracker for tilt %f"%(self.nsew,tilt)
            self.log.log_tcc_status(self._name, "error",msg)
            sleep(2)
    
    def slew(self):
        self.state = "slewing"
        #print "%s slew"%(self.nsew)
        while not self.on_target() and not self._stop.is_set():
            if self.drive.active():
                sleep(3)
                continue
            dt = self.drive_time()
            date = eph.now() + dt*eph.second
            self.coords.compute(date)
            self.set_tilts(getattr(self.coords,self.nsew))
                        
    def track(self):
        self.state = "tracking"
        while not self._stop.is_set():
            if self.drive.active() or self.on_target():
                sleep(3)
                continue
            else:
                pt = fmin(self.__mpd,[0.0,])[0]
                date = eph.now() + pt*eph.second
                self.coords.compute(date)
                self.set_tilts(getattr(self.coords,self.nsew))
                
    def run(self):
        self.slew()
        self.track()
            
    def end(self):
        self._stop.set()
        sleep(2)
        self.drive.stop()
        

class NSTracker(BaseTracker):
    def __init__(self, drive, coords):
        rate = config.ns_drive.east_rate
        tolerance = config.ns_drive.tolerance
        BaseTracker.__init__(self, drive, coords, "ns", rate, tolerance)

class MDTracker(BaseTracker):
    def __init__(self, drive, coords):
        rate = config.md_drive.east_rate
        tolerance = config.md_drive.tolerance
        BaseTracker.__init__(self, drive, coords, "ew", rate, tolerance)

class Tracker(object):
    def __init__(self,ns_drive,md_drive,coords):
        self.md_tracker = MDTracker(md_drive,copy.copy(coords))
        self.ns_tracker = NSTracker(ns_drive,copy.copy(coords))
        self.md_tracker.start()
        self.ns_tracker.start()
        
    def end(self):
        self.md_tracker.end()
        self.ns_tracker.end()
        
    def on_target(self,drive_name,arm):
        if drive_name == "ns":
            return self.ns_tracker.on_source
        elif drive_name == "md":
            return self.md_tracker.on_source
        else:
            raise Exception("Valid drive names are ns and md")

class TelescopeController(object):
    def __init__(self):
        self.log = LogDB()
        self.log.log_tcc_status("TelescopeController", "info",
                                "Spawning telescope controller thread")
        self.current_track = None
        self.ns_drive = NSDriveInterface()
        self.md_drive = MDDriveInterface()
        self.coordinates = None

    def clean_up(self):
        self.ns_drive.clean_up()
        self.md_drive.clean_up()

    def set_east_state(self,state):
        self.ns_drive.set_east_state(state)
        self.md_drive.set_east_state(state)

    def set_west_state(self,state):
        self.ns_drive.set_west_state(state)
        self.md_drive.set_west_state(state)
        
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
        ns = d2r(config.presets.wind_stow_nw)
        ew = d2r(config.presets.wind_stow_ew)
        self._drive_to(ns,ew)
        
    def maintenance_stow(self):
        self.end_current_track()
        self.log.log_tcc_status(
            "TelescopeController.maintenance_stow",
            "info", "Sending telescope to maintenance stow")
        ns = d2r(config.presets.maintenance_stow_nw)
        ew = d2r(config.presets.maintenance_stow_ew)
        self._drive_to(ns,ew)

    
