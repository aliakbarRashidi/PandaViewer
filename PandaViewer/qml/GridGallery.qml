import QtQuick 2.0
import QtQuick.Controls 1.3
import QtQuick.Layouts 1.1
import Material 0.1

Gallery {
    id: gallery
    //    height: Units.dp(350 + 16)
    height: Units.dp(280)
    width: Units.dp(200)

    Component.onCompleted: {
        galleryMouseArea.anchors.fill = gallery
    }

    Card {
        anchors.fill: parent
        Image {
            id: galleryImage

            source: image
            cache: false
            //            sourceSize.width: 200
            asynchronous: false
            anchors {
                top: parent.top
                left: parent.left
                right: parent.right
            }
            fillMode: Image.PreserveAspectCrop

            width: Units.dp(200)
            //            height: Math.min(Units.dp(280), implicitHeight)
            height: Units.dp(280)
        }

        Connections {
            target: galleryMouseArea
            onEntered: {
                galleryRectLoader.sourceComponent = galleryRectComponent
                galleryActionsLoader.sourceComponent = galleryActionsComponent
                galleryRectLoader.item.state = "loaded"
                galleryActionsLoader.item.state = "loaded"
            }

            onPositionChanged: {
                galleryRectLoader.sourceComponent = galleryRectComponent
                galleryActionsLoader.sourceComponent = galleryActionsComponent
                galleryRectLoader.item.state = "loaded"
                galleryActionsLoader.item.state = "loaded"
            }

            onExited: {
                loaderTimer.start()
            }
        }

        Loader {
            id: galleryActionsLoader
            anchors {
                left: galleryImage.left
                right: galleryImage.right
                top: galleryImage.top
            }
        }

        Loader {
            id: galleryRectLoader
            anchors {
                left: galleryImage.left
                right: galleryImage.right
                bottom: galleryImage.bottom
            }
        }
        Timer {
            id: loaderTimer
            interval: 1
            onTriggered: {
                if (!galleryRectLoader.item.containsMouse
                        && !galleryMouseArea.containsMouse
                        && !galleryActionsLoader.item.containsMouse) {
                    galleryRectLoader.item.state = "unloaded"
                    galleryActionsLoader.item.state = "unloaded"
                }
            }
        }

        Component {
            id: galleryActionsComponent

            Rectangle {
                id: galleryActions
                height: 0
                color: Qt.rgba(0.2, 0.2, 0.2, 0.9)
                property real maxHeight: Units.dp((40 - 16) + (16 * 1))
                property alias containsMouse: galleryActionsMouseArea.containsMouse
                state: "unloaded"
                states: [
                    State {
                        name: "unloaded"
                    },

                    State {
                        name: "loaded"
                    }
                ]

                transitions: [
                    Transition {
                        from: "unloaded"
                        to: "loaded"
                        animations: [
                            NumberAnimation {
                                target: parent
                                property: "height"
                                to: galleryActions.maxHeight
                                duration: 200
                                easing.type: Easing.InOutQuad
                            }
                        ]
                    },
                    Transition {
                        from: "loaded"
                        to: "unloaded"
                        NumberAnimation {
                            target: parent
                            property: "height"
                            to: 0
                            duration: 200
                            easing.type: Easing.InOutQuad
                        }
                        onRunningChanged: {
                            if (!running) {
                                galleryRectLoader.sourceComponent = undefined
                            }
                        }
                    }
                ]

                MouseArea {
                    id: galleryActionsMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    onExited: loaderTimer.start()

                    Row {
                        visible: parent.height === galleryActions.maxHeight
                        spacing: Units.dp(16)
//                        spacing: (width - Units.dp(16) - (4 * Units.dp(24)))/3
                        anchors {
                            margins: Units.dp(8)
                            top: parent.top
                            bottom: parent.bottom
                            horizontalCenter: parent.horizontalCenter
//                            verticalCenter: parent.verticalCenterr
                        }

                        IconButton {
                            color: Theme.dark.iconColor
                            size: Units.dp(24)
                            action: Action {
                                name: "Info"
                                iconName: "action/info"
                                onTriggered: mainWindow.getDetailedGallery(dbUUID)
                            }
                        }

                        IconButton {
                            color: Theme.dark.iconColor
                            size: Units.dp(24)
                            action: Action {
                                name: "Delete"
                                iconName: "action/delete"
                                onTriggered: gallery.processDelete()
                            }
                        }
                        IconButton {
                            color: Theme.dark.iconColor
                            size: Units.dp(24)
                            action: Action {
                                name: "Open folder"
                                iconName: "file/folder"
                                onTriggered: gallery.openGalleryFolder()
                            }
                        }
                        IconButton {
                            color: Theme.dark.iconColor
                            size: Units.dp(24)
                            visible: !gallery.hasMetadata
                            action: Action {
                                name: "Download metadata"
                                iconName: "file/cloud_download"
                                onTriggered: mainWindow.metadataSearch(dbUUID)
                            }
                        }
                        IconButton {
                            color: Theme.dark.iconColor
                            size: Units.dp(24)
                            visible: gallery.hasMetadata
                            action: Action {
                                name: "View online"
                                iconName: "action/open_in_browser"
                                onTriggered: mainWindow.openOnEx(dbUUID)
                            }
                        }


                    }

                }
            }
        }


        Component {
            id: galleryRectComponent
            Rectangle {
                id: galleryRect
                property real maxHeight: Units.dp((40 - 16) + (16 * 3))
                height: 0
                color: Qt.rgba(0.2, 0.2, 0.2, 0.9)
                property alias containsMouse: galleryRectMouseArea.containsMouse

                state: "unloaded"
                states: [
                    State {
                        name: "unloaded"
                    },

                    State {
                        name: "loaded"
                    }
                ]

                transitions: [
                    Transition {
                        from: "unloaded"
                        to: "loaded"
                        animations: [
                            NumberAnimation {
                                target: parent
                                property: "height"
                                to: galleryRect.maxHeight
                                duration: 200
                                easing.type: Easing.InOutQuad
                            }
                        ]
                    },
                    Transition {
                        from: "loaded"
                        to: "unloaded"
                        NumberAnimation {
                            target: parent
                            property: "height"
                            to: 0
                            duration: 200
                            easing.type: Easing.InOutQuad
                        }
                        onRunningChanged: {
                            if (!running) {
                                galleryRectLoader.sourceComponent = undefined
                            }
                        }
                    }
                ]

                MouseArea {
                    id: galleryRectMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    onExited: loaderTimer.start()

                    Loader {
                        sourceComponent: gallery.titleTextComponent
                        anchors {
                            margins: Units.dp(8)
                            horizontalCenter: parent.horizontalCenter
                            top: parent.top
                        }
                        width: parent.width - anchors.margins
                        onLoaded: {
                            item.style = "tooltip"
                            item.color = Theme.lightDark(galleryRect.color,
                                                         Theme.light.textColor,
                                                         Theme.dark.textColor)
                        }
                    }

                    Item {
                        height: Units.dp(16)
                        visible: parent.height === galleryRect.maxHeight
                        anchors {
                            margins: Units.dp(8)
                            left: parent.left
                            right: parent.right
                            bottom: parent.bottom
                        }

                        StarRating {
                            id: starRating
                            starColor: Theme.dark.iconColor
                            currentRating: rating
                            anchors {
                                left: parent.left
                                verticalCenter: parent.verticalCenter
                                bottom: parent.bottom
                            }
                        }
                        Loader {
                            sourceComponent: gallery.categoryTextComponent
                            anchors {
                                bottom: parent.bottomm
                                verticalCenter: parent.verticalCenter
                                right: parent.right
                            }
                            onLoaded: {
                                item.style = "tooltip"
                                item.color = Theme.lightDark(galleryRect.color,
                                                         Theme.light.textColor,
                                                         Theme.dark.textColor)
                            }
                        }
                    }

                    Component.onCompleted: {
                        starRating.starClicked.connect(updateRating)
                    }
                }
            }
        }
    }
}
