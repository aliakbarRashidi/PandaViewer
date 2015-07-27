from Logger import Logger
import weakref

class GalleryBoilerplate(Logger): # Need to fix this shit, not scalable with additional metadata
    @property
    def parent(self):
        return self._parent()

    @parent.setter
    def parent(self, val):
        self._parent = weakref.ref(val)

    @property
    def title(self):
        title = self.ctitle or self.extitle or self.name
        return title.replace("_", " ")

    @property
    def ctitle(self):
        return self.metadata.get("cmetadata", {}).get("title", "")

    @ctitle.setter
    def ctitle(self, val):
        self.metadata["cmetadata"] = self.metadata.get("cmetadata", {})
        self.metadata["cmetadata"]["title"] = val

    @property
    def extitle(self):
        return self.metadata.get("gmetadata", {}).get("title", "")

    @extitle.setter
    def extitle(self, val):
        self.metadata["gmetadata"] = self.metadata.get("gmetadata", {})
        self.metadata["gmetadata"]["title"] = val
        
    @property
    def ex_auto_collection(self):
        return self.metadata.get("gmetadata", {}).get("auto", True)

    @ex_auto_collection.setter
    def ex_auto_collection(self, val):
        self.metadata["gmetadata"] = self.metadata.get("gmetadata", {})
        self.metadata["gmetadata"]["auto"] = val

    @property
    def extags(self):
        return self.metadata.get("gmetadata", {}).get("tags", [])

    @extags.setter
    def extags(self, val):
        self.metadata["gmetadata"] = self.metadata.get("gmetadata", {})
        self.metadata["gmetadata"]["tags"] = val

    @property
    def ctags(self):
        return self.metadata.get("cmetadata", {}).get("tags", [])

    @ctags.setter
    def ctags(self, val):
        self.metadata["cmetadata"] = self.metadata.get("cmetadata", {})
        self.metadata["cmetadata"]["tags"] = val

    @property
    def tags(self):
        return list(map(lambda x: x.replace(" ", "_"), set(self.extags + self.ctags)))

    @property
    def rating(self):
        return self.crating or self.exrating or 0

    @property
    def crating(self):
        return self.metadata.get("cmetadata", {}).get("rating")

    @crating.setter
    def crating(self, val):
        self.metadata["cmetadata"] = self.metadata.get("cmetadata", {})
        self.metadata["cmetadata"]["rating"] = val

    @property
    def exrating(self):
        return self.metadata.get("gmetadata", {}).get("rating")

    @exrating.setter
    def exrating(self, val):
        self.metadata["gmetadata"] = self.metadata.get("gmetadata", {})
        self.metadata["gmetadata"]["rating"] = val

    @property
    def gid(self):
        return self.metadata.get("gmetadata", {}).get("gid")

    @gid.setter
    def gid(self, val):
        self.metadata["gmetadata"] = self.metadata.get("gmetadata", {})
        self.metadata["gmetadata"]["gid"] = val

    @property
    def token(self):
        return self.metadata.get("gmetadata", {}).get("token")

    @token.setter
    def token(self, val):
        self.metadata["gmetadata"] = self.metadata.get("gmetadata", {})
        self.metadata["gmetadata"]["token"] = val

    @property
    def id(self):
        return [self.gid, self.token]

    @id.setter
    def id(self, val):
        self.gid = val[0]
        self.token = val[1]

