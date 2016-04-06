import os
import json
import shutil
import hashlib
import tempfile
import humanize
import subprocess
from time import time
from enum import Enum
from uuid import uuid1
from unrar import rarfile
from threading import RLock
from datetime import datetime
from operator import itemgetter
from send2trash import send2trash
from typing import List, Dict, Tuple
from contextlib import contextmanager
from PyQt5 import QtGui, QtCore, QtQml
from sqlalchemy import select, update, insert, delete
import PandaViewer
from . import zipfile, metadata, exceptions, user_database
from .utils import Utils
from .logger import Logger
from .config import Config


class GalleryIDMap(Enum):
    FolderGallery = 0
    ZipGallery = 1
    RarGallery = 2


class GenericGallery(Logger):
    IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif")
    IMAGE_WIDTH = 200
    IMAGE_HEIGHT = 280
    MAX_TOOLTIP_LENGTH = 80
    FILTERED_FILES = ("hentairulesbanner", "credits", "recruit", "zcredits", "kameden", "!credits")
    thumbnail_source = None
    image_hash = None
    mtime_hash = None
    force_metadata = False
    db_id = None
    db_uuid = None
    ui_uuid = None
    name = ""
    read_count = 0
    last_read = ""
    time_added = None
    expired = False
    user_deleted = False
    folder = None
    type = None
    thumbnail_verified = False
    db_uuid_verified = False
    metadata_manager = None
    release_called = False
    lock = RLock()

    def __repr__(self):
        return "%s: %s" % (self.__class__.__name__, self.location)

    def __init__(self, **kwargs):
        self.ui_uuid = str(uuid1())
        self.metadata_manager = metadata.MetadataManager(gallery=self)
        if kwargs.get("loaded"):
            self.load_from_json(kwargs["json"])
        else:
            assert self.file_count > 0
            self.find_in_db()
            if self.db_id is None:
                self.create_in_db()
            self.load_from_db()

    def __lt__(self, other):
        key = [t.value for t in PandaViewer.app.SortMethodMap][Config.sort_type]
        return getattr(self, key) < getattr(other, key)

    @classmethod
    def create_from_type(cls, type: int, gallery_json: dict) -> 'GenericGallery':
        return list(GalleryClassMap)[type].value(**gallery_json)

    @classmethod
    def generate_hash_from_file(cls, file_path: str) -> str:
        with open(file_path, "rb") as f:
            return Utils.generate_hash_from_source(f)

    @classmethod
    def get_image_from_file(self, file_path: str) -> QtGui.QImage:
        assert os.path.exists(file_path)
        image = QtGui.QImageReader()
        image.setDecideFormatFromContent(True)  # Required for cases when the extension doesn't match the content
        image.setFileName(file_path)
        image = image.read()
        assert image.width()
        return image

    @classmethod
    def filtered_files(cls, files: List[str]) -> List[str]:
        return [
            f for f in files if
            os.path.splitext(os.path.basename(f).lower())[0] not in cls.FILTERED_FILES
            ]

    def release(self):
        if self.release_called:
            return
        if self.user_deleted:
            self.delete_from_db()
        self.release_called = True

    def save_customization(self, ui_metadata: QtQml.QJSValue):
        if self.metadata_manager.update_from_ui_metadata(ui_metadata):
            with self.lock:
                self.force_metadata = True
                self.get_metadata()
        self.save_metadata(update_ui=True)
        PandaViewer.app.setup_tags()

    def get_json(self) -> Dict:
        return {
            "title": self.title,
            "rating": self.metadata_manager.get_value("rating"),
            "tooltip": self.get_tooltip(),
            "dbUUID": self.ui_uuid,
            "category": self.metadata_manager.get_value("category"),
            "galleryHasMetadata": self.metadata_manager.get_metadata_value(
                metadata.MetadataClassMap.gmetadata, "url") != "", # TODO fix for future sites
            "image": Utils.convert_to_qml_path(self.thumbnail_path),
        }

    def get_detailed_json(self) -> Dict:
        gallery_json = self.get_json()
        gallery_json["files"] = self.get_files()
        gallery_json["metadata"] = self.metadata_manager.get_customize_json()
        return gallery_json

    def get_tooltip(self) -> str:
        plural = "s" if self.read_count != 1 else ""
        tooltip = "Read %s time%s" % (self.read_count, plural)
        if self.last_read:
            tooltip += "<br>Last read %s" % self.local_last_read_time
        tag_map = {}
        for tag in self.metadata_manager.all_tags:
            tag, namespace = Utils.separate_tag(tag)
            namespace = str(namespace).lower().capitalize()
            value = tag_map.get(namespace, [])
            value.append(tag)
            tag_map[namespace] = value
        if tag_map:
            namespace_tags = sorted([(namespace, sorted(tags)) for namespace, tags in tag_map.items()],
                                    key=itemgetter(0))
            tag_tooltip = "<table align=left cellspacing=0 cellpadding=0>"
            for namespace, tags in namespace_tags:
                tag_tooltip += "<tr><td>%s: </td><td>" % namespace
                current_line = ""
                for tag in tags:
                    tag_entry = tag + ", "
                    if len(current_line + tag) > self.MAX_TOOLTIP_LENGTH:
                        current_line = ""
                        tag_tooltip += "<br>" + tag_entry
                    else:
                        tag_tooltip += tag_entry
                    current_line += tag
                if tag_tooltip[-2:] == ", ":
                    tag_tooltip = tag_tooltip[:-2]
                tag_tooltip += "</td></tr>"
            tag_tooltip += "</table>"
            tooltip += tag_tooltip
        return tooltip

    def set_rating(self, rating: float):
        rating = str(rating)
        if rating == "0.0":
            rating = ""
        self.metadata_manager.update_metadata_value(metadata.MetadataClassMap.cmetadata,
                                                    "rating", rating)
        self.metadata_manager.save(metadata.MetadataClassMap.cmetadata)
        self.update_ui_gallery()

    def find_in_db(self):
        self.db_uuid = self.generate_uuid()
        with user_database.get_session(self, acquire=True) as session:
            db_gallery = Utils.convert_result(session.execute(
                select([user_database.Gallery]).where(
                    user_database.Gallery.uuid == self.db_uuid).where(
                    user_database.Gallery.type == self.type).where(
                    user_database.Gallery.dead == True
                )))
            if db_gallery:
                self.db_id = db_gallery[0]["id"]
                session.execute(update(user_database.Gallery).where(
                    user_database.Gallery.id == self.db_id).values(
                    {
                        "path": self.location,
                        "dead": False,
                    }
                ))

    def create_in_db(self, **kwargs):
        self.mtime_hash = self.generate_mtime_hash()
        with user_database.get_session(self) as session:
            result = session.execute(insert(user_database.Gallery).values(
                {
                    "type": self.type,
                    "uuid": self.db_uuid,
                    "time_added": int(time()),
                    "path": self.location,
                    "mtime_hash": self.mtime_hash,

                }))
            self.db_id = int(result.inserted_primary_key[0])

    def mark_for_deletion(self):
        self.logger.info("Marked for deletion")
        try:
            self.delete_file()
            self.expired = True
            self.user_deleted = True
        except OSError:
            self.logger.error("Failed to delete gallery from hd", exc_info=True)
            raise exceptions.UnableToDeleteGalleryError(self)

    def delete_from_db(self):
        self.logger.debug("Deleting from db.")
        self.metadata_manager.delete_all()
        with user_database.get_session(self) as session:
            session.execute(delete(user_database.Gallery).where(user_database.Gallery.id == self.db_id))

    def delete_dbmetadata(self, metadata: 'metadata.MetadataClassMap'):
        self.metadata_manager.get_metadata(metadata).delete()

    def load_from_db(self):
        with user_database.get_session(self) as session:
            db_gallery = Utils.convert_result(
                session.execute(select([user_database.Gallery]).where(
                    user_database.Gallery.id == self.db_id)))[0]
            db_metadata = Utils.convert_result(session.execute(select([user_database.Metadata]).where(
                user_database.Metadata.gallery_id == self.db_id)))
        db_gallery["metadata"] = {m["name"]: json.loads(m["json"]) for m in db_metadata}
        self.load_from_json(db_gallery)

    def load_from_json(self, gallery_json: Dict):
        self.thumbnail_source = gallery_json.get("thumbnail_source")
        self.image_hash = gallery_json.get("image_hash")
        self.db_uuid = gallery_json.get("uuid")
        self.db_id = gallery_json.get("id")
        self.read_count = gallery_json.get("read_count")
        self.last_read = gallery_json.get("last_read") or 0
        self.time_added = gallery_json.get("time_added")
        self.mtime_hash = gallery_json.get("mtime_hash")
        if isinstance(self, ArchiveGallery):
            self.archive_file = gallery_json.get("path")
            self.folder = os.path.dirname(self.archive_file)
        else:
            self.folder = gallery_json.get("path")
        for key, value in gallery_json.get("metadata", {}).items():
            self.metadata_manager.load_metadata_from_json(metadata.MetadataClassMap[key], value)

    def update_metadata(self, new_metadata: Dict[str, Dict]):
        for name, values in new_metadata.items():
            self.metadata_manager.update_metadata(metadata.MetadataClassMap[name], values)
        self.force_metadata = False

    def save_metadata(self, update_ui: bool = True):
        self.logger.info("Saving gallery metadata")
        self.metadata_manager.save_all()
        with user_database.get_session(self) as session:
            session.execute(update(user_database.Gallery).where(user_database.Gallery.id == self.db_id).values(
                {
                    "image_hash": self.image_hash,
                    "read_count": self.read_count,
                    "last_read": self.last_read,
                    "path": self.location,
                    "uuid": self.db_uuid,
                    "mtime_hash": self.mtime_hash,
                    "thumbnail_source": self.thumbnail_source,
                }
            ))
        self.logger.info("Gallery metadata saved")
        if update_ui:
            self.update_ui_gallery()

    def update_ui_gallery(self):
        PandaViewer.app.set_ui_gallery(self)

    def resize_thumbnail_source(self) -> QtGui.QImage:
        try:
            image = self.get_image(index=int(self.thumbnail_source))
        except (ValueError, TypeError):
            image = self.get_image_from_file(self.thumbnail_source)
        if image.width() > image.height():
            transform = QtGui.QTransform()
            transform.rotate(-90)
            image = image.transformed(transform)
        return image.scaled(self.IMAGE_WIDTH, self.IMAGE_HEIGHT,
                            QtCore.Qt.KeepAspectRatioByExpanding, QtCore.Qt.SmoothTransformation)

    def generate_thumbnail(self):
        try:
            self.image_hash = self.generate_image_hash(index=int(self.thumbnail_source))
        except (TypeError, ValueError):
            self.image_hash = self.generate_hash_from_file(self.thumbnail_source)
        if not os.path.exists(self.thumbnail_path):
            image = self.resize_thumbnail_source()
            self.logger.debug("Saving new thumbnail")
            assert image.save(self.thumbnail_path, "JPG")
            assert os.path.exists(self.thumbnail_path)

    def load_thumbnail(self):
        if not self.has_valid_thumbnail():
            self.thumbnail_source = self.thumbnail_source or str(0)
            self.generate_thumbnail()
            self.save_metadata(update_ui=False)
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
        valid = self.thumbnail_source is not None and self.validate_thumbnail_source()
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
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.get_files()[index]))

    def open_on_ex(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(
            self.metadata_manager.get_metadata_value(
                metadata.MetadataClassMap.gmetadata, "url")))

    def open_folder(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.folder))

    def get_metadata(self):
        PandaViewer.app.get_metadata(self.ui_uuid)

    def generate_uuid(self) -> str:
        return str(hashlib.sha1((self.generate_image_hash(index=0) +
                                 self.generate_image_hash(index=-1) +
                                 str(self.file_count)).encode("utf8")).hexdigest())

    def has_ex_id(self) -> bool:
        return self.metadata_manager.get_metadata_value()

    def has_custom_metadata(self) -> bool:
        return self.metadata_manager.has_metadata(metadata.MetadataClassMap.cmetadata)

    def has_ex_metadata(self) -> bool:
        return self.metadata_manager.has_metadata(metadata.MetadataClassMap.gmetadata)

    def is_archive_gallery(self):
        return isinstance(self, ArchiveGallery)

    def validate_db_uuid(self):
        mtime_hash = self.generate_mtime_hash()
        if mtime_hash != self.mtime_hash:
            self.mtime_hash = mtime_hash
            self.db_uuid = self.generate_uuid()
            self.save_metadata(update_ui=False)
        self.db_uuid_verified = True

    def reset_filesystem_data(self):
        with self.lock:
            self.validate_db_uuid()
            self.thumbnail_verified = False
            self.load_thumbnail()
            self.update_ui_gallery()

    def valid_for_ex_search(self):
        return self.metadata_manager.get_metadata_value(
            metadata.MetadataClassMap.gmetadata, "gid") is None and not self.expired

    def valid_for_force_ex_search(self):
        return self.metadata_manager.get_metadata_value(
            metadata.MetadataClassMap.gmetadata, "gid") is not None and not self.expired and self.force_metadata

    def gallery_deleted(self):
        self.expired = True
        with user_database.get_session(self) as session:
            session.execute(update(user_database.Gallery).where(
                user_database.Gallery.id == self.db_id).values({
                    "dead": True
            }))

    def get_file_size(self):
        raise NotImplementedError

    def find_file_index(self, path):
        raise NotImplementedError

    def get_image(self, index=None):
        raise NotImplementedError

    def generate_image_hash(self, index=None):
        raise NotImplementedError

    def generate_mtime_hash(self):
        raise NotImplementedError

    def delete_file(self):
        raise NotImplementedError

    def reset_files(self):
        raise NotImplementedError

    def file_belongs_to_gallery(self, file):
        raise NotImplementedError

    def file_moved(self, destination):
        raise NotImplementedError

    def file_deleted(self):
        raise NotImplementedError

    def folder_moved(self, source, destination):
        raise NotImplementedError

    def get_files(self, filtered=False):
        raise NotImplementedError

    def find_files(self, find_all=False) -> List[str]:
        raise NotImplementedError

    @property
    def image_folder(self) -> str:
        return Utils.convert_to_qml_path(os.path.dirname(self.get_files()[0]))

    @property
    def thumbnail_path(self) -> str:
        if self.image_hash:
            return os.path.join(PandaViewer.app.THUMB_DIR, self.image_hash) + ".jpg"
        return ""

    @property
    def ex_id(self) -> List:
        return self.metadata_manager.get_metadata_value(metadata.MetadataClassMap.gmetadata, "id")

    @property
    def title(self) -> str:
        title = self.metadata_manager.get_value("title") or self.name
        return title.replace("_", " ")

    @property
    def sort_name(self) -> str:
        return Utils.clean_title(self.title)

    @property
    def clean_name(self) -> str:
        return Utils.clean_title(self.title, remove_enclosed=False)

    @property
    def sort_rating(self) -> float:
        return self.metadata_manager.get_value("rating")

    @property
    def local_last_read_time(self) -> str:
        return humanize.naturaltime(datetime.fromtimestamp(self.last_read)) if self.last_read else ""

    @property
    def sort_path(self):
        raise NotImplementedError

    @property
    def file_count(self):
        raise NotImplementedError

    @property
    def location(self):
        raise NotImplementedError


class FolderGallery(GenericGallery):
    _files = None
    type = GalleryIDMap.FolderGallery.value

    def __init__(self, **kwargs):
        self.folder = Utils.normalize_path(kwargs.get("path"))
        self._files = kwargs.get("files")
        if kwargs.get("loaded"):
            assert any(os.path.isfile(os.path.join(self.folder, f)) for f in os.listdir(self.folder))
        super().__init__(**kwargs)

    def invalidate_files(self):
        with self.lock:
            self._files = None

    def get_files(self, filtered=True):
        with self.lock:
            if self._files is None:
                self._files = self.find_files()
        if filtered:
            return self.filtered_files(self._files)
        else:
            return self._files

    def validate_file_count(self):
        assert len(self.get_files()) > 0

    def get_image(self, index=None):
        return self.get_image_from_file(self.get_files()[index])

    def generate_image_hash(self, index=None):
        index = index if index is not None else 0
        return self.generate_hash_from_file(self.get_files()[index])

    def find_files(self, find_all=False) -> List[str]:
        found_files = []
        for base_folder, _, files in os.walk(self.folder):
            for f in files:
                if Utils.file_has_allowed_extension(f, self.IMAGE_EXTS) or find_all:
                    found_files.append(os.path.join(base_folder, f))
            break
        found_files = list(map(os.path.normpath, found_files))
        return Utils.human_sort_paths(found_files)

    def delete_file(self):
        if (len(self.get_files(filtered=False)) != len(self.find_files(find_all=True))):
            for f in self.get_files(filtered=False): send2trash(f)
        else:
            send2trash(self.folder)

    def get_file_size(self):
        return sum(os.path.getsize(f) for f in self.get_files(filtered=False))

    def find_file_index(self, path):
        path = Utils.normalize_path(path)
        files = self.get_files()
        for i in range(len(files)):
            if path == files[i]:
                return i

    def generate_mtime_hash(self):
        hash_algo = hashlib.sha1()
        files = self.get_files()
        with self.lock:
            for f in (files[0], files[-1]):
                stat = os.stat(f)
                hash_algo.update((str(stat.st_mtime_ns) + str(stat.st_size)).encode("utf8"))
        return hash_algo.hexdigest()

    def reset_files(self):
        with self.lock:
            self._files = None
        self.get_files()

    def file_belongs_to_gallery(self, file):
        if Utils.file_has_allowed_extension(file, self.IMAGE_EXTS):
            return os.path.dirname(file) == self.folder
        return False

    def file_deleted(self):
        with self.lock:
            self.reset_files()
            if not len(self.get_files()):
                return True
            else:
                self.reset_filesystem_data()
                return False

    def file_moved(self, destination):
        with self.lock:
            self.reset_files()
            self.reset_filesystem_data()

    def folder_moved(self, source, destination):
        self.logger.info("Moving %s from %s to %s" % (self, source, destination))
        self.folder = Utils.normalize_path(self.folder.replace(source, destination))
        self.logger.debug("New folder: %s" % self.folder)
        self.reset_files()

    @property
    def location(self) -> str:
        return Utils.normalize_path(self.folder)

    @property
    def name(self):
        return self.folder.split(os.sep)[-1]

    @property
    def file_count(self):
        return len(self.get_files())

    @property
    def sort_path(self):
        return self.folder


class ArchiveGallery(GenericGallery):
    ARCHIVE_EXTS = ()
    temp_dir = None
    archive_type = None
    archive_file = None
    _raw_files = None

    def __init__(self, **kwargs):
        self.change_archive_file(kwargs.get("path"))
        super().__init__(**kwargs)

    def __del__(self):
        super().__del__()
        if self.temp_dir:
            try:
                shutil.rmtree(self.temp_dir)
            except Exception:
                self.logger.warning("Failed to delete tempdir", exc_info=True)

    def change_archive_file(self, file):
        with self.lock:
            self.archive_file = Utils.normalize_path(file)
            self.folder = os.path.dirname(self.archive_file)
            self.name, self.archive_type = os.path.splitext(os.path.basename(self.archive_file))
            self.archive_type = self.archive_type[1:]

    @property
    def location(self):
        return Utils.normalize_path(self.archive_file)

    def get_raw_files(self, filtered=True):
        with self.lock:
            if self._raw_files is None:
                self._raw_files = self.find_files()
        if filtered:
            return self.filtered_files(self._raw_files)
        else:
            return self._raw_files

    @property
    def file_count(self):
        return len(self.get_raw_files())

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
        if getattr(Config, "extract_" + self.archive_type.lower()) or index != 0:
            super().open_file(index)
        else:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.archive_file))

    def extract(self):
        if not self.temp_dir:
            self.temp_dir = Utils.normalize_path(tempfile.mkdtemp())
            with self.archive as archive:
                archive.extractall(self.temp_dir)

    def get_file_size(self):
        return os.path.getsize(self.archive_file)

    def get_raw_image(self, index=None):
        index = index if index is not None else 0
        with self.archive as archive:
            return archive.open(self.get_raw_files()[index])

    def get_files(self, filtered=True):
        self.extract()
        files = [os.path.join(self.temp_dir, f) for f in self.get_raw_files(filtered=filtered)]
        return self.filtered_files(list(map(Utils.normalize_path, files)))

    def find_files(self, find_all=False) -> List[str]:
        with self.archive as archive:
            raw_files = [f for f in archive.namelist()
                         if Utils.file_has_allowed_extension(f, self.IMAGE_EXTS)]
        return Utils.human_sort_paths(raw_files)

    def delete_file(self):
        send2trash(self.archive_file)

    def generate_image_hash(self, index=None):
        return Utils.generate_hash_from_source(self.get_raw_image(index))

    def generate_archive_hash(self):
        with open(self.archive_file, "rb") as archive:
            return Utils.generate_hash_from_source(archive)

    def open_folder(self):
        if os.name == "nt":
            subprocess.call("explorer.exe /select, \"%s\"" % self.archive_file)
        else:
            super().open_folder()

    def find_file_index(self, path):
        path = os.path.basename(Utils.normalize_path(path))
        raw_files = self.get_raw_files()
        for i in range(len(raw_files)):
            if path == os.path.basename(raw_files[i]):
                return i

    def generate_mtime_hash(self):
        hash_algo = hashlib.sha1()
        with self.lock:
            stat = os.stat(self.archive_file)
            hash_algo.update((str(stat.st_mtime_ns) + str(stat.st_size)).encode("utf8"))
        return hash_algo.hexdigest()

    def reset_files(self):
        with self.lock:
            self._raw_files = None
        self._raw_files = self.find_files()

    def file_belongs_to_gallery(self, f: str):
        return f == self.archive_file

    def file_moved(self, destination):
        with self.lock:
            self.change_archive_file(destination)
            self.reset_files()
            self.reset_filesystem_data()

    def folder_moved(self, source, destination):
        with self.lock:
            self.change_archive_file(self.archive_file.replace(source, destination))
            self.reset_files()

    def file_deleted(self):
        return True


class ZipGallery(ArchiveGallery):
    ARCHIVE_EXTS = (".zip", ".cbz")
    type = GalleryIDMap.ZipGallery.value

    @property
    @contextmanager
    def archive(self):
        archive = None
        try:
            archive = zipfile.ZipFile(self.archive_file, "r")
            yield archive
        except Exception:
            self.logger.error("Failed to complete archive op for %s" % self.archive_file, exc_info=True)
            raise exceptions.UnknownArchiveError()
        finally:
            archive and archive.close()


class RarGallery(ArchiveGallery):
    ARCHIVE_EXTS = (".rar", ".cbr")
    type = GalleryIDMap.RarGallery.value
    _archive = None

    @property
    @contextmanager
    def archive(self):
        try:
            archive = rarfile.RarFile(self.archive_file, "r")
            yield archive
        except Exception:
            self.logger.error("Failed to complete archive op for %s" % self.archive_file, exc_info=True)
            raise exceptions.UnknownArchiveError()


class GalleryClassMap(Enum):
    FolderGallery = FolderGallery
    ZipGallery = ZipGallery
    RarGallery = RarGallery
