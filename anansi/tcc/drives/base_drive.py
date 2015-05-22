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

        #def __del__(self):
        #self._close_client()
        #self.client = None

            
    def _open_client(self):
        if self.client is None:
            try:
                self.client = TCPClient(self._ip,self._port,timeout=self.timeout)
            except Exception as e:
                self.log.log_tcc_status("BaseDriveInterface._open_client",
                                        "error", str(e))
                raise e

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
        self.client.send(header)
        if len(msg)>0:
            self.client.send(msg)
        
        if data:
            data_repr = unpack("B"*len(data),data)
            self.log.log_eZ80_command(code,str(data_repr))
        else:
            self.log.log_eZ80_command(code,"None")

