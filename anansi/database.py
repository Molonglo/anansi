import numpy as np
import logging
logger = logging.getLogger('anansi')

try:
    import MySQLdb
except ImportError:
    logger.warning("Could not import MySQLdb: database functionality will be disabled")

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
                    logger.warn(str(error))
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
            logger.warn(str(error))
            return None
        if not output or len(output) == 0:
            return None
        else:
            output = np.rec.fromrecords(output,names=names)
            return output


class AnansiDataBase(BaseDBManager):
    def __init__(self):
        super(AnansiDataBase,self).__init__()
        try:
            self.connect()
        except Exception as error:
            self.connected = False
            logger.warn(str(error))
        else:
            self.connected = True
    
    def execute_insert(self,query):
        if self.connected:
            super(AnansiDataBase,self).execute_insert(query)

    def connect(self):
        return MySQLdb.connect(
            host=config.database.host,
            port=config.database.port,
            db=config.database.name,
            user=config.database.user,
            passwd=config.database.passwd)

from anansi.config import config
