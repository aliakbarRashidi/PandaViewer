import QtQuick 2.0
import QtQuick.Controls 1.3
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
            sourceSize.width: 200
            asynchronous: false
            anchors {
                top: parent.top
                left: parent.left
                right: parent.right
            }

            width: Units.dp(200)
            //            height: Math.min(Units.dp(280), implicitHeight)
            height: Units.dp(280)
        }

        Connections {
            target: galleryMouseArea
            onEntered: {
                galleryRectLoader.sourceComponent = galleryRectComponent
                galleryRectLoader.item.state = "loaded"
            }

            onPositionChanged: {
                galleryRectLoader.sourceComponent = galleryRectComponent
                galleryRectLoader.item.state = "loaded"
            }

            onExited: {
                loaderTimer.start()
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
                        && !galleryMouseArea.containsMouse) {
                    galleryRectLoader.item.state = "unloaded"
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
                            item.color = Theme.dark.textColor
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
                    }

                    Component.onCompleted: {
                        starRating.starClicked.connect(updateRating)
                    }
                }
            }
        }

        //        Loader {
        //            sourceComponent: gallery.titleTextComponent
        //            anchors {
        //                margins: Units.dp(8)
        //                horizontalCenter: parent.horizontalCenter
        //                bottom: bottomRow.top
        //            }
        //            width: parent.width - anchors.margins
        //        }

        //        Item {
        //            id: bottomRow
        //            height: Units.dp(16)
        //            anchors {
        //                bottom: parent.bottom
        //                margins: Units.dp(8)
        //                right: parent.right
        //                left: parent.left
        //            }
        //            IconButton {
        //                id: button
        //                iconName: "awesome/ellipsis_v"
        //                size: Units.dp(16)
        //                anchors {
        //                    right: parent.right
        //                    verticalCenter: parent.verticalCenter
        //                }

        //                function openDropdown() {
        //                    menuLoader.sourceComponent = menuComponent
        //                    menuLoader.item.open(button, button.width, button.height)
        //                }

        //                Component.onCompleted: button.clicked.connect(
        //                                           button.openDropdown)
        //            }

        //            StarRating {
        //                id: starRating
        //                currentRating: rating
        //                anchors {
        //                    left: parent.left
        //                    verticalCenter: parent.verticalCenter
        //                }
        //            }

        //            Component.onCompleted: {
        //                starRating.starClicked.connect(updateRating)
        //            }
        //        }
    }
}
