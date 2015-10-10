call vcvars32.bat
cd ../
rem nuitka --recurse-all --standalone -j 2 --improved --windows-icon=icon.ico --show-progress --show-modules --python-flag=no_site --show-scons --verbose PandaViewer/
nuitka --standalone -j 2 --improved --windows-disable-console --windows-icon=icon.ico --python-flag=no_site --output-dir=build --explain-imports --show-modules main.py

