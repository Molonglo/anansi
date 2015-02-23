from anansi.tcc import drive_control_thread as dct
import unittest

class TestNSController(unittest.TestCase):
    
    def setUp(self):
        self.drive = dct.NSDriveInterface()
    
    def _test_slew(self,tilt,speed):
        self.drive.set_east_tilt(0.5,speed)
        self.drive.join()
        if not self.error_queue.empty():
            raise self.error_queue.get()

    def test_north_long_slew(self):
        self._test_slew(0.5,"fast")

    def test_south_long_slew(self):
        self._test_slew(-0.5,"fast")
        
    def test_north_short_slew(self):
        self._test_slew(0.01,"slow")

    def test_south_short_slew(self):
        self._test_slew(-0.01,"slow")
    
    def test_north_short_fast(self):
        self._test_slew(0.01,"fast")

    def test_south_short_fast(self):
        self._test_slew(-0.01,"fast")
    
    def test_north_limit(self):
        self._test_slew(1.5,"fast")

    def test_south_limit(self):
        self._test_slew(-1.5,"fast")

    
unittest.main()
    
    
        
