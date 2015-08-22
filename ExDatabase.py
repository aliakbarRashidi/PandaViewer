import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from Utils import Utils
import contextlib
from threading import Lock
from Logger import Logger
import os


class ExDatabase(Logger):
    "Dummy class to log in this file"
    pass

Database = ExDatabase()


DB_NAME = "exdb.sqlite"
DATABASE_FILE = Utils.convert_from_relative_path(DB_NAME)
exists = os.path.exists(DATABASE_FILE)
DATABASE_URI = "sqlite:///" + DATABASE_FILE

base = declarative_base()
engine = sqlalchemy.create_engine(DATABASE_URI)
session_maker = sqlalchemy.orm.sessionmaker(bind=engine)
lock = Lock()


class Gallery(base):
    __tablename__ = "galleries"
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    gid = sqlalchemy.Column(sqlalchemy.Integer, index=True)
    token = sqlalchemy.Column(sqlalchemy.Text, index=True)
    archiver_key = sqlalchemy.Column(sqlalchemy.Text)
    title = sqlalchemy.Column(sqlalchemy.Text, index=True)
    title_jpn = sqlalchemy.Column(sqlalchemy.Text)
    category = sqlalchemy.Column(sqlalchemy.Text)
    thumb = sqlalchemy.Column(sqlalchemy.Text)
    uploader = sqlalchemy.Column(sqlalchemy.Text)
    posted = sqlalchemy.Column(sqlalchemy.Text)
    filecount = sqlalchemy.Column(sqlalchemy.Text, index=True)
    filesize = sqlalchemy.Column(sqlalchemy.Text, index=True)
    expunged = sqlalchemy.Column(sqlalchemy.Boolean)
    rating = sqlalchemy.Column(sqlalchemy.Text)
    torrentcount = sqlalchemy.Column(sqlalchemy.Text)
    tags = sqlalchemy.Column(sqlalchemy.Text, index=True)

class Title(base):
    __tablename__ = "titles"
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    title = sqlalchemy.Column(sqlalchemy.Text, index=True)
    filecount = sqlalchemy.Column(sqlalchemy.Text, index=True)
    filesize = sqlalchemy.Column(sqlalchemy.Text, index=True)


@contextlib.contextmanager
def get_session(requester, acquire=False):
    Database.logger.debug("New DB session requested from %s" % requester)
    session = None
    try:
        if acquire:
            lock.acquire()
        session = sqlalchemy.orm.scoped_session(session_maker)
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        if acquire:
            lock.release()
        session.close()

