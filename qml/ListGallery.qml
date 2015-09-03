import QtQuick 2.0
import Material 0.1


Gallery {
//    anchors {
//        left: parent.left
//        right: parent.right
//    }

    height: Units.dp(100)

    GalleryListItem{
            anchors {
                fill: parent
            }
    }



    Row {
        anchors.fill: parent

        Loader {
            sourceComponent: titleTextComponent
            anchors.verticalCenter: parent.verticalCenter

        }
    }
}
