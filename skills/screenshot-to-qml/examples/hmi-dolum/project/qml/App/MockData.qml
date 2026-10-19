pragma Singleton
import QtQuick
import App.Style

// Sample data for the screen. In production replace this singleton with a
// Python/C++ backend that exposes the same property names (see README).
QtObject {
    readonly property string station: "Hat 3 · Dolum İstasyonu"
    readonly property string company: "NOVA MAKİNE"
    readonly property string runtime: "02:14:36"
    readonly property string shift: "B Vardiyası"
    readonly property string operatorName: "M. Yıldız"
    readonly property string time: "14:32:07"
    readonly property string date: "Perşembe, 25.09.2026"
    readonly property string recipe: "R-12 · Ayran 250 ml"
    readonly property string lot: "LOT-26-0925-B"
    readonly property string version: "HMI-03 · v2.4.1"

    readonly property var tanks: [
        {
            name: "Tank A",
            content: "Süt",
            level: 0.72,
            liters: "7.200",
            capacity: "10.000",
            warning: false
        },
        {
            name: "Tank B",
            content: "Şurup",
            level: 0.18,
            liters: "1.800",
            capacity: "10.000",
            warning: true
        },
        {
            name: "Tank C",
            content: "Su",
            level: 0.91,
            liters: "9.100",
            capacity: "10.000",
            warning: false
        }
    ]

    readonly property var kpis: [
        {
            label: "Üretim Hızı",
            glyph: Icons.gaugeHigh,
            value: "1.248",
            unit: "şişe/dk",
            foot: "Hedef 1.200 · ",
            delta: "+%4,0",
            trend: "up"
        },
        {
            label: "Vardiya Üretimi",
            glyph: Icons.listCheck,
            value: "58.392",
            unit: "",
            foot: "Hedef 60.000 · %97,3 tamamlandı",
            delta: "",
            trend: ""
        },
        {
            label: "OEE",
            glyph: Icons.bolt,
            value: "%87,4",
            unit: "",
            foot: "Dün %85,1 · ",
            delta: "+2,3 puan",
            trend: "up"
        },
        {
            label: "Red Oranı",
            glyph: Icons.flask,
            value: "%0,62",
            unit: "",
            foot: "Limit %1,00 · ",
            delta: "+0,08 puan",
            trend: "down"
        }
    ]

    readonly property var alarms: [
        {
            severity: "danger",
            code: "A-214 · 14:28",
            message: "Tank B seviyesi kritik eşiğe yakın"
        },
        {
            severity: "warning",
            code: "W-031 · 14:05",
            message: "Filtre değişimine 36 saat kaldı"
        },
        {
            severity: "warning",
            code: "W-017 · 13:52",
            message: "Basınç dalgalanması algılandı"
        },
        {
            severity: "info",
            code: "I-008 · 13:30",
            message: "Vardiya değişimi 16:00'da"
        }
    ]

    readonly property int activeAlarmCount: 3

    readonly property var pressure: [2.39, 2.4, 2.44, 2.42, 2.45, 2.44, 2.42, 2.44, 2.4, 2.41, 2.37, 2.36, 2.36, 2.37, 2.33, 2.34, 2.36, 2.26, 2.25, 2.26, 2.46, 2.4, 2.45, 2.43, 2.43, 2.43, 2.43, 2.45, 2.4, 2.41, 2.39]
    readonly property real pressureSetpoint: 2.40
    readonly property var pressureTimeLabels: ["13:30", "13:45", "14:00", "14:15", "14:30"]

    readonly property var modes: ["Otomatik", "Manuel", "Bakım"]
    readonly property int speedTarget: 1200
    readonly property int speedMax: 2000
}
