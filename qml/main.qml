import QtQuick 2.5
import QtQuick.Controls 1.3
import QtQuick.Layouts 1.2
import Qt.labs.settings 1.0
import Material 0.1
import Material.Extras 0.1
import Material.ListItems 0.1 as ListItem

ApplicationWindow {
    id: mainWindow
    title: "PandaViewer - Page " + currentPage + " of " + numPages

    theme {
        primaryColor: Palette.colors["blue"]["500"]
        primaryDarkColor: Palette.colors["blue"]["700"]
        accentColor: Palette.colors["blue"]["500"]
        tabHighlightColor: "white"
    }

    Settings {
        property alias x: mainWindow.x
        property alias y: mainWindow.y
        property alias width: mainWindow.width
        property alias height: mainWindow.height
    }

    property bool scanningModeOn: false
    property bool searchModeOn: false
    width: Units.dp(16 * 5) + Units.dp(200 * 4) + Units.dp(1) + Units.dp(16)

    onClosing: {
        closedUI()
        close.accepted = false
    }
    Component.onDestruction: closedUI()

    signal scanningModeSet(var mode)
    function setScanningMode(val) {
        scanningModeOn = val
        scanningModeSet(val)
        if (!scanningModeOn) {
            snackbar.opened = false
        }
    }

    function setSearchMode(mode) {
        searchModeOn = mode
        if (!mode) {
            snackbar.opened = false
        }
    }

    function setPageCount(pageCount) {
        mainWindow.numPages = pageCount
    }

    function setPage(page) {
        mainWindow.currentPage = page
    }

    function setCurrentMetadataGallery(galleryName) {
        snackbar.open("Getting metadata for " + galleryName)
    }

    signal scanGalleries
    signal metadataSearch(string uuid)

    signal setSortMethod(int sortType, int reversed)
    signal setSearchText(string searchText)

    signal saveSettings(var settings)

    signal removeGallery(string uuid)
    signal openGallery(string uuid, int index)
    signal openGalleryFolder(string uuid)

    signal getGalleryImageFolder(string uuid)
    signal setGalleryImageFolder(string uuid, string path)
    signal setGalleryImage(string uuid, string path)

    signal setGallery(string uuid, var gallery)
    signal updateGalleryRating(string uuid, real rating)
    signal saveGallery(string uuid, var gallery)
    signal askForTags(var tag)
    signal openOnEx(string uuid)
    signal setNoSearchResults(bool noSearchResults)
    signal searchForDuplicates

    signal pageChange(int page)

    signal setUIGallery(int index, var gallery, bool resetScroll)
    signal removeUIGallery(int index, int count)
    signal getDetailedGallery(string uuid)
    signal setUISort(int sortType, int reversed)
    signal setDisplayModeToGrid(bool gridMode)
    signal closedUI

    signal openDetailedGallery(var gallery)

    function garbageCollect() {
//        gc()
    }

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

    function setScanFolder(folder) {
        snackbar.open("Scanning " + folder)
    }

    function setSettings(settings) {
        mainWindow.settings = settings
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

    property var settings: {
        ""
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
        id: page
        states: [
            State {
                when: scanningModeOn

                PropertyChanges {
                    target: page.actionBar
                    enabled: false
                }
            }
        ]

        title: "PandaViewer"
        tabs: []
        actionBar.maxActionCount: 6
        actionBar.extendedContent: Rectangle {
            id: searchContainer
            visible: false
            property int start: 0
            property int end: 0
            anchors {
                left: parent.left
                right: parent.right
                margins: 0
            }
            color: Palette.colors["blue"]["500"]
            height: visible ? Units.dp(32) : 0

            function toggle() {
                visible = !visible && enabled
                searchText.forceActiveFocus()
            }

            function accept() {
                setSearchText(searchText.text)
                autoCompleteDropdown.close()
            }



            Card {
                id: searchCard
                anchors {
                    left: parent.left
                    right: parent.right
                    leftMargin: Units.dp(4)
                    rightMargin: Units.dp(4)
                    topMargin: 0
                    bottomMargin: Units.dp(4)
                }

                height: Units.dp(24)

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
                        searchContainer.end = nextSpace == -1 ? searchText.text.length : nextSpace
                        var substr = searchText.text.substring(
                                    0, searchContainer.end)
                        searchContainer.start = substr.lastIndexOf(" ")
                        searchContainer.start = searchContainer.start
                                == 0 ? searchContainer.start : searchContainer.start + 1

                        var word = searchText.text.substring(
                                    searchContainer.start, searchContainer.end)
                        mainWindow.askForTags(word)
                    }
                    function proccessEnter() {
                        if (autoCompleteDropdown.visible && autoCompleteDropdown.view.count > 0) {
                            addTag()
                            autoCompleteDropdown.close()
                        } else {
                            searchContainer.accept()
                        }
                    }

                    function addTag() {
                        var first = searchText.text.substring(
                                    0, searchContainer.start)
                        var end = searchText.text.substring(
                                    searchContainer.end, searchText.text.length)
                        searchText.text = first + listView.currentItem.text + end
                    }

                    onTextChanged: {
                        var lastIsSpace = searchText.text.substring(
                                    searchText.text.length - 1) == " "
                        if (searchText.text.length != 0 && !lastIsSpace) {
                            autoCompleteDropdown.open(searchText, 0,
                                                      searchText.height)
                            findWord()
                        } else {
                            autoCompleteDropdown.close()
                        }
                    }

                    Keys.onTabPressed: {
                        autoCompleteDropdown.view.incrementCurrentIndex()
                    }

                    Keys.onDownPressed: autoCompleteDropdown.view.incrementCurrentIndex()
                    Keys.onUpPressed: autoCompleteDropdown.view.decrementCurrentIndex()
                }

                Dropdown {
                    id: autoCompleteDropdown
                    property alias view: listView
                    width: searchText.width
                    height: listView.height

                    ListView {
                        id: listView
                        anchors {
                            left: parent.left
                            right: parent.right
                            top: parent.top
                        }
                        spacing: Units.dp(4)

                        height: contentHeight
                        keyNavigationWraps: true
                        model: matchingTags

                        delegate: ListItem.Standard {
                            id: item
                            text: tag
                            height: Units.dp(24)
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
            }
        }

        actions: [
            Action {
                id: backPageAction
                iconName: "navigation/arrow_back"
                name: "Previous"
                enabled: currentPage != 1
                onTriggered: pageChange(currentPage - 1)
            },

            Action {
                iconName: "navigation/more_horiz"
                name: "Goto page"
                //                onTriggered: pageDialog.show()
                enabled: numPages > 1
                onTriggered: {
                    pageDialog.show()
//                    gotoPageDropdownLoader.sourceComponent = gotoPageDropdownComponent
//                    gotoPageDropdownLoader.item.open(page.actionBar, -1 * ((8 * Units.dp(24))), page.actionBar.height)
                }
            },

            Action {
                id: forwardsPageAction
                iconName: "navigation/arrow_forward"
                name: "Next"
                enabled: currentPage != numPages
                onTriggered: pageChange(currentPage + 1)
            },

            Action {
                id: searchAction
                iconName: "action/search"
                name: "Search"
                shortcut: "Ctrl+F"
                onTriggered: searchContainer.toggle()
            },

            Action {
                name: "Sort"
                iconName: "content/sort"
                onTriggered: sortDialog.show()
            },

//            Action {
//                name: gridMode ? "List" : "Grid"
//                property bool gridMode: true
//                iconName: gridMode ? "action/view_list" : "action/view_module"

//                onTriggered: {
//                    gridMode = !gridMode
//                    mainWindow.setDisplayModeToGrid(gridMode)
//                }

//            },

            Action {
                name: "Find new galleries"
                iconName: "awesome/database"
                onTriggered: scanGalleries()
            },

            Action {
                id: metadataAction
                name: "Download metadata"
                iconName: "file/file_download"
                enabled: !searchModeOn
                onTriggered: metadataDialog.show()
            },

            Action {
                id: duplicateAction
                name: "Delete duplicates"
                iconName: "awesome/files_o"
                onTriggered: duplicateDialog.show()
            },

            Action {
                name: "Settings"
                iconName: "action/settings"
                onTriggered: pageStack.push(Qt.resolvedUrl("Settings.qml"))
            }
        ]

        backAction: navDrawer.action
        NavigationDrawer {
            id: navDrawer
            enabled: false
            visible: enabled

            Keys.onEscapePressed: navDrawer.close()
            Flickable {
                anchors.fill: parent
                enabled: page.actionBar.enabled
                contentHeight: Math.max(content.implicitHeight, height)

                Column {
                    id: content
                    anchors.fill: parent

                    ListItem.Standard {
                        action: Icon {
                            size: Units.dp(32)

                        }
                    }

                }
            }
        }

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
                    Loader {
                        id: example

                        anchors.fill: parent
                        asynchronous: false

                        MouseArea {
                            anchors.fill: parent
                            acceptedButtons: Qt.ForwardButton | Qt.BackButton
                            onClicked: {
                                mouse.accepted = true
                                if (mouse.button == Qt.ForwardButton
                                        && page.actionBar.enabled
                                        && forwardsPageAction.enabled) {
                                    pageChange(currentPage + 1)
                                } else if (mouse.button == Qt.BackButton
                                           && page.actionBar.enabled
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

    Loader {
        id: gotoPageDropdownLoader
        asynchronous: false
    }

    Component {
        id: gotoPageDropdownComponent
        Dropdown {
            id: gotoPageDropdown
            property alias view: listView
            width: Units.dp(100)
            height: listView.childrenRect.height < Units.dp(mainWindow.height /2) ?
                        listView.childrenRect.height : Units.dp(mainWindow.height /2)
            data: ListView {
                id: listView
                anchors.fill: parent
                model: numPages
                delegate: ListItem.Standard {
                    text: modelData + 1
                    onClicked: {
                        pageChange(text)
                        gotoPageDropdown.close()
                    }
                }
            }
        }
    }

    Dialog {
        id: pageDialog
        title: "Goto page"
        positiveButtonText: "Go"
        positiveButtonEnabled: pageText.acceptableInput
        Component.onCompleted: {
            pageText.forceActiveFocus()
        }

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
        property alias messageText: exceptionLabel.text
        property bool fatal: true
        positiveButtonText: fatal ? "Quit" : "Ok"

        Label {
            id: exceptionLabel
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
        dismissOnTap: false

        onAccepted: {
            if (fatal) {
                mainWindow.close()
            }

            close()
        }
    }

    Dialog {
        id: duplicateDialog
        title: "Delete duplicates"
        positiveButtonText: "Delete duplicates"

        Label {
            anchors {
                left: parent.left
                right: parent.right
            }

            text: "This will try to find and delete any duplicate galleries in your collection.\nAny deleted galleries will be moved to your OS's trash incase you wish to restore them."
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

        CheckBox {
            id: forceAll
            text: "Redownload metadata for all galleries"
        }

        onAccepted: metadataSearch(forceAll.checked ? -1 : 0)
    }

    Dialog {
        id: sortDialog
        title: "Sort by"
        positiveButtonText: "Sort"

        Component.onCompleted: {
            mainWindow.setUISort.connect(sortGrid.setUISort)
        }

        onAccepted: {
            setSortMethod(sortType.current.sortValue,
                          sortMode.current.sortValue)
        }

        Grid {
            id: sortGrid
            ExclusiveGroup {
                id: sortType
            }

            ExclusiveGroup {
                id: sortMode
            }

            function setUISort(sortType, sortMode) {
                for (var i = 0; i < typeRepeater.model.length; ++i) {
                    if (i === sortType) {
                        typeRepeater.itemAt(i).checked = true
                        break
                    }
                }
                for (var i = 0; i < modeRepeater.model.length; ++i) {
                    if (i === sortMode) {
                        modeRepeater.itemAt(i).checked = true
                        break
                    }
                }
            }

            Column {
                Repeater {
                    id: typeRepeater
                    model: [["Name", 0], ["Read Count", 1], ["Last Read", 2], ["Rating", 3], ["Date Added", 4], ["File Path", 5]]

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
                    id: modeRepeater
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
        id: snackbar
        duration: 1000000
        buttonText: "Dismiss"
        onClicked: visible = false
        fullWidth: true
    }
}
