#!/usr/bin/env python3

import os
import sys
import json
import math
import time
import copy
import queue
import weakref
import scandir
import threading
from PyQt5 import QtCore
from typing import List, Dict
from collections import namedtuple
from difflib import SequenceMatcher
from sqlalchemy import select, update
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import PandaViewer
from .import Metadata
from .Utils import Utils
from .Logger import Logger
from .Search import Search
from .Config import Config
from PandaViewer import Exceptions, ExDatabase, UserDatabase
# from PandaViewer.Exceptions as Exceptions
# import PandaViewer.ExDatabase as ExDatabase
# import PandaViewer.UserDatabase as UserDatabase
from .RequestManager import RequestManager
from .Gallery import GenericGallery, FolderGallery, ZipGallery, RarGallery


class BaseThread(threading.Thread, Logger):
    dead = False
    THREAD_COUNT = 4

    def __init__(self, **kwargs):
        super().__init__()
        self.daemon = True
        self.queue = queue.Queue()


    def setup(self):
        self.basesignals = self.BaseSignals()
        self.basesignals.exception.connect(PandaViewer.app.thread_exception_handler)

    class BaseSignals(QtCore.QObject):
        exception = QtCore.pyqtSignal(object, tuple)

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
    running = False

    def setup(self):
        super().setup()
        self.signals = self.Signals()
        self.signals.end.connect(PandaViewer.app.find_galleries_done)
        self.signals.folder.connect(PandaViewer.app.set_scan_folder)
        self.existing_paths = [os.path.normpath(g.folder) for g in PandaViewer.app.galleries]

    class Signals(QtCore.QObject):
        end = QtCore.pyqtSignal(list)
        folder = QtCore.pyqtSignal(str)

    def _run(self):
        while True:
            self.running = False
            paths = self.queue.get()
            self.running = True
            if paths is None:
                self.load_all_galleries_from_db()
            else:
                self.find_galleries()

    def load_all_galleries_from_db(self):
        self.logger.info("Starting to load galleries from database.")
        candidates = []
        with UserDatabase.get_session(self) as session:
            db_gallery_list = Utils.convert_result(session.execute(select([UserDatabase.Gallery])).fetchall())
            db_metadata_list = Utils.convert_result(session.execute(select([UserDatabase.Metadata])).fetchall())
        metadata_map = {}
        for metadata in db_metadata_list:
            gallery_id = metadata["gallery_id"]
            metadata_json = json.loads(metadata["json"])
            metadata_json["id"] = metadata["id"]
            metadata_json["name"] = metadata["name"]
            if metadata_map.get(gallery_id):
                metadata_map[gallery_id].append(metadata_json)
            else:
                metadata_map[gallery_id] = [metadata_json]
        for gallery in db_gallery_list:
            gallery["path"] = Utils.normalize_path(gallery["path"])
            path_exists = os.path.exists(gallery["path"])
            if not path_exists and not gallery["dead"]:
                with UserDatabase.get_session(self) as session:
                    session.execute(
                        update(UserDatabase.Gallery).where(
                            UserDatabase.Gallery.id == gallery["id"]).values({"dead": True}))
                continue
            elif path_exists and gallery["dead"]:
                with UserDatabase.get_session(self) as session:
                    session.execute(
                        update(UserDatabase.Gallery).where(
                            UserDatabase.Gallery.id == gallery["id"]).values({"dead": False}))
                gallery["dead"] = False
            elif gallery["dead"]:
                continue
            gallery["metadata"] = {}
            for metadata in metadata_map.get(gallery["id"], []):
                name = metadata.pop("name")
                gallery["metadata"][name] = metadata
            candidate = {"path": gallery["path"],
                         "json": gallery,
                         "type": gallery["type"],
                         "loaded": True}
            candidates.append(candidate)
        self.logger.info("Done loading galleries from database.")
        self.create_from_dict(candidates)

    def find_galleries(self):
        candidates = []
        self.logger.info("Starting search for new galleries.")
        for path in Config.folders[:]:
            for base_folder, folders, files in scandir.walk(path):
                images = []
                self.signals.folder.emit(base_folder)
                for f in files:
                    ext = os.path.splitext(f)[-1].lower()
                    if ext in FolderGallery.IMAGE_EXTS:
                        images.append(os.path.join(base_folder, f))
                    elif ext in ZipGallery.ARCHIVE_EXTS + RarGallery.ARCHIVE_EXTS:
                        archive_file = os.path.join(base_folder, f)
                        if ext in ZipGallery.ARCHIVE_EXTS:
                            type = GenericGallery.TypeMap.ZipGallery
                        elif ext in RarGallery.ARCHIVE_EXTS:
                            type = GenericGallery.TypeMap.RarGallery
                        candidates.append({"path": archive_file,
                                           "type": type,})
                if images:
                    candidates.append({"path": base_folder,
                                       "type": GenericGallery.TypeMap.FolderGallery,
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
            candidate["path"] = Utils.normalize_path(candidate["path"])
            if candidate["path"] not in self.existing_paths:
                global_queue.put(candidate)
                self.existing_paths.append(candidate["path"])

        workers = self.generate_workers(global_queue, self.init_galleries)
        self.logger.debug("Starting gallery workers")
        for w in workers: w.thread.start()
        for w in workers: w.thread.join()
        self.logger.debug("Gallery workers done.")
        for worker in workers:
            galleries += worker.data.get_nowait()
            errors = worker.errors.get_nowait()
            dead_galleries += errors.dead_galleries
            invalid_files += errors.invalid_files
        if dead_galleries:
            with UserDatabase.get_session(self) as session:
                db_galleries = session.query(UserDatabase.Gallery).filter(UserDatabase.Gallery.id.in_(dead_galleries))
                for db_gallery in db_galleries:
                    db_gallery.dead = True
                    session.add(db_gallery)
        self.logger.debug("Done creating galleries from dicts.")
        self.signals.end.emit(galleries)
        if invalid_files:
            raise Exceptions.UnknownArchiveErrorMessage(invalid_files)
        gallery_validator_thread.queue.put(galleries)

    def init_galleries(self, global_queue, data_queue, error_queue):
        galleries = []
        invalid_files = []
        dead_galleries = []

        errors = namedtuple("errors", "invalid_files dead_galleries")
        while not global_queue.empty():
            try:
                candidate = global_queue.get_nowait()
                self.signals.folder.emit(candidate["path"])
                gallery_obj = GenericGallery.get_class_from_type(candidate["type"])(**candidate)
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
                dead_galleries.append(candidate["json"]["id"])
        data_queue.put(galleries)
        error_queue.put(errors(invalid_files, dead_galleries))

gallery_thread = GalleryThread()


class FolderWatcherThread(BaseThread):
    observer = None

    class Handler(FileSystemEventHandler):
        def on_any_event(self, event):
            event_processor_thread.queue.put([event])

    def setup(self):
        super().setup()
        self.observer = Observer()
        self.observer.start()
        self.set_folders()

    def _run(self):
        while True:
            self.queue.get()
            self.set_folders()

    def set_folders(self):
        self.observer.unschedule_all()
        for folder in Config.folders:
            self.observer.schedule(self.Handler(), folder, recursive=True)

folder_watcher_thread = FolderWatcherThread()


class EventProcessorThread(BaseThread):

    def _run(self):
        while True:
            self.process_events(self.queue.get())

    def process_events(self, events):
        for event in events:
            self.logger.debug(event)
            source = Utils.normalize_path(event.src_path)
            if event.event_type == "moved":
                destination = Utils.normalize_path(event.dest_path)
                if event.is_directory:
                    for gallery in PandaViewer.app.galleries:
                        if Utils.path_exists_under_directory(source, gallery.folder):
                            gallery.folder_moved(source, destination)
                else:
                    gallery = next((g for g in PandaViewer.app.galleries if g.file_belongs_to_gallery(source)),
                                   None)
                    if gallery:
                        source_folder = os.path.dirname(source)
                        dest_folder = os.path.dirname(destination)
                        if source_folder != dest_folder:
                            gallery.folder_moved(source_folder, dest_folder)
                        gallery.file_moved(destination)


event_processor_thread = EventProcessorThread()

class GalleryValidatorThread(BaseThread):

    def _run(self):
        while True:
            galleries = self.queue.get()
            time.sleep(5)
            for gallery in galleries:
                while gallery_thread.running:
                    time.sleep(1)
                try:
                    gallery.validate_db_uuid()
                except Exception:
                    self.logger.warning("Validator failed on %s" % gallery, exc_info=True)

gallery_validator_thread = GalleryValidatorThread()


class ImageThread(BaseThread):
    EMIT_FREQ = 5
    WAIT = 1
    BG_GALLERY_COUNT = 25
    MAX_BG_RUNS = 20
    bg_run_count = 0

    def setup(self):
        super().setup()
        self.signals = self.Signals()
        self.signals.end.connect(PandaViewer.app.image_thread_done)
        self.signals.gallery.connect(PandaViewer.app.set_ui_gallery)

    class Signals(QtCore.QObject):
        end = QtCore.pyqtSignal()
        gallery = QtCore.pyqtSignal(object)

    def _run(self):
        while True:
            try:
                galleries = self.queue.get(block=True, timeout=self.WAIT)
                self.generate_images(galleries)
            except queue.Empty:
                pass
            if self.bg_run_count < self.MAX_BG_RUNS:
                galleries = [g for g in PandaViewer.app.filter_galleries(PandaViewer.app.galleries)
                             if not g.thumbnail_verified]
                if galleries:
                    self.bg_run_count += 1
                    self.generate_images(galleries[:self.BG_GALLERY_COUNT], background=True)


    def generate_images(self, galleries, background=False):
        """
        @:type galleries list[Gallery]
        """
        global_queue = queue.Queue()
        for gallery in galleries:
            if not gallery.expired and not gallery.thumbnail_verified:
                global_queue.put(gallery)

        workers = self.generate_workers(global_queue, self.generate_image)
        for w in workers: w.thread.start()
        for w in workers: w.thread.join()
        if not background:
            self.signals.end.emit()
            thumbs = map(os.path.normcase,
                         [os.path.join(PandaViewer.app.THUMB_DIR, f)
                          for f in os.listdir(PandaViewer.app.THUMB_DIR)])
            with UserDatabase.get_session(self) as session:
                alive_hashes = list(map(lambda x: x[0], session.execute(
                    select([UserDatabase.Gallery.image_hash]).where(
                        UserDatabase.Gallery.dead == False))))
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

image_thread = ImageThread()

class SearchThread(BaseThread):

    class Signals(QtCore.QObject):
        gallery = QtCore.pyqtSignal(object, dict)

    def setup(self):
        super().setup()
        self.signals = self.Signals()
        self.signals.gallery.connect(PandaViewer.app.update_gallery_metadata)

    def _run(self):
        while True:
            galleries = self.queue.get()
            self.search(galleries)

    def search(self, galleries: List[GenericGallery]):
        search_galleries = [g for g in galleries if
                            g.metadata_manager.get_metadata_value(
                                Metadata.MetadataClassMap.gmetadata, "gid")
                            is None and g.expired is False]
        ex_search_thread.queue.put([g for g in galleries if g.force_metadata])
        if not ExDatabase.exists:
            ex_search_thread.queue.put(search_galleries)
            return
        self.logger.debug("Search galleries: %s" % [g.name for g in search_galleries])
        not_found_galleries = []
        with ExDatabase.get_session(self) as session:
            for gallery in search_galleries:
                exact_matches =  Utils.convert_result(session.execute(select([ExDatabase.Title]).where(
                    ExDatabase.Title.title.match('"%s"' % gallery.name))))
                if len(exact_matches) == 1:
                    self.update_gallery(gallery, exact_matches[0])
                elif len(exact_matches) > 1:
                    if not self.select_match(gallery, exact_matches):
                        not_found_galleries.append(gallery)
                else:
                    exploded_name = list(filter(None, Utils.removed_enclosed(gallery.name).split(" ")))
                    rough_name = " ".join(['"%s"' % w for w in exploded_name])
                    rough_matches = Utils.convert_result(session.execute(select([ExDatabase.Title]).where(
                        ExDatabase.Title.title.match(rough_name))))
                    if len(rough_matches) == 1:
                        self.update_gallery(gallery, rough_matches[0])
                    elif len(rough_matches) > 1 and not self.select_match(gallery, rough_matches):
                        not_found_galleries.append(gallery)
                    elif len(rough_matches) == 0:
                        not_found_galleries.append(gallery)
                if len(not_found_galleries) >= ex_search_thread.API_ENTRIES:
                    ex_search_thread.queue.put(not_found_galleries)
                    not_found_galleries = []
        if not_found_galleries:
            ex_search_thread.queue.put(not_found_galleries)

    def select_match(self, gallery: GenericGallery, matches: List[Dict]) -> bool:
        matches = [m for m in matches if SequenceMatcher(None, gallery.name, m["title"]).ratio() >= .6]
        file_size = gallery.get_file_size()
        file_size_matches = [m for m in matches if int(m["filesize"]) == file_size]
        if len(file_size_matches) >= 1:
            self.update_gallery(gallery, file_size_matches[0])
            return True
        size_percent_diff = .1 if isinstance(gallery, FolderGallery) else .15
        max_file_size = math.floor(file_size * (1 + size_percent_diff))
        min_file_size = math.floor(file_size * (1 - size_percent_diff))
        rough_file_size_matches = [m for m in matches if min_file_size <= int(m["filesize"]) <= max_file_size]
        if len(rough_file_size_matches) == 1:
            self.update_gallery(gallery, rough_file_size_matches[0])
            return True
        file_count_matches = [m for m in matches if int(m["filecount"]) == gallery.file_count]
        if len(file_count_matches) >= 1:
            self.update_gallery(gallery, file_count_matches[0])
            return True
        max_file_count = math.floor(gallery.file_count * (1.1))
        min_file_count = math.floor(gallery.file_count * (.9))
        rough_file_count_matches = [m for m in matches if min_file_count <= int(m["filecount"]) <= max_file_count]
        if len(rough_file_count_matches) == 1:
            self.update_gallery(gallery, rough_file_count_matches[0])
            return True
        rough_intersection = [m for m in rough_file_size_matches if m in rough_file_count_matches]
        if len(rough_intersection) >= 1:
            self.update_gallery(gallery, rough_intersection[0])
            return True
        return False

    def update_gallery(self, gallery: GenericGallery, match: Dict):
        with ExDatabase.get_session(self) as session:
            result = dict(session.execute(select([ExDatabase.Gallery]).where(
                ExDatabase.Gallery.id == match["id"])).fetchone())
        result.pop("id")
        result["tags"] = json.loads(result["tags"])
        self.signals.gallery.emit(gallery, {"gmetadata": result})

search_thread = SearchThread()


class ExSearchThread(BaseThread):
    API_URL = "http://exhentai.org/api.php"
    BASE_REQUEST = {"method": "gdata", "gidlist": [], "namespace": 1}
    API_MAX_ENTRIES = 25
    API_ENTRIES = 5

    def setup(self):
        super().setup()
        self.signals = self.Signals()
        self.signals.end.connect(PandaViewer.app.get_metadata_done)
        self.signals.gallery.connect(PandaViewer.app.update_gallery_metadata)
        self.signals.current_gallery.connect(PandaViewer.app.set_current_metadata_gallery)

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

    def search(self, galleries: List[GenericGallery]):
        search_galleries = [g for g in galleries if g.valid_for_ex_search()]
        self.logger.debug("Search galleries: %s" % [g.name for g in search_galleries])
        need_metadata_galleries = []
        for gallery in search_galleries:
            if gallery.expired:
                continue
            self.signals.current_gallery.emit(gallery)
            try:
                search_results = Search.search_by_gallery(gallery)
                if search_results:
                    gallery.process_search_result(search_results)
                    need_metadata_galleries.append(gallery)
                if len(need_metadata_galleries) == self.API_ENTRIES:
                    self.get_metadata(need_metadata_galleries)
                    need_metadata_galleries = []
            except Exceptions.CustomBaseException:
                raise
            except Exception:
                self.logger.error("%s failed to search" % gallery, exc_info=True)
        if need_metadata_galleries:
            self.get_metadata(need_metadata_galleries)
        force_galleries = [g for g in galleries if g.valid_for_force_ex_search()]
        force_gallery_list = [force_galleries[i:i + self.API_MAX_ENTRIES]
                                  for i in range(0, len(galleries), self.API_MAX_ENTRIES)]
        for gallery_list in force_gallery_list: self.get_metadata(gallery_list)

    def get_metadata(self, galleries: List[GenericGallery]):
        assert len(galleries) <= self.API_MAX_ENTRIES
        payload = copy.deepcopy(self.BASE_REQUEST)
        gid_list = [gallery.ex_id for gallery in galleries]
        if not gid_list:
            return
        payload["gidlist"] = gid_list
        response = RequestManager.post(self.API_URL, payload=payload)
        for gallery in galleries:
            if gallery.expired:
                continue
            for metadata in response["gmetadata"]:
                id = (metadata["gid"], metadata["token"])
                if id == gallery.ex_id:
                    self.signals.gallery.emit(gallery, {"gmetadata": metadata})
                    break
ex_search_thread = ExSearchThread()


class DuplicateFinderThread(BaseThread):

    class Signals(QtCore.QObject):
        end = QtCore.pyqtSignal()

    def setup(self):
        super().setup()
        self.signals = self.Signals()
        self.signals.end.connect(PandaViewer.app.duplicate_thread_done)

    def _run(self):
        while True:
            galleries = self.queue.get()
            self.generate_duplicate_map(galleries)

    def generate_duplicate_map(self, galleries: List[GenericGallery]):
        duplicate_map = {}
        for gallery in galleries:
            uuid = gallery.generate_uuid()
            if duplicate_map.get(uuid):
                duplicate_map[uuid].append(gallery)
            else:
                duplicate_map[uuid] = [gallery]
        Utils.reduce_gallery_duplicates(duplicate_map)
        self.signals.end.emit()

duplicate_thread = DuplicateFinderThread()

DAEMON_THREADS = [gallery_thread, image_thread, ex_search_thread, duplicate_thread,
                  gallery_validator_thread, search_thread,]# folder_watcher_thread, event_processor_thread]

def setup():
    for thread in DAEMON_THREADS:
        thread.setup()
        thread.start()

