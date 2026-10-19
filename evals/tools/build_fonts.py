#!/usr/bin/env python3
"""Build static TTF instances for the eval font library.

Variable fonts come from the google/fonts repo (OFL). Each needed weight is
instanced to a static TTF so that Chromium (ground-truth render) and Qt (output
render) rasterize from byte-identical outlines.

Variable families are instanced only when their OFL has no Reserved Font Name. IBM Plex has
one ("Plex"), so only its upstream static files are used, byte for byte (STATIC).

Naming: every instance of a family gets the same nameID 1 family ("Inter") and a
correct OS/2 usWeightClass, so both Chromium (@font-face) and Qt
(QFontDatabase) select by family + weight. nameID 16/17 are removed to keep
Qt's family grouping unambiguous.

Usage: python build_fonts.py --src ../../../fontsrc --out ../assets/fonts [--only "Onest,Sora"]
"""
import argparse
import pathlib
import sys

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

# family name -> (source file, extra pinned axes, weights)
FAMILIES = {
    "Inter": ("Inter[opsz,wght].ttf", {"opsz": 14}, [400, 500, 600, 700]),
    "JetBrains Mono": ("JetBrainsMono[wght].ttf", {}, [400, 500, 700]),
    "Manrope": ("Manrope[wght].ttf", {}, [400, 500, 600, 700, 800]),
    "DM Sans": ("DMSans[opsz,wght].ttf", {"opsz": 14}, [400, 500, 700]),
    "Space Grotesk": ("SpaceGrotesk[wght].ttf", {}, [400, 500, 600, 700]),
    "Nunito": ("Nunito[wght].ttf", {}, [400, 600, 700, 800]),
    "Outfit": ("Outfit[wght].ttf", {}, [300, 400, 500, 600]),
    "Plus Jakarta Sans": ("PlusJakartaSans[wght].ttf", {}, [400, 500, 600, 700]),
    # v1.0 cases 09-20
    "Onest": ("Onest[wght].ttf", {}, [400, 500, 600, 700]),
    "Sora": ("Sora[wght].ttf", {}, [300, 400, 500, 600, 700]),
    "Albert Sans": ("AlbertSans[wght].ttf", {}, [400, 500, 600, 700]),
    "Red Hat Display": ("RedHatDisplay[wght].ttf", {}, [500, 600, 700, 800]),
    "Red Hat Text": ("RedHatText[wght].ttf", {}, [400, 500, 600]),
    "Mulish": ("Mulish[wght].ttf", {}, [400, 500, 600, 700, 800]),
    "Public Sans": ("PublicSans[wght].ttf", {}, [400, 500, 600, 700]),
    "Instrument Sans": ("InstrumentSans[wdth,wght].ttf", {"wdth": 100}, [400, 500, 600, 700]),
    "Karla": ("Karla[wght].ttf", {}, [400, 500, 600, 700]),
    # not in the skill's font catalog: the "unknown / proprietary font" hard case (20)
    "Bricolage Grotesque": ("BricolageGrotesque[opsz,wdth,wght].ttf", {"opsz": 24, "wdth": 100}, [300, 400, 500, 600, 700, 800]),
}

# Families shipped as static TTFs upstream: copied byte-for-byte (no modification).
STATIC = {
    "Barlow": ["Barlow-Regular.ttf", "Barlow-Medium.ttf", "Barlow-SemiBold.ttf", "Barlow-Bold.ttf"],
    "Rajdhani": ["Rajdhani-Regular.ttf", "Rajdhani-Medium.ttf", "Rajdhani-SemiBold.ttf", "Rajdhani-Bold.ttf"],
    "Titillium Web": ["TitilliumWeb-Light.ttf", "TitilliumWeb-Regular.ttf", "TitilliumWeb-SemiBold.ttf", "TitilliumWeb-Bold.ttf"],
    "Be Vietnam Pro": ["BeVietnamPro-Regular.ttf", "BeVietnamPro-Medium.ttf", "BeVietnamPro-SemiBold.ttf", "BeVietnamPro-Bold.ttf"],
    "DM Mono": ["DMMono-Regular.ttf", "DMMono-Medium.ttf"],
    # IBM Plex has a Reserved Font Name ("Plex"): only the upstream static files, unmodified
    "IBM Plex Mono": ["IBMPlexMono-Regular.ttf", "IBMPlexMono-Medium.ttf", "IBMPlexMono-SemiBold.ttf"],
}

WEIGHT_NAMES = {100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Regular",
                500: "Medium", 600: "SemiBold", 700: "Bold", 800: "ExtraBold", 900: "Black"}


def set_names(font: TTFont, family: str, weight: int) -> None:
    style = WEIGHT_NAMES[weight]
    name = font["name"]
    for nid in (16, 17, 21, 22, 25):
        name.removeNames(nameID=nid)
    ps_family = family.replace(" ", "")
    for rec_platform in ((3, 1, 0x409), (1, 0, 0)):
        name.setName(family, 1, *rec_platform)
        name.setName(style, 2, *rec_platform)
        name.setName(f"{family} {style}", 4, *rec_platform)
        name.setName(f"{ps_family}-{style}", 6, *rec_platform)
        name.setName(f"{ps_family}-{style};static", 3, *rec_platform)
    os2 = font["OS/2"]
    os2.usWeightClass = weight
    bold = weight >= 700
    # fsSelection: bit0 italic, bit5 bold, bit6 regular
    os2.fsSelection = (os2.fsSelection & ~0b1100001) | (0b100000 if bold else 0b1000000)
    font["head"].macStyle = 0b1 if bold else 0
    if "STAT" in font:
        del font["STAT"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", help="comma-separated families to (re)build; default: all")
    args = ap.parse_args()
    only = {f.strip() for f in args.only.split(",")} if args.only else None
    src = pathlib.Path(args.src)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for family, files in STATIC.items():
        if only and family not in only:
            continue
        for fname in files:
            path = src / fname
            if not path.exists():
                print(f"[error] missing source font: {path}", file=sys.stderr)
                return 2
            (out / fname).write_bytes(path.read_bytes())
            print(f"{fname}  {family} (static copy)")
    for family, (fname, pins, weights) in FAMILIES.items():
        if only and family not in only:
            continue
        path = src / fname
        if not path.exists():
            print(f"[error] missing source font: {path}", file=sys.stderr)
            return 2
        for w in weights:
            vf = TTFont(path)
            axes = {a.axisTag for a in vf["fvar"].axes}
            loc = {k: v for k, v in pins.items() if k in axes}
            loc["wght"] = w
            static = instancer.instantiateVariableFont(vf, loc, updateFontNames=False)
            set_names(static, family, w)
            dst = out / f"{family.replace(' ', '')}-{WEIGHT_NAMES[w]}.ttf"
            static.save(dst)
            print(f"{dst.name}  {family} {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
