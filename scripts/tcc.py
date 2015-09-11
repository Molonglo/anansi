from time import sleep
from anansi import args
from anansi.config import config
from anansi.tcc.interface_server import TCCServer
from anansi.tcc.status_server import StatusServer
from anansi.tcc.telescope_controller import TelescopeController

def main():
    tcc_ip = config.get("IPAddresses","tcc_ip")
    tcc_port = config.getint("IPAddresses","tcc_port")
    status_ip = config.get("IPAddresses","status_ip")
    status_port = config.getint("IPAddresses","status_port")
    controller = TelescopeController()
    interface_server = TCCServer(tcc_ip,tcc_port,controller)
    status_server = StatusServer(status_ip,status_port,controller)
    interface_server.start()
    status_server.start()
    while not interface_server.shutdown_requested.is_set():
        sleep(1.0)
    
if __name__ == "__main__":
    args.init()
    main()
