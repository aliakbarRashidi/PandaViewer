import QtQuick 2.0
import QtQuick.Controls 1.3
import QtQuick.Layouts 1.1
import Material 0.1
import Material.ListItems 0.1 as ListItem



ListItem.Standard {
    text: "Replace me!"
    property alias value: textField.text

    id: item
    secondaryItem: TextField {
        id: textField
        width: Units.dp(300)
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter

    }
}


