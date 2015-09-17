import signal
import sys
import weakref
import logging
from anansi import log

def callback(signum,frame):
    logger = logging.getLogger('anansi')
    msg = "Caught signal %d, running all callbacks"%signum
    logger.debug(msg,extra=log.tcc_status())
    
    while _CALLBACKS:
        try:
            func,args,kwargs = _CALLBACKS.pop()
            func(*args,**kwargs)
        except Exception as error:
            logger.error("Error while running callbacks",
                         extra=log.tcc_status(),exc_info=True)
    sys.exit(0)

def register(func,*args,**kwargs):
    _CALLBACKS.append((func,args,kwargs))

def deregister(func,*args,**kwargs):
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

