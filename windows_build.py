from subprocess import Popen
import os
import sys
import shutil

build_dir = os.path.abspath("Program.dist/")
dist_dir = os.path.join(os.path.abspath("."), "PandaViewer")
remove_files = ["d.dll", "d.pdb", "qt5webkit.dll", "qt5webkitwidgets.dll", "qt5printsupport.dll", "qt5location.dll",
               "qt5sql.dll", "qt5script.dll", "qt5designer.dll", ".pyc"]
subp = Popen("nuitka_build.bat", shell=True)
subp.communicate()
shutil.copytree("qml", os.path.join(build_dir, "qml/"))
os.rename(os.path.join(build_dir, "Program.exe"), os.path.join(build_dir, "PandaViewer.exe"))
shutil.copy("icon.ico", os.path.join(build_dir, "icon.ico"))
# shutil.copy("unrar.exe", os.path.join(build_dir, "unrar.exe"))
# shutil.copy("unrar3.dll", os.path.join(build_dir, "unrar3.dll"))
shutil.copy("unrar.dll", os.path.join(build_dir, "unrar.dll"))
shutil.copytree("migrate_repo", os.path.join(build_dir, "migrate_repo/"))
for base_folder, folders, files in os.walk(build_dir):
    for f in files:
        for d in remove_files:
            if d in f:
                os.remove(os.path.join(base_folder, f))
                break


os.rename(build_dir, dist_dir)
