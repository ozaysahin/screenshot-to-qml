#!/usr/bin/env python3
"""Build docs/img/demo.gif: the cluster screenshot turning into the live Qt Quick app.

Usage (Linux without a display: xvfb-run -a -s "-screen 0 2000x800x24" python docs/tools/demo_gif.py):
  python docs/tools/demo_gif.py [--out docs/img/demo.gif] [--width 960]

Loads skills/screenshot-to-qml/examples/auto-cluster/project with PySide6 (the Qt 5.15 QML runs
through the skill's assets/qt5-shim), then:
  1. shows input.png (the screenshot the skill received),
  2. wipes from the screenshot to the app's own frame,
  3. drives MockData.speed / rpm to show that the dials are live QML bound to properties,
  4. ends on the check result from examples/auto-cluster/check/summary.json.
Every frame of the app is grabbed from the running window; nothing is drawn by hand.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "screenshot-to-qml"
EXAMPLE = SKILL / "examples" / "auto-cluster"
PROJECT = EXAMPLE / "project"
FONT = ROOT / "evals" / "assets" / "fonts" / "Inter-SemiBold.ttf"
W, H, BAR = 1920, 720, 72
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
os.environ["QT_SCALE_FACTOR"] = "1"

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from PySide6.QtCore import QUrl  # noqa: E402
from PySide6.QtGui import QFontDatabase, QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickWindow  # noqa: F401,E402

BG, INK, MUTED, ACCENT = (6, 8, 11), (242, 245, 248), (125, 138, 153), (53, 200, 255)


def qimage_to_pil(img) -> Image.Image:
    img = img.convertToFormat(img.Format.Format_RGBA8888)
    return Image.frombuffer("RGBA", (img.width(), img.height()), bytes(img.constBits()), "raw", "RGBA", 0, 1).convert("RGB")


def ease(t: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, t)))


class Captioner:
    def __init__(self):
        self.big = ImageFont.truetype(str(FONT), 30)
        self.small = ImageFont.truetype(str(FONT), 24)
        self.tag = ImageFont.truetype(str(FONT), 26)

    def tags(self, img: Image.Image, x: int) -> None:
        """Pills on both sides of the wipe line: what is left of it is QML, right of it the PNG."""
        d = ImageDraw.Draw(img)
        for text, right in (("Qt Quick", False), ("screenshot", True)):
            w = d.textlength(text, font=self.tag) + 36
            x0 = x + 14 if right else x - 14 - w
            d.rounded_rectangle([x0, 330, x0 + w, 390], radius=30, fill=ACCENT if not right else (38, 48, 59))
            d.text((x0 + w / 2, 360), text, font=self.tag, fill=BG if not right else INK, anchor="mm")

    def frame(self, img: Image.Image, left: str, right: str = "", step: int = 0) -> Image.Image:
        out = Image.new("RGB", (W, H + BAR), BG)
        out.paste(img, (0, 0))
        d = ImageDraw.Draw(out)
        d.line([(0, H), (W, H)], fill=(24, 33, 43), width=2)
        d.text((40, H + BAR / 2), left, font=self.big, fill=INK, anchor="lm")
        d.text((W - 40, H + BAR / 2), right, font=self.small, fill=MUTED, anchor="rm")
        for i in range(3):    # progress dots: screenshot · rebuild · live
            x = W / 2 - 30 + i * 30
            d.ellipse([x - 6, H + BAR / 2 - 6, x + 6, H + BAR / 2 + 6], fill=ACCENT if i == step else (38, 48, 59))
        return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "img" / "demo.gif")
    ap.add_argument("--width", type=int, default=960)
    args = ap.parse_args(argv)

    app = QGuiApplication(sys.argv[:1])
    for f in sorted((PROJECT / "assets" / "fonts").glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(f))
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(PROJECT / "qml"))
    engine.addImportPath(str(SKILL / "assets" / "qt5-shim"))
    engine.load(QUrl.fromLocalFile(str(PROJECT / "qml" / "App" / "Main.qml")))
    if not engine.rootObjects():
        print("[error] QML failed to load", file=sys.stderr)
        return 2
    window = engine.rootObjects()[0]
    window.resize(W, H)
    window.setWidth(W)
    window.setHeight(H)
    window.show()
    data = engine.singletonInstance("App", "MockData")
    for _ in range(20):
        app.processEvents()

    def grab(speed: float | None = None, rpm: float | None = None) -> Image.Image:
        if speed is not None:
            data.setProperty("speed", speed)
        if rpm is not None:
            data.setProperty("rpm", rpm)
        app.processEvents()
        return qimage_to_pil(window.grabWindow())

    summary = json.loads((EXAMPLE / "check" / "summary.json").read_text())
    m = summary["metrics"]
    cap = Captioner()
    shot = Image.open(EXAMPLE / "input.png").convert("RGB")
    app_frame = grab(87, 2.4)
    frames: list[tuple[Image.Image, int]] = []

    frames.append((cap.frame(shot, "input.png — a screenshot of a car's instrument cluster", "1920 × 720", 0), 1600))
    n = 14
    for i in range(1, n + 1):          # wipe: app frame from the left
        x = round(W * ease(i / n))
        img = shot.copy()
        img.paste(app_frame.crop((0, 0, x, H)), (0, 0))
        ImageDraw.Draw(img).line([(x, 0), (x, H)], fill=ACCENT, width=4)
        if 0 < i < n:
            cap.tags(img, x)
        frames.append((cap.frame(img, "→ rebuilt as native Qt Quick by the skill", "QML | screenshot", 1), 70))
    frames.append((cap.frame(app_frame, "Qt Quick app — Qt 5.15 · C++ host · no web view",
                             f"SSIM {m['globalSSIM']:.3f} · {round(m['textMatchRate'] * 61)}/61 texts", 1), 1600))

    # live: the dials are bound to MockData.speed / rpm
    keys = [(87, 2.4), (138, 4.6), (64, 1.7), (87, 2.4)]
    steps = 16
    k = 0
    for (s0, r0), (s1, r1) in zip(keys, keys[1:], strict=False):
        for i in range(1, steps + 1):
            t = ease(i / steps)
            k += 1
            data.setProperty("turnLeft", (k // 8) % 2 == 0)     # the turn signal blinks
            img = grab(s0 + (s1 - s0) * t, r0 + (r1 - r0) * t)
            frames.append((cap.frame(img, "live QML: the dials are bound to properties", "MockData.speed / rpm", 2), 50))
        frames[-1] = (frames[-1][0], 500)
    data.setProperty("turnLeft", True)
    frames.append((cap.frame(grab(87, 2.4), "check.py: all 13 quality gates pass",
                             f"geometry ≤ {m['geometryMaxPx']:.1f} px · ΔE {m['colorDeltaEMax']:.1f}", 2), 2200))

    scale = args.width / W
    size = (args.width, round((H + BAR) * scale))
    imgs = [f.resize(size, Image.LANCZOS) for f, _ in frames]
    # one shared palette keeps the file small and the colors stable between frames
    palette_src = Image.new("RGB", (size[0], size[1] * 3))
    for k, idx in enumerate((0, len(imgs) // 2, len(imgs) - 1)):
        palette_src.paste(imgs[idx], (0, size[1] * k))
    pal = palette_src.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    q = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in imgs]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    q[0].save(args.out, save_all=True, append_images=q[1:], duration=[d for _, d in frames], loop=0,
              optimize=True, disposal=1)
    print(f"wrote {args.out} ({len(q)} frames, {size[0]}x{size[1]}, {args.out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
