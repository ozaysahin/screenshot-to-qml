#!/usr/bin/env python3
"""Find which icon set and icon a screenshot shows, and export it as SVG.

Usage:
  python icon_match.py fetch [--sets lucide,tabler]              # npm pack + index (once)
  python icon_match.py match IMG --spec design-spec.json [--dpr 2] [--top 3] [--out icons.json]
  python icon_match.py match IMG --box X Y W H [--dpr 2]           # one icon, design px
  python icon_match.py export lucide:gauge [--stroke 2] [--color "#1E293B"] --out assets/icons

`fetch` downloads the sets in assets/catalog/icons.json (Lucide, Tabler outline and filled,
Font Awesome solid / regular / brands, Heroicons outline and solid; about 11,700 icons) with
`npm pack` into the cache (~/.cache/screenshot-to-qml/icons, or $S2Q_CACHE) and renders a
32×32 index of every icon.

`match` cuts each icon box out of the screenshot and turns it into an ink-coverage map:
  1. coarse  normalized ink shape (tight box, square, 32×32, blurred) against the whole
             index by correlation, plus an aspect-ratio penalty → 40 candidates
  2. fine    every candidate re-rendered at the screenshot's scale (stroke sets at stroke
             widths 1.25–2.75), aligned on the ink box, compared at full resolution
  3. screen  the sets that win ≥ 25 % of the screen's icons get a small bonus, so the same
             shape in another set (Tabler "plus" vs Lucide "plus") loses the tie
Result per icon: candidates [{id, score, strokeWidth, setBonus}], best first.

`export` writes the SVG with the stroke width and color applied (for svgtoqml / VectorImage,
see references/icons-vectors.md). Exit codes: 0 ok, 2 error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

CATALOG = Path(__file__).resolve().parent.parent / "assets" / "catalog" / "icons.json"
CANON = 32
COARSE_KEEP = 40
STROKES = (1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75)
ASPECT_PENALTY = 0.3
SET_SHARE = 0.25           # sets winning this share of a screen's icons are "the screen's sets"
SET_BONUS = 0.08           # score bonus for candidates from the screen's sets (breaks cross-set ties)


def cache_dir() -> Path:
    return Path(os.environ.get("S2Q_CACHE", Path.home() / ".cache" / "screenshot-to-qml")) / "icons"


def catalog() -> list[dict]:
    return json.loads(CATALOG.read_text())["sets"]


def set_dir(s: dict) -> Path:
    return cache_dir() / "packages" / f"{s['package'].replace('/', '__')}-{s['version']}" / "package" / s["dir"]


# ---- fetching -------------------------------------------------------------------------------

def fetch_package(pkg: str, version: str) -> Path | None:
    dest = cache_dir() / "packages" / f"{pkg.replace('/', '__')}-{version}"
    if (dest / "package").is_dir():
        return dest
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        npm = shutil.which("npm") or "npm"          # npm.cmd on Windows
        res = subprocess.run([npm, "pack", f"{pkg}@{version}", "--silent"], cwd=tmp, capture_output=True, text=True)
        tgz = next(Path(tmp).glob("*.tgz"), None)
        if res.returncode != 0 or tgz is None:
            print(f"[warn] npm pack {pkg}@{version} failed: {res.stderr.strip()[:200]}", file=sys.stderr)
            return None
        with tarfile.open(tgz) as tf:
            tf.extractall(dest, filter="data")
    return dest


# ---- rendering ------------------------------------------------------------------------------

def _app():
    from PySide6.QtGui import QGuiApplication
    if QGuiApplication.instance() is None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        _app.keep = QGuiApplication([])
    return QGuiApplication.instance()


def svg_source(svg: str, stroke: float | None = None, color: str = "#000000") -> str:
    """The SVG with currentColor set and (stroke sets) the root stroke width replaced."""
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S).replace("currentColor", color)
    if stroke is not None:
        m = re.search(r"<svg\b[^>]*>", svg)
        if m:
            tag = m.group(0)
            if re.search(r'stroke-width="[^"]*"', tag):
                new_tag = re.sub(r'stroke-width="[^"]*"', f'stroke-width="{stroke:g}"', tag, count=1)
            else:
                new_tag = tag[:-1] + f' stroke-width="{stroke:g}">'
            svg = svg[:m.start()] + new_tag + svg[m.end():]
    return svg


def render_svg(svg: str, scale: float) -> np.ndarray:
    """Coverage (0..1) of the SVG drawn at `scale` px per viewBox unit."""
    from PySide6.QtCore import QByteArray, QRectF
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    _app()
    r = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    vb = r.viewBoxF()
    w, h = max(1, int(np.ceil(vb.width() * scale))), max(1, int(np.ceil(vb.height() * scale)))
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r.render(p, QRectF(0, 0, vb.width() * scale, vb.height() * scale))
    p.end()
    bpl = img.bytesPerLine()
    a = np.frombuffer(img.constBits(), np.uint8, bpl * h).reshape(h, bpl)[:, : w * 4].reshape(h, w, 4)[..., 3]
    return a.astype(np.float32) / 255.0


def ink(cov: np.ndarray, thr: float = 0.25) -> np.ndarray | None:
    ys, xs = np.nonzero(cov > thr)
    if len(xs) < 3:
        return None
    return cov[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def canonical(cov: np.ndarray) -> np.ndarray:
    """Ink box, padded to a square, resized to CANON-4 inside a CANON square, blurred."""
    h, w = cov.shape
    side = max(h, w)
    sq = np.zeros((side, side), np.float32)
    sq[(side - h) // 2:(side - h) // 2 + h, (side - w) // 2:(side - w) // 2 + w] = cov
    inner = CANON - 4
    small = cv2.resize(sq, (inner, inner), interpolation=cv2.INTER_AREA)
    out = np.zeros((CANON, CANON), np.float32)
    out[2:2 + inner, 2:2 + inner] = small
    return cv2.GaussianBlur(out, (0, 0), 0.8)


# ---- index ----------------------------------------------------------------------------------

def build_index(sets: list[dict]) -> dict:
    ids, imgs, aspects = [], [], []
    for s in sets:
        folder = set_dir(s)
        for f in sorted(folder.glob("*.svg")):
            svg = svg_source(f.read_text(errors="ignore"), s.get("strokeWidth") if s["kind"] == "stroke" else None)
            try:
                from PySide6.QtCore import QByteArray
                from PySide6.QtSvg import QSvgRenderer
                _app()
                vb = QSvgRenderer(QByteArray(svg.encode())).viewBoxF()
                cov = render_svg(svg, 64 / max(vb.width(), vb.height(), 1))
            except Exception:
                continue
            k = ink(cov)
            if k is None:
                continue
            ids.append(f"{s['id']}:{f.stem}")
            imgs.append(canonical(k))
            aspects.append(k.shape[1] / k.shape[0])
    arr = np.stack(imgs) if imgs else np.zeros((0, CANON, CANON), np.float32)
    out = cache_dir() / "index.npz"
    np.savez_compressed(out, ids=np.array(ids), imgs=(arr * 255).astype(np.uint8), aspects=np.array(aspects, np.float32))
    return {"icons": len(ids), "file": str(out)}


@lru_cache(maxsize=1)
def load_index() -> dict:
    path = cache_dir() / "index.npz"
    if not path.exists():
        raise SystemExit("[error] no icon index; run: python icon_match.py fetch")
    z = np.load(path)
    imgs = z["imgs"].astype(np.float32) / 255.0
    flat = imgs.reshape(len(imgs), -1)
    flat = flat - flat.mean(axis=1, keepdims=True)
    flat /= np.linalg.norm(flat, axis=1, keepdims=True) + 1e-6
    ids = [str(i) for i in z["ids"]]
    return {"ids": ids, "pos": {i: k for k, i in enumerate(ids)}, "flat": flat, "aspects": z["aspects"],
            "sets": {s["id"]: s for s in catalog()}}


def svg_path(icon_id: str) -> Path:
    set_id, name = icon_id.split(":", 1)
    s = next(s for s in catalog() if s["id"] == set_id)
    return set_dir(s) / f"{name}.svg"


def same_drawing(index: dict, pred: str, truth_set: str, truth_name: str) -> bool:
    """True when `pred` is the truth icon or draws the same shape (an alias)."""
    aliases = {a: s["id"] for s in catalog() for a in s.get("aliases", [])}
    truth = f"{aliases.get(truth_set, truth_set)}:{truth_name}"
    if pred == truth:
        return True
    a, b = index["pos"].get(pred), index["pos"].get(truth)
    return a is not None and b is not None and float(index["flat"][a] @ index["flat"][b]) > 0.985


# ---- matching -------------------------------------------------------------------------------

def load_rgb(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"[error] cannot read {path}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32)


def coverage(img: np.ndarray, bbox, dpr: float) -> np.ndarray | None:
    x, y, w, h = bbox
    pad = max(2, int(round(0.12 * max(w, h) * dpr)))
    x0, y0 = max(0, int(x * dpr) - pad), max(0, int(y * dpr) - pad)
    x1, y1 = min(img.shape[1], int((x + w) * dpr) + pad + 1), min(img.shape[0], int((y + h) * dpr) + pad + 1)
    crop = img[y0:y1, x0:x1]
    if crop.size == 0 or min(crop.shape[:2]) < 4:
        return None
    border = np.concatenate([crop[0], crop[-1], crop[:, 0], crop[:, -1]])
    bg = np.median(border, axis=0)
    d = np.linalg.norm(crop - bg, axis=2)
    if d.max() < 20:
        return None
    fg = np.median(crop[d >= np.percentile(d, 95)], axis=0)
    v = fg - bg
    return ink(np.clip(((crop - bg) @ v) / float(v @ v), 0, 1).astype(np.float32))


def _ncc(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a - a.mean(), b - b.mean()
    den = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return float((a * b).sum()) / den if den > 0 else 0.0


def fine_score(target: np.ndarray, icon_id: str, index: dict) -> tuple[float, float | None]:
    s = index["sets"][icon_id.split(":", 1)[0]]
    raw = svg_path(icon_id).read_text(errors="ignore")
    strokes = STROKES if s["kind"] == "stroke" else (None,)
    th, tw = target.shape
    sigma = max(0.6, max(th, tw) / 40)
    t = cv2.GaussianBlur(target, (0, 0), sigma)
    best = (-1.0, None)
    for sw in strokes:
        svg = svg_source(raw, sw)
        probe = ink(render_svg(svg, 4.0))
        if probe is None:
            continue
        # scale so the candidate's ink box fits the target's (by its limiting side)
        scale = 4.0 * (th / probe.shape[0] if th / tw > probe.shape[0] / probe.shape[1] else tw / probe.shape[1])
        cand = ink(render_svg(svg, scale))
        if cand is None:
            continue
        aspect_err = abs(np.log((cand.shape[1] / cand.shape[0]) / (tw / th)))
        c = cv2.resize(cand, (tw, th), interpolation=cv2.INTER_AREA)
        score = _ncc(t, cv2.GaussianBlur(c, (0, 0), sigma)) - ASPECT_PENALTY * aspect_err
        if score > best[0]:
            best = (score, sw)
    return best


def match_coverage(target: np.ndarray, index: dict, top: int = 3) -> dict:
    q = canonical(target).reshape(-1)
    q = q - q.mean()
    q /= np.linalg.norm(q) + 1e-6
    sims = index["flat"] @ q
    aspect = target.shape[1] / target.shape[0]
    sims = sims - ASPECT_PENALTY * np.abs(np.log(index["aspects"] / aspect))
    cand = np.argsort(-sims)[:COARSE_KEEP]
    rows = []
    for k in cand:
        icon_id = index["ids"][k]
        score, sw = fine_score(target, icon_id, index)
        rows.append({"id": icon_id, "score": round(score, 4), "coarse": round(float(sims[k]), 4),
                     **({"strokeWidth": sw} if sw is not None else {})})
    rows.sort(key=lambda r: -r["score"])
    return {"candidates": rows[:top], "size": [int(target.shape[1]), int(target.shape[0])]}


def match_box(img, dpr: float, bbox, index: dict | None = None, top: int = 3) -> dict | None:
    target = coverage(img, bbox, dpr)
    if target is None or min(target.shape) < 3:
        return None
    return match_coverage(target, index or load_index(), top)


def match_many(img, dpr: float, boxes: list, index: dict | None = None, top: int = 3) -> list[dict | None]:
    """Match several icons of one screen. A screen draws its icons from one or two sets, so
    after a first pass the sets that win at least SET_SHARE of the icons get SET_BONUS: the
    same shape found in another set (Tabler plus vs Lucide plus) then loses the tie."""
    index = index or load_index()
    first = [match_box(img, dpr, b, index, top=12) for b in boxes]
    votes: dict[str, int] = {}
    for r in first:
        if r and r["candidates"]:
            set_id = r["candidates"][0]["id"].split(":", 1)[0]
            votes[set_id] = votes.get(set_id, 0) + 1
    n = sum(votes.values())
    screen_sets = {k for k, v in votes.items() if n and v >= SET_SHARE * n}
    out = []
    for r in first:
        if r is None:
            out.append(None)
            continue
        for c in r["candidates"]:
            c["setBonus"] = SET_BONUS if c["id"].split(":", 1)[0] in screen_sets else 0.0
        r["candidates"].sort(key=lambda c: -(c["score"] + c["setBonus"]))
        r["candidates"] = r["candidates"][:top]
        r["screenSets"] = sorted(screen_sets)
        out.append(r)
    return out


def export(icon_id: str, out_dir: Path, stroke: float | None, color: str) -> Path:
    s = next(s for s in catalog() if s["id"] == icon_id.split(":", 1)[0])
    svg = svg_source(svg_path(icon_id).read_text(), stroke if s["kind"] == "stroke" else None, color).strip() + "\n"
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{icon_id.split(':', 1)[1]}.svg"
    dst.write_text(svg)
    return dst


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--sets", default="", help="comma-separated set ids (default: all)")
    m = sub.add_parser("match")
    m.add_argument("image", type=Path)
    m.add_argument("--spec", type=Path)
    m.add_argument("--box", type=float, nargs=4, metavar=("X", "Y", "W", "H"))
    m.add_argument("--dpr", type=float, default=None)
    m.add_argument("--top", type=int, default=3)
    m.add_argument("--out", type=Path)
    e = sub.add_parser("export")
    e.add_argument("icon", help="set:name, e.g. lucide:gauge")
    e.add_argument("--stroke", type=float, default=None)
    e.add_argument("--color", default="#000000")
    e.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    if args.cmd == "fetch":
        wanted = {s.strip() for s in args.sets.split(",") if s.strip()}
        sets = [s for s in catalog() if not wanted or s["id"] in wanted]
        ok = []
        for s in sets:
            if fetch_package(s["package"], s["version"]) and set_dir(s).is_dir():
                ok.append(s)
            else:
                print(f"[warn] set {s['id']} unavailable", file=sys.stderr)
        info = build_index(ok)
        print(f"indexed {info['icons']} icons from {len(ok)} sets -> {info['file']}")
        return 0 if ok else 2

    if args.cmd == "export":
        print(export(args.icon, args.out, args.stroke, args.color))
        return 0

    img = load_rgb(args.image)
    spec = json.loads(args.spec.read_text()) if args.spec else {}
    dpr = args.dpr or float(spec.get("meta", {}).get("dpr", 1))
    boxes = [{"id": "box", "bbox": list(args.box)}] if args.box else [
        {"id": ic.get("id", f"i{k}"), "bbox": ic["bbox"]} for k, ic in enumerate(spec.get("icons", []))]
    if not boxes:
        print("[error] no icons: pass --box or a spec with icons[]", file=sys.stderr)
        return 2
    index = load_index()
    results = []
    for b, r in zip(boxes, match_many(img, dpr, [b["bbox"] for b in boxes], index, args.top), strict=True):
        results.append({"id": b["id"], "bbox": b["bbox"], **(r or {"candidates": []})})
        best = r["candidates"][0] if r and r["candidates"] else None
        alts = ", ".join(c["id"] for c in (r["candidates"][1:] if r else []))
        print(f"{b['id']:10s} {best['id'] if best else '—':32s} {best['score'] if best else '':>7} alt: {alts}")
    if args.out:
        args.out.write_text(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
