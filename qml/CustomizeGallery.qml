import QtQuick 2.4
import QtQuick.Controls 1.3
import QtQuick.Layouts 1.1
import Material 0.1
import QtQuick.Dialogs 1.2
import Material.ListItems 0.1 as ListItem

Page {
    id: customizePage

    property var gallery
    title: gallery.title

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
        mainWindow.setGallery.connect(customizePage.setGallery)
        mainWindow.setGalleryImageFolder.connect(
                    customizePage.openGalleryImageFolder)
        galleryModel.append(gallery)
    }

    Component.onDestruction: {
        mainWindow.setGallery.disconnect(customizePage.setGallery)
        mainWindow.setGalleryImageFolder.disconnect(
                    customizePage.openGalleryImageFolder)
    }

    actions: [
        Action {
            iconName: "awesome/image"
            name: "Select thumbnail"
            onTriggered: {
                mainWindow.getGalleryImageFolder(gallery.dbUUID)
            }
        },

        Action {
            iconName: "content/Save"
            name: "Save"
            enabled: !exURLField.hasError
            onTriggered: {
                save()
                mainWindow.pageStack.pop()
            }
        }
    ]
    ListModel {
        id: galleryModel
    }

    function setGallery(uuid, gallery) {
        if (gallery.dbUUID === uuid) {
            galleryModel.set(0, gallery)
        }
    }

    function openGalleryImageFolder(uuid, folder) {
        if (gallery.dbUUID === uuid) {
            imageDialog.folder = folder
            imageDialog.open()
        }
    }

    function save() {
        var galleryValues = {

        }
        galleryValues["title"] = titleField.text
        galleryValues["tags"] = tagsField.text
        galleryValues["exURL"] = exURLField.text
        galleryValues["exTags"] = exTagsField.text
        galleryValues["exAuto"] = exAutoSwitch.checked
        mainWindow.saveGallery(gallery.dbUUID, galleryValues)
    }

    ListView {
        id: galleryContent

        boundsBehavior: Flickable.StopAtBounds
        width: Units.dp(200)
        height: Units.dp(350 + 16)
        anchors {
            top: parent.top
            left: parent.left
            margins: Units.dp(16)
        }

        model: galleryModel
        delegate: Component {
            Gallery {
                id: galleryCard
                customizationEnabled: false
            }
        }
    }

    Card {
        id: statsCard
        flat: false
        visible: false

        width: Units.dp(200)

        anchors {
            left: parent.left
            top: galleryContent.bottom
            margins: Units.dp(16)
        }

        Label {
            style: "subheading"
            text: "Info"
            anchors {
                horizontalCenter: parent.horizontalCenter
            }
        }
    }

    ColumnLayout {
        anchors {
            left: galleryContent.right
            top: parent.top
            right: parent.right
            bottom: parent.bottom
            margins: Units.dp(16)
        }
        spacing: Units.dp(16)

        Label {
            style: "subheading"
            text: "Custom Metadata"
            anchors {
                horizontalCenter: parent.horizontalCenter
            }
        }

        TextField {
            id: titleField

            anchors {
                left: parent.left
                right: parent.right
            }
            placeholderText: "Custom Title"
            floatingLabel: true
            text: title

            Component.onCompleted: cursorPosition = 0
        }

        TextField {
            id: tagsField
            anchors {
                left: parent.left
                right: parent.right
            }
            text: gallery.tags
            placeholderText: "Custom Tags - Use commas to seperate"
            floatingLabel: true
            Component.onCompleted: cursorPosition = 0
        }

        Label {
            style: "subheading"
            text: "ExH Metadata"
            anchors {
                horizontalCenter: parent.horizontalCenter
            }
        }

        TextField {
            id: exTagsField
            anchors {
                left: parent.left
                right: parent.right
            }
            text: gallery.exTags
            placeholderText: "ExH Tags"
            visible: text !== ""
            floatingLabel: true
            Component.onCompleted: cursorPosition = 0
        }
        TextField {
            id: exURLField
            placeholderText: "ExH URL"
            floatingLabel: true
            anchors {
                left: parent.left
                right: parent.right
            }
            Component.onCompleted: cursorPosition = 0
            text: gallery.exURL
            onTextChanged: {
                exURLField.hasError = !/^(https?:\/\/)?(www.)?exhentai.org\/g\/\d+\/\w+?\/?$/.test(
                            exURLField.text) && exURLField.text !== ""
            }
        }

        Label {
            style: "subheading"
            text: "Options"
            anchors {
                horizontalCenter: parent.horizontalCenter
            }
        }
        ListItem.Subtitled {
            text: "Enable automatic metadata collection"
            secondaryItem: Switch {
                id: exAutoSwitch
                checked: gallery.exAuto
                anchors.verticalCenter: parent.verticalCenter
            }

            onClicked: exAutoSwitch.checked = !exAutoSwitch.checked
        }

        Label {
            style: "subheading"
            text: "Pages"
            anchors {
                horizontalCenter: parent.horizontalCenter
            }
        }

        ScrollView {
            Layout.fillHeight: true
            Layout.fillWidth: true
            __wheelAreaScrollSpeed: 100

            GridView {
                anchors.fill: parent
                cellWidth: Units.dp(200 + 16)
                cellHeight: Units.dp(300 + 16)
                model: gallery.files
                delegate: Component {
                        Image {
                            id: pageImage
                            source: modelData
                            asynchronous: true
                            width: 200
                            height: Math.min(Units.dp(300), implicitHeight)
                            sourceSize.width: 200

                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    if (mouse.button & Qt.LeftButton) {
                                        mainWindow.openGallery(gallery.dbUUID, index)
                                    }
                                }
                            }
                        }
                    }
                }
            }
    }
    FileDialog {
        id: imageDialog
        selectFolder: false
        nameFilters: ["Image files (*.jpg *.jpeg *.png)"]
        title: "Please select an image"
        onAccepted: {
            var path = imageDialog.fileUrl.toString()

            // remove prefixed "file:///"
            path = Qt.platform.os == "windows" ? path.replace(
                                                     /^(file:\/{3})/,
                                                     "") : path.replace(
                                                     /^(file:\/{2})/, "")
            // unescape html codes like '%23' for '#'
            var cleanPath = decodeURIComponent(path)
            mainWindow.setGalleryImage(gallery.dbUUID, cleanPath.toString())
        }
    }
}
