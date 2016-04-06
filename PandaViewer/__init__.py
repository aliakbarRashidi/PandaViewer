import os
import sys
#sys.stdout = open("stdout.txt", "w")
#sys.stderr = open("stderr.txt", "w")
import logging
from PyQt5 import QtCore
from time import strftime
from .utils import Utils
from .logger import Logger

# Setup application-wide logging
if not os.path.exists(Utils.convert_from_relative_lsv_path()):
    os.mkdir(Utils.convert_from_relative_lsv_path())
log_dir = Utils.convert_from_relative_path("logs")
if not os.path.exists(log_dir):
    os.mkdir(log_dir)
filename = os.path.join(log_dir, strftime("%Y-%m-%d-%H.%M.%S") + ".log")
logging.basicConfig(handlers=[logging.FileHandler(filename, 'w', 'utf-8')],
                    format="%(asctime)s: %(name)s %(levelname)s %(message)s",
                    level=logging.DEBUG)
qt_logger = Logger()
qt_logger.name = "Qt logger"
def message_handler(kind, context, msg):
    print(msg)
    qt_logger.logger.info(msg)
QtCore.qInstallMessageHandler(message_handler) # Connections qml/qt stream to logging method

#  Windows specific setup requirements
if os.name == "nt":
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("pv.test") # Required for Windows 7+
    os.environ["UNRAR_LIB_PATH"] = Utils.convert_from_relative_path("unrar.dll")

# Qt app setup
from . import metadata, gallery, program, threads
app = program.Program(sys.argv)

#  Flask setup
sys.excepthook = app.exception_hook
threads.setup()
app.setup()
