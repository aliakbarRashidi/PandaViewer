import os
import re
import gc
from enum import Enum
from random import randint
from threading import RLock
from typing import List, Dict, Tuple
from bisect import insort_left
from operator import attrgetter
from PyQt5 import QtCore, QtQml, QtQuick, QtNetwork, QtWidgets, QtGui
from . import threads, exceptions, user_database, metadata
from .utils import Utils
from .logger import Logger
from .config import Config
from .gallery import GenericGallery


class Program(QtWidgets.QApplication, Logger):
    PAGE_SIZE = 100
    BUG_PAGE = "https://github.com/seanegoodwin/pandaviewer/issues"
    THUMB_DIR = Utils.convert_from_relative_lsv_path("thumbs")
    QML_PATH = Utils.convert_from_relative_path("qml/")
    MAX_TAG_RETURN_COUNT = 5
    gallery_lock = RLock()

    class SortMethodMap(Enum):
        NameSort = "sort_name"
        ReadCountSort = "read_count"
        LastReadSort = "last_read"
        RatingSort = "sort_rating"
        DateAddedSort = "time_added"
        FilePathSort = "sort_path"

    def __init__(self, args):
        self.addLibraryPath(Utils.convert_from_relative_path())
        super().__init__(args)
        self.setOrganizationName("PV")
        self.setOrganizationDomain(self.BUG_PAGE)
        self.setApplicationName("PandaViewer")
        self.tags = []  # type: List[str]
        self.pages = [[]]  # type: List[List[GenericGallery]]
        self.galleries = []  # type: List[GenericGallery]
        self.version = "0.1"  # Most likely used for db changes only
        self.page_number = 0
        self.search_text = ""

    def setup(self):
        if not os.path.exists(self.THUMB_DIR):
            os.makedirs(self.THUMB_DIR)
        user_database.setup()

        self.qml_engine = QtQml.QQmlApplicationEngine()
        self.qml_engine.addImportPath(self.QML_PATH)
        # self.qml_engine.addPluginPath(self.QML_PATH)
        self.setAttribute(QtCore.Qt.AA_UseOpenGLES, True)
        self.qml_engine.load(os.path.join(self.QML_PATH, "main.qml"))
        self.app_window = self.qml_engine.rootObjects()[0]
        self.app_window.updateGalleryRating.connect(self.update_gallery_rating)
        self.app_window.askForTags.connect(self.get_tags_from_search)
        self.app_window.saveSettings.connect(self.update_config)
        self.app_window.setSortMethod.connect(self.set_sorting)
        self.app_window.setSearchText.connect(self.update_search)
        self.app_window.pageChange.connect(self.switch_page)
        self.app_window.scanGalleries.connect(self.find_galleries)
        self.app_window.openGallery.connect(self.open_gallery)
        self.app_window.openGalleryFolder.connect(self.open_gallery_folder)
        self.app_window.metadataSearch.connect(self.get_metadata)
        self.app_window.removeGallery.connect(self.remove_gallery_by_uuid)
        self.app_window.openOnEx.connect(self.open_on_ex)
        self.app_window.saveGallery.connect(self.save_gallery_customization)
        self.app_window.searchForDuplicates.connect(self.remove_duplicates)
        self.app_window.closedUI.connect(self.close)
        self.app_window.getDetailedGallery.connect(self.get_detailed_gallery)
        self.app_window.getGalleryImageFolder.connect(self.get_gallery_image_folder)
        self.app_window.setGalleryImage.connect(self.set_gallery_image)
        self.app_window.setUISort.emit(Config.sort_type, 1 if Config.sort_mode_reversed else 0)
        self.completer_line = QtWidgets.QLineEdit()
        self.completer_line.hide()
        self.setup_completer()
        self.setWindowIcon(QtGui.QIcon(Utils.convert_from_relative_path("icon.ico")))
        self.set_ui_config()
        self.app_window.show()

    def setup_completer(self):
        self.completer = QtWidgets.QCompleter(self.tags)
        self.completer.setModelSorting(self.completer.CaseInsensitivelySortedModel)
        self.completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.completer_line.setCompleter(self.completer)

    def set_sorting(self, sort_type, reversed):
        Config.sort_type = sort_type
        Config.sort_mode_reversed = reversed
        Config.save()
        self.sort()
        self.search()

    def update_search(self, search_text: str):
        self.search_text = search_text
        self.search()

    def set_ui_gallery(self, gallery: GenericGallery):
        self.app_window.setGallery.emit(gallery.ui_uuid, gallery.get_json())

    def remove_gallery_by_uuid(self, uuid: str):
        gallery = self.get_gallery_by_ui_uuid(uuid)
        gallery.mark_for_deletion()
        self.setup_tags()
        self.remove_gallery_and_recalculate_pages(gallery)

    def get_detailed_gallery(self, uuid: str):
        self.app_window.openDetailedGallery.emit(self.get_gallery_by_ui_uuid(uuid).get_detailed_json())

    def get_tags_from_search(self, search: str):
        self.completer_line.setText(search)
        self.completer.setCompletionPrefix(search)
        tags = []
        for i in range(self.completer.completionCount()):
            self.completer.setCurrentRow(i)
            tags.append(self.completer.currentCompletion())
        tags.sort(key=len)
        self.app_window.setTags(tags[:self.MAX_TAG_RETURN_COUNT])

    def get_gallery_by_ui_uuid(self, uuid: str) -> GenericGallery:
        assert uuid
        return next(g for g in self.current_page if g.ui_uuid == uuid)

    def update_gallery_rating(self, uuid: str, rating: str):
        self.get_gallery_by_ui_uuid(uuid).set_rating(rating)

    def get_gallery_image_folder(self, uuid: str):
        self.app_window.setGalleryImageFolder.emit(uuid,
                                                   self.get_gallery_by_ui_uuid(uuid).image_folder)

    def set_gallery_image(self, uuid, image_path):
        self.get_gallery_by_ui_uuid(uuid).set_thumbnail_source(image_path)

    def open_gallery(self, uuid, index):
        self.get_gallery_by_ui_uuid(uuid).open(index)

    def open_random_gallery(self):
        galleries = self.filter_galleries(self.galleries)
        index = randint(0, len(galleries) - 1)
        galleries[index].open()

    def open_gallery_folder(self, uuid):
        self.get_gallery_by_ui_uuid(uuid).open_folder()

    def open_on_ex(self, uuid):
        self.get_gallery_by_ui_uuid(uuid).open_on_ex()

    def save_gallery_customization(self, uuid, gallery):
        self.get_gallery_by_ui_uuid(uuid).save_customization(gallery)

    def exec_(self):
        self.find_galleries(initial=True)
        return super().exec_()

    @property
    def current_page(self) -> List[GenericGallery]:
        return self.pages[self.page_number]

    @property
    def page_count(self) -> int:
        return len(self.pages)

    def set_ui_config(self):
        self.app_window.setSettings(Config.get_ui_config())

    def update_config(self, ui_config):
        if Config.update_from_ui_config(ui_config):
            self.set_auto_metadata_collection()
        self.setup_tags()
        self.search()

    def set_scan_folder(self, folder):
        self.app_window.setScanFolder(folder)

    def set_auto_metadata_collection(self, galleries: List[GenericGallery] = None):
        galleries = galleries or self.galleries
        for gallery in self.filter_galleries(galleries):
            metadata_changed = False
            matching_dir = Utils.get_parent_folder(Config.folders, gallery.folder)
            assert matching_dir
            auto_collection = Config.folder_options.get(matching_dir, {}).get(Config.AUTO_METADATA_KEY, True)
            for metadata_name in metadata.MetadataClassMap:
                metadata_entry = gallery.metadata_manager.get_metadata(metadata_name)
                if hasattr(metadata_entry, "auto_collection") and metadata_entry.auto_collection != auto_collection:
                    metadata_changed = True
                    metadata_entry.auto_collection = auto_collection
            if metadata_changed:
                gallery.save_metadata(update_ui=False)

    def process_search(self, search_text: str) -> (List[str], [List[str], str]):
        search_text = search_text.lower()
        quote_regex = re.compile(r"(-)?\"(.*?)\"")
        filter_regex = re.compile(r"(?:^|\s)\-(.*?)(?=(?:$|\ ))")
        rating_method = re.search(r"rating:(\S*)", search_text)
        if rating_method:
            search_text = re.sub("rating:\S*", "", search_text)
            rating_method = rating_method.groups()[0]
            if rating_method:
                if rating_method[0] == "=" and rating_method[1] != "=":
                    rating_method = "=" + rating_method
                try:
                    eval("0.0" + rating_method)
                except:
                    raise exceptions.InvalidRatingSearch
            else:
                raise exceptions.InvalidRatingSearch
        quoted_words = re.findall(quote_regex, search_text)
        quoted_words = " ".join(map(lambda x: "".join(x).replace(" ", "_"), quoted_words))
        search_text = re.sub(quote_regex, "", search_text) + quoted_words
        filter_words = re.findall(filter_regex, search_text)
        words = re.sub(filter_regex, "", search_text).split()
        self.logger.info("Search words: %s" % words)
        self.logger.info("Filter words: %s" % filter_words)
        self.logger.info("Rating function: %s" % rating_method)
        return words, filter_words, rating_method

    def search(self):
        self.logger.info("Search_text: %s" % self.search_text)
        if self.search_text:
            words, filters, rating_method = self.process_search(self.search_text)
            galleries = []
            with self.gallery_lock:
                for gallery in self.filter_galleries(self.galleries):
                    if gallery.expired:
                        continue
                    title = gallery.clean_name.lower().split()
                    rating = gallery.metadata_manager.get_value("rating")
                    tags = [t.replace(" ", "_").lower() for t in gallery.metadata_manager.all_tags]
                    if rating_method and (not rating or not eval(str(rating) + rating_method)):
                        continue
                    if any(self.in_search(tags, title, w) for w in filters):
                        continue
                    if all(self.in_search(tags, title, w) for w in words) or len(words) == 0:
                        galleries.append(gallery)
            self.app_window.setNoSearchResults.emit(not bool(galleries))
            self.setup_pages(galleries)
            self.show_page()
        else:
            self.app_window.setNoSearchResults.emit(False)
            self.setup_pages()
            self.show_page()

    @staticmethod
    def in_search(tags: List[str], title: str, input_tag: str) -> bool:
        input_tag, namespace = Utils.separate_tag(input_tag)
        for title_word in title:
            if input_tag in title_word:
                return True
        for tag in tags:
            tag, tag_namespace = Utils.separate_tag(tag)
            if input_tag in tag and (namespace is None or tag_namespace == namespace):
                return True
        return False

    def setup_tags(self):
        tags = []
        # tag_count_map = {}
        for gallery in self.filter_galleries(self.galleries):
            new_tags = list(set(map(lambda x: x.replace(" ", "_").lower(), gallery.metadata_manager.all_tags)))
            # for tag in new_tags:
            #     tag_count_map[tag] = tag_count_map.get(tag, 0) + 1
            tags += new_tags
        self.tags = list(set(tags))
        for tag in self.tags[:]:
            raw_tag, namespace = Utils.separate_tag(tag)
            if namespace:
                self.tags.append(raw_tag)
        self.tags += list(map(lambda x: "-" + x, self.tags))
        self.tags = list(set(self.tags))
        self.tags.sort()
        self.setup_completer()

    def find_galleries(self, initial: bool = False):
        self.app_window.setScanningMode(True)
        self.logger.debug("Sending start signal to gallery thread")
        folders = Config.folders[:] if not initial else None
        threads.gallery_thread.queue.put(folders)

    def find_galleries_done(self, galleries: List[GenericGallery]):
        self.app_window.setScanningMode(False)
        self.set_auto_metadata_collection(galleries)
        with self.gallery_lock:
            self.galleries += galleries
        self.logger.debug("Gallery thread done")
        self.setup_tags()
        self.sort()
        self.search()

    def send_page(self, reset_scroll=True):
        index_list = (i for i in range(0, self.PAGE_SIZE))
        for gallery in self.current_page:
            self.app_window.setUIGallery.emit(next(index_list), gallery.get_json(), reset_scroll)
        for i in list(index_list)[::-1]: self.app_window.removeUIGallery.emit(i, 1)
        # index_list = list(index_list)
        # if index_list:
        #     self.app_window.removeUIGallery.emit(index_list[0], len(index_list))
        self.garbage_collect()
        threads.image_thread.bg_run_count = 0

    def garbage_collect(self):
        return
        self.qml_engine.clearComponentCache()
        gc.collect()
        self.app_window.garbageCollect()

    def show_page(self, reset_scroll=True):
        need_images = [g for g in self.current_page if not g.thumbnail_verified]
        if need_images:
            self.generate_images(need_images)
        else:
            self.send_page(reset_scroll)

    def hide_page(self):
        self.app_window.clearGalleries.emit()

    def generate_images(self, galleries: List[GenericGallery]):
        self.app_window.setScanningMode(True)
        threads.image_thread.queue.put(galleries)

    def image_thread_done(self):
        self.app_window.setScanningMode(False)
        self.logger.debug("Image thread done.")
        self.send_page()

    def get_metadata(self, uuid: str):
        try:
            uuid = int(uuid)
            galleries = [g for g in self.filter_galleries(self.galleries)
                         if g.metadata_manager.metadata_collection_enabled()]
            if uuid == -1:
                for gallery in galleries:
                    gallery.force_metadata = True
        except ValueError:
            gallery = self.get_gallery_by_ui_uuid(uuid)
            gallery.force_metadata = True
            galleries = [gallery]
        self.logger.debug("Starting metadata thread")
        self.app_window.setSearchMode(True)
        threads.search_thread.queue.put(galleries)

    def set_current_metadata_gallery(self, gallery):
        self.app_window.setCurrentMetadataGallery(gallery.title)

    def update_gallery_metadata(self, gallery: GenericGallery, metadata: dict):
        gallery.update_metadata(metadata)
        gallery.save_metadata()

    def get_metadata_done(self):
        self.app_window.setSearchMode(False)
        self.logger.debug("Metadata thread done.")
        self.setup_tags()

    def remove_duplicates(self):
        self.app_window.setScanningMode(True)
        threads.duplicate_thread.queue.put(self.filter_galleries(self.galleries))

    def duplicate_thread_done(self):
        self.app_window.setScanningMode(False)
        self.setup_tags()
        self.sort()

    def close(self):
        with self.gallery_lock:
            for g in self.galleries: g.__del__()
        self.quit()

    def sort(self):
        key = attrgetter([t.value for t in self.SortMethodMap][Config.sort_type])
        assert key
        with self.gallery_lock:
            self.galleries.sort(key=key, reverse=Config.sort_mode_reversed)

    def switch_page(self, page_num: int):
        self.page_number = int(page_num) - 1
        self.show_page()
        self.app_window.setPage(self.page_number + 1)

    def filter_galleries(self, galleries: List[GenericGallery]) -> List[GenericGallery]:
        return_galleries = []
        for gallery in galleries:
            if gallery.expired:
                continue
            if not any(Utils.path_exists_under_directory(d, gallery.folder) for d in Config.folders):
                continue
            return_galleries.append(gallery)
        return return_galleries

    def setup_pages(self, galleries: List[GenericGallery] = None):
        if galleries is None:  # Need to do it this way because passing in galleries of [] would cause problems
            galleries = self.galleries
        galleries = self.filter_galleries(galleries)
        self.pages = [galleries[i:i + self.PAGE_SIZE] for i in range(0, len(galleries), self.PAGE_SIZE)] or [[]]
        self.app_window.setPageCount(self.page_count)
        self.page_number = 0
        self.app_window.setPage(self.page_number + 1)

    def remove_gallery_and_recalculate_pages(self, gallery: GenericGallery):
        assert gallery in self.galleries
        working_page = None
        with self.gallery_lock:
            self.galleries.remove(gallery)
            for i in range(0, self.page_count):
                if gallery in self.pages[i]:
                    self.pages[i].remove(gallery)
                    working_page = i
                    break
            assert working_page is not None
            initial_page_is_displayed = working_page == self.page_number
            while working_page < self.page_count - 1:
                self.pages[working_page].append(self.pages[working_page + 1].pop(0))
                working_page += 1
            self.pages = [p for p in self.pages if p]
            if self.page_number >= self.page_count:
                self.switch_page(self.page_count)
            elif initial_page_is_displayed:
                self.show_page(reset_scroll=False)

    def thread_exception_handler(self, thread, exception):
        self.exception_hook(*exception)

    def exception_hook(self, extype, exvalue, extraceback):
        fatal = True  # Default to true for unhandled exceptions
        if issubclass(extype, exceptions.CustomBaseException):
            fatal = exvalue.fatal
            message = exvalue.msg
        else:
            message = "Sorry, PandaViewer got an unhandled %s exception and must close.\nPlease feel free to submit a bug report" % extype
            self.logger.error("Got unhandled exception", exc_info=(extype, exvalue, extraceback))
        self.app_window.setException(message, fatal)
