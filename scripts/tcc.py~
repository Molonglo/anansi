from time import sleep
from ConfigParser import ConfigParser
from anansi.tcc.interface_server import TCCServer
from anansi.tcc.status_server import StatusServer
from anansi.tcc.telescope_controller import TelescopeController

def main(config_file):
    config = ConfigParser()
    config.read(config_file)
    anansi_ip = config.get("IPAddresses","anansi_ip")
    anansi_port = config.getint("IPAddresses","anansi_port")
    status_ip = config.get("IPAddresses","status_ip")
    status_port = config.getint("IPAddresses","status_port")
    controller = TelescopeController()
    interface_server = TCCServer(anansi_ip,anansi_port,controller)
    status_server = StatusServer(status_ip,status_port)
    interface_server.start()
    status_server.start()
    while not interface_server.shutdown_requested.is_set():
        sleep(1.0)
    
if __name__ == "__main__":
    import os
    config_path = os.environ["ANANSI_CONFIG"]
    config_file = os.path.join(config_path,"anansi.cfg")
    main(config_file)
