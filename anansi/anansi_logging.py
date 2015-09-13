import os
import warnings
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime as dt
from functools import wraps
from anansi import database_structure as models
from anansi.config import config

#session singleton
def get_session():
    if get_session.session_class is None:
        engine = create_engine(config.database.engine)
        models.Base.metadata.create_all(engine,checkfirst=True)
        get_session.session_class = sessionmaker(bind=engine)
    return get_session.session_class()
get_session.session_class = None

class DataBaseLogger(object):
    def __init__(self):
        self.session = get_session()

    def __del__(self):
        self.session.close()

    def insert(self,object):
        self.session.add(object)
        try:
            self.session.commit()
        except Exception as error:
            self.session.rollback()
            raise error
        
    def log_tcc_command(self,cmd_type,xml_msg):
        self.insert(models.CommandsTCC(utc=dt.utcnow(),command_type=cmd_type,xml=xml_msg))

    def log_position(self,drive,west_count,east_count):
        self.insert(models.PositionEZ80(utc=dt.utcnow(),drive=drive,east_count=east_count,west_count=west_count))
        
    def log_eZ80_status(self,code_level,code_num):
        self.insert(models.StatusEZ80(utc=dt.utcnow(),code_level=code_level,code_num=code_num))

    def log_eZ80_command(self,code,data):
        self.insert(models.CommandsEZ80(utc=dt.utcnow(),code=code,message=str(data)))

    def log_tcc_status(self,location,level,msg):
        self.insert(models.StatusTCC(location=location,utc=dt.utcnow(),level=level,message=msg.replace("'","")))

