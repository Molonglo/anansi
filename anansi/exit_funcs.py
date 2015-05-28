import signal
import atexit
import sys
import weakref
# This file contains a dictionary of callbacks 
# for interrupt and terminate signals

def callback(*args,**kwargs):
    for func,args,kwargs in _CALLBACKS:
        func(*args,**kwargs)
    sys.exit(0)

def register(func,*args,**kwargs):
    _CALLBACKS.append((func,args,kwargs))

def deregister(func,*args,**kwargs):
    try:
        x.remove((func,args,kwargs))
    except ValueError:
        pass
    
_CALLBACKS = []
signal.signal(signal.SIGINT,callback)
signal.signal(signal.SIGTERM,callback)
atexit.register(callback)

if __name__ == "__main__":
    from time import sleep
    
    def display(*args,**kwargs):
        print args,kwargs

    register(display,1,2,3,4,5,k=20,f=45)
    register(display,1,2,k=20,f=45)
    register(display,1,j=10,f=4500)
    print "Press Ctrl-C in next 10 seconds to test interrupt..."
    sleep(10)

