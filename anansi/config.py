import socket
from os import environ,getcwd
from os.path import join,isfile
from ConfigParser import ConfigParser

#Default parameters
DEFAULT_CONFIG = "anansi.cfg"
DEFAULT_PATH = environ["ANANSI_CONFIG"]

#eZ80 codes
EZ80_CODES_CONFIG = "eZ80_codes.cfg"

def guess_type(data):
    types = [int,float,complex,str]
    for typename in types:
        try:
            val = typename(data)
            if typename == str:
                if data.lower() == "true":
                    return True
                elif data.lower()== "false":
                    return False
            return val
        except:
            pass

class AnansiConfig(object):
    def update(self,config):
        for section in config.sections():
            self.add_section(section)
            self.__getattribute__(section).update(section,config)
    
    def add_section(self,name):
        if not hasattr(self,name):
            self.__setattr__(name,ConfigSection())
        
    def __repr__(self):
        msg = []
        for key,val in self.__dict__.items():
            msg.append("[%s]"%key)
            msg.append(repr(val)+"\n")
        return "\n".join(msg)


class ConfigSection(object):
    def update(self,name,config):
        for key,val in config.items(name):
            self.__setattr__(key,guess_type(val))

    def __repr__(self):
        msg = []
        for key,val in self.__dict__.items():
            msg.append("%s: %s"%(key,val))
        return "\n".join(msg)


class EZ80Codes(object):
    def __init__(self,config):
        self._code_to_name_map = {}
        self._name_to_code_map = {}
        for code in config.sections():
            for name,num in config.items(code):
                self._code_to_name_map[(code,int(num))] = name
                self._name_to_code_map[name] = (code,int(num))

    def get_string(self,code,num):
        return self._code_to_name_map[(code,num)]

    def get_code(self,name):
        return self._name_to_code_map[name.lower()]
    

config = AnansiConfig()
    
def _find_file(fname):
    if isfile(fname):
        return fname
    elif isfile(join(DEFAULT_PATH,fname)):
        return join(DEFAULT_PATH,fname)
    else:
        msg = ("Could not locate %s."
               "\nThe following locations were checked:\n%s"%(
                fname,
                "\n".join([join(getcwd(),fname),join(DEFAULT_PATH,fname)])))
        raise IOError(msg)
    

def build_config(config_file=None):
    _config = ConfigParser()
    _config.read(_find_file(DEFAULT_CONFIG))
    if config_file is not None:
        _config.read(_find_file(config_file))
    config.update(_config)
    _config = ConfigParser()
    _config.read(_find_file(EZ80_CODES_CONFIG))
    config.eZ80_codes = EZ80Codes(_config)
    
def update_config_from_args(args):
    _config = ConfigParser()
    if args.config is not None:
        _config.read(_find_file(args.config))
    if not 'cli' in _config.sections():
        _config.add_section('cli')
    for key,val in args.__dict__.items():
        _config.set('cli',key,str(val))
    config.update(_config)

build_config()

if __name__ == "__main__":
    from anansi import args
    update_config_from_args(args.parse_anansi_args())
