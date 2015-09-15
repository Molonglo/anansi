import warnings
import ephem as eph
import numpy as np
from anansi.utils import d2r,r2d
from anansi.coords import nsew_to_hadec,hadec_to_nsew,azel_to_nsew,nsew_to_azel
from anansi.config import config

class Molonglo(eph.Observer):
    def __init__(self,date=None,epoch=None):
        super(Molonglo,self).__init__()
        if epoch is not None:
            self.epoch = epoch
        if date is not None:
            self.date = date
        mol = config.most_ephemeris
        self.lat       = d2r(mol.latitude)
        self.long      = d2r(mol.longitude)
        self.elevation = mol.elevation
        self.horizon   = d2r(mol.horizon)
        self.compute_pressure()

    def sidereal_time(self):
        return super(Molonglo,self).sidereal_time()

class CoordinatesMixin(object):
    def generate_other_systems(self):
        eq = eph.Equatorial(self.a_ra,self.a_dec,epoch=self._epoch)
        gal = eph.Galactic(eq)
        self.glat = gal.lat
        self.glon = gal.long
        ecl = eph.Ecliptic(eq)
        self.elat = ecl.lat
        self.elon = ecl.long

    def _convert(self):
        def _to_type(_type,name):
            val = getattr(self,name)
            if not isinstance(val,eph.Angle):
                setattr(self,name,_type(val))
        _to_type(eph.degrees,"ns")
        _to_type(eph.degrees,"ew")
        _to_type(eph.hours,"ra")
        _to_type(eph.degrees,"dec")
        _to_type(eph.degrees,"ha")
        _to_type(eph.degrees,"glat")
        _to_type(eph.degrees,"glon")
        _to_type(eph.degrees,"elat")
        _to_type(eph.degrees,"elon")
        _to_type(eph.degrees,"az")
        _to_type(eph.degrees,"alt")
        
    def is_up(self,date=None):
        self.compute(date)
        return self.alt > MOL_HOR
    
    
class RADecCoordinates(eph.FixedBody,CoordinatesMixin):
    def __init__(self,ra,dec,epoch=eph.J2000):
        self._ra = ra
        self._dec = dec
        self._epoch = epoch
        eph.FixedBody.__init__(self)
        
    def compute(self,date=None):
        date = eph.now() if date is None else date
        most = Molonglo(date,self._epoch)
        eph.FixedBody.compute(self,most)
        self.lst = most.sidereal_time()
        self.ha = self.lst - self.ra
        self.ns,self.ew = hadec_to_nsew(self.ha,self.dec)
        self.generate_other_systems()
        self._convert()

class NSEWCoordinates(eph.FixedBody,CoordinatesMixin):
    def __init__(self,ns,ew):
        self.ns = ns
        self.ew = ew
        eph.FixedBody.__init__(self)

    def compute(self,date=None):
        self._epoch = eph.now()
        date = eph.now() if date is None else date
        most = Molonglo(date,self._epoch)
        self.lst = most.sidereal_time()
        self.ha,self._dec = nsew_to_hadec(self.ns,self.ew)
        self._ra = self.lst - self.ha
        eph.FixedBody.compute(self,most)
        self.generate_other_systems()
        self._convert()

class BodyCoordinates(eph.FixedBody,CoordinatesMixin):
    def __init__(self,body,epoch=eph.J2000):
        self.body = body()
        self.body._epoch = epoch
        self._epoch = epoch
        eph.FixedBody.__init__(self)

    def compute(self,date=None):
        date = eph.now() if date is None else date
        most = Molonglo(date,self._epoch)
        self.lst = most.sidereal_time()
        self.body.compute(most)
        self._ra,self._dec = self.body.ra,self.body.dec
        eph.FixedBody.compute(self,most)
        self.ha = self.lst - self.ra
        self.ns,self.ew = hadec_to_nsew(self.ha,self.dec)
        self.generate_other_systems()
        self._convert()

def make_coordinates(x,y,system="equatorial",units="hhmmss",epoch="J2000"):
    system = system.lower()
    units = units.lower()
    epoch = epoch.upper()
    
    try:
        epoch = getattr(eph,epoch)
    except AttributeError as error:
        try:
            epoch = eph.date(epoch)
        except Exception as error:
            raise Exception("Invalid epoch: %s"%epoch)
    
    try:
        if units == "degrees":
            x = eph.degrees(d2r(float(x)))
            y = eph.degrees(d2r(float(y)))
        elif units == "radians":
            x = eph.degrees(float(x))
            y = eph.degrees(float(x))
        elif units == "hhmmss":
            if system in ["equatorial_ha","equatorial"]:
                x = eph.hours(x)
            else:
                x = eph.degrees(x)
                y = eph.degrees(y)
        else:
            raise Exception("Invalid units. Must be degrees, radians or hhmmss.")
    except Exception as error:
        print str(error)
        raise Exception("Invalid coordinates: %s, %s"%(x,y))

    if system in ["equatorial","radec"]:
        return RADecCoordinates(x,y,epoch)

    elif system in ["equatorial_ha","hadec"]:
        ns,ew = hadec_to_nsew(x,y)
        return NSEWCoordinates(ns,ew)
    
    elif system == "nsew":
        return NSEWCoordinates(x,y)
    
    elif system in ["horizontal","azel"]:
        ns,ew = azel_to_nsew(x,y)
        return NSEWCoordinates(ns,ew)

    elif system in ["galactic","glgb"]:
        eq = eph.Equatorial(eph.Galactic(x,y))
        return RADecCoordinates(eq.ra,eq.dec,epoch)
        
    else:
        raise Exception("Unknown coordinate system: %s"%system)
    

def make_body(name,epoch="J2000"):
    name = name.capitalize()
    epoch = epoch.upper()
    try:
        epoch = getattr(eph,epoch)
    except AttributeError as error:
        raise Exception("Invalid epoch: %s"%epoch)
    body = getattr(eph,name)
    return BodyCoordinates(body,epoch)
    

# Old conversion code for ns ew from ha dec
# A version of this is retained as a standard 
# against which to test the telescope coordinate 
# conversion
def get_nsew(dec,ha):
    ew = np.arcsin((0.9999940546 * np.cos(dec) * np.sin(ha))
                   - (0.0029798011806 * np.cos(dec) * np.cos(ha))
                   + (0.002015514993 * np.sin(dec)))
    ns = np.arcsin(((-0.0000237558704 * np.cos(dec) * np.sin(ha))
                    + (0.578881847 * np.cos(dec) * np.cos(ha))
                    + (0.8154114339 * np.sin(dec)))
                   / np.cos(ew))
    return ns,ew

