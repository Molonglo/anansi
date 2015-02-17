from datetime import datetime
from threading import _Timer,Thread,Event
import ctypes as C
from struct import unpack,pack
from lxml import etree
from numpy import pi
 
class CustomTimer(_Timer):
    def __init__(self,interval,func,*args,**kwargs):
        super(CustomTimer,self).__init__(interval,func,*args,**kwargs)
        self.name = "timer(%.1f)"%(interval)
        
class RepeatTimer(Thread):
    def __init__(self, interval, func, args=[], kwargs={}):
        super(RepeatTimer,self).__init__()
        self.interval = interval
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.event = Event()
        self.event.set()
        self._timer = None
        self.daemon = True
        self.name = "RepeatTimer"
        
    def run(self):
        self.func(*self.args,**self.kwargs)
        while self.event.is_set():
            self._timer = CustomTimer(self.interval,
                                      self.func,
                                      self.args,
                                      self.kwargs)
            self._timer.start()
            self._timer.join()
 
    def cancel(self):
        self.event.clear()
        if self._timer is not None:
            self._timer.cancel()
 
    def trigger(self):
        self.callable(*self.args, **self.kwargs)
        if self._timer is not None:
            self._timer.cancel()

class NestedDict(dict):
    def __missing__(self, key):
        self[key] = NestedDict()
        return self[key]

def gen_xml_element(name,text=None,attributes=None):
    root = etree.Element(name)
    if attributes is not None:
        for key,val in attributes.items():
            root.attrib[key] = val
    if text is not None:
        root.text = text
    return root

def d2r(val):
    return pi*val/180.

def r2d(val):
    return 180.*val/pi
