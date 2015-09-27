import QtQuick 2.0
import QtQuick.Controls 1.3
import QtQuick.Layouts 1.1
import Material 0.1
import Material.Extras 0.1
import Material.ListItems 0.1 as ListItem

Column {
    property var metadata
    ListItem.SectionHeader {
        id: header
        text: modelData.name

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
        height: Units.dp(8)
        visible: header.expanded
    }

    Item {
        anchors {
            left: parent.left
            right: parent.right
            margins: Units.dp(16)
        }
        visible: header.expanded

        TextField {
            anchors {
                left: parent.left
                right: parent.right
            }

            placeholderText: "Tags"
            floatingLabel: true
            text: metadata.tags
        }
    }

    ThinDivider {
        anchors {
            left: parent.left
            right: parent.right
        }
        visible: header.expanded
    }
}
