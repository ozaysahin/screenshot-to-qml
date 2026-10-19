#!/usr/bin/env python3
"""Write expected.json and thresholds.json for every eval case.

expected.json  - rubric a grader (human or model) checks the generated project against.
thresholds.json - numeric gates used by scripts/diff.py and scripts/quality_gate.py.

Thresholds were calibrated on cases 01-08 (2026-09-27) and carried over to 09-20 unchanged.
Usage: python expectations.py
"""
import json
import pathlib

CASES = pathlib.Path(__file__).resolve().parent.parent / "cases"

# Applies to every case; listed once here and copied into each expected.json.
COMMON = [
    "Project runs offscreen (QT_QPA_PLATFORM=offscreen) with zero QML warnings or errors.",
    "No web engine, WebView or screenshot image embedded as a background; the UI is built from Qt Quick items.",
    "All colors, font sizes, spacing and radii come from a Theme singleton; no raw hex or pixel literals elsewhere (production mode).",
    "Fonts are bundled under assets/fonts and loaded by scanning the folder; QML uses the family names returned by QFontDatabase.",
    "All visible text matches golden-spec text[].string verbatim, including Turkish characters (ç ğ ı İ ö ş ü) and uppercase transforms.",
    "Repeated patterns listed in golden-spec nodes[].model are generated from a model (Repeater/ListView/GridView/TableView), not copy-pasted items.",
    "Interactive controls are keyboard reachable and expose Accessible.role/name.",
    "README lists every value whose source is not 'truth'-equivalent (assumed/low confidence) and every approximation with its reason.",
]

# Calibrated on 16 runs (8 cases x baseline / skill-v0.4, 2026-09-27; see evals/results/):
# every run scored global SSIM >= 0.987, max ΔE 1.21, max geometry offset 1.94 px; region SSIM
# (aligned within 1 px) >= 0.92 except real defects (dashed chip borders, a misdrawn logo).
BASE_THRESHOLDS = {
    "provisional": False,
    "calibratedOn": "evals/results (baseline + skill-v0.4, 16 runs, 2026-09-27)",
    "compareAt": "design size x dpr (same pixel size as input.png)",
    "globalSSIM": 0.98,
    "regionSSIM": 0.90,
    "regionAlignPx": 1,
    "maskTextForSSIM": True,
    "colorDeltaE2000": 2.0,
    "geometryPx": 2,
    "textStringMatch": 1.0,
    "textPositionPx": 2,
    "qmllintWarnings": 0,
    "runtimeWarnings": 0,
    "hardcodedValues": 0,
    "maxFixIterations": 5,
}

CASES_SPEC = {
    "01-hmi-dolum": {
        "summary": "1920x1080 dark industrial HMI for a filling line; embedded-gpu profile, touch-first.",
        "mustHave": [
            "Fixed 1920x1080 design canvas scaled to the window (fitScale) or equivalent Layouts; aspect preserved.",
            "Three tank gauges from a model (level 0.72 / 0.18 / 0.91); Tank B uses the warning palette.",
            "Alarm list from a model of 4 items; severity drives the side bar, icon tile and colors via one delegate.",
            "Mode selector (Otomatik/Manuel/Bakım) is an exclusive button group with 'Otomatik' checked.",
            "Speed slider is a real slider: range 0-2000, value 1200, tick labels 0/500/1.000/1.500/2.000.",
            "BAŞLAT is disabled through enabled:false (styling reacts to the state), not only by opacity.",
            "Font Awesome glyphs use the bundled Font Awesome 7 Free Solid font with escaped code points (e.g. \\uf275).",
            "Pressure chart has 31 points plus a dashed setpoint line at 2.40, drawn with Qt Graphs or Shape; axis labels use comma decimals.",
            "Numbers use JetBrains Mono with tabular figures.",
        ],
        "niceToHave": ["Clock text bound to a Timer-driven property.", "Alarm badge count bound to the model count."],
        "allowedApproximations": ["Tank fill gradients may use Gradient on Rectangle.", "Chart smoothing may differ slightly (catmull-rom vs straight segments)."],
        "forbidden": ["MultiEffect/blur shaders (embedded-gpu profile)."],
        "thresholds": {},
    },
    "02-kiosk-kafe": {
        "summary": "1080x1920 portrait self-order kiosk, warm light theme, large touch targets.",
        "mustHave": [
            "Portrait fixed canvas 1080x1920.",
            "Category tabs are a horizontal ListView/Flickable with the 5th tab clipped at the screen edge; 'Kahveler' selected.",
            "Product grid of 4 cards from a model; Latte card shows the selected state (accent border) and a quantity stepper with value 2.",
            "Promo banner uses a 135-degree two-stop gradient (#FF8A4C to #FF5A36) and two translucent circles with icons.",
            "Currency sign ₺ renders with the bundled Manrope font (no tofu).",
            "Cart bar is anchored to the bottom and overlays the scrolling content.",
            "Card shadows approximate the 2-layer CSS shadow (MultiEffect shadow on Qt 6.8; RectangularShadow only when minQt >= 6.9).",
            "Lucide icons are rendered as vector (VectorImage/svgtoqml or Image with sourceSize x DPR) and recolored to the design colors.",
        ],
        "niceToHave": ["Product list driven by mock JSON loaded at startup."],
        "allowedApproximations": ["Soft card shadow simplified to one shadow layer."],
        "forbidden": ["Blur shaders."],
        "thresholds": {},
    },
    "03-dashboard-dark": {
        "summary": "1440x900 dark edge-AI fleet dashboard captured at DPR 2 (input is 2880x1800).",
        "mustHave": [
            "Analysis divides by DPR 2: Theme values and layout are in 1440x900 design pixels.",
            "Sidebar navigation from a model with a selected item (accent bar + tinted background) and a red count badge.",
            "Four KPI cards from a model, each with a sparkline (12 points) in its own color.",
            "Latency chart: two series of 28 points (p50 filled area, p95 line), 5 y-ticks 0-60, 7 day labels.",
            "Donut with 4 segments (62/37/24/11) and centered total '134'.",
            "Deployments table with 4 rows; status badge is one component with 3 variants (ok/run/err).",
            "Search field has placeholderText and a 'Ctrl K' shortcut hint.",
            "Space Grotesk (numbers, headings) and Inter (body) are both identified and used.",
        ],
        "niceToHave": ["Segmented 24S/7G/30G switches chart data from mock models."],
        "allowedApproximations": ["Area gradients under lines may be approximated with Shape + LinearGradient."],
        "forbidden": [],
        "thresholds": {},
    },
    "04-dashboard-light": {
        "summary": "1440x900 light energy dashboard captured at 125% scale (input is 1800x1125).",
        "mustHave": [
            "Fractional DPR 1.25 handled: design size 1440x900, no off-by-one layout drift.",
            "Top navigation tabs with underline indicator on 'Özet'.",
            "Solar card: 155-degree gradient, 12 hourly bars with the current hour highlighted in white.",
            "Battery ring at 78% with gradient stroke and centered labels.",
            "Weekly grouped bar chart: 7 days x 2 series, y-ticks 0-40, today's label bold.",
            "Device consumption list of 5 rows from a model with proportional progress bars.",
            "Multi-layer card shadow approximated (MultiEffect on Qt 6.8; RectangularShadow only when minQt >= 6.9).",
        ],
        "niceToHave": ["Bar values bound to mock data, not hard-coded heights."],
        "allowedApproximations": ["Two-layer shadow merged into one."],
        "forbidden": [],
        "thresholds": {},
    },
    "05-settings-form": {
        "summary": "1280x800 settings screen; the control-state case.",
        "mustHave": [
            "Controls are built on QtQuick.Templates (T.TextField, T.Slider, T.Switch, T.ComboBox, T.CheckBox, T.RadioButton, T.Button).",
            "TextField states: normal, focused (primary border + 4px focus ring), placeholder, error (red border, tinted bg, icon, error text).",
            "Brightness slider value 0.7 with value label '%70'.",
            "Auto-brightness switch checked.",
            "Theme selector is an exclusive group with 'Açık' checked; timeout ComboBox shows '5 dakika'.",
            "Four checkboxes: two checked, one unchecked, one disabled via enabled:false with the 'Pro lisans' tag.",
            "Radio group with 'Anında' checked.",
            "Footer: ghost, secondary and primary buttons; unsaved-changes indicator.",
            "Tab order follows visual order: nav, fields top to bottom, right column, footer buttons.",
        ],
        "niceToHave": ["Validation logic in Python/C++ backend, QML only binds the error state."],
        "allowedApproximations": [],
        "forbidden": ["MouseArea+Rectangle fake controls for any of the listed controls."],
        "thresholds": {},
    },
    "06-mobile-aliskanlik": {
        "summary": "390x844 mobile habit tracker captured at DPR 3 (input is 1170x2532).",
        "mustHave": [
            "Design size 390x844 (input divided by 3); raster assets requested at sourceSize x devicePixelRatio.",
            "Week strip of 7 day chips from a model: 3 done (green dot), today selected, 3 future (muted).",
            "Hero card: 125-degree gradient, decorative circle, ring progress 4/6 with '%67'.",
            "Habit list of 5 rows from a model; the 5th row is partly hidden under the tab bar (clip/z-order correct).",
            "Tabler filled vs outline icons chosen as in the source (e.g. filled droplet/book/moon/home, outline walk/yoga).",
            "Tab bar with raised circular FAB and home indicator.",
        ],
        "niceToHave": ["ListView with bottom margin so the last row can scroll clear of the tab bar."],
        "allowedApproximations": ["Colored drop shadows may be simplified."],
        "forbidden": [],
        "thresholds": {},
    },
    "07-data-table": {
        "summary": "1440x900 data table with filters, selection, sorting and pagination.",
        "mustHave": [
            "Table from a model of 10 rows (mock JSON), using TableView + HorizontalHeaderView or an equivalent ListView with fixed columns.",
            "Column widths match the source; serial numbers use JetBrains Mono.",
            "Header checkbox in partially-checked state; row 'rpi5-kapi-03' selected with tinted background.",
            "Hovered row 'rpi4-lobi-01' reproduced as a hover state (assumed state, documented).",
            "Sort indicator on 'Son görülme' (descending).",
            "Status badge component with 3 variants (online/maintenance/offline); CPU bar turns amber above 80%.",
            "Filter chips: dashed default style and solid active style with a clear icon.",
            "Pagination: disabled previous, page 1 active, ellipsis, 14, next.",
        ],
        "niceToHave": ["Sorting and filtering via QML SortFilterProxyModel (Qt 6.10+) or a Python proxy model."],
        "allowedApproximations": ["Dashed chip border may be approximated with a Shape dash pattern."],
        "forbidden": [],
        "thresholds": {},
    },
    "08-glass-home": {
        "summary": "HARD CASE. 1280x800 glassmorphism smart-home panel at DPR 2 (input is 2560x1600).",
        "mustHave": [
            "Background: dark base plus three large blurred color blobs.",
            "Glass cards: translucent fill with background blur (MultiEffect on a captured background layer) on the desktop profile.",
            "1px gradient border on glass cards approximated (Shape stroke with gradient or layered Rectangles) and listed in README approximations.",
            "Album art uses a conic gradient (ConicalGradient/Shape) with a center hole.",
            "Play button and active scene use the violet-to-cyan gradient with glow.",
            "Seek slider at 43% and volume slider at 60% as real sliders.",
            "Four room tiles from a model; the lights tile is in the active style; switches checked/unchecked as in the source.",
            "Outfit Light (300) used for the large clock and numbers.",
        ],
        "niceToHave": ["Fallback path documented for embedded profiles (no blur: higher-opacity flat glass)."],
        "allowedApproximations": ["backdrop-filter saturation boost", "exact blur radius", "mask-composite gradient border"],
        "forbidden": [],
        "thresholds": {"note": "Glass surfaces sample a blurred background; ΔE is checked on solid tokens only."},
    },
    "09-dashboard-sales": {
        "summary": "1440x900 light sales-analytics dashboard captured at DPR 1.5 (input is 2160x1350).",
        "mustHave": [
            "DPR 1.5 handled: Theme values and layout in 1440x900 design pixels, no drift from the fractional scale.",
            "Icon-only rail (72 px) from a model of 6 items with the chart item selected; settings button and 'EK' avatar pinned to the bottom.",
            "Header: exclusive segmented control Gün/Hafta/Ay with 'Ay' checked, date-range button, primary 'Rapor indir' button.",
            "Four KPI cards from a model; uppercase Turkish labels ('TOPLAM CİRO'); one delta-chip component with up (green) and down (red) variants.",
            "Revenue chart: 12 months, 'Bu dönem' solid with area gradient, 'Önceki dönem' dashed; data from a model, not hand-drawn paths.",
            "Static hover state: guide line at 'May', both points highlighted, dark tooltip with 'Mayıs 2026' and two ₺ values.",
            "Conversion funnel from a model of 4 bars of decreasing width with counts and percentages.",
            "Category share: one stacked bar of 5 segments with gaps plus a 5-row legend model.",
            "Top products: 5 rows from a model with initials tiles, right-aligned tabular numbers and share bars.",
        ],
        "niceToHave": ["Segmented control switches chart data from mock models.", "Tooltip position computed from the hovered index."],
        "allowedApproximations": ["Curve smoothing may differ.", "Two-layer tooltip and card shadows merged into one."],
        "forbidden": ["Dashed series drawn as a solid line.", "Chart or tooltip embedded as an image."],
        "thresholds": {},
    },
    "10-dashboard-ops-dark": {
        "summary": "1920x1080 dark network-operations dashboard: gauges, a 7x24 heatmap, a traffic chart, incidents and a live log.",
        "mustHave": [
            "Sora for UI text and DM Mono for numbers, ids, the clock and the log; both bundled.",
            "Top bar: breadcrumb with the last item emphasized, static 'CANLI' pill, search field with placeholder and '/' hint, clock, bell badge, avatar.",
            "Three semicircle gauges from one component (0.47 / 0.81 / 0.66) with threshold ticks; arc color and chip follow state (warning on 'Bellek'); no needle.",
            "Latency heatmap: 168 cells (7 x 24) from a model, colored by a 5-step scale from the data; day and hour labels, legend, region ComboBox.",
            "Throughput chart: two 49-point series with vertical gradient fills, dotted grid, legend with current values.",
            "Incident list from a model of 5 rows; severity chip is one component with 3 variants.",
            "Log panel: 12 lines in DM Mono from a model, colored level tags, columns aligned by the monospace font; the last line clipped by the panel edge.",
        ],
        "niceToHave": ["Heatmap delegate maps value to color through thresholds.", "Log as a ListView fed by a model."],
        "allowedApproximations": ["Curve smoothing and gradient opacity.", "Live dot ring drawn as a second circle."],
        "forbidden": ["Gauges or heatmap as images.", "A gauge needle."],
        "thresholds": {},
    },
    "11-hmi-boiler": {
        "summary": "1280x800 ISA-101-style boiler-room HMI (embedded-gpu): alarm banner, vector mimic diagram, setpoint steppers, soft keys.",
        "mustHave": [
            "Fixed 1280x800 canvas in a grayscale palette; color only for pipes, the amber alarm and running/selected states. No shadows, gradients or blur.",
            "Alarm banner with priority badge, message, time and a dark 'ONAYLA' button; the same alarm marks tag TT-104 in the diagram.",
            "Mimic diagram drawn as vectors (Shape paths): pipe runs with rounded elbows in 3 colors, flow arrows, stacks, tank legs.",
            "Boilers from a model of 2 (running / standby) with level fills clipped to the body and burner boxes that are filled when on.",
            "Pumps from a model of 2 (running filled, stopped outline) and valves from a model of 3 (open filled, closed outline).",
            "Sensor readouts from a model of 10 placed at the data coordinates, values with comma decimals.",
            "Setpoint panel: 3 setpoints from a model with -/+ buttons at least 56 px tall; mode switch checked ('OTOMATİK').",
            "Soft-key bar: 6 keys from a model with F1-F6 hints; 'GENEL BAKIŞ' selected; 'ALARMLAR' has a count badge.",
        ],
        "niceToHave": ["One delegate per equipment type whose state drives the fill.", "Steppers apply a step with locale formatting."],
        "allowedApproximations": ["Diagram text placed by bounding box.", "Elbows drawn as quadratic curves."],
        "forbidden": ["MultiEffect/shadows/blur (embedded-gpu flat HMI).", "A raster image of the diagram."],
        "thresholds": {},
    },
    "12-ev-charger": {
        "summary": "1024x600 7-inch EV charger session screen for the software renderer (embedded-sw).",
        "mustHave": [
            "Fixed 1024x600 canvas; profile embedded-sw: no MultiEffect, RectangularShadow, ShaderEffect or layer effects.",
            "Big '%70' (Titillium Web Bold) and a 20-segment bar from a model: 14 lit, 6 unlit, target marker at 80 %.",
            "Four stat tiles from a model (32,6 kWh / 98,4 kW / 9 dk / 293,40); uppercase labels keep the Turkish İ.",
            "₺ drawn as a vector icon (the font has no ₺ glyph); no fallback-font ₺.",
            "Connector card with a vector CCS2 face; session id with tabular digits and letter spacing.",
            "Language selector: exclusive group of 3 from a model with TR checked.",
            "Red 'ŞARJI DURDUR' button with a 2-stop vertical gradient and a secondary 'Yardım' button.",
        ],
        "niceToHave": ["Lit segment count bound to the percentage.", "Cost bound to energy x unit price."],
        "allowedApproximations": ["CCS2 face as Shape paths or a vector image."],
        "forbidden": ["Shader effects, opacity layers or translucent overlays (software scene graph)."],
        "thresholds": {},
    },
    "13-form-wizard": {
        "summary": "1280x800 device-registration wizard at DPR 1.25 with an open date-picker popup over the form.",
        "mustHave": [
            "DPR 1.25 handled: design size 1280x800.",
            "Stepper from a model of 5: 2 completed (check icons), 1 current (ring), 2 upcoming; uppercase captions with Turkish İ.",
            "Text fields: one filled, one with placeholder; the date field focused (primary border + ring).",
            "Calendar popup above the form (not clipped by the card): 'Ekim 2026', prev/next, Monday-first weekday row, 42-day grid from a model with disabled, today, selected and outside-month states, 'Temizle'/'Bugün'.",
            "ComboBox 'Ankara · Ostim Deposu'; TextArea with wrapped note and counter '84/200'.",
            "Tag input with 3 removable chips from a model and a placeholder.",
            "Dashed-border drop zone and an upload row with a progress bar at 0.64 and a cancel button.",
            "Footer: 'Geri' secondary, 'Taslak olarak kaydet' ghost, 'Devam' primary.",
        ],
        "niceToHave": ["Month grid generated from a date.", "Counter bound to the text length."],
        "allowedApproximations": ["Dashed border with a Shape dash pattern.", "Popup shadow merged into one layer."],
        "forbidden": ["Popup clipped inside the card.", "Calendar drawn as an image."],
        "thresholds": {},
    },
    "14-form-login-dark": {
        "summary": "1280x800 dark split-screen sign-in at DPR 2: gradient brand panel, form with a busy button, session toast.",
        "mustHave": [
            "DPR 2 handled: design size 1280x800.",
            "Brand panel inset 16 px with radius 24 and three radial gradients over the dark base; feature list of 3 from a model.",
            "Red Hat Display for headings and Red Hat Text for body text; both bundled.",
            "E-mail TextField filled with a valid check icon; password TextField in password echo mode showing 10 '•' with an eye button; caps-lock hint below.",
            "'Beni hatırla' checkbox checked; 'Şifremi unuttum' link.",
            "Primary button in a busy state: spinner + 'Giriş yapılıyor…'.",
            "'veya' divider and two secondary buttons with icons.",
            "Toast in the top-right corner: icon tile, title, 3-line body, close button, timer bar at 62 %.",
        ],
        "niceToHave": ["Spinner animates (frozen in the reference pose for checks)."],
        "allowedApproximations": ["Elliptical radial gradients via RadialGradient or Shape.", "Dashed dial decoration simplified."],
        "forbidden": ["Raster image for the brand background.", "Blur instead of gradients."],
        "thresholds": {"note": "Gradient panel: ΔE is checked on opaque solid fills only."},
    },
    "15-mobile-wallet": {
        "summary": "393x852 mobile wallet home at DPR 3: gradient balance card, quick actions, transactions grouped by day under a bottom nav.",
        "mustHave": [
            "Design size 393x852 (input divided by 3).",
            "Balance card: 135-degree 3-stop gradient, radius 24, two translucent circles clipped to the card, '₺48.215' + ',70' on one baseline, masked '•••• 4821'.",
            "Quick actions from a model of 4 round buttons; 'Gönder' filled, the others white.",
            "Filter tabs Tümü/Gelen/Giden as an exclusive group with 'Tümü' checked.",
            "Transactions grouped by day ('Bugün', 'Dün') via ListView sections or nested models; amounts right-aligned with tabular figures, incoming green, outgoing with a real minus.",
            "Last row partly hidden under the bottom nav (z-order and clipping correct).",
            "Bottom nav from a model of 5 with 'Ana sayfa' selected and a raised center button; status bar and home indicator.",
        ],
        "niceToHave": ["ListView bottomMargin so the last row can scroll clear.", "Amounts formatted with Qt.locale('tr_TR')."],
        "allowedApproximations": ["Colored shadows simplified."],
        "forbidden": ["Raster images for the card or tiles."],
        "thresholds": {},
    },
    "16-mobile-chat": {
        "summary": "360x800 Android-style team chat at DPR 2: bubbles with asymmetric radii, reply quote, voice message, typing indicator.",
        "mustHave": [
            "Design size 360x800 (input divided by 2).",
            "App bar: back button, avatar stack of 3 overlapping initials + '+3', title and subtitle, call and more buttons.",
            "Pinned-message bar with accent bar and uppercase 'SABİTLENMİŞ MESAJ'.",
            "Messages from a model through one delegate (incoming / outgoing / voice) with per-corner radii (topLeftRadius …); sender names colored per user; avatar only on the last bubble of a group.",
            "Reply quote inside the first outgoing bubble; timestamps with double read ticks.",
            "Voice bubble: play button and 28 waveform bars from a model, first 9 in the played color.",
            "Reaction chip (heart + '2') overlapping the bubble edge; typing indicator with 3 dots.",
            "Composer: attach button, pill TextField with placeholderText 'Mesaj yazın…', mic button; gesture bar.",
        ],
        "niceToHave": ["Messages loaded from JSON.", "Animated typing dots."],
        "allowedApproximations": ["Waveform as a Repeater of Rectangles or one Shape."],
        "forbidden": ["Images for avatars or the waveform."],
        "thresholds": {},
    },
    "17-data-table-stock": {
        "summary": "1366x768 dense inventory table: frozen SKU column, horizontal scroll, depot groups, inline editing.",
        "mustHave": [
            "Toolbar: search field with value 'kablo' and clear button, 'Filtreler' button with badge '3', column menu, 'Dışa aktar' and 'Ürün ekle'.",
            "Frozen first column (SKU in IBM Plex Mono) with an edge shadow; the last column cut at the viewport edge (horizontal scroll), styled horizontal scrollbar.",
            "Group headers Ankara (expanded, 6 rows), Bursa (collapsed), İstanbul (expanded, 8 rows) with totals; zebra stripes within groups.",
            "Numeric columns right-aligned with tabular figures and Turkish separators ('1.248', '₺3.450,00').",
            "Stock-level mini bar with reorder tick; status pill component with 3 variants.",
            "Row NW-6005-G in editing state: focused price field with ring, '₺' prefix, right-aligned value.",
            "Header: uppercase labels with Turkish İ, ascending sort arrow on SKU, hovered resize handle.",
            "Totals row, '1–14 / 326', rows-per-page ComboBox, pagination with disabled first/previous.",
        ],
        "niceToHave": ["Column widths from data.", "Sorting and grouping through a proxy model."],
        "allowedApproximations": ["Frozen-edge shadow as a gradient Rectangle.", "Scrollbar as a styled ScrollBar."],
        "forbidden": ["Dropping the cut column or shrinking columns to fit.", "Flattening group rows into data rows."],
        "thresholds": {},
    },
    "18-html-tailwind-billing": {
        "summary": "HTML INPUT. 1280x800 'Plan ve faturalama' page written with Tailwind CSS v4 utilities (oklch palette).",
        "mustHave": [
            "Values come from the HTML: Tailwind v4 palette converted from oklch to sRGB (indigo-600 #4F39F6, zinc-500 #71717B), not v3 hex values.",
            "Sidebar: 8 nav items from a model in two groups with uppercase headers; 'Plan ve faturalama' selected with a count badge.",
            "Billing Switch checked between 'Aylık' and 'Yıllık' with the '2 ay bedava' badge.",
            "Plan cards from a model of 3: current plan with a disabled button (enabled:false), recommended plan with a 2 px ring and badge, 'Özel fiyat' plan.",
            "Usage: 3 progress bars from a model (0.6 / 0.684 / 0.912), the last amber with a warning icon.",
            "Payment method card with masked number, expiry, 'Varsayılan' badge and 'Değiştir' button.",
            "Invoices: 4 rows from a model, right-aligned amounts, one status-badge component with 3 variants, download icon buttons.",
        ],
        "niceToHave": ["Theme token names mirror Tailwind (zinc500, indigo600 …).", "Prices switch monthly/yearly from data."],
        "allowedApproximations": ["Tailwind multi-layer shadow + ring as a border plus one shadow."],
        "forbidden": ["WebEngine/WebView rendering of the HTML.", "Parsing the CSS at runtime."],
        "thresholds": {},
    },
    "19-html-css-board": {
        "summary": "HTML INPUT. 1366x768 content-calendar kanban at DPR 2 written in hand-written HTML/CSS with real form elements.",
        "mustHave": [
            "Values come from the HTML/CSS: :root custom properties become Theme tokens; Karla bundled.",
            "Board: 4 equal columns with status dot, count badge (3/4/2/3) and menu button; card models of 3/4/2/3.",
            "Card delegate: uppercase channel tag (Turkish İ), title up to 2 lines, due date (overdue red), checklist 'n/m' with a progress bar, avatar stack with '+1'.",
            "Search TextField with value 'sonbahar' and 'Ctrl K' hint; two ComboBoxes ('Tüm kanallar', 'Ekim 2026').",
            "CheckBox 'Gecikenleri vurgula' checked; view toggle Pano/Liste exclusive with 'Pano' checked; primary 'Yeni içerik'.",
            "Top bar: logo, workspace switcher, nav with 'İçerikler' current, bell with dot, avatar.",
            "'Kart ekle' button after the last card of every column.",
        ],
        "niceToHave": ["Card models loaded from JSON mirroring the markup."],
        "allowedApproximations": ["Card ring shadow as a border plus one shadow.", "Checkmark drawn as an icon."],
        "forbidden": ["WebEngine/WebView rendering of the HTML."],
        "thresholds": {},
    },
    "20-hard-weather": {
        "summary": "HARD CASE. 1280x800 editorial weather dashboard at DPR 2 in a font that is not in the skill's catalog (Bricolage Grotesque).",
        "mustHave": [
            "Font: the family is not in the font catalog; the README names it as unidentified and documents the substitute (or the user-supplied file) and its metric fit.",
            "Background: light base plus 3 large radial gradients; translucent white cards with 1 px border and soft shadow.",
            "Huge '24°' filled with a 150-degree 3-stop gradient applied to the glyphs.",
            "Sun-path card: dashed semicircle, gradient trail to the sun at 60 % of the day, sunrise/sunset labels.",
            "Weekly card: vertical rotated label 'HAFTALIK TAHMİN', 7 rows from a model, range bars on a shared 16-28 °C scale with the gradient mapped to the scale.",
            "Hourly strip of 8 from a model with 'Şimdi' selected.",
            "Air-quality ring: 270-degree conic gradient with a knob and '42' in the center.",
            "Wind compass with the needle rotated 225 degrees.",
        ],
        "niceToHave": ["Bars, ring and needle driven by data.", "Details list from a model."],
        "allowedApproximations": ["Gradient-text interpolation.", "Arc dash pattern.", "Shadow as one layer.", "Ring hollow via Shape arcs."],
        "forbidden": ["Raster crops of the input."],
        "thresholds": {"note": "Font is outside the catalog: text is scored by position (left/center/right edge and baseline), not by glyph shapes."},
    },
}


def main() -> None:
    for case_id, spec in CASES_SPEC.items():
        d = CASES / case_id
        if not d.exists():
            raise SystemExit(f"[error] case folder missing: {d} (run build_case.py first)")
        golden = json.loads((d / "golden-spec.json").read_text())
        meta = golden["meta"]
        expected = {
            "id": case_id,
            "summary": spec["summary"],
            "input": ({"file": "source/index.html", "renderAt": {"designSize": meta["designSize"], "dpr": meta["dpr"]},
                       "fonts": "source/fonts (the build's font files)"}
                      if meta.get("category") == "html" else
                      {"file": "input.png", "size": meta["captureSize"], "dpr": meta["dpr"], "designSize": meta["designSize"]}),
            "target": "pyside6", "mode": "production", "profile": meta["profile"], "minQt": "6.8",
            "common": COMMON,
            "mustHave": spec["mustHave"],
            "niceToHave": spec["niceToHave"],
            "allowedApproximations": spec["allowedApproximations"],
            "forbidden": spec["forbidden"],
        }
        thresholds = {**BASE_THRESHOLDS, **spec["thresholds"]}
        if int(case_id[:2]) > 8:
            thresholds["calibratedOn"] = "carried over from cases 01-08: " + BASE_THRESHOLDS["calibratedOn"]
        (d / "expected.json").write_text(json.dumps(expected, indent=1, ensure_ascii=False))
        (d / "thresholds.json").write_text(json.dumps(thresholds, indent=1, ensure_ascii=False))
        print(f"{case_id}: {len(spec['mustHave'])} must-have, thresholds SSIM {thresholds['globalSSIM']}")


if __name__ == "__main__":
    main()
