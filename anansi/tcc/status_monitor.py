import os
from lxml import etree
from anansi.comms import TCPClient
from time import sleep
from ConfigParser import ConfigParser
from anansi.anansi_logging import DataBaseLogger as LogDB
from anansi import exit_funcs

if __name__ == "__main__":
    from anansi import args
    from anansi.config import config
    args.init()
    status_ip = config.get("IPAddresses","status_ip")
    status_port = config.getint("IPAddresses","status_port")

    def is_on_target(xml):
        return bool(xml.find("overview").find("on_target").text)

    client = TCPClient(status_ip,status_port,timeout=10.0)
    xml = client.receive()

    try:
        xml = etree.fromstring(xml)
        print etree.tostring(xml,pretty_print=True)
    except:
        print xml

