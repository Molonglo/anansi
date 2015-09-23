import Tkinter as tk
from anansi import args
from anansi.config import config,update_config_from_args
from anansi.ui_tools.dict_controller import DictController
from anansi.tcc.drives import NSDriveInterface,MDDriveInterface
from collections import OrderedDict

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
        tk.Label(self,text=label_text).pack(side=tk.LEFT)
        self.state_var = tk.StringVar()
        self.state_menu = tk.OptionMenu(self, self.state_var, "auto", "slow", "disabled")
        self.state_var.set("auto")
        self.state_menu.pack(side=tk.RIGHT)
        

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
        self.entry = tk.Entry(self,textvariable=self.value, validate='key',
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
    def __init__(self,parent,default):
        tk.Frame.__init__(self,parent)
        tk.Label(self,text="Counts").pack(side=tk.TOP)
        
        self.system = tk.StringVar()
        self.system.set("NS drive counts")
        self.units = tk.StringVar()
        self.units.set("counts")
        
        x,y = ["East","West"]
        self.xy_frame = tk.Frame(self)
        self.x_coord = ParamController(self.xy_frame,x,default)
        self.x_coord.pack()
        self.y_coord = ParamController(self.xy_frame,y,default)
        self.y_coord.pack()
        self.xy_frame.pack(side=tk.LEFT,pady=1)
                
    def get_xy(self):
        x = int(self.x_coord.get())
        y = int(self.y_coord.get())
        return x,y
        

class NSControls(tk.Frame):
    def __init__(self,parent,drive,pos,arms):
        tk.Frame.__init__(self,parent)
        self.parent = parent
        self.drive = drive
        self.pos = pos
        self.east_arm = arms.east
        self.west_arm = arms.west
        tk.Button(self,text="Drive",command=self.drive_to).pack(side=tk.LEFT)
        tk.Button(self,text="Stop",command=self.stop).pack(side=tk.LEFT)
        tk.Button(self,text="Status",command=self.get_status).pack(side=tk.LEFT)
        tk.Button(self,text="Close",command=self.close).pack(side=tk.LEFT)
        
    def get_status(self):
        print self.drive.get_status()

    def drive_to(self):
        east_state = self.east_arm.state_var.get()
        west_state = self.west_arm.state_var.get()
        east_count,west_count = self.pos.get_xy()
        if east_state!="disabled" and west_state!="disabled":
            self.drive.set_tilts_from_counts(east_count,west_count)
        elif east_state!="disabled" and west_state=="disabled":
            self.drive.set_east_tilt_from_counts(east_count)
        elif east_state=="disabled" and west_state!="disabled":
            self.drive.set_west_tilt_from_counts(east_count)
        else:
            raise Exception("Both arms disabled")

    def stop(self):
        self.drive.stop()

    def close(self):
        self._root().destroy()


class MDControls(NSControls):
    def __init__(self,parent,drive,pos,arms):
        NSControls.__init__(self,parent,drive,pos,arms)
        tk.Button(self,text="Start SAZ",command=self.start_saz).pack(side=tk.LEFT)
        tk.Button(self,text="Stop SAZ",command=self.stop_saz).pack(side=tk.LEFT)
        
    def _get_code(self):
        east_state = self.east_arm.state_var.get()
        west_state = self.west_arm.state_var.get()
        east_arm = east_state!="disabled"
        west_arm = west_state!="disabled"
        if east_arm and west_arm:
            code = "B"
        elif east_arm:
            code = "E"
        elif west_arm:
            code = "W"
        else:
            raise Exception("Both arms disabled")
        return code
            
    def start_saz(self):
        self.drive.zero_meridian_drives(self._get_code(),1)

    def stop_saz(self):
        self.drive.zero_meridian_drives(self._get_code(),0)
        


class DriveGui(tk.Frame):
    def __init__(self,parent,drive,control_class,default):
        tk.Frame.__init__(self,parent)
        tk.Label(self,text=control_class.__name__).pack(side=tk.TOP)
        self.drive = drive
        self.parent = parent
        frame = tk.Frame(self)
        self.coord = CoordController(frame,default)
        self.coord.pack(side=tk.LEFT)
        self.arms = Arms(frame)
        self.arms.pack(side=tk.LEFT)
        frame.pack(side=tk.TOP,padx=20)
        self.controls = control_class(self,self.drive,
                                 self.coord,self.arms)
        self.controls.pack(side=tk.BOTTOM,pady=15)




if __name__ == "__main__":
    update_config_from_args(args.parse_anansi_args())
    root = tk.Tk()
    ns_drive = NSDriveInterface()
    ui = DriveGui(root,ns_drive,NSControls,int(config.ns_drive.tilt_zero))
    ui.pack()
    md_drive = MDDriveInterface()
    ui = DriveGui(root,md_drive,MDControls,int(config.md_drive.tilt_zero))
    ui.pack()
    root.mainloop()
