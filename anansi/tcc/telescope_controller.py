from threading import Thread,Event
from time import sleep,time
import copy
import logging
from scipy.optimize import fmin
import ephem as eph
from anansi.utils import gen_xml_element,d2r,r2d
from anansi.tcc.drives import NSDriveInterface,MDDriveInterface,CountError
from anansi.tcc import drives
from anansi.config import config
from anansi import log
logger = logging.getLogger('anansi')

class TelescopeArmsDisabled(Exception):
    def __init__(self,name):
        message = "Both telescope arms disabled for %s drive"%(name)
        logger.error(message,extra=log.tcc_status())
        super(TelescopeArmsDisabled,self).__init__(message)

class BaseTracker(Thread):
    def __init__(self, drive, coords, nsew, rate, tolerance, track, stop):
        self._name = "%s Tracker"%(drive.name.upper())
        self.drive = drive
        self.drive.clear_error()
        self._track = track
        self.coords = coords
        self.rate = rate
        self.nsew = nsew
        self._stop = stop
        self.tolerance = tolerance
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
            raise TelescopeArmsDisabled(self.drive.name)
        
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
        self.on_source = offset<=self.tolerance
        logger.info("%s drive is %.5f radians from target"%(self.drive.name,offset))
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
        dt = fmin(self.__mdt,[0.0,],args=(tilt,),disp=False)[0]
        logger.info("Predicted slew time for %s drive: %.0f"%(self.drive.name,dt),
                    extra=log.tcc_status())
        return dt
        
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
            logger.info("Setting %s drive tilt to %.5f"%(self.drive.name,tilt),extra=log.tcc_status())
            if self.drive.get_east_state() != drives.DISABLED and self.drive.get_west_state()!=drives.DISABLED:
                self.drive.set_tilts(tilt,tilt)
            elif self.drive.get_east_state() != drives.DISABLED:
                self.drive.set_east_tilt(tilt)
            elif self.drive.get_west_state() != drives.DISABLED:
                self.drive.set_west_tilt(tilt)
            else:
                raise TelescopeArmsDisabled(self.drive.name)
        except CountError:
            sleep(2)
        except eZ80Error:
            logger.error("Caught eZ80 error in %s tracker"%(self.drive.name),extra=log.tcc_status())
            self.end()
        except Exception as error:
            msg = "Set tilt failed on %s drive tracker for tilt %f"%(self.drive.name,tilt)
            logger.error(msg,extra=log.tcc_status(),exc_info=True)
            sleep(2)
    
    def slew(self):
        while not self.on_target():
            if self._stop.is_set():
                self.end()
                break
            elif self.drive.has_error():
                logger.error("%s drive in error state"%(self.drive.name),extra=log.tcc_status())
                self.end()
                break
            elif self.drive.active():
                sleep(3)
                continue
            else:
                dt = self.drive_time()
                date = eph.now() + dt*eph.second
                self.coords.compute(date)
                self.set_tilts(getattr(self.coords,self.nsew))
                        
    def track(self):
        while not self._stop.is_set():
            if self.drive.has_error():
                logger.error("%s drive in error state"%(self.drive.name),extra=log.tcc_status())
                self.end()
                break
            elif self.drive.active() or self.on_target():
                sleep(3)
                continue
            else:
                logger.info("Updating tracking position for %s drive"%self.drive.name,
                            extra=log.tcc_status())
                pt = fmin(self.__mpd,[0.0,],disp=False)[0]
                date = eph.now() + pt*eph.second
                self.coords.compute(date)
                self.set_tilts(getattr(self.coords,self.nsew))
                                
    def run(self):
        self.slew()
        if self._track:
            self.track()
            
    def end(self):
        logger.info("Ending %s drive track"%(self.drive.name),extra=log.tcc_status())
        self._stop.set()
        sleep(2)
        self.drive.stop()
        

class NSTracker(BaseTracker):
    def __init__(self, drive, coords,track,stop):
        rate = config.ns_drive.east_rate
        tolerance = config.ns_drive.tolerance
        BaseTracker.__init__(self, drive, coords, "ns", rate, tolerance, track,stop)

class MDTracker(BaseTracker):
    def __init__(self, drive, coords,track,stop):
        rate = config.md_drive.east_rate
        tolerance = config.md_drive.tolerance
        BaseTracker.__init__(self, drive, coords, "ew", rate, tolerance, track,stop)

class Tracker(object):
    def __init__(self,ns_drive,md_drive,coords,track=True):
        stop = Event()
        self.md_tracker = MDTracker(md_drive,coords.new_instance(), track, stop)
        self.ns_tracker = NSTracker(ns_drive,coords.new_instance(), track, stop)
        self.md_tracker.start()
        self.ns_tracker.start()
        
    def end(self):
        self.md_tracker.end()
        self.ns_tracker.end()
        self.md_tracker.join()
        self.ns_tracker.join()
        
    def on_target(self,drive_name,arm):
        if drive_name == "ns":
            return self.ns_tracker.on_source
        elif drive_name == "md":
            return self.md_tracker.on_source
        else:
            raise Exception("Valid drive names are ns and md")

class TelescopeController(object):
    def __init__(self):
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
        logger.info("Ending tracks and stopping telescope",extra=log.tcc_status())
        self.end_current_track()
        self.ns_drive.stop()
        self.md_drive.stop()
        
    def observe(self,coordinates,track=True):
        self.coordinates = coordinates
        self.end_current_track()
        self.current_track = Tracker(self.ns_drive,self.md_drive,coordinates,track=track)
        
    def end_current_track(self):
        if self.current_track:
            logger.info("Ending current track",extra=log.tcc_status())
            try:
                self.current_track.end()
            except Exception as error:
                logger.error("Exception caught while attempting to end the current track",
                             extra=log.tcc_status(),exc_info=True)
            finally:
                self.current_track = None
    
    def wind_stow(self):
        self.end_current_track()
        logger.info("Sending telescope to wind stow",extra=log.tcc_status())
        ns = d2r(config.presets.wind_stow_ns)
        ew = d2r(config.presets.wind_stow_ew)
        
        self._drive_to(ns,ew)
        
    def maintenance_stow(self):
        self.end_current_track()
        logger.info("Sending telescope to maintenance stow",extra=log.tcc_status())
        ns = d2r(config.presets.maintenance_stow_ns)
        ew = d2r(config.presets.maintenance_stow_ew)
        self._drive_to(ns,ew)

    
