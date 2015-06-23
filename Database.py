import sqlalchemy
import migrate
from migrate.versioning import api
import contextlib
from sqlalchemy.ext.declarative import declarative_base
import os
from threading import Lock
from Logger import Logger
from Program import resource_path

CONFIG_DIR = os.path.expanduser("~/.lsv")
DB_NAME = "db.sqlite"
DATABASE_URI = "sqlite:///" + os.path.join(CONFIG_DIR, DB_NAME)
DATABASE_FILE = os.path.join(CONFIG_DIR, DB_NAME)
MIGRATE_REPO = resource_path("migrate_repo/")

base = declarative_base()
engine = sqlalchemy.create_engine(DATABASE_URI)
session_maker = sqlalchemy.orm.sessionmaker(bind=engine)
lock = Lock()


class Database(Logger):
    "Dummy class to log in this file"
    pass

Database = Database()


class Config(base):
    __tablename__ = "config"
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    version = sqlalchemy.Column(sqlalchemy.Text)
    json = sqlalchemy.Column(sqlalchemy.Text)


class Gallery(base):
    __tablename__ = "gallery"
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    favorite = sqlalchemy.Column(sqlalchemy.Boolean)
    dead = sqlalchemy.Column(sqlalchemy.Boolean, default=False)
    path = sqlalchemy.Column(sqlalchemy.Text)
    type = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)
    thumbnail_path = sqlalchemy.Column(sqlalchemy.Text)
    image_hash = sqlalchemy.Column(sqlalchemy.Text)
    uuid = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    last_read = sqlalchemy.Column(sqlalchemy.Integer)
    read_count = sqlalchemy.Column(sqlalchemy.Integer, default=0, nullable=False)
    time_added = sqlalchemy.Column(sqlalchemy.Integer)
    metadata_collection = sqlalchemy.orm.relationship("Metadata", lazy="joined", backref="gallery")

    def to_json(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class Metadata(base):
    __tablename__ = "metadata"
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    name = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    json = sqlalchemy.Column(sqlalchemy.Text)
    gallery_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey("gallery.id"))


def setup():
    Database.logger.debug("Setting up database.")
    if not os.path.exists(DATABASE_FILE):
        base.metadata.create_all(engine)
        api.version_control(DATABASE_URI, MIGRATE_REPO, version=api.version(MIGRATE_REPO))
    else:
        try:
            api.version_control(DATABASE_URI, MIGRATE_REPO, version=1)
        except migrate.DatabaseAlreadyControlledError:
            pass
    api.upgrade(DATABASE_URI, MIGRATE_REPO)

@contextlib.contextmanager
def get_session(requester):
    Database.logger.debug("New DB session requested from %s" % requester)
    session = None
    try:
        lock.acquire()
        session = sqlalchemy.orm.scoped_session(session_maker)
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        lock.release()
        session.close()


if __name__ == "__main__":
    setup()
