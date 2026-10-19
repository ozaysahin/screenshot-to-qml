#!/usr/bin/env python3
"""Render an HTML page and extract a design-spec from its live DOM (the HTML-input path).

Usage:
  python html_to_spec.py page.html --size 1280 800 [--dpr 2] [--out-dir analysis]
                         [--lang tr-TR] [--wait-ms 300] [--json]

Writes to --out-dir (default: analysis/):
  input.png          the page rendered at size x dpr: the reference image for check.py
  design-spec.json   values measured from the DOM, all src "truth": tokens from :root custom
                     properties (Tailwind v4 @theme too; oklch converted to sRGB hex), nodes
                     (painted boxes, controls, landmarks, repeated children as models), every
                     text run with font/baseline, form-field values and placeholders, icons
  icons/iN.svg       each inline SVG icon (<= 64 px), ready for VectorImage / svgtoqml
  fonts/             font files the page loads from local @font-face URLs (bundle these)

The page is rendered by headless Chromium with --font-render-hinting=none, so text metrics
match Qt's (references/typography.md). Scripts and network requests run as in a browser;
remote resources that fail to load are reported.

Needs Playwright: pip install playwright && python -m playwright install chromium

Exit codes: 0 ok, 1 written with warnings (a font or resource failed to load),
            2 could not run (missing page, Playwright or Chromium).
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

HERE = Path(__file__).resolve().parent
EXTRACT_JS = HERE / "html_extract.js"
RGB_RE = re.compile(r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)")


def parse_color(s):
    if not isinstance(s, str):
        return None
    m = RGB_RE.fullmatch(s.strip())
    if not m:
        return None
    r, g, b = (round(float(m.group(i))) for i in (1, 2, 3))
    a = m.group(4)
    alpha = 1.0 if a is None else (float(a[:-1]) / 100 if a.endswith("%") else float(a))
    return {"hex": f"#{r:02X}{g:02X}{b:02X}", "alpha": round(alpha, 3)}


def convert_colors(obj, skip=("svg", "file", "src", "fillImage", "transform")):
    if isinstance(obj, dict):
        return {k: (v if k in skip else convert_colors(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_colors(v) for v in obj]
    if isinstance(obj, str):
        return parse_color(obj) or obj
    return obj


def parse_shadows(s):
    """CSS box-shadow list -> layers; transparent placeholder layers (Tailwind's `0 0 #0000`) dropped."""
    out = []
    for part in re.split(r",(?![^()]*\))", s or ""):
        part = part.strip()
        if not part or part == "none":
            continue
        cm = RGB_RE.search(part)
        color = parse_color(cm.group(0)) if cm else None
        if color and color["alpha"] == 0:
            continue
        rest = RGB_RE.sub("", part)
        nums = [float(x) for x in re.findall(r"(-?[\d.]+)px", rest)] + [0.0] * 4
        out.append({"x": nums[0], "y": nums[1], "blur": nums[2], "spread": nums[3], "color": color, "inset": "inset" in rest})
    return out


def length_px(raw: str):
    raw = raw.strip()
    if raw.startswith("calc(infinity"):
        return 9999.0
    m = re.fullmatch(r"(-?[\d.]+)(px|rem)?", raw)
    return float(m.group(1)) * (16 if m.group(2) == "rem" else 1) if m else None


def tokens_from(raw_tokens: dict, text: list) -> dict:
    tok = {"color": {}, "space": {}, "radius": {}, "shadow": {}, "other": {}}
    for name, t in raw_tokens.items():
        short = name.lstrip("-")
        if short.startswith("color-") and parse_color(t.get("color")):
            tok["color"][short[6:]] = {**parse_color(t["color"]), "src": "truth", "conf": 1.0, "css": t["raw"]}
        elif short.startswith(("space-", "spacing-")) and length_px(t["raw"]) is not None:
            tok["space"][short.split("-", 1)[1]] = length_px(t["raw"])
        elif short.startswith("radius-") and length_px(t["raw"]) is not None:
            tok["radius"][short[7:]] = length_px(t["raw"])
        elif short.startswith("shadow-"):
            tok["shadow"][short[7:]] = {"css": t["raw"]}
        elif parse_color(t.get("color")) and "var(" not in t["raw"]:   # other color variables (--bg, --primary …)
            tok["color"][short] = {**parse_color(t["color"]), "src": "truth", "conf": 1.0, "css": t["raw"]}
        else:
            tok["other"][short] = t["raw"]
    scale = {}
    for r in text:
        f = r["font"]
        key = (f["family"], f["px"], f["weight"], f.get("lineHeight"), f.get("letterSpacing"))
        e = scale.setdefault(key, {"family": f["family"], "px": f["px"], "weight": f["weight"], "lineHeight": f.get("lineHeight"),
                                   "letterSpacing": f.get("letterSpacing"), "count": 0, "example": r["string"][:40]})
        e["count"] += 1
    tok["typeScale"] = sorted(scale.values(), key=lambda e: (-e["px"], -e["weight"]))
    return tok


def font_names(path: Path):
    try:
        from fontTools.ttLib import TTFont
        t = TTFont(path, lazy=True, fontNumber=0)
        name = t["name"]
        return (name.getDebugName(16) or name.getDebugName(1)), name.getDebugName(1), t["OS/2"].usWeightClass
    except Exception:           # noqa: BLE001 - woff2 without brotli, broken files
        return None, None, None


def collect_fonts(faces: list, loaded: list, used: set, out_dir: Path) -> tuple[list, list]:
    """Copy local @font-face files of the used families into out_dir/fonts; meta.fonts entries."""
    warnings, fonts, copied = [], {}, set()
    fdir = out_dir / "fonts"
    for face in faces:
        fam = face["family"]
        entry = fonts.setdefault(fam, {"css": fam, "qtFamily": None, "legacyFamily": None, "files": [], "weights": []})
        for url in face["urls"]:
            u = urlparse(url)
            if u.scheme == "data":                  # an inlined font (base64 data: URI): write it out
                head, _, payload = url.partition(",")
                ext = ".woff2" if "woff2" in head else ".woff" if "woff" in head else ".otf" if "otf" in head else ".ttf"
                try:
                    data = base64.b64decode(payload) if ";base64" in head else unquote(payload).encode("latin-1")
                except (ValueError, UnicodeEncodeError):
                    warnings.append(f"inline font for {fam} could not be decoded")
                    continue
                fdir.mkdir(parents=True, exist_ok=True)
                src = fdir / f"{re.sub(r'[^A-Za-z0-9]+', '', fam) or 'font'}-{face['weight'].split()[0]}{ext}"
                src.write_bytes(data)
            elif u.scheme != "file":
                entry.setdefault("remote", []).append(url)
                continue
            else:
                src = Path(unquote(u.path))
            if not src.exists():
                warnings.append(f"font file missing: {src}")
                continue
            fdir.mkdir(parents=True, exist_ok=True)
            if src.name not in copied and src.parent.resolve() != fdir.resolve():
                shutil.copy2(src, fdir / src.name)
            copied.add(src.name)
            qt, legacy, weight = font_names(src)
            entry["qtFamily"] = entry["qtFamily"] or qt
            entry["legacyFamily"] = entry["legacyFamily"] or legacy
            if src.name not in entry["files"]:
                entry["files"].append(src.name)
            if weight and weight not in entry["weights"]:
                entry["weights"].append(weight)
            break                                   # first loadable source is the one used
    for f in loaded:
        if f["status"] == "error":
            warnings.append(f"font failed to load: {f['family']} {f['weight']}")
    for fam in used:
        if fam not in fonts and fam.lower() not in {"sans-serif", "serif", "monospace", "system-ui", "ui-sans-serif"}:
            fonts[fam] = {"css": fam, "qtFamily": None, "files": [], "weights": [],
                          "note": "no @font-face: a system font; find the file or substitute (typography.md)"}
    out = [dict(v, weights=sorted(v["weights"])) for k, v in fonts.items() if k in used or v["files"]]
    return out, warnings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("page", type=Path, help="HTML file (its CSS, fonts and images next to it)")
    ap.add_argument("--size", nargs=2, type=int, metavar=("W", "H"), required=True, help="viewport = design size in CSS px")
    ap.add_argument("--dpr", type=float, default=1.0, help="device pixel ratio of input.png (default 1)")
    ap.add_argument("--out-dir", type=Path, default=Path("analysis"))
    ap.add_argument("--lang", default=None, help="browser locale, e.g. tr-TR (default: Chromium's); the page's own lang "
                                                  "attribute still drives text-transform")
    ap.add_argument("--wait-ms", type=int, default=300, help="extra wait after fonts load (animations, charts)")
    ap.add_argument("--json", action="store_true", help="print the summary as JSON")
    args = ap.parse_args(argv)

    if not args.page.exists():
        print(f"[error] page not found: {args.page}", file=sys.stderr)
        return 2
    try:
        from playwright.sync_api import Error as PwError
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[error] Playwright missing: pip install playwright && python -m playwright install chromium", file=sys.stderr)
        return 2

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    w, h = args.size
    failed: list[str] = []
    console: list[str] = []
    try:
        with sync_playwright() as p:
            # file access: a page's linked stylesheets (style.css next to it) are only readable from
            # file:// pages with this flag; without it their rules (tokens, @font-face) are invisible
            browser = p.chromium.launch(args=["--font-render-hinting=none", "--allow-file-access-from-files"])
            ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=args.dpr,
                                      **({"locale": args.lang} if args.lang else {}))
            page = ctx.new_page()
            page.on("requestfailed", lambda r: failed.append(r.url))
            page.on("console", lambda m: console.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
            page.goto(args.page.resolve().as_uri(), wait_until="load")
            page.evaluate("document.fonts.ready.then(() => true)")
            page.wait_for_timeout(args.wait_ms)
            raw = page.evaluate(EXTRACT_JS.read_text())
            page.screenshot(path=str(out / "input.png"), full_page=False, caret="initial", animations="disabled")
            browser.close()
    except PwError as exc:
        msg = str(exc).splitlines()[0]
        hint = " (run: python -m playwright install chromium)" if "Executable doesn't exist" in str(exc) else ""
        print(f"[error] Chromium failed: {msg}{hint}", file=sys.stderr)
        return 2

    used = {t["font"]["family"] for t in raw["text"]}
    fonts, warnings = collect_fonts(raw["fontFaces"], raw["loaded"], used, out)
    warnings += [f"stylesheet not readable (its tokens and @font-face rules are missing): {h}" for h in raw.get("unreadableSheets", [])]
    warnings += [f"request failed: {u}" for u in failed[:10]]
    warnings += [f"console {c}" for c in console[:5]]

    icons = raw["icons"]
    for ic in icons:
        if ic["kind"] == "svg":
            (out / ic["file"]).parent.mkdir(parents=True, exist_ok=True)
            svg = ic.pop("svg")
            if "xmlns=" not in svg:
                svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
            (out / ic["file"]).write_text(svg)
    for n in raw["nodes"]:
        st = n["style"]
        if "shadow" in st:
            st["shadow"] = parse_shadows(st["shadow"]) or None
            if st["shadow"] is None:
                del st["shadow"]
    for t in raw["text"]:
        t["font"] = {k: v for k, v in t["font"].items() if v is not None and v is not False or k == "italic"}
    spec = convert_colors({"nodes": raw["nodes"], "text": raw["text"], "icons": icons, "colorsUsed": raw["colorsUsed"]})
    for ic in spec["icons"]:                       # write svg files with the resolved hex color
        if ic["kind"] == "svg" and isinstance(ic.get("color"), dict):
            f = out / ic["file"]
            f.write_text(f.read_text().replace("currentColor", ic["color"]["hex"]))
    lang = raw["lang"]
    spec = {
        "meta": {"id": args.page.stem, "title": raw.get("title"), "source": str(args.page), "generator": "html_to_spec.py",
                 "designSize": [w, h], "dpr": args.dpr, "captureSize": [round(w * args.dpr), round(h * args.dpr)], "lang": lang,
                 "units": "CSS px at 1x (design px). Multiply by dpr for input.png pixels.", "fonts": fonts},
        "tokens": tokens_from(raw["rawTokens"], spec["text"]),
        **spec,
    }
    (out / "design-spec.json").write_text(json.dumps(spec, indent=1, ensure_ascii=False))

    summary = {"out": str(out), "image": str(out / "input.png"), "spec": str(out / "design-spec.json"),
               "size": [w, h], "dpr": args.dpr, "nodes": len(spec["nodes"]), "text": len(spec["text"]),
               "icons": {k: sum(1 for i in icons if i["kind"] == k) for k in ("svg", "font-glyph", "raster")},
               "colorTokens": len(spec["tokens"]["color"]), "models": sum(1 for n in spec["nodes"] if n.get("model")),
               "fonts": [{"family": f["css"], "files": len(f["files"])} for f in fonts], "warnings": warnings}
    if args.json:
        print(json.dumps(summary, indent=1, ensure_ascii=False))
    else:
        print(f"{out / 'input.png'}: {w}x{h} @{args.dpr}x  nodes={summary['nodes']} text={summary['text']} "
              f"icons={sum(summary['icons'].values())} color tokens={summary['colorTokens']} models={summary['models']}")
        for f in fonts:
            print(f"  font {f['css']}: {len(f['files'])} file(s)" + (f" — {f['note']}" if f.get("note") else ""))
        for wmsg in warnings:
            print(f"[warn] {wmsg}")
    return 1 if warnings else 0


if __name__ == "__main__":
    sys.exit(main())
