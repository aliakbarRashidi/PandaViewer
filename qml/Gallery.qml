import QtQuick 2.4
import QtQuick.Controls 1.3
import QtQuick.Layouts 1.1
import Material 0.1
import Material.ListItems 0.1 as ListItem
import Material.Extras 0.1


Card {
    id: galleryCard
    height: Units.dp(350)
    width: Units.dp(200)
    flat: false
    property bool customizationEnabled: true

    anchors {
        margins: 0
    }

    function updateRating(newRating) {
        mainWindow.updateGalleryRating(dbUUID, newRating)
    }

    function removeGallery() {
        mainWindow.removeGallery(dbUUID)
    }

    function openGallery() {
        mainWindow.openGallery(dbUUID)
    }

    function openGalleryFolder() {
        mainWindow.openGalleryFolder(dbUUID)
    }

    function exAction(needMetadata) {
        if (needMetadata) {
            mainWindow.metadataSearch(dbUUID)
        } else {
            mainWindow.openOnEx(dbUUID)
        }
    }

    Label {
        id: titleText
        anchors {
            horizontalCenter: parent.horizontalCenter
            //top: parent.top
            bottom: bottomRow.top
            margins: Units.dp(8)
        }

        text: title
        width: parent.width - anchors.margins
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight

        Tooltip {
            text: titleText.text
            mouseArea: textMouseArea
        }

        MouseArea {
            id: textMouseArea
            anchors.fill: parent
            hoverEnabled: true
        }
    }
    states: [
        State {
            name: "imageLoading"
            when: galleryImage.status == Image.Loading
            PropertyChanges {
                target: galleryImage
            }
        }
    ]

    Image {
        Tooltip {
            text: tooltip
            mouseArea: imageMouseArea
            implicitHeight: Units.dp(16) * tooltipLines
        }

        MouseArea {
            id: imageMouseArea
            anchors.fill: parent
            hoverEnabled: true
            onClicked: openGallery()

            cursorShape: Qt.OpenHandCursor
        }

        id: galleryImage

        source: image
        smooth: true
        cache: true
        sourceSize.width: 200
        asynchronous: true
        anchors {
            //horizontalCenter: parent.horizontalCenter
            //verticalCenter: parent.verticalCenter
            top: parent.top
            left: parent.left
            right: parent.right
        }

        width: Units.dp(200)
        height: Math.min(Units.dp(300), implicitHeight)
    }
    Rectangle {
        id: bottomRow
        height: Units.dp(16)
        anchors {
            bottom: parent.bottom
            margins: Units.dp(8)
            right: parent.right
            left: parent.left
        }

        IconButton {
            id: button
            iconName: "awesome/ellipsis_v"
            size: Units.dp(16)
            anchors {
                right: parent.right
                verticalCenter: parent.verticalCenter
            }

            function openDropdown() {
                menuDropdown.open(button, 0, button.height)
            }

            //Can't assign directly for some reason
            Component.onCompleted: button.clicked.connect(button.openDropdown)
        }

        StarRating {
            id: starRating
            currentRating: rating
            anchors {
                left: parent.left
                verticalCenter: parent.verticalCenter
            }
        }

        Component.onCompleted: {
            starRating.starClicked.connect(updateRating)
        }
    }

    Dropdown {
        id: menuDropdown
        property alias view: listView
        width: Units.dp(200)
        height: listView.childrenRect.height

        data: Column {
            id: listView

            anchors {
                fill: parent
            }

            ListItem.Standard {
                visible: customizationEnabled
                id: editItem
                text: "Info"
                onClicked: {

                    //Here be deep magic
                    menuDropdown.close()
                    pageStack.push(Qt.resolvedUrl("CustomizeGallery.qml"), {
                                     gallery: galleryModel.get(index)
                                   })

                }
            }


            ListItem.Standard {
                text: "Delete"
                onClicked: {
                    menuDropdown.close()
                    removeGallery()
                }
            }

            ListItem.Standard {
                text: "Open folder"
                onClicked: {
                    menuDropdown.close()
                    openGalleryFolder()
                }
            }


            ListItem.Standard {
                property bool needMetadata: !hasMetadata
                text: needMetadata ? "Download metadata" : "View on EX"
                onClicked: {
                    menuDropdown.close()
                    exAction(needMetadata)
                }
            }
        }
    }

}
