PandaViewer
=====================


Overview
---------------------
PandaViewer is a cross-platform(\*) application designed for helping you browse and manage your collections of 
manga, doujinshi, comics, and similar articles. 

* \* Only binaries for Windows are currently provided. Linux and Mac binaries will likely become available at a later date.

![img1](http://i.imgur.com/oo4v5hG.jpg)

Features
---------------------

* Directory-structure independent scanning - no matter how (un)organized your collection is, PandaViewer can import it.
* Metadata editor/support for custom metadata.
* Automated metadata collection from EX, either directly or through provided offline database.
* Ability to disable metadata collection for specific galleries/folders.
* Namespace-aware search bar with tag auto-completion.
* Sort galleries by name, read-count, last read time, time added, file path, or rating.
* Filter out galleries by rating via the rating: field. (e.g. rating:>=4 will show galleries with a rating greater than or equal to 4)

Currently we support folder galleries (i.e. loose files in a folder), ZIP/CBZ, and RAR/CBR.


Installation
---------------------
PandaViewer strives to be as cross platform as possible. However, only Windows binaries are currently provided.
Users on different platforms (OSX/Linux) should try running the program from source (see development setup).

Check the [releases page](https://github.com/seanegoodwin/PandaViewer/releases) and download the most recent one.


Development Setup
---------------------
This section details the steps needed to setup your computer to run PandaViewer directly from source
\- that is, the Python files in this repo. The steps are mostly the same whether you are using 
Windows, OSX, or Linux, although there are some platform specific steps required. 

Please note that the vast majority of development and testing is done on Windows and it is
possible that you may encounter difficulties running this on a different platform.
If you do encounter such issues, please file a bug with a description of what you were doing and what went wrong.


Notes: 

* For Linux users - You will want to download most of these through your distro's repos. 
* For Windows/OSX users - If no specific download is provided, use Google.

Steps:

1. Install Python. PandaViewer only runs on the latest version of Python3 (3.5). 
Python2 or older versions of Python3 are not supported. 
If you are on Windows, I recommend downloading the 32-bit version, not the 64-bit one.

1. Install Qt. PandaViewer makes use of open source edition of Qt 5.4.
It can be found [here](http://www.qt.io/download-open-source/)

1. Clone PandaViewer to your computer. The best way to do this is using Git with the command:

        git clone https://github.com/seanegoodwin/PandaViewer

1. Install Python dependencies. PandaViewer uses a number of third party Python libraries. The best
way to install these is to use Pip and the requirements.txt file in the PandaViewer directory.

    Note - If you have Python2 installed make sure you are using the correct version of Pip; you might need need to use pip3 explicitly.

        pip install -r requirements.txt
    
    
 
1. Install PyQt5. PyQt is a set of bindings that allow Python code (e.g. PandaViewer) to call Qt
library code (C++). While technically a part of the previous section, 
PyQt is complex enough the warrant its own section. 

    * For Linux users - Check if PyQt5 is available from your disto's repos. If it is, install it
    and skip this section.
    
    PyQt must be built from source. To do this, you will need a compiler.

       * For Linux users - You will want to use GCC as your compiler. You may already have it installed - 
       check with your distro otherwise.
       * For OSX users - You will want to use Clang. You may have this installed already, otherwise download and install
         XCode.
       * For Windows users - You will want to use MSVC2013 for this. I believe MinGW can also work, but I have no
         experience with it.
         
    You will need to download and install SIP before you can build PyQt.
    SIP can be found [here](https://riverbankcomputing.com/software/sip/download)
    Open a terminal prompt (Windows users will want to use VS2013 x86 Native Tools Command Prompt), extract SIP,
    navigate to its folder, and build it.

        python configure.py
        make
        make install

    Windows users using MSVC will want to use `nmake` instead of `make`.
    
    When this is done, download the PyQt5 source from 
    [here](https://www.riverbankcomputing.com/software/pyqt/download5) and build it just like SIP.

1. Install unRAR. PandaViewer requires an unrar library to be installed in order to interact with 
RAR files. 

    * For OSX users - The default unrar provided should work.
    * For Linux users - Check your distro's repo for an "unrar" package. 
    * For Windows users - Download [this](http://www.rarlab.com/rar/UnRARDLL.exe) and extract it to 
      somewhere in your PATH. Alternatively, you can place the dll in the same directory as PandaViewer.
      
1. You should now be able to run PandaViewer from source. You can start it by running the `Program.py` file.

   
Compiling
---------------------
TODO


Licensing
---------------------
PandaViewer is licensed under version three of the GNU General Public License v3. 
The details of the license can be found in the LICENSE file.

A number of third party libraries and tools are used by PandaViewer. 
A list of them and their respective licenses can be found in the THIRD_PARTY_LICENSES file.

The Windows builds are distributed with an UnRAR DLL.
Program icon provided by - http://polkaparadise.deviantart.com/art/FREE-Panda-icon-352383477
