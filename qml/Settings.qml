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
        setSettings()
    }

    function saveSettings() {
        mainWindow.settings["folders"] = []
        mainWindow.settings["folder_metadata_map"] = {}
        mainWindow.settings["exPassHash"] = exPassHash.value
        mainWindow.settings["exUserID"] = exUserID.value
        for (var i = 0; i < folderModel.count; ++i) {
            var folder = folderModel.get(i)
            mainWindow.settings["folders"].push(folder.folderPath)
            mainWindow.settings["folder_metadata_map"][folder.folderPath] = folder.metadataEnabled
        }
        mainWindow.saveSettings(mainWindow.settings)
    }

    function setSettings() {
        exPassHash.value = mainWindow.settings["exPassHash"]
        exUserID.value = mainWindow.settings["exUserID"]
        for (var i = 0; i < mainWindow.settings["folders"].length; ++i) {
            var folder = mainWindow.settings["folders"][i]
            var metadataEnabled = mainWindow.settings["folder_metadata_map"][folder]
            galleriesTab.addFolder(folder, metadataEnabled)
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


//                        Label {
//                            anchors {
//                                left: parent.left
//                            }
//                            text: "Path"
//                            color: Theme.light.subTextColor
//                            style: "body1"
//                        }

//                        Label {
//                            anchors {
//                                right: parent.right
//                            }

//                            text: "Enable metadata collection          "
//                            color: Theme.light.subTextColor
//                            style: "body1"
//                        }

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
                        margins: Units.dp(8)
                    }

                    TextField {
                        id: folderText
                        text: folderPath
                        anchors {
                            left: parent.left
                            right: metadataSwitch.left
                            rightMargin: Units.dp(16)
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
                    CheckBox {
                        id: metadataSwitch
                        checked: metadataEnabled
                        text: "Metadata collection enabled"
                        anchors {
                            right: removeButton.left
                            rightMargin: Units.dp(16)
                        }

                        onCheckedChanged: {
                            folderModel.setProperty(index, "metadataEnabled", metadataSwitch.checked)
                        }
                    }

                }
            }

            function addFolder(folderPath, metadataEnabled) {
                folderModel.append({
                                       folderPath: folderPath.toString(),
                                       metadataEnabled: metadataEnabled,
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
                    galleriesTab.addFolder(cleanPath, true)
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
