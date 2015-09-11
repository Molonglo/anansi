# coding: utf-8
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, text
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()
metadata = Base.metadata


class CommandCodesEZ80(Base):
    __tablename__ = 'Command_codes_eZ80'

    id = Column(Integer, primary_key=True)
    code_num = Column(Integer, nullable=False)
    description = Column(Text)


class CommandsTCC(Base):
    __tablename__ = 'Commands_TCC'

    id = Column(Integer, primary_key=True)
    utc = Column(DateTime, nullable=False)
    command_type = Column(String, nullable=False)
    xml = Column(Text, nullable=False)


class CommandsEZ80(Base):
    __tablename__ = 'Commands_eZ80'

    id = Column(Integer, primary_key=True)
    utc = Column(DateTime, nullable=False)
    code = Column(String)
    message = Column(String)


class Constant(Base):
    __tablename__ = 'Constants'

    name = Column(String(255), primary_key=True, server_default=text("''"))
    value = Column(Float(asdecimal=True), nullable=False)


class ErrorCodesEZ80(Base):
    __tablename__ = 'Error_codes_eZ80'

    code_id = Column(Integer, primary_key=True)
    code_level = Column(String(1), nullable=False, server_default=text("''"))
    code_num = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)


class IPAdress(Base):
    __tablename__ = 'IP_adresses'

    name = Column(String(255), primary_key=True, server_default=text("''"))
    ip = Column(String(15), nullable=False, server_default=text("''"))
    port = Column(Integer, nullable=False)


class PositionEZ80(Base):
    __tablename__ = 'Position_eZ80'

    id = Column(Integer, primary_key=True)
    utc = Column(DateTime, nullable=False)
    drive = Column(String, nullable=False)
    west_count = Column(Integer, nullable=False)
    east_count = Column(Integer, nullable=False)


class StatusTCC(Base):
    __tablename__ = 'Status_TCC'

    id = Column(Integer, primary_key=True)
    location = Column(String, nullable=False)
    utc = Column(DateTime, nullable=False)
    level = Column(String, nullable=False)
    message = Column(Text, nullable=False)


class StatusEZ80(Base):
    __tablename__ = 'Status_eZ80'

    id = Column(Integer, primary_key=True)
    utc = Column(DateTime, nullable=False)
    code_level = Column(String, nullable=False)
    code_num = Column(Integer, nullable=False)

