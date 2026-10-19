"""Candidate font library for font_match.py: catalog, on-demand download, rendering.

Families are listed in assets/catalog/fonts.json. Files come from github.com/google/fonts
(each family folder's METADATA.pb names its upright files) and are cached under
$S2Q_CACHE (default ~/.cache/screenshot-to-qml)/fonts/<slug>/. Nothing is bundled with the
skill; licenses are those of google/fonts (OFL / Apache / UFL) and the files are only used
to render comparison samples.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from functools import cache, lru_cache
from pathlib import Path

CATALOG = Path(__file__).resolve().parent.parent / "assets" / "catalog" / "fonts.json"
RAW = "https://raw.githubusercontent.com/google/fonts/main"
LICENSE_DIRS = ("ofl", "apache", "ufl")
LICENSE_FILES = ("OFL.txt", "LICENSE.txt", "UFL.txt")
WEIGHT_NAMES = {100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Regular", 500: "Medium",
                600: "SemiBold", 700: "Bold", 800: "ExtraBold", 900: "Black"}


def cache_dir() -> Path:
    base = Path(os.environ.get("S2Q_CACHE", Path.home() / ".cache" / "screenshot-to-qml"))
    return base / "fonts"


def slug(family: str) -> str:
    return re.sub(r"[^a-z0-9]", "", family.lower())


def catalog() -> list[dict]:
    return json.loads(CATALOG.read_text())["families"]


NET_ERRORS: list[str] = []      # connection failures (not 404s), so callers can tell "offline" from "no such family"


def _get(url: str, timeout: int = 30, tries: int = 4) -> bytes | None:
    """GET with retries on rate limits and server errors; None for 404 (no such file)."""
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            err = f"HTTP {e.code} for {url}"                  # 429 rate limit, 5xx: try again
        except Exception as e:      # URLError, timeout, proxy or sandbox refusing the connection
            err = f"{type(e).__name__}: {e}"
        if attempt < tries - 1:
            time.sleep(1.5 * 2 ** attempt)
    NET_ERRORS.append(err[:200])
    return None


def fetch(family: str, category: str = "sans", force: bool = False) -> dict | None:
    """Download the upright font files of `family`; returns its manifest (or None)."""
    folder = cache_dir() / slug(family)
    manifest = folder / "manifest.json"
    if manifest.exists() and not force:
        return json.loads(manifest.read_text())
    meta = base = None
    for lic in LICENSE_DIRS:
        base = f"{RAW}/{lic}/{slug(family)}"
        meta = _get(f"{base}/METADATA.pb")
        if meta:
            break
    if not meta:
        return None
    text = meta.decode("utf-8", "replace")
    files = []
    for block in re.findall(r"fonts\s*\{(.*?)\}", text, re.S):
        style = re.search(r'style:\s*"(\w+)"', block)
        fname = re.search(r'filename:\s*"([^"]+)"', block)
        weight = re.search(r"weight:\s*(\d+)", block)
        if not fname or (style and style.group(1) != "normal"):
            continue
        files.append({"file": fname.group(1), "weight": int(weight.group(1)) if weight else 400})
    if not files:
        return None
    folder.mkdir(parents=True, exist_ok=True)
    kept = []
    for f in files:
        dst = folder / f["file"]
        if not dst.exists():
            data = _get(f"{base}/{urllib.request.quote(f['file'])}")
            if not data:
                continue
            dst.write_bytes(data)
        kept.append(f)
    if not kept:
        return None
    lic = None
    for name in LICENSE_FILES:
        data = _get(f"{base}/{name}")
        if data:
            (folder / name).write_bytes(data)
            lic = name
            break
    info = {"family": family, "category": category, "files": kept, "license": lic, "source": base}
    manifest.write_text(json.dumps(info, indent=1))
    return info


def available() -> list[dict]:
    """Manifests of every family already in the cache (catalog order)."""
    out = []
    for entry in catalog():
        m = cache_dir() / slug(entry["family"]) / "manifest.json"
        if m.exists():
            out.append(json.loads(m.read_text()))
    return out


@cache
def _axes(path: str) -> dict:
    from fontTools.ttLib import TTFont
    font = TTFont(path, lazy=True)
    if "fvar" not in font:
        return {}
    return {a.axisTag: (a.minValue, a.defaultValue, a.maxValue) for a in font["fvar"].axes}


def weights(manifest: dict) -> list[int]:
    """Weights this family can render (100 steps)."""
    ws = set()
    folder = cache_dir() / slug(manifest["family"])
    for f in manifest["files"]:
        ax = _axes(str(folder / f["file"])).get("wght")
        if ax:
            ws.update(w for w in range(100, 1000, 100) if ax[0] <= w <= ax[2])
        else:
            ws.add(f["weight"])
    return sorted(ws)


@lru_cache(maxsize=4096)
def load(family: str, weight: int, px: int):
    """PIL font for `family` at `weight` and pixel size `px` (variable axes set like CSS)."""
    from PIL import ImageFont
    m = json.loads((cache_dir() / slug(family) / "manifest.json").read_text())
    folder = cache_dir() / slug(family)
    best, best_d = None, 1e9
    for f in m["files"]:
        path = str(folder / f["file"])
        ax = _axes(path).get("wght")
        d = 0 if ax and ax[0] <= weight <= ax[2] else abs(f["weight"] - weight)
        if d < best_d:
            best, best_d = path, d
    font = ImageFont.truetype(best, max(4, int(round(px))))
    axes = _axes(best)
    if axes:
        values = []
        for tag, (lo, default, hi) in axes.items():
            if tag == "wght":
                values.append(min(max(weight, lo), hi))
            elif tag == "opsz":
                values.append(min(max(px, lo), hi))      # CSS font-optical-sizing: auto
            else:
                values.append(default)
        try:
            font.set_variation_by_axes(values)
        except OSError:
            pass
    return font


def render(family: str, weight: int, px: float, text: str):
    """Coverage image (float32 0..1) of `text`, cropped to its ink."""
    import numpy as np
    from PIL import Image, ImageDraw
    font = load(family, weight, int(round(px)))
    x0, y0, x1, y1 = font.getbbox(text)
    w, h = max(1, x1 - x0 + 4), max(1, y1 - y0 + 4)
    img = Image.new("L", (w, h), 0)
    ImageDraw.Draw(img).text((2 - x0, 2 - y0), text, font=font, fill=255)
    a = np.asarray(img, dtype=np.float32) / 255.0
    ys, xs = np.nonzero(a > 0.25)
    if len(xs) == 0:
        return a
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def reserved_name(family: str) -> bool:
    """True when the family's OFL declares a Reserved Font Name (instancing would need a rename)."""
    folder = cache_dir() / slug(family)
    for name in LICENSE_FILES:
        f = folder / name
        if f.exists():
            head = f.read_text(errors="ignore")[:1200]
            return "Reserved Font Name" in head and "with Reserved Font Name" in head.replace("\n", " ")
    return False


def bundle(family: str, weights_used: list[int], out_dir: Path) -> list[str]:
    """Write static TTFs of `family` for `weights_used` into out_dir (+ the license).

    Variable files are instanced per weight (other axes pinned: opsz 14, the rest default) and
    named "<Family>" + weight class, so Qt's QFontDatabase selects them by family + weight.
    A family with a Reserved Font Name is copied unmodified instead (a modified font must not
    keep that name). Returns the written file names."""
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    m = json.loads((cache_dir() / slug(family) / "manifest.json").read_text())
    folder = cache_dir() / slug(family)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    rfn = reserved_name(family)
    for w in sorted(set(weights_used)):
        best, best_d = None, 1e9
        for f in m["files"]:
            path = folder / f["file"]
            ax = _axes(str(path)).get("wght")
            d = 0 if ax and ax[0] <= w <= ax[2] else abs(f["weight"] - w)
            if d < best_d:
                best, best_d = path, d
        axes = _axes(str(best))
        if not axes or rfn:
            if best.name not in written:
                (out_dir / best.name).write_bytes(best.read_bytes())
                written.append(best.name)
            continue
        vf = TTFont(str(best))
        loc = {tag: (min(max(w, lo), hi) if tag == "wght" else (min(max(14, lo), hi) if tag == "opsz" else default))
               for tag, (lo, default, hi) in axes.items()}
        font = instancer.instantiateVariableFont(vf, loc, updateFontNames=False)
        style = WEIGHT_NAMES.get(w, str(w))
        name = font["name"]
        for nid in (16, 17, 21, 22, 25):
            name.removeNames(nameID=nid)
        ps = family.replace(" ", "")
        for plat in ((3, 1, 0x409), (1, 0, 0)):
            name.setName(family, 1, *plat)
            name.setName(style, 2, *plat)
            name.setName(f"{family} {style}", 4, *plat)
            name.setName(f"{ps}-{style}", 6, *plat)
            name.setName(f"{ps}-{style};static", 3, *plat)
        font["OS/2"].usWeightClass = w
        bold = w >= 700
        font["OS/2"].fsSelection = (font["OS/2"].fsSelection & ~0b1100001) | (0b100000 if bold else 0b1000000)
        font["head"].macStyle = 0b1 if bold else 0
        if "STAT" in font:
            del font["STAT"]
        dst = out_dir / f"{ps}-{style}.ttf"
        font.save(str(dst))
        written.append(dst.name)
    lic = m.get("license")
    if not lic:                                   # caches made before licenses were fetched
        for cand in LICENSE_FILES:
            data = _get(f"{m.get('source') or RAW + '/ofl/' + slug(family)}/{cand}")
            if data:
                (folder / cand).write_bytes(data)
                lic = cand
                break
    if lic and (folder / lic).exists():
        dst = out_dir / f"{family.replace(' ', '')}-{lic}"
        dst.write_bytes((folder / lic).read_bytes())
        written.append(dst.name)
    return written
