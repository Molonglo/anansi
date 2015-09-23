import logging
import logging.handlers
import atexit
from struct import unpack
from Queue import Queue
from threading import Thread,Event
from logutils.queue import QueueHandler, QueueListener

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"
COLORS = {
    'WARNING': YELLOW,
    'INFO': WHITE,
    'DEBUG': BLUE,
    'CRITICAL': YELLOW,
    'ERROR': RED
}

class ColoredFormatter(logging.Formatter):
    def __init__(self, msg):
        logging.Formatter.__init__(self, msg)

    def format(self, record):
        levelname = record.levelname
        if levelname in COLORS:
            record.levelname = COLOR_SEQ % (30 + COLORS[levelname]) + levelname + RESET_SEQ
        return logging.Formatter.format(self, record)


class CustomQueueListener(QueueListener):
    def __init__(self, queue, *handlers):
        super(CustomQueueListener, self).__init__(queue, *handlers)
        """
        Initialise an instance with the specified queue and
        handlers.
        """
        # Changing this to a list from tuple in the parent class
        self.handlers = list(handlers)

    def handle(self, record):
        """
        Override handle a record.

        This just loops through the handlers offering them the record
        to handle.

        :param record: The record to handle.
        """
        record = self.prepare(record)
        for handler in self.handlers:
            if record.levelno >= handler.level: # This check is not in the parent class
                handler.handle(record)

    def addHandler(self, hdlr):
        """
        Add the specified handler to this logger.
        """
        if not (hdlr in self.handlers):
            self.handlers.append(hdlr)

    def removeHandler(self, hdlr):
        """
        Remove the specified handler from this logger.
        """
        if hdlr in self.handlers:
            hdlr.close()
            self.handlers.remove(hdlr)


class DBDispatchHandler(logging.Handler):
    def __init__(self,database,level=logging.NOTSET):
        self.db = database
        logging.Handler.__init__(self,level=level)
    
    def emit(self,record):
        record.msg = record.msg.replace("'","").replace("\n","")
        if hasattr(record,"to_database"):
            info = record.to_database
            target = info["target_table"]
            if target == "Commands_TCC":
                columns = "(utc,command_type,user,xml)"
                values = "(UTC_TIMESTAMP(),'{command_type}','{user}','{xml}')".format(**info)
            elif target == "Status_TCC":
                columns = "(utc,level,location,thread_name,message,traceback)"
                values = ("(UTC_TIMESTAMP(),'{levelname}','{module}:{funcName}',"
                          "'{threadName}','{msg}','{exc_info}')".format(**record.__dict__))
            elif target == "Commands_eZ80":
                columns = "(utc,code,message,drive)"
                values = "(UTC_TIMESTAMP(),'{code}','{message}','{drive}')".format(**info)
            elif target == "Status_eZ80":
                columns = "(utc,response_type,code_num,drive)"
                values = "(UTC_TIMESTAMP(),'{response_type}',{code_num},'{drive}')".format(**info)
            elif target == "Position_eZ80":
                columns = "(utc,drive,west_count,east_count,west_tilt,east_tilt,west_status,east_status)"
                values = ("(UTC_TIMESTAMP(),'{drive}',{west_count},{east_count},{west_tilt},"
                          "{east_tilt},{west_status},{east_status})".format(**info))
            else:
                return
            query = "INSERT INTO {0} {1} VALUES {2}".format(target,columns,values)
            try:
                self.db.execute_insert(query)
            except Exception as error:
                logger.error("Could not execute query: %s"%query,exc_info=True)

def tcc_command(cmd_type,xml,user):
    return {'to_database':{
            'target_table':"Commands_TCC",
            'command_type':cmd_type,
            'xml':xml.replace("'",""),
            'user':user}
            }

def eZ80_position(drive,drive_status):
    output = {'to_database':{
            'target_table':"Position_eZ80",
            'drive':drive }
              }
    output['to_database'].update(drive_status)
    return output
    
    
def eZ80_status(drive,response_type,code_num):
    return {'to_database':{
            'target_table':"Status_eZ80",
            'drive':drive,
            'response_type':response_type,
            'code_num':code_num}
            }

def eZ80_command(code,data,drive):
    if data is None:
        data = 'None'
    else:
        data = str(unpack("B"*len(data),data))

    return {'to_database':{
            'target_table':"Commands_eZ80",
            'drive':drive,
            'code':code,
            'message':data}
            }

def tcc_status():
    return {'to_database':{
            'target_table':"Status_TCC"}
            }

logging.basicConfig(level=1)
queue = Queue(64001)
queue_listner = CustomQueueListener(queue)
queue_handler = QueueHandler(queue)
logger = logging.getLogger('anansi')
logger.propagate = False
logger.addHandler(queue_handler)
logger.setLevel(logging.NOTSET)
queue_listner.start()
atexit.register(queue_listner.stop)

def _init_stream_logging(level=logging.NOTSET):
    handler = logging.StreamHandler()
    formatter = ColoredFormatter(
        '%(asctime)s: %(name)s: %(levelname)s: %(module)s: %(funcName)s: %(threadName)s: %(message)s')
    handler.setFormatter(formatter)
    handler.setLevel(level)
    queue_listner.addHandler(handler)

def _init_database_logging(database,level=logging.NOTSET):
    handler = DBDispatchHandler(database)
    formatter = logging.Formatter(
        '%(asctime)s: %(name)s: %(levelname)s: %(module)s: %(funcName)s: %(threadName)s: %(message)s')
    handler.setFormatter(formatter)
    handler.setLevel(level)
    queue_listner.addHandler(handler)

def init_logging(stream_level=None, database_level=None):
    [queue_listner.removeHandler(handler) for handler in queue_listner.handlers]
    if database_level is None:
        database_level = config.logging.database_level
    if stream_level is None:
        stream_level = config.logging.stream_level
    logger = logging.getLogger('anansi')
    _init_stream_logging(stream_level)
    try:
        database = AnansiDataBase()
    except Exception as error:
        logger.error("Could not open connection to AnansiDataBase",exc_info=True)
    else:
        _init_database_logging(database,database_level)

def test():
    init_logging()
    logger = logging.getLogger('anansi')
    logger.error("This is an error",extra=eZ80_command("E","this is an error message","Fictional drive"))
    logger.warn("This is a warn",extra=eZ80_command("W","this is a warning message","XY drive"))
    logger.info("This is information",extra=eZ80_command("I","this is information","Alpha Omega drive"))
    logger.error("Hi database!",extra=tcc_status())
    logger.info("Hi database!",extra=tcc_status())

from anansi.database import AnansiDataBase
from anansi.config import config
