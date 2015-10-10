import time
import json
import random
import requests
import threading
from copy import deepcopy
from PandaViewer import exceptions
from PandaViewer.logger import Logger
from PandaViewer.config import Config


class RequestManager(Logger):
    API_TIME_WAIT = 3
    API_RETRY_COUNT = 3
    API_TIME_REQ_DELAY = 3
    API_MAX_SEQUENTIAL_REQUESTS = 3
    API_TIME_TOO_FAST_WAIT = 100
    SEQ_TIME_DIFF = 10
    SALT_BASE = 10 ** 4
    SALT_MAX_MULTI = 2
    HEADERS = {"User-Agent": "Mozilla/5.0 ;Windows NT 6.1; WOW64; Trident/7.0; rv:11.0; like Gecko"}
    count = 0
    prevtime = 0
    lock = threading.Lock()

    @classmethod
    def salt_time(cls, sleep_time):
        return sleep_time * (random.randint(cls.SALT_BASE,
                                            cls.SALT_BASE * cls.SALT_MAX_MULTI) / cls.SALT_BASE)

    def rest(self, method, url, **kwargs):
        with self.lock:
            return self._rest(method, url, **kwargs)

    def get(self, *args, **kwargs):
        return self.rest("get", *args, **kwargs)

    def post(self, *args, **kwargs):
        return self.rest("post", *args, **kwargs)

    def _rest(self, method, url, **kwargs):
        retry_count = kwargs.pop("retry_count", self.API_RETRY_COUNT)
        payload = kwargs.pop("payload", None)
        if payload:
            payload = json.dumps(payload)
        while retry_count > 0:
            gen_time_sleep = self.salt_time(self.API_TIME_REQ_DELAY)
            time_diff = time.time() - self.prevtime
            if time_diff <= gen_time_sleep:
                time.sleep(gen_time_sleep)
            sequential = time_diff <= self.SEQ_TIME_DIFF
            if sequential and self.count >= self.API_MAX_SEQUENTIAL_REQUESTS:
                time.sleep(self.salt_time(self.API_TIME_WAIT))
                self.count = 0
            if sequential:
                self.count += 1
            else:
                self.count = 0
            self.logger.info("Sending %s request to %s with payload %s" %
                             (method, url, payload))
            self.prevtime = time.time()
            response = getattr(requests, method)(url, data=payload, headers=self.HEADERS,
                                                 cookies=self.cookies, **kwargs)
            if self.validate_response(response):
                break
            else:
                retry_count -= 1
                self.logger.warning(
                    "Request failed, retry with %s tries left." % retry_count)
        if retry_count == 0:
            self.logger.warning("Request ran out of retry attempts.")
            return
        try:
            return response.json()
        except ValueError:
            pass
        if "text/html" in response.headers["content-type"]:
            return response.text
        else:
            return response

    def validate_response(self, response):
        content_type = response.headers["content-type"]
        assert response is not None
        self.logger.debug("Response: %s" % response)
        self.logger.debug("Response headers: %s" % response.headers)
        if response.status_code != 200:
            self.logger.warning("Error code: %s")
            return False
        if "image/gif" in content_type:
            raise(exceptions.BadCredentialsError)
        if "text/html" in content_type and "Your IP address" in response.text:
            raise(exceptions.UserBannedError)
        try:
            if response.json().get("error") is not None:
                self.logger.warning("Got error message %s" %
                                    response.json().get("error"))
                return False
        except ValueError:
            pass
        return True

    @property
    def cookies(self):
        return {}


class ExRequestManager(RequestManager):
    API_TIME_WAIT = 2
    API_RETRY_COUNT = 3
    API_TIME_REQ_DELAY = 3
    API_MAX_SEQUENTIAL_REQUESTS = 3
    API_TIME_TOO_FAST_WAIT = 100
    SEQ_TIME_DIFF = 10
    MEMBER_ID_KEY = "ipb_member_id"
    PASS_HASH_KEY = "ipb_pass_hash"
    COOKIES = {"uconfig": ""}

    @property
    def cookies(self):
        cookies = deepcopy(self.COOKIES)
        cookies[self.MEMBER_ID_KEY] = Config.ex_member_id
        cookies[self.PASS_HASH_KEY] = Config.ex_pass_hash
        return cookies


ex_request_manager = ExRequestManager()


class ChaikaRequestManager(RequestManager):
    API_TIME_WAIT = 1
    API_TIME_REQ_DELAY = 0


chaika_request_manager = ChaikaRequestManager()
