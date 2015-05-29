import signal
import sys
import weakref
from anansi.logging_db import MolongloLoggingDataBase as LogDB
# This file contains a dictionary of callbacks 
# for interrupt and terminate signals

log = LogDB()

def callback(signum,frame):
    log.log_tcc_status("exit_funcs.callback","debug",
                       "Caught signal %d, running callbacks"%signum)
    while _CALLBACKS:
        try:
            func,args,kwargs = _CALLBACKS.pop()
            func(*args,**kwargs)
        except Exception as error:
            log.log_tcc_status("exit_funcs.callback","error",
                               str(error))
    sys.exit(0)

def register(func,*args,**kwargs):
    log.log_tcc_status("exit_funcs.register","debug",
                       "Registering %s"%(str((func,args,kwargs))))
    _CALLBACKS.append((func,args,kwargs))

def deregister(func,*args,**kwargs):
    log.log_tcc_status("exit_funcs.deregister","debug",
                       "Deregistering %s"%(str((func,args,kwargs))))
    try:
        _CALLBACKS.remove((func,args,kwargs))
    except ValueError:
        pass
    
_CALLBACKS = []
signal.signal(signal.SIGINT,callback)
signal.signal(signal.SIGTERM,callback)

if __name__ == "__main__":
    from time import sleep
    
    def display(*args,**kwargs):
        print args,kwargs

    register(display,1,2,3,4,5,k=20,f=45)
    register(display,1,2,k=20,f=45)
    register(display,1,j=10,f=4500)
    print "Press Ctrl-C in next 10 seconds to test interrupt..."
    sleep(10)

