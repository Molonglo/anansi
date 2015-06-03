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

    def tcc_pointing(self,x,y,east_arm="enabled",west_arm="enabled",
                     east_speed="auto",west_speed="auto",**attributes):
        elem = self._gen_element("tcc_command")
        elem.append(self._gen_element("command",text="point"))
        pointing = self._gen_element("pointing",attributes=attributes)
        pointing.append(self._gen_element("xcoord",text=str(x)))
        pointing.append(self._gen_element("ycoord",text=str(y)))
        arms = self._gen_element("arms")
        arms.append(self._gen_element("east",text=east_arm,
                                      attributes={"speed":east_speed}))
        arms.append(self._gen_element("west",text=west_arm,
                                      attributes={"speed":west_speed}))
        elem.append(pointing)
        elem.append(arms)
        self.root.append(elem)
