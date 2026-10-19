# Eval designs 09–20: brief (v1.0)

You are adding original eval screens to the `screenshot-to-qml` eval set. Each screen is an HTML
template rendered by headless Chromium into `input.png` plus a ground-truth `golden-spec.json`.
Agents later rebuild the screen in Qt Quick from the PNG, and the result is scored against the
golden spec, so the templates must follow the conventions below exactly.

Repo: `/home/claude/work/screenshot-to-qml`. Work only in `evals/tools/designs/<your files>` and
`evals/cases/<your case ids>/` (written by the build). Do not edit `build_case.py`, `extract.js`,
`_charts.js`, `expectations.py`, other designs, or anything else; if you think a tool needs a
change, say so in your report.

## Hard rules

- **Original and fictional.** Invent brand/product names; no real companies, products, logos,
  people or trademarks (no "Google", "Visa", "Tesla" …). Real city names are fine.
- **Turkish UI text** with the special letters (ç ğ ı İ ö ş ü) appearing naturally, including at
  least one `text-transform: uppercase` run with an i/ı (Turkish İ). `<html lang="tr">`.
- **No raster images, no emoji, no external resources.** Everything is drawn with CSS/SVG. Avatars
  are initials on colored circles; "photos" are gradients. No `content:` text in CSS (text must be
  real DOM text nodes to be in the golden spec).
- **Looks like a real, polished product screenshot**: consistent spacing scale, aligned grid,
  realistic data, no accidental overlaps or clipped text (unless the brief asks for clipping).
- Fonts: only the families in your case meta, loaded by the build from `evals/assets/fonts`
  (see the table below for available weights). Do not add `@font-face` yourself.
- Icons: `<i data-icon="lucide:name" class="ic"></i>` (sets: `lucide`, `tabler`, `tabler-filled`).
  Do not use `fa`. Size icons with CSS on `svg.ic` (width/height), color with `color:`; lucide
  stroke width via `stroke-width` CSS on the svg if needed. Icon names must exist in
  lucide-static 1.48 / @tabler/icons 3.48 (`ls /home/claude/work/pkg/*/package/icons`).

## Template conventions (copy the structure of `designs/05-settings-form.html`)

```html
<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<title>…</title>
<script type="application/json" id="case-meta">
{"id": "09-…", "title": "…", "category": "dashboard", "profile": "desktop",
 "viewport": [1440, 900], "dpr": 1.5, "fonts": ["Onest"]}
</script>
<script type="application/json" id="case-data">{ …the data behind lists/charts… }</script>
<!--@fonts-->
<!--@charts-->            (only if you use Charts.*; then call Charts.done() at the end)
<style>
:root { --color-…: #…; --space-…: …px; --radius-…: …px; --shadow-…: …; }
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: Wpx; height: Hpx; overflow: hidden; }
…
</style>
</head>
<body> … </body>
</html>
```

- **Tokens** on `:root` as `--color-*`, `--space-*`, `--radius-*`, `--shadow-*`; use `var()` for them.
- **Semantic markup attributes** (stripped from the HTML snapshot, used for the golden spec):
  - `data-node="name"` on every meaningful element (panels, cards, controls, list rows, chart
    containers, badges). Repeated items share one name (they become `name[0]`, `name[1]` …).
  - `data-role` — Qt-ish role: `Button`, `IconButton`, `TextField`, `TextArea`, `ComboBox`,
    `CheckBox`, `RadioButton`, `Switch`, `Slider`, `SpinBox`, `TabBar`, `Tab`, `NavItem`,
    `Sidebar`, `Header`, `Footer`, `Panel`, `Card`, `ListItem`, `TableRow`, `HeaderCell`,
    `Badge`, `Chip`, `Chart`, `Gauge`, `ProgressBar`, `Popup`, `Tooltip`, `Toast`, `Avatar` …
  - `data-state` — space-separated: `selected checked disabled focused hover pressed error
    placeholder loading open indeterminate expanded collapsed editing`.
  - `data-model="listName"` on the container whose direct `data-node` children are the repeated items.
  - `data-value` on controls (slider value, progress, selected option).
- **Charts**: `_charts.js` offers `Charts.line`, `Charts.spark`, `Charts.bars`, `Charts.donut`,
  `Charts.ring` drawing into `<svg id=…>` (see `designs/03-dashboard-dark.html` and
  `04-dashboard-light.html` for usage). Hand-written inline SVG is fine too. Put the chart data in
  `case-data`.
- Canvas: `html, body` exactly the viewport size, `overflow: hidden`.

## Build and check (repeat until good)

```bash
cd /home/claude/work/screenshot-to-qml/evals/tools
python build_case.py --only 09 --pkg /home/claude/work/pkg      # must exit 0, no [warn] lines
```

Then **look at `evals/cases/<id>/input.png`** (open the image) and fix anything that looks off.
Also sanity-check the golden spec with a short Python snippet: every `text[].string` is what you
meant (Turkish letters intact), every text bbox lies inside the viewport, `nodes` have the ids you
expect, `icons` resolved. Iterate until the screen looks like a shipped product.

## Fonts available (family: weights)

Onest 400–700 · Sora 300–700 · Albert Sans 400–700 · Red Hat Display 500–800 ·
Red Hat Text 400–600 · Mulish 400–800 · Public Sans 400–700 · Instrument Sans 400–700 ·
Karla 400–700 · Bricolage Grotesque 300–800 · Rajdhani 400/500/600/700 ·
Titillium Web 300/400/600/700 · Be Vietnam Pro 400/500/600/700 · DM Mono 400/500 ·
IBM Plex Mono 400/500/600 (plus the older ones: Inter, JetBrains Mono, Manrope, DM Sans,
Space Grotesk, Nunito, Outfit, Plus Jakarta Sans, Barlow — do not use these for new cases).

Use only weights that exist.

## Report back (for each case)

1. The case meta line and a one-sentence summary (English).
2. 6–9 **mustHave** bullets in the style of `evals/tools/expectations.py` (what a correct Qt
   rebuild must contain: models and their counts, control states, notable geometry/effects),
   plus niceToHave, allowedApproximations, forbidden (English).
3. Anything that makes the case unusually hard to score (so thresholds can be set).
4. Build output line (`id: WxH @dpr nodes= text= icons= colors=`).

---

## The cases

### 09-dashboard-sales — group A
- category `dashboard`, profile `desktop`, viewport 1440×900, **dpr 1.5**, fonts `Onest`.
- Light sales analytics for a fictional online textile shop. Collapsed icon-only rail (≈72 px) with
  a selected item; header with page title, a date-range button and a segmented control
  (Gün/Hafta/Ay, "Ay" selected).
- 4 KPI tiles (model) with delta chips (up = green, down = red, arrow icons).
- Revenue line chart: this year (solid, with soft area) vs last year (**dashed**), 12 months, with
  a **hover state**: vertical guide line, highlighted point and a tooltip bubble with two values.
- Conversion funnel: 4 horizontal bars of decreasing width with labels and percentages.
- Category share: one horizontal **stacked bar** with a legend (5 categories).
- Top products list (5 rows, model) with colored initial tiles, units and revenue right-aligned.

### 10-dashboard-ops-dark — group A
- category `dashboard`, profile `desktop`, viewport **1920×1080**, dpr 1, fonts `Sora`, `DM Mono`.
- Dark network operations center for a fictional ISP. Top bar with breadcrumbs, a static "CANLI"
  live indicator, search field.
- 3 **semicircle gauges** (CPU, bellek, bant genişliği) with needle-free arcs and big values.
- Region latency **heatmap**: 7 rows (days) × 24 columns (hours) of cells colored on a 5-step
  scale (model), hour labels every 3 h, legend.
- Throughput area chart with gradient fill (2 series).
- Incident list (5, model) with severity chips (Kritik/Yüksek/Orta), durations.
- Live log panel in DM Mono: ~12 lines with timestamps, colored level tags (INFO/WARN/ERR),
  columns aligned by the monospace font; the last line partly cut by the panel's bottom (clip).

### 17-data-table-stock — group A
- category `table`, profile `desktop`, viewport 1366×768, dpr 1, fonts `Public Sans`, `IBM Plex Mono`.
- Dense inventory table. Toolbar: search with value, filter button with count badge, column menu,
  export button.
- Table of ~14 visible rows with **zebra stripes**; a **frozen first column** (SKU in IBM Plex
  Mono) with a subtle edge shadow because the table scrolls horizontally; the last visible
  column is cut at the right edge (horizontal scroll), and a styled horizontal scrollbar shows.
- Numeric columns right-aligned with Turkish separators ("1.248", "₺3.450,00"), a stock-level
  mini bar, status pill (3 variants).
- **Group header rows** ("Depo: Ankara · 6 ürün") with expand/collapse chevrons; one group
  collapsed.
- One row in **inline-edit** state (a cell shows an input with focus ring).
- Header with sort indicator and a column resize handle; footer with totals row and pagination
  ("1–14 / 326", rows-per-page select).

### 11-hmi-boiler — group B
- category `hmi`, profile `embedded-gpu`, viewport 1280×800, dpr 1, fonts `Rajdhani`.
- High-performance HMI (ISA-101 style: gray background, color only for state/abnormal) for a
  fictional boiler room. Top alarm banner (one active alarm, amber) with time and acknowledge
  button.
- Main **mimic diagram** (inline SVG): 2 boilers (with level fill), a buffer tank, pipes with
  elbows (hot supply, return, gas line in distinct muted colors), 2 pumps (circle + triangle; one
  running = filled, one stopped = outline), 3 valves (bow-tie; open vs closed), flow arrows,
  sensor tag boxes (e.g. "TT-101 78,4 °C", "PT-201 2,35 bar").
- Right panel: 3 setpoints with big −/+ steppers (touch targets ≥ 56 px) and a mode switch.
- Bottom soft-key bar with 6 navigation buttons (model), one selected.
- No shadows or blur (embedded GPU); flat fills and strokes.

### 12-ev-charger — group B
- category `kiosk`, profile **`embedded-sw`**, viewport **1024×600**, dpr 1, fonts `Titillium Web`.
- 7-inch touch screen of a fictional EV charging station during a session.
- Big battery percentage and a **segmented progress bar** (e.g. 20 segments, 14 lit), charged
  energy (kWh), power (kW), remaining time, cost (₺ with Turkish decimals).
- Connector card (type, max power, connector icon), session id in a monospace-looking style
  (use the same font, tabular numbers).
- Language buttons (TR/EN/DE, TR selected), a large red "ŞARJI DURDUR" button, a secondary
  "Yardım" button.
- **Flat design only**: no box-shadow, no blur, no filters, no opacity layers (software
  renderer). Gradients allowed only as simple 2-stop linear fills.

### 20-hard-weather — group B
- category `hard`, profile `desktop`, viewport 1280×800, **dpr 2**, fonts **`Bricolage Grotesque`**
  (this family is deliberately NOT in the skill's font catalog: the case tests the fallback when
  the font cannot be identified).
- Editorial weather dashboard for İzmir. Hard features, all of them:
  - huge temperature "24°" with **gradient text** (`background-clip: text`),
  - a **sun-path arc** (dashed SVG arc with the sun's current position and sunrise/sunset times),
  - a **vertically rotated label** (`writing-mode` or `rotate(-90deg)`), e.g. "HAFTALIK TAHMİN",
  - 7-day list (model) with **temperature range bars** positioned by min/max on a shared scale
    and filled with a warm-cold gradient,
  - hourly strip (8 items, model) with icons,
  - air-quality ring drawn with a **conic gradient** and a center value,
  - a wind compass with a rotated arrow (e.g. 225°),
  - background made of 2–3 large radial gradients (mesh look).
- Mixed tracking: an uppercase label with wide letter-spacing.

### 13-form-wizard — group C
- category `form`, profile `desktop`, viewport 1280×800, **dpr 1.25**, fonts `Albert Sans`.
- Multi-step "new device registration" wizard. Horizontal stepper: 2 completed (check icons), 1
  current, 2 upcoming.
- Step form with: 2 text fields (one filled, one placeholder), a **date field with an open
  calendar popup** overlaying the form (month grid 6×7 as a model, selected day, today outlined,
  past days disabled, prev/next buttons), a combo box, a textarea with a character counter
  ("84/200"), a **tag input** with 3 removable chips, a **dashed-border drop zone** and one
  uploaded file row with a progress bar at 64 %.
- Footer: "Geri" (secondary), "Taslak olarak kaydet" (ghost), "Devam" (primary).

### 14-form-login-dark — group C
- category `form`, profile `desktop`, viewport 1280×800, **dpr 2**, fonts `Red Hat Display`
  (headings), `Red Hat Text` (body).
- Dark split screen sign-in for a fictional password vault. Left: brand panel with 2–3 large
  radial gradients, product name, a headline and 3 feature bullets with icons (no testimonials).
- Right: form — e-mail field (filled, valid check icon), password field (masked "••••••••••",
  eye toggle icon), a **caps-lock warning** hint under it, "Beni hatırla" checkbox (checked),
  "Şifremi unuttum" link, primary button in **loading** state (spinner + "Giriş yapılıyor…"),
  divider "veya", 2 secondary buttons ("Kurumsal SSO", "Güvenlik anahtarı") with icons.
- A **toast** in the top-right corner ("Oturum süreniz doldu…") with an icon and close button.

### 19-html-css-board — group C  (HTML-input case)
- category `html`, profile `desktop`, viewport 1366×768, **dpr 2**, fonts `Karla`.
- Agents will receive the **HTML snapshot** (not the PNG), so write clean, realistic hand-written
  CSS (custom properties, flex/grid, `gap`, `:hover`-free static states) and **use real HTML
  elements** where a real page would: `<header> <nav> <main> <button> <input type="search"
  value="…"> <select>` with a selected option, `<label>`, `<input type="checkbox">` styled with
  `appearance: none`, `<progress>` or a div bar. (The build records input/select/textarea text.)
- Content: a content-calendar **kanban board**: 4 columns (Fikir / Yazılıyor / İncelemede /
  Yayında) with count badges, 2–4 cards each (tags, title, due date, avatar stack, checklist
  progress "3/5"), a column-level "Kart ekle" button; top bar with search, filter selects, view
  toggle (Pano/Liste, Pano selected) and a primary button.

### 15-mobile-wallet — group D
- category `mobile`, profile `desktop`, viewport **393×852**, **dpr 3**, fonts `Mulish`.
- Wallet app home. Status bar (9:41, signal/wifi/battery icons), header with initials avatar and
  greeting, **balance card** with a gradient and masked card number "•••• 4821", quick actions
  (4 round buttons: Gönder, İste, Yükle, Öde), segmented tabs (Tümü/Gelen/Giden, Tümü selected),
  transaction list **grouped by date** with section headers ("Bugün", "Dün") — ≥ 6 rows, icon
  tiles, amounts right-aligned (+ green / − ink), the last row partly under the bottom nav;
  bottom nav (5 items, center one raised) and home indicator.

### 16-mobile-chat — group D
- category `mobile`, profile `desktop`, viewport **360×800**, **dpr 2**, fonts `Be Vietnam Pro`.
- Team chat (Android-like). App bar: back arrow, **avatar stack** (3 overlapping initials +
  "+3"), title + subtitle "8 üye · 3 çevrimiçi", call/more icons.
- Message list: date separator chip, incoming bubbles (gray, sender name in a per-user color,
  small avatar on the last bubble of a group), outgoing bubbles (primary color, right-aligned)
  with **asymmetric corner radii**, multi-line wrapped text, a **reply quote** inside one bubble,
  a **voice message** bubble with a play button and ~28 waveform bars (model), timestamps and
  **double read ticks**, a reaction chip (heart icon + "2") on one bubble, a **typing indicator**
  (3 dots) at the bottom.
- Composer: attach icon, field with placeholder "Mesaj yazın…", mic button; gesture bar.

### 18-html-tailwind-billing — group D  (HTML-input case)
- category `html`, profile `desktop`, viewport 1280×800, dpr 1, fonts `Instrument Sans`.
- Agents will receive the **HTML snapshot**, so this one is written with **Tailwind CSS v4
  utility classes**. Author the markup with utilities, compile the CSS with the Tailwind v4 CLI
  (`npm i -D @tailwindcss/cli@4` in a scratch folder; input CSS `@import "tailwindcss";` + an
  `@theme { --font-sans: "Instrument Sans", sans-serif; … }` block; `@source` your HTML), and
  paste the compiled CSS into the template's `<style>` (keep the Tailwind banner comment, and add
  a short comment saying how it was generated). Use Tailwind's default palette (oklch colors) —
  that is part of the test. Keep `<!--@fonts-->` before the style.
- Real elements: `<button>`, `<input type="checkbox" role="switch">` styled as a toggle,
  `<table>` for invoices, `<label>`.
- Content: "Plan ve faturalama" settings page: monthly/yearly toggle (yearly on, "2 ay bedava"
  badge), 3 plan cards (middle one highlighted with a ring and "Önerilen" badge, current plan
  marked), usage meters (3 progress bars with "12 / 20 kullanıcı" style labels), payment method
  card (masked number, expiry, generic card icon, "Değiştir" button), invoices table (4 rows,
  status badges, download icon buttons).
