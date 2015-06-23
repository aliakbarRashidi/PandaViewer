#!/usr/bin/env python2

from PyQt5 import QtGui
from PyQt5 import QtWidgets
from PyQt5 import QtQml
from PyQt5 import QtQuick
from PyQt5 import QtNetwork
from PyQt5 import QtCore
from time import strftime
from Logger import Logger
from RequestManager import RequestManager
from operator import attrgetter
import sys
import os
import re
import json
import logging
import Threads
import Exceptions
import Database



def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller
    http://stackoverflow.com/questions/7674790/bundling-data-files-with-pyinstaller-onefile
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class Program(QtWidgets.QApplication, Logger):
    PAGE_SIZE = 100
    BUG_PAGE = "https://github.com/seanegoodwin/pandaviewer/issues"
    CONFIG_DIR = os.path.expanduser("~/.lsv")
    THUMB_DIR = os.path.join(CONFIG_DIR, "thumbs")
    DEFAULT_CONFIG = {"dirs": [], "cookies": {"ipb_member_id": "",
                                              "ipb_pass_hash": ""}}
    QML_PATH = resource_path("qml/")
    MAX_TAG_RETURN_COUNT = 3

    class SortMap(object):
        NameSort = 0
        ReadCountSort = 1
        LastReadSort = 2
        RatingSort = 3
        DateAddedSort = 4

    def __init__(self, args):
        super(Program, self).__init__(args)

        self.tags = []
        self.threads = {}
        self.config = {}
        self.pages = [[]]
        self.galleries = []
        self.version = "0.1"  # Most likely used for db changes only
        self.page_number = 0
        self.search_text = ""

        self.addLibraryPath(self.QML_PATH)
        self.qml_engine = QtQml.QQmlApplicationEngine()
        self.qml_engine.addImportPath(self.QML_PATH)
        self.qml_engine.addPluginPath(self.QML_PATH)
        self.qml_engine.load(os.path.join(self.QML_PATH, "main.qml"))
        self.app_window = self.qml_engine.rootObjects()[0]
        self.app_window.show()

        self.app_window.updateGalleryRating.connect(self.update_gallery_rating)
        self.app_window.askForTags.connect(self.get_tags_from_search)
        self.app_window.saveSettings.connect(self.update_config)
        self.app_window.askForSettings.connect(self.send_config)
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
        self.app_window.searchForDuplicates.connect(self.generate_duplicate_map)

        self.completer_line = QtWidgets.QLineEdit()
        self.completer_line.hide()
        self.setup_completer()
        self.sort_type = self.SortMap.NameSort
        self.sort_mode_reversed = False
        if not os.path.exists(self.THUMB_DIR):
            os.makedirs(self.THUMB_DIR)
        Database.setup()
        self.load_config()
        self.setWindowIcon(QtGui.QIcon("icon.ico"))
        self.setup_threads()

    def setup_completer(self):
        self.completer = QtWidgets.QCompleter(self.tags)
        self.completer.setModelSorting(self.completer.CaseInsensitivelySortedModel)
        self.completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.completer_line.setCompleter(self.completer)

    def set_sorting(self, sort_type, reversed):
        self.sort_type = sort_type
        self.sort_mode_reversed = reversed
        self.sort()

    def update_search(self, search_text):
        self.search_text = search_text
        self.search()

    def set_ui_gallery(self, gallery):
        self.app_window.setUiGallery.emit(gallery.ui_uuid, gallery.get_json())

    def remove_gallery_by_uuid(self, uuid):
        gallery = self.get_gallery_by_uuid(uuid)
        gallery.mark_for_deletion()
        self.setup_tags()

    def get_tags_from_search(self, search):
        self.completer_line.setText(search)
        self.completer.setCompletionPrefix(search)
        tags = []
        for i in range(self.completer.completionCount()):
            self.completer.setCurrentRow(i)
            tags.append(self.completer.currentCompletion())
        tags.sort(key=len)
        self.app_window.setTags(tags[:self.MAX_TAG_RETURN_COUNT])

    def get_gallery_by_uuid(self, uuid):
        assert uuid
        return next(g for g in self.current_page if g.ui_uuid == uuid)

    def update_gallery_rating(self, uuid, rating):
        gallery = self.get_gallery_by_uuid(uuid)
        gallery.set_rating(rating)

    def open_gallery(self, uuid):
        gallery = self.get_gallery_by_uuid(uuid)
        gallery.open_file()

    def open_gallery_folder(self, uuid):
        gallery = self.get_gallery_by_uuid(uuid)
        gallery.open_folder()

    def open_on_ex(self, uuid):
        gallery = self.get_gallery_by_uuid(uuid)
        gallery.open_on_ex()

    def save_gallery_customization(self, uuid, gallery):
        self.get_gallery_by_uuid(uuid).save_customization(gallery)

    def exec_(self):
        self.find_galleries(initial=True)
        return super(Program, self).exec_()

    @property
    def current_page(self):
        return self.pages[self.page_number]

    @property
    def page_count(self):
        return len(self.pages)

    @property
    def member_id(self):
        return self.config["cookies"]["ipb_member_id"]

    @member_id.setter
    def member_id(self, val):
        self.config["cookies"]["ipb_member_id"] = val

    @property
    def pass_hash(self):
        return self.config["cookies"]["ipb_pass_hash"]

    @pass_hash.setter
    def pass_hash(self, val):
        self.config["cookies"]["ipb_pass_hash"] = val

    @property
    def dirs(self):
        return self.config["dirs"]

    @dirs.setter
    def dirs(self, val):
        self.config["dirs"] = val

    @property
    def cookies(self):
        return self.config["cookies"]

    def load_config(self):
        self.logger.debug("Loading config from db.")
        with Database.get_session(self) as session:
            db_config = session.query(Database.Config)
            if db_config.count() == 0:
                self.config = self.DEFAULT_CONFIG
                new_config = Database.Config()
                new_config.json = json.dumps(self.config)
                new_config.version = self.version
                session.add(new_config)
                session.commit()
            else:
                assert db_config.count() == 1
                db_config = db_config[0]
                self.config = json.loads(db_config.json)
                self.version = db_config.version
        RequestManager.COOKIES = self.config["cookies"]

    def send_config(self):
        self.app_window.setSettings.emit({"exUserID": self.member_id,
                                          "exPassHash": self.pass_hash,
                                          "folders": self.dirs})

    def save_config(self):
        self.logger.debug("Save config to db.")
        with Database.get_session(self) as session:
            db_config = session.query(Database.Config)[0]
            db_config.json = unicode(json.dumps(self.config, ensure_ascii=False).encode("utf8"))
            db_config.version = self.version
            session.add(db_config)
        self.sort()

    def update_config(self, config):
        self.logger.info("Updating config.")
        self.dirs = config.property("folders").toVariant()
        self.member_id = config.property("exUserID").toString()
        self.pass_hash = config.property("exPassHash").toString()
        RequestManager.COOKIES = self.cookies
        self.save_config()

    def process_search(self, search_text):
        search_text = search_text.lower()
        rating = re.search(r"rating:(\S*)", search_text)
        if rating:
            search_text = re.sub("rating:\S*", "", search_text)
            rating = rating.groups()[0]
            if rating[0] == "=" and rating[1] != "=":
                rating = "=" + rating
            try:
                eval("0.0" + rating)
            except:
                raise Exceptions.InvalidRatingSearch()
        filter_words = re.findall(r"[\"]?[\-][\"]?([\w]*)[\"]?",
                                  search_text)
        search_text = re.sub(r"[\"]?[\-][\"]?([\w]*)[\"]?", "",
                             search_text)
        filter_words = [w.replace(" ", "_") for w in filter_words]
        quoted_words = re.findall(r"\"([^-].+?)\"", search_text)
        quoted_words = [w.replace(" ", "_") for w in quoted_words]
        words = re.sub(r"\"([^-].+?)\"", "", search_text)
        words = words.split() + quoted_words
        words = [w.replace("\"", "") for w in words]
        self.logger.info("Search words: %s" % words)
        self.logger.info("Filter words: %s" % filter_words)
        self.logger.info("Rating function: %s" % rating)
        return words, filter_words, rating

    def search(self):
        self.logger.info("Search_text: %s" % self.search_text)
        if self.search_text == "":
            self.app_window.setNoSearchResults.emit(False)
            self.setup_pages()
            self.show_page()
        else:
            words, filters, rating = self.process_search(self.search_text)
            galleries = []
            for gallery in self.galleries:
                if gallery.expired:
                    continue
                title = re.sub("\W", " ", gallery.title.lower()).split()
                tags = [t.replace(" ", "_").lower() for t in gallery.tags]
                if rating and (not gallery.rating or
                               not eval(gallery.rating + rating)):
                    continue
                if any(self.in_search(tags, title, w) for w in filters):
                    continue
                if all(self.in_search(tags, title, w) for w in words) or len(words) == 0:
                    galleries.append(gallery)
            self.app_window.setNoSearchResults.emit(len(galleries) == 0)
            self.setup_pages(galleries)
            self.show_page()

    @staticmethod
    def in_search(tags, title, input_tag):
        for title_word in title:
            if input_tag in title_word:
                return True
        for tag in tags:
            if input_tag in tag:
                return True
        return False

    def setup_threads(self):
        self.threads["gallery"] = Threads.GalleryThread(self)
        self.threads["gallery"].start()
        self.threads["image"] = Threads.ImageThread(self)
        self.threads["image"].start()
        self.threads["metadata"] = Threads.SearchThread(self)
        self.threads["metadata"].start()
        self.threads["duplicate"] = Threads.DuplicateFinderThread(self)
        self.threads["duplicate"].start()

    def setup_tags(self):
        tags = []
        tag_count_map = {}
        for gallery in [g for g in self.galleries if not g.expired]:
            new_tags = list(set(map(lambda x: x.replace(" ", "_").lower(), gallery.tags)))
            for tag in new_tags:
                if tag_count_map.get(tag):
                    tag_count_map[tag] += 1
                else:
                    tag_count_map[tag] = 1
            tags += new_tags
        self.tags = list(set(tags))
        self.tags += list(map(lambda x: "-" + x, self.tags))
        self.tags.sort()
        self.setup_completer()

    def find_galleries(self, initial=False):
        self.app_window.setScanningMode(True)
        self.logger.debug("Sending start signal to gallery thread")
        self.threads["gallery"].queue.put(None)

    def find_galleries_done(self, galleries):
        self.galleries += galleries
        self.logger.debug("Gallery thread done")
        self.setup_tags()
        self.sort()

    def send_page(self):
        self.hide_page()
        for gallery in self.current_page:
            if gallery.expired:
                continue
            self.app_window.addGallery.emit(gallery.get_json())

    def show_page(self):
        self.hide_page()
        need_images = []
        for gallery in self.current_page:
            if not gallery.thumbnail_verified:
                need_images.append(gallery)
        self.generate_images(need_images)

    def hide_page(self):
        self.app_window.clearGalleries.emit()

    def generate_images(self, galleries):
        self.app_window.setScanningMode(True)
        self.threads["image"].queue.put(galleries)

    def image_thread_done(self):
        self.app_window.setScanningMode(False)
        self.logger.debug("Image thread done.")
        self.send_page()

    def get_metadata(self, uuid):
        try:
            uuid = int(uuid)
            assert uuid == -1
            galleries = self.filter_galleries(self.galleries)
        except (ValueError, TypeError):
            galleries = [self.get_gallery_by_uuid(uuid)]
        self.logger.debug("Starting metadata thread")
        self.app_window.setSearchMode(True)
        self.threads["metadata"].queue.put(galleries)

    def set_current_metadata_gallery(self, gallery):
        self.app_window.setCurrentMetadataGallery(gallery.title)

    def update_gallery_metadata(self, gallery, metadata):
        gallery.update_metadata(metadata)
        gallery.save_metadata()

    def get_metadata_done(self):
        self.app_window.setSearchMode(False)
        self.logger.debug("Metadata thread done.")
        self.setup_tags()

    def generate_duplicate_map(self):
        self.app_window.setDuplicateScanMode(True)
        self.threads["duplicate"].queue.put(self.filter_galleries(self.galleries))

    def duplicate_map_generated(self, duplicate_map):
        self.app_window.setDuplicateScanMode(False)
        for key in duplicate_map:
            if len(duplicate_map[key]) > 1:
                print duplicate_map[key][0]

    def close(self):
        for gallery in self.galleries:
            gallery.__del__()
        self.quit()

    def sort(self):
        key = None
        if self.sort_type == self.SortMap.NameSort:
            key = attrgetter("sort_name")
        elif self.sort_type == self.SortMap.LastReadSort:
            key = attrgetter("last_read")
        elif self.sort_type == self.SortMap.RatingSort:
            key = attrgetter("sort_rating")
        elif self.sort_type == self.SortMap.ReadCountSort:
            key = attrgetter("read_count")
        elif self.sort_type == self.SortMap.DateAddedSort:
            key = attrgetter("time_added")
        self.galleries.sort(key=key, reverse=self.sort_mode_reversed)
        self.search()

    def switch_page(self, page_num):
        self.page_number = int(page_num) - 1
        self.app_window.setPage(self.page_number + 1)
        self.show_page()

    def filter_galleries(self, galleries):
        return_galleries = []
        for gallery in galleries:
            if gallery.expired:
                continue
            if not any(gallery.exists_under(d) for d in self.dirs):
                continue
            return_galleries.append(gallery)
        return return_galleries

    def setup_pages(self, galleries=None):
        if galleries is None:  # Need to do it this way because passing in galleries of [] would cause problems
            galleries = self.galleries
        galleries = self.filter_galleries(galleries)
        self.pages = [galleries[i:i + self.PAGE_SIZE]
                      for i in range(0, len(galleries),
                                     self.PAGE_SIZE)] or [[]]
        self.app_window.setPageCount(self.page_count)
        self.page_number = 0
        self.app_window.setPage(self.page_number + 1)

    def thread_exception_handler(self, thread, exception):
        self.exception_hook(*exception)

    def exception_hook(self, extype, exvalue, extraceback):
        fatal = True  # Default to true for unhandled exceptions
        if issubclass(extype, Exceptions.CustomBaseException):
            fatal = exvalue.fatal
            message = exvalue.msg
        else:
            message = "Sorry, PandaViewer got an unhandled %s exception and must close.\nPlease feel free to submit a bug report" % extype
            self.logger.error("Got unhandled exception", exc_info=(extype, exvalue, extraceback))
        self.app_window.setException(message, fatal)



if __name__ == "__main__":
    reload(sys)
    sys.setdefaultencoding("utf-8")
    filename = strftime("%Y-%m-%d-%H.%M.%S") + ".log"
    logging.basicConfig(level=logging.DEBUG,
                        filename=filename,
                        format="%(asctime)s: %(name)s %(levelname)s %(message)s")
    if os.name == "nt":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("lsv.ui")
    app = Program(sys.argv)
    sys.excepthook = app.exception_hook
    sys.exit(app.exec_())
