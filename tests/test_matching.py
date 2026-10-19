"""v0.6 matchers on synthetic images (no network; font/icon tests skip without their caches)."""
import json
import math

import cv2
import numpy as np
import pytest

import gradient_fit
import shadow_fit

# ------------------------------------------------------------------ helpers (independent of the fitters)

def css_gradient(w, h, angle, stops, ss=1):
    """Pixel colors of CSS linear-gradient(angle, stops) over a w×h box (stops: [(t, rgb)])."""
    ys, xs = np.mgrid[0:h * ss, 0:w * ss]
    x = (xs + 0.5) / ss - w / 2
    y = (ys + 0.5) / ss - h / 2
    a = math.radians(angle)
    length = abs(w * math.sin(a)) + abs(h * math.cos(a))
    t = np.clip((x * math.sin(a) - y * math.cos(a)) / length + 0.5, 0, 1)
    out = np.zeros((h * ss, w * ss, 3), np.float32)
    for (t0, c0), (t1, c1) in zip(stops, stops[1:], strict=False):
        sel = (t >= t0) & (t <= t1)
        u = ((t[sel] - t0) / (t1 - t0))[:, None]
        out[sel] = np.array(c0) * (1 - u) + np.array(c1) * u
    return out


def shadow_scene(dpr=1, y=8, blur=16, alpha=0.2, spread=0, with_shadow=True):
    W, H = 320, 260
    bg = np.array([240.0, 242.0, 245.0])
    img = np.ones((H * dpr, W * dpr, 3), np.float32) * bg
    box = (90, 70, 140, 100)
    if with_shadow:
        m = np.zeros((H * dpr, W * dpr), np.float32)
        x0, y0 = (box[0] - spread) * dpr, (box[1] + y - spread) * dpr
        x1, y1 = (box[0] + box[2] + spread) * dpr, (box[1] + y + box[3] + spread) * dpr
        m[int(y0):int(y1), int(x0):int(x1)] = 1.0
        m = cv2.GaussianBlur(m, (0, 0), blur / 2 * dpr)
        img = img * (1 - alpha * m[..., None])
    bx, by, bw, bh = (v * dpr for v in box)
    img[by:by + bh, bx:bx + bw] = 255.0
    return img, box


# ------------------------------------------------------------------ gradients

@pytest.mark.parametrize("angle", [0, 90, 135, 200, 315])
def test_gradient_angle_and_stops(angle):
    c0, c1 = (167, 139, 250), (34, 211, 238)
    img = np.full((140, 260, 3), 250.0, np.float32)
    img[20:120, 30:230] = css_gradient(200, 100, angle, [(0, c0), (1, c1)])
    fit = gradient_fit.fit_region(img, 1, [30, 20, 200, 100])
    want, first, last = angle, c0, c1
    if abs((fit["angle"] - angle + 180) % 360 - 180) > 90:        # reported the other way round
        want, first, last = (angle + 180) % 360, c1, c0
    assert 0 < fit["angle"] <= 180
    assert abs((fit["angle"] - want + 180) % 360 - 180) < 0.5
    assert gradient_fit.delta_e(fit["stops"][0]["rgb"], first) < 1.5
    assert gradient_fit.delta_e(fit["stops"][-1]["rgb"], last) < 1.5
    assert gradient_fit.accept(fit)


def test_gradient_three_stops():
    stops = [(0, (255, 138, 76)), (0.4, (250, 240, 120)), (1, (40, 90, 200))]
    img = css_gradient(240, 120, 60, stops)
    fit = gradient_fit.fit_region(img, 1, [0, 0, 240, 120])
    assert len(fit["stops"]) == 3
    assert abs(fit["stops"][1]["t"] - 0.4) <= 0.05
    assert abs(fit["angle"] - 60) < 0.5


def test_gradient_ignores_undeclared_knob():
    img = css_gradient(104, 60, 90, [(0, (167, 139, 250)), (1, (34, 211, 238))], ss=1)
    cv2.circle(img, (78, 30), 24, (255, 255, 255), -1)          # a switch knob nobody declared
    fit = gradient_fit.fit_region(img, 1, [0, 0, 104, 60], radius=30)
    assert len(fit["stops"]) == 2
    assert fit["outliers"] > 0.2
    assert gradient_fit.delta_e(fit["stops"][0]["rgb"], (167, 139, 250)) < 2
    assert gradient_fit.delta_e(fit["stops"][-1]["rgb"], (34, 211, 238)) < 2


def test_solid_fill_is_not_a_gradient():
    img = np.full((80, 160, 3), (51, 102, 204), np.float32)
    img += np.random.default_rng(0).normal(0, 0.6, img.shape).astype(np.float32)
    fit = gradient_fit.fit_region(img, 1, [0, 0, 160, 80])
    assert not gradient_fit.accept(fit)


def test_qt_hints_for_axis_aligned_gradients():
    img = css_gradient(100, 60, 180, [(0, (0, 0, 0)), (1, (255, 255, 255))])
    fit = gradient_fit.fit_region(img, 1, [0, 0, 100, 60])
    assert fit["qt"]["orientation"] == "Gradient.Vertical" and not fit["qt"]["reverseStops"]
    assert fit["qt"]["y1"] == pytest.approx(0, abs=0.5) and fit["qt"]["y2"] == pytest.approx(60, abs=0.5)


# ------------------------------------------------------------------ shadows

@pytest.mark.parametrize("dpr", [1, 2])
def test_shadow_parameters_are_recovered(dpr):
    img, box = shadow_scene(dpr=dpr, y=8, blur=16, alpha=0.2)
    fit = shadow_fit.fit_node(img, dpr, box, 0)
    assert fit["hasShadow"]
    assert abs(fit["y"] - 8) <= 1.5 and abs(fit["x"]) <= 1.0
    assert abs(fit["blur"] - 16) <= 2.5
    assert abs(fit["alpha"] - 0.2) <= 0.05
    assert fit["residual"] < 0.3 * fit["rawResidual"]


def test_no_shadow_is_reported():
    img, box = shadow_scene(with_shadow=False)
    fit = shadow_fit.fit_node(img, 1, box, 0)
    assert not fit["hasShadow"]


def test_scene_mode_on_a_spec(tmp_path):
    img, box = shadow_scene(y=6, blur=12, alpha=0.25)
    path = tmp_path / "s.png"
    cv2.imwrite(str(path), cv2.cvtColor(img.clip(0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
    spec = {"meta": {"dpr": 1}, "nodes": [{"id": "card", "parent": None, "bbox": list(box),
                                           "style": {"fill": {"hex": "#FFFFFF", "alpha": 1}, "radius": 0}}]}
    (tmp_path / "spec.json").write_text(json.dumps(spec))
    assert shadow_fit.main([str(path), "--spec", str(tmp_path / "spec.json"), "--out", str(tmp_path / "o.json")]) == 0
    out = json.loads((tmp_path / "o.json").read_text())
    assert out[0]["id"] == "card" and out[0]["hasShadow"]
    assert abs(out[0]["y"] - 6) <= 1.5 and abs(out[0]["blur"] - 12) <= 2.5
    spec["nodes"][0]["style"]["radius"] = [0, 0, 6, 6]          # per-corner radii (CSS border-*-radius)
    (tmp_path / "spec.json").write_text(json.dumps(spec))
    assert shadow_fit.main([str(path), "--spec", str(tmp_path / "spec.json"), "--out", str(tmp_path / "o.json")]) == 0


# ------------------------------------------------------------------ match.py (effects only: no caches needed)

def test_match_writes_measured_effects(tmp_path):
    import match
    img, box = shadow_scene(y=10, blur=20, alpha=0.2)
    img[20:60, 20:300] = css_gradient(280, 40, 90, [(0, (255, 138, 76)), (1, (255, 90, 54))])
    path = tmp_path / "s.png"
    cv2.imwrite(str(path), cv2.cvtColor(img.clip(0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
    spec = {"meta": {"dpr": 1}, "tokens": {"color": {}}, "text": [], "icons": [], "nodes": [
        {"id": "card", "parent": None, "bbox": list(box), "style": {"fill": {"hex": "#FFFFFF", "alpha": 1}}},
        {"id": "banner", "parent": None, "bbox": [20, 20, 280, 40], "style": {"fill": {"hex": "#FF7A4C", "alpha": 1}}}]}
    sp = tmp_path / "design-spec.json"
    sp.write_text(json.dumps(spec))
    assert match.main([str(path), str(sp), "--only", "shadows,gradients"]) == 0
    got = json.loads((tmp_path / "design-spec.matched.json").read_text())
    nodes = {n["id"]: n for n in got["nodes"]}
    sh = nodes["card"]["style"]["shadow"][0]
    assert abs(sh["y"] - 10) <= 1.5 and abs(sh["blur"] - 20) <= 3
    assert nodes["banner"]["style"]["fillImage"].startswith("linear-gradient(90deg")
    assert "fillImage" not in nodes["card"]["style"]
    assert (tmp_path / "design-spec.match-report.json").exists()


# ------------------------------------------------------------------ fonts / icons (need the caches)

def _fonts_cached(*names):
    import fontlib
    have = {m["family"] for m in fontlib.available()}
    return all(n in have for n in names)


@pytest.mark.skipif(not _fonts_cached("Inter", "Manrope", "JetBrains Mono"), reason="font cache not fetched")
def test_font_match_picks_the_rendering_family():
    from PIL import Image, ImageDraw

    import font_match
    import fontlib
    img = Image.new("RGB", (520, 90), (250, 250, 250))
    ImageDraw.Draw(img).text((12, 20), "Weekly energy report", font=fontlib.load("Manrope", 700, 32), fill=(20, 24, 40))
    arr = np.asarray(img, np.float32)
    fams = [m for m in fontlib.available() if m["family"] in ("Inter", "Manrope", "JetBrains Mono")]
    res = font_match.match(arr, 1, [{"string": "Weekly energy report", "bbox": [10, 18, 380, 44]}], fams)
    run = res["runs"][0]
    assert run["family"] == "Manrope" and abs(run["weight"] - 700) <= 100


def _icons_indexed():
    import icon_match
    return (icon_match.cache_dir() / "index.npz").exists()


@pytest.mark.skipif(not _icons_indexed(), reason="icon index not built")
def test_icon_match_finds_a_rendered_icon():
    import icon_match
    svg = icon_match.svg_source(icon_match.svg_path("lucide:bell").read_text(), 2.0)
    cov = icon_match.render_svg(svg, 2.0)                     # 48×48 coverage
    img = np.full((80, 80, 3), 255.0, np.float32)
    img[16:16 + cov.shape[0], 16:16 + cov.shape[1]] -= cov[..., None] * 230
    res = icon_match.match_box(img, 1, [16, 16, cov.shape[1], cov.shape[0]])
    ids = [c["id"] for c in res["candidates"]]
    index = icon_match.load_index()
    assert any(icon_match.same_drawing(index, i, "lucide", "bell") for i in ids[:3])


def test_font_fetch_reports_network_errors(tmp_path, monkeypatch, capsys):
    """Offline (or a sandbox blocking the network) is reported as such, not as 'not found'."""
    import font_match
    import fontlib
    monkeypatch.setenv("S2Q_CACHE", str(tmp_path))
    monkeypatch.setattr(fontlib, "RAW", "http://127.0.0.1:9/fonts")
    monkeypatch.setattr(fontlib, "NET_ERRORS", [])
    monkeypatch.setattr(fontlib.time, "sleep", lambda s: None)
    assert font_match.main(["fetch", "--families", "Inter"]) == 2
    err = capsys.readouterr().err
    assert "failed" in err and "network access" in err
