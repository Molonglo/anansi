import warnings
import ephem as eph
import numpy as np
from anansi.utils import d2r,r2d
import os
from ConfigParser import ConfigParser

config_path = os.environ["ANANSI_CONFIG"]
config = ConfigParser()
config.read(os.path.join(config_path,"anansi.cfg"))
MOL_LAT = config.getfloat("MolongloEphemeris","latitude")
MOL_LON = config.getfloat("MolongloEphemeris","longitude")
MOL_ELV = config.getfloat("MolongloEphemeris","elevation")
MOL_HOR = config.getfloat("MolongloEphemeris","horizon")

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
                 name="unknown",epoch=None,date=None):
        super(Coordinates,self).__init__()
        self.lst = "00:00:00"
        self.name = name
        self.system = system
        if units == "degrees":
            x = d2r(x)
            y = d2r(y)
        elif units == "hhmmss":
            if system in ["equatorial_ha","equatorial"]:
                x = eph.hours(x)
            else:
                x = eph.degrees(x)
            y = eph.degrees(y)

        if system in ["equatorial_ha","horizontal"]:
            warnings.warn("Fixed coordinate system: setting epoch to current date")
            self.epoch = eph.now()
        else:
            self.epoch = epoch

        if system == "equatorial":
            coords = eph.Equatorial(x,y)
            self._ra  = coords.ra
            self._dec = coords.dec

        if system == "equatorial_ha":
            coords = eph.Equatorial(x,y)
            observatory = Molonglo(date,self.epoch)
            self.ha = coords.ra
            self._ra  = observatory.sidereal_time() - self.ha
            self._dec = coords.dec

        elif system == "galactic":
            coords = eph.Galactic(x,y)
            self.glat  = coords.lat
            self.glong = coords.long
            coords = eph.Equatorial(x,y)
            self._ra  = coords.ra
            self._dec = coords.dec

        elif system == "ewdec":
            ns,ew = ewdec_to_nsew(x,y)
            self.ew = x
            self.ns = ns
            self.system = "nsew"

        elif system == "horizontal":
            observatory = Molonglo(date,self.epoch)
            self._ra,self._dec = observatory.radec_of(x,y)

        elif system == "nsew":
            self.ns = x
            self.ew = y

        self._compute(date=date)

    def _compute(self,date=None):
        if self.system == "nsew":
            return
        self.observatory = Molonglo(date=date,epoch=self.epoch)
        self.lst = str(self.observatory.sidereal_time())
        self.compute(self.observatory)
        self.get_galactic()
        self.get_ha()
        self.get_nsew()

    def get_galactic(self):
        gal = eph.Galactic(eph.Equatorial(self.a_ra,self.a_dec))
        self.glat = gal.lat
        self.glon = gal.long

    def get_ha(self):
        self.ha = np.arcsin(-1*np.cos(self.alt)*np.sin(self.az)
                             /np.cos(self.a_dec))

    def get_nsew(self):
        print "Calling get_nsew"
        self.ew = np.arcsin((0.9999940546 * np.cos(self.a_dec) * np.sin(self.ha))
                            - (0.0029798011806 * np.cos(self.a_dec) * np.cos(self.ha))
                            + (0.002015514993 * np.sin(self.a_dec)))
        self.ns = np.arcsin(((-0.0000237558704 * np.cos(self.a_dec) * np.sin(self.ha))
                             + (0.578881847 * np.cos(self.a_dec) * np.cos(self.ha))
                             + (0.8154114339 * np.sin(self.a_dec)))
                            / np.cos(self.ew))
        print "done"

    def next_rise(self):
        self._compute()
        return self.observatory.next_rising(self)

    def next_set(self):
        self._compute()
        return self.observatory.next_setting(self)

    def next_transit(self):
        self._compute()
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

# the next few functions are a copy an paste job from an updated version of this file
# the repeated functions are left in for legacy applications.
def hadec_to_nsew(ha,a_dec):
    ew = np.arcsin((0.9999940546 * np.cos(a_dec) * np.sin(ha))
                    - (0.0029798011806 * np.cos(a_dec) * np.cos(ha))
                    + (0.002015514993 * np.sin(a_dec)))
    ns = np.arcsin(((-0.0000237558704 * np.cos(a_dec) * np.sin(ha))
                        + (0.578881847 * np.cos(a_dec) * np.cos(ha))
                        + (0.8154114339 * np.sin(a_dec)))
                        / np.cos(ew))
    return ns,ew

# ewdec conversion function
def ewdec_to_nsew(ew,dec):
    A = 0.9999940546
    B = 0.0029798011806
    C = 0.002015514993
    E = -1.00000443965
    F = 0.00297981007727
    ha = F - np.arcsin((np.sin(ew)-C*np.sin(dec))/(A*E*np.cos(dec)))
    ns,ew = hadec_to_nsew(ha,dec)
    return ns,ew

def _replace_nan(a,b,value=np.inf):
    to_replace = np.isnan(a) | np.isnan(b)
    a[to_replace] = value
    b[to_replace] = value
    return a,b

def nsew_to_hadec(ns,ew,precision=0.0001,init_res=0.1):
    """Determing the HA and Decl of a given set of Molonglo NSEW coordinates.

    Args:
    ns - north south angle in radians
    ew - meridian distance angle in radians (east is -ve)
    precision - the precision with which to calculate the result
    init_res - the initial resolution of the grid to search

    Return:
    Hour angle in radians, Declination in radians
    """

    def recursive_solve(grid,res):
        print "Searching grid (resolution=%f)"%res

        # flatten out the search grid for simplicity
        a_dec,ha = grid[0].ravel(),grid[1].ravel()

        # get the ns-ew coordinate for every ha and dec in the grid
        # this may raise warnings (that can be safely ignored)
        ns_,ew_ = hadec_to_nsew(ha,a_dec)

        # replace any dud values by infinity
        ns_,ew_ = _replace_nan(ns_,ew_)

        # find the closest point to the desired ns-ew
        pos = np.argmin(np.sqrt((ns_-ns)**2+(ew_-ew)**2))
        print "Acheived: ",ns_[pos],ew_[pos]

        # if we have not yet reached our desired precision, recurse
        # else return the determined values
        if abs(ns-ns_[pos]) > precision or abs(ew-ew_[pos]) > precision:
            # increase the resolution for the next search (i.e. narrow the grid)
            new_res = 2*res*init_res

            # generate new grid to search
            new_grid = np.mgrid[a_dec[pos]-res:a_dec[pos]+res:new_res,ha[pos]-res:ha[pos]+res:new_res]
            return recursive_solve(new_grid,new_res)
        else:
            return ha[pos],a_dec[pos]

    print "Target (ns,ew):",ns,ew

    # generate an initial grid of declinations and hour angles
    init_grid = np.mgrid[-np.pi/2:np.pi/2:init_res,0:np.pi:init_res]
    return recursive_solve(init_grid,init_res)

