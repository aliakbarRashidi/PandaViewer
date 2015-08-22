import sqlalchemy
import migrate
from migrate.versioning import api
import contextlib
from sqlalchemy.ext.declarative import declarative_base
import os
from threading import Lock
from Logger import Logger
from Utils import Utils



class Database(Logger):
    DB_FILE_NAME = ""

    @property
    def DATABASE_FILE(self):
        return Utils.convert_from_relative_lsv_path(self.DB_FILE_NAME)

    @property
    def DATABASE_URI(self):
        return "sqlite:///" + self.DATABASE_FILE

    def __init__(self):
        super(Database, self).__init__()
        self.lock = Lock()



class UserDatabase(Database):
    DB_FILE_NAME = "db.sqlite"

