import os
import re
import sys
import hashlib
from sqlalchemy.engine import ResultProxy
from typing import List, Dict, Any, Tuple, Iterable, Optional
from PandaViewer.logger import Logger


class Utils(Logger):


    @staticmethod
    def convert_result(result: ResultProxy) -> List:
        return list(map(dict, result))

    @classmethod
    def convert_from_relative_path(cls, path: str = "") -> str:
        folder = os.path.dirname(__file__)
        # TODO: Ugly hack please fix. Used to tell if program is running from source or not
        if not os.path.exists(Utils.normalize_path(os.path.join(folder, __file__))):
            folder = os.path.dirname(folder)
        return cls.normalize_path(os.path.join(folder, path))

    @classmethod
    def convert_from_relative_lsv_path(cls, path: str = "") -> str:
        portable_path = cls.convert_from_relative_path(os.path.join(".lsv", path))
        if os.path.exists(portable_path):
            return portable_path
        else:
            return cls.normalize_path(os.path.join("~/.lsv", path))

    @classmethod
    def path_exists_under_directory(cls, main_directory: str, sub_directory: str) -> bool:
        ensure_trailing_sep = lambda x: x if x[-1] == os.path.sep else x + os.path.sep
        main_directory = ensure_trailing_sep(cls.normalize_path(main_directory))
        sub_directory = ensure_trailing_sep(cls.normalize_path(sub_directory))
        return sub_directory.startswith(main_directory)

    @classmethod
    def get_parent_folder(cls, candidates: List[str], folder: str) -> str:
        candidates = map(cls.normalize_path, candidates)
        candidates = [c for c in candidates
                      if cls.path_exists_under_directory(c, folder)]
        return max(candidates, key=len)

    @staticmethod
    def file_has_allowed_extension(check_file: str, allowed_extensions: List[str]) -> bool:
        allowed_extensions = [ext.lower() for ext in allowed_extensions]
        ext = os.path.splitext(check_file)[-1].lower()
        return ext in allowed_extensions

    @staticmethod
    def normalize_path(path: str) -> str:
        return os.path.normpath(os.path.realpath(os.path.expanduser(path)))

    @staticmethod
    def convert_to_qml_path(path: str) -> str:
        base_string = "file://"
        if os.name == "nt":
            base_string += "/"
        return base_string + path

    @classmethod
    def reduce_gallery_duplicates(cls, duplicate_map):
        cls = cls()
        for galleries in duplicate_map.values():
            paths = [cls.normalize_path(gallery.location) for gallery in galleries]
            assert len(paths) == len(set(paths))
            method_names = ["has_ex_metadata", "has_custom_metadata", "is_archive_gallery"]
            for method_name in method_names:
                if any(getattr(gallery, method_name)() for gallery in galleries):
                    cls.logger.info("Applying method: %s" % method_name)
                    cls.logger.debug("Before galleries: %s" % galleries)
                    filtered_galleries = []
                    for gallery in galleries:
                        if not getattr(gallery, method_name)():
                            gallery.mark_for_deletion()
                        else:
                            filtered_galleries.append(gallery)
                    galleries = filtered_galleries
                    cls.logger.debug("After galleries: %s" % galleries)
            for gallery in galleries[1:]:
                gallery.mark_for_deletion()

    @classmethod
    def generate_hash_from_source(cls, source) -> str:
        BUFF_SIZE = 65536
        hash_algo = hashlib.sha1()
        buff = source.read(BUFF_SIZE)
        while len(buff) > 0:
            hash_algo.update(buff)
            buff = source.read(BUFF_SIZE)
        return hash_algo.hexdigest()

    @classmethod
    def debug_trace(cls):
        from PyQt5.QtCore import pyqtRemoveInputHook, pyqtRestoreInputHook
        from pdb import set_trace
        pyqtRemoveInputHook()
        set_trace()
        pyqtRestoreInputHook()

    @classmethod
    def convert_ui_tags(cls, ui_tags: str) -> List[str]:
        return list(map(lambda x: x.replace(" ", "_"), cls.convert_csv_to_list(ui_tags)))

    @classmethod
    def process_ex_url(cls, url: str) -> (str, str):
        split_url = url.split("/")
        if split_url[-1]:
            return int(split_url[-2]), split_url[-1]
        else:
            return int(split_url[-3]), split_url[-2]

    @staticmethod
    def convert_list_to_csv(input_list: List) -> str:
        return ", ".join(input_list)

    @staticmethod
    def convert_csv_to_list(csv: str) -> List[str]:
        return list(filter(None, map(lambda x: re.sub("^\s+", "", x), csv.split(","))))

    @staticmethod
    def human_sort_paths(paths: List[str]) -> List[str]:
        key = None
        if os.name == "nt":
            import ctypes
            import functools
            key = functools.cmp_to_key(ctypes.windll.shlwapi.StrCmpLogicalW)
        return sorted(paths, key=key)

    @staticmethod
    def separate_tag(tag: str) -> (str, Optional[str]):
        namespace_regex = re.compile("^(.*):(.*)$")
        match = re.search(namespace_regex, tag)
        if match:
            return match.group(2), match.group(1)
        return tag, None

    @classmethod
    def clean_title(cls, title: str, remove_enclosed: bool = True) -> str:
        banned_chars = ("=", "-", ":", "|", "~", "+", "]", "[", ",", ")", "(")
        if remove_enclosed:
            title = cls.removed_enclosed(title)
        title = title.lstrip().lower()
        for char in banned_chars:
            title = title.replace(char, " ")
        return " ".join(title.split())

    @staticmethod
    def removed_enclosed(input_str: str) -> str:
        """
        Removes any values between/including containers (braces, parens, etc)
        :param input_str: str to operate on
        :return: str with enclosed data removed
        """
        pairs = (("{", "}"), ("(", ")"), ("[", "]"))
        regex = r"\s*\%s[^%s]*\%s"
        for pair in pairs:
            input_str = re.sub(regex % (pair[0], pair[0], pair[1]), " ",  input_str)
        return " ".join(filter(None, input_str.split()))

