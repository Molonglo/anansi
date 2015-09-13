from time import sleep
from anansi import args
from anansi.config import config
from anansi.tcc.interface_server import TCCServer
from anansi.tcc.status_server import StatusServer
from anansi.tcc.telescope_controller import TelescopeController

def main():
    controller = TelescopeController()
    tcc = config.tcc_server
    status = config.status_server
    interface_server = TCCServer(tcc.ip,tcc.port,controller)
    status_server = StatusServer(status.ip,status.port,controller)
    interface_server.start()
    status_server.start()
    while not interface_server.shutdown_requested.is_set():
        sleep(1.0)
    
if __name__ == "__main__":
    config.build_config(args.parse_anansi_args())
    main()
