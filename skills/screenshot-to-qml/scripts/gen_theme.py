#!/usr/bin/env python3
"""Generate Theme.qml (and Icons.qml) from design-spec.json tokens.

Usage:
  python gen_theme.py design-spec.json OUT_STYLE_DIR [--no-format]

OUT_STYLE_DIR is usually PROJECT/qml/App/Style (its qmldir must list Theme and Icons as
singletons; scaffold.py creates it). Generates:

  Theme.qml   designWidth/Height; every tokens.color (#AARRGGBB when alpha < 1, CSS rgba in a
              comment); space*/radius* ints; fontSans/fontMono/fontIcon families; one font
              token per typeScale entry (name = entry.name, or text<px><Weight>); line-height
              ints lh<Name>; alpha() helper
  Icons.qml   one string per icon-font glyph in spec.icons (kind font-glyph with codepoint)

Token names are made QML-safe: camelCase, no leading digit, and never 'on' + capital
(signal-handler syntax) — 'onAccent' becomes 'accentInk'.
The files are qmlformat-ed when qmlformat is available. Rename font tokens by role
(title, body, caption …) in the spec (typeScale[].name) and re-run instead of editing the QML.

Exit codes: 0 ok, 2 error.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

WEIGHTS = {100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Normal", 500: "Medium",
           600: "DemiBold", 700: "Bold", 800: "ExtraBold", 900: "Black"}
ICON_FONT_HINTS = ("awesome", "symbols", "icons", "lucide", "tabler", "phosphor")


def qml_name(raw: str, prefix: str = "") -> str:
    parts = [p for p in re.split(r"[^0-9A-Za-z]+", raw) if p]
    if not parts:
        parts = ["token"]
    name = parts[0][0].lower() + parts[0][1:] + "".join(p[:1].upper() + p[1:] for p in parts[1:])
    if prefix:
        name = prefix + name[:1].upper() + name[1:]
    if name[0].isdigit():
        name = "c" + name
    if re.match(r"on[A-Z0-9]", name):
        name = name[2].lower() + name[3:] + "Ink"
    return name


def qcolor(hex_: str, alpha: float) -> str:
    if alpha >= 0.999:
        return f'"{hex_.upper()}"'
    return f'"#{round(alpha * 255):02X}{hex_[1:].upper()}"'


def weight_enum(w: int) -> str:
    return "Font." + WEIGHTS[min(WEIGHTS, key=lambda k: abs(k - w))]


def families(spec: dict) -> dict:
    fams = [f.get("qtFamily") or f["css"] for f in spec["meta"].get("fonts", [])]
    counts: dict[str, int] = {}
    for t in spec["tokens"].get("typeScale", []):
        if t["family"] != "?":
            counts[t["family"]] = counts.get(t["family"], 0) + t.get("count", 1)
    fams += [f for f in counts if f not in fams]
    icon = next((f for f in fams if any(h in f.lower() for h in ICON_FONT_HINTS)), None)
    mono = next((f for f in fams if "mono" in f.lower() or "code" in f.lower()), None)
    text_fams = [f for f in fams if f not in (icon, mono)]
    sans = max(text_fams, key=lambda f: counts.get(f, 0)) if text_fams else "Inter"
    return {"sans": sans, "mono": mono, "icon": icon, "all": fams}


# ---- control roles ---------------------------------------------------------------------------
# App.Controls reads these names. A spec token with the same name wins; an alias points at a
# spec token; otherwise the value is derived from other roles or assumed (listed in README).
ROLE_ALIASES = {
    "bg": ("bg", "background", "page", "canvas", "base"),
    "surface": ("surface", "panel", "card", "surface1", "bgElevated"),
    "text": ("text", "textPrimary", "ink", "fg", "foreground", "textStrong"),
    "textMuted": ("textMuted", "muted", "textDim", "textSecondary", "textSubtle"),
    "placeholder": ("placeholder", "textFaint", "textPlaceholder", "textDisabled"),
    "accent": ("accent", "primary", "brand", "accentPrimary"),
    "accentInk": ("accentInk", "primaryInk", "brandInk"),
    "border": ("border", "line", "divider", "stroke", "borderSubtle"),
    "borderStrong": ("borderStrong", "borderHover", "borderInput", "lineStrong"),
    "danger": ("danger", "error", "err", "critical", "alarm", "red"),
}
TOUCH_PROFILES = ("embedded-gpu", "embedded-sw")


def _rgb(h: str) -> tuple[int, int, int]:
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _lum(h: str) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _chroma(h: str) -> float:
    r, g, b = _rgb(h)
    return (max(r, g, b) - min(r, g, b)) / 255


def control_roles(spec: dict, colors: dict, used: set, radii: dict, fonts: dict) -> list[str]:
    """Theme lines for the control contract that the spec does not define itself."""
    touch = spec["meta"].get("profile") in TOUCH_PROFILES or spec["meta"]["designSize"][0] <= 600
    out = ["", "    // control roles: the contract App.Controls uses (references/controls.md).",
           "    // Aliases point at spec tokens; 'derived' follow from them; 'assumed' are defaults to confirm."]
    have = dict(colors)

    def emit(kind, name, expr, note=""):
        if name in used:
            return
        used.add(name)
        out.append(f"    readonly property {kind} {name}: {expr}" + (f"   // {note}" if note else ""))

    def alias(role):
        if role in used:
            return role
        for a in ROLE_ALIASES.get(role, ()):
            if a in colors:
                emit("color", role, a)
                have[role] = colors[a]
                return role
        return None

    # anchors: background, text, surface, accent
    if not alias("bg"):
        bg = max(colors.items(), key=lambda kv: _lum(kv[1]))[1] if colors else "#FFFFFF"
        emit("color", "bg", f'"{bg}"', "assumed")
        have["bg"] = bg
    bg = have.get("bg", "#FFFFFF")
    if not alias("text"):
        txt = max(colors.values(), key=lambda h: _contrast(h, bg)) if colors else "#111827"
        if _contrast(txt, bg) < 4.5:
            txt = "#111827" if _lum(bg) > 0.4 else "#F3F4F6"
        emit("color", "text", f'"{txt}"', "derived: highest contrast on bg")
        have["text"] = txt
    if not alias("surface"):
        emit("color", "surface", "bg", "derived")
        have["surface"] = bg
    dark = _lum(bg) < 0.2
    if not alias("accent"):
        cands = [h for h in colors.values() if _chroma(h) > 0.25]
        acc = max(cands, key=_chroma) if cands else ("#60A5FA" if dark else "#2563EB")
        emit("color", "accent", f'"{acc}"', "derived: most saturated color" if cands else "assumed")
        have["accent"] = acc
    acc = have.get("accent", "#2563EB")
    if not alias("accentInk"):
        ink = max(("#FFFFFF", have.get("text", "#111827"), bg), key=lambda h: _contrast(h, acc))
        emit("color", "accentInk", f'"{ink}"', "derived: best contrast on accent")
    shade = "Qt.lighter({}, 1.12)" if dark else "Qt.darker({}, 1.1)"
    shade2 = "Qt.lighter({}, 1.24)" if dark else "Qt.darker({}, 1.2)"
    emit("color", "accentHover", shade.format("accent"), "derived")
    emit("color", "accentPressed", shade2.format("accent"), "derived")
    alias("textMuted") or emit("color", "textMuted", "Qt.tint(text, alpha(surface, 0.4))", "derived")
    alias("placeholder") or emit("color", "placeholder", "Qt.tint(text, alpha(surface, 0.55))", "derived")
    alias("border") or emit("color", "border", "Qt.tint(surface, alpha(text, 0.14))", "derived")
    alias("borderStrong") or emit("color", "borderStrong", "Qt.tint(surface, alpha(text, 0.28))", "derived")
    emit("color", "surfaceHover", "Qt.tint(surface, alpha(text, 0.05))", "derived")
    emit("color", "surfacePressed", "Qt.tint(surface, alpha(text, 0.1))", "derived")
    if not alias("danger"):
        emit("color", "danger", '"#F87171"' if dark else '"#DC2626"', "assumed")
        have["danger"] = "#F87171" if dark else "#DC2626"
    dng = have.get("danger", "#DC2626")
    ink = max(("#FFFFFF", have.get("text", "#111827"), bg), key=lambda h: _contrast(h, dng))
    emit("color", "dangerInk", f'"{ink}"', "derived: best contrast on danger")
    emit("color", "dangerHover", shade.format("danger"), "derived")
    emit("color", "dangerPressed", shade2.format("danger"), "derived")
    emit("color", "dangerSoft", "alpha(danger, 0.1)", "derived")
    emit("color", "focusRing", "alpha(accent, 0.4)", "derived")
    emit("color", "track", "borderStrong", "derived")
    emit("color", "knob", '"#FFFFFF"', "assumed")
    # sizes
    emit("int", "controlHeight", "48" if touch else "40", "assumed" + (": touch profile" if touch else ""))
    emit("int", "controlHeightSm", "40" if touch else "32", "assumed")
    emit("int", "controlPadding", "16" if touch else "12", "assumed")
    emit("int", "controlSpacing", "8", "assumed")
    emit("int", "touchTarget", "44", "minimum hit area on touch profiles")
    if radii:
        near = min(radii, key=lambda k: (abs(radii[k] - 8), -radii[k]))
        emit("int", "radiusControl", near, "derived: spec radius closest to 8")
    else:
        emit("int", "radiusControl", "8", "assumed")
    emit("int", "borderWidth", "1", "assumed")
    emit("int", "focusRingWidth", "3", "assumed")
    emit("int", "motionFast", "120", "ms, assumed")
    emit("real", "disabledOpacity", "0.45", "assumed")
    # control font
    px = 16 if touch else 14
    for name in ("button", "control", "label", "body"):
        if name in fonts:
            emit("font", "fontControl", name)
            break
    else:
        emit("font", "fontControl", f"Qt.font({{ family: fontSans, pixelSize: {px}, weight: Font.Medium }})", "assumed")
    for name in ("input", "body", "bodyText", "text"):
        if name in fonts:
            emit("font", "fontInput", name)
            break
    else:
        emit("font", "fontInput", f"Qt.font({{ family: fontSans, pixelSize: {px}, weight: Font.Normal }})", "assumed")
    return out if len(out) > 3 else []


def build_theme(spec: dict) -> str:
    W, H = spec["meta"]["designSize"]
    t = spec["tokens"]
    fam = families(spec)
    L = ["pragma Singleton", "import QtQuick", "",
         "// Generated by gen_theme.py from design-spec.json. Edit the spec and re-run.",
         "QtObject {", f"    readonly property int designWidth: {round(W)}",
         f"    readonly property int designHeight: {round(H)}", "", "    // colors"]
    used = set()
    colors: dict[str, str] = {}
    for raw, c in t.get("color", {}).items():
        name = qml_name(raw)
        while name in used:
            name += "2"
        used.add(name)
        if c.get("alpha", 1) >= 0.999:
            colors[name] = c["hex"].upper()
        comment = ""
        if c.get("alpha", 1) < 0.999:
            r, g, b = (int(c["hex"][i:i + 2], 16) for i in (1, 3, 5))
            comment = f"   // rgba({r},{g},{b},{c['alpha']:g})"
        if c.get("src") == "assumed" or c.get("conf", 1) < 0.7:
            comment += "   // verify: " + (c.get("src") or "") + f" conf {c.get('conf', '?')}"
        L.append(f"    readonly property color {name}: {qcolor(c['hex'], c.get('alpha', 1))}{comment}")
    if t.get("space"):
        L += ["", "    // spacing"]
        for k, v in t["space"].items():
            L.append(f"    readonly property int {qml_name(k, 'space')}: {round(v)}")
            used.add(qml_name(k, "space"))
    radii: dict[str, float] = {}
    if t.get("radius"):
        L += ["", "    // radius"]
        for k, v in t["radius"].items():
            L.append(f"    readonly property int {qml_name(k, 'radius')}: {round(v)}")
            radii[qml_name(k, "radius")] = v
    for k in (t.get("size") or {}):
        used.add(qml_name(k))
    if t.get("size"):
        L += ["", "    // sizes"]
        for k, v in t["size"].items():
            L.append(f"    readonly property int {qml_name(k)}: {round(v)}")
    L += ["", "    // typography: family names as QFontDatabase reports them",
          f'    readonly property string fontSans: "{fam["sans"]}"']
    if fam["mono"]:
        L.append(f'    readonly property string fontMono: "{fam["mono"]}"')
    L.append(f'    readonly property string fontIcon: "{fam["icon"] or ""}"')
    seen = set()
    fonts: dict[str, dict] = {}
    for ts in t.get("typeScale", []):
        family = ts["family"] if ts["family"] != "?" else fam["sans"]
        fvar = "fontMono" if family == fam["mono"] else "fontSans" if family == fam["sans"] else None
        fexpr = fvar or f'"{family}"'
        name = qml_name(ts["name"]) if ts.get("name") else f"text{round(ts['px'])}{WEIGHTS[min(WEIGHTS, key=lambda k: abs(k - ts['weight']))]}"
        if fvar == "fontMono" and not ts.get("name"):
            name = "mono" + name[4:]
        base = name
        i = 2
        while name in seen:
            name = f"{base}{i}"
            i += 1
        seen.add(name)
        fonts[name] = ts
        props = [f"family: {fexpr}", f"pixelSize: {round(ts['px'])}", f"weight: {weight_enum(ts['weight'])}"]
        if ts.get("letterSpacing"):
            props.append(f"letterSpacing: {ts['letterSpacing']:g}")
        L.append(f"    readonly property font {name}: Qt.font({{ {', '.join(props)} }})")
        lh = ts.get("lineHeight")
        if isinstance(lh, (int, float)):
            L.append(f"    readonly property real lh{name[0].upper() + name[1:]}: {lh:g}")
    L += control_roles(spec, colors, used, radii, fonts)
    L += ["", "    function alpha(c: color, a: real): color {", "        return Qt.rgba(c.r, c.g, c.b, a)", "    }", "}"]
    return "\n".join(L) + "\n"


def build_icons(spec: dict) -> str:
    L = ["pragma Singleton", "import QtQuick", "", "// Icon-font code points, generated by gen_theme.py.", "QtObject {"]
    seen = set()
    for ic in spec.get("icons", []):
        if ic.get("kind") != "font-glyph" or not ic.get("codepoint") or not ic.get("match"):
            continue
        name = qml_name(ic["match"].split(":", 1)[-1])
        if name in seen:
            continue
        seen.add(name)
        cp = ic["codepoint"].replace("U+", "").lower()
        L.append(f'    readonly property string {name}: "\\u{cp}"   // {ic["match"]}')
    L.append("}")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--no-format", action="store_true")
    args = ap.parse_args(argv)
    spec = json.loads(args.spec.read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    files = {"Theme.qml": build_theme(spec), "Icons.qml": build_icons(spec)}
    fmt = None if args.no_format else (shutil.which("pyside6-qmlformat") or shutil.which("qmlformat"))
    for name, text in files.items():
        path = args.out / name
        path.write_text(text)
        if fmt:
            subprocess.run([fmt, "-i", str(path)], capture_output=True)
    n_colors = len(spec["tokens"].get("color", {}))
    n_fonts = len(spec["tokens"].get("typeScale", []))
    print(f"wrote {args.out}/Theme.qml ({n_colors} colors, {n_fonts} font tokens) and Icons.qml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
