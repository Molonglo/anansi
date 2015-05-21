from threading import Thread
import logging
logging.basicConfig(format="%(levelname)s  %(thread)s  %(message)s",level=20)
from anansi.tcc.drives.ns_drive import NSDriveInterface
from time import sleep

def log_func_name(func):
    def wrapped(*args,**kwargs):
        logging.info(func.__name__)
        return func(*args,**kwargs)
    return wrapped

def _test_slew(tilt,force_slow):
    drive = NSDriveInterface()
    drive.set_east_tilt(tilt,force_slow)
    drive.join()
    if not drive.error_queue.empty():
        logging.error(repr(drive.error_queue.get()))

@log_func_name
def test_north_long_slew():
    _test_slew(0.5,False)

@log_func_name
def test_south_long_slew():
    _test_slew(-0.5,False)
        
@log_func_name
def test_north_short_slew():
    _test_slew(0.01,True)
    
@log_func_name
def test_south_short_slew():
    _test_slew(-0.01,True)
    
@log_func_name
def test_north_short_fast():
    _test_slew(0.01,False)
        
@log_func_name
def test_south_short_fast():
    _test_slew(-0.01,False)
    
@log_func_name
def test_north_limit():
    _test_slew(1.5,False)

@log_func_name
def test_south_limit():
    _test_slew(-1.5,False)
    
def _threaded_slew(tilt):
    _test_slew(tilt,False)

def thread_test():
    thread1 = Thread(target=_threaded_slew,args=(0.5,))
    thread1.start()
    sleep(10)
    thread2 = Thread(target=_threaded_slew,args=(0.5,))
    thread2.start()
    thread1.join()
    sleep(10)
    drive = NSDriveInterface()
    drive.stop()
    thread2.join()

try:   
    thread_test()
except:
    drive = NSDriveInterface()
    drive.stop()

    
    
    
