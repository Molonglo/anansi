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
from anansi import exit_funcs
from struct import unpack
MAX_PACKET_SIZE = 64000 #bytes

class SocketError(Exception):
    def __init__(self,obj,msg):
        new_msg = "%s at %s:%d"%(msg,obj.ip,obj.port)
        super(SocketError,self).__init__(msg)

class BaseConnection(object):
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
                pass
                #logging.warning(error)
            try:
                self.sock.close()
            except Exception as error:
                pass
                #logging.warning(error)
            self.sock = None


class BaseHandler(SocketServer.BaseRequestHandler):
    def __init__(self, request, client_address, server):
        self.server = server
        self.server.client_address = client_address
        SocketServer.BaseRequestHandler.__init__(self,request,
                                                 client_address, server)

    def recvall(self):
        message = []
        self.request.setblocking(0)
        while True:
            try:
                message.append(self.request.recv(8192))
            except:
                if not message:
                    continue
                else:
                    break
        return "".join(message)
            

class TCPServer(SocketServer.TCPServer):
    def __init__(self, ip, port, handler_class=BaseHandler):
        SocketServer.TCPServer.__init__(self, (ip, port), handler_class,
                                        bind_and_activate=False)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_bind()
        self.server_activate()
        self.client_address = None
        self.ip = ip
        self.port = port
        self.accept_thread = None
        self.shutdown_requested = Event()

    def start(self):
        self.accept_thread = Thread(target=self.serve_forever)
        self.accept_thread.daemon = True
        self.accept_thread.start()
        exit_funcs.register(self.shutdown)
        
    def shutdown(self):
        SocketServer.TCPServer.shutdown(self)
        self.accept_thread.join()
        exit_funcs.deregister(self.shutdown)


class TCPClient(BaseConnection):
    def __init__(self,ip,port,timeout=2):
        super(TCPClient,self).__init__(ip,port,socket.AF_INET,socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.connect()

    def send(self,msg):
        self.sock.send(msg)

    def receive(self,n=MAX_PACKET_SIZE):
        return self.sock.recv(n)


class ReconnectingTCPClient(object):
    def __init__(self,ip,port):
        self.ip = ip
        self.port = port

    def send(self,msg,timeout=2):
        client = TCPClient(self.ip,self.port,timeout=timeout)
        client.send(msg)
        client.close()    

