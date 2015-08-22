import QtQuick 2.4
import QtQuick.Controls 1.3
import QtQuick.Layouts 1.1
import Material 0.1
import Material.ListItems 0.1 as ListItem
import Material.Extras 0.1

Card {
    id: galleryCard
    height: Units.dp(350 + 16)
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
        mainWindow.openGallery(dbUUID, 0)
    }

    function openGalleryFolder() {
        mainWindow.openGalleryFolder(dbUUID)
    }

    Loader {
        id: galleryTooltipLoader
        asynchronous: false
    }

    Component {
        id: galleryTooltipComponent
        Tooltip {
            text: tooltip
            mouseArea: imageMouseArea
            Component.onCompleted: start()
            height: Units.dp((40 - 16) + (16 * tooltipLines))
        }
    }

    MouseArea {
        id: imageMouseArea
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        anchors.fill: parent
        hoverEnabled: true
        onEntered: galleryTooltipLoader.sourceComponent = galleryTooltipComponent
        onPositionChanged: galleryTooltipLoader.sourceComponent = galleryTooltipComponent
        onExited: galleryTooltipLoader.source = ""
        onClicked: {
            if (mouse.button & Qt.LeftButton) {
                openGallery()
            } else if (mouse.button & Qt.RightButton) {
                menuLoader.sourceComponent = menuComponent
                menuLoader.item.open(imageMouseArea, mouseX, mouseY)
            }
        }
    }

    Image {
        id: galleryImage

        source: image
        cache: false
        sourceSize.width: 200
        asynchronous: false
        anchors {
            top: parent.top
            left: parent.left
            right: parent.right
        }

        width: Units.dp(200)
        height: Math.min(Units.dp(300), implicitHeight)
    }

    Label {
        id: titleText
        anchors {
            horizontalCenter: parent.horizontalCenter
            bottom: bottomRow.top
            //            bottom: parent.bottom
            margins: Units.dp(8)
        }

        text: title
        width: parent.width - anchors.margins
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        maximumLineCount: 2
        wrapMode: Text.Wrap

        Loader {
            id: titleTooltipLoader
            asynchronous: false
        }
        Component {
            id: titleTooltipComponent
            Tooltip {
                text: titleText.text
                mouseArea: textMouseArea
                Component.onCompleted: start()
            }
        }

        MouseArea {
            id: textMouseArea
            anchors.fill: parent
            hoverEnabled: true
            onEntered: titleTooltipLoader.sourceComponent = titleTooltipComponent
            onPositionChanged: titleTooltipLoader.sourceComponent = titleTooltipComponent
            onExited: titleTooltipLoader.source = ""
        }
    }

    Item {
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
                menuLoader.sourceComponent = menuComponent
                menuLoader.item.open(button, button.width, button.height)
            }

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

    Loader {
        id: menuLoader
    }

    Component {
        id: menuComponent
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
                        menuDropdown.close()
                        mainWindow.getDetailedGallery(dbUUID)
                        //                        pageStack.push(Qt.resolvedUrl("CustomizeGallery.qml"), {
                        //                                           gallery: galleryModel.get(index)
                        //                                       })
                    }
                }

                ListItem.Standard {
                    text: "Delete"
                    onClicked: {
                        menuDropdown.close()
                        if (mainWindow.settings["confirm_delete"]) {
                            confirmDeleteDialogLoader.sourceComponent = confirmDeleteDialogComponent
                            confirmDeleteDialogLoader.item.show()
                        } else {
                            removeGallery()
                        }
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
                    text: "Download metadata"
                    onClicked: {
                        menuDropdown.close()
                        mainWindow.metadataSearch(dbUUID)
                    }
                }

                ListItem.Standard {
                    visible: hasMetadata
                    text: "View on EX"
                    onClicked: {
                        menuDropdown.close()
                        mainWindow.openOnEx(dbUUID)
                    }
                }
            }
        }
    }

    Loader {
        id: confirmDeleteDialogLoader
        asynchronous: false
    }

    Component {
        id: confirmDeleteDialogComponent
        Dialog {
            id: confirmDeleteDialog
            title: "Confirm deletion"
            positiveButtonText: "Delete"
            Label {
                anchors {
                    left: parent.left
                    right: parent.right
                }

                text: "This will delete the gallery from your harddrive.\n\nYou will be able to restore it from your OS's recyling bin if needed."
                wrapMode: Text.WordWrap
            }
            onAccepted: removeGallery()
        }
    }
}
