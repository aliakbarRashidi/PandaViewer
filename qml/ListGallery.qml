import QtQuick 2.5
import QtQuick.Layouts 1.2
import Material 0.1
import Material.ListItems 0.1 as ListItem
import Material.Extras 0.1


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
