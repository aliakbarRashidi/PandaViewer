#!/usr/bin/env python2

from PyQt5 import QtGui
from PyQt5 import QtWidgets
from PyQt5 import QtQml
from PyQt5 import QtQuick
from PyQt5 import QtNetwork
from PyQt5 import QtCore
from time import strftime
from Logger import Logger
from operator import attrgetter
import sys
import os
import re
import gc
import json
import logging
import Threads
import Exceptions
import Database
from Utils import Utils
from Gallery import Gallery
from profilehooks import profile
from Config import config


class Program(QtWidgets.QApplication, Logger):
    PAGE_SIZE = 100
    BUG_PAGE = "https://github.com/seanegoodwin/pandaviewer/issues"
    THUMB_DIR = Utils.convert_from_relative_lsv_path("thumbs")
    QML_PATH = os.path.join(os.path.abspath("."), "qml/")
    MAX_TAG_RETURN_COUNT = 5

    class SortMap(object):
        NameSort = 0
        ReadCountSort = 1
        LastReadSort = 2
        RatingSort = 3
        DateAddedSort = 4
        FilePathSort = 5

    def __init__(self, args):
        """
        :type pages list[list[Gallery]]
        :type galleries list[Gallery]
        """
        super(Program, self).__init__(args)

        self.tags = []
        self.pages = [[]]
        self.galleries = []
        self.version = "0.1"  # Most likely used for db changes only
        self.page_number = 0
        self.search_text = ""
        self.setOrganizationName("SG")
        self.setOrganizationDomain(self.BUG_PAGE)
        self.setApplicationName("PandaViewer")

    def setup(self):
        if not os.path.exists(self.THUMB_DIR):
            os.makedirs(self.THUMB_DIR)
        Database.setup()
        self.setAttribute(QtCore.Qt.AA_UseOpenGLES, True)
        self.addLibraryPath(self.QML_PATH)
        self.qml_engine = QtQml.QQmlApplicationEngine()
        self.qml_engine.addImportPath(self.QML_PATH)
        self.qml_engine.addPluginPath(self.QML_PATH)
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
        self.app_window.setUISort.emit(config.sort_type, 1 if config.sort_mode_reversed else 0)
        self.completer_line = QtWidgets.QLineEdit()
        self.completer_line.hide()
        self.setup_completer()
        self.setWindowIcon(QtGui.QIcon("icon.ico"))
        self.set_ui_config()
        self.app_window.show()
        self.setup_threads()

    def setup_completer(self):
        self.completer = QtWidgets.QCompleter(self.tags)
        self.completer.setModelSorting(self.completer.CaseInsensitivelySortedModel)
        self.completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.completer_line.setCompleter(self.completer)

    def set_sorting(self, sort_type, reversed):
        config.sort_type = sort_type
        config.sort_mode_reversed = reversed
        config.save()
        self.sort()

    def update_search(self, search_text):
        self.search_text = search_text
        self.search()

    def set_ui_gallery(self, gallery):
        self.app_window.setGallery.emit(gallery.ui_uuid, gallery.get_json())

    def remove_gallery_by_uuid(self, uuid):
        gallery = self.get_gallery_by_ui_uuid(uuid)
        gallery.mark_for_deletion()
        self.current_page.remove(gallery)
        self.setup_tags()

    def get_detailed_gallery(self, uuid):
        self.app_window.openDetailedGallery.emit(self.get_gallery_by_ui_uuid(uuid).get_detailed_json())

    def get_tags_from_search(self, search):
        self.completer_line.setText(search)
        self.completer.setCompletionPrefix(search)
        tags = []
        for i in range(self.completer.completionCount()):
            self.completer.setCurrentRow(i)
            tags.append(self.completer.currentCompletion())
        tags.sort(key=len)
        self.app_window.setTags(tags[:self.MAX_TAG_RETURN_COUNT])

    def get_gallery_by_ui_uuid(self, uuid):
        """
        :rtype Gallery
        """
        assert uuid
        return next(g for g in self.current_page if g.ui_uuid == uuid)

    def update_gallery_rating(self, uuid, rating):
        self.get_gallery_by_ui_uuid(uuid).set_rating(rating)

    def get_gallery_image_folder(self, uuid):
        self.app_window.setGalleryImageFolder.emit(uuid,
                                                   self.get_gallery_by_ui_uuid(uuid).image_folder)

    def set_gallery_image(self, uuid, image_path):
        self.get_gallery_by_ui_uuid(uuid).set_thumbnail_source(image_path)

    def open_gallery(self, uuid, index):
        self.get_gallery_by_ui_uuid(uuid).open(index)

    def open_gallery_folder(self, uuid):
        self.get_gallery_by_ui_uuid(uuid).open_folder()

    def open_on_ex(self, uuid):
        self.get_gallery_by_ui_uuid(uuid).open_on_ex()

    def save_gallery_customization(self, uuid, gallery):
        self.get_gallery_by_ui_uuid(uuid).save_customization(gallery)

    def exec_(self):
        self.find_galleries(initial=True)
        return super(Program, self).exec_()

    @property
    def current_page(self):
        """
        :rtype list[Gallery]
        """
        return self.pages[self.page_number]

    @property
    def page_count(self):
        return len(self.pages)

    def set_ui_config(self):
        self.app_window.setSettings(config.get_ui_config())
        # self.app_window.setSettings(
        #     {
        #         "exUserID": Config.ex_member_id,
        #         "exPassHash": Config.ex_pass_hash,
        #         "folders": Config.folders,
        #         "confirm_delete": Config.confirm_delete,
        #     })

    def update_config(self, ui_config):
        if config.update_from_ui_config(ui_config):
            self.set_auto_metadata_collection()
        self.sort()

    def set_scan_folder(self, folder):
        self.app_window.setScanFolder(folder)

    def set_auto_metadata_collection(self, galleries=None):
        galleries = galleries or self.galleries
        for gallery in self.filter_galleries(galleries):
            matching_dir = Utils.get_parent_folder(config.folders, gallery.path)
            assert matching_dir
            ex_auto_collection = config.folder_options.get(matching_dir,
                                                           {}).get(config.AUTO_METADATA_KEY, True)
            if ex_auto_collection != gallery.ex_auto_collection:
                gallery.ex_auto_collection = ex_auto_collection
                gallery.save_metadata()

    def process_search(self, search_text):
        quote_regex = re.compile(r"(-)?\"(.*?)\"")
        filter_regex = re.compile(r"(?:^|\s)\-(.*?)(?=(?:$|\ ))")
        search_text = search_text.lower()
        rating_method = re.search(r"rating:(\S*)", search_text)
        if rating_method:
            search_text = re.sub("rating:\S*", "", search_text)
            rating_method = rating_method.groups()[0]
            if rating_method[0] == "=" and rating_method[1] != "=":
                rating_method = "=" + rating_method
            try:
                eval("0.0" + rating_method)
            except:
                raise Exceptions.InvalidRatingSearch()
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
        if self.search_text == "":
            self.app_window.setNoSearchResults.emit(False)
            self.setup_pages()
            self.show_page()
        else:
            words, filters, rating_method = self.process_search(self.search_text)
            galleries = []
            for gallery in self.galleries:
                if gallery.expired:
                    continue
                title = gallery.clean_name.lower().split()
                tags = [t.replace(" ", "_").lower() for t in gallery.tags]
                if rating_method and (not gallery.rating or
                                          not eval(gallery.rating + rating_method)):
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
        for thread in Threads.DAEMON_THREADS:
            thread.setup(self)
            thread.start()

    def setup_tags(self):
        tags = []
        tag_count_map = {}
        for gallery in self.filter_galleries(self.galleries):
            new_tags = list(set(map(lambda x: x.replace(" ", "_").lower(), gallery.tags)))
            for tag in new_tags:
                tag_count_map[tag] = tag_count_map.get(tag, 0) + 1
            tags += new_tags
        self.tags = list(set(tags))

        namespace_match = re.compile(r":(.*)")
        for tag in self.tags[:]:
            raw_tag = re.search(namespace_match, tag)
            if raw_tag:
                self.tags.append(raw_tag.groups()[0])
        self.tags += list(map(lambda x: "-" + x, self.tags))
        self.tags.sort()
        self.setup_completer()

    def find_galleries(self, initial=False):
        self.app_window.setScanningMode(True)
        self.logger.debug("Sending start signal to gallery thread")
        Threads.gallery_thread.queue.put(None)

    def find_galleries_done(self, galleries):
        self.app_window.setScanningMode(False)
        self.set_auto_metadata_collection(galleries)
        self.galleries += galleries
        self.logger.debug("Gallery thread done")
        self.setup_tags()
        self.sort()

    def send_page(self):
        index_list = (i for i in range(0, self.PAGE_SIZE))
        for gallery in self.current_page:
            self.app_window.setUIGallery.emit(next(index_list), gallery.get_json())

        [self.app_window.removeUIGallery.emit(i, 1) for i in list(index_list)[::-1]]

        # index_list = list(index_list)
        # if index_list:
        #     self.app_window.removeUIGallery.emit(index_list[0], len(index_list))
        gc.collect()

    def show_page(self):
        need_images = []
        for gallery in self.current_page:
            if not gallery.thumbnail_verified:
                need_images.append(gallery)
        if need_images:
            self.generate_images(need_images)
        else:
            self.send_page()

    def hide_page(self):
        self.app_window.clearGalleries.emit()

    def generate_images(self, galleries):
        self.app_window.setScanningMode(True)
        Threads.image_thread.queue.put(galleries)

    def image_thread_done(self):
        self.app_window.setScanningMode(False)
        self.logger.debug("Image thread done.")
        self.send_page()

    def get_metadata(self, uuid):
        try:
            uuid = int(uuid)
            galleries = [g for g in self.filter_galleries(self.galleries) if g.ex_auto_collection]
            if uuid == -1:
                for gallery in galleries:
                    gallery.force_metadata = True
        except (ValueError, TypeError):
            gallery = self.get_gallery_by_ui_uuid(uuid)
            gallery.force_metadata = True
            galleries = [gallery]
        self.logger.debug("Starting metadata thread")
        self.app_window.setSearchMode(True)
        Threads.search_thread.queue.put(galleries)

    def set_current_metadata_gallery(self, gallery):
        self.app_window.setCurrentMetadataGallery(gallery.title)

    def update_gallery_metadata(self, gallery, metadata):
        gallery.update_metadata(metadata)
        gallery.save_metadata()

    def get_metadata_done(self):
        self.app_window.setSearchMode(False)
        self.logger.debug("Metadata thread done.")
        self.setup_tags()

    def remove_duplicates(self):
        self.app_window.setScanningMode(True)
        Threads.duplicate_thread.queue.put(self.filter_galleries(self.galleries))

    def duplicate_thread_done(self):
        self.app_window.setScanningMode(False)
        self.setup_tags()
        self.sort()

    def close(self):
        [g.__del__() for g in self.galleries]
        self.quit()

    def sort(self):
        key = None
        if config.sort_type == self.SortMap.NameSort:
            key = attrgetter("sort_name")
        elif config.sort_type == self.SortMap.LastReadSort:
            key = attrgetter("last_read")
        elif config.sort_type == self.SortMap.RatingSort:
            key = attrgetter("sort_rating")
        elif config.sort_type == self.SortMap.ReadCountSort:
            key = attrgetter("read_count")
        elif config.sort_type == self.SortMap.DateAddedSort:
            key = attrgetter("time_added")
        elif config.sort_type == self.SortMap.FilePathSort:
            key = attrgetter("sort_path")
        assert key
        self.galleries.sort(key=key, reverse=config.sort_mode_reversed)
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
            if not any(Utils.path_exists_under_directory(d, gallery.path) for d in config.folders):
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

    def remove_gallery_and_recalculate_pages(self, gallery):
        assert gallery in self.current_page
        self.galleries.remove(gallery)
        self.current_page.remove(gallery)
        working_page = self.page_number
        while working_page < self.page_count:
            self.pages[working_page].append(self.pages[working_page + 1].pop(0))
            working_page += 1


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
    # import locale
    # locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
    filename = strftime("%Y-%m-%d-%H.%M.%S") + ".log"
    logging.basicConfig(handlers=[logging.FileHandler(filename, 'w', 'utf-8')],
                        format="%(asctime)s: %(name)s %(levelname)s %(message)s",
                        level=logging.DEBUG)

    if os.name == "nt":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("pv.ui")
    app = Program(sys.argv)
    sys.excepthook = app.exception_hook
    app.setup()
    sys.exit(app.exec_())
