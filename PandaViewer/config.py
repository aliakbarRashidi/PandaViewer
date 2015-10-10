import json
import codecs
import weakref
from configparser import SafeConfigParser
import PandaViewer
from PandaViewer.utils import Utils
from PandaViewer.logger import Logger


class Config(Logger, SafeConfigParser):

    CONFIG_FILE = Utils.convert_from_relative_lsv_path("settings.ini")
    SECTIONS = {
        "General": [
            "folders",
            "folder_options",
            "sort_type",
            "sort_mode_reversed",
            "confirm_delete",

        ],
        "Archives": [
            "extract_zip",
            "extract_cbz",
            "extract_rar",
            "extract_cbr",
        ],
        "Ex": [
            "ex_member_id",
            "ex_pass_hash",
        ],
    }
    AUTO_METADATA_KEY = "auto_metadata"
    FOLDER_OPTIONS = [
        AUTO_METADATA_KEY,
    ]


    def __init__(self):
        super().__init__()
        try:
            self.load()
        except FileNotFoundError:
            self.save()
        self.setup()
        self.save()

    def setup(self):
        for section in self.SECTIONS:
            if not self.has_section(section):
                self.add_section(section)
            for option in self.SECTIONS.get(section):
                if not self.has_option(section, option):
                    self.set(section, option, "")

    def load(self):
        with codecs.open(self.CONFIG_FILE, "r", encoding="utf8") as file:
            self.read_file(file)

    def save(self):
        self.logger.debug("Saving config")
        with codecs.open(self.CONFIG_FILE, "w", encoding="utf8") as file:
            self.write(file)

    def get_ui_config(self):
        ui_config = {}
        for section in self.SECTIONS:
            for option in self.SECTIONS.get(section):
                ui_config[option] = getattr(self, option)
        return ui_config

    def update_from_ui_config(self, ui_config):
        self.logger.info("Updating config")
        old_folders = self.folders
        self.folders = ui_config.property("folders").toVariant()
        if old_folders != self.folders:
            PandaViewer.threads.folder_watcher_thread.queue.put(None)
        self.confirm_delete = ui_config.property("confirm_delete").toString()
        self.ex_member_id = ui_config.property("ex_member_id").toString()
        self.ex_pass_hash = ui_config.property("ex_pass_hash").toString()

        self.extract_zip = ui_config.property("extract_zip").toString()
        self.extract_cbz = ui_config.property("extract_cbz").toString()
        self.extract_rar = ui_config.property("extract_rar").toString()
        self.extract_cbr = ui_config.property("extract_cbr").toString()

        folder_options = ui_config.property("folder_options").toVariant()
        update_auto_metadata_collection = False
        for folder in folder_options:
            if folder_options.get(folder) != self.folder_options.get(folder):
                self.folder_metadata_map = folder_options
                update_auto_metadata_collection = True
                break
        self.folder_options = folder_options
        self.save()
        return update_auto_metadata_collection

    @property
    def folders(self):
        folders = self.get("General", "folders") or "[]"
        return list(map(Utils.normalize_path, json.loads(folders)))

    @folders.setter
    def folders(self, value):
        self.set("General", "folders", json.dumps(value, ensure_ascii=False))

    @property
    def folder_options(self):
        options = self.get("General", "folder_options") or "{}"
        return json.loads(options)

    @folder_options.setter
    def folder_options(self, value):
        self.set("General", "folder_options", json.dumps(value, ensure_ascii=False))

    @property
    def ex_member_id(self):
        return self.get("Ex", "ex_member_id")

    @ex_member_id.setter
    def ex_member_id(self, value):
        self.set("Ex", "ex_member_id", str(value))

    @property
    def ex_pass_hash(self):
        return self.get("Ex", "ex_pass_hash")

    @ex_pass_hash.setter
    def ex_pass_hash(self, value):
        self.set("Ex", "ex_pass_hash", value)

    @property
    def sort_type(self):
        try:
            return self.getint("General", "sort_type")
        except ValueError:
            return 0

    @sort_type.setter
    def sort_type(self, value):
        self.set("General", "sort_type", str(value))

    @property
    def sort_mode_reversed(self):
        try:
            return self.getboolean("General", "sort_mode_reversed")
        except ValueError:
            return False

    @sort_mode_reversed.setter
    def sort_mode_reversed(self, value):
        self.set("General", "sort_mode_reversed", str(value))

    @property
    def confirm_delete(self):
        try:
            return self.getboolean("General", "confirm_delete")
        except ValueError:
            return True

    @confirm_delete.setter
    def confirm_delete(self, value):
        self.set("General", "confirm_delete", str(value))

    @property
    def extract_zip(self):
        try:
            return self.getboolean("Archives", "extract_zip")
        except ValueError:
            return True

    @extract_zip.setter
    def extract_zip(self, value):
        self.set("Archives", "extract_zip", str(value))

    @property
    def extract_cbz(self):
        try:
            return self.getboolean("Archives", "extract_cbz")
        except ValueError:
            return True

    @extract_cbz.setter
    def extract_cbz(self, value):
        self.set("Archives", "extract_cbz", str(value))

    @property
    def extract_rar(self):
        try:
            return self.getboolean("Archives", "extract_rar")
        except ValueError:
            return True

    @extract_rar.setter
    def extract_rar(self, value):
        self.set("Archives", "extract_rar", str(value))

    @property
    def extract_cbr(self):
        try:
            return self.getboolean("Archives", "extract_cbr")
        except ValueError:
            return True

    @extract_cbr.setter
    def extract_cbr(self, value):
        self.set("Archives", "extract_cbr", str(value))


Config = Config()
