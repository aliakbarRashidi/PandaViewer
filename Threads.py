#!/usr/bin/env python

from PyQt5 import QtCore
from Logger import Logger
import threading
import queue
import weakref
import copy
from collections import namedtuple
from itertools import cycle
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
from Utils import Utils
from profilehooks import profile


class BaseThread(threading.Thread, Logger):
    dead = False
    THREAD_COUNT = 10

    def __init__(self, parent, **kwargs):
        super(BaseThread, self).__init__()
        self.name = self.__class__.__name__
        self.daemon = True
        self.queue = queue.Queue()
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

    @classmethod
    def generate_workers(cls, global_queue, target):
        worker = namedtuple("worker", "thread data errors")
        workers = []
        for _ in range(0, cls.THREAD_COUNT):
            data_queue = queue.Queue()
            error_queue = queue.Queue()
            thread = threading.Thread(target=target, args=(global_queue, data_queue, error_queue))
            workers.append(worker(thread, data_queue, error_queue))
        return workers

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
                            self.queue.get_nowait()
                    except queue.Empty:
                        pass


class GalleryThread(BaseThread):

    def __init__(self, parent, **kwargs):
        super(GalleryThread, self).__init__(parent)
        self.signals = self.Signals()
        self.signals.end.connect(self.parent.find_galleries_done)
        self.existing_paths = [os.path.normpath(g.path) for g in self.parent.galleries]
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

    def load_from_db(self):
        self.logger.info("Starting to load galleries from database.")
        candidates = []
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
                             "type": gallery["type"],
                             "loaded": True}
                candidates.append(candidate)
        self.logger.info("Done loading galleries from database.")
        self.create_from_dict(candidates)
        self.loaded = True

    def find_galleries(self):
        candidates = []
        self.logger.info("Starting search for new galleries.")
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
                            type = Gallery.TypeMap.ZipGallery
                        elif ext in RarGallery.ARCHIVE_EXTS:
                            type = Gallery.TypeMap.RarGallery
                        candidates.append({"path": archive_file,
                                           "type": type,
                                           "parent": self.parent})
                if images:
                    candidates.append({"path": base_folder,
                                       "parent": self.parent,
                                       "type": Gallery.TypeMap.FolderGallery,
                                       "files": sorted(images, key=lambda f: f.lower())})
        self.logger.info("Done with search for new galleries.")
        self.create_from_dict(candidates)

    def create_from_dict(self, candidates):
        self.logger.info("Starting gallery creation from dicts.")
        galleries = []
        dead_galleries = []
        invalid_files = []
        global_queue = queue.Queue()
        for candidate in candidates:
            candidate["path"] = os.path.normpath(candidate["path"])
            if candidate["path"] not in self.existing_paths:
                global_queue.put(candidate)
                self.existing_paths.append(candidate["path"])

        workers = self.generate_workers(global_queue, self.init_galleries)
        self.logger.info("Starting gallery workers")
        [w.thread.start() for w in workers]
        [w.thread.join() for w in workers]
        self.logger.info("Gallery workers done.")
        for worker in workers:
            galleries += worker.data.get_nowait()
            errors = worker.errors.get_nowait()
            dead_galleries += errors.dead_galleries
            invalid_files += errors.invalid_files
        if dead_galleries:
            with Database.get_session(self) as session:
                db_galleries = session.query(Database.Gallery).filter(Database.Gallery.id.in_(dead_galleries))
                for db_gallery in db_galleries:
                    db_gallery.dead = True
                    session.add(db_gallery)
        self.logger.debug("Done creating galleries from dicts.")
        self.signals.end.emit(galleries)
        if invalid_files:
            raise Exceptions.UnknownArchiveErrorMessage(invalid_files)

    def init_galleries(self, global_queue, data_queue, error_queue):
        galleries = []
        invalid_files = []
        dead_galleries = []

        errors = namedtuple("errors", "invalid_files dead_galleries")
        while not global_queue.empty():
            try:
                candidate = global_queue.get_nowait()
                gallery_obj = Gallery.get_class_from_type(candidate["type"])(**candidate)
                galleries.append(gallery_obj)
            except queue.Empty:
                break
            except Exceptions.UnknownArchiveError:
                gallery_obj = None
                invalid_files.append(candidate["path"])
            except AssertionError:
                gallery_obj = None
            except Exception:
                gallery_obj = None
                self.logger.error("%s gallery got unhandled exception" % candidate, exc_info=True)
            if candidate.get("loaded") and not gallery_obj:
                dead_galleries.append(candidate["id"])
        data_queue.put(galleries)
        error_queue.put(errors(invalid_files, dead_galleries))




class ImageThread(BaseThread):
    EMIT_FREQ = 5

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

    def generate_images(self, galleries):
        """
        @:type galleries list[Gallery]
        """

        global_queue = queue.Queue()
        for gallery in galleries:
            if not gallery.expired:
                global_queue.put(gallery)

        workers = self.generate_workers(global_queue, self.generate_image)
        [w.thread.start() for w in workers]
        [w.thread.join() for w in workers]
        self.signals.end.emit()

        thumbs = map(os.path.normcase,
                     [os.path.join(self.parent.THUMB_DIR, f)
                      for f in os.listdir(self.parent.THUMB_DIR)])
        with Database.get_session(self) as session:
            alive_hashes = list(map(lambda x: x[0], session.execute(
                select([Database.Gallery.image_hash]).where(
                    Database.Gallery.dead == False))))
            for thumb in thumbs:
                file_hash = os.path.splitext(os.path.basename(thumb))[0]
                if file_hash not in alive_hashes:
                    try:
                        os.remove(thumb)
                    except OSError:
                        pass

    def generate_image(self, global_queue, *args):
        while not global_queue.empty():
            gallery = None
            try:
                gallery = global_queue.get_nowait()
                gallery.load_thumbnail()
            except queue.Empty:
                break
            except Exception:
                self.logger.error("%s failed to get image" % gallery, exc_info=True)


class SearchThread(BaseThread):
    API_URL = "http://exhentai.org/api.php"
    BASE_REQUEST = {"method": "gdata", "gidlist": [], "namespace": 1}
    API_MAX_ENTRIES = 25
    API_ENTRIES = 3

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
        """
        :type galleries list[Gallery]
        :return: None
        """
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
        force_galleries = [g for g in galleries if g.force_metadata and g.gid]
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

    class Signals(QtCore.QObject):
        end = QtCore.pyqtSignal()

    def __init__(self, parent):
        super(DuplicateFinderThread, self).__init__(parent)
        self.signals = self.Signals()
        self.signals.end.connect(self.parent.duplicate_thread_done)

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
        Utils.reduce_gallery_duplicates(duplicate_map)
        self.signals.end.emit()
