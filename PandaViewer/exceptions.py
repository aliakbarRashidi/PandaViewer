from PandaViewer.logger import Logger


class CustomBaseException(Exception, Logger):
    fatal = False
    thread_restart = False
    details = ""
    msg = ""

    def __init__(self):
        super().__init__()
        self.logger.error("%s raised with message %s.\nDetails: %s" %
                          (self.__class__.__name__, self.msg, self.details))


class BadCredentialsError(CustomBaseException):
    "Raised for incorrect/missing credentials"

    thread_restart = True
    msg = "Your user id/password hash combination is incorrect."


class UserBannedError(CustomBaseException):
    "Raised when user is banned on EX"

    thread_restart = True
    msg = "You are currently banned on EX."


class InvalidExUrl(CustomBaseException):
    "Raised when user inputs invalid ex url for a gallery"

    msg = "Sorry, the gallery URL you entered is invalid.\nPlease enter either a valid or blank URL."


class InvalidRatingSearch(CustomBaseException):
    "Raised when an incorrect rating function is given to search"

    msg = "The rating function you provided is invalid."  # TODO better wording


class UnknownArchiveError(CustomBaseException):
    msg = "Sorry, the archive file you tried to access is unable to be opened."


class UnknownArchiveErrorMessage(CustomBaseException):
    msg = """Sorry, the some archives failed to work correcrtly.
They might be broken, have invalid permissions, or be otherwise incompatible.
For more details, check the log file, or post an issue on Github."""
    def __init__(self, zips):
        self.details = "\n".join(zips)
        super().__init__()


class UnableToDeleteGalleryError(CustomBaseException):
    msg = "Sorry, the gallery %s failed to delete.\nPlease look at the log for more information."

    def __init__(self, gallery):
        self.msg = self.msg % gallery
        super().__init__()