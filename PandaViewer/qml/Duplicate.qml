import QtQuick 2.4
import QtQuick.Controls 1.3
import QtQuick.Layouts 1.1
import Material 0.1
import Material.Extras 0.1



Page {
    id: duplicatePage
    property int numGalleries: 0

    ListModel {
        id: galleryModel
    }

    Component.onCompleted: {
        mainWindow.setUiGallery.connect(galleriesPage.setGallery)
    }


    function close() {
        mainWindow.pageStack.pop()
    }

    function getNextPage() {

    }



    function getIndexFromUUID(uuid) {
        for (var i = 0; i < galleryModel.count; ++i) {
            if (galleryModel.get(i).dbUUID === uuid) {
                return i
            }
        }
    }

    function clearGalleries() {
        galleryModel.clear()
    }

    function addGallery(gallery) {
        galleryModel.append(gallery)
    }







}
