from lxml import etree
from anansi.xml import XMLMessage,gen_element

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

