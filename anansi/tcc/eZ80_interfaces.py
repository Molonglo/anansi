import utils
from comms import TCPClient
from struct import pack,unpack
import ctypes as C
import ip_addresses as ips


class BaseHardwareInterface(object):
    """Abstract base class for control of MOST eZ80 controllers.

    Inheriting classes must define:
    _ip     - the IP address of the board to be accessed
    _port   - the port number of the board to be accessed
    _node   - the MOST communication protocol string (e.g. "TCC_TDC0")
    
    This class is designed only to work with the MOST style communication 
    protocol. Here all "set" commands for telescope parameters are send only
    operations and all "get" commands receive a command specific return message.
    Both "get" and "set" commands are defined by a single character command code
    which in the case of "set" commands may be followed by packed binary data.
    """
    def __init__(self,timeout):
        self.timeout = timeout
        decoder,size = utils.gen_header_decoder(self._node)
        self.header_decoder = decoder
        self.header_size = size

    def set(self,code,data=None,client=None):
        if client is None:
            client = TCPClient(self._ip,self._port,timeout=self.timeout)
        header,msg = utils.simple_encoder(self._node,code,data)
        client.send(header)
        if len(msg) > 0:
            client.send(msg)

    def get(self,code,response_decoder):
        client = TCPClient(self._ip,self._port,timeout=self.timeout)
        self.set(code,client=client)
        response = client.receive(self.header_size)
        header = utils.simple_decoder(response,self.header_decoder)
        data_size = header["HOB"]*256+header["LOB"]
        data = client.receive(data_size)
        decoded_response = utils.simple_decoder(data,response_decoder)
        return decoded_response


#-------------------Tilt Interface------------------------#

class BaseTiltInterface(BaseHardwareInterface):
    """Abstract base class for control of the MOST tilt drives. 
    
    Tilt values are controlled through sending of the desired number
    of encoder counts (rotations of the drive shaft for either MD or NS).
    To this end inheriting classes define:
    _east_scaling - encoder counts per radian of tilt for east arm
    _west_scaling - encoder counts per radian of tilt for west arm
    _tilt_zero        - encoder counts at zenith
    """
    def __init__(self,timeout):
        super(BaseTiltInterface,self).__init__(timeout)
            
    def _decode_tilt(self,x,scaling):
        counts = utils.it_unpack(x)
        tilt = (counts-self._tilt_zero)/scaling
        return tilt

    def set_tilt(self,east_tilt,west_tilt=None):
        if west_tilt is None:
            west_tilt = east_tilt
        east_counts = int(self._tilt_zero + self._east_scaling * east_tilt)
        west_counts = int(self._tilt_zero + self._west_scaling * west_tilt)
        data = utils.it_pack(east_counts) + utils.it_pack(west_counts)
        self.set("1",data)

    def get_state(self):
        response_decoder = [
            ("east_status" ,lambda x: unpack("B",x)[0],1),
            ("east_tilt"   ,lambda x: self._decode_tilt(x,self._east_scaling), 3),
            ("west_status" ,lambda x: unpack("B",x)[0],1),
            ("west_tilt"   ,lambda x: self._decode_tilt(x,self._west_scaling), 3)
            ]
        return self.get("U",response_decoder)

    def stop(self):
        self.set("0")


class NSInterface(BaseTiltInterface):
    _node         = "TCC_TDC0"
    _ip,_port     = ips.NS_CONTROLLER
    _west_scaling = 23623.0498932
    _east_scaling = 23623.0498932
    _tilt_zero    = 8388608.0
    def __init__(self,timeout=5.0):
        super(NSInterface,self).__init__(timeout)
    

class MDInterface(BaseTiltInterface):
    _node         = "TCC_MDC0"
    _ip,_port     = ips.MD_CONTROLLER
    _west_scaling = 136450.0
    _east_scaling = 136450.0
    _tilt_zero    = 8388608.0

    def __init__(self,timeout=5.0):
        super(MDInterface,self).__init__(timeout)
        
    def _decode_tilt(self,x,scaling):
        return np.arcsin(super(MDInterface,self)._decode_tilt(x,scaling))
    
    def set_tilt(self,east_tilt,west_tilt=None):
        if west_tilt is None:
            west_tilt = east_tilt
        super(MDInterface,self).set_tilt(np.sin(east_tilt),np.sin(west_tilt))


#-------------------Environment interface------------------------# 

class EnvInterface(BaseHardwareInterface):
    _node               = "TCC_ENV0"
    _ip,_port           = ips.ENV_CONTROLLER
    _lna_scaling        = 0.0024441
    _ambient_scaling    = 0.0025709
    _mixer_scaling      = 0.0025951
    _cable_scaling      = 0.0025951
    _temp_offset        = 2.7314
    _humidity_scaling   = 0.063080457
    _humidity_offset    = -17.2361
    _wind_speed_scaling = 0.1
    _wind_speed_offset  = 2.0
    _wind_dir_scaling   = 0.0022

    def __init__(self,timeout=5.0):
        super(EnvInterface,self).__init__(timeout)
        
    def _to_float(self,x,scale=2048.0):
        lo,hi = unpack("BB",x)
        return (hi*16.0 + lo) - scale
        
    def _temp_conv(self,x,scaling):
        val = self._to_float(x)
        return (val * scaling - self._temp_offset) * 100.0
    
    def _humidity_conv(self,x):
        val = self._to_float(x)
        return self._humidity_scaling * val + self._humidity_offset
    
    def _wind_speed_conv(self,x):
        val = self._to_float(x)
        return self._wind_speed_scaling * max(val,0.0) + self._wind_speed_offset
    
    def _wind_dir_conv(self,x):
        val = self._to_float(x,0.0)
        return self._wind_dir_scaling * val 
    
    def get_state(self):
        response_decoder = [
            ("lna_temp"     ,lambda x: self._temp_conv(x,self._lna_scaling),2),
            ("mixer_temp"   ,lambda x: self._temp_conv(x,self._mixer_scaling),2),
            ("cable_temp"   ,lambda x: self._temp_conv(x,self._cable_scaling),2),
            ("ambient_temp" ,lambda x: self._temp_conv(x,self._ambient_scaling),2),
            ("humidity"     ,lambda x: self._humidity_conv(x),2),
            ("wind_speed"   ,lambda x: self._wind_speed_conv(x),2),
            ("wind_dir"     ,lambda x: self._wind_dir_conv(x),2)
            ]
        return self.get("U",response_decoder)
    
    
