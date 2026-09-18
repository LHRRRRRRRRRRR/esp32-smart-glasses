# server/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
from config import DB_PATH

# 连接SQLite
DATABASE_URL = f"sqlite:///{DB_PATH}"

# 以后换MySQL只改这行：
# DATABASE_URL = "mysql+pymysql://root:password@localhost:3306/smart_glasses"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)

def init_db():
    """创建所有表"""
    Base.metadata.create_all(engine)

def get_session():
    """获取数据库会话"""
    return SessionLocal()
