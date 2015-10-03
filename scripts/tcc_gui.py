import Tkinter as tk
from lxml import etree
from collections import OrderedDict
from numpy import pi
from anansi import args
from anansi.config import config,update_config_from_args
from anansi.comms import TCPClient
from anansi.tcc.tcc_utils import TCCMessage
from anansi.ui_tools.dict_controller import DictController
from anansi.ui_tools.accordion import Accordion,Chord
from anansi.tcc.drives import VALID_STATES,AUTO,SLOW,DISABLED
from anansi.utils import r2d

def aabbcc_validate(value,min_,max_):
    try:
        h,m,s = value.split(":")
        h = min_ <= int(h) < max_
        m = 0 <= int(m) < 60
        s = 0 <= float(s) < 60.0
        return h and s and m
    except:
        return False

hhmmss = lambda val: aabbcc_validate(val,0,24)
ddmmss = lambda val: aabbcc_validate(val,-90,90)
dec_deg = lambda val: -90.0 < float(val) < 90.0
dec_rad = lambda val: -pi/2 <= float(val) < pi/2
ra_deg = lambda val: 0.0 <= float(val) < 360.0
ra_rad = lambda val: 0.0 <= float(val) < pi*2    

UNITS = {
    "hhmmss":{
        "validators":[hhmmss,ddmmss],
        "defaults": ["00:00:00","00:00:00"]
        },
    "degrees":{
        "validators":[ra_deg,dec_deg],
        "defaults": ["0.0","0.0"],
        },
    "radians":{
        "validators":[ra_rad,dec_rad],
        "defaults": ["0.0","0.0"],
        }
    }

SYSTEMS = {
    "equatorial":{
        "labels":["RA","Dec"],
        "units":["hhmmss","degrees","radians"]
        },
    "equatorial_ha":{
        "labels":["HA","Dec"],
        "units":["hhmmss","degrees","radians"]
        },
    "galactic":{
        "labels":["Glong","Glat"],
        "units":["degrees","radians"]
        },
    "ecliptic":{
        "labels":["Elong","Elat"],
        "units":["degrees","radians"]
        },
    "horizontal":{
        "labels":["Az","Elv"],
        "units":["degrees","radians"]
        },
    "nsew":{
        "labels":["NS","EW"],
        "units":["degrees","radians"]
        }
    }

TRACKING_SYSTEMS = ["equatorial","galactic","ecliptic"]

class ObservableMixin(object):
    def __init__(self):
        self.callbacks = []

    def register_callback(self,callback):
        self.callbacks.append(callback)

    def notify(self):
        for callback in self.callbacks:
            callback()


class Validator(object):
    def __init__(self,func):
        self.func = func
        self._onvalid = None
        self._oninvalid = None

    def valid_callback(self,func):
        self._onvalid = func

    def invalid_callback(self,func):
        self._oninvalid = func
        
    def __call__(self,value):
        if self.validate(value):
            if self._onvalid:
                self._onvalid()
            return True
        else:
            if self._oninvalid:
                self._oninvalid()
            return True
            
    def validate(self,value):
        try:
            return self.func(value)
        except Exception as e:
            print e
            return False


class ValueEntry(tk.Frame,object):
    def __init__(self,parent,name,value,units,validator,show_units=False):
        tk.Frame.__init__(self,parent)
        self._text = tk.StringVar()
        self._text.set(name)
        self._value = tk.StringVar()
        self._value.set(value)
        self._units = tk.StringVar()
        self._units.set(units)
        self._validator = validator
        self._show_units = show_units
        self.init()

    def _init_validator(self):
        validator = self.register(self._validator)
        self._entry.config(validate='all', validatecommand=(validator, '%P'))
        self._validator.valid_callback(lambda: self._entry.config(bg='white'))
        self._validator.invalid_callback(lambda: self._entry.config(bg='red'))
        
    def init(self):
        self._text_label = tk.Label(self,textvariable=self._text,width=6)
        validator = self.register(self._validator)
        self._entry = tk.Entry(self,textvariable=self._value, width=12)
        self._init_validator()
        self._text_label.pack(side=tk.LEFT)
        self._entry.pack(side=tk.LEFT)
        if self._show_units:
            self._units_label = tk.Label(self,textvariable=self._units,width=8,justify=tk.LEFT)
            self._units_label.pack(side=tk.LEFT)

    @property
    def label(self):
        return self._text.get()
    
    @label.setter
    def label(self,val):
        self._text.set(val)
        
    @property
    def value(self):
        return self._value.get()

    @value.setter
    def value(self,val):
        self._value.set(val)
        self._entry.focus()

    @property
    def units(self):
        return self._units.get()
    
    @units.setter
    def units(self,val):
        self._units.set(val)

    @property
    def validator(self):
        return self._validator

    @validator.setter
    def validator(self,val):
        self._validator = val
        self._init_validator()



class Selector(tk.Frame,ObservableMixin):
    def __init__(self,parent,values):
        tk.Frame.__init__(self,parent)
        ObservableMixin.__init__(self)
        self._selection = tk.StringVar()
        self._selection.set(values[0])
        self._selection.trace("w",lambda *args:self.notify())
        self._values = values
        self.init()

    def init(self):
        self._selection_menu = tk.OptionMenu(self, self._selection, *self._values)
        self._selection_menu.config(width=12)
        self._selection_menu.pack()

    def _update_values(self):
        self._selection_menu['menu'].delete(0, 'end')
        for choice in self._values:
            self._selection_menu['menu'].add_command(label=choice, command=tk._setit(self._selection, choice))
        self._selection.set(self._values[0])

    @property
    def value(self):
        return self._selection.get()
    
    @value.setter
    def value(self,val):
        self._selection.set(val)

    @property
    def values(self):
        return self._values

    @value.setter
    def values(self,val):
        self._values = val
        self._update_values()


class ArmController(tk.Frame,object):
    def __init__(self,parent,arm):
        tk.Frame.__init__(self,parent)
        self._arm = arm
        self.init()
        
    def init(self):
        self._arm_label = tk.Label(self,text=self._arm,width=12)
        self._mode_selector = Selector(self,VALID_STATES)
        self._mode_selector.value = AUTO
        self._offset = ValueEntry(self,"Offset","0.0","degrees",Validator(dec_deg),show_units=True)
        self._mode_label = tk.Label(self,text="Mode",width=6)
        self._arm_label.pack(side=tk.LEFT)
        self._mode_label.pack(side=tk.LEFT)
        self._mode_selector.pack(side=tk.LEFT)
        self._offset.pack(side=tk.LEFT)

    @property
    def mode(self):
        return self._mode_selector.value

    @property
    def offset(self):
        return self._offset.value

    
class DriveController(tk.Frame):
    def __init__(self,parent,name,**kwargs):
        tk.Frame.__init__(self,parent,**kwargs)
        self._text = name
        self.init()

    def init(self):
        self._name_label = tk.Label(self,text=self._text)
        self._name_label.pack(side=tk.TOP)
        self.east = ArmController(self,"East:  ")
        self.east.pack(side=tk.TOP)
        self.west = ArmController(self,"West:  ")
        self.west.pack(side=tk.TOP)




class CoordinatesController(tk.Frame,object):
    def __init__(self,parent,**kwargs):
        tk.Frame.__init__(self,parent,**kwargs)
        self.init()

    def init(self):
        self._title = tk.Label(self,text="Telescope Coordinates")
        self._system_selector = Selector(self,SYSTEMS.keys())
        self._system_selector.value = "equatorial"
        self._system = SYSTEMS[self._system_selector.value]
        self._units_selector = Selector(self,self._system['units'])
        self._units = UNITS[self._units_selector.value]
        self._coords_frame = tk.Frame(self)
        self._x = ValueEntry(self._coords_frame,
                             self._system['labels'][0],
                             self._units['defaults'][0],
                             self._units_selector.value,
                             Validator(self._units['validators'][0]))
        self._y = ValueEntry(self._coords_frame,
                             self._system['labels'][1],
                             self._units['defaults'][1],
                             self._units_selector.value,
                             Validator(self._units['validators'][1]))
        self._system_selector.register_callback(self.update_system)
        self._units_selector.register_callback(self.update_units)
        self._title.pack()
        self._coords_frame.pack(side=tk.LEFT)
        self._system_selector.pack(side=tk.LEFT)
        self._units_selector.pack(side=tk.LEFT)
        self._x.pack()
        self._y.pack()
        
    def _update_x(self):
        self._x.label = self._system['labels'][0]
        self._x.value = self._units['defaults'][0]
        self._x.units = self._units_selector.value
        self._x.validator = Validator(self._units['validators'][0])
        
    def _update_y(self):
        self._y.label = self._system['labels'][1]
        self._y.value = self._units['defaults'][1]
        self._y.units =self._units_selector.value
        self._y.validator = Validator(self._units['validators'][1])

    def update_units(self):
        self._units = UNITS[self._units_selector.value]
        self._update_x()
        self._update_y()

    def update_system(self):
        self._system = SYSTEMS[self._system_selector.value]
        self._units_selector.values = self._system['units']
        self.update_units()
        
    @property
    def system(self):
        return self._system_selector.value
    
    @property
    def units(self):
        return self._units_selector.value
    
    @property
    def x(self):
        return self._x.value

    @property
    def y(self):
        return self._y.value


class ArmStatus(tk.Frame,object):
    def __init__(self,parent,arm):
        tk.Frame.__init__(self,parent,relief=tk.SUNKEN,borderwidth=2,padx=5,pady=2)
        self._arm = arm
        self._state = AUTO
        self._state_var = tk.StringVar()
        self._state_var.set("Idle")
        self._tilt_var = tk.StringVar()
        self._tilt_var.set("Tilt: 0.0 radians")
        self._tilt = 0.0
        self._driving = False
        self._on_target = False
        self.init()
        
    def init(self):
        self._arm_label = tk.Label(self,text=self._arm)
        self._state_label = tk.Label(self,textvariable=self._state_var)
        self._tilt_label = tk.Label(self,textvariable=self._tilt_var)
        self._arm_label.pack()
        self._state_label.pack()
        self._tilt_label.pack()
    
    def _set_colour(self):
        def _set(colour):
            self._arm_label.config(bg=colour)
            self._state_label.config(bg=colour)
            self._tilt_label.config(bg=colour)
            self.config(bg=colour)
        if self._state == DISABLED:
            _set("red")
        elif self._on_target: 
            _set("green")
        elif self._driving:
            _set("yellow")
        else:
            _set("white")

    @property
    def tilt(self):
        return self._tilt
    
    @tilt.setter
    def tilt(self,val):
        self._tilt = val
        self._tilt_var.set("Tilt: %.2f deg"%r2d(val))
        
    @property
    def driving(self):
        return self._driving
    
    @driving.setter
    def driving(self,val):
        self._driving = val
        if self._state == DISABLED:
            self._state_var.set("Disabled")
        elif self._driving: 
            self._state_var.set("Driving")
        else:
            self._state_var.set("Idle")
        self._set_colour()
            
    @property
    def on_target(self):
        return self._on_target
    
    @on_target.setter
    def on_target(self,val):
        self._on_target = val
        self._set_colour()
        
    @property
    def state(self):
        return self._state
    
    @state.setter
    def state(self,val):
        self._state = val
        if self._state == DISABLED:
            self._state_var.set("Disabled")
        self._set_colour()

class DriveStatus(tk.Frame,object):
    def __init__(self,parent,drive):
        tk.Frame.__init__(self,parent,relief=tk.SUNKEN,borderwidth=2)
        self._drive = drive
        self._error_var = tk.StringVar()
        self._error_var.set("Error: None")
        self.init()
        
    def init(self):
        tk.Label(self,text=self._drive).pack()
        self._error_label = tk.Label(self,textvariable=self._error_var,relief=tk.SUNKEN,borderwidth=2)
        self._arms_frame = tk.Frame(self)
        self._east = ArmStatus(self._arms_frame,"East Arm")
        self._west = ArmStatus(self._arms_frame,"West Arm")
        self._east.pack(side=tk.LEFT)
        self._west.pack(side=tk.LEFT)
        self._error_label.pack(fill=tk.BOTH)
        self._arms_frame.pack()

    @property
    def error(self):
        return self._error_var.get()
    
    @error.setter
    def error(self,val):
        if val == "None":
            self._error_label.config(bg='green')
            self._error_var.set("Error: None")
        else:
            self._error_label.config(bg='red')
            self._error_var.set("Error: %s"%val)
            

class StatusMonitor(tk.Frame):
    def __init__(self,parent,status_ip,status_port):
        tk.Frame.__init__(self,parent,relief=tk.SUNKEN,borderwidth=2)
        self.status_ip = status_ip
        self.status_port = status_port
        self._target_var = tk.StringVar()
        self._target_var.set("[Source]  NS  %.2f deg  MD  %.2f deg"%(0.0,0.0))
        self.init()
        self.update()

    def init(self):
        self._target_label = tk.Label(self,textvariable=self._target_var,relief=tk.SUNKEN,borderwidth=2)
        self._drive_frame = tk.Frame(self)
        self._ns_drive = DriveStatus(self._drive_frame,"NS Drive Status")
        self._md_drive = DriveStatus(self._drive_frame,"MD Drive Status")
        self._target_label.pack(fill=tk.BOTH)
        self._drive_frame.pack()
        self._ns_drive.pack(side=tk.LEFT)
        self._md_drive.pack(side=tk.LEFT)

    def update(self):
        try:
            self._update()
        except Exception as error:
            print error
        finally:
            self.after(3000,self.update)

    def _update(self):
        client = TCPClient(self.status_ip,self.status_port,timeout=5.0)
        response = client.receive(64000)
        try:
            xml = etree.fromstring(response)
        except Exception as error:
            print "Failed to retrieve status from TCC"
            print str(error)
            print response
            return
        finally:
            client.close()
        coords = xml.find("coordinates")
        ns = float(coords.find("NS").text)
        md = float(coords.find("EW").text)
        self._target_var.set("[Source]  NS  %.2f deg  MD  %.2f deg"%(r2d(ns),r2d(md)))
        for drive in ['ns','md']:
            _drive_ui = getattr(self,"_%s_drive"%drive)
            _drive = xml.find(drive)
            _drive_ui.error = _drive.find('error').text
            for arm in ['east','west']:
                _arm_ui = getattr(_drive_ui,"_%s"%arm)
                _arm = _drive.find(arm)
                _arm_ui.tilt = float(_arm.find('tilt').text)
                _arm_ui.driving = _arm.find('driving').text == 'True'
                _arm_ui.on_target = _arm.find('on_target').text == 'True'

class Controls(tk.Frame):
    def __init__(self,parent,anansi_ip,anansi_port,
                 status_ip,status_port,pos,ns_drive,md_drive):
        tk.Frame.__init__(self,parent)
        self.anansi_ip = anansi_ip
        self.anansi_port = anansi_port
        self.status_ip = status_ip
        self.status_port = status_port
        self.pos = pos
        self.ns_drive = ns_drive
        self.md_drive = md_drive
        self.init()

    def init(self):
        tk.Button(self,text="Observe",command=self.observe).pack(side=tk.LEFT)
        tk.Button(self,text="Wind Stow",command=self.wind_stow).pack(side=tk.LEFT)
        tk.Button(self,text="Maintenance Stow",command=self.maintenance_stow).pack(side=tk.LEFT)
        tk.Button(self,text="Stop",command=self.stop).pack(side=tk.LEFT)
        tk.Button(self,text="Status",command=self.recv_status).pack(side=tk.LEFT)
        tk.Button(self,text="Close",command=self.close).pack(side=tk.LEFT)
    
    def send_recv_anansi(self,msg):
        print repr(msg)
        client = TCPClient(self.anansi_ip,self.anansi_port,timeout=20.0)
        client.send(str(msg))
        print str(msg)
        response = client.receive()
        client.close()
        try:
            xml = etree.fromstring(response)
        except etree.XMLSyntaxError:
            print response
        else:
            print etree.tostring(xml,encoding='ISO-8859-1',pretty_print=True)
                
    def recv_status(self):
        client = TCPClient(self.status_ip,self.status_port,timeout=5.0)
        response = client.receive(64000)
        print response
        try:
            xml = etree.fromstring(response)
            print etree.tostring(xml,encoding='ISO-8859-1',pretty_print=True)
        except Exception as error:
            print str(error)
            print response
        client.close()

    def observe(self):
        system = self.pos.system
        units = self.pos.units
        if system in TRACKING_SYSTEMS:
            track = "on"
        else:
            track = "off"
        x = self.pos.x
        y = self.pos.y
        msg = TCCMessage("tcc_gui")
        msg.tcc_pointing(x,y,system=system,
                         tracking=track,
                         ns_east_state=self.ns_drive.east.mode,
                         ns_west_state=self.ns_drive.west.mode,
                         md_east_state=self.md_drive.east.mode,
                         md_west_state=self.md_drive.west.mode,
                         ns_east_offset=self.ns_drive.east.offset,
                         ns_west_offset=self.ns_drive.west.offset,
                         md_east_offset=self.md_drive.east.offset,
                         md_west_offset=self.md_drive.west.offset,
                         units=units,
                         offset_units="degrees")
        self.send_recv_anansi(msg)

    def wind_stow(self):
        msg = TCCMessage("tcc_gui")
        msg.tcc_command("wind_stow")
        self.send_recv_anansi(msg)

    def maintenance_stow(self):
        msg = TCCMessage("tcc_gui")
        msg.tcc_command("maintenance_stow")
        self.send_recv_anansi(msg)

    def stop(self):
        msg = TCCMessage("tcc_gui")
        msg.tcc_command("stop")
        self.send_recv_anansi(msg)

    def close(self):
        self._root().destroy()


class TCCGraphicalInterface(tk.Frame):
    def __init__(self,parent,anansi_ip,anansi_port,status_ip,status_port):
        tk.Frame.__init__(self,parent)
        self._coordinate_controller = CoordinatesController(self)
        self._accordion = Accordion(self)
        self._ns_chord = Chord(self._accordion, title='NS Drive Controls')
        self._ns_drive = DriveController(self._ns_chord,"NS Drive")
        self._ns_drive.pack()
        self._md_chord = Chord(self._accordion, title='MD Drive Controls')
        self._md_drive = DriveController(self._md_chord,"MD Drive")
        self._md_drive.pack()
        self._accordion.append_chords([self._ns_chord,self._md_chord])
        self._coordinate_controller.pack(pady=10)
        self._accordion.pack(fill='both', expand=1)
        self.controls = Controls(self,anansi_ip,anansi_port,
                                 status_ip,status_port,
                                 self._coordinate_controller,
                                 self._ns_drive,
                                 self._md_drive)
        self.controls.pack(pady=15,fill=tk.BOTH,padx=10)
        self.status = StatusMonitor(self,status_ip,status_port)
        self.status.pack(pady=15,fill=tk.BOTH)


def test():
    root = tk.Tk()
    tcc = config.tcc_server
    status = config.status_server
    ui = TCCGraphicalInterface(root,tcc.ip,tcc.port,status.ip,status.port)
    ui.pack()
    return ui

if __name__ == "__main__":
    update_config_from_args(args.parse_anansi_args())
    root = tk.Tk()
    tcc = config.tcc_server
    status = config.status_server
    ui = TCCGraphicalInterface(root,tcc.ip,tcc.port,status.ip,status.port)
    ui.pack()
    root.wm_title("Anansi TCC Interface")
    root.mainloop()
