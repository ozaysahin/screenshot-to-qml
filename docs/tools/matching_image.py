#!/usr/bin/env python3
"""Build docs/img/matching.png: what the v0.6 matchers read off the eval screenshots.

Usage (needs the font and icon caches: font_match.py fetch, icon_match.py fetch):
  python docs/tools/matching_image.py

Rows: fonts (text crops with the family/weight found), icons (crop → matched icon), shadows
(crop, the same crop with the fitted shadow subtracted, the CSS), gradients (crop, the fitted
gradient re-rendered, the CSS). Every value is computed live; the truth is only used to mark
a result right (green) or wrong (red).
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "screenshot-to-qml" / "scripts"))
CASES = ROOT / "evals" / "cases"
OUT = ROOT / "docs" / "img" / "matching.png"

import font_match  # noqa: E402
import fontlib  # noqa: E402
import gradient_fit  # noqa: E402
import icon_match  # noqa: E402
import shadow_fit  # noqa: E402

W = 1600
PAD = 32
BG, INK, MUTED, OK, BAD, LINE = (255, 255, 255), (17, 24, 39), (100, 116, 139), (22, 128, 61), (190, 18, 60), (226, 232, 240)
FONTS = [("03-dashboard-dark", "Genel Bakış"), ("03-dashboard-dark", "Son güncelleme 14:32"),
         ("01-hmi-dolum", None), ("05-settings-form", "Cihaz bilgileri"), ("08-glass-home", "21:47"),
         ("06-mobile-aliskanlik", None)]
ICONS = [("01-hmi-dolum", 0), ("01-hmi-dolum", 3), ("03-dashboard-dark", 2), ("03-dashboard-dark", 6),
         ("06-mobile-aliskanlik", 1), ("06-mobile-aliskanlik", 4), ("08-glass-home", 1), ("08-glass-home", 5)]
SHADOWS = [("03-dashboard-dark", "deployButton"), ("06-mobile-aliskanlik", "progressCard"), ("04-dashboard-light", "solarCard")]
GRADIENTS = [("02-kiosk-kafe", "promo"), ("06-mobile-aliskanlik", "progressCard"), ("08-glass-home", "playButton")]


def ui_font(size, weight=500):
    try:
        return fontlib.load("Inter", weight, size)
    except Exception:
        return ImageFont.load_default()


def load(case):
    spec = json.loads((CASES / case / "golden-spec.json").read_text())
    return spec, font_match.load_rgb(CASES / case / "input.png"), float(spec["meta"]["dpr"])


def crop(img, dpr, box, pad=0):
    x, y, w, h = box
    X0, Y0 = max(0, int((x - pad) * dpr)), max(0, int((y - pad) * dpr))
    X1, Y1 = min(img.shape[1], int(math.ceil((x + w + pad) * dpr))), min(img.shape[0], int(math.ceil((y + h + pad) * dpr)))
    return Image.fromarray(img[Y0:Y1, X0:X1].clip(0, 255).astype(np.uint8))


def fit_h(im, h):
    return im.resize((max(1, round(im.width * h / im.height)), h), Image.LANCZOS)


def fit_box(im, w, h):
    s = min(w / im.width, h / im.height)
    return im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)


def section(draw, y, title, sub):
    draw.text((PAD, y), title, font=ui_font(26, 700), fill=INK)
    draw.text((PAD + draw.textlength(title, font=ui_font(26, 700)) + 14, y + 8), sub, font=ui_font(16, 400), fill=MUTED)
    return y + 48


def font_row(canvas, draw, y):
    fams = fontlib.available()
    tiles = []
    for case, want in FONTS:
        spec, img, dpr = load(case)
        runs = font_match.pick_runs(spec, 40)
        res = font_match.match(img, dpr, [{k: v for k, v in r.items() if k != "font"} for r in runs], fams)
        truth = {(r["string"], tuple(r["bbox"])): r["font"] for r in runs}
        pick = None
        for r in res["runs"]:
            t = truth.get((r["string"], tuple(r["bbox"])))
            if t and (want is None and t["family"].endswith("Mono") or want and r["string"].startswith(want)):
                pick = (r, t)
                break
        if pick is None:
            pick = next(((r, truth[(r["string"], tuple(r["bbox"]))]) for r in res["runs"]), None)
        if pick:
            tiles.append((crop(img, dpr, pick[0]["bbox"], 4), pick[0], pick[1]))
    x, row_h = PAD, 150
    for im, r, t in tiles:
        tw = 240
        im = fit_box(im, tw, 70)
        canvas.paste(im, (x, y + (70 - im.height) // 2))
        ok = r["family"] == t["family"]
        draw.text((x, y + 82), f"{r['family']} {r['weight']}", font=ui_font(16, 600), fill=OK if ok else BAD)
        draw.text((x, y + 104), f"truth {t['family']} {t['weight']}", font=ui_font(13, 400), fill=MUTED)
        x += tw + 16
    return y + row_h


def icon_row(canvas, draw, y):
    index = icon_match.load_index()
    x = PAD
    for case, k in ICONS:
        spec, img, dpr = load(case)
        icons = spec["icons"]
        if k >= len(icons):
            continue
        ic = icons[k]
        res = icon_match.match_many(img, dpr, [i["bbox"] for i in icons], index, top=3)[k]
        best = res["candidates"][0]
        tset, tname = ic["match"].split(":", 1)
        ok = icon_match.same_drawing(index, best["id"], tset, tname)
        shot = fit_box(crop(img, dpr, ic["bbox"], 3), 64, 64)
        svg = icon_match.svg_source(icon_match.svg_path(best["id"]).read_text(), best.get("strokeWidth"))
        probe = icon_match.render_svg(svg, 1.0)
        cov = icon_match.render_svg(svg, 56 / max(probe.shape))
        rend = Image.fromarray((255 - cov * 230).clip(0, 255).astype(np.uint8)).convert("RGB")
        rend = fit_box(rend, 56, 56)
        canvas.paste(shot, (x, y + (64 - shot.height) // 2))
        draw.text((x + 70, y + 18), "→", font=ui_font(22, 500), fill=MUTED)
        canvas.paste(rend, (x + 100, y + (64 - rend.height) // 2))
        draw.text((x, y + 74), best["id"], font=ui_font(13, 600), fill=OK if ok else BAD)
        sw = best.get("strokeWidth")
        draw.text((x, y + 92), f"stroke {sw:g}" if sw else "filled", font=ui_font(12, 400), fill=MUTED)
        x += 188
    return y + 124


def stretch(a, lo, span):
    return ((a - lo) / span * 235 + 10).clip(0, 255).astype(np.uint8)


def shadow_row(canvas, draw, y):
    x = PAD
    for case, nid in SHADOWS:
        spec, img, dpr = load(case)
        blind = json.loads(json.dumps(spec))
        for n in blind["nodes"]:
            (n.get("style") or {}).pop("shadow", None)
        jobs = {j["id"]: j for j in shadow_fit.jobs_from_spec(blind)}
        f = shadow_fit.fit_scene(img, dpr, list(jobs.values()))[nid]
        node = next(n for n in spec["nodes"] if n["id"] == nid)
        bx, by, bw, bh = node["bbox"]
        pad = 48
        region = [bx - pad, by - pad, bw + 2 * pad, bh + 2 * pad]
        shot = np.asarray(crop(img, dpr, region)).astype(np.float32)
        H, Wd = shot.shape[:2]
        X0, Y0 = max(0, int((bx - pad) * dpr)), max(0, int((by - pad) * dpr))
        m = np.zeros((H, Wd), np.float32)
        x0 = (bx + f["x"] - f["spread"]) * dpr - X0
        y0 = (by + f["y"] - f["spread"]) * dpr - Y0
        cv2.rectangle(m, (int(x0), int(y0)), (int(x0 + (bw + 2 * f["spread"]) * dpr), int(y0 + (bh + 2 * f["spread"]) * dpr)), 1.0, -1)
        if f["blur"] > 0.2:
            m = cv2.GaussianBlur(m, (0, 0), f["blur"] / 2 * dpr)
        inside = np.zeros((H, Wd), bool)
        inside[int(by * dpr - Y0):int((by + bh) * dpr - Y0), int(bx * dpr - X0):int((bx + bw) * dpr - X0)] = True
        clean = shot - m[..., None] * np.asarray(f["u"], np.float32)[None, None, :]
        clean[inside] = shot[inside]
        # the same contrast stretch on both, from the pixels around the box, so the shadow shows
        # stretch the range between the background and the shadow's deepest point
        edge = np.concatenate([shot[:4].reshape(-1, 3), shot[-4:].reshape(-1, 3)])
        bg = float(np.median(edge.mean(axis=1)))
        u = np.asarray(f["u"], float)
        d = max(float(np.abs(u).max()), 6.0)
        lo = bg - 1.3 * d if u.mean() < 0 else bg - 0.3 * d
        span = 1.6 * d

        a = fit_box(Image.fromarray(stretch(shot, lo, span)), 230, 150)
        b = fit_box(Image.fromarray(stretch(clean, lo, span)), 230, 150)
        canvas.paste(a, (x, y))
        canvas.paste(b, (x + a.width + 8, y))
        t = [s for s in node["style"]["shadow"] if not s.get("inset")]
        dom = max(t, key=lambda s: s["color"]["alpha"] * (s["blur"] + 1))
        draw.text((x, y + 158), f"{f['x']:.0f} {f['y']:.1f} {f['blur']:.1f} {f['spread']:.1f}  α {f['alpha']:.2f}",
                  font=ui_font(14, 600), fill=OK if abs(f["blur"] - dom["blur"]) <= 5 and abs(f["y"] - dom["y"]) <= 3 else BAD)
        draw.text((x, y + 178), f"css {dom['x']:.0f} {dom['y']:.0f} {dom['blur']:.0f} {dom['spread']:.0f}  α {dom['color']['alpha']:.2f}"
                  + (f"  (+{len(t) - 1} layer)" if len(t) > 1 else ""), font=ui_font(13, 400), fill=MUTED)
        x += a.width + b.width + 40
    return y + 210


def gradient_row(canvas, draw, y):
    x = PAD
    for case, nid in GRADIENTS:
        spec, img, dpr = load(case)
        job = gradient_fit.jobs_from_spec(spec, {nid})[0]
        f = gradient_fit.fit_region(img, dpr, job["bbox"], job["mask"], job["radius"], border=job["border"])
        bx, by, bw, bh = job["bbox"]
        shot = crop(img, dpr, job["bbox"])
        w, h = shot.size
        ys, xs = np.mgrid[0:h, 0:w]
        px, py = (xs + 0.5) / dpr - bw / 2, (ys + 0.5) / dpr - bh / 2
        t = gradient_fit._t(px.ravel(), py.ravel(), bw, bh, f["angle"])
        knots = [s["t"] for s in f["stops"]]
        cols = np.array([s["rgb"] for s in f["stops"]], float)
        rend = (gradient_fit._hat(t, knots) @ cols).reshape(h, w, 3)
        r = min(job["radius"] or 0, bw / 2, bh / 2) * dpr
        mask = np.zeros((h, w), np.uint8)
        rr = int(round(r))
        cv2.rectangle(mask, (rr, 0), (w - rr - 1, h - 1), 255, -1)
        cv2.rectangle(mask, (0, rr), (w - 1, h - rr - 1), 255, -1)
        for cx, cy in ((rr, rr), (w - rr - 1, rr), (rr, h - rr - 1), (w - rr - 1, h - rr - 1)):
            cv2.circle(mask, (cx, cy), rr, 255, -1)
        rend = np.where(mask[..., None] > 0, rend, 255.0)
        a = fit_box(shot, 230, 120)
        b = fit_box(Image.fromarray(rend.clip(0, 255).astype(np.uint8)), 230, 120)
        canvas.paste(a, (x, y))
        canvas.paste(b, (x + a.width + 8, y))
        truth = next(n for n in spec["nodes"] if n["id"] == nid)["style"]["fillImage"]
        cols_t = [tuple(int(v) for v in c.split(",")[:3]) for c in re.findall(r"rgba?\(([^)]*)\)", truth)]
        ang_t = float(re.search(r"\((\d+(?:\.\d+)?)deg", truth).group(1))
        fit_txt = f"{f['angle']:g}°  " + " → ".join(st["hex"] for st in f["stops"])
        css_txt = f"css {ang_t:g}°  " + " → ".join("#{:02X}{:02X}{:02X}".format(*c) for c in cols_t)
        draw.text((x, y + 128), fit_txt, font=ui_font(15, 600), fill=OK)
        draw.text((x, y + 150), css_txt, font=ui_font(13, 400), fill=MUTED)
        x += a.width + b.width + 40
    return y + 176


def main() -> int:
    canvas = Image.new("RGB", (W, 1200), BG)
    draw = ImageDraw.Draw(canvas)
    y = PAD
    y = section(draw, y, "Fonts", "font_match.py — family and weight per text run (green: right; grey: truth)")
    y = font_row(canvas, draw, y)
    draw.line((PAD, y - 10, W - PAD, y - 10), fill=LINE, width=2)
    y = section(draw, y + 6, "Icons", "icon_match.py — screenshot crop → best of 11,869 icons, with its stroke width")
    y = icon_row(canvas, draw, y)
    draw.line((PAD, y - 10, W - PAD, y - 10), fill=LINE, width=2)
    y = section(draw, y + 6, "Shadows", "shadow_fit.py — screenshot | fitted shadow subtracted (contrast raised on both); x y blur spread α")
    y = shadow_row(canvas, draw, y)
    draw.line((PAD, y - 10, W - PAD, y - 10), fill=LINE, width=2)
    y = section(draw, y + 6, "Gradients", "gradient_fit.py — screenshot | re-rendered from the fit (text and icons masked)")
    y = gradient_row(canvas, draw, y)
    canvas = canvas.crop((0, 0, W, y + PAD - 20))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT, optimize=True)
    print(OUT, canvas.size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
