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
    "nsew":["NS","EW"]
}

UNITS = [
    "hhmmss",
    "degrees",
    "radians",
    "counts"
]

class ArmController(tk.Frame):
    def __init__(self,parent,label_text):
        tk.Frame.__init__(self,parent)
        tk.Label(self,text=label_text).pack(side=tk.TOP)
        self.enabled = tk.StringVar()
        self.enabled.set("disabled")
        self.enabled_cb = tk.Checkbutton(
            self, text="Enable", variable=self.enabled,
            onvalue="enabled",offvalue="disabled")
        self.speed = tk.StringVar()
        self.speed.set("auto")
        self.speed_cb = tk.Checkbutton(
            self, text="Force slow", variable=self.speed,
            onvalue="slow",offvalue="auto")
        self.enabled_cb.pack(side=tk.LEFT)
        self.speed_cb.pack(side=tk.RIGHT)


class CoordController(tk.Frame):
    def __init__(self,parent):
        tk.Frame.__init__(self,parent)
        tk.Label(self,text="Coordinates").pack(side=tk.TOP)
        
        self.param_controller = DictController(self,OrderedDict({"RA":"","Dec":""}))
        self.param_controller.pack(side=tk.LEFT,pady=1)

        self.system = tk.StringVar()
        self.system.set("equatorial")
        self.system_menu = tk.OptionMenu(self,self.system,*COORD_SYSTEMS.keys(),
                                         command=self.callback)
        self.system_menu.pack(side=tk.LEFT)
        self.units = tk.StringVar()
        self.units.set("hhmmss")
        self.units_menu = tk.OptionMenu(self,self.units,*UNITS,
                                        command=self.callback)
        self.units_menu.pack(side=tk.RIGHT)

    def get_xy(self):
        a,b = COORD_SYSTEMS[self.system.get()]
        x = self.param_controller[a]
        y = self.param_controller[b]
        return x,y

    def callback(self,*args,**kwargs):
        system = self.system.get()
        units = self.units.get()
        if units == "counts":
            self.system.set("nsew")
        system = self.system.get()
        if units == "hhmmss":
            default = ""
        if units == "counts":
            default = 0
        else:
            default = 0.0
        a,b = COORD_SYSTEMS[system]
        self.param_controller.update(OrderedDict({a:default,b:default}))


class Controls(tk.Frame):
    def __init__(self,parent,ip,port,pos,east_arm,west_arm):
        tk.Frame.__init__(self,parent)
        self.parent = parent
        self.ip = ip
        self.port = port
        self.pos = pos
        self.east_arm = east_arm
        self.west_arm = west_arm
        tk.Button(self,text="Observe",command=self.observe).pack(side=tk.LEFT)
        tk.Button(self,text="Wind Stow",command=self.wind_stow).pack(side=tk.LEFT)
        tk.Button(self,text="Maintenance Stow",command=self.maintenance_stow
                  ).pack(side=tk.LEFT)
        tk.Button(self,text="Stop",command=self.stop).pack(side=tk.LEFT)
        tk.Button(self,text="Close",command=self.close).pack(side=tk.LEFT)

    def send_recv(self,msg):
        client = TCPClient(self.ip,self.port,timeout=5.0)
        print "Sending:"
        print repr(msg)
        client.send(str(msg))
        response = client.receive()
        try:
            xml = etree.fromstring(response)
        except etree.XMLSyntaxError:
            print response
        else:
            print etree.tostring(xml,encoding='ISO-8859-1',pretty_print=True)
                
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
        self.send_recv(msg)

    def wind_stow(self):
        msg = TCCMessage("tcc_gui")
        msg.tcc_command("wind_stow")
        self.send_recv(msg)

    def maintenance_stow(self):
        msg = TCCMessage("tcc_gui")
        msg.tcc_command("maintenace_stow")
        self.send_recv(msg)

    def stop(self):
        msg = TCCMessage("tcc_gui")
        msg.tcc_command("stop")
        self.send_recv(msg)

    def close(self):
        self._root().destroy()


class TCCGraphicalInterface(tk.Frame):
    def __init__(self,parent,ip,port):
        tk.Frame.__init__(self,parent)
        self.parent = parent
        subframe = tk.Frame(self)
        self.coord = CoordController(subframe)
        self.coord.pack(side=tk.LEFT,anchor="n")
        subframe2 = tk.Frame(subframe)
        self.east_arm = ArmController(subframe2,"East Arm")
        self.east_arm.pack()
        self.west_arm = ArmController(subframe2,"West Arm")
        self.west_arm.pack()
        subframe2.pack(side=tk.RIGHT,padx=20)
        subframe.pack(side=tk.TOP)
        self.controls = Controls(self,ip,port,self.coord,self.east_arm,self.west_arm)
        self.controls.pack(side=tk.BOTTOM,pady=15)


if __name__ == "__main__":
    
    config_path = os.environ["ANANSI_CONFIG"]
    config_file = os.path.join(config_path,"anansi.cfg")
    config = ConfigParser()
    config.read(config_file)
    anansi_ip = config.get("IPAddresses","anansi_ip")
    anansi_port = config.getint("IPAddresses","anansi_port")
    root = tk.Tk()
    ui = TCCGraphicalInterface(root,anansi_ip,anansi_port)
    ui.pack()
    root.mainloop()
