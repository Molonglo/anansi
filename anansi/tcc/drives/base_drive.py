from anansi.logging_db import MolongloLoggingDataBase as LogDB
from anansi.comms import TCPClient
from struct import unpack
from anansi import codec

class BaseDriveInterface(object):
    _data_decoder = [
        ("east_status" ,lambda x: unpack("B",x)[0],1),
        ("east_count"   ,lambda x: codec.it_unpack(x),3),
        ("west_status" ,lambda x: unpack("B",x)[0],1),
        ("west_count"   ,lambda x: codec.it_unpack(x),3)]
    
    def __init__(self,timeout):
        self.timeout = timeout
        self.client = None
        decoder,size = codec.gen_header_decoder(self._node)
        self.header_decoder = decoder
        self.header_size = size
        self.log = LogDB()
            
    def __del__(self):
        del self.client
        
    def _open_client(self):
        if self.client is None:
            self.client = TCPClient(self._ip,self._port,timeout=self.timeout)
            
    def _close_client(self):
        if self.client is not None:
            self.client.close()
            self.client = None

    def _receive_message(self):
        response = self.client.receive(self.header_size)
        header = codec.simple_decoder(response,self.header_decoder)
        data_size = header["HOB"]*256+header["LOB"]
        if data_size > 0:
            data = self.client.receive(data_size)
        else:
            data = None
        return header,data

    def _send_message(self,code,data=None):
        header,msg = codec.simple_encoder(self._node,code,data)
        self.log.log_eZ80_status(code,data)
        self.client.send(header)
        if len(msg)>0:
            self.client.send(msg)


