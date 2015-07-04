import QtQuick 2.0
import QtQuick.Controls 1.3
import QtQuick.Layouts 1.1
import Material 0.1
import Material.Extras 0.1

import QtQuick.Dialogs 1.0
import Material.ListItems 0.1 as ListItem

Page {
    id: page
    title: "Settings"
    property bool settingsChanged: false

    actions: [
        Action {
            iconName: "content/Save"
            name: "Save"
            onTriggered: {
                page.saveSettings()
                mainWindow.pageStack.pop()

            }
        }
    ]
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.BackButton
        onClicked: {
            if (mouse.button == Qt.BackButton) {
                mainWindow.pageStack.pop()
            }
        }
    }

    Component.onCompleted: {
        mainWindow.setSettings.connect(setSettings)
        mainWindow.askForSettings()
    }

    function saveSettings() {
        var settings = {

        }
        settings["folders"] = []
        settings["exPassHash"] = exPassHash.value
        settings["exUserID"] = exUserID.value
        for (var i = 0; i < folderModel.count; ++i) {
            var folder = folderModel.get(i)
            settings["folders"].push(folder.folderPath)
        }
        mainWindow.saveSettings(settings)
    }

    function setSettings(settings) {
        exPassHash.value = settings["exPassHash"]
        exUserID.value = settings["exUserID"]
        for (var i = 0; i < settings["folders"].length; ++i) {
            galleriesTab.addFolder(settings["folders"][i])
        }
    }

    tabs: ["General", "Folders"]

    TabView {
        id: tabView
        anchors.fill: parent
        currentIndex: page.selectedTab
        model: tabs
    }

    VisualItemModel {
        id: tabs

        Rectangle {
            width: tabView.width
            height: tabView.height


            Column {
                anchors {
                    fill: parent
                    margins: Units.dp(16)
                }

            ListItem.Subheader {
                text: "ExH Settings"
            }
                SettingsItem {
                    id: exUserID
                    text: "ExH User ID"
                }

                SettingsItem {
                    id: exPassHash
                    text: "ExH Password Hash"
                }
            }
        }

        Rectangle {
            id: galleriesTab
            width: tabView.width
            height: tabView.height

            ListModel {
                id: folderModel
            }

            states: [
                State {
                    when: folderModel.count === 0
                    PropertyChanges {
                        target: folderView
                        visible: false
                    }

                    PropertyChanges {
                        target: messageLabel
                        text: "No folders found.\nClick the button in the bottom right to add folders to scan."
                    }
                    PropertyChanges {
                        target: centerMessage
                        visible: true

                    }
                }
            ]

            Column {
                id: centerMessage
                visible: false
                anchors.centerIn: parent

                Icon {
                    id: messageIcon
                    anchors.horizontalCenter: parent.horizontalCenter
                    name: "awesome/warning"
                    size: Units.dp(100)
                }

                Label {
                    id: messageLabel
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: ""
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                }
            }

            ListView {
                id: folderView

                anchors {
                    fill: parent
                    margins: Units.dp(16)
                }
                model: folderModel
                delegate: RowLayout {
                    id: row
                    anchors {
                        left: parent.left
                        right: parent.right
                    }

                    TextField {
                        id: folderText
                        text: folderPath
                        anchors {
                            left: parent.left
                            right: removeButton.left
                        }
                        onTextChanged: folderModel.setProperty(index,
                                                               "folderPath",
                                                               text)
                    }

                    Button {
                        id: removeButton
                        anchors {
                            right: parent.right
                        }

                        text: "Remove"
                        onClicked: folderModel.remove(index)
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
            }

            function addFolder(folderPath) {
                folderModel.append({
                                       folderPath: folderPath.toString()
                                   })
            }

            FileDialog {
                id: fileDialog
                selectFolder: true
                title: "Please select a folder"
                onAccepted: {
                    var path = fileDialog.fileUrl.toString()

                    // remove prefixed "file:///"
                    path = Qt.platform.os == "windows" ? path.replace(
                                                             /^(file:\/{3})/,
                                                             "") : path.replace(
                                                             /^(file:\/{2})/,
                                                             "")
                    // unescape html codes like '%23' for '#'
                    var cleanPath = decodeURIComponent(path)
                    galleriesTab.addFolder(cleanPath)
                }
            }

            ActionButton {
                id: addGallery
                anchors {
                    right: parent.right
                    bottom: parent.bottom
                    margins: Units.dp(32)
                }
                iconName: "content/add"
                onClicked: fileDialog.open()
            }
        }
    }
}
