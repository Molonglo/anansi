import warnings
import ephem as eph
import numpy as np
from anansi.utils import d2r,r2d
from anansi.coords import nsew_to_hadec,hadec_to_nsew
import os
from ConfigParser import ConfigParser

config_path = os.environ["ANANSI_CONFIG"]
config = ConfigParser()
config.read(os.path.join(config_path,"anansi.cfg"))
MOL_LAT = config.getfloat("MolongloEphemeris","latitude")
MOL_LON = config.getfloat("MolongloEphemeris","longitude")
MOL_ELV = config.getfloat("MolongloEphemeris","elevation")
MOL_HOR = config.getfloat("MolongloEphemeris","horizon")


FIXED_SYSTEMS = [
    "equatorial_ha",
    "nsew",
    "horizontal"
    ]

# COMPLETE JUST EQUATORIAL TRACKING FOR TESTING PURPOSES

class Molonglo(eph.Observer):
    def __init__(self,date=None,epoch=None):
        super(Molonglo,self).__init__()
        if epoch is not None:
            self.epoch = epoch
        if date is not None:
            self.date = date
        self.lat       = MOL_LAT
        self.long      = MOL_LON
        self.elevation = MOL_ELV
        self.horizon   = MOL_HOR
        self.compute_pressure()


class Coordinates(eph.FixedBody):
    def __init__(self,x,y,system="equatorial",units="radians",
                 name="unknown",epoch="2000",date=None):
        super(Coordinates,self).__init__()
        self.name = name
        self.system = system
        x,y = self._fix_units(x,y,units)
        self.x = x
        self.y = y
        self.date = eph.now()
        self._epoch = epoch
        self.update(date=self.date)

    def _fix_units(self,x,y,units):
        if units == "degrees":
            x = d2r(x)
            y = d2r(y)
        elif units == "hhmmss":
            if self.system in ["equatorial_ha","equatorial"]:
                x = eph.hours(x)
            else:
                x = eph.degrees(x)
            y = eph.degrees(y)
        return x,y

    def update(self,date=None):
        """Convert all moving systems to equatorial"""
        
        if self.system in FIXED_SYSTEMS:
            self._epoch = eph.now()
            date = self.date
            
        self.observatory = Molonglo(date=date,epoch=self._epoch)
        self.lst = self.observatory.sidereal_time()
        
        if self.system == "equatorial":
            coords = eph.Equatorial(self.x,self.y)
            self._ra  = coords.ra
            self._dec = coords.dec

        elif self.system == "galactic":
            coords = eph.Equatorial(eph.Galactic(self.x,self.y))
            self._ra  = coords.ra
            self._dec = coords.dec

        elif self.system == "equatorial_ha":
            coords = eph.Equatorial(self.x,self.y)
            ha = coords.ra
            self._ra  = self.lst - ha
            self._dec = coords.dec

        elif self.system == "horizontal":
            self._ra,self._dec = self.observatory.radec_of(self.x,self.y)

        elif self.system == "nsew":
            ha,dec = nsew_to_hadec(self.x,self.y)
            coords = eph.Equatorial(ha,dec)
            self.observatory = Molonglo(date,self.epoch)
            self._ra  = self.observatory.sidereal_time() - ha
            self._dec = coords.dec

        self.compute(self.observatory)
        gal = eph.Galactic(eph.Equatorial(self.a_ra,self.a_dec))
        self.glat = gal.lat
        self.glon = gal.long
        self.ha = self.lst - self.a_ra
        self.ns,self.ew = hadec_to_nsew(self.ha,self.a_dec)

    def is_up(self):
        self.update()
        return self.alt > self.observatory.horizon

    def _check_fixed(self):
        if self.system in FIXED_SYSTEMS:
            if not self.is_up():
                raise eph.NeverUpError("Source never above horizon")
            else:
                raise eph.AlwaysUpError("Source never below horizon")

    def next_rise(self):
        self._check_fixed()
        self.update()
        return self.observatory.next_rising(self)

    def next_set(self):
        self._check_fixed()
        self.update()
        return self.observatory.next_setting(self)
    
    def next_transit(self):
        self._check_fixed()
        self.update()
        return self.observatory.next_transit(self)

def get_nsew(a_dec,ha):
    ew = np.arcsin((0.9999940546 * np.cos(a_dec) * np.sin(ha))
                   - (0.0029798011806 * np.cos(a_dec) * np.cos(ha))
                   + (0.002015514993 * np.sin(a_dec)))
    ns = np.arcsin(((-0.0000237558704 * np.cos(a_dec) * np.sin(ha))
                    + (0.578881847 * np.cos(a_dec) * np.cos(ha))
                    + (0.8154114339 * np.sin(a_dec)))
                   / np.cos(ew))
    return ns,ew

