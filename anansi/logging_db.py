import MySQLdb
import os
import warnings

from ConfigParser import ConfigParser
config_path = os.environ["ANANSI_CONFIG"]
config = ConfigParser()
config.read(os.path.join(config_path,"logging_db.cfg"))
USER   = config.get("Login","user")
PASSWD = config.get("Login","password")
HOST   = config.get("Login","host")
PORT   = config.getint("Login","port")
NAME   = config.get("Login","name")

class BaseDBManager(object):
    def __init__(self):
        self.cursor = None
        self.connection = None

    def __del__(self):
        if self.connection is not None:
            self.connection.close()

    def with_connection(func):
        """Decorator to make database connections."""
        def wrapped(self,*args,**kwargs):
            if self.connection is None:
                try:
                    self.connection = self.connect()
                    self.cursor = self.connection.cursor()
                except Exception as error:
                    self.cursor = None
                    warnings.warn(str(error),Warning)
            else:
                self.connection.ping(True)
            func(self,*args,**kwargs)
        return wrapped

    @with_connection
    def execute_query(self,query):
        """Execute a mysql query"""
        try:
            self.cursor.execute(query)
        except Exception as error:
            raise error

    @with_connection
    def execute_insert(self,insert):
        """Execute a mysql insert/update/delete"""
        try:
            self.cursor.execute(insert)
            self.connection.commit()
        except Exception as error:
            self.connection.rollback()
            raise error
    
    @with_connection
    def execute_many(self,insert,values):
        try:
            self.cursor.executemany(insert,values)
            self.connection.commit()
        except Exception as error:
            self.connection.rollback()
            raise error
        
    @with_connection
    def execute_delete(self,delete):
        self.execute_insert(delete)

    def lock(self,lockname,timeout=5):
        self.execute_query("SELECT GET_LOCK('%s',%d)"%(lockname,timeout))
        response = self.get_output()
        return bool(response[0][0])

    def release(self,lockname):
        self.execute_query("SELECT RELEASE_LOCK('%s')"%(lockname))

    def fix_duplicate_field_names(self,names):
        """Fix duplicate field names by appending 
        an integer to repeated names."""
        used = []
        new_names = []
        for name in names:
            if name not in used:
                new_names.append(name)
            else:
                new_name = "%s_%d"%(name,used.count(name))
                new_names.append(new_name)
            used.append(name)
        return new_names

    def get_output(self):
        """Get sql data in numpy recarray form."""
        if self.cursor.description is None:
            return None
        names = [i[0] for i in self.cursor.description]
        names = self.fix_duplicate_field_names(names)
        try:
            output  = self.cursor.fetchall()
        except Exception as error:
            warnings.warn(str(error),Warning)
            return None
        if not output or len(output) == 0:
            return None
        else:
            output = np.rec.fromrecords(output,names=names)
            return output


class MolongloLoggingDataBase(BaseDBManager):
    __HOST = HOST
    __NAME = NAME
    __USER = USER
    __PORT = PORT
    __PASSWD = PASSWD
    def __init__(self):
        super(MolongloLoggingDataBase,self).__init__()
        try:
            self.connect()
        except Exception as error:
            self.connected = False
            warnings.warn(str(error))
        else:
            self.connected = True
    
    def execute_insert(self,query):
        if self.connected:
            super(MolongloLoggingDataBase,self).execute_insert(query)
        else:
            print query

    def connect(self):
        return MySQLdb.connect(
            host=self.__HOST,
            port=self.__PORT,
            db=self.__NAME,
            user=self.__USER,
            passwd=self.__PASSWD)

    def log_command(self,cmd_type,xml_msg):
        query = ("INSERT INTO Commands (utc,command_type,xml) "
                 "VALUES (UTC_TIMESTAMP(),'%s','%s')")%(cmd_type,xml_msg)
        self.execute_insert(query)

    def log_position(self,drive,west_count,east_count):
        query = ("INSERT INTO Position_eZ80 " 
                 "(utc,drive,west_count,east_count) "
                 "VALUES (UTC_TIMESTAMP(),'%s',%d,%d)")%(drive,west_count,east_count)
        self.execute_insert(query)

    def log_eZ80_status(self,code_level,code_num):
        query = ("INSERT INTO Status_eZ80 "
                 "(utc,code_level,code_num) "
                 "VALUES (UTC_TIMESTAMP(),'%s',%d)")%(code_level,code_num)
        self.execute_insert(query)

    def log_eZ80_command(self,code,data):
        query = ("INSERT INTO Commands_eZ80 "
                 "(utc,code,message) "
                 "VALUES (UTC_TIMESTAMP(),'%s','%s')")%(code,str(data))
        self.execute_insert(query)
    
    def log_tcc_status(self,sender,level,msg):
        query = ("INSERT INTO Status_TCC "
                 "(location,utc,level,message) "
                 "VALUES ('%s',UTC_TIMESTAMP(),'%s','%s')")%(sender,level,msg)
        self.execute_insert(query)
        
