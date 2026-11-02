# Scripts

Every script prints `--help` and exits 0 (ok), 1 (below threshold / gate failed) or 2 (could
not run). The commands SKILL.md gives are the ones a build needs; this list is for the rest.

| Script | Purpose |
| --- | --- |
| `analyze.py` | draft spec from a screenshot: palette + surfaces + OCR, overlay and OCR sheet; `--match` adds a first font/icon match; prints the draft as a table |
| `html_to_spec.py` | HTML input: render the page (Chromium) → `input.png` + a truth spec, icon SVGs, font files |
| `palette.py` · `geometry.py` · `text_ocr.py` | the three analyzers on their own |
| `match.py` | fonts, icons, shadows, gradients measured into the spec; prints what to confirm (icon alternatives, the measured size scale); `--fonts-dir` bundles static TTFs |
| `font_match.py` · `icon_match.py` | font family/weight/size per run; icon set:name + stroke; `fetch` the caches, `export` an SVG |
| `shadow_fit.py` · `gradient_fit.py` | CSS box-shadow / linear-gradient of one box (`--box`) or a whole spec |
| `probe.py` | colors at points, regions, edge/border/padding runs (many boxes per call); zoomed crops; coordinate ruler |
| `spec_view.py` | a spec as a compact table (tokens, nodes, text, icons; `--verify`, `--ids`) |
| `sheet.py` | contact sheets: `compare` (worst items, source \| render) and `ocr` (all text runs) |
| `validate_spec.py` | schema + consistency checks for design-spec.json |
| `qt5.py` | Qt 5.15: `check` what 5.15 cannot load, `port` a Qt 6 tree's imports, pragmas and qmldirs |
| `scaffold.py` | new project (shared `assets/templates/project` + a `pyside6` and/or `cpp` host, `--min-qt 5.15` for the Qt 5 host); `--add-host` |
| `gen_theme.py` | Theme.qml + Icons.qml from the spec tokens (5.15 imports when `meta.minQt` is 5.15) |
| `render.py` | headless render at size × DPR + `scene.json` (texts, images, QML warnings, perf); `--interact` → `interaction.json`; `--lang xx` loads a translation; `--scenegraph software` |
| `diff.py` | source vs render: SSIM, ΔE2000, geometry, text positions (glyph metrics from the project's fonts), spec audit against the draft → `report.json`, `diff.png` |
| `quality_gate.py` | 13 gates (static, runtime, a11y, states, i18n, effects, perf, cpp) → `gate.json` |
| `check.py` | render + diff + C++ build + gates in one command |
| `build_cpp.py` | CMake configure/build (Qt 6 or Qt 5.15), run with `APP_GRAB`, parity with the PySide6 render, `--install` |
| `deploy.py` | desktop bundle (pyside6-deploy / cmake --install, windeployqt for Qt 5) or a board's kiosk service files |
