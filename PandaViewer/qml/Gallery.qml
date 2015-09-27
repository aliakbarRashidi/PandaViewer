import QtQuick 2.0
import QtQuick.Controls 1.3
import QtQuick.Layouts 1.1
import Material 0.1
import Material.ListItems 0.1 as ListItem
import Material.Extras 0.1

Item {
    property bool customizationEnabled: true
    property bool hasMetadata: galleryHasMetadata
    property alias titleTextComponent: titleTextComponent
    property alias categoryTextComponent: categoryTextComponent
    property alias galleryMouseArea: galleryMouseArea
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

    function processDelete() {
                        if (mainWindow.settings["confirm_delete"]) {
                            confirmDeleteDialogLoader.sourceComponent = confirmDeleteDialogComponent
                            confirmDeleteDialogLoader.item.show()
                        } else {
                            removeGallery()
                        }
    }

    Loader {
        id: galleryTooltipLoader
    }

    Component {
        id: titleTextComponent
        Label {
            id: titleText
            text: title
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            maximumLineCount: 2
            wrapMode: Text.Wrap

            Loader {
                id: titleTooltipLoader
            }
            Component {
                id: titleTooltipComponent
                Tooltip {
                    text: titleText.text
                    mouseArea: textMouseArea
                }
            }

            MouseArea {
                id: textMouseArea
                anchors.fill: parent
                hoverEnabled: true
                onEntered: titleTooltipLoader.sourceComponent = titleTooltipComponent
                onPositionChanged: titleTooltipLoader.sourceComponent = titleTooltipComponent
                onExited: titleTooltipLoader.sourceComponent = undefined
                onClicked: openGallery()
            }
        }
    }

    Component {
        id: categoryTextComponent
        Label {
            text: category
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    Component {
        id: galleryTooltipComponent
        Tooltip {
            text: tooltip
            textFormat: Text.RichText

            mouseArea: galleryMouseArea
            //            Component.onCompleted: timer.start()
        }
    }

    MouseArea {
        id: galleryMouseArea
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        anchors.fill: parent
        hoverEnabled: true
        onEntered: galleryTooltipLoader.sourceComponent = galleryTooltipComponent
        onPositionChanged: galleryTooltipLoader.sourceComponent = galleryTooltipComponent
        onExited: galleryTooltipLoader.sourceComponent = undefined
        onClicked: {
            if (mouse.button & Qt.LeftButton) {
                openGallery()
            } else if (mouse.button & Qt.RightButton) {
                menuLoader.sourceComponent = menuComponent
                menuLoader.item.open(galleryMouseArea, mouseX, mouseY)
            }
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
                        processDelete()
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
                    visible: !hasMetadata
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
