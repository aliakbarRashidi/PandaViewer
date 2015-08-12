#!/usr/bin/env python
import os
from os.path import splitext
import subprocess
import hashlib
import json
import re
from uuid import uuid1
import shutil
import Exceptions
import zipfile
from Utils import Utils
from profilehooks import profile
from unrar import rarfile
import tempfile
import Database
from contextlib import contextmanager
from Search import Search
from Boilerplate import GalleryBoilerplate
from sqlalchemy import select, update, insert, delete
from PyQt5 import QtGui
from PyQt5 import QtCore
from time import time
from datetime import datetime
import scandir
from send2trash import send2trash
from Config import config
from threading import Lock


class Gallery(GalleryBoilerplate):
    IMAGE_EXTS = (".png", ".jpg", ".jpeg")
    HASH_SIZE = 8192
    IMAGE_WIDTH = 200
    MAX_TOOLTIP_LENGTH = 80
    BASE_EX_URL = "http://exhentai.org/g/%s/%s/"
    FILTERED_FILES = ["hentairulesbanner.jpg"]
    thumbnail_source = None
    image_hash = None
    metadata = None
    force_metadata = False
    db_id = None
    db_uuid = None
    ui_uuid = None
    name = ""
    read_count = 0
    last_read = ""
    files = None
    time_added = None
    expired = False
    path = None
    type = None
    thumbnail_verified = False

    class TypeMap(object):
        FolderGallery = 0
        ZipGallery = 1
        RarGallery = 2

    def __repr__(self):
        return self.__class__.__name__ + ": " + self.name

    def __init__(self, **kwargs):
        self.files_lock = Lock()
        self.ui_uuid = str(uuid1())
        self.metadata = {}
        self.parent = kwargs["parent"]
        if kwargs.get("loaded"):
            self.load_from_json(kwargs["json"])
        else:
            assert self.file_count > 0
            self.db_id = self.find_in_db()
            self.load_metadata()

    def __del__(self):
        if self.expired:
            self.delete()

    @property
    def files(self):
        raise NotImplementedError

    @property
    def image_folder(self):
        return Utils.convert_to_qml_path(os.path.dirname(self.files[0]))

    @property
    def thumbnail_path(self):
        if self.image_hash:
            return os.path.join(self.parent.THUMB_DIR, self.image_hash) + ".jpg"
        else:
            return ""

    @classmethod
    def get_class_from_type(cls, type):
        if type == cls.TypeMap.FolderGallery:
            return FolderGallery
        elif type == cls.TypeMap.ZipGallery:
            return ZipGallery
        elif type == cls.TypeMap.RarGallery:
            return RarGallery

    def save_customization(self, ui_gallery): #TODO abstract all of this out for easier use with more sites
        ctags = ui_gallery.property("tags").toString()
        ctitle = ui_gallery.property("title").toString()
        extags = ui_gallery.property("exTags").toString()
        exurl = ui_gallery.property("exURL").toString()
        ex_auto_collection = ui_gallery.property("exAuto").toBool()

        self.ctags = list(filter(None,
                                 map(lambda x: re.sub("^\s+", "", x),
                                     ctags.split(","))))

        self.extags = list(map(lambda x: x.replace(" ", "_"),
                               filter(None, map(lambda x: re.sub("^\s+", "", x), extags.split(",")))))
        self.ctitle = ctitle
        if self.ctitle in (self.extitle, self.name):
            self.ctitle = ""
        if exurl:
            old_id = self.id
            self.id = Gallery.process_ex_url(exurl)
            if self.id == "":
                self.delete_dbmetadata("gmetadata")
            elif self.id != old_id:
                self.force_metadata = True
                self.get_metadata()
        elif exurl != self.ex_url and exurl == "":
            self.delete_dbmetadata("gmetadata")
        self.parent.setup_tags()
        self.ex_auto_collection = ex_auto_collection
        self.save_metadata()
        self.update_ui_gallery()

    def get_json(self):
        tooltip, lines = self.get_tooltip()
        return {"title": self.title,
                "rating": float(self.rating),
                "tooltip": tooltip,
                "tooltipLines": lines,
                "dbUUID": self.ui_uuid,
                "hasMetadata": self.gid is not None,
                "image": Utils.convert_to_qml_path(self.thumbnail_path)}

    def get_detailed_json(self):
        gallery_json = self.get_json()
        tags = ", ".join(self.ctags)
        exTags = ", ".join(self.extags)
        # "fileSize": self.get_file_size(),
        # "fileCount": self.file_count,
        ex_url= self.ex_url if self.gid else ""
        gallery_json["tags"] = tags
        gallery_json["exTags"] = exTags
        gallery_json["exTitle"] = self.extitle
        gallery_json["exAuto"] = self.ex_auto_collection
        gallery_json["exURL"] = ex_url
        gallery_json["files"] = list(map(Utils.convert_to_qml_path, self.files))


        return gallery_json

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
    def location(self):
        return self.path

    @property
    def sort_name(self):
        return Search.clean_title(self.title)

    @property
    def sort_path(self):
        raise NotImplementedError

    @property
    def clean_name(self):
        return Search.clean_title(self.title, remove_enclosed=False)

    @property
    def sort_rating(self):
        return float(self.rating or 0)

    def set_rating(self, rating):
        rating = str(rating)
        if rating == "0.0":
            self.crating = ""
        else:
            self.crating = str(rating)
        self.save_metadata()

    def find_in_db(self):
        # TODO: Deprecate uuid for folder galleries
        self.db_uuid = self.generate_uuid()
        with Database.get_session(self, acquire=True) as session:
            db_gallery = list(map(dict, session.execute(
                select([Database.Gallery]).where(
                    Database.Gallery.uuid == self.db_uuid).where(
                    Database.Gallery.type == self.type).where(
                    Database.Gallery.dead == True
                ))))
            if db_gallery:
                self.db_id = db_gallery[0]["id"]
                session.execute(update(Database.Gallery).where(
                    Database.Gallery.id == self.db_id).values(
                    {
                        "path": self.location,
                        "dead": False,
                    }
                ))
        if not self.db_id:
            self.db_id = self.create_in_db()
        return self.db_id

    def create_in_db(self, **kwargs):
        with Database.get_session(self) as session:
            result = session.execute(insert(Database.Gallery).values(
                {
                    "type": self.type,
                    "uuid": self.db_uuid,
                    "time_added": int(time()),
                    "path": self.location

                }))
            return int(result.inserted_primary_key[0])

    def mark_for_deletion(self):
        self.logger.info("Marked for deletion")
        try:
            self.delete_file()
            self.expired = True
        except OSError:
            self.logger.error("Failed to delete gallery from hd", exc_info=True)
            raise Exceptions.UnableToDeleteGalleryError(self)

    def delete(self):
        self.delete_from_db()

    def delete_from_db(self):
        with Database.get_session(self) as session:
            session.execute(delete(Database.Metadata).where(Database.Metadata.gallery_id == self.db_id))
            session.execute(delete(Database.Gallery).where(Database.Gallery.id == self.db_id))

    def delete_dbmetadata(self, metadata):
        self.metadata.pop(metadata)
        with Database.get_session(self) as session:
            session.execute(delete(Database.Metadata).where(
                Database.Metadata.gallery_id == self.db_id).where(
                Database.Metadata.name == metadata))

    def load_metadata(self):
        with Database.get_session(self) as session:
            db_gallery = list(map(dict,
                                  session.execute(select([Database.Gallery]).where(
                                      Database.Gallery.id == self.db_id))))[0]

            db_metadata = list(map(dict, session.execute(select([Database.Metadata]).where(
                Database.Metadata.gallery_id == self.db_id))))
        db_gallery["metadata"] = {m["name"]: json.loads(m["json"]) for m in db_metadata}
        self.load_from_json(db_gallery)

    def load_from_json(self, gallery_json):
        self.thumbnail_source = gallery_json.get("thumbnail_source")
        self.image_hash = gallery_json.get("image_hash")
        self.db_uuid = gallery_json.get("uuid")
        self.db_id = gallery_json.get("id")
        self.read_count = gallery_json.get("read_count")
        self.last_read = gallery_json.get("last_read") or 0
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

    def save_metadata(self, update_ui=True):
        self.logger.info("Saving gallery metadata")
        self.metadata = self.clean_metadata(self.metadata)
        with Database.get_session(self) as session:
            db_metadata_list = list(map(dict, session.execute(select([Database.Metadata]).where(
                Database.Metadata.gallery_id == self.db_id))))
            for name in self.metadata:
                metadata_json = str(json.dumps(self.metadata[name], ensure_ascii=False))
                db_metadata = next((m for m in db_metadata_list if m["name"] == name), None)
                if not db_metadata:
                    session.execute(insert(Database.Metadata).values(
                        {
                            "name": name,
                            "gallery_id": self.db_id,
                            "json": metadata_json,
                        }
                    ))
                else:
                    session.execute(update(Database.Metadata).where(
                        Database.Metadata.gallery_id == self.db_id).where(
                        Database.Metadata.name == name).values(
                        {
                            "json": metadata_json,

                        }
                    ))
            session.execute(update(Database.Gallery).where(Database.Gallery.id == self.db_id).values(
                {
                    "image_hash": self.image_hash,
                    "read_count": self.read_count,
                    "last_read": self.last_read,
                    "path": self.location,
                    "uuid": self.db_uuid,
                    "thumbnail_source": self.thumbnail_source,
                }
            ))
        self.logger.info("Gallery metadata saved")
        if update_ui:
            self.update_ui_gallery()

    def get_file_size(self):
        raise NotImplementedError

    @property
    def file_count(self):
        raise NotImplementedError

    def find_file_index(self, path):
        raise NotImplementedError

    @classmethod
    def generate_hash_from_file(cls, file_path):
        with open(file_path, "rb") as f:
            return cls.generate_hash(f)

    @classmethod
    def generate_hash(cls, source):
        sha1 = hashlib.sha1()
        buff = source.read(cls.HASH_SIZE)
        while len(buff) > 0:
            sha1.update(buff)
            buff = source.read(cls.HASH_SIZE)
        return sha1.hexdigest()

    def update_ui_gallery(self):
        self.parent.set_ui_gallery(self)

    def clean_metadata(self, metadata):
        if isinstance(metadata, dict):
            metadata = {key: self.clean_metadata(metadata[key])
                        for key in metadata}
        elif isinstance(metadata, list):
            metadata = [self.clean_metadata(val) for val in metadata]
        elif isinstance(metadata, str):
            metadata = re.sub("&#039;", "'", metadata)
            metadata = re.sub("&quot;", "\"", metadata)
            metadata = re.sub("(&amp;)", "&", metadata)
            #metadata = re.sub("&#(\d+)(;|(?=\s))", "", metadata)
        return metadata

    @property
    def ex_url(self):
        return self.BASE_EX_URL % (self.gid, self.token)

    @classmethod
    def process_ex_url(cls, url):
        split_url = url.split("/")
        if split_url[-1]:
            return int(split_url[-2]), split_url[-1]
        else:
            return int(split_url[-3]), split_url[-2]

    def get_image(self, index=None):
        raise NotImplementedError

    def generate_image_hash(self, index=None):
        raise NotImplementedError

    def delete_file(self):
        raise NotImplementedError

    @classmethod
    def get_image_from_file(self, file_path):
        assert os.path.exists(file_path)
        image = QtGui.QImageReader()
        image.setDecideFormatFromContent(True)
        image.setFileName(file_path)
        image = image.read()
        assert image.width()
        return image

    def resize_thumbnail_source(self):
        try:
            image = self.get_image(index=int(self.thumbnail_source))
        except (ValueError, TypeError):
            image = self.get_image_from_file(self.thumbnail_source)
        if image.width() > image.height():
            transform = QtGui.QTransform()
            transform.rotate(-90)
            image = image.transformed(transform)
        return image.scaledToWidth(self.IMAGE_WIDTH, QtCore.Qt.SmoothTransformation)

    def generate_thumbnail(self):
        try:
            self.image_hash = self.generate_image_hash(index=int(self.thumbnail_source))
        except (TypeError, ValueError):
            self.image_hash = self.generate_hash_from_file(self.thumbnail_source)
        image = self.resize_thumbnail_source()
        self.logger.debug("Saving new thumbnail")
        assert image.save(self.thumbnail_path, "JPG")
        assert os.path.exists(self.thumbnail_path)

    def load_thumbnail(self):
        if not self.has_valid_thumbnail():
            self.generate_thumbnail()
            self.save_metadata()
        self.thumbnail_verified = True

    def set_thumbnail_source(self, thumbnail_source):
        index = self.find_file_index(thumbnail_source)
        if index is not None:
            self.thumbnail_source = str(index)
        else:
            self.thumbnail_source = thumbnail_source
        self.generate_thumbnail()
        self.save_metadata()
        self.update_ui_gallery()

    def has_valid_thumbnail(self):
        thumb_exists = self.thumbnail_path and os.path.exists(self.thumbnail_path)
        valid = self.thumbnail_source and self.validate_thumbnail_source()
        return thumb_exists and valid

    def validate_thumbnail_source(self):
        try:
            hash = self.generate_image_hash(index=int(self.thumbnail_source))
        except (TypeError, ValueError):
            try:
                hash = self.generate_hash_from_file(self.thumbnail_source)
            except FileNotFoundError:
                self.thumbnail_source = str(0)
                return False
        return hash == self.image_hash

    def open(self, index=0):
        self.read_count += 1
        self.last_read = int(time())
        self.save_metadata()
        self.open_file(index)

    def open_file(self, index=0):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.files[index]))


    def open_on_ex(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(self.ex_url))

    def open_folder(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.path))

    def get_metadata(self):
        self.parent.get_metadata(self.ui_uuid)

    @property
    def local_last_read_time(self):
        if self.last_read:
            return datetime.fromtimestamp(self.last_read).strftime("%Y-%m-%d")

    def generate_uuid(self):
        return str(hashlib.sha1((self.generate_image_hash(index=0) +
                                 self.generate_image_hash(index=-1) +
                                 str(self.file_count)).encode("utf8")).hexdigest())

    def has_metadata_by_key(self, key):
        metadata = self.metadata.get(key, {})
        for key in metadata:
            if metadata[key] and key != "auto": #TODO ugly hack please fix
                return True
        return False

    def has_custom_metadata(self):
        return self.has_metadata_by_key("cmetadata")

    def has_ex_metadata(self):
        return self.has_metadata_by_key("gmetadata")

    def is_archive_gallery(self):
        return isinstance(self, ArchiveGallery)

    @classmethod
    def filtered_files(cls, files):
        return [f for f in files if os.path.basename(f).lower() not in cls.FILTERED_FILES]


class FolderGallery(Gallery):
    _files = None
    type = Gallery.TypeMap.FolderGallery

    def __init__(self, **kwargs):
        self.path = Utils.normalize_path(kwargs.get("path"))
        if kwargs.get("loaded"):
            assert any(os.path.isfile(os.path.join(self.path, f)) for f in os.listdir(self.path))
        self.name = self.path.split(os.sep)[-1]
        self.files = kwargs.get("files")
        super(FolderGallery, self).__init__(**kwargs)

    @property
    def files(self):
        self.files_lock.acquire()
        if self._files is None:
            self.find_files()
        self.files_lock.release()
        return self.filtered_files(self._files)

    @files.setter
    def files(self, val):
        self._files = val

    @property
    def file_count(self):
        return len(self.files)

    @property
    def sort_path(self):
        return self.path

    def get_image(self, index=None):
        return self.get_image_from_file(self.files[index])

    def generate_image_hash(self, index=None):
        index = index if index is not None else 0
        return self.generate_hash_from_file(self.files[index])

    def find_files(self):
        found_files = []
        for base_folder, _, files in scandir.walk(self.path):
            for f in files:
                if Utils.file_has_allowed_extension(f, self.IMAGE_EXTS):
                    found_files.append(os.path.join(base_folder, f))
            break
        found_files = list(map(os.path.normpath, found_files))
        self.files = sorted(found_files, key=lambda f: f.lower())

    def delete_file(self):
        send2trash(self.path)

    def get_file_size(self):
        size = sum(os.path.getsize(f) for f in self.files)
        return Utils.get_readable_size(size)

    def find_file_index(self, path):
        path = Utils.normalize_path(path)
        for i in range(self.file_count):
            if path == self.files[i]:
                return i


class ArchiveGallery(Gallery):
    temp_dir = None
    archive_class = None
    archive_type = None
    _raw_files = None

    def __init__(self, **kwargs):
        self.archive_file = Utils.normalize_path(kwargs.get("path"))
        self.path = os.path.dirname(self.archive_file)
        self.name, self.archive_type = splitext(os.path.basename(self.archive_file))
        self.archive_type = self.archive_type[1:]
        super(ArchiveGallery, self).__init__(**kwargs)

    def __del__(self):
        super(ArchiveGallery, self).__del__()
        if self.temp_dir:
            try:
                shutil.rmtree(self.temp_dir)
            except Exception:
                self.logger.warning("Failed to delete tempdir", exc_info=True)

    @property
    def location(self):
        return self.archive_file

    @property
    def raw_files(self):
        self.files_lock.acquire()
        if self._raw_files is None:
            self.find_files()
        self.files_lock.release()
        return self._raw_files

    @raw_files.setter
    def raw_files(self, val):
        self._raw_files = val

    @property
    def sort_path(self):
        return self.archive_file

    @property
    def archive(self):
        raise NotImplementedError

    def get_image(self, index=None):
        image = QtGui.QImage()
        assert image.loadFromData(self.get_raw_image(index=index).read())
        return image

    def open_file(self, index=0):
        if getattr(config, "extract_" + self.archive_type.lower()) or index != 0:
            super(ArchiveGallery, self).open_file(index)
        else:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.archive_file))

    def extract(self):
        if not self.temp_dir:
            self.temp_dir = Utils.normalize_path(tempfile.mkdtemp())
            with self.archive as archive:
                archive.extractall(self.temp_dir)

    def get_file_size(self):
        return Utils.get_readable_size(os.path.getsize(self.archive_file))

    def get_raw_image(self, index=None):
        index = index if index is not None else 0
        with self.archive as archive:
            return archive.open(self.raw_files[index])

    @property
    def file_count(self):
        return len(self.raw_files)

    @property
    def files(self):
        self.extract()
        files = [os.path.join(self.temp_dir, f) for f in self.raw_files]
        #print(self.raw_files)
        return self.filtered_files(list(map(Utils.normalize_path, files)))

    def find_files(self, **kwargs):
        raw_files = []
        with self.archive as archive:
            raw_files = [f for f in archive.namelist()
                         if Utils.file_has_allowed_extension(f, self.IMAGE_EXTS)]
        self.raw_files = sorted(raw_files, key=lambda f: f.lower())

    def delete_file(self):
        send2trash(self.archive_file)

    def generate_image_hash(self, index=None):
        return self.generate_hash(self.get_raw_image(index))

    def generate_archive_hash(self):
        with open(self.archive_file, "rb") as archive:
            return self.generate_hash(archive)

    def open_folder(self):
        if os.name == "nt":
            subprocess.call("explorer.exe /select, \"%s\"" % self.archive_file)
        else:
            super(ArchiveGallery, self).open_folder()

    def find_file_index(self, path):
        path = os.path.basename(Utils.normalize_path(path))
        for i in range(self.file_count):
            if path == os.path.basename(self.raw_files[i]):
                return i


class ZipGallery(ArchiveGallery):
    ARCHIVE_EXTS = (".zip", ".cbz")
    type = Gallery.TypeMap.ZipGallery

    @property
    @contextmanager
    def archive(self):
        archive = None
        try:
            archive =  zipfile.ZipFile(self.archive_file, "r")
            yield archive
        except Exception:
            self.logger.error("Failed to complete archive op for %s" % self.archive_file, exc_info=True)
            raise Exceptions.UnknownArchiveError()
        finally:
            archive and archive.close()


class RarGallery(ArchiveGallery):
    ARCHIVE_EXTS = (".rar", ".cbr")
    type = Gallery.TypeMap.RarGallery
    _archive = None

    @property
    @contextmanager
    def archive(self):
        try:
            archive = rarfile.RarFile(self.archive_file, "r")
            yield archive
        except Exception:
            self.logger.error("Failed to complete archive op for %s" % self.archive_file, exc_info=True)
            raise Exceptions.UnknownArchiveError()
