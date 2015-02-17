from datetime import datetime
from threading import _Timer,Thread,Event
import ctypes as C
from struct import unpack,pack
 
def gen_header_decoder(control_node):
    header_decoder = [
        ("Control node"  ,lambda x:x,len(control_node)),
        ("HOB"           ,lambda x:unpack("B",x)[0],1),
        ("LOB"           ,lambda x:unpack("B",x)[0],1),
        ("Command option",lambda x:unpack("c",x)[0],1)
        ]
    header_size= sum(ii[2] for ii in header_decoder)
    return header_decoder,header_size

def simple_decoder(msg,babel_fish):
    decoded = {}
    ii = 0
    for key, func, nbytes in babel_fish:
        decoded[key] = func(msg[ii:ii+nbytes])
        ii+=nbytes
    return decoded

def simple_encoder(node,command,data=None):
    if data is None:
        data = ""
    header = node
    header += pack("B",len(data)/256)
    header += pack("B",len(data)%256)
    header += command
    return header,data

def ft_unpack(data):
    """IEEE754 float data unpacker

    :param data: a byte string of length 4
    :return: floating point representation of data
    """
    bits = 32
    expbits = 8
    shift = C.c_longlong()
    result = C.c_longdouble()
    data = unpack("BBBB",data)
    buf = (C.c_ubyte*4)(*data)
    i = buf[0]<<24 | buf[1]<<16 | buf[2]<<8 | buf[3]<<0
    significandbits = bits - expbits - 1
    if (i==0):
        return 0.0;
    result.value = (i&((1<<significandbits)-1)) 
    result.value /= (1<<significandbits) 
    result.value += 1.0 
    bias = (1<<(expbits-1)) - 1
    shift.value = ((i>>significandbits)&((1<<expbits)-1)) - bias;
    while(shift.value > 0):
        result.value *= 2.0
        shift.value-=1
    while(shift.value < 0):
        result.value /= 2.0
        shift.value+=1
    result.value *= -1.0 if (i>>(bits-1))&1 else 1.0
    return result.value

def ft_pack(value):
    """IEEE754 float data packer

    :param value: a floating point number
    :return: an 4 bytes string 
    """
    bits = 32
    expbits = 8
    significandbits = C.c_uint(bits - expbits - 1)
    value = C.c_longdouble(value)
    shift = C.c_int()
    output = (C.c_ubyte*4)(0,0,0,0)

    if (value.value == 0.0):
        return output

    if (value.value < 0):
        sign = 1
        fnorm = -value.value
    else:
        sign = 0
        fnorm = value.value

    shift.value = 0
    while (fnorm >= 2.0):
        fnorm/=2.0
        shift.value+=1
    while (fnorm < 1.0):
        fnorm *= 2.0
        shift.value -= 1
    fnorm = fnorm - 1.0
    
    significand = C.c_longlong(long(fnorm * ((1<<significandbits.value) + 0.5)))
    exp = shift.value + ((1<<(expbits-1)) - 1)
    result = C.c_ulonglong((sign<<(bits-1)) | (exp<<(bits-expbits-1)) | significand.value)
    output[0] = result.value >> 24
    output[1] = result.value >> 16
    output[2] = result.value >> 8
    output[3] = result.value >> 0
    return output
    
def it_pack(val):
    to_pack = []
    to_pack.append(val&255)
    to_pack.append((val>>8)&255)
    to_pack.append((val>>16)&255)
    return pack("BBB",*to_pack)

def it_unpack(val):
    x = unpack("BBB",val)
    val = x[0] + x[1]*256 + x[2]*256**2
    return val
    
