from subprocess import Popen
import os
import sys
import shutil
import time
from distutils import dir_util

code_dir = os.path.abspath("../PandaViewer")
# build_dir = os.path.abspath("../build/main.dist/")
build_dir = os.path.abspath("../dist/main/")
try:
    shutil.rmtree(build_dir)
except FileNotFoundError:
    pass
# pv_dir = os.path.join(build_dir, "")
pv_dir = build_dir
dist_dir = os.path.join(os.path.abspath("../"), "PandaViewer")
remove_files = ["d.dll", "d.pdb", "qt5webkit.dll", "qt5webkitwidgets.dll", "qt5printsupport.dll", "qt5location.dll",
               "qt5sql.dll", "qt5script.dll", "qt5designer.dll", ".pyc", "qt5declarative.dll", "xml", "mf",]
# subp = Popen("nuitka_build.bat", shell=True)
subp = Popen("pyinstaller.bat", shell=True)
subp.communicate()
time.sleep(20)
shutil.rmtree(os.path.join(pv_dir, "qml/"))
dir_util.copy_tree(os.path.abspath("../copy"), build_dir)
shutil.copytree(os.path.join(code_dir, "qml/"), os.path.join(pv_dir, "qml/"))
# shutil.copy(os.path.join(code_dir, "icon.ico"), os.path.join(build_dir, "icon.ico"))
shutil.copy(os.path.join(code_dir, "unrar.dll"), os.path.join(pv_dir, "unrar.dll"))
shutil.copytree(os.path.join(code_dir, "migrate_repo"), os.path.join(pv_dir, "migrate_repo/"))
for base_folder, folders, files in os.walk(build_dir):
    for f in files:
        for d in remove_files:
            if d in f:
                os.remove(os.path.join(base_folder, f))
                break


os.rename(os.path.join(build_dir, "main.exe"), os.path.join(build_dir, "PandaViewer.exe"))
os.rename(build_dir, dist_dir)
