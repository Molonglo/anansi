# coding: utf-8
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
metadata = Base.metadata

class Baseline(Base):
    __tablename__ = 'baselines'

    id = Column(Integer, primary_key=True)
    calib_id = Column(ForeignKey(u'calibrations.id'), index=True)
    module_a = Column(String(6), nullable=False, server_default=text("''"))
    module_b = Column(String(6), nullable=False, server_default=text("''"))
    coarse_delay = Column(Integer)
    fine_delay = Column(Float)
    snr = Column(Float)
    phase = Column(Float)
    weighted_coherence = Column(Float)
    unweighted_coherence = Column(Float)

    calib = relationship(u'Calibration')


class Calibration(Base):
    __tablename__ = 'calibrations'

    id = Column(Integer, primary_key=True)
    obs_id = Column(ForeignKey(u'observations.id'), nullable=False, index=True)
    sefd = Column(Float)
    tsys = Column(Float)
    reference_module = Column(String(6))
    rfi_fraction = Column(Float)
    threshold = Column(Float)

    obs = relationship(u'Observation')


class Delay(Base):
    __tablename__ = 'delays'

    id = Column(Integer, primary_key=True)
    calib_id = Column(ForeignKey(u'calibrations.id'), nullable=False, index=True)
    module = Column(String(6), nullable=False, server_default=text("''"))
    delay = Column(Float, nullable=False)
    weight = Column(Float, nullable=False)

    calib = relationship(u'Calibration')


class Observation(Base):
    __tablename__ = 'observations'

    id = Column(Integer, primary_key=True)
    source_id = Column(ForeignKey(u'sources.id'), nullable=False, index=True)
    utc_start = Column(DateTime, nullable=False)
    lst_start = Column(DateTime, nullable=False)
    tsamp = Column(Float, nullable=False)
    ncoarse = Column(Integer, nullable=False)
    nfine = Column(Integer, nullable=False)
    nchans = Column(Integer, nullable=False)
    notes = Column(Text)

    source = relationship(u'Source')


class Source(Base):
    __tablename__ = 'sources'

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    raj = Column(String(11), nullable=False, server_default=text("''"))
    decj = Column(String(11), nullable=False, server_default=text("''"))
    flux = Column(Float, nullable=False)
