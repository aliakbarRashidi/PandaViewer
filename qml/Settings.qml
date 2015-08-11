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
        mainWindow.settings["folder_options"] = {

        }
        mainWindow.settings["ex_pass_hash"] = exPassHash.value
        mainWindow.settings["ex_member_id"] = exUserID.value
        mainWindow.settings["confirm_delete"] = confirmDeleteSwitch.checked

        mainWindow.settings["extract_zip"] = extractZipSwitch.checked
        mainWindow.settings["extract_cbz"] = extractCbzSwitch.checked
        mainWindow.settings["extract_rar"] = extractRarSwitch.checked
        mainWindow.settings["extract_cbr"] = extractCbrSwitch.checked



        for (var i = 0; i < folderModel.count; ++i) {
            var folder = folderModel.get(i)
            mainWindow.settings["folders"].push(folder.folderPath)
            var folderOptions = {}
            folderOptions["auto_metadata"] = folder.metadataEnabled
            mainWindow.settings["folder_options"][folder.folderPath] = folderOptions
        }
        mainWindow.saveSettings(mainWindow.settings)
    }

    function setSettings() {
        exPassHash.value = mainWindow.settings["ex_pass_hash"]
        exUserID.value = mainWindow.settings["ex_member_id"]
        confirmDeleteSwitch.checked = mainWindow.settings["confirm_delete"]

        extractZipSwitch.checked = mainWindow.settings["extract_zip"]
        extractCbzSwitch.checked = mainWindow.settings["extract_cbz"]
        extractRarSwitch.checked = mainWindow.settings["extract_rar"]
        extractCbrSwitch.checked = mainWindow.settings["extract_cbr"]

        for (var i = 0; i < mainWindow.settings["folders"].length; ++i) {
            var folder = mainWindow.settings["folders"][i]
            var metadataEnabled = true
            var folderOptions = mainWindow.settings["folder_options"][folder]
            if (folderOptions !== undefined) {
                metadataEnabled = folderOptions["auto_metadata"]
            }
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
                    text: "General"
                }

                ListItem.Subtitled {
                    text: "Enable gallery deletion confirmation"
                    secondaryItem: Switch {
                        id: confirmDeleteSwitch
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    onClicked: confirmDeleteSwitch.checked = !confirmDeleteSwitch.checked
                }

                ListItem.Subheader {
                    text: "Archives"
                }

                ListItem.Subtitled {
                    text: "Extract Zip files before opening"
                    secondaryItem: Switch {
                        id: extractZipSwitch
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    onClicked: extractZipSwitch.checked = !extractZipSwitch.checked

                }
                ListItem.Subtitled {
                    text: "Extract Cbz files before opening"
                    secondaryItem: Switch {
                        id: extractCbzSwitch
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    onClicked: extractCbzSwitch.checked = !extractCbzSwitch.checked

                }
                ListItem.Subtitled {
                    text: "Extract Rar files before opening"
                    secondaryItem: Switch {
                        id: extractRarSwitch
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    onClicked: extractRarSwitch.checked = !extractRarSwitch.checked

                }
                ListItem.Subtitled {
                    text: "Extract Cbr files before opening"
                    secondaryItem: Switch {
                        id: extractCbrSwitch
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    onClicked: extractCbrSwitch.checked = !extractCbrSwitch.checked

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
                            folderModel.setProperty(index, "metadataEnabled",
                                                    metadataSwitch.checked)
                        }
                    }
                }
            }

            function addFolder(folderPath, metadataEnabled) {
                folderModel.append({
                                       folderPath: folderPath.toString(),
                                       metadataEnabled: metadataEnabled
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
