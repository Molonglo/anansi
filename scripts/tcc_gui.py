import Tkinter as tk
import os
from lxml import etree
from ConfigParser import ConfigParser
from anansi.tcc.tcc_utils import TCCMessage
from anansi.ui_tools.dict_controller import DictController
from anansi.comms import TCPClient
from collections import OrderedDict

COORD_SYSTEMS = {
    "equatorial":["RA","Dec"],
    "equatorial_ha":["HA","Dec"],
    "galactic":["Glong","Glat"],
    "ewdec":["East","Dec"],
    "horizontal":["Az","Elv"],
    "nsew":["NSe","NSw"]
}

UNITS = {
    "hhmmss":"00:00:00",
    "degrees":"0.0",
    "radians":"0.0",
    "counts":"0"
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
        tk.Label(self,text=label_text).pack(side=tk.TOP)
        self.enabled = LabeledCheckButton(self,"Enable","enabled","disabled")
        self.speed = LabeledCheckButton(self,"Force slow","slow","auto")
        self.enabled.pack(side=tk.LEFT)
        self.speed.pack(side=tk.RIGHT)
        

class Arms(tk.Frame):
    def __init__(self,parent):
        tk.Frame.__init__(self,parent)
        self.east = ArmController(self,"East Arm")
        self.east.pack()
        self.west = ArmController(self,"West Arm")
        self.west.pack()


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
        self.entry.pack(side=tk.RIGHT)

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
            if c.isdigit() or c in [":","."]:
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
        tk.Frame.__init__(self,parent)
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
        if units == "counts":
            self.set_system("nsew")

    def system_callback(self,*args,**kwargs):
        system = self.system.get()
        self.set_system(system)
        

class Controls(tk.Frame):
    def __init__(self,parent,anansi_ip,anansi_port,
                 status_ip,status_port,pos,arms):
        tk.Frame.__init__(self,parent)
        self.parent = parent
        self.anansi_ip = anansi_ip
        self.anansi_port = anansi_port
        self.status_ip = status_ip
        self.status_port = status_port
        self.pos = pos
        self.east_arm = arms.east
        self.west_arm = arms.west
        tk.Button(self,text="Observe",command=self.observe).pack(side=tk.LEFT)
        tk.Button(self,text="Wind Stow",command=self.wind_stow).pack(side=tk.LEFT)
        tk.Button(self,text="Maintenance Stow",command=self.maintenance_stow
                  ).pack(side=tk.LEFT)
        tk.Button(self,text="Stop",command=self.stop).pack(side=tk.LEFT)
        tk.Button(self,text="Status",command=self.recv_status).pack(side=tk.LEFT)
        tk.Button(self,text="Close",command=self.close).pack(side=tk.LEFT)
        
    def send_recv_anansi(self,msg):
        client = TCPClient(self.anansi_ip,self.anansi_port,timeout=5.0)
        print "Sending:"
        print repr(msg)
        client.send(str(msg))
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
        response = client.receive()
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
        if system in ["equatorial_ha","ewdec"]:
            track = "off"
        else:
            track = "on"
        east_arm = self.east_arm.enabled.get()
        west_arm = self.west_arm.enabled.get()
        east_speed = self.east_arm.speed.get()
        west_speed = self.west_arm.speed.get()
        x,y = self.pos.get_xy()
        msg = TCCMessage("tcc_gui")
        msg.tcc_pointing(x,y,system=system,
                         tracking=track,
                         east_arm=east_arm,
                         west_arm=west_arm,
                         east_speed=east_speed,
                         west_speed=west_speed,                         
                         units=units)
        self.send_recv_anansi(msg)

    def wind_stow(self):
        msg = TCCMessage("tcc_gui")
        msg.tcc_command("wind_stow")
        self.send_recv_anansi(msg)

    def maintenance_stow(self):
        msg = TCCMessage("tcc_gui")
        msg.tcc_command("maintenace_stow")
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
        self.coord.pack(side=tk.LEFT)
        self.arms = Arms(frame)
        self.arms.pack(side=tk.LEFT)
        frame.pack(side=tk.TOP,padx=20)
        self.controls = Controls(self,anansi_ip,anansi_port,
                                 status_ip,status_port,
                                 self.coord,self.arms)
        self.controls.pack(side=tk.BOTTOM,pady=15)


if __name__ == "__main__":
    
    config_path = os.environ["ANANSI_CONFIG"]
    config_file = os.path.join(config_path,"anansi.cfg")
    config = ConfigParser()
    config.read(config_file)
    anansi_ip = config.get("IPAddresses","anansi_ip")
    anansi_port = config.getint("IPAddresses","anansi_port")
    status_ip = config.get("IPAddresses","status_ip")
    status_port = config.getint("IPAddresses","status_port")
    root = tk.Tk()
    ui = TCCGraphicalInterface(root,anansi_ip,anansi_port,status_ip,status_port)
    ui.pack()
    root.mainloop()
