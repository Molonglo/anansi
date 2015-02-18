from threading import Thread
import utils
from comms import TCPClient
from struct import pack,unpack
import ctypes as C

from ConfigParser import ConfigParser
config_path = os.environ["ANANSI_CONFIG"]
config = ConfigParser()
config.read(os.path.join(config_path,"anansi.cfg"))




class DriveInterface(Thread):
    def __init__(self,timeout,kevent=None):
        self.timeout = timeout
        self.event = kevent
        self.data_decoder = [
            ("east_status" ,lambda x: unpack("B",x)[0],1),
            ("east_tilt"   ,lambda x: self._decode_tilt(x,self._east_scaling),3),
            ("west_status" ,lambda x: unpack("B",x)[0],1),
            ("west_tilt"   ,lambda x: self._decode_tilt(x,self._west_scaling),3)]
        Thread.__init__(self)
        
    def open_client(self):
        if self.client is None:
            self.client = TCPClient(self._ip,self._port,timeout=self.timeout)
            
    def close_client(self):
        if self.client is not None:
            self.client.close()
            self.client = None
            
    def drive(self,data):
        self.open_client()
        self.send_message("1",data)
        while True:
            code,_ = self.parse_message(self.receive_message())
            if code == "S":
                self.run = self.drive_thread
                self.start()
                break

    def drive_thread(self):
        west_reached = False
        east_reached = False
        while not self.event.is_set():
            code,response = self.parse_message(self.receive_message())
            if not west_reached:
                west_reached = (code == "I") and (response == 13)
            if not east_reached:
                east_reached = (code == "I") and (response == 14)
            if west_reached and east_reached:
                break
        self.close_client()
        
    def parse_message(self,header,data):
        code = header["Command option"]
        if code in ["E","I","W","V"]:
            decoded_response = unpack("B",data)[0]
        elif code == "U":
            decoded_response = utils.simple_decoder(data,self.data_decoder)
            # log position
            # status broadcast
        else:
            decoded_response = None

        if code == "E":
            break #raise and log error
        else:
            pass #log response
        return code,decoded_response

    def get_status(self):
        self.open_client()
        self.send_message("U",None)
        code = None
        while code != "U":
            code,decoded_response = self.parse_message(self.receive_message())
        while code != "S":
            code,_ = self.parse_message(self.receive_message())
        self.close_client()
        return decoded_response
    
    def stop(self):
        self.open_client()
        self.send_message("0",None)
        code = None
        while code != "S":
            code,_ = self.parse_message(self.receive_message())
        self.close_client()
                
    def receive_message(self):
        response = self.client.receive(self.header_size)
        header = utils.simple_decoder(response,self.header_decoder)
        data_size = header["HOB"]*256+header["LOB"]
        if data_size > 0:
            data = self.client.receive(data_size)
        else:
            data = None
        return header,data
    
    def send_message(self,code,data=None):
        header,msg = utils.simple_encoder(self._node,code,data)
        client.send(header)
        if len(msg)>0: 
            client.send(msg)
    
        
    
