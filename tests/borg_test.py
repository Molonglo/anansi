from threading import Thread,Event
from anansi.tcc.drives.ns_drive import NSDriveInterface
import time

event = Event()

def test_thread():
    x = NSDriveInterface()
    x.x = 5
    while not event.is_set():
        time.sleep(1)
        x.x += 1

def run_test():
    a = Thread(target=test_thread)
    a.daemon = True
    a.start()
    x =  NSDriveInterface()
    for ii in range(10):
        time.sleep(1)
        print x.x
    event.set()
    
run_test()
