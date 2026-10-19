#!/usr/bin/env python3
"""Build eval cases from HTML design templates.

For every template in designs/ this script:
  1. inlines icons (<i data-icon="lucide:gauge"></i> -> inline <svg>, FA -> glyph),
  2. injects @font-face rules for the fonts listed in the case meta,
  3. renders the page in headless Chromium at the case viewport and DPR,
  4. extracts a ground-truth golden-spec.json from the live DOM
     (tokens, node boxes and styles, text runs, icons, colors used, chart data),
  5. saves input.png (the "screenshot") and a static source/index.html snapshot
     (scripts and data-* hint attributes stripped) for the HTML-input path.

Usage:
  python build_case.py                 # build all designs
  python build_case.py --only 03       # build designs whose file name starts with 03
  python build_case.py --pkg /path/to/npm/pkgs   # resolve icons not yet cached

Exit codes: 0 ok, 1 build produced warnings (missing icon, font not loaded), 2 error.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

from fontTools.ttLib import TTFont

HERE = pathlib.Path(__file__).resolve().parent
EVALS = HERE.parent
DESIGNS = HERE / "designs"
CASES = EVALS / "cases"
ASSETS = EVALS / "assets"
FONTS = ASSETS / "fonts"
ICON_CACHE = ASSETS / "icons"

ICON_RE = re.compile(r'<i\s+data-icon="([a-z0-9-]+):([a-z0-9-]+)"([^>]*)>\s*</i>')
RGB_RE = re.compile(r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)")

warnings: list[str] = []


# ----------------------------------------------------------------- fonts
def font_library() -> dict[str, list[dict]]:
    """CSS family name -> [{file, weight, qtFamily, legacyFamily}]"""
    lib: dict[str, list[dict]] = {}
    for f in sorted(FONTS.glob("*.ttf")):
        t = TTFont(f, lazy=True)
        name = t["name"]
        legacy = name.getDebugName(1)
        typo = name.getDebugName(16) or legacy
        weight = t["OS/2"].usWeightClass
        lib.setdefault(typo, []).append(
            {"file": f.name, "weight": weight, "qtFamily": typo, "legacyFamily": legacy})
    return lib


def font_face_css(families: list[str], lib: dict, rel_prefix: str) -> str:
    rules = []
    for fam in families:
        if fam not in lib:
            warnings.append(f"font family not in library: {fam}")
            continue
        for e in lib[fam]:
            rules.append(
                f"@font-face{{font-family:'{fam}';font-weight:{e['weight']};font-style:normal;"
                f"font-display:block;src:url('{rel_prefix}{e['file']}') format('truetype');}}")
    return "<style>\n" + "\n".join(rules) + "\n</style>"


# ----------------------------------------------------------------- icons
_fa_meta: dict | None = None


def fa_codepoint(name: str, pkg: pathlib.Path | None) -> str | None:
    global _fa_meta
    cache = ICON_CACHE / "fa" / "codepoints.json"
    data = json.loads(cache.read_text()) if cache.exists() else {}
    if name in data:
        return data[name]
    if pkg is None:
        return None
    if _fa_meta is None:
        import yaml
        metas = list(pkg.glob("fortawesome-fontawesome-free-*/package/metadata/icons.yml"))
        _fa_meta = yaml.safe_load(metas[0].read_text()) if metas else {}
    entry = _fa_meta.get(name)
    if not entry:
        return None
    data[name] = entry["unicode"]
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data, indent=1, sort_keys=True))
    return entry["unicode"]


def svg_source(icon_set: str, name: str, pkg: pathlib.Path | None) -> str | None:
    cached = ICON_CACHE / icon_set / f"{name}.svg"
    if cached.exists():
        return cached.read_text()
    if pkg is None:
        return None
    patterns = {
        "lucide": f"lucide-static-*/package/icons/{name}.svg",
        "tabler": f"tabler-icons-*/package/icons/outline/{name}.svg",
        "tabler-filled": f"tabler-icons-*/package/icons/filled/{name}.svg",
    }
    if icon_set not in patterns:
        return None
    hits = list(pkg.glob(patterns[icon_set]))
    if not hits:
        return None
    text = hits[0].read_text()
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(text)
    return text


def inline_icons(src: str, pkg: pathlib.Path | None) -> str:
    def repl(m: re.Match) -> str:
        icon_set, name, attrs = m.group(1), m.group(2), m.group(3)
        key = f"{icon_set}:{name}"
        if icon_set == "fa":
            cp = fa_codepoint(name, pkg)
            if cp is None:
                warnings.append(f"icon not found: {key}")
                return m.group(0)
            return f'<i data-icon="{key}"{attrs}>&#x{cp};</i>'
        svg = svg_source(icon_set, name, pkg)
        if svg is None:
            warnings.append(f"icon not found: {key}")
            return m.group(0)
        svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S).strip()
        open_tag, rest = svg.split(">", 1)
        # keep drawing attributes, drop size/class so CSS controls layout
        keep = {}
        for a in ("viewBox", "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin"):
            mm = re.search(rf'\s{a}="([^"]*)"', open_tag)
            if mm:
                keep[a] = mm.group(1)
        inner = rest.rsplit("</svg>", 1)[0]
        inner = re.sub(r"\s+", " ", inner).strip()
        attr_str = " ".join(f'{k}="{v}"' for k, v in keep.items())
        cls = f"{icon_set} {icon_set}-{name}"
        mcls = re.search(r'class="([^"]*)"', attrs)
        if mcls:
            attrs = attrs.replace(mcls.group(0), "")
            cls = f"{mcls.group(1)} {cls}"
        return (f'<svg xmlns="http://www.w3.org/2000/svg" data-icon="{key}" class="{cls}" '
                f'{attr_str}{attrs} aria-hidden="true">{inner}</svg>')

    return ICON_RE.sub(repl, src)


# ----------------------------------------------------------------- colors
def parse_color(s: str | None) -> dict | None:
    if not s:
        return None
    m = RGB_RE.fullmatch(s.strip())
    if not m:
        return None
    r, g, b = (round(float(m.group(i))) for i in (1, 2, 3))
    a = m.group(4)
    alpha = 1.0 if a is None else (float(a[:-1]) / 100 if a.endswith("%") else float(a))
    return {"hex": f"#{r:02X}{g:02X}{b:02X}", "alpha": round(alpha, 3)}


def parse_shadows(s: str | None) -> list[dict] | None:
    if not s or s == "none":
        return None
    out = []
    for part in re.split(r",(?![^()]*\))", s):
        part = part.strip()
        cm = RGB_RE.search(part)
        color = parse_color(cm.group(0)) if cm else None
        rest = RGB_RE.sub("", part)
        inset = "inset" in rest
        nums = [float(x) for x in re.findall(r"(-?[\d.]+)px", rest)]
        nums += [0.0] * (4 - len(nums))
        if color and color["alpha"] == 0:
            continue          # transparent placeholder layer (Tailwind's `0 0 #0000` ring/shadow slots)
        out.append({"x": nums[0], "y": nums[1], "blur": nums[2], "spread": nums[3],
                    "color": color, "inset": inset})
    return out or None


def length_px(raw: str) -> float | None:
    """'12px' / '0.75rem' (16 px) / Tailwind's pill 'calc(infinity * 1px)' -> px."""
    raw = raw.strip()
    if raw.startswith("calc(infinity"):
        return 9999.0
    m = re.fullmatch(r"(-?[\d.]+)(px|rem)?", raw)
    if not m:
        return None
    return float(m.group(1)) * (16 if m.group(2) == "rem" else 1)


def convert_colors(obj):
    """Recursively turn plain rgb()/rgba() strings into {hex, alpha}."""
    if isinstance(obj, dict):
        return {k: convert_colors(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_colors(v) for v in obj]
    if isinstance(obj, str):
        c = parse_color(obj)
        return c if c else obj
    return obj


# ----------------------------------------------------------------- render
EXTRACT_JS = (HERE / "extract.js").read_text()


def build(template: pathlib.Path, pkg: pathlib.Path | None, lib: dict) -> dict:
    from playwright.sync_api import sync_playwright

    raw = template.read_text()
    meta_m = re.search(r'<script type="application/json" id="case-meta">(.*?)</script>', raw, re.S)
    if not meta_m:
        raise SystemExit(f"[error] {template.name}: missing case-meta script")
    meta = json.loads(meta_m.group(1))
    case_dir = CASES / meta["id"]
    src_dir = case_dir / "source"
    src_dir.mkdir(parents=True, exist_ok=True)

    page_src = inline_icons(raw, pkg)
    rel = "../../../assets/fonts/"
    page_src = page_src.replace("<!--@fonts-->", font_face_css(meta["fonts"], lib, rel))
    charts = (HERE / "designs" / "_charts.js").read_text()
    page_src = page_src.replace("<!--@charts-->", f"<script>\n{charts}\n</script>")
    build_file = src_dir / "_build.html"
    build_file.write_text(page_src)

    w, h = meta["viewport"]
    dpr = meta.get("dpr", 1)
    with sync_playwright() as p:
        # No hinting + subpixel positioning: fractional glyph advances like macOS/Windows
        # and Qt's default text renderer (headless Linux Chrome otherwise rounds advances).
        browser = p.chromium.launch(args=["--font-render-hinting=none"])
        ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=dpr,
                                  locale="tr-TR")
        page = ctx.new_page()
        console = []
        page.on("console", lambda m: console.append(f"{m.type}: {m.text}"))
        page.on("pageerror", lambda e: console.append(f"pageerror: {e}"))
        page.goto(build_file.as_uri())
        page.evaluate("document.fonts.ready.then(() => true)")
        page.wait_for_function("window.__chartsDone !== false", timeout=5000)
        page.wait_for_timeout(150)
        loaded = page.evaluate("[...document.fonts].filter(f => f.status === 'loaded').map(f => f.family + ' ' + f.weight)")
        spec = page.evaluate(EXTRACT_JS)
        page.screenshot(path=str(case_dir / "input.png"), full_page=False)
        page.evaluate("""() => {
            document.querySelectorAll('script').forEach(s => s.remove());
            document.querySelectorAll('*').forEach(el => {
                for (const a of [...el.attributes]) if (a.name.startsWith('data-')) el.removeAttribute(a.name);
            });
            // Playwright's caret hiding leaves style="" on inputs after page.screenshot()
            document.querySelectorAll('[style=""]').forEach(el => el.removeAttribute('style'));
        }""")
        snapshot = page.content()
        browser.close()
    for c in console:
        if c.startswith(("error", "pageerror", "warning")):
            warnings.append(f"{meta['id']} console {c}")
    used_families = {t["font"]["family"] for t in spec["text"]} | {
        i["font"]["family"] for i in spec["icons"] if i.get("font")}
    for fam in used_families:
        if not any(ld.startswith(fam.strip("\"'") + " ") for ld in loaded):
            warnings.append(f"{meta['id']}: font used but not loaded from library: {fam}")

    if meta.get("category") == "html":
        # HTML-input cases are handed to agents as-is: make source/ self-contained
        font_dir = src_dir / "fonts"
        font_dir.mkdir(exist_ok=True)
        for fam in meta["fonts"]:
            for e in lib.get(fam, []):
                (font_dir / e["file"]).write_bytes((FONTS / e["file"]).read_bytes())
        snapshot = snapshot.replace(rel, "fonts/")
    (src_dir / "index.html").write_text(snapshot)
    build_file.unlink()

    spec = post_process(spec, meta, lib)
    (case_dir / "golden-spec.json").write_text(json.dumps(spec, indent=1, ensure_ascii=False))
    return spec


def post_process(spec: dict, meta: dict, lib: dict) -> dict:
    # tokens
    tok = {"color": {}, "space": {}, "radius": {}, "shadow": {}, "other": {}}
    for name, t in spec.pop("rawTokens").items():
        short = name.lstrip("-")
        if short.startswith("color-") and t.get("color"):
            c = parse_color(t["color"]) or {}
            tok["color"][short[6:]] = {**c, "src": "truth", "conf": 1.0, "css": t["raw"]}
        elif short.startswith("space-") and length_px(t["raw"]) is not None:
            tok["space"][short[6:]] = length_px(t["raw"])
        elif short.startswith("radius-") and length_px(t["raw"]) is not None:
            tok["radius"][short[7:]] = length_px(t["raw"])
        elif short.startswith("shadow-"):
            tok["shadow"][short[7:]] = {"css": t["raw"]}
        else:
            tok["other"][short] = t["raw"]
    # type scale derived from rendered text runs
    scale: dict[tuple, dict] = {}
    for t in spec["text"]:
        f = t["font"]
        key = (f["family"], f["px"], f["weight"], f["lineHeight"], f["letterSpacing"])
        e = scale.setdefault(key, {"family": f["family"], "px": f["px"], "weight": f["weight"],
                                   "lineHeight": f["lineHeight"], "letterSpacing": f["letterSpacing"],
                                   "count": 0, "example": t["string"][:40]})
        e["count"] += 1
    tok["typeScale"] = sorted(scale.values(), key=lambda e: (-e["px"], -e["weight"]))

    for t in spec["text"]:
        t["font"] = {k: v for k, v in t["font"].items() if v is not None and v is not False or k == "italic"}
    for n in spec["nodes"]:
        st = n["style"]
        if "shadow" in st:
            st["shadow"] = parse_shadows(st["shadow"])
            if st["shadow"] is None:
                del st["shadow"]
    spec = convert_colors(spec)
    spec["tokens"] = tok

    fonts = []
    for fam in meta["fonts"]:
        entries = lib.get(fam, [])
        fonts.append({"css": fam, "qtFamily": entries[0]["qtFamily"] if entries else None,
                      "legacyFamily": entries[0]["legacyFamily"] if entries else None,
                      "files": [e["file"] for e in entries],
                      "weights": sorted(e["weight"] for e in entries)})
    w, h = meta["viewport"]
    dpr = meta.get("dpr", 1)
    ordered = {
        "meta": {
            "id": meta["id"], "title": meta.get("title"), "category": meta.get("category"),
            "profile": meta.get("profile", "desktop"), "lang": spec.pop("lang"),
            "designSize": [w, h], "dpr": dpr, "captureSize": [round(w * dpr), round(h * dpr)],
            "units": "CSS px at 1x (design px). Multiply by dpr for input.png pixels.",
            "fonts": fonts,
        },
        "tokens": spec["tokens"],
        "nodes": spec["nodes"],
        "text": spec["text"],
        "icons": spec["icons"],
        "colorsUsed": spec["colorsUsed"],
        "data": spec.get("data"),
        "states": spec.get("states", {}),
    }
    return ordered


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="build templates whose name starts with this prefix")
    ap.add_argument("--pkg", type=pathlib.Path, help="dir with extracted npm icon packages")
    args = ap.parse_args()
    lib = font_library()
    templates = sorted(t for t in DESIGNS.glob("*.html") if not t.name.startswith("_"))
    if args.only:
        templates = [t for t in templates if t.name.startswith(args.only)]
    if not templates:
        print("[error] no templates matched", file=sys.stderr)
        return 2
    for t in templates:
        spec = build(t, args.pkg, lib)
        m = spec["meta"]
        print(f"{m['id']}: {m['captureSize'][0]}x{m['captureSize'][1]} @{m['dpr']}x  "
              f"nodes={len(spec['nodes'])} text={len(spec['text'])} icons={len(spec['icons'])} "
              f"colors={len(spec['tokens']['color'])}")
    for w in warnings:
        print(f"[warn] {w}", file=sys.stderr)
    return 1 if warnings else 0


if __name__ == "__main__":
    sys.exit(main())
