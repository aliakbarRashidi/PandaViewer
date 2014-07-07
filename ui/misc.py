#!/usr/bin/python2
import os
from PySide import QtCore, QtGui

class C_QTextEdit(QtGui.QTextEdit):
    clicked = QtCore.Signal()
    def __init__(self, parent=None):
        super(C_QTextEdit, self).__init__(parent)
        self.setReadOnly(True)
        
    def mousePressEvent(self, event):
        self.clicked.emit()

class C_QFileDialog(QtGui.QFileDialog):
    def __init__(self, parent=None):
        super(C_QFileDialog, self).__init__(parent)
        self.open_clicked = False
        self.setOption(self.DontUseNativeDialog, True)
        self.setFileMode(self.ExistingFiles)
        buttons = self.findChildren(QtGui.QPushButton)
        self.openButton = [x for x in buttons if "open" in str(
            x.text()).lower()][0]
        self.openButton.clicked.disconnect()
        self.openButton.clicked.connect(self.openClicked)
        self.tree = self.findChild(QtGui.QTreeView)
        self.setOption(QtGui.QFileDialog.ShowDirsOnly)

    def openClicked(self):
        inds = self.tree.selectionModel().selectedIndexes()
        files = []
        for i in inds:
            if i.column() == 0:
                files.append(os.path.join(str(self.directory().absolutePath()),
                                          str(i.data())))
        self.selectedFiles = files
        self.hide()
        self.open_clicked = True

    def filesSelected(self):
        return self.selectedFiles