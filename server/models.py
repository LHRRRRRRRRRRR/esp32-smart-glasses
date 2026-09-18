# server/models.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Device(Base):
    __tablename__ = "devices"
    
    id = Column(String(50), primary_key=True)
    name = Column(String(100))
    status = Column(String(20), default="online")
    last_seen = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now)
    
    records = relationship("Record", back_populates="device")

class Record(Base):
    __tablename__ = "records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(50), ForeignKey("devices.id"))
    filename = Column(String(255))
    mode = Column(String(20))
    text = Column(String(500))
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    device = relationship("Device", back_populates="records")
