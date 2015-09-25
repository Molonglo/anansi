from lxml.etree import Element,tostring

class XMLError(Exception):
    def __init__(self,xml_string):
        msg = "Failed to parse message: %s"%xml_string
        super(XMLError,self).__init__(msg)


class XMLMessage(object):
    def __init__(self,root):
        self.root = root

    def __str__(self):
        return tostring(self.root,encoding='ISO-8859-1')

    def __repr__(self):
        return tostring(self.root,encoding='ISO-8859-1',pretty_print=True)


def gen_element(name,text=None,attributes=None):
    root = Element(name)
    if attributes is not None:
        for key,val in attributes.items():
            root.attrib[key] = str(val)
    if text is not None:
        root.text = str(text)
    return root
