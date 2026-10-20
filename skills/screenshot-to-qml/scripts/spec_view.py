#!/usr/bin/env python3
"""Print a design-spec as a compact table instead of reading its JSON.

Usage:
  python spec_view.py design-spec.json [--tokens] [--nodes] [--text] [--icons] [--ids s1,t3] [--verify]

Without a section flag every section is printed. One line per item:
  tokens  c3  #1E293B
  nodes   s4  Card  x,y w×h  fill=c3 r=12 border=1 c5 shadow  parent=s1  [verify]
  text    t7  "Kaydet"  x,y w×h  px15 w600 Inter  c1  [verify]
  icons   i2  lucide:settings  x,y w×h  c4
--verify keeps only items flagged `verify` or with conf < 0.7; --ids keeps the listed ids.
Exit codes: 0 ok, 2 error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def box(b) -> str:
    if not b:
        return "-"
    x, y, w, h = (round(v, 1) for v in b)
    return f"{x:g},{y:g} {w:g}×{h:g}"


def color(v) -> str:
    if isinstance(v, dict):
        if v.get("token"):
            return v["token"]
        hx = v.get("hex", "")
        a = v.get("alpha", 1)
        return hx + (f"@{a:g}" if a not in (1, 1.0, None) else "")
    return str(v) if v else "-"


def ident(it: dict) -> str:
    return str(it.get("id") or ("@" + it["owner"] if it.get("owner") else "-"))


def flagged(it: dict) -> bool:
    return bool(it.get("verify")) or (isinstance(it.get("conf"), (int, float)) and it["conf"] < 0.7)


def tokens(spec: dict) -> list[str]:
    out = []
    t = spec.get("tokens", {})
    colors = t.get("color") or t.get("colors") or {}
    if colors:
        out.append("color   " + "  ".join(f"{k}={color(v)}" for k, v in colors.items()))
    for name in ("space", "radius"):
        if t.get(name):
            out.append(f"{name:7s} " + "  ".join(f"{k}={v}" for k, v in t[name].items()))
    scale = t.get("typeScale") or []
    items = scale.items() if isinstance(scale, dict) else ((e.get("role") or e.get("name") or f"#{i}", e)
                                                           for i, e in enumerate(scale) if isinstance(e, dict))
    for k, v in items:
        out.append(f"type    {k}: {v.get('family', '')} px{v.get('px', v.get('size', ''))} w{v.get('weight', '')}")
    return out


def node_line(n: dict) -> str:
    st = n.get("style", {})
    parts = [f"{ident(n):8s}", f"{(n.get('role') or '-'):12s}", box(n.get("bbox"))]
    if st.get("fill") or n.get("fillToken"):
        parts.append("fill=" + (n.get("fillToken") or color(st.get("fill"))))
    r = st.get("radius")
    if r:
        parts.append(f"r={r}")
    b = st.get("border")
    if isinstance(b, dict) and b.get("width"):
        parts.append(f"border={b['width']} {color(b.get('color'))}")
    if st.get("shadow"):
        parts.append("shadow")
    if st.get("gradient") or (isinstance(st.get("fill"), dict) and st["fill"].get("gradient")):
        parts.append("gradient")
    if n.get("parent"):
        parts.append(f"parent={n['parent']}")
    if n.get("model"):
        md = n["model"]
        parts.append("model=" + (f"{md.get('name')}×{md.get('count')}" if isinstance(md, dict) else str(md)))
    if flagged(n):
        parts.append("[verify]")
    return "  ".join(parts)


def text_line(t: dict) -> str:
    f = t.get("font", {}) or {}
    parts = [f"{ident(t):8s}", json.dumps(t.get("string", ""), ensure_ascii=False), box(t.get("bbox"))]
    spec_font = " ".join(str(x) for x in (f"px{f['px']}" if f.get("px") else "", f"w{f['weight']}" if f.get("weight") else "",
                                          f.get("family", "")) if x)
    if spec_font:
        parts.append(spec_font)
    if t.get("color"):
        parts.append(color(t["color"]))
    if flagged(t):
        parts.append("[verify]")
    return "  ".join(parts)


def icon_line(i: dict) -> str:
    m = i.get("match")
    name = i.get("name") or (m.get("name") if isinstance(m, dict) else m)
    parts = [f"{ident(i):8s}", str(name or "?"), box(i.get("bbox"))]
    if i.get("color"):
        parts.append(color(i["color"]))
    if flagged(i):
        parts.append("[verify]")
    return "  ".join(parts)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path)
    for s in ("tokens", "nodes", "text", "icons"):
        ap.add_argument(f"--{s}", action="store_true")
    ap.add_argument("--ids", default="", help="comma-separated ids to show")
    ap.add_argument("--verify", action="store_true", help="only items flagged verify or with conf < 0.7")
    args = ap.parse_args(argv)
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"[error] {e}", file=sys.stderr)
        return 2
    every = not any((args.tokens, args.nodes, args.text, args.icons))
    ids = {s.strip() for s in args.ids.split(",") if s.strip()}

    def keep(it: dict) -> bool:
        return (not ids or it.get("id") in ids or it.get("owner") in ids) and (not args.verify or flagged(it))

    m = spec.get("meta", {})
    print(f"# {args.spec.name}: design {m.get('designSize')} @{m.get('dpr')}x  profile {m.get('profile', '-')}  "
          f"nodes {len(spec.get('nodes', []))}  text {len(spec.get('text', []))}  icons {len(spec.get('icons', []))}")
    if (every or args.tokens) and not ids and not args.verify:
        print("## tokens")
        print("\n".join(tokens(spec)) or "(none)")
    for name, items, fn in (("nodes", spec.get("nodes", []), node_line), ("text", spec.get("text", []), text_line),
                            ("icons", spec.get("icons", []), icon_line)):
        if every or getattr(args, name):
            if name == "text":      # runs without an id are shown as #index, as in sheet.py's OCR sheet
                items = [t if t.get("id") else dict(t, id=f"#{k}") for k, t in enumerate(items)]
            rows = [fn(i) for i in items if keep(i)]
            if rows:
                print(f"## {name}")
                print("\n".join(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
