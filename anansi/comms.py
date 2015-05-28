import socket
import SocketServer
import sys
from time import sleep
from multiprocessing import RawArray,RawValue
from threading import Thread,Event
from Queue import Queue
import ctypes as C
import logging
from anansi import decorators
MAX_PACKET_SIZE = 64000 #bytes

class SocketError(Exception):
    def __init__(self,obj,msg):
        super(SocketError,self).__init__(msg)
        logging.getLogger(self.__class__.__name__).error("%s (%s,%d)",msg,obj.ip,obj.port)

class BaseConnection(object):
    @decorators.log_args
    def __init__(self,ip,port,sock_family,sock_type):
        super(BaseConnection,self).__init__()
        self.ip = ip
        self.port = port
        self.sock = socket.socket(sock_family,sock_type)
        self.sock.settimeout(2)
        
    def connect(self):
        try:
            self.sock.connect((self.ip, self.port))
        except Exception as error:
            raise SocketError(self,error)

    def bind(self):
        if self.sock is not None:
            try:
                self.sock.bind((self.ip, self.port))
            except Exception as error:
                raise SocketError(self,error)
        
    def close(self):
        self.__del__()

    def __del__(self):
        if self.sock is not None:

            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception as error:
                logging.warning(error)
            try:
                self.sock.close()
            except Exception as error:
                logging.warning(error)
            self.sock = None

#####################
# TCP related
#####################

class BaseHandler(SocketServer.BaseRequestHandler):
    @decorators.log_args
    def __init__(self, request, client_address, server):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug('Handling request from %s'%(repr(client_address)))
        self.server = server
        server.client_address = client_address
        SocketServer.BaseRequestHandler.__init__(self,request, client_address, server)

    def handle(self):
        data = self.request.recv(4096)
        self.request.send(data)

class QueueHandler(BaseHandler):
    def __init__(self, request, client_address, server):
        BaseHandler.__init__(self,request, client_address, server)
        
    def handle(self):
        data = self.request.recv(4096)
        self.logger.debug('received %d byte data packet'%(len(data)))
        self.server.recv_q.put(data)
        response = None
        while not self.server.stop.is_set():
            try:
                response = self.server.send_q.get(timeout=1.0)
            except:
                pass
            else:
                break
        if response is not None:
            self.request.send(response)
            self.logger.debug('sending %d byte data packet'%(len(response)))


class TCPServer(SocketServer.TCPServer):
    @decorators.log_args
    def __init__(self, ip, port, handler_class=QueueHandler):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.recv_q = Queue()
        self.send_q = Queue()
        self.client_address = None
        self.ip = ip
        self.port = port
        self.stop = Event()
        SocketServer.TCPServer.__init__(self, (ip, port), handler_class,bind_and_activate=False)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_bind()
        self.server_activate()
        self.logger.debug('TCP server bound and listening on (%s,%d)'%(self.ip,self.port))

    def shutdown(self):
        self.stop.set()
        SocketServer.TCPServer.shutdown(self)

    def __del__(self):
        self.server_close()


class TCPClient(BaseConnection):
    def __init__(self,ip,port,timeout=2):
        super(TCPClient,self).__init__(ip,port,socket.AF_INET,socket.SOCK_STREAM)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.sock.settimeout(timeout)
        self.connect()
        self.logger.debug("Connected TCP client to (%s,%d)"%(self.ip,self.port))
        
    @decorators.log_args
    def send(self,msg):
        self.logger.debug("Sending %d bytes to (%s,%d)"%(len(msg),self.ip,self.port))
        self.sock.send(msg)
        
    @decorators.log_args
    def receive(self,n=MAX_PACKET_SIZE):
        msg = self.sock.recv(n)
        self.logger.debug("Received %d bytes from (%s,%d)"%(len(msg),self.ip,self.port))
        return msg

class ReconnectingTCPClient(object):
    def __init__(self,ip,port):
        self.ip = ip
        self.port = port

    def send(self,msg,timeout=2):
        client = TCPClient(self.ip,self.port,timeout=timeout)
        client.send(msg)
        client.close()    

            
#####################
# UDP related 
#####################

class _UDPReceiverThread(Thread):
    STOP = "s"
    PAUSE = "p"
    def __init__(self,parent,timeout=1):
        super(_UDPReceiverThread,self).__init__()
        self.parent = parent
        self.parent.sock.settimeout(1)
        self.stop = Event()

    def run(self):
        while not self.stop.is_set():
            sleep(1)
            try:
                data, addr = self.parent.sock.recvfrom(MAX_PACKET_SIZE)
            except socket.timeout:
                continue
            except Exception as error:
                raise SocketError(self,error)
            self.parent.msg = data
            #self.msg[:len(data)] = data[:]
          

class UDPReceiver(BaseConnection):
    def __init__(self,ip,port):
        super(UDPReceiver,self).__init__(ip,port,socket.AF_INET,socket.SOCK_DGRAM)
        self.bind()
        self.msg = "" #RawArray(C.c_char,MAX_PACKET_SIZE)
        self.state = RawValue(C.c_char,"c")
        self.listen()
        
    def listen(self):
        self.listner = _UDPReceiverThread(self)
        self.listner.start()

    def stop(self):
        self.listner.stop.set()
        self.listner.join()
                
    def read_packet(self,decoder):
        return decoder(self.listner.msg)

    def __del__(self):
        self.stop()

class UDPSender(BaseConnection):
    def __init__(self,ip,port,broadcast=True):
        super(UDPSender,self).__init__(ip,port,socket.AF_INET,socket.SOCK_DGRAM)
        if broadcast:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
    @decorators.log_args
    def send(self,msg):
        try:
            self.sock.sendto(msg,(self.ip,self.port))
        except Exception as error:
            logging.error(repr(error))
            


if __name__ == "__main__":
    pass
