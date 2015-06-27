#!/usr/bin/env python

import bs4 as BeautifulSoup
from Logger import Logger
from RequestManager import RequestManager
import re


class Search(Logger):
    BASE_URL = r"http://exhentai.org/?f_doujinshi=1&f_manga=1&f_artistcg=1&f_gamecg=1&f_western=1&f_non-h=1&f_imageset=1&f_cosplay=1&f_asianporn=1&f_misc=1&f_sname=on&adv&f_search=%s&advsearch=1&f_srdd=2&f_apply=Apply+Filter&f_shash=%s&page=%s&fs_smiliar=1&fs_covers=%s"

    @classmethod
    def clean_title(cls, name, remove_enclosed=True):
        banned_chars = ["=", "-", ":", "|", "~", "+", "]", "[", ",", ")", "("]
        pairs = [("{", "}"), ("(", ")"), ("[", "]")]
        if remove_enclosed:
            regex = ur"\s*\%s[^%s]*\%s"
            for pair in pairs:
                name = re.sub(regex % (pair[0], pair[0], pair[1]), "",  name)
        name = name.lstrip().lower()
        for char in banned_chars:
            name = name.replace(char, " ")
        return " ".join(name.split())

    @classmethod
    def search_by_gallery(cls, gallery):
        cls = cls()
        cls.name = gallery.title  # For logging
        sha_hash = gallery.image_hash or gallery.generate_image_hash()
        hash_search = cls._search(sha_hash=sha_hash)
        cls.logger.info("Hash search results: %s" % hash_search)
        if len(hash_search) == 1:
            return hash_search[0]
        all_pages_hash = cls._search(sha_hash=sha_hash, title_only=0)
        cls.logger.info("All pages hash results: %s" % all_pages_hash)
        if len(all_pages_hash) == 1:
            return all_pages_hash[0]
        else:
            hash_search += all_pages_hash
        title = cls.clean_title(gallery.name)
        title_search = cls._search(title=title)
        cls.logger.info("Title search results: %s" % title_search)
        if len(title_search) == 1:
            return title_search[0]
        if len(hash_search) == 0:
            if len(title_search) == 0:
                cls.logger.info("No search results for gallery.")
            else:
                # TODO Implement gallery picker
                cls.logger.info("No definite gallery found, picking first title result.")
                return title_search[0]
        else:
            intersection = [val for val in hash_search if val in title_search]
            if len(intersection) == 0:
                cls.logger.info("No search intersection found, picking first hash result.")
                return hash_search[0]
            elif len(intersection) > 1:
                cls.logger.info("No definite gallery found, picking first insersection result")
            return intersection[0]

    @classmethod
    def _search(cls, **kwargs):
        cls = cls()
        recursive = kwargs.get("recursive", False)
        page_num = kwargs.get("page_num", 0)
        num_pages = kwargs.get("num_pages", 0)
        sha_hash = kwargs.get("sha_hash", "")
        cover_only = kwargs.get("title_only", 1)
        title = kwargs.get("title", "")
        url = cls.BASE_URL % (title, sha_hash, page_num, cover_only)
        response = RequestManager.get(url)
        html_results = BeautifulSoup.BeautifulSoup(response)
        results = html_results.findAll("div", {"class": "it5"})
        #result_urls = [r.a.attrs[0][1] for r in results]
        result_urls = [r.a.attrs["href"] for r in results]
        if num_pages is None:
            pages = html_results.find("table", "ptt")
            if pages is not None:
                try:
                    num_pages = int(pages.findAll("a")[-2].contents[0]) - 1
                except IndexError:
                    pass
                kwargs["num_pages"] = num_pages
        if not recursive or page_num >= num_pages:
            return result_urls
        if page_num == 0:
            kwargs["page_num"] = 1
        else:
            kwargs["page_num"] += 1
        return result_urls + cls._search(**kwargs)
