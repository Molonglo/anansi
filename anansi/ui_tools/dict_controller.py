import Tkinter as tk
import warnings

VAR_TYPES = {
    int: tk.IntVar,
    float: tk.DoubleVar,
    str: tk.StringVar
    }

class ParameterController(tk.Frame):
    def __init__(self,parent, key, value):
        tk.Frame.__init__(self, parent)
        self.value_type = type(value)
        self._var = VAR_TYPES[self.value_type]()
        self._var.set(value)
        self._label = tk.Label(self,text=key,justify=tk.LEFT,width=4)
        self._label.pack(side=tk.LEFT,padx=1,anchor="e",fill=tk.BOTH)
        validator = self.register(self.validator)
        self._entry = tk.Entry(self,textvariable=self._var, validate='all',
                               validatecommand=(validator, '%P', '%s'),width=12)
        self._entry.pack(side=tk.RIGHT,expand=1,padx=2)
        
    def set_bg(self,colour):
        try:
            self._entry.config(bg=colour)
        except:
            pass

    def validator(self,value,last_value):
        if not value.strip() and not self.value_type == str:
            self.set_bg('red')
            self.bell()
            return True
        else:
            try:
                self.value_type(value)
            except Exception as error:
                return False
            else:
                self.set_bg('white')
                return True
        
    def get(self):
        return self._var.get()
        
    def set(self,value):
        if self.validator(value):
            self._var.set(self.value_type(value))
    

class DictController(tk.Frame):
    def __init__(self, parent, dict_):
        tk.Frame.__init__(self, parent)
        self._dict = {}
        self.update(dict_)

    def update(self,new_dict):
        for controller in self._dict.values():
            controller.pack_forget()
        self._dict = new_dict
        
        for key,val in self._dict.items():
            controller = ParameterController(self,key,val)
            controller.pack(side=tk.BOTTOM)
            self._dict[key] = controller
            
    def __getitem__(self,key):
        return self._dict[key].get()

    def __setitem__(self,key,value):
        self._dict[key].set(value)

    def as_dict(self):
        output = {}
        for key,val in self._dict.items():
            try:
                output[key] = val.get()
            except ValueError:
                raise ValueError("Invalid value for key '%s'"%key)
        return output


if __name__ == "__main__":
    test_dict = {
        "Test1":"node name",
        "Test2":90,
        "Test3":123.
        }
        
    root = tk.Tk()
    c = DictController(root,test_dict)
    c.pack()

    def print_vals():
        for key in test_dict:
            try:
                print c.as_dict()
            except ValueError as error:
                warnings.warn(repr(error))
        root.after(1000,print_vals)
        
    root.after(4000,print_vals)
        
    root.mainloop()
        
    
