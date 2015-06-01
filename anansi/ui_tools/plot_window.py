import Tkinter as tk
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg

class PlotWindow(tk.Frame):
    def __init__(self,parent):
        tk.Frame.__init__(self,parent)
        self.parent = parent
        self.fig = mpl.figure.Figure()
        self.axes = self.setup_axes()
        self.canvas = FigureCanvasTkAgg(self.fig,self.parent)
        self.toolbar = NavigationToolbar2TkAgg(self.canvas,self.parent)
        self.toolbar.update()
        self.toolbar.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        self.plot_widget = self.canvas.get_tk_widget()
        self.plot_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        self.canvas.show()

    def setup_axes(self):
        ax = self.fig.add_subplot(111)
        return [ax]

    def draw(self):
        self.canvas.draw()

if __name__ == "__main__":
    root = tk.Tk()
    viewer = PlotWindow(root)
    viewer.pack()
    ax = viewer.axes[0]
    ax.plot(range(10))
    viewer.draw()
    root.mainloop()
