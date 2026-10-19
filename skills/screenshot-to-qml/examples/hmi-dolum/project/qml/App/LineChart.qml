pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Shapes
import App.Style

// Time-series line chart drawn with Qt Quick Shapes (no chart module needed):
// y grid + labels, x labels, dashed setpoint, smoothed line with area fill, end dot.
Item {
    id: root

    property var values: []
    property real yMin: 0
    property real yMax: 1
    property var yTicks: []
    property var xLabels: []
    property real setpoint: NaN
    property int decimals: 1
    property color lineColor: Theme.accent
    property color setpointColor: Theme.warn
    property color gridColor: Theme.border
    property color labelColor: Theme.textDim
    property color dotFill: Theme.panel
    property real areaOpacity: Theme.chartAreaOpacity
    property real padLeft: 52
    property real padRight: 28
    property real padTop: 10
    property real padBottom: 30

    readonly property real plotLeft: padLeft
    readonly property real plotRight: width - padRight
    readonly property real plotBottom: height - padBottom
    readonly property var points: {
        const n = values.length;
        const pts = [];
        for (let i = 0; i < n; ++i)
            pts.push([xAt(i), yAt(values[i])]);
        return pts;
    }

    function xAt(i) {
        return plotLeft + i / Math.max(1, values.length - 1) * (plotRight - plotLeft);
    }
    function yAt(v) {
        return plotBottom - (v - yMin) / (yMax - yMin) * (plotBottom - padTop);
    }
    function f(v) {
        return v.toFixed(2);
    }
    // Catmull-Rom style smoothing (tension 0.16) expressed as cubic Béziers.
    function smoothPath(pts) {
        if (pts.length < 2)
            return "";
        let d = "M" + f(pts[0][0]) + "," + f(pts[0][1]);
        for (let i = 0; i < pts.length - 1; ++i) {
            const p0 = pts[Math.max(0, i - 1)], p1 = pts[i], p2 = pts[i + 1], p3 = pts[Math.min(pts.length - 1, i + 2)];
            const t = 0.16;
            d += " C" + f(p1[0] + (p2[0] - p0[0]) * t) + "," + f(p1[1] + (p2[1] - p0[1]) * t) + " " + f(p2[0] - (p3[0] - p1[0]) * t) + "," + f(p2[1] - (p3[1] - p1[1]) * t) + " " + f(p2[0]) + "," + f(p2[1]);
        }
        return d;
    }
    readonly property string linePath: smoothPath(points)
    readonly property real curveTop: {
        let m = plotBottom;
        for (const p of points)
            m = Math.min(m, p[1]);
        return m;
    }

    Accessible.role: Accessible.Chart
    Accessible.name: qsTr("Zaman serisi grafiği")

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            strokeColor: root.gridColor
            strokeWidth: 1
            fillColor: "transparent"
            PathSvg {
                path: root.yTicks.map(v => "M" + root.plotLeft + "," + root.f(root.yAt(v)) + " H" + root.plotRight).join(" ")
            }
        }
        ShapePath {
            strokeColor: "transparent"
            fillGradient: LinearGradient {
                x1: 0
                y1: root.curveTop
                x2: 0
                y2: root.plotBottom
                GradientStop {
                    position: 0.0
                    color: Theme.alpha(root.lineColor, root.areaOpacity)
                }
                GradientStop {
                    position: 1.0
                    color: Theme.alpha(root.lineColor, 0)
                }
            }
            PathSvg {
                path: root.points.length < 2 ? "" : root.linePath + " L" + root.f(root.points[root.points.length - 1][0]) + "," + root.plotBottom + " L" + root.f(root.points[0][0]) + "," + root.plotBottom + " Z"
            }
        }
        ShapePath {
            strokeColor: isNaN(root.setpoint) ? "transparent" : root.setpointColor
            strokeWidth: 1.5
            strokeStyle: ShapePath.DashLine
            dashPattern: [6 / 1.5, 4 / 1.5]
            fillColor: "transparent"
            PathSvg {
                path: isNaN(root.setpoint) ? "" : "M" + root.plotLeft + "," + root.f(root.yAt(root.setpoint)) + " H" + root.plotRight
            }
        }
        ShapePath {
            strokeColor: root.lineColor
            strokeWidth: 2.5
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            fillColor: "transparent"
            PathSvg {
                path: root.linePath
            }
        }
    }

    Repeater {
        model: root.yTicks
        delegate: Text {
            required property real modelData
            x: root.plotLeft - 10 - implicitWidth
            y: root.yAt(modelData) + 4 - baselineOffset
            text: modelData.toFixed(root.decimals).replace(".", ",")
            color: root.labelColor
            font: Theme.mono13
        }
    }
    Repeater {
        model: root.xLabels
        delegate: Text {
            required property string modelData
            required property int index
            x: root.xAt(index * (root.values.length - 1) / Math.max(1, root.xLabels.length - 1)) - implicitWidth / 2
            y: root.height - 6 - baselineOffset
            text: modelData
            color: root.labelColor
            font: Theme.mono13
        }
    }

    Rectangle {
        visible: root.points.length > 0
        x: visible ? root.points[root.points.length - 1][0] - width / 2 : 0
        y: visible ? root.points[root.points.length - 1][1] - height / 2 : 0
        width: 12.5
        height: 12.5
        radius: width / 2
        color: root.dotFill
        border.color: root.lineColor
        border.width: 2.5
    }
}
