from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from solidworks_ai.config import DATABASE_URL
from solidworks_ai.memory.models import Base

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
