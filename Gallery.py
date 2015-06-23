#!/usr/bin/env python
import os
from os import listdir
from os.path import splitext
import hashlib
import json
import re
from uuid import uuid1
import shutil
import Exceptions
import zipfile
import rarfile
import scandir
import tempfile
import Database
from contextlib import contextmanager
from Search import Search
from threading import Lock
from Boilerplate import GalleryBoilerplate
from sqlalchemy import select, update, insert
from PyQt5 import QtGui
from PyQt5 import QtCore
from time import time
from datetime import datetime
from send2trash import send2trash


class Gallery(GalleryBoilerplate):
    IMAGE_EXTS = [".png", ".jpg", ".jpeg"]
    HASH_SIZE = 8192
    IMAGE_WIDTH = 200
    MAX_TOOLTIP_LENGTH = 80
    BASE_EX_URL = "http://exhentai.org/g/%s/%s/"
    DB_ID_FILENAME = ".dbid"
    thumbnail_path = None
    image_hash = None
    metadata = None
    force_metadata = False
    thumbnail_verified = False
    db_id = None
    db_uuid = None
    ui_uuid = None
    name = None
    read_count = 0
    last_read = None
    files = None
    db_file = ""
    time_added = None
    expired = False
    path = None
    all_files_loaded = False

    class TypeMap(object):
        FolderGallery = 0
        ZipGallery = 1
        RarGallery = 2

    def __repr__(self):
        return self.name or super(self, Gallery).__repr__()

    def __init__(self, **kwargs):
        self.ui_uuid = str(uuid1())
        self.type = getattr(self.TypeMap, self.__class__.__name__)
        self.lock = Lock()
        self.metadata = {}
        self.parent = kwargs.get("parent", self)
        if not kwargs.get("loaded", False):
            self.db_id = self.find_in_db()
            self.load_metadata()
        else:
            self.load_from_json(kwargs["json"])

    def __del__(self):
        if self.expired:
            self.delete()

    def save_customization(self, ui_gallery): #TODO abstract all of this out for easier use with more sites
        ctags = ui_gallery.property("tags").toString()
        ctitle = ui_gallery.property("title").toString()
        extags = ui_gallery.property("exTags").toString()
        exurl = ui_gallery.property("exURL").toString()

        self.ctags = list(filter(None,
                                 map(lambda x: re.sub("^\s+", "", x),
                                     ctags.split(","))))

        self.extags = list(filter(None,
                                  map(lambda x: re.sub("^\s+", "", x),
                                      extags.split(","))))
        if ctitle != self.ctitle or self.name:
            self.ctitle = ctitle
        if exurl:
            old_id = self.id
            self.id = Gallery.process_ex_url(exurl)
            if self.id == "":
                self.delete_dbmetadata("gmetadata")
            elif self.id != old_id:
                self.force_metadata = True
                self.get_metadata()
        self.parent.setup_tags()
        self.save_metadata()
        self.update_ui_gallery()

    def get_json(self):
        tooltip, lines = self.get_tooltip()
        thumbnail_path = self.thumbnail_path or ""
        tags = ", ".join(self.ctags)
        exTags = ", ".join(self.extags)
        ex_url= self.generate_ex_url() if self.gid else ""
        return {"title": self.title,
                "rating": float(self.rating),
                "tooltip": tooltip,
                "tooltipLines": lines,
                "dbUUID": self.ui_uuid,
                "tags": tags,
                "exTags": exTags,
                "exTitle": self.extitle,
                "fileSize": self.get_file_size(),
                "fileCount": self.file_count,
                "exURL": ex_url,
                "hasMetadata": self.gid is not None,
                "image": "file:///" + thumbnail_path}

    def get_tooltip(self):
        plural = "s" if self.read_count != 1 else ""
        tooltip = "Read %s time%s" % (self.read_count, plural)
        lines = 1
        if self.last_read:
            lines += 1
            tooltip += "\nLast read on: %s" % self.local_last_read_time
        if self.tags:
            tags = ["\nTags: "]
            lines += 1
            for tag in self.tags:
                tag += ", "
                if len(tags[-1] + tag) > self.MAX_TOOLTIP_LENGTH:
                    lines += 1
                    tags.append(tag)
                else:
                    tags[-1] += tag
            tooltip += "\n".join(tags)
            if tooltip[-2:] == ", ":
                tooltip = tooltip[:-2]
        return tooltip, lines

    @property
    def sort_name(self):
        "Only used for sorting. Removed parens/braces/brackets."
        return Search.clean_title(self.title)

    @property
    def sort_rating(self):
        return float(self.rating or 0)

    def set_rating(self, rating):
        self.crating = str(rating)
        self.save_metadata()

    def find_in_db(self):
        # TODO: Deprecate uuid for folder galleries
        uuid = None
        # if os.path.exists(self.db_file):
        #     try:
        #         self.db_uuid = self.load_db_file()
        #     except Exception:
        #         self.logger.warning("DB UUID file invalid.", exc_info=True)
        #         self.delete_db_file()
        if isinstance(self, ArchiveGallery):
            with Database.get_session(self) as session:
                uuid = self.generate_uuid()
                dead_gallery = list(map(dict, session.execute(
                    select([Database.Gallery]).where(
                        Database.Gallery.dead == True).where(
                        Database.Gallery.type == self.TypeMap.ZipGallery).where(
                        Database.Gallery.uuid == uuid
                        ))))
                if dead_gallery:
                    self.db_uuid = dead_gallery[0]["uuid"]
        if self.db_uuid:
            with Database.get_session(self) as session:
                gallery = list(map(dict, session.execute(
                    select([Database.Gallery]).where(
                        Database.Gallery.uuid == self.db_uuid))))
                if gallery:
                    self.db_id = gallery[0]["id"]
                    if isinstance(self, ArchiveGallery):
                        path = self.archive_file
                    else:
                        path = self.path
                    session.execute(update(Database.Gallery).where(
                        Database.Gallery.id == self.db_id).values({"path": path}))
        if not self.db_id:
            self.create_in_db(uuid=uuid)
        return self.db_id

    def create_in_db(self, **kwargs):
        with Database.get_session(self) as session:
            if isinstance(self, ArchiveGallery):
                path = self.archive_file
                self.db_uuid = kwargs.get("uuid") or self.generate_uuid()
            else:
                path = self.path
                self.db_uuid = str(uuid1())
                self.save_db_file()

            result = session.execute(insert(Database.Gallery).values(
                {
                    "type": self.type,
                    "uuid": self.db_uuid,
                    "time_added": int(time()),
                    "path": path

                }))
            self.db_id = int(result.inserted_primary_key[0])

    def mark_for_deletion(self):
        try:
            self.delete_file()
            self.expired = True
        except OSError:
            self.logger.error("Failed to delete gallery from hd", exc_info=True)
            raise Exceptions.UnableToDeleteGalleryError(self)

    def delete(self):
        try:
            self.lock.acquire()
            self.delete_from_db()
            self.delete_thumbnail()
        finally:
            self.lock.release()

    def delete_from_db(self):
        for metadata in self.metadata:
            self.delete_dbmetadata(metadata)
        with Database.get_session(self) as session:
            db_gallery = session.query(Database.Gallery).filter(Database.Gallery.id == self.db_id)[0]
            session.delete(db_gallery)

    def delete_dbmetadata(self, metadata):
        with Database.get_session(self) as session:
            db_gallery = session.query(Database.Gallery).filter(Database.Gallery.id == self.db_id)[0]
            db_metadata = db_gallery.metadata_collection[metadata]
            session.delete(db_metadata)

    def load_metadata(self):
        with Database.get_session(self) as session:
            db_gallery = session.query(Database.Gallery).filter(Database.Gallery.id == self.db_id)[0]
            self.thumbnail_path = db_gallery.thumbnail_path
            self.image_hash = db_gallery.image_hash
            self.db_uuid = db_gallery.uuid
            self.read_count = db_gallery.read_count
            self.last_read = db_gallery.last_read
            self.time_added = db_gallery.time_added
            if isinstance(self, ArchiveGallery):
                self.archive_file = db_gallery.path
                self.path = os.path.dirname(self.archive_file)
            else:
                self.path = db_gallery.path
            for metadata in db_gallery.metadata_collection:
                self.metadata[metadata.name] = json.loads(metadata.json)
            db_gallery.dead = False
            session.add(db_gallery)

    def load_from_json(self, gallery_json):
        self.thumbnail_path = gallery_json.get("thumbnail_path")
        self.image_hash = gallery_json.get("image_hash")
        self.db_uuid = gallery_json.get("uuid")
        self.db_id = gallery_json.get("id")
        self.read_count = gallery_json.get("read_count")
        self.last_read = gallery_json.get("last_read")
        self.time_added = gallery_json.get("time_added")
        self.metadata = gallery_json.get("metadata", {})
        if isinstance(self, ArchiveGallery):
            self.archive_file = gallery_json.get("path")
            self.path = os.path.dirname(self.archive_file)
        else:
            self.path = gallery_json.get("path")

    def update_metadata(self, new_metadata):
        self.metadata.update(new_metadata)
        self.force_metadata = False
        self.save_metadata()

    def save_metadata(self):
        self.logger.info("Saving gallery metadata")
        self.metadata = self.clean_metadata(self.metadata)
        with Database.get_session(self) as session:
            db_gallery = session.query(Database.Gallery).filter(Database.Gallery.id == self.db_id)[0]
            db_metadata_list = db_gallery.metadata_collection
            for name in self.metadata:
                db_metadata = next((m for m in db_metadata_list if m.name == name), None)
                if not db_metadata:
                    self.logger.debug("Creating new metadata table %s" % name)
                    db_metadata = Database.Metadata()
                    db_metadata.gallery = db_gallery
                    db_metadata.name = name
                    db_gallery.metadata_collection.append(db_metadata)
                    session.add(db_metadata)
                    session.add(db_gallery)
                db_metadata.name = name
                db_metadata.json = unicode(json.dumps(self.metadata[name], ensure_ascii=False).encode("utf8"))
                session.commit()  # Have to run this on each iteration in case a new metadata table was created
            db_gallery.thumbnail_path = self.thumbnail_path
            db_gallery.image_hash = self.image_hash
            db_gallery.read_count = self.read_count
            db_gallery.last_read = self.last_read
            if isinstance(self, ArchiveGallery):
                db_gallery.path = self.archive_file
            else:
                db_gallery.path = self.path
            session.add(db_gallery)
        if isinstance(self, FolderGallery):
            self.save_db_file()
        self.update_ui_gallery()

    def save_db_file(self):
        raise NotImplementedError

    def delete_db_file(self):
        raise NotImplementedError

    def load_db_file(self):
        raise NotImplementedError

    def get_file_size(self):
        raise NotImplementedError

    @property
    def file_count(self):
        raise NotImplementedError

    def exists_under(self, directory):
        "Returns whether the gallery exists under any of the given directories"
        directory = os.path.normcase(os.path.realpath(directory))
        path = os.path.normcase(os.path.realpath(self.path))
        return directory in path

    def generate_hash(self, source):
        sha1 = hashlib.sha1()
        buff = source.read(self.HASH_SIZE)
        while len(buff) > 0:
            sha1.update(buff)
            buff = source.read(self.HASH_SIZE)
        return sha1.hexdigest()

    def update_ui_gallery(self):
        self.parent.set_ui_gallery(self)

    def clean_metadata(self, metadata):
        if isinstance(metadata, dict):
            metadata = {key: self.clean_metadata(metadata[key])
                        for key in metadata}
        elif isinstance(metadata, list):
            metadata = [self.clean_metadata(val) for val in metadata]
        elif isinstance(metadata, unicode):
            metadata = re.sub("&#039;", "'", metadata)
            metadata = re.sub("&quot;", "\"", metadata)
            metadata = re.sub("(&amp;)", "&", metadata)
            #metadata = re.sub("&#(\d+)(;|(?=\s))", "", metadata)
        return metadata

    def generate_ex_url(self):
        return self.BASE_EX_URL % (self.gid, self.token)

    @classmethod
    def process_ex_url(cls, url):
        split_url = url.split("/")
        if split_url[-1]:
            return int(split_url[-2]), split_url[-1]
        else:
            return int(split_url[-3]), split_url[-2]

    def get_image(self):
        raise NotImplementedError

    def generate_image_hash(self):
        raise NotImplementedError

    def delete_file(self):
        raise NotImplementedError

    def resize_image(self):
        return self.get_image().scaledToWidth(self.IMAGE_WIDTH,
                                              QtCore.Qt.SmoothTransformation)

    def verify_hash(self, image_hash):
        if self.image_hash != image_hash:
            self.delete_thumbnail()
        return self.image_hash == image_hash

    def load_thumbnail(self):
        image_hash = self.generate_image_hash()
        if not self.thumbnail_path or not os.path.exists(self.thumbnail_path) or not self.verify_hash(image_hash):
            self.image_hash = image_hash
            self.thumbnail_path = os.path.join(self.parent.THUMB_DIR, self.image_hash + ".jpg")
            image = self.resize_image()
            self.logger.debug("Saving new thumbnail")
            assert image.save(self.thumbnail_path, "JPG")
            self.save_metadata()
        self.thumbnail_verified = True

    def delete_thumbnail(self):
        try:
            os.remove(self.thumbnail_path)
        except (OSError, TypeError):
            pass

    def open_file(self):
        self.read_count += 1
        self.last_read = int(time())
        self.save_metadata()
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.files[0]))

    def open_on_ex(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(self.generate_ex_url()))

    def open_folder(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.path))

    def get_metadata(self):
        self.parent.get_metadata(self.ui_uuid)

    @property
    def local_last_read_time(self):
        if self.last_read:
            return datetime.fromtimestamp(self.last_read).strftime("%Y-%m-%d")

    @staticmethod
    def sizeof_fmt(num, suffix='B'):
        for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
            if abs(num) < 1024.0:
                return "%3.1f%s%s" % (num, unit, suffix)
            num /= 1024.0
        return "%.1f%s%s" % (num, 'Yi', suffix)

    def generate_uuid(self):
        if isinstance(self, ArchiveGallery):
            files = self.raw_files
        else:
            files = self.files
        return hashlib.sha1(self.generate_image_hash() + str(len(files))).hexdigest()


class FolderGallery(Gallery):
    files = None

    def __init__(self, **kwargs):
        self.path = os.path.normpath(kwargs.get("path"))
        self.name = os.path.normpath(self.path).split(os.sep)[-1]
        self.files = kwargs.get("files", self.find_files(find_all=True))
        assert len(self.files) > 0
        self.db_file = os.path.join(self.path, self.DB_ID_FILENAME)
        super(FolderGallery, self).__init__(**kwargs)

    @property
    def file_count(self):
        return len(self.files)

    def get_image(self):
        image = QtGui.QImageReader()
        image.setDecideFormatFromContent(True)
        image.setFileName(self.files[0])
        image = image.read()
        assert image.width()
        return image

    def save_db_file(self):
        self.logger.debug("Saving DB UUID file.")
        try:
            db_file = open(self.db_file, "r+b")
        except IOError:
            db_file = open(self.db_file, "wb")
        try:
            db_file.write(self.db_uuid)
            db_file.truncate()
        finally:
            db_file.close()

    def load_db_file(self):
        self.logger.debug("Loading DB UUID file.")
        db_file = open(self.db_file, "rb")
        db_uuid = str(db_file.read())
        self.logger.info("DB UUID loaded from file: %s" % db_uuid)
        db_file.close()
        db_uuid = self.validate_db_uuid(db_uuid)
        return db_uuid

    def validate_db_uuid(self, db_uuid):
        db_id = None
        with Database.get_session(self) as session:
            db_gallery = session.query(Database.Gallery).filter(Database.Gallery.uuid == db_uuid, Database.Gallery.dead == True)
            assert db_gallery.count() == 1
            db_gallery[0].dead = False
            session.add(db_gallery[0])
            db_id = db_gallery[0].id
        return db_id

    def generate_image_hash(self):
        with open(self.files[0], "rb") as image:
            return self.generate_hash(image)

    def find_files(self, find_all=False):
        files = []
        found_files = []
        files = sorted(list(map(lambda x: os.path.join(self.path, x), listdir(self.path))), key=lambda f: f.lower())
        for f in files:
            path = os.path.join(self.path, f)
            if os.path.isfile(path) and splitext(path)[-1].lower() in self.IMAGE_EXTS:
                found_files.append(path)
                if not find_all:
                    break # Only getting the first file for now as a speedup
        self.all_files_loaded = find_all
        found_files = list(map(os.path.normpath, found_files))
        self.files = sorted(found_files, key=lambda f: f.lower())
        return self.files

    def delete_db_file(self):
        os.remove(self.db_file)

    def delete_file(self):
        send2trash(self.path)

    def get_file_size(self):
        size = sum(os.path.getsize(f) for f in self.files)
        return self.sizeof_fmt(size)


class ArchiveGallery(Gallery):
    ARCHIVE_EXTS = [".zip", ".cbz"]
    DB_ID_KEY = "lsv-db_id"
    temp_dir = None
    archive_class = None
    raw_files = None

    def __init__(self, **kwargs):
        self.archive_file = os.path.normpath(kwargs.get("path"))
        self.path = os.path.dirname(self.archive_file)
        self.name, self.archive_type = splitext(os.path.basename(self.archive_file))
        self.find_files()
        assert len(self.raw_files) > 0
        super(ArchiveGallery, self).__init__(**kwargs)

    def __del__(self):
        super(ArchiveGallery, self).__del__()
        if self.temp_dir:
            try:
                shutil.rmtree(self.temp_dir)
            except Exception:
                self.logger.warning("Failed to delete tempdir", exc_info=True)

    @property
    @contextmanager
    def archive(self):
        archive = None
        try:
            archive = self.archive_class(self.archive_file, "r")
            yield archive
        except Exception:
            self.logger.error("Failed to complete archive op for %s" % self.archive_file, exc_info=True)
            raise Exceptions.UnknownArchiveError()
        finally:
            if archive:
                archive.close()

    def get_image(self):
        image = QtGui.QImage()
        assert image.loadFromData(self.raw_image.read())
        return image

    def extract(self):
        self.temp_dir = os.path.normpath(tempfile.mkdtemp())
        with self.archive as archive:
            archive.extractall(self.temp_dir)

    def get_file_size(self):
        return self.sizeof_fmt(os.path.getsize(self.archive_file))

    @property
    def raw_image(self):
        with self.archive as archive:
            return archive.open(self.raw_files[0])

    @property
    def file_count(self):
        return len(self.raw_files)

    @property
    def files(self):
        if not self.temp_dir:
            self.extract()
        return list(map(lambda f: os.path.normpath(os.path.join(
            self.temp_dir, f)), self.raw_files))

    def find_files(self, **kwargs):
        raw_files = []
        with self.archive as archive:
            for f in archive.namelist():
                # Really shouldn't be duplicating this code but it's late and I'm tired
                ext = splitext(f)[-1].lower()
                if ext in self.IMAGE_EXTS:
                    raw_files.append(f)
        self.all_files_loaded = True
        self.raw_files = sorted(raw_files, key=lambda f: f.lower())
        return self.raw_files

    def delete_file(self):
        send2trash(self.archive_file)

    def generate_image_hash(self):
        return self.generate_hash(self.raw_image)

    def generate_archive_hash(self):
        with open(self.archive_file, "rb") as archive:
            return self.generate_hash(archive)


class ZipGallery(ArchiveGallery):
    ARCHIVE_EXTS = [".zip", ".cbz"]
    archive_class = zipfile.ZipFile


class RarGallery(ArchiveGallery):
    ARCHIVE_EXTS = [".rar", ".cbr"]
    archive_class = rarfile.RarFile

