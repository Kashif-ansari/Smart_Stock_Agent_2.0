from functools import lru_cache
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from .config import database_url
from .models import Base

@lru_cache(maxsize=1)
def engine():
    url = database_url()
    e = create_engine(url, connect_args={'check_same_thread': False, 'timeout': 30} if url.startswith('sqlite') else {}, pool_pre_ping=True)
    if url.startswith('sqlite'):
        @event.listens_for(e, 'connect')
        def enable_fk(conn, _):
            conn.execute('PRAGMA foreign_keys=ON')
            conn.execute('PRAGMA journal_mode=WAL')
    return e

def init_db():
    Base.metadata.create_all(engine())

@contextmanager
def session():
    s = sessionmaker(bind=engine(), expire_on_commit=False)()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()

