pragma Singleton
import QtQuick 2.15

// Sample vehicle state. On the target, replace this singleton with a C++ object fed by the CAN
// gateway (Q_PROPERTY speed, rpm, gear, telltales …) under the same names.
QtObject {
    property real speed: 87               // km/h
    readonly property real speedMax: 240
    readonly property int speedLimit: 90
    property real rpm: 2.4                // ×1000 rpm
    readonly property real rpmMax: 8
    readonly property real redline: 6.5
    property string gear: "D"
    readonly property var gears: ["P", "R", "N", "D"]
    readonly property string driveMode: "ECO"
    property bool turnLeft: true
    property bool turnRight: false

    readonly property string clock: "14:32"
    readonly property string outside: "18°C"
    readonly property string date: "Çar 28 Eki"

    // tone: ok | warn | danger; off telltales are drawn in the dim color
    readonly property var telltales: [
        {
            icon: "bulb",
            on: true,
            tone: "ok"
        },
        {
            icon: "engine",
            on: true,
            tone: "warn"
        },
        {
            icon: "battery-automotive",
            on: false,
            tone: "danger"
        },
        {
            icon: "parking-circle",
            on: false,
            tone: "danger"
        },
        {
            icon: "gas-station",
            on: false,
            tone: "warn"
        },
        {
            icon: "steering-wheel",
            on: false,
            tone: "warn"
        }
    ]

    readonly property string navDistance: "350 m"
    readonly property string navStreet: "Atatürk Bulvarı"
    readonly property string navTowards: "Kızılay yönü"
    readonly property real navProgress: 0.62
    readonly property var route: [
        {
            icon: "flag",
            text: "Varış 14:58"
        },
        {
            icon: "route",
            text: "23 km"
        },
        {
            icon: "clock",
            text: "26 dk"
        }
    ]

    readonly property var trip: [
        {
            label: "MENZİL",
            value: "412",
            unit: "km"
        },
        {
            label: "ORT. TÜKETİM",
            value: "6,1",
            unit: "L/100"
        },
        {
            label: "YOLCULUK A",
            value: "128,4",
            unit: "km"
        }
    ]

    readonly property string mediaTitle: "Ayaz FM 103,1"
    readonly property string mediaSubtitle: "Akşam Yolu · canlı"
    readonly property int volume: 12

    property real fuel: 0.6
    property real coolant: 0.5
    readonly property string odometer: "48.216 km"
    readonly property string tripB: "1.204,7 km"
}
