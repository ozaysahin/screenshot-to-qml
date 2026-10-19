# design-spec.json

The spec is the single source of truth between measuring and building. `diff.py` also reads it:
node boxes become the regions it scores, text entries become the strings it looks for. A good
spec therefore makes both the build and the verification better.

Schema: `assets/schema/design-spec.schema.json` (JSON Schema 2020-12). Units are design px.

## Minimal spec (enough for build + verification)

```json
{
  "meta": {"source": "input.png", "designSize": [1440, 900], "dpr": 2,
           "profile": "desktop", "mode": "production", "target": "pyside6",
           "layout": "responsive", "minQt": "6.8", "lang": "tr"},
  "tokens": {
    "color": {
      "bg":      {"hex": "#0A0B10", "alpha": 1, "src": "measured", "conf": 0.98},
      "accent":  {"hex": "#7C5CFF", "alpha": 1, "src": "measured", "conf": 0.95},
      "okSoft":  {"hex": "#34D399", "alpha": 0.14, "src": "inferred", "conf": 0.7}
    },
    "space": {"1": 4, "2": 8, "3": 12, "4": 16, "5": 20, "6": 24},
    "radius": {"md": 8, "lg": 12, "xl": 14},
    "typeScale": [
      {"family": "Space Grotesk", "px": 26, "weight": 600, "lineHeight": 32, "letterSpacing": -0.5},
      {"family": "Inter", "px": 14, "weight": 400, "lineHeight": 20}
    ]
  },
  "nodes": [
    {"id": "sidebar", "role": "Sidebar", "parent": null, "bbox": [0, 0, 240, 900],
     "style": {"fill": {"hex": "#0E1017", "alpha": 1}}},
    {"id": "navMain", "role": null, "parent": "sidebar", "bbox": [16, 222, 207, 206],
     "model": {"name": "nav", "count": 5, "itemId": "navItem"}},
    {"id": "kpi[0]", "role": "StatCard", "parent": "kpis", "bbox": [272, 100, 272, 132],
     "style": {"fill": {"hex": "#12141C", "alpha": 1}, "radius": 14}}
  ],
  "text": [
    {"string": "Genel Bakış", "owner": "topbar", "bbox": [272, 24, 138, 34],
     "color": {"hex": "#ECEEF5", "alpha": 1}, "align": "start",
     "font": {"family": "Space Grotesk", "px": 26, "weight": 600, "lineHeight": 32}}
  ],
  "icons": [
    {"match": "lucide:cpu", "score": 0.9, "owner": "kpi[0]", "bbox": [290, 124, 16, 16],
     "color": {"hex": "#7C5CFF", "alpha": 1}, "kind": "svg"}
  ],
  "states": {}
}
```

## Field rules

- `src`: `measured` (read from pixels by a script), `inferred` (derived from measurements,
  e.g. an alpha or a font family), `assumed` (not visible in the input, e.g. a hover color).
  Eval ground truth uses `truth`.
- `conf` in 0–1. Anything below 0.7 goes into the README's "please verify" list.
- `alpha` is always separate from `hex`. Only the Theme generator writes Qt `#AARRGGBB`.
- `nodes[].id`: stable, role-based (`sidebar`, `kpi[0]`). Repeated items use `name[i]` and the
  container carries `model`.
- `nodes[].bbox`: outer box (border included). Give every visually distinct surface a node;
  `diff.py` scores each node larger than 24×24 as a region.
- `text[].string`: exactly what is visible (after uppercase transforms). `bbox` is the painted
  text box (glyph ascent to descent), not the element box.
- `text[].align`: `start` | `center` | `end`; the diff measures position from that edge.
- Nodes with a solid fill (`style.fill.alpha == 1`) get a color check; give them `style.fill`.

## Checks before building

- Child boxes lie inside parent boxes.
- Every token referenced in a node style exists in `tokens`.
- Spacing values fit the spacing scale (±1 px) or are recorded as one-offs on purpose.
- Every repeated group has a `model` with the right count.
- Validate: `python -c "import json,jsonschema; jsonschema.validate(json.load(open('design-spec.json')), json.load(open('<skill>/assets/schema/design-spec.schema.json')))"`
