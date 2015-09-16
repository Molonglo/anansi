import socket
from os import environ,getcwd
from os.path import join,isfile
from ConfigParser import ConfigParser
from anansi.log import init_logging

#Default parameters
DEFAULT_CONFIG = "anansi.cfg"
DEFAULT_PATH = environ["ANANSI_CONFIG"]

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
            if not hasattr(self,section):
                self.__setattr__(section,ConfigSection())
            self.__getattribute__(section).update(section,config)
    
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
    fileConfig(_find_file(DEFAULT_LOGGING_CONFIG))
    if config_file is not None:
        _config.read(_find_file(config_file))
    config.update(_config)
    init_logging()
    
def update_config_from_args(args):
    _config = ConfigParser()
    if args.config is not None:
        _config.read(_find_file(args.config))
    if not 'cli' in _config.sections():
        _config.add_section('cli')
    for key,val in args.__dict__.items():
        _config.set('cli',key,str(val))
    config.update(_config)
    init_logging()

build_config()

if __name__ == "__main__":
    from anansi import args
    update_config_from_args(args.parse_anansi_args())
