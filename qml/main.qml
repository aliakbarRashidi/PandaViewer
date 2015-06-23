import QtQuick 2.4
import QtQuick.Controls 1.3
import QtQuick.Layouts 1.1
import Material 0.1
import Material.Extras 0.1
import Material.ListItems 0.1 as ListItem

ApplicationWindow {
    id: mainWindow
    title: "PandaViewer"

    theme {
        primaryColor: Palette.colors["blue"]["500"]
        primaryDarkColor: Palette.colors["blue"]["700"]
        accentColor: Palette.colors["blue"]["500"]
        tabHighlightColor: "white"
    }

    property bool scanningModeOn: false
    property bool searchModeOn: false
    property bool duplicateScanOn: false
    width: Units.dp(16 * 5) + Units.dp(200 * 4) + Units.dp(1)

    signal scanningModeSet(var mode)
    function setScanningMode(val) {
        scanningModeOn = val
        scanningModeSet(val)
    }

    function setDuplicateScanMode(mode) {
        duplicateScanOn = mode
    }

    function setSearchMode(mode) {
        searchModeOn = mode
        if (!mode) {
            metadataSnackbar.opened = false
        }
    }

    function setPageCount(pageCount) {
        mainWindow.numPages = pageCount
    }

    function setPage(page) {
        mainWindow.currentPage = page
    }

    function setCurrentMetadataGallery(galleryName) {
        metadataSnackbar.open("Getting metadata for " + galleryName)

    }

    signal setSortMethod(int sortType, int reversed)
    signal setSearchText(string searchText)
    signal saveSettings(var settings)
    signal askForSettings
    signal setSettings(var settings)
    signal addGallery(var gallery)
    signal removeGallery(string uuid)
    signal openGallery(string uuid)
    signal openGalleryFolder(string uuid)
    signal clearGalleries
    signal setUiGallery(string uuid, var gallery)
    signal updateGalleryRating(string uuid, real rating)
    signal saveGallery(string uuid, var gallery)
    signal askForTags(var tag)
    signal scanGalleries
    signal metadataSearch(string uuid)
    signal openOnEx(string uuid)
    signal setNoSearchResults(bool noSearchResults)
    signal searchForDuplicates

    signal pageChange(int page)


    function setTags(tags) {

        for (var i = 0; i < tags.length; ++i) {
            matchingTags.append({
                                    tag: tags[i]
                                })
        }
        if (tags.length === 0) {
            autoCompleteDropdown.close()
        }
    }

    function setException(message, fatal) {
        if (exceptionDialog.visible) {
            exceptionDialog.accept()
        }
        if (fatal) {
            page.enabled = false
            page.actionBar.enabled = false
        }
        exceptionDialog.fatal = fatal
        exceptionDialog.messageText = message
        exceptionDialog.show()
    }

    property var homeSections: ["Galleries"]

    property var sections: [homeSections]

    property var sectionTitles: ["Galleries"]

    property int numPages: 1
    property int currentPage: 1
    ListModel {
        id: matchingTags
    }

    property string selectedComponent: homeSections[0]

    initialPage: Page {
        states: [
            State {
                when: scanningModeOn

                PropertyChanges {
                    target: page.actionBar
                    enabled: false
                }
            }
        ]

        id: page
        title: "PandaViewer"
        //tabs: navDrawer.enabled ? [] : sectionTitles
        tabs: []
        actionBar.maxActionCount: 6

        actions: [
            Action {
                id: backPageAction
                iconName: "awesome/arrow_left"
                name: "Previous"
                enabled: currentPage != 1
                onTriggered: pageChange(currentPage - 1)
            },

            Action {
                id: gotoPageAction
                iconName: "awesome/ellipsis_h"
                name: "Goto page"
                onTriggered: pageDialog.show()
            },

            Action {
                id: forwardsPageAction
                iconName: "awesome/arrow_right"
                name: "Next"
                enabled: currentPage != numPages
                onTriggered: pageChange(currentPage + 1)
            },

            Action {
                id: searchAction
                iconName: "action/search"
                name: "Search"
                onTriggered: searchDialog.show()
            },

            Action {
                name: "Sort"
                iconName: "content/sort"
                onTriggered: sortDialog.show()
            },

            Action {
                name: "Scan folders"
                iconName: "awesome/database"
                onTriggered: scanGalleries()
            },

            Action {
                id: metadataAction
                name: "Download metadata"
                iconName: "awesome/download"
                enabled: !searchModeOn
                onTriggered: metadataDialog.show()
            },

            Action {
                id: duplicateAction
                name: "Scan for duplicates"
                enabled: !duplicateScanOn
                iconName: "awesome/files_o"
                visible: false
                onTriggered: duplicateDialog.show()
            },

            Action {
                name: "Settings"
                iconName: "action/settings"
                onTriggered: pageStack.push(Qt.resolvedUrl("Settings.qml"))
            }
        ]


        TabView {
            id: tabView
            anchors.fill: parent
            currentIndex: page.selectedTab
            model: sections

            delegate: Item {
                width: tabView.width
                height: tabView.height
                clip: true

                property string selectedComponent: modelData[0]

                Flickable {
                    id: flickable
                    anchors {
                        fill: parent
                    }
                    clip: true
                    boundsBehavior: Flickable.DragOverBounds
                    contentHeight: Math.max(example.implicitHeight + 40, height)
                    Keys.onDownPressed: console.log("Test")
                    Loader {
                        id: example
                        onLoaded: example.forceActiveFocus()
                        anchors.fill: parent
                        asynchronous: false

                        MouseArea {
                            anchors.fill: parent
                            acceptedButtons: Qt.ForwardButton | Qt.BackButton
                            onClicked: {
                                if (mouse.button == Qt.ForwardButton
                                        && forwardsPageAction.enabled) {
                                    pageChange(currentPage + 1)
                                } else if (mouse.button == Qt.BackButton
                                           && backPageAction.enabled) {
                                    pageChange(currentPage - 1)
                                }
                            }
                        }

                        visible: status == Loader.Ready
                        source: {
                            return Qt.resolvedUrl("%.qml").arg(
                                        selectedComponent)
                        }
                    }

                    ProgressCircle {
                        anchors.centerIn: parent
                        visible: example.status == Loader.Loading
                    }
                }
                Scrollbar {
                    flickableItem: flickable
                }
            }
        }
    }

    Dialog {
        id: searchDialog
        title: "Search"
        positiveButtonText: "Search"
        property int start: 0
        property int end: 0

        TextField {
            id: searchText
            placeholderText: "Search..."
            anchors {
                left: parent.left
                right: parent.right
            }
            Keys.onReturnPressed: {
                proccessEnter()
            }

            function findWord() {
                matchingTags.clear()
                var nextSpace = searchText.text.indexOf(
                            " ", searchText.cursorPosition)
                searchDialog.end = nextSpace == -1 ? searchText.text.length : nextSpace
                var substr = searchText.text.substring(0, searchDialog.end)
                searchDialog.start = substr.lastIndexOf(" ")
                searchDialog.start = searchDialog.start
                        == 0 ? searchDialog.start : searchDialog.start + 1

                var word = searchText.text.substring(searchDialog.start,
                                                     searchDialog.end)
                mainWindow.askForTags(word)
            }
            function proccessEnter() {
                if (autoCompleteDropdown.visible) {
                    addTag()
                    autoCompleteDropdown.close()
                } else {
                    searchDialog.accepted()
                }
            }

            function addTag() {
                var first = searchText.text.substring(0, searchDialog.start)
                var end = searchText.text.substring(searchDialog.end,
                                                    searchText.text.length)
                searchText.text = first + listView.currentItem.text + end
            }

            onTextChanged: {
                var lastIsSpace = searchText.text.substring(
                            searchText.text.length - 1) == " "
                if (searchText.text.length != 0 && !lastIsSpace) {
                    autoCompleteDropdown.open(searchText, 0, searchText.height)
                    findWord()
                } else {
                    autoCompleteDropdown.close()
                }
            }

            Keys.onTabPressed: {
                autoCompleteDropdown.view.incrementCurrentIndex()
            }

            Keys.onDownPressed: autoCompleteDropdown.view.incrementCurrentIndex(
                                    )
            Keys.onUpPressed: autoCompleteDropdown.view.decrementCurrentIndex()
        }

        Dropdown {
            id: autoCompleteDropdown
            property alias view: listView
            width: searchText.width

            Rectangle {
                anchors.fill: parent
                radius: Units.dp(2)
            }

            height: listView.height

            ListView {
                id: listView
                anchors {
                    left: parent.left
                    right: parent.right
                    top: parent.top
                    //topMargin: Units.dp(8)
                }

                height: contentHeight
                keyNavigationWraps: true
                model: matchingTags

                delegate: ListItem.Standard {
                    id: item
                    text: tag
                    selected: listView.currentItem == item
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        onEntered: listView.currentIndex = index
                        onPositionChanged: listView.currentIndex = index
                        onClicked: {
                            searchText.addTag()
                            autoCompleteDropdown.close()
                        }
                    }
                }
            }
        }

        Component.onCompleted: searchText.forceActiveFocus()
        Keys.onEscapePressed: rejected()

        onAccepted: {
            setSearchText(searchText.text)
            autoCompleteDropdown.close()
            searchDialog.close()
        }

        onRejected: {
            autoCompleteDropdown.close()
            searchDialog.close()
        }
    }

    Dialog {
        id: pageDialog
        title: "Goto page"
        positiveButtonText: "Go"
        positiveButtonEnabled: pageText.acceptableInput

        TextField {
            id: pageText
            anchors {
                left: parent.left
                right: parent.right
            }

            placeholderText: "Enter 1 to " + mainWindow.numPages
            validator: IntValidator {
                bottom: 1
                top: mainWindow.numPages
            }
            hasError: !acceptableInput
            Keys.onReturnPressed: pageDialog.accepted()
            focus: true
        }

        onAccepted: {
            pageChange(pageText.text)
            pageDialog.close()
        }
    }

    Dialog {
        id: exceptionDialog
        title: "Whoops"
        Component.onCompleted: negativeButton.visible = false
        property alias messageText: label.text
        property bool fatal: true
        positiveButtonText: fatal ? "Quit" : "Ok"

        Label {
            id: label
            anchors {
                left: parent.left
                right: parent.right
            }
            wrapMode: Text.WordWrap
            text: "Replace me"
            textFormat: Text.RichText
        }

        function accept() {
            accepted()
        }

        Keys.onEscapePressed: accepted()
        onRejected: accepted()

        onAccepted: {
            if (fatal) {
                Qt.quit()
            }

            close()
        }
    }

    Dialog {
        id: duplicateDialog
        title: "Scan for duplicates"

        Label {
            anchors {
                left: parent.left
                right: parent.right
            }

            text: "This will try to find any duplicate galleries in your collection.\n\nIf any are found, they will automatically be brought to your attention."
            wrapMode: Text.WordWrap
        }
        onAccepted: searchForDuplicates()

    }

    Dialog {
        id: metadataDialog
        title: "Download metadata"

        Label {
            anchors {
                left: parent.left
                right: parent.right
            }

            text: "This will search through all of your galleries and try to find a matching gallery on EX.\n\nYou are strongly advised not to browse EX while this is running as sending too many requests can result in a ban."
            wrapMode: Text.WordWrap
        }
        onAccepted: metadataSearch(-1)
    }

    Dialog {
        id: sortDialog
        title: "Sort by"
        positiveButtonText: "Sort"

        onAccepted: {
            setSortMethod(sortType.current.sortValue,
                          sortMode.current.sortValue)
        }

        Grid {
                ExclusiveGroup {
                    id: sortType
                }

                ExclusiveGroup {
                    id: sortMode
                }
            Column {

                Repeater {
                    model: [["Name", 0], ["Read Count", 1], ["Last Read", 2], ["Rating", 3], ["Date Added", 4]]

                    delegate: RadioButton {
                        checked: modelData[1] === 0
                        text: modelData[0]
                        property int sortValue: modelData[1]
                        exclusiveGroup: sortType
                    }
                }
            }

            Column {
                Repeater {
                    model: [["Ascending", 0], ["Descending", 1]]

                    delegate: RadioButton {
                        checked: modelData[1] === 0
                        text: modelData[0]
                        property int sortValue: modelData[1]
                        exclusiveGroup: sortMode
                    }
                }
            }
        }
    }

    Snackbar {
        id: metadataSnackbar
        duration: 1000000
        buttonText: "Dismiss"
        onClicked: visible = false
        fullWidth: true


    }






}
