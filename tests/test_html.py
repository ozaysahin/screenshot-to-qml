"""v1.0: the HTML-input path (html_to_spec.py) and the eval set's HTML cases.

Needs Playwright with Chromium; skipped without it.
"""
import json
import shutil

import html_to_spec
import pytest
import validate_spec

from conftest import EVALS

try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as _p:
        _ok = bool(_p.chromium.executable_path) and __import__("os").path.exists(_p.chromium.executable_path)
except Exception:   # noqa: BLE001
    _ok = False
requires_chromium = pytest.mark.skipif(not _ok, reason="needs playwright + chromium")

FONT = EVALS / "assets" / "fonts" / "Karla-Regular.ttf"

PAGE = """<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>Test</title><style>
@font-face { font-family: 'Karla'; font-weight: 400; src: url('fonts/Karla-Regular.ttf'); }
@layer theme { :root, :host { --color-brand: oklch(0.585 0.233 277.117); --radius-lg: 0.5rem; --radius-full: calc(infinity * 1px); } }
:root { --surface: #ffffff; --space-4: 16px; }
body { margin: 0; font-family: Karla, sans-serif; background: #f4f4f5; }
.card { margin: 16px; padding: 16px; background: var(--surface); border-radius: var(--radius-lg);
        box-shadow: 0 0 #0000, 0 1px 3px rgb(0 0 0 / .1); display: flex; flex-direction: column; gap: 8px; width: 260px; }
.btn { background: var(--color-brand); color: #fff; border: 0; border-radius: var(--radius-full); height: 36px; font: inherit; }
input { font: inherit; font-size: 15px; height: 36px; padding: 0 10px; border: 1px solid #ccc; border-radius: 8px; }
ul { list-style: none; padding: 0; margin: 0; } li.row { padding: 4px 0; }
svg.ic { width: 16px; height: 16px; color: #52525b; }
</style></head><body><div class="card">
<h1 style="font-size:18px;margin:0;text-transform:uppercase">Kişi listesi</h1>
<input type="search" value="Işık">
<select><option>Tümü</option><option selected>Ekim 2026</option></select>
<ul class="list"><li class="row">Ayşe</li><li class="row active">İlker</li><li class="row">Şule</li></ul>
<button class="btn"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14"/></svg>Kaydet</button>
</div></body></html>"""


@requires_chromium
def test_html_to_spec(tmp_path):
    (tmp_path / "fonts").mkdir()
    shutil.copy(FONT, tmp_path / "fonts" / FONT.name)
    page = tmp_path / "page.html"
    page.write_text(PAGE)
    out = tmp_path / "analysis"
    assert html_to_spec.main([str(page), "--size", "320", "400", "--dpr", "2", "--out-dir", str(out)]) == 0
    spec = json.loads((out / "design-spec.json").read_text())
    assert spec["meta"]["captureSize"] == [640, 800] and (out / "input.png").exists()
    tok = spec["tokens"]
    assert tok["color"]["brand"]["hex"] == "#615FFF"            # Tailwind v4 indigo-500, oklch -> sRGB
    assert tok["color"]["surface"]["hex"] == "#FFFFFF" and tok["space"]["4"] == 16
    assert tok["radius"]["lg"] == 8 and tok["radius"]["full"] == 9999
    strings = {t["string"] for t in spec["text"]}
    assert {"KİŞİ LİSTESİ", "Işık", "Ekim 2026", "Kaydet", "İlker"} <= strings
    card = next(n for n in spec["nodes"] if n["id"] == "div.card")
    assert len(card["style"]["shadow"]) == 1                    # transparent placeholder layer dropped
    btn = next(n for n in spec["nodes"] if n["role"] == "Button")
    assert btn["style"]["radius"] == 18                         # pill radius capped at half the height
    lst = next(n for n in spec["nodes"] if n.get("model"))
    assert lst["model"]["count"] == 3 and lst["model"]["itemId"] == "li.row"
    icon = spec["icons"][0]
    assert icon["kind"] == "svg" and "#52525B" in (out / icon["file"]).read_text()   # currentColor resolved
    assert spec["meta"]["fonts"][0]["files"] == ["Karla-Regular.ttf"] and (out / "fonts" / "Karla-Regular.ttf").exists()
    errors, _, _ = validate_spec.validate(spec)
    assert errors == []


@requires_chromium
def test_html_eval_cases_render_like_the_golden(tmp_path):
    """The skill's HTML path reproduces the eval's ground truth: same pixels, same text runs."""
    import numpy as np
    from PIL import Image
    case = EVALS / "cases" / "19-html-css-board"
    gold = json.loads((case / "golden-spec.json").read_text())
    w, h = gold["meta"]["designSize"]
    out = tmp_path / "a"
    assert html_to_spec.main([str(case / "source" / "index.html"), "--size", str(w), str(h), "--dpr", str(gold["meta"]["dpr"]),
                              "--lang", "tr-TR", "--out-dir", str(out)]) == 0
    a = np.asarray(Image.open(case / "input.png").convert("RGB"), dtype=int)
    b = np.asarray(Image.open(out / "input.png").convert("RGB"), dtype=int)
    assert a.shape == b.shape and np.abs(a - b).max() <= 2
    spec = json.loads((out / "design-spec.json").read_text())
    key = lambda t: (t["string"], tuple(t["bbox"]))                     # noqa: E731
    assert sorted(map(key, spec["text"])) == sorted(map(key, gold["text"]))


@requires_chromium
def test_linked_css_inline_fonts_and_textareas(tmp_path):
    """A page with its CSS in a linked file, a font inlined as data: URI, a wrapped textarea,
    text under an invisible ancestor and an invalid lang attribute."""
    import base64
    font = base64.b64encode(FONT.read_bytes()).decode()
    (tmp_path / "style.css").write_text(
        f"@font-face {{ font-family: 'Karla'; src: url(data:font/ttf;base64,{font}); }}\n"
        ":root { --color-ink: #1f2937; --space-3: 0.75rem; }\n"
        "body { margin: 0; font-family: Karla; color: var(--color-ink); }\n"
        "textarea { font: 15px/22px Karla; width: 200px; height: 90px; padding: 8px; border: 1px solid #ccc; resize: none; }\n")
    page = tmp_path / "index.html"
    page.write_text('<!doctype html><html lang="tr_TR"><head><meta charset="utf-8"><link rel="stylesheet" href="style.css"></head>'
                    '<body><p style="text-transform:uppercase">ilk satır</p>'
                    '<textarea>Yükleme rampasının sol üst köşesine kuzey cephesine bakacak şekilde</textarea>'
                    '<div style="opacity:0"><p>gizli metin</p></div></body></html>')
    out = tmp_path / "a"
    assert html_to_spec.main([str(page), "--size", "320", "240", "--out-dir", str(out)]) == 0
    spec = json.loads((out / "design-spec.json").read_text())
    assert spec["tokens"]["color"]["ink"]["hex"] == "#1F2937" and spec["tokens"]["space"]["3"] == 12
    assert spec["meta"]["fonts"][0]["files"] and (out / "fonts").exists()
    strings = [t["string"] for t in spec["text"]]
    assert "İLK SATIR" in strings and "gizli metin" not in strings
    area = [t for t in spec["text"] if t.get("field") == "textarea"]
    assert len(area) >= 3 and all(t["bbox"][2] <= 200 for t in area)
    assert " ".join(t["string"] for t in area).startswith("Yükleme rampasının")
