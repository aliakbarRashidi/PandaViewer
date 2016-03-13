call vcvars32.bat
cd ../
nuitka --standalone -j 2 --improved  --windows-icon=icon.ico --output-dir=build --explain-imports --show-modules main.py

