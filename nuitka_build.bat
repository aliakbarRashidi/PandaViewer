call vcvars32.bat
nuitka --recurse-all --windows-disable-console --standalone -j 2 --improved --windows-icon=icon.ico --python-version=3.4 --show-progress --show-modules --python-flag=no_site --show-scons --verbose Program.py

