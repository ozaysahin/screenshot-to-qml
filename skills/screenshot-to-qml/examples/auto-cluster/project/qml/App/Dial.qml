import QtQuick 2.15
import QtQuick.Shapes 1.15
import App.Style 1.0

// Round gauge: face, hub, 270° track (+ optional redline), value arc, ticks, scale labels and a
// needle, all bound to `value`. Children go on top (readouts), in dial coordinates.
Item {
    id: root

    property real value: 0
    property real maximum: 100
    property real minorStep: 5
    property real majorStep: 10
    property real redlineFrom: -1          // < 0: no redline
    property real startAngle: 135          // degrees, clockwise from 3 o'clock
    property real sweep: 270
    default property alias content: overlay.data

    readonly property real center: width / 2
    readonly property real valueAngle: angleOf(Math.max(0, Math.min(value, maximum)))

    function angleOf(v) {
        return startAngle + sweep * v / maximum;
    }

    function px(r, deg) {
        return center + r * Math.cos(deg * Math.PI / 180);
    }

    function py(r, deg) {
        return center + r * Math.sin(deg * Math.PI / 180);
    }

    implicitWidth: Theme.dial
    implicitHeight: Theme.dial
    Accessible.role: Accessible.Indicator

    Rectangle {
        anchors.fill: parent
        radius: width / 2
        color: Theme.face
        border.width: 2
        border.color: Theme.faceBorder
    }

    Rectangle {
        x: root.center - width / 2
        y: root.center - height / 2
        width: (Theme.hubRadius + 1) * 2
        height: width
        radius: width / 2
        color: Theme.hub
        border.width: 2
        border.color: Theme.hubBorder
    }

    // the arcs share one Shape, so Qt 5.15 antialiases them with one multisampled layer
    Shape {
        anchors.fill: parent
        layer.enabled: true
        layer.samples: 4

        ShapePath {
            strokeColor: Theme.track
            strokeWidth: Theme.arcWidth
            fillColor: "transparent"
            capStyle: ShapePath.FlatCap

            PathAngleArc {
                centerX: root.center
                centerY: root.center
                radiusX: Theme.arcRadius
                radiusY: Theme.arcRadius
                startAngle: root.startAngle
                sweepAngle: root.sweep
            }
        }

        ShapePath {
            strokeColor: root.redlineFrom >= 0 ? Theme.redline : "transparent"
            strokeWidth: Theme.arcWidth
            fillColor: "transparent"
            capStyle: ShapePath.FlatCap

            PathAngleArc {
                centerX: root.center
                centerY: root.center
                radiusX: Theme.arcRadius
                radiusY: Theme.arcRadius
                startAngle: root.angleOf(Math.max(0, root.redlineFrom))
                sweepAngle: root.redlineFrom >= 0 ? root.sweep * (1 - root.redlineFrom / root.maximum) : 0
            }
        }

        ShapePath {
            strokeColor: Theme.accent
            strokeWidth: Theme.arcWidth
            fillColor: "transparent"
            capStyle: ShapePath.FlatCap

            PathAngleArc {
                centerX: root.center
                centerY: root.center
                radiusX: Theme.arcRadius
                radiusY: Theme.arcRadius
                startAngle: root.startAngle
                sweepAngle: root.valueAngle - root.startAngle
            }
        }
    }

    // ticks: radial bars with round ends, every minorStep; longer on majorStep
    Repeater {
        model: Math.round(root.maximum / root.minorStep) + 1

        Rectangle {
            required property int index
            readonly property real v: index * root.minorStep
            readonly property bool major: Math.abs(v / root.majorStep - Math.round(v / root.majorStep)) < 1e-6
            readonly property real inner: major ? Theme.tickMajorInner : Theme.tickMinorInner
            readonly property real mid: (Theme.tickOuter + inner) / 2
            readonly property real angle: root.angleOf(v)

            x: root.px(mid, angle) - width / 2
            y: root.py(mid, angle) - height / 2
            width: Theme.tickOuter - inner + Theme.tickWidth
            height: Theme.tickWidth
            radius: height / 2
            rotation: angle
            antialiasing: true
            color: root.redlineFrom >= 0 && v >= root.redlineFrom - 1e-6 ? Theme.danger : major ? Theme.tickMajor : Theme.tick
        }
    }

    // scale labels on a circle inside the ticks
    Repeater {
        model: Math.round(root.maximum / root.majorStep) + 1

        Text {
            required property int index
            readonly property real v: index * root.majorStep
            readonly property real angle: root.angleOf(v)

            x: root.px(Theme.labelRadius, angle) - width / 2
            y: root.py(Theme.labelRadius, angle) - height / 2
            width: 60
            height: Theme.lhDialLabel
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            text: Math.round(v)
            font: Theme.dialLabel
            color: root.redlineFrom >= 0 && v >= root.redlineFrom ? Theme.danger : Theme.muted
        }
    }

    Rectangle {
        readonly property real mid: (Theme.needleInner + Theme.needleOuter) / 2

        x: root.px(mid, root.valueAngle) - width / 2
        y: root.py(mid, root.valueAngle) - height / 2
        width: Theme.needleOuter - Theme.needleInner + Theme.needleWidth
        height: Theme.needleWidth
        radius: height / 2
        rotation: root.valueAngle
        antialiasing: true
        color: Theme.text
    }

    Item {
        id: overlay

        anchors.fill: parent
    }
}
