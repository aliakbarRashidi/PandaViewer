import re
import json
import weakref
from enum import Enum
from PyQt5 import QtQml
from typing import Dict, Any, List, Tuple
from sqlalchemy import select, update, insert, delete
import PandaViewer
from PandaViewer import user_database
from .logger import Logger
from .utils import  Utils


class MetadataManager(Logger):
    """
    Interface for managing metadata
    Instead of directly storing and accessing metadata through the gallery, this acts as a go-between
    for the gallery and the new metadata objects
    """

    DEFAULTS = {
        "title": "",
        "rating": 0,
        "category": "",
        "url": "",
        "tags": [],
    }

    _gallery = None


    def __init__(self, gallery: 'PandaViewer.gallery.GenericGallery' = None):
        self.metadata = {} # type: Dict[str, Metadata]
        self.gallery = gallery
        self.name = gallery.name

    def get_metadata(self, metadata: 'MetadataClassMap') -> 'Metadata':
        self.metadata[metadata.name] = self.metadata.get(metadata.name) or metadata.value(manager=self)
        return self.metadata[metadata.name]

    def get_value(self, key: str) -> Any:
        for entry in MetadataClassMap:
            if entry.name in self.metadata:
                value = self.get_metadata_value(entry, key)
                if value:
                    return value
        return self.DEFAULTS.get(key)

    def update_metadata(self, metadata: 'MetadataClassMap', metadata_json: Dict):
        self.get_metadata(metadata).update(new_metadata=metadata_json)

    def save(self, metadata: 'MetadataClassMap'):
        self.metadata.get(metadata.name).save()

    def save_all(self):
        for metadata in self.metadata.values(): metadata.save()

    def delete(self, metadata: 'MetadataClassMap'):
        self.get_metadata(metadata=metadata).delete()
        self.metadata.pop(metadata.name)

    def delete_all(self):
        for metadata in self.metadata.values(): metadata.delete()
        self.metadata = {}

    def load_metadata_from_json(self, metadata: 'MetadataClassMap', metadata_json: Dict):
        self.metadata[metadata.name] = metadata.value(self, json=metadata_json)

    def get_metadata_value(self, metadata: 'MetadataClassMap', key: str) -> Any:
        return getattr(self.get_metadata(metadata), key, None)

    def update_metadata_value(self, metadata: 'MetadataClassMap', key: str, value: Any):
        self.get_metadata(metadata).update_value(key=key, value=value)

    def get_customize_json(self) -> List[Dict]:
        return [self.get_metadata(metadata).get_customize_json() for metadata in MetadataClassMap]

    def update_from_ui_metadata(self, ui_metadata: QtQml.QJSValue) -> bool:
        """
        Updates all metadata objects managed by this object with new values from ui_metadata
        :param ui_metadata: Value from QML containing new metadata
        :return: boolean saying if any WebMetadata have changed their urls a valid value
        """

        webmetadata_url_changed = False
        for db_name, metadata in ui_metadata.toVariant().items():
            for key, value in metadata.items():
                if not hasattr(self.get_metadata(MetadataClassMap[db_name]), key):
                    continue
                if key == "tags":
                    value = Utils.convert_csv_to_list(value)
                elif key == "url" and isinstance(self.get_metadata(MetadataClassMap[db_name]),
                        WebMetadata) and value and value != self.get_metadata_value(MetadataClassMap[db_name], "url"):
                    webmetadata_url_changed = True
                self.update_metadata_value(MetadataClassMap[db_name], key, value)
        for metadata in list(self.metadata.values()):
            if isinstance(metadata, WebMetadata) and not metadata.url:
                self.metadata.pop(metadata.DB_NAME)
                metadata.delete()
        return webmetadata_url_changed

    def has_metadata(self, metadata: 'MetadataClassMap') -> bool:
        return any(True for k in self.get_metadata(metadata).json if k != "auto")

    def metadata_collection_enabled(self) -> bool:
        for metadata in self.metadata.values():
            auto_collection = getattr(metadata, "auto_collection", None)
            if auto_collection is not None and not auto_collection:
                return False
        return True

    @property
    def all_tags(self):
        return list(set(tag.lower() for metadata in self.metadata.values() for tag in metadata.tags))

    @property
    def gallery(self) -> 'PandaViewer.gallery.GenericGallery':
        return self._gallery()

    @gallery.setter
    def gallery(self, value: 'PandaViewer.gallery.GenericGallery'):
        self._gallery = weakref.ref(value)


class Metadata(Logger):
    DB_NAME = None
    GALLERY_URL = None
    json = None
    _manager = None


    def __repr__(self):
        return "%s: %s" % (self.manager.gallery, self.DB_NAME)

    def __init__(self, manager: MetadataManager, json: Dict = None):
        self.json = json or {}
        self.manager = manager
        self.db_id = self.json.pop("id", None)

    @classmethod
    def clean_metadata(cls, metadata) -> Dict:
        if isinstance(metadata, dict):
            metadata = {key: cls.clean_metadata(metadata[key])
                        for key in metadata}
        elif isinstance(metadata, list):
            metadata = [cls.clean_metadata(val) for val in metadata]
        elif isinstance(metadata, str):
            metadata = re.sub("&#039;", "'", metadata)
            metadata = re.sub("&quot;", "\"", metadata)
            metadata = re.sub("(&amp;)", "&", metadata)
            #metadata = re.sub("&#(\d+)(;|(?=\s))", "", metadata)
        return metadata

    def update(self, new_metadata: Dict):
        new_metadata = self.clean_metadata(new_metadata)
        for key in new_metadata:
            self.json[key] = new_metadata[key]

    def update_value(self, key: str, value: Any):
            getattr(self, key)
            setattr(self, key, value)

    def save(self):
        if self.db_id is None:
            self.create()
        else:
            self.logger.info("{SELF} saving metadata".format(SELF=self))
            with user_database.get_session(self, acquire=True) as session:
                session.execute(update(user_database.Metadata).where(user_database.Metadata.id == self.db_id).values(
                    {
                        "json": self.str_json,
                    }
                ))

    def create(self):
        self.logger.info("{SELF} creating db entry".format(SELF=self))
        with user_database.get_session(self, acquire=True) as session:
            result = session.execute(insert(user_database.Metadata).values(
                {
                    "json": self.str_json,
                    "name": self.DB_NAME,
                    "gallery_id": self.manager.gallery.db_id,
                }
            ))
            self.db_id = int(result.inserted_primary_key[0])

    def delete(self):
        self.logger.info("{SELF} deleting db entry".format(SELF=self))
        with user_database.get_session(self, acquire=True) as session:
            session.execute(delete(user_database.Metadata).where(
                user_database.Metadata.id == self.db_id
            ))
        self.db_id = None

    def get_customize_json(self):
        raise NotImplementedError

    @property
    def manager(self) -> MetadataManager:
        return self._manager()

    @manager.setter
    def manager(self, value: MetadataManager):
        self._manager = weakref.ref(value)

    @property
    def str_json(self) -> str:
        return str(json.dumps(self.clean_metadata(self.json), ensure_ascii=False))

    @property
    def rating(self):
        raise NotImplementedError

    @property
    def tags(self):
        raise NotImplementedError

    @property
    def category(self):
        raise NotImplementedError


class GenericMetadata(Metadata):

    @property
    def rating(self) -> float:
        return float(self.json.get("rating") or 0)

    @rating.setter
    def rating(self, value: float):
        self.json["rating"] = value

    @property
    def tags(self) -> List[str]:
        return self.json.get("tags", [])

    @tags.setter
    def tags(self, value: List[str]):
        self.json["tags"] = value

    @property
    def title(self) -> str:
        return self.json.get("title", "").replace("_", " ")

    @title.setter
    def title(self, value: str):
        self.json["title"] = value

    @property
    def category(self) -> str:
        return self.json.get("category")

    @category.setter
    def category(self, value: str):
        self.json["category"] = value


class WebMetadata(Metadata):
    BASE_GALLERY_URL = None
    URL_VALIDATOR_REGEX = None
    METADATA_NAME = None


    def get_customize_json(self) -> Dict:
        return {
            "name": self.METADATA_NAME,
            "db_name": self.DB_NAME,
            "tags": Utils.convert_list_to_csv(self.tags),
            "category": self.category,
            "auto_collection": self.auto_collection,
            "url": self.url,
            "regex": self.URL_VALIDATOR_REGEX,
        }

    @property
    def auto_collection(self) -> bool:
        return self.json.get("auto", True)

    @auto_collection.setter
    def auto_collection(self, value: bool):
        self.json["auto"] = value

    @property
    def id(self):
        raise NotImplementedError

    @property
    def url(self):
        raise NotImplementedError


class CustomMetadata(GenericMetadata):
    DB_NAME = "cmetadata"


    def get_customize_json(self) -> Dict:
        return {
            "name": "Custom Metadata",
            "db_name": self.DB_NAME,
            "title": self.title,
            "tags": Utils.convert_list_to_csv(self.tags),
            "category": self.category,
        }


class ExMetadata(WebMetadata, GenericMetadata):
    DB_NAME = "gmetadata"
    BASE_GALLERY_URL = "http://exhentai.org/g/{GID}/{TOKEN}/"
    URL_VALIDATOR_REGEX = "^(https?:\/\/)?(www.)?exhentai.org\/g\/\d+\/\w+?\/?$"
    METADATA_NAME = "ExHentai Metadata"


    @property
    def id(self) -> Tuple[int, str]:
        return (self.gid, self.token)

    @property
    def gid(self) -> int:
        return self.json.get("gid")

    @gid.setter
    def gid(self, value: int):
        self.json["gid"] = value

    @property
    def token(self) -> str:
        return self.json.get("token")

    @token.setter
    def token(self, value: str):
        self.json["token"] = value

    @property
    def url(self) -> str:
        if self.gid != None and self.token:
            return self.BASE_GALLERY_URL.format(GID=self.gid, TOKEN=self.token)
        return ""

    @url.setter
    def url(self, value: str):
        if value:
            self.gid, self.token = Utils.process_ex_url(value)
        else:
            self.gid, self.token = None, None


class ChaikaMetadata(WebMetadata, GenericMetadata):
    DB_NAME = "chaikametadata"
    BASE_GALLERY_URL = "http://panda.chaika.moe/archive/{ID}/"
    URL_VALIDATOR_REGEX = "^(https?:\/\/)?panda\.chaika\.moe\/archive\/\w+?\/$"
    METADATA_NAME = "Chaika Metadata"


    @property
    def id(self):
        return self.json.get("id")

    @id.setter
    def id(self, value):
        self.json["id"] = value

    @property
    def url(self) -> str:
        if self.id:
            return self.BASE_GALLERY_URL.format(ID=self.id)
        else:
            return ""

    @url.setter
    def url(self, value: str):
        split = value.split("/")
        self.json["id"] = split[-1] if split[-1] else split[-2]


class MetadataClassMap(Enum):
    cmetadata = CustomMetadata
    gmetadata = ExMetadata
