import socket
from os import environ,getcwd
from os.path import join,isfile
from ConfigParser import ConfigParser
from logging.config import fileConfig

DEFAULT_CONFIG = "anansi.cfg"
DEFAULT_LOGGING_CONFIG = "anansi_logging.cfg"
DEFAULT_PATH = environ["ANANSI_CONFIG"]
config = ConfigParser()

def build_config(anansi_config=None,logging_config=None):
    default_config = join(DEFAULT_PATH,DEFAULT_CONFIG)

    if not isfile(default_config):
        msg = ("Could not locate default configuration file.\n"
               "The following locations where checked:\n%s"%(default_config))
        raise IOError(msg)
    else:
        config.read(default_config)
    
    if anansi_config is not None:
        cfile = anansi_config
        if isfile(cfile):
            config.read(cfile)
        elif isfile(join(DEFAULT_PATH,cfile)):
            config.read(join(DEFAULT_PATH,cfile))
        else:
            msg = ("Could not locate user configuration file.\n"
                   "The following locations were checked:\n%s"%(
                    "\n".join([join(getcwd(),cfile),join(DEFAULT_PATH,cfile)])))
            raise IOError(msg)
    
    if logging_config is not None:
        if isfile(logging_config):
            fileConfig(logging_config)
        elif isfile(join(DEFAULT_PATH,logging_config)):
            fileConfig(join(DEFAULT_PATH,logging_config))
        else:
            msg = ("Could not locate default configuration file.\n"
                   "The following locations where checked:\n%s"%(
                    "\n".join([join(getcwd(),logging_config),
                               join(DEFAULT_PATH,logging_config)])))
        raise IOError(msg)
    else:
        fileConfig(join(DEFAULT_PATH,DEFAULT_LOGGING_CONFIG))

build_config()


