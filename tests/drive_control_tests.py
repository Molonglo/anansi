import logging
logging.basicConfig(level=20)
from anansi.tcc import drive_control_thread as dct

def log_func_name(func):
    def wrapped(*args,**kwargs):
        logging.info(func.__name__)
        return func(*args,**kwargs)
    return wrapped

def _test_slew(tilt,speed):
    drive = dct.NSDriveInterface()
    drive.set_east_tilt(0.5,speed)
    drive.join()
    if not drive.error_queue.empty():
        logging.error(repr(drive.error_queue.get()))

@log_func_name
def test_north_long_slew():
    _test_slew(0.5,"fast")

@log_func_name
def test_south_long_slew():
    _test_slew(-0.5,"fast")
        
@log_func_name
def test_north_short_slew():
    _test_slew(0.01,"slow")
    
@log_func_name
def test_south_short_slew():
    _test_slew(-0.01,"slow")
    
@log_func_name
def test_north_short_fast():
    _test_slew(0.01,"fast")
        
@log_func_name
def test_south_short_fast():
    _test_slew(-0.01,"fast")
    
@log_func_name
def test_north_limit():
    _test_slew(1.5,"fast")

@log_func_name
def test_south_limit():
    _test_slew(-1.5,"fast")
    
if __name__ == "__main__":
    functions = [i for i in dir() if i.split("_")[0] == "test"]
    for func in functions:
        exec("%s()"%func)
