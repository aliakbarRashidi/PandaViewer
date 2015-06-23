import QtQuick 2.4
import QtQuick.Controls 1.3
import QtQuick.Layouts 1.1
import Material 0.1

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
        mainWindow.setUiGallery.connect(customizePage.setGallery)
        galleryModel.append(gallery)
    }

    Component.onDestruction: {
        mainWindow.setUiGallery.disconnect(customizePage.setGallery)
    }

    actions: [
        Action {
            iconName: "content/Save"
            name: "Save"
            //enabled: !exURLField.hasError
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

    function save() {
        var galleryValues = {

        }
        galleryValues["title"] = titleField.text
        galleryValues["tags"] = tagsField.text
        galleryValues["exURL"] = exURLField.text
        galleryValues["exTags"] = exTagsField.text
        mainWindow.saveGallery(gallery.dbUUID, galleryValues)
    }

    ListView {
        id: galleryContent

        boundsBehavior: Flickable.StopAtBounds
        width: Units.dp(200)
        height: Units.dp(350)
        anchors {
            top: parent.top
            left: parent.left
            margins: Units.dp(16)
        }

        model: galleryModel
        delegate: Component {
            Gallery {
                id: galleryCard
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

    Column {
        anchors {
            left: galleryContent.right
            top: parent.top
            right: parent.right
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
    }
}
