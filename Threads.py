#!/usr/bin/env python

from PyQt5 import QtCore
from Logger import Logger
import threading
import Queue
import weakref
import copy
import scandir
import os
import sys
import json
from Gallery import Gallery, FolderGallery, ZipGallery, RarGallery
import Exceptions
import Database
from RequestManager import RequestManager
from Search import Search
from sqlalchemy import select, update
from profilehooks import profile


class BaseThread(threading.Thread, Logger):
    id = None
    dead = False

    def __init__(self, parent, **kwargs):
        super(BaseThread, self).__init__()
        self.daemon = True
        self.queue = Queue.Queue()
        self.parent = parent
        self.basesignals = self.BaseSignals()
        self.basesignals.exception.connect(self.parent.thread_exception_handler)

    class BaseSignals(QtCore.QObject):
        exception = QtCore.pyqtSignal(object, tuple)

    @property
    def parent(self):
        return self._parent()

    @parent.setter
    def parent(self, val):
        self._parent = weakref.ref(val)

    def _run(self):
        raise NotImplementedError

    def run(self):
        while True:
            restart = False
            try:
                self._run()
            except (KeyboardInterrupt, SystemExit):
                return
            except Exception:
                exc_info = sys.exc_info()
                extype = exc_info[0]
                exvalue = exc_info[1]
                if issubclass(extype, Exceptions.CustomBaseException):
                    restart = exvalue.thread_restart
                self.basesignals.exception.emit(self, exc_info)
                if restart:
                    try:
                        while True:
                            self.queue.get(False)
                    except Queue.Empty:
                        pass




class GalleryThread(BaseThread):
    id = "gallery"

    def __init__(self, parent, **kwargs):
        super(GalleryThread, self).__init__(parent)
        self.signals = self.Signals()
        self.signals.end.connect(self.parent.find_galleries_done)
        self.existing_paths = [g.path for g in self.parent.galleries]
        self.loaded = False

    class Signals(QtCore.QObject):
        end = QtCore.pyqtSignal(list)

    def _run(self):
        while True:
            self.queue.get()
            if not self.loaded:
                self.load_from_db()
            else:
                self.find_galleries()

    """
    Explanation/rationale for the following:
    Initially I planned on using the ORM for everything, mostly because it looks nice and makes things easy
    But given the scale I've had to deal with, I've found it to be too slow to be viable everywhere.
    This method where we get all galleries/metadata was the main culprit.
    So I switched from the ORM to the core for these two intensive statements.
    """

    @profile(sort="tottime", filename="dbload.stats")
    def load_from_db(self):
        candidates = {"folder": [], "zip": [], "rar": []}
        with Database.get_session(self) as session:
            db_gallery_list = map(dict, session.execute(select([Database.Gallery])))
            db_metadata_list = map(dict, session.execute(select([Database.Metadata])))
            metadata_map = {}
            for metadata in db_metadata_list:
                id = metadata["gallery_id"]
                if metadata_map.get(id):
                    metadata_map[id].append(metadata)
                else:
                    metadata_map[id] = [metadata]
            for gallery in db_gallery_list:
                if gallery.get("path") in self.existing_paths:
                    continue
                if not os.path.exists(gallery.get("path")) and not gallery["dead"]:
                    session.execute(
                        update(Database.Gallery).where(
                            Database.Gallery.id == gallery["id"]).values({"dead": True}))
                    continue
                elif os.path.exists(gallery.get("path")) and gallery["dead"]:
                    session.execute(
                        update(Database.Gallery).where(
                            Database.Gallery.id == gallery["id"]).values({"dead": False}))
                    gallery["dead"] = False
                elif gallery["dead"]:
                    continue
                gallery["metadata"] = {}
                for metadata in metadata_map.get(gallery["id"], []):
                    gallery["metadata"][metadata["name"]] = json.loads(metadata["json"])
                candidate = {"path": gallery["path"],
                             "parent": self.parent,
                             "json": gallery,
                             "loaded": True}
                if gallery["type"] == Gallery.TypeMap.FolderGallery:
                    candidates["folder"].append(candidate)
                elif gallery["type"] == Gallery.TypeMap.ZipGallery:
                    candidates["zip"].append(candidate)
                elif gallery["type"] == Gallery.TypeMap.RarGallery:
                    candidates["rar"].append(candidate)
        self.create_from_dict(candidates)
        self.loaded = True

    @profile(sort="tottime", filename="find.stats")
    def find_galleries(self):
        candidates = {"folder": [], "zip": [], "rar": []}
        paths = map(os.path.normpath, map(os.path.expanduser,
                                          self.parent.dirs))
        for path in paths:
            for base_folder, folders, files in scandir.walk(path):
                images = []
                for f in files:
                    ext = os.path.splitext(f)[-1].lower()
                    if ext in FolderGallery.IMAGE_EXTS:
                        images.append(os.path.join(base_folder, f))
                    elif ext in ZipGallery.ARCHIVE_EXTS + RarGallery.ARCHIVE_EXTS:
                        archive_file = os.path.join(base_folder, f)
                        if ext in ZipGallery.ARCHIVE_EXTS:
                            type = "zip"
                        elif ext in RarGallery.ARCHIVE_EXTS:
                            type = "rar"
                        candidates[type].append({"path": archive_file,
                                                 "parent": self.parent})
                if images:
                    candidates["folder"].append({"path": base_folder,
                                                 "parent": self.parent,
                                                 "files": sorted(images, key=lambda f: f.lower())})
        self.create_from_dict(candidates)

    def create_from_dict(self, candidates, session=None):
        invalid_files = []
        galleries = []
        dead_galleries = []
        gallery_candidates = []
        for key in candidates:
            gallery_candidates += candidates[key]
        for gallery in gallery_candidates:
            if gallery.get("path") in self.existing_paths:
                continue
            self.existing_paths.append(gallery.get("path"))
            gallery_obj = None
            try:
                if gallery in candidates["zip"]:
                    gallery_obj = ZipGallery(**gallery)
                elif gallery in candidates["rar"]:
                    gallery_obj = RarGallery(**gallery)
                elif gallery in candidates["folder"]:
                    gallery_obj = FolderGallery(**gallery)
                galleries.append(gallery_obj)
            except Exceptions.UnknownArchiveError:
                gallery_obj = None
                invalid_files.append(gallery.get("path"))
            except AssertionError:
                gallery_obj = None
            except Exception:
                gallery_obj = None
                self.logger.error("%s gallery got unhandled exception" % gallery, exc_info=True)
            if gallery.get("loaded"):
                if not gallery_obj:  # TODO Awful hack please remove
                    dead_galleries.append(gallery.get("id"))
        self.signals.end.emit(galleries)
        if invalid_files:
            raise Exceptions.UnknownZipErrorMessage(invalid_files)
        if dead_galleries:
            with Database.get_session(self) as session:
                db_galleries = session.query(Database.Gallery).filter(Database.Gallery.id.in_(dead_galleries))
                for db_gallery in db_galleries:
                    db_gallery.dead = True
                    session.add(db_gallery)


class ImageThread(BaseThread):
    EMIT_FREQ = 5
    id = "image"

    def __init__(self, parent, **kwargs):
        super(ImageThread, self).__init__(parent)
        self.signals = self.Signals()
        self.signals.end.connect(self.parent.image_thread_done)
        self.signals.gallery.connect(self.parent.set_ui_gallery)

    class Signals(QtCore.QObject):
        end = QtCore.pyqtSignal()
        gallery = QtCore.pyqtSignal(object)

    def _run(self):
        while True:
            galleries = self.queue.get()
            self.generate_images(galleries)

    @profile(sort="tottime", filename="image.stats")
    def generate_images(self, galleries):
        for gallery in galleries:
            if gallery.expired:
                continue
            if not gallery.thumbnail_verified:
                try:
                    gallery.load_thumbnail()
                    #self.signals.gallery.emit(gallery)
                except Exception:
                    self.logger.error("%s gallery failed to get image" % gallery, exc_info=True)
        self.signals.end.emit()
        with Database.get_session(self) as session:
            dead_galleries = session.query(Database.Gallery).filter(Database.Gallery.dead == True)
            for gallery in dead_galleries:
                if gallery.thumbnail_path:
                    try:
                        os.remove(gallery.thumbnail_path)
                    except OSError:
                        pass


class SearchThread(BaseThread):
    API_URL = "http://exhentai.org/api.php"
    BASE_REQUEST = {"method": "gdata", "gidlist": []}
    API_MAX_ENTRIES = 25
    API_ENTRIES = 3
    id = "metadata"

    def __init__(self, parent, **kwargs):
        super(SearchThread, self).__init__(parent)
        self.signals = self.Signals()
        self.signals.end.connect(self.parent.get_metadata_done)
        self.signals.gallery.connect(self.parent.update_gallery_metadata)
        self.signals.current_gallery.connect(self.parent.set_current_metadata_gallery)

    class Signals(QtCore.QObject):
        end = QtCore.pyqtSignal()
        current_gallery = QtCore.pyqtSignal(object)
        gallery = QtCore.pyqtSignal(object, dict)

    def _run(self):
        while True:
            galleries = self.queue.get()
            try:
                self.search(galleries)
            finally:
                self.signals.end.emit()

    def search(self, galleries):
        search_galleries = [g for g in galleries if
                            g.gid is None and g.expired is False]
        self.logger.debug("Search galleries: %s" % [g.name for g in search_galleries])
        need_metadata_galleries = []
        for gallery in search_galleries:
            if gallery.expired:
                continue
            self.signals.current_gallery.emit(gallery)
            search_results = Search.search_by_gallery(gallery)
            if search_results:
                gallery.id = Gallery.process_ex_url(search_results)
            if gallery.gid:
                need_metadata_galleries.append(gallery)
            if len(need_metadata_galleries) == self.API_ENTRIES:
                self.get_metadata(need_metadata_galleries)
                need_metadata_galleries = []
        if need_metadata_galleries:
            self.get_metadata(need_metadata_galleries)
        force_galleries = [g for g in galleries if g.force_metadata]
        force_gallery_metalist = [force_galleries[i:i + self.API_MAX_ENTRIES]
                                  for i in range(0, len(galleries), self.API_MAX_ENTRIES)]
        [self.get_metadata(g) for g in force_gallery_metalist]

    def get_metadata(self, galleries):
        assert len(galleries) <= self.API_MAX_ENTRIES
        payload = copy.deepcopy(self.BASE_REQUEST)
        gid_list = [g.id for g in galleries]
        if not gid_list:
            return
        payload["gidlist"] = gid_list
        response = RequestManager.post(self.API_URL, payload=payload)
        for gallery in galleries:
            if gallery.expired:
                continue
            for metadata in response["gmetadata"]:
                id = [metadata["gid"], metadata["token"]]
                if id == gallery.id:
                    self.signals.gallery.emit(gallery, {"gmetadata": metadata})
                    break


class DuplicateFinderThread(BaseThread):
    id = "duplicate"

    class Signals(QtCore.QObject):
        end = QtCore.pyqtSignal(dict)

    def __init__(self, parent):
        super(DuplicateFinderThread, self).__init__(parent)
        self.signals = self.Signals()
        self.signals.end.connect(self.parent.duplicate_map_generated)

    def _run(self):
        while True:
            galleries = self.queue.get()
            self.generate_duplicate_map(galleries)

    def generate_duplicate_map(self, galleries):
        duplicate_map = {}
        for gallery in galleries:
            uuid = gallery.generate_uuid()
            if duplicate_map.get(uuid):
                duplicate_map[uuid].append(gallery)
            else:
                duplicate_map[uuid] = [gallery]
        self.signals.end.emit(duplicate_map)
