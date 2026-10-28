import QtQuick 2.15
import QtQuick.Window 2.15
import QtGraphicalEffects 1.15

// SVG icon in a Theme color for Qt 5.15 (no VectorImage, no MultiEffect): the SVG is rasterized
// at its drawn size × the screen's DPR (sharp, never upscaled), then ColorOverlay paints every
// opaque pixel in `color`. Export the SVG with any solid color (icon_match.py export).
//   SvgIcon { source: "../../assets/icons/bell.svg"; width: 24; height: 24; color: Theme.textMuted }
Item {
    id: root

    property url source
    property color color   // set it from the Theme

    implicitWidth: 24
    implicitHeight: 24

    Image {
        id: image

        anchors.fill: parent
        source: root.source
        sourceSize.width: Math.ceil(root.width * Screen.devicePixelRatio)
        sourceSize.height: Math.ceil(root.height * Screen.devicePixelRatio)
        fillMode: Image.PreserveAspectFit
        smooth: true
        visible: false
    }

    ColorOverlay {
        anchors.fill: image
        source: image
        color: root.color
    }
}
