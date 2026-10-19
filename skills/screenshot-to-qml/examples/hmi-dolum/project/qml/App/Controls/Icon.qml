import QtQuick
import App.Style

// Icon-font glyph (Font Awesome 7 Free Solid). `glyph` takes a code point from Icons.
Text {
    id: root

    property string glyph
    property int size: 16

    text: glyph
    color: Theme.text
    font.family: Theme.fontIcon
    font.weight: Font.Black
    font.pixelSize: size
    height: size
    horizontalAlignment: Text.AlignHCenter
    verticalAlignment: Text.AlignVCenter
    Accessible.ignored: true
}
