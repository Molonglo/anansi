import os
from lxml import etree
from anansi.comms import TCPClient
from time import sleep
from ConfigParser import ConfigParser
from anansi.anansi_logging import DataBaseLogger as LogDB
from anansi import exit_funcs

if __name__ == "__main__":
    from anansi import args
    from anansi.config import config,update_config_from_args
    update_config_from_args(args.parse_anansi_args())
    status = config.status_server

    def is_on_target(xml):
        return bool(xml.find("overview").find("on_target").text)
    client = TCPClient(status.ip,status.port,status.timeout)
    xml = client.receive()
    try:
        xml = etree.fromstring(xml)
        print etree.tostring(xml,pretty_print=True)
    except:
        print xml

