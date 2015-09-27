import bs4 as BeautifulSoup
from .Logger import Logger
from .Gallery import GenericGallery
from .RequestManager import RequestManager


class Search(Logger):
    BASE_URL = r"http://exhentai.org/?inline_set=dm_t&f_doujinshi=1&f_manga=1&f_artistcg=1&f_gamecg=1&f_western=1&f_non-h=1&f_imageset=1&f_cosplay=1&f_asianporn=1&f_misc=0&f_sname=on&adv&f_search=%s&advsearch=1&f_srdd=2&f_apply=Apply+Filter&f_shash=%s&page=%s&fs_smiliar=1&fs_covers=%s"

    @classmethod
    def search_by_gallery(cls, gallery: GenericGallery):
        cls = cls()
        cls.name = gallery.title  # For logging
        sha_hash = gallery.generate_image_hash(index=0)
        hash_search = next(cls._search(sha_hash=sha_hash))
        cls.logger.info("Cover hash search results: %s" % hash_search)
        if len(hash_search) == 1:
            return hash_search[0]
        all_pages_hash = next(cls._search(sha_hash=sha_hash, cover_only=0))
        cls.logger.info("All pages hash results: %s" % all_pages_hash)
        if len(all_pages_hash) == 1:
            return all_pages_hash[0]
        combined = hash_search + all_pages_hash
        if len(combined) == 0:
            try:
                sha_hash = gallery.generate_image_hash(index=1)
                second_hash_search = next(cls._search(sha_hash=sha_hash))
                if len(second_hash_search) == 1:
                    return second_hash_search[0]
                else:
                    hash_search += second_hash_search
                    combined += hash_search
            except IndexError:
                pass
        if len(combined) == 0:
            cls.logger.info("No search results for gallery.")
            return
        intersection = [r for r in hash_search if r in all_pages_hash]
        if intersection:
            cls.logger.info("Returning intersection result.")
            return intersection[0]
        else:
            cls.logger.info("No intersection results, picking first available hash.")
            return combined[0]
        # else:
        #     hash_search += all_pages_hash
        # title = cls.clean_title(gallery.name)
        # title_search = cls._search(title=title)
        # cls.logger.info("Title search results: %s" % title_search)
        # if len(title_search) == 1:
        #     return title_search[0]
            # if len(title_search) == 0:
            #     cls.logger.info("No search results for gallery.")
            # else:
            #     # TODO Implement gallery picker
            #     cls.logger.info("No definite gallery found, picking first title result.")
            #     return title_search[0]
        # else:

            # intersection = [val for val in hash_search if val in title_search]
            # if len(intersection) == 0:
            #     cls.logger.info("No search intersection found, picking first hash result.")
            #     return hash_search[0] or title_search[0]
            # elif len(intersection) > 1:
            #     cls.logger.info("No definite gallery found, picking first intersection result")
            # return intersection[0]


    @classmethod
    def _search(cls, **kwargs):
        cls = cls()
        recursive = kwargs.get("recursive", False)
        page_num = kwargs.get("page_num", 0)
        num_pages = kwargs.get("num_pages")
        sha_hash = kwargs.get("sha_hash", "")
        cover_only = kwargs.get("cover_only", 1)
        title = kwargs.get("title", "")
        url = kwargs.get("url") or cls.BASE_URL % (title, sha_hash, page_num, cover_only)
        response = RequestManager.get(url)
        html_results = BeautifulSoup.BeautifulSoup(response, "html.parser")
        results = html_results.findAll("div", {"class": "it5"})
        # print(html_results.findAll("div", {"class": "it5"}))
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
            yield from cls._search(**kwargs)
