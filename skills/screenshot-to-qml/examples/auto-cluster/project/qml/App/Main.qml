import QtQuick 2.15
import QtQuick.Window 2.15
import App.Style 1.0
import App.Controls 1.0

// 1920×720 instrument cluster canvas, uniformly scaled to the window (12.3" panel: full screen).
Window {
    id: window

    readonly property real fitScale: Math.min(width / Theme.designWidth, height / Theme.designHeight)

    width: 1280
    height: 480
    visible: true
    color: Theme.bg
    title: qsTr("Ayaz gösterge paneli")
    // On the vehicle: visibility: Window.FullScreen

    Item {
        id: stage

        width: Theme.designWidth
        height: Theme.designHeight
        scale: window.fitScale
        transformOrigin: Item.TopLeft
        x: (window.width - width * scale) / 2
        y: (window.height - height * scale) / 2

        SvgIcon {
            x: 56
            y: 26
            width: Theme.turnIcon
            height: Theme.turnIcon
            source: Qt.resolvedUrl("../../assets/icons/arrow-big-left.svg")
            color: MockData.turnLeft ? Theme.ok : Theme.dim
            Accessible.role: Accessible.Indicator
            Accessible.name: qsTr("Sol sinyal")
        }

        SvgIcon {
            x: stage.width - 56 - width
            y: 26
            width: Theme.turnIcon
            height: Theme.turnIcon
            source: Qt.resolvedUrl("../../assets/icons/arrow-big-right.svg")
            color: MockData.turnRight ? Theme.ok : Theme.dim
            Accessible.role: Accessible.Indicator
            Accessible.name: qsTr("Sağ sinyal")
        }

        Dial {
            id: speedDial

            x: 168
            y: 118
            value: MockData.speed
            maximum: MockData.speedMax
            minorStep: 10
            majorStep: 20
            Accessible.name: qsTr("Hız %1 km/sa").arg(Math.round(MockData.speed))

            Text {
                x: (parent.width - width) / 2
                y: 186
                width: Theme.readoutWidth
                height: Theme.lhDisplay
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                text: Math.round(MockData.speed)
                font: Theme.display
                color: Theme.text
            }

            Text {
                x: (parent.width - width) / 2
                y: 336
                width: Theme.readoutWidth
                height: Theme.lhSpeedUnit
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                text: qsTr("km/sa")
                font: Theme.speedUnit
                color: Theme.muted
            }

            Rectangle {
                x: (parent.width - width) / 2
                y: 426
                width: Theme.limitSign
                height: Theme.limitSign
                radius: width / 2
                color: Theme.sign
                border.width: Theme.limitRing
                border.color: Theme.signRing
                Accessible.role: Accessible.StaticText
                Accessible.name: qsTr("Hız sınırı %1").arg(MockData.speedLimit)

                Text {
                    anchors.centerIn: parent
                    height: Theme.lhLimit
                    verticalAlignment: Text.AlignVCenter
                    text: MockData.speedLimit
                    font: Theme.limit
                    color: Theme.signInk
                }
            }
        }

        Dial {
            x: 1228
            y: 118
            value: MockData.rpm
            maximum: MockData.rpmMax
            minorStep: 0.5
            majorStep: 1
            redlineFrom: MockData.redline
            Accessible.name: qsTr("Devir %1 bin").arg(MockData.rpm)

            Text {
                x: (parent.width - width) / 2
                y: 150
                width: Theme.readoutWidth
                height: Theme.lhOverline
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                text: qsTr("×1000 DEV/DK")
                font: Theme.overline
                color: Theme.muted
            }

            Text {
                x: (parent.width - width) / 2
                y: 186
                width: Theme.readoutWidth
                height: Theme.lhDisplay
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                text: MockData.gear
                font: Theme.display
                color: Theme.text
            }

            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                y: 344
                spacing: Theme.gearGap

                Repeater {
                    model: MockData.gears

                    Item {
                        id: gearCell

                        required property string modelData
                        readonly property bool selected: modelData === MockData.gear

                        width: Theme.gearCell
                        height: 34

                        Text {
                            width: parent.width
                            height: Theme.lhGear
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            text: gearCell.modelData
                            font: Theme.gear
                            color: gearCell.selected ? Theme.accent : Theme.dim
                        }

                        Rectangle {
                            visible: gearCell.selected
                            anchors.bottom: parent.bottom
                            width: parent.width
                            height: Theme.gearMark
                            color: Theme.accent
                        }
                    }
                }
            }

            Rectangle {
                x: (parent.width - width) / 2
                y: 442
                width: Theme.chipWidth
                height: Theme.chipHeight
                radius: height / 2
                color: Theme.okSoft

                Row {
                    anchors.centerIn: parent
                    spacing: Theme.space1 + 2

                    SvgIcon {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 20
                        height: 20
                        source: Qt.resolvedUrl("../../assets/icons/leaf.svg")
                        color: Theme.ok
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        height: Theme.lhChip
                        verticalAlignment: Text.AlignVCenter
                        text: MockData.driveMode
                        font: Theme.chip
                        color: Theme.ok
                    }
                }
            }
        }

        Item {
            id: center

            x: 720
            y: 26
            width: Theme.centerWidth
            height: 586

            StatusRow {
                width: parent.width
            }

            TelltaleRow {
                anchors.horizontalCenter: parent.horizontalCenter
                y: 68
            }

            NavCard {
                y: 124
                width: parent.width
            }

            Row {
                y: 372
                spacing: Theme.space3

                Repeater {
                    model: MockData.trip

                    TripTile {
                        required property var modelData

                        label: modelData.label
                        value: modelData.value
                        unit: modelData.unit
                    }
                }
            }

            MediaCard {
                y: 510
                width: parent.width
            }
        }

        SegmentMeter {
            x: 248
            y: 650
            icon: Qt.resolvedUrl("../../assets/icons/gas-station.svg")
            low: qsTr("E")
            high: qsTr("F")
            level: MockData.fuel
        }

        Row {
            anchors.horizontalCenter: center.horizontalCenter
            y: 650
            height: 30
            spacing: Theme.space3 + 2

            Text {
                anchors.verticalCenter: parent.verticalCenter
                height: Theme.lhOdoLabel
                verticalAlignment: Text.AlignVCenter
                text: qsTr("ODO")
                font: Theme.odoLabel
                color: Theme.muted
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                height: Theme.lhReading
                verticalAlignment: Text.AlignVCenter
                text: MockData.odometer
                font: Theme.reading
                color: Theme.text2
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                height: Theme.lhOdoLabel
                verticalAlignment: Text.AlignVCenter
                text: qsTr("B")
                font: Theme.odoLabel
                color: Theme.muted
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                height: Theme.lhReading
                verticalAlignment: Text.AlignVCenter
                text: MockData.tripB
                font: Theme.reading
                color: Theme.text2
            }
        }

        SegmentMeter {
            x: 1308
            y: 650
            icon: Qt.resolvedUrl("../../assets/icons/temperature.svg")
            low: qsTr("C")
            high: qsTr("H")
            level: MockData.coolant
        }
    }
}
