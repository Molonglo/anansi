import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from anansi.calib import models
from anansi.config import config

class CalibDataBase(object):
    def __init__(self,session):
        self.engine = create_engine(config.calib_database.engine)
        models.metadata.create_all(self.engine,checkfirst=True)
        self.session = sessionmaker(bind=self.engine)()

    def __del__(self):
        self.session.close()

    def insert(self,object):
        self.session.add(object)
        try:
            self.session.commit()
        except Exception as error:
            self.session.rollback()
            raise error
