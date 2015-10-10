import bs4
from typing import List, Dict
from collections import namedtuple
from difflib import SequenceMatcher
from .logger import Logger
from .gallery import GenericGallery
from .request_managers import ex_request_manager, chaika_request_manager

ChaikaResult = namedtuple("ChaikaResult", "url title")

class Search(Logger):
    BASE_EX_URL = "http://exhentai.org/?inline_set=dm_t&f_doujinshi=1&f_manga=1&f_artistcg=1&f_gamecg=1&f_western=1&f_non-h=1&f_imageset=1&f_cosplay=1&f_asianporn=1&f_misc=0&f_sname=on&adv&f_search=%s&advsearch=1&f_srdd=2&f_apply=Apply+Filter&f_shash=%s&page=%s&fs_smiliar=1&fs_covers=%s"
    BASE_CHAIKA_URL = "http://panda.chaika.moe/?title={TITLE}&tags=&posted_from=&posted_to=&filesize_from=&filesize_to=&source_type=&sort=posted&asc_desc=desc&apply=Apply"

    @classmethod
    def search_ex_by_gallery(cls, gallery: GenericGallery):
        cls = cls()
        cls.name = gallery.title  # For logging
        sha_hash = gallery.generate_image_hash(index=0)
        hash_search = next(cls.ex_search(sha_hash=sha_hash))
        cls.logger.info("EX cover hash search results: %s" % hash_search)
        if len(hash_search) == 1:
            return hash_search[0]
        all_pages_hash = next(cls.ex_search(sha_hash=sha_hash, cover_only=0))
        cls.logger.info("EX all pages hash results: %s" % all_pages_hash)
        if len(all_pages_hash) == 1:
            return all_pages_hash[0]
        combined = hash_search + all_pages_hash
        if len(combined) == 0:
            try:
                sha_hash = gallery.generate_image_hash(index=1)
                second_hash_search = next(cls.ex_search(sha_hash=sha_hash))
                if len(second_hash_search) == 1:
                    return second_hash_search[0]
                else:
                    hash_search += second_hash_search
                    combined += hash_search
            except IndexError:
                pass
        if len(combined) == 0:
            cls.logger.info("No ex search results for gallery.")
            return
        intersection = [r for r in hash_search if r in all_pages_hash]
        if intersection:
            cls.logger.info("Returning ex intersection result.")
            return intersection[0]
        else:
            cls.logger.info("No ex intersection results, picking first available hash.")
            return combined[0]

    @classmethod
    def ex_search(cls, **kwargs):
        cls = cls()
        recursive = kwargs.get("recursive", False)
        page_num = kwargs.get("page_num", 0)
        num_pages = kwargs.get("num_pages")
        sha_hash = kwargs.get("sha_hash", "")
        cover_only = kwargs.get("cover_only", 1)
        title = kwargs.get("title", "")
        url = kwargs.get("url") or cls.BASE_EX_URL % (title, sha_hash, page_num, cover_only)
        response = ex_request_manager.get(url)
        html_results = bs4.BeautifulSoup(response, "html.parser")
        results = html_results.findAll("div", {"class": "it5"})
        result_urls = [r.a.attrs["href"] for r in results]
        if num_pages is None:
            pages = html_results.find("table", "ptt")
            if pages is not None:
                try:
                    num_pages = int(pages.findAll("a")[-2].contents[0]) - 1
                except IndexError:
                    pass
                kwargs["num_pages"] = num_pages
        yield result_urls
        if not recursive or page_num >= num_pages:
            return
        else:
            if page_num == 0:
                kwargs["page_num"] = 1
            else:
                kwargs["page_num"] += 1
            yield from cls.ex_search(**kwargs)

    @classmethod
    def search_chaika_by_gallery(cls, gallery: GenericGallery) -> str:
        cls = cls()
        chaika_url = cls.search_chaika(gallery)
        if chaika_url:
            cls.logger.info("{GALLERY} - Chaika url of {URL} found".format(GALLERY=gallery, URL=chaika_url))
            gallery_page = bs4.BeautifulSoup(chaika_request_manager.get(chaika_url), "html.parser")
            ex_url = gallery_page.find("a", {"rel": "nofollow"})
            if ex_url:
                return ex_url.get_text()

    @classmethod
    def search_chaika(cls, gallery: GenericGallery) -> str:
        cls = cls()
        cls.name = gallery.name
        title_results = cls.convert_chaika_results(
            chaika_request_manager.get(cls.BASE_CHAIKA_URL.format(TITLE=gallery.title)))
        cls.logger.info("Chaika results: {RESULTS}".format(RESULTS=title_results))
        for result in title_results:
            ratio = SequenceMatcher(None, gallery.name, result.title).ratio()
            if ratio >= .6:
                return result.url

    @classmethod
    def convert_chaika_results(cls, results: str) -> List[ChaikaResult]:
        base_gallery_url = "http://panda.chaika.moe{PATH}"
        results_html = bs4.BeautifulSoup(results, "html.parser").find("table", {"class": "resulttable"})
        galleries = bs4.BeautifulSoup(str(results_html), "html.parser").find_all("tr")
        return [ChaikaResult(base_gallery_url.format(PATH=gallery.a.attrs["href"]),
                         gallery.a.get_text()) for gallery in galleries if gallery.a]

