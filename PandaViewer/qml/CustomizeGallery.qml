import QtQuick 2.0
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
            id: saveAction
            iconName: "content/Save"
            name: "Save"
            onTriggered: {
                save()
                mainWindow.pageStack.pop()
            }
        }
    ]
    ListModel {
        id: galleryModel
    }

    ListModel {
        id: metadataModel
    }

    function setGallery(uuid, newgallery) {
        if (gallery.dbUUID === uuid) {
            galleryModel.set(0, newgallery)
        }
    }

    function openGalleryImageFolder(uuid, folder) {
        if (gallery.dbUUID === uuid) {
            imageDialog.folder = folder
            imageDialog.open()
        }
    }

    function save() {
        var new_metadata = {

        }
        var item
        for (var i = 0; i < metadataContent.metadataRepeater.count; ++i) {
            item = metadataContent.metadataRepeater.itemAt(i)
            new_metadata[item.dbName] = item.get_save_data()
        }
        mainWindow.saveGallery(gallery.dbUUID, new_metadata)
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
            GridGallery {
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

    Column {
        id: metadataContent
        property alias metadataRepeater: metadataRepeater
        anchors {
            left: galleryContent.right
            top: parent.top
            right: parent.right
            margins: Units.dp(16)
        }

        Repeater {
            id: metadataRepeater
            model: gallery.metadata
            delegate: ColumnLayout {
                id: metadataColumn
                width: parent.width
                spacing: Units.dp(8)
                property string dbName: modelData.db_name
                function get_save_data() {
                    return {
                        title: titleField.text,
                        tags: tagsField.text,
                        url: urlField.text,
                        category: categoryField.text,
                        auto_collection: autoSwitch.checked
                    }
                }

                ListItem.SectionHeader {
                    id: header
                    text: modelData.name
                    expanded: true

                    ThinDivider {
                        anchors {
                            left: parent.left
                            right: parent.right
                            top: parent.top
                        }
                        visible: header.expanded
                    }
                }

                Item {
                    width: parent.width
                    height: Units.dp(16)
                    visible: header.expanded
                }

                ColumnLayout {
                    spacing: Units.dp(16)
                    anchors {
                        top: header.bottom
                        left: parent.left
                        right: parent.right
                        margins: Units.dp(16)
                    }
                    visible: header.expanded
                    TextField {
                        id: titleField
                        enabled: modelData.hasOwnProperty("title")
                        visible: enabled
                        anchors {
                            left: parent.left
                            right: parent.right
                        }

                        placeholderText: "Title"
                        floatingLabel: true
                        text: enabled ? modelData.title : ""
                    }

                    TextField {
                        id: tagsField
                        anchors {
                            left: parent.left
                            right: parent.right
                        }

                        placeholderText: "Tags"
                        floatingLabel: true
                        text: enabled ? modelData.tags : ""
                        Component.onCompleted: cursorPosition = 0
                    }

                    TextField {
                        id: categoryField
                        enabled: modelData.hasOwnProperty("category")
                        visible: enabled
                        anchors {
                            left: parent.left
                            right: parent.right
                        }
                        placeholderText: "Category"
                        floatingLabel: true
                        text: enabled ? modelData.category : ""
                    }

                    TextField {
                        id: urlField
                        enabled: modelData.hasOwnProperty("url")
                        visible: enabled
                        anchors {
                            left: parent.left
                            right: parent.right
                        }
                        placeholderText: "URL"
                        floatingLabel: true
                        text: enabled ? modelData.url : ""
                        onTextChanged: {
                            var re = new RegExp(modelData.regex)
                            urlField.hasError = !re.test(urlField.text)
                                    && urlField.text !== ""
                            saveAction.enabled
                                    = !urlField.hasError //TODO: Fix for multiple url fields
                        }
                    }

                    ListItem.Subtitled {
                        id: metadataCollection
                        anchors {
                            left: parent.left
                            right: parent.right
                        }
                        enabled: modelData.hasOwnProperty("url")
                        visible: enabled
                        text: "Enable automatic metadata collection"
                        secondaryItem: Switch {
                            id: autoSwitch
                            checked: modelData.auto_collection
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        onClicked: autoSwitch.checked = !autoSwitch.checked
                    }
                }
                Item {
                    width: parent.width
                    height: Units.dp(16)
                    visible: header.expanded && !metadataCollection.visible
                }

                ThinDivider {
                    anchors {
                        left: parent.left
                        right: parent.right
                    }
                    visible: header.expanded
                }
            }
        }
    }

    ListItem.SectionHeader {
        id: filesHeader
        text: "Files"
        expanded: true
        anchors {
            top: metadataContent.bottom
            left: metadataContent.left
            right: metadataContent.right
        }

        ThinDivider {
            anchors {
                left: parent.left
                right: parent.right
                top: parent.top
            }
            visible: filesHeader.expanded
        }
    }
    ScrollView {
        id: scrollView
        visible: filesHeader.expanded
        Layout.fillHeight: true
        Layout.fillWidth: true
        __wheelAreaScrollSpeed: 100

        function encodeURIComponents(uri) {
            return uri.split('/').map(encodeURIComponent).join('/')
        }

        anchors {
            left: filesHeader.left
            right: filesHeader.right
            top: filesHeader.bottom
            bottom: parent.bottom
            margins: Units.dp(8)
        }

        GridView {
            anchors.fill: parent
            cellWidth: Units.dp(200 + 16)
            cellHeight: Units.dp(300 + 16)
            model: gallery.files
            cacheBuffer: cellWidth * gallery.files.length / 2
            delegate: Component {
                Image {
                    id: pageImage
                    source: "file:" + scrollView.encodeURIComponents(modelData)
                    asynchronous: index > 10
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

    ThinDivider {
        anchors {
            left: parent.left
            right: parent.right
        }
        visible: filesHeader.expanded
    }


    //    Item {
    //        width: parent.width
    //        height: Units.dp(16)
    //        visible: filesHeader.expanded
    //    }
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
