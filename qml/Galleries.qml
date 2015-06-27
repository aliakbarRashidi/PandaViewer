import QtQuick 2.4
import QtQuick.Controls 1.3
import QtQuick.Layouts 1.1
import Material 0.1

Item {
    id: galleriesPage
    property bool scanningMode: false
    property bool noSearchResults: false
    ListModel {
        id: galleryModel
    }
    ProgressCircle {
        id: progressCircle
        anchors.centerIn: parent
        visible: false
    }

    Component.onCompleted: {
        mainWindow.addGallery.connect(galleriesPage.addGallery)
        mainWindow.removeGallery.connect(galleriesPage.removeGallery)
        mainWindow.scanningModeSet.connect(galleriesPage.setScanningMode)
        mainWindow.clearGalleries.connect(galleriesPage.clearGalleries)
        mainWindow.setUiGallery.connect(galleriesPage.setGallery)
        mainWindow.setNoSearchResults.connect(galleriesPage.setNoSearchResults)
    }

    function addGallery(gallery) {
        galleryModel.append(gallery)
    }

    function removeGallery(uuid) {
        galleryModel.remove(getIndexFromUUID(uuid))
    }

    function clearGalleries() {
        galleryModel.clear()
    }

    function getIndexFromUUID(uuid) {
        for (var i = 0; i < galleryModel.count; ++i) {
            if (galleryModel.get(i).dbUUID === uuid) {
                return i
            }
        }
    }

    function setGallery(uuid, gallery) {
        galleryModel.set(getIndexFromUUID(uuid), gallery)
    }

    function setNoSearchResults(noResults) {
        galleriesPage.noSearchResults = noResults
    }

    function setScanningMode(mode) {
        galleriesPage.scanningMode = mode
    }

    states: [
        State {
            when: galleriesPage.scanningMode

            PropertyChanges {
                target: centerMessage
                visible: false
            }

            PropertyChanges {
                target: galleryContent
                visible: false
            }

            PropertyChanges {
                target: progressCircle
                visible: true
            }
        },

        State {
            when: galleriesPage.noSearchResults
            PropertyChanges {
                target: progressCircle
                visible: false
            }
            PropertyChanges {
                target: centerMessage
                visible: true
            }

            PropertyChanges {
                target: galleryContent
                visible: false
            }

            PropertyChanges {
                target: messageLabel
                text: "Your search returned zero results."
            }

            PropertyChanges {
                target: messageIcon
                name: "awesome/search"
            }
        },

        State {
            when: galleryModel.count == 0
            PropertyChanges {
                target: progressCircle
                visible: false
            }
            PropertyChanges {
                target: centerMessage
                visible: true
            }

            PropertyChanges {
                target: galleryContent
                visible: false
            }

            PropertyChanges {
                target: messageLabel
                text: "Sorry, we couldn't find any galleries.\nPlease ensure you've added folders to your settings page and have scanned folders."
            }

            PropertyChanges {
                target: messageIcon
                name: "awesome/warning"
            }
        },

        State {
            when: !galleriesPage.scanningMode
            PropertyChanges {
                target: progressCircle
                visible: false
            }
            PropertyChanges {
                target: centerMessage
                visible: false
            }

            PropertyChanges {
                target: galleryContent
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
            text: ""
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }
    }

    GridView {
        id: galleryContent
        focus: true
        boundsBehavior: Flickable.DragOverBounds
        anchors {
            top: parent.top
            bottom: parent.bottom
            right: parent.right
            left: parent.left
            topMargin: Units.dp(16)
            leftMargin: Units.dp(16)
        }

        //width: parent.width

        //        columns: parseInt(content.width / Units.dp(200 + 16)) || 1
        //        rowSpacing: 0
        //        columnSpacing: 0
        cellWidth: Units.dp(200 + 16)
        cellHeight: Units.dp(350 + 16)

        model: galleryModel
        cacheBuffer: 4000

        delegate: Component {
            Gallery {
                id: gallery
            }
        }

        //        Repeater {
        //            id: galleryRepeater
        //            model: galleryModel
        //            delegate: Component {
        //                Gallery {
        //                id: gallery
        //            }
        //        }
        //    }
    }

    Scrollbar {
        flickableItem: galleryContent
    }
}
