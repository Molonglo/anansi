import Tkinter as tk
from lxml import etree
from collections import OrderedDict
from anansi import args
from anansi.config import config,update_config_from_args
from anansi.comms import TCPClient
from anansi.tcc.tcc_utils import TCCMessage
from anansi.ui_tools.dict_controller import DictController

COORD_SYSTEMS = {
    "equatorial":["RA","Dec"],
    "equatorial_ha":["HA","Dec"],
    "galactic":["Glong","Glat"],
    "ecliptic":["Elong","Elat"],
    "horizontal":["Az","Elv"],
    "nsew":["NS","EW"]
}

UNITS = {
    "hhmmss":"00:00:00",
    "degrees":"0.0",
    "radians":"0.0"
}

class LabeledCheckButton(tk.Frame):
    def __init__(self,parent,text,onvalue,offvalue):
        tk.Frame.__init__(self,parent)
        self.var = tk.StringVar()
        self.var.set(offvalue)
        self.cb = tk.Checkbutton(
            self, text=text, variable=self.var,
            onvalue=onvalue, offvalue=offvalue)
        self.cb.pack()

    def get(self):
        return self.var.get()

    def set(self,val):
        self.var.set(val)


class ArmController(tk.Frame):
    def __init__(self,parent,label_text):
        tk.Frame.__init__(self,parent)
        tk.Label(self,text=label_text,width=5).pack(side=tk.LEFT)
        tk.Label(self,text="State").pack(side=tk.LEFT)
        self.state_var = tk.StringVar()
        self.state_menu = tk.OptionMenu(self, self.state_var, "auto", "slow", "disabled")
        self.state_menu.config(width=6,padx=20)
        self.state_var.set("auto")
        self.state_menu.pack(side=tk.LEFT)
        self.offset_entry = ParamController(self,"Offset","0.0")
        self.offset_entry.pack(side=tk.LEFT)
        tk.Label(self.offset_entry,text="degrees").pack(side=tk.LEFT)

    @property
    def state(self):
        return self.state_var.get()

    @property
    def offset(self):
        return float(self.offset_entry.get())
    

class DriveController(tk.Frame):
    def __init__(self,parent,name):
        tk.Frame.__init__(self,parent,relief=tk.SUNKEN,borderwidth=2,padx=5,pady=20)
        tk.Label(self,text=name).pack(side=tk.TOP)
        self.east = ArmController(self,"East:")
        self.east.pack(side=tk.TOP)
        self.west = ArmController(self,"West:")
        self.west.pack(side=tk.TOP)


class ParamController(tk.Frame):
    def __init__(self,parent, key, val):
        tk.Frame.__init__(self, parent)
        self.text = tk.StringVar()
        self.text.set(key)
        self.value = tk.StringVar()
        self.value.set(val)
        self.label = tk.Label(self,textvariable=self.text,justify=tk.LEFT,width=4)
        validator = self.register(self.validator)
        self.entry = tk.Entry(self,textvariable=self.value, validate='all',
                              validatecommand=(validator, '%P', '%s'),width=12)
        self.label.pack(side=tk.LEFT)
        self.entry.pack(side=tk.LEFT)

    def set_bg(self,c):
        try:
            self.entry.config(bg=c)
        except Exception as error:
            print str(error)

    def validator(self,value,last_value):
        if value.strip() == "":
            self.set_bg('red')
            self.bell()
            return True
        elif value:
            c = value[-1]
            if c.isdigit() or c in [":",".","-"]:
                self.set_bg('white')
                return True
            else:
                self.bell()
                return False

    def set_label(self,val):
        self.text.set(val)

    def get(self):
        return self.value.get()


class CoordController(tk.Frame):
    def __init__(self,parent):
        tk.Frame.__init__(self,parent,relief=tk.SUNKEN,borderwidth=2,padx=5,pady=20)
        tk.Label(self,text="Coordinates").pack(side=tk.TOP)
        
        self.system = tk.StringVar()
        self.system.set("equatorial")
        self.units = tk.StringVar()
        self.units.set("hhmmss")
        
        x,y = COORD_SYSTEMS["equatorial"]
        self.xy_frame = tk.Frame(self)
        self.x_coord = ParamController(self.xy_frame,x,"00:00:00")
        self.x_coord.pack()
        self.y_coord = ParamController(self.xy_frame,y,"00:00:00")
        self.y_coord.pack()
        self.xy_frame.pack(side=tk.LEFT,pady=1)
        
        self.system_menu = tk.OptionMenu(self,self.system,
                                         *COORD_SYSTEMS.keys(),
                                         command=self.system_callback)
        self.system_menu.pack(side=tk.LEFT)
        
        self.units_menu = tk.OptionMenu(self,self.units,*UNITS.keys(),
                                        command=self.units_callback)
        self.units_menu.pack(side=tk.LEFT)

    def set_system(self,system):
        x,y = COORD_SYSTEMS[system]
        self.x_coord.set_label(x)
        self.y_coord.set_label(y)
        
    def get_xy(self):
        x = self.x_coord.get()
        y = self.y_coord.get()
        return x,y

    def units_callback(self,*args,**kwargs):
        units = self.units.get()

    def system_callback(self,*args,**kwargs):
        system = self.system.get()
        self.set_system(system)
        

class Controls(tk.Frame):
    def __init__(self,parent,anansi_ip,anansi_port,
                 status_ip,status_port,pos,ns_drive,md_drive):
        tk.Frame.__init__(self,parent)
        self.parent = parent
        self.anansi_ip = anansi_ip
        self.anansi_port = anansi_port
        self.status_ip = status_ip
        self.status_port = status_port
        self.pos = pos
        self.ns_drive = ns_drive
        self.md_drive = md_drive
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
        system = self.pos.system.get()
        units = self.pos.units.get()
        if system in ["equatorial_ha","horizontal","nsew"]:
            track = "off"
        else:
            track = "on"
        x,y = self.pos.get_xy()
        msg = TCCMessage("tcc_gui")
        msg.tcc_pointing(x,y,system=system,
                         tracking=track,
                         ns_east_state=self.ns_drive.east.state,
                         ns_west_state=self.ns_drive.west.state,
                         md_east_state=self.md_drive.east.state,
                         md_west_state=self.md_drive.west.state,
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
        self.parent = parent
        frame = tk.Frame(self)
        self.coord = CoordController(frame)
        self.coord.pack(side=tk.TOP)
        self.ns_drive = DriveController(frame,"NS Drive")
        self.ns_drive.pack(side=tk.TOP)
        self.md_drive = DriveController(frame,"MD Drive")
        self.md_drive.pack(side=tk.TOP)
        frame.pack(side=tk.TOP,padx=20)
        self.controls = Controls(self,anansi_ip,anansi_port,
                                 status_ip,status_port,
                                 self.coord,self.ns_drive,self.md_drive)
        self.controls.pack(side=tk.BOTTOM,pady=15)


if __name__ == "__main__":
    update_config_from_args(args.parse_anansi_args())
    root = tk.Tk()
    tcc = config.tcc_server
    status = config.status_server
    ui = TCCGraphicalInterface(root,tcc.ip,tcc.port,status.ip,status.port)
    ui.pack()
    root.mainloop()
    
