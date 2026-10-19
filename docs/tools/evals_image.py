#!/usr/bin/env python3
"""Render docs/img/evals.png: a contact sheet of every eval case's input.

Usage: python docs/tools/evals_image.py [--out docs/img/evals.png] [--cols 5]
Needs Playwright with Chromium. Exit codes: 0 ok, 2 error.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "evals" / "cases"
FONTS = ROOT / "evals" / "assets" / "fonts"


def thumb(path: Path, box: tuple[int, int]) -> str:
    from PIL import Image
    im = Image.open(path).convert("RGB")
    im.thumbnail((box[0] * 2, box[1] * 2), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "img" / "evals.png")
    ap.add_argument("--cols", type=int, default=5)
    args = ap.parse_args(argv)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[error] pip install playwright && python -m playwright install chromium", file=sys.stderr)
        return 2
    cases = sorted(p for p in CASES.iterdir() if (p / "golden-spec.json").exists())
    tw, th = 360, 220
    cards = []
    for c in cases:
        m = json.loads((c / "golden-spec.json").read_text())["meta"]
        fonts = ", ".join(f["css"] for f in m["fonts"])
        dpr = f"{m['dpr']:g}"
        kind = "HTML input" if m.get("category") == "html" else m.get("category", "")
        cards.append(f"""<div class="card"><div class="shot"><img src="data:image/png;base64,{thumb(c / 'input.png', (tw, th))}"></div>
          <b>{c.name}</b><span>{m['designSize'][0]}×{m['designSize'][1]} @{dpr}x · {kind} · {fonts}</span></div>""")
    width = 40 + args.cols * (tw + 24)
    html = f"""<!doctype html><meta charset="utf-8"><style>
@font-face {{ font-family: 'Inter'; font-weight: 400; src: url('{(FONTS / 'Inter-Regular.ttf').as_uri()}'); }}
@font-face {{ font-family: 'Inter'; font-weight: 600; src: url('{(FONTS / 'Inter-SemiBold.ttf').as_uri()}'); }}
body {{ margin: 0; padding: 28px 28px 20px; background: #fff; font-family: Inter; color: #111827; width: {width - 56}px; }}
h1 {{ font-size: 30px; font-weight: 600; margin: 0 0 22px; letter-spacing: -0.4px; }}
.grid {{ display: grid; grid-template-columns: repeat({args.cols}, {tw}px); gap: 22px 24px; }}
.shot {{ width: {tw}px; height: {th}px; border-radius: 10px; background: #EEF0F3; display: grid; place-items: center; overflow: hidden; }}
.shot img {{ max-width: {tw - 16}px; max-height: {th - 16}px; border-radius: 4px; }}
b {{ display: block; font-size: 16px; font-weight: 600; margin-top: 10px; }}
span {{ display: block; font-size: 12.5px; color: #6B7280; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
</style><h1>Eval set — {len(cards)} original screens with DOM-extracted ground truth</h1><div class="grid">{''.join(cards)}</div>"""
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": width, "height": 400}, device_scale_factor=1)
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:   # file:// so the fonts load
            f.write(html)
        page.goto(Path(f.name).as_uri())
        page.evaluate("document.fonts.ready.then(() => true)")
        page.wait_for_timeout(200)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(args.out), full_page=True)
        b.close()
    Path(f.name).unlink()
    print(f"{args.out}: {len(cards)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
