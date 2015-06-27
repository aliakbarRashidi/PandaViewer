import QtQuick 2.4
import QtQuick.Controls 1.3
import QtQuick.Layouts 1.1
import Material 0.1

RowLayout {
    id: layout
    spacing: 0
    property real currentRating
    signal starClicked(real rating)

    onCurrentRatingChanged: starRepeater.currentStarValue = currentRating

    Repeater {
        id: starRepeater
        model: [1, 2, 3, 4, 5]
        property real currentStarValue: currentRating
        property string fullStar: "awesome/star"
        property string halfStar: "awesome/star_half_full"
        property string noStar: "awesome/star_o"

        delegate: Icon {
            id: starIcon
            property int starNum: modelData
            name: starRepeater.noStar
            size: Units.dp(16)

            //color: theme.accentColor
            states: [
                State {
                    when: (starIcon.starNum <= starRepeater.currentStarValue)
                    PropertyChanges {
                        target: starIcon
                        name: starRepeater.fullStar
                    }
                },

                State {
                    when: Math.round(
                              starRepeater.currentStarValue) == Math.floor(
                              starIcon.starNum)
                    PropertyChanges {
                        target: starIcon
                        name: starRepeater.halfStar
                    }
                },

                State {
                    PropertyChanges {
                        target: starIcon
                        name: starRepeater.noStar
                    }
                }
            ]

            Repeater {
                model: [0, 1]

                delegate: MouseArea {
                    property bool leftArea: modelData == 0
                    anchors {
                        top: parent.top
                        bottom: parent.bottom
                        left: leftArea ? parent.left : parent.horizontalCenter
                        right: leftArea ? parent.horizontalCenter : parent.right
                    }
                    hoverEnabled: true
                    Tooltip {
                        text: "Rating: " + currentRating
                        mouseArea: parent
                    }
                    onEntered: {
                        starRepeater.currentStarValue
                                = leftArea ? starIcon.starNum - .5 : starIcon.starNum
                    }
                    onExited: starRepeater.currentStarValue = currentRating
                    onClicked: {
                        mouse.accepted = true
                        starClicked(starRepeater.currentStarValue)
                    }
                }
            }
        }
    }
}
