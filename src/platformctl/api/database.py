import os
from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
class Base(DeclarativeBase): pass
def _database_url() -> str: return os.getenv("DATABASE_URL", "sqlite:///./platformctl.db")
def _build_engine():
    url = _database_url(); connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)
engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
def init_db() -> None:
    from platformctl.api import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try: yield db
    finally: db.close()
