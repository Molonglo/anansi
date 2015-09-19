from lxml import etree

class TCCMessage(object):
    def __init__(self,user,comment=""):
        self.root = self._gen_element("tcc_request")
        self.user_info(user,comment)
        
    def __str__(self):
        return etree.tostring(self.root,encoding='ISO-8859-1')

    def __repr__(self):
        return etree.tostring(self.root,encoding='ISO-8859-1',pretty_print=True)

    def _gen_element(self,name,text=None,attributes=None):
        root = etree.Element(name)
        if attributes is not None:
            for key,val in attributes.items():
                root.attrib[key] = val
        if text is not None:
            root.text = text
        return root

    def server_command(self,command):
        elem = self._gen_element("server_command")
        elem.append(self._gen_element("command",text=command))
        self.root.append(elem)

    def user_info(self,username,comment):
        elem = self._gen_element("user_info")
        elem.append(self._gen_element("name",text=username))
        elem.append(self._gen_element("comment",text=comment))
        self.root.append(elem)

    def tcc_command(self,command):
        elem = self._gen_element("tcc_command")
        elem.append(self._gen_element("command",text=command))
        self.root.append(elem)

    def tcc_pointing(self,x,y,
                     ns_east_state="auto",ns_west_state="auto",
                     md_east_state="auto",md_west_state="auto",
                     ns_east_offset=0.0,ns_west_offset=0.0,
                     md_east_offset=0.0,md_west_offset=0.0,
                     offset_units="degrees",**attributes):
        
        elem = self._gen_element("tcc_command")
        elem.append(self._gen_element("command",text="point"))
        pointing = self._gen_element("pointing",attributes=attributes)
        pointing.append(self._gen_element("xcoord",text=str(x)))
        pointing.append(self._gen_element("ycoord",text=str(y)))
        
        ns = self._gen_element("ns")
        ns_east = self._gen_element("east")
        ns_east.append(self._gen_element("state",text=ns_east_state))
        ns_east.append(self._gen_element("offset",text=str(ns_east_offset),attributes={'units':offset_units}))
        ns_west = self._gen_element("west")
        ns_west.append(self._gen_element("state",text=ns_west_state))
        ns_west.append(self._gen_element("offset",text=str(ns_west_offset),attributes={'units':offset_units}))
        ns.append(ns_east)
        ns.append(ns_west)
        md = self._gen_element("md")
        md_east = self._gen_element("east")
        md_east.append(self._gen_element("state",text=md_east_state))
        md_east.append(self._gen_element("offset",text=str(md_east_offset),attributes={'units':offset_units}))
        md_west = self._gen_element("west")
        md_west.append(self._gen_element("state",text=md_west_state))
        md_west.append(self._gen_element("offset",text=str(md_west_offset),attributes={'units':offset_units}))
        md.append(md_east)
        md.append(md_west)
        elem.append(pointing)
        elem.append(ns)
        elem.append(md)
        self.root.append(elem)

