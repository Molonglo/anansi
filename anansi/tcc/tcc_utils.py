from lxml import etree
from anansi.xml import XMLMessage,gen_element,XMLError

class TCCError(Exception):
    def __init__(self,msg):
        super(TCCError,self).__init__(msg)

class TCCMessage(XMLMessage):
    def __init__(self,user,comment=""):
        super(TCCMessage,self).__init__(gen_element('tcc_request'))
        self.user_info(user,comment)

    def server_command(self,command):
        elem = gen_element("server_command")
        elem.append(gen_element("command",text=command))
        self.root.append(elem)

    def user_info(self,username,comment):
        elem = gen_element("user_info")
        elem.append(gen_element("name",text=username))
        elem.append(gen_element("comment",text=comment))
        self.root.append(elem)

    def tcc_command(self,command):
        elem = gen_element("tcc_command")
        elem.append(gen_element("command",text=command))
        self.root.append(elem)

    def tcc_pointing(self,x,y,
                     ns_east_state="auto",ns_west_state="auto",
                     md_east_state="auto",md_west_state="auto",
                     ns_east_offset=0.0,ns_west_offset=0.0,
                     md_east_offset=0.0,md_west_offset=0.0,
                     offset_units="degrees",**attributes):
        
        elem = gen_element("tcc_command")
        elem.append(gen_element("command",text="point"))
        pointing = gen_element("pointing",attributes=attributes)
        pointing.append(gen_element("xcoord",text=str(x)))
        pointing.append(gen_element("ycoord",text=str(y)))
        
        ns = gen_element("ns")
        ns_east = gen_element("east")
        ns_east.append(gen_element("state",text=ns_east_state))
        ns_east.append(gen_element("offset",text=str(ns_east_offset),attributes={'units':offset_units}))
        ns_west = gen_element("west")
        ns_west.append(gen_element("state",text=ns_west_state))
        ns_west.append(gen_element("offset",text=str(ns_west_offset),attributes={'units':offset_units}))
        ns.append(ns_east)
        ns.append(ns_west)
        md = gen_element("md")
        md_east = gen_element("east")
        md_east.append(gen_element("state",text=md_east_state))
        md_east.append(gen_element("offset",text=str(md_east_offset),attributes={'units':offset_units}))
        md_west = gen_element("west")
        md_west.append(gen_element("state",text=md_west_state))
        md_west.append(gen_element("offset",text=str(md_west_offset),attributes={'units':offset_units}))
        md.append(md_east)
        md.append(md_west)
        elem.append(pointing)
        elem.append(ns)
        elem.append(md)
        self.root.append(elem)


class TCCResponseHandler(XMLMessage):
    def __init__(self,msg):
        try:
            super(MPSRDefaultResponse,self).__init__(etree.fromstring(msg))
        except:
            logger.error("Unknown TCC message: %s"%msg)
            raise XMLError(msg)
        self._parse()
    
    def _parse(self):
        if self.root.find('success') is not None:
            self.passed = True
            self.message = self.root.find('success').text
        elif self.root.find('error') is not None:
            self.passed = False
            self.message = self.root.find('error').text
            raise TCCError(self.message)


class TCCControls(object):
    def __init__(self,user="anansi"):
        conf = config.tcc_server
        self.ip = conf.ip 
        self.port = conf.port 
        self.user = user

    def _send(self,msg):
        client = TCPClient(self.ip,self.port,timeout=10.0)
        client.send(msg)
        return TCCResponseHandler(client.receive())

    def track(self,x,y,system,units,**kwargs):
        msg = TCCMessage(self.user)
        msg.tcc_pointing(x,y,system=system,units=units,**kwargs)
        return self._send(str(msg))
    
    def stop(self):
        msg = TCCMessage(self.user)
        msg.tcc_command("stop")
        return self._send(str(msg))
    
    def maintenance_stow(self):
        msg = TCCMessage(self.user)
        msg.tcc_command("maintenance_stow")
        return self._send(str(msg))

    def wind_stow(self):
        msg = TCCMessage(self.user)
        msg.tcc_command("wind")
        return self._send(str(msg))

