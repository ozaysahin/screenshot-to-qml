// Minimal SVG chart helpers used only while authoring eval designs.
// The build snapshots the resulting static SVG, so source/index.html has no JS.
window.__chartsDone = false;
window.Charts = (function () {
  const NS = 'http://www.w3.org/2000/svg';
  const f2 = v => Number(v.toFixed(2));
  function el(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) if (attrs[k] !== undefined) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  const lerp = (v, d0, d1, r0, r1) => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);
  function smooth(pts, t = 0.16) {
    let d = `M${f2(pts[0][0])},${f2(pts[0][1])}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
      const c1 = [p1[0] + (p2[0] - p0[0]) * t, p1[1] + (p2[1] - p0[1]) * t];
      const c2 = [p2[0] - (p3[0] - p1[0]) * t, p2[1] - (p3[1] - p1[1]) * t];
      d += ` C${f2(c1[0])},${f2(c1[1])} ${f2(c2[0])},${f2(c2[1])} ${f2(p2[0])},${f2(p2[1])}`;
    }
    return d;
  }
  const poly = pts => pts.map((p, i) => (i ? 'L' : 'M') + f2(p[0]) + ',' + f2(p[1])).join(' ');
  let gid = 0;
  function gradient(svg, stops, vertical = true) {
    let defs = svg.querySelector('defs') || el('defs', {}, svg);
    const id = `g${++gid}`;
    const g = el('linearGradient', { id, x1: 0, y1: 0, x2: vertical ? 0 : 1, y2: vertical ? 1 : 0 }, defs);
    stops.forEach(s => el('stop', { offset: s[0], 'stop-color': s[1], 'stop-opacity': s[2] ?? 1 }, g));
    return `url(#${id})`;
  }
  function size(svg, w, h) { svg.setAttribute('viewBox', `0 0 ${w} ${h}`); svg.setAttribute('width', w); svg.setAttribute('height', h); }
  function label(svg, x, y, txt, o, anchor = 'middle') {
    const t = el('text', { x: f2(x), y: f2(y), 'text-anchor': anchor, fill: o.labelColor,
      'font-family': o.font, 'font-size': o.fontSize || 12, 'font-weight': o.fontWeight || 400 }, svg);
    t.textContent = txt;
    return t;
  }

  function line(svg, o) {
    const { width: W, height: H } = o; size(svg, W, H);
    const p = Object.assign({ l: 40, r: 8, t: 8, b: 26 }, o.padding);
    const x = i => lerp(i, 0, o.xCount - 1, p.l, W - p.r);
    const y = v => lerp(v, o.yMin, o.yMax, H - p.b, p.t);
    (o.yTicks || []).forEach(v => {
      el('line', { x1: p.l, x2: W - p.r, y1: f2(y(v)), y2: f2(y(v)), stroke: o.grid, 'stroke-width': 1, 'stroke-dasharray': o.gridDash }, svg);
      label(svg, p.l - 10, y(v) + 4, o.yFormat ? o.yFormat(v) : v, o, 'end');
    });
    (o.xLabels || []).forEach((t, i) => { if (t !== '') label(svg, x(i * (o.xCount - 1) / (o.xLabels.length - 1)), H - 6, t, o); });
    if (o.ref) {
      el('line', { x1: p.l, x2: W - p.r, y1: f2(y(o.ref.value)), y2: f2(y(o.ref.value)), stroke: o.ref.color, 'stroke-width': o.ref.width || 1.5, 'stroke-dasharray': o.ref.dash || '6 6' }, svg);
    }
    o.series.forEach(s => {
      const pts = s.values.map((v, i) => [x(i), y(v)]);
      const d = s.smooth === false ? poly(pts) : smooth(pts);
      if (s.area) {
        const fill = gradient(svg, [[0, s.color, s.area[0]], [1, s.color, s.area[1]]]);
        el('path', { d: `${d} L${f2(pts[pts.length - 1][0])},${H - p.b} L${f2(pts[0][0])},${H - p.b} Z`, fill, stroke: 'none' }, svg);
      }
      el('path', { d, fill: 'none', stroke: s.color, 'stroke-width': s.width || 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-dasharray': s.dash }, svg);
      if (s.dot) {
        const last = pts[s.dot === 'last' ? pts.length - 1 : s.dot];
        el('circle', { cx: f2(last[0]), cy: f2(last[1]), r: 5, fill: o.dotFill || '#fff', stroke: s.color, 'stroke-width': 2.5 }, svg);
      }
    });
  }

  function spark(svg, o) {
    const { width: W, height: H } = o; size(svg, W, H);
    const min = Math.min(...o.values), max = Math.max(...o.values);
    const pts = o.values.map((v, i) => [lerp(i, 0, o.values.length - 1, 1, W - 1), lerp(v, min, max, H - 2, 2)]);
    const d = smooth(pts);
    if (o.area) el('path', { d: `${d} L${W - 1},${H} L1,${H} Z`, fill: gradient(svg, [[0, o.color, o.area], [1, o.color, 0]]) }, svg);
    el('path', { d, fill: 'none', stroke: o.color, 'stroke-width': o.strokeWidth || 1.75, 'stroke-linecap': 'round' }, svg);
  }

  function bars(svg, o) {
    const { width: W, height: H } = o; size(svg, W, H);
    const p = Object.assign({ l: 36, r: 4, t: 8, b: 28 }, o.padding);
    const y = v => lerp(v, 0, o.yMax, H - p.b, p.t);
    (o.yTicks || []).forEach(v => {
      el('line', { x1: p.l, x2: W - p.r, y1: f2(y(v)), y2: f2(y(v)), stroke: o.grid, 'stroke-width': 1, 'stroke-dasharray': o.gridDash }, svg);
      label(svg, p.l - 10, y(v) + 4, o.yFormat ? o.yFormat(v) : v, o, 'end');
    });
    const n = o.groups.length, slot = (W - p.l - p.r) / n;
    o.groups.forEach((g, i) => {
      const k = g.values.length, bw = o.barWidth, inner = o.innerGap || 4;
      const total = k * bw + (k - 1) * inner;
      let x0 = p.l + slot * i + (slot - total) / 2;
      g.values.forEach((v, j) => {
        const top = y(v), h = H - p.b - top, r = Math.min(o.radius || 0, bw / 2, h);
        const x = x0 + j * (bw + inner);
        const d = `M${f2(x)},${f2(H - p.b)} V${f2(top + r)} Q${f2(x)},${f2(top)} ${f2(x + r)},${f2(top)} H${f2(x + bw - r)} Q${f2(x + bw)},${f2(top)} ${f2(x + bw)},${f2(top + r)} V${f2(H - p.b)} Z`;
        el('path', { d, fill: (g.colors || o.colors)[j] }, svg);
      });
      label(svg, p.l + slot * i + slot / 2, H - 8, g.label, Object.assign({}, o, g.highlight ? { labelColor: o.highlightColor, fontWeight: 700 } : {}));
    });
  }

  function arc(cx, cy, r, a0, a1) {
    const pt = a => [cx + r * Math.cos((a - 90) * Math.PI / 180), cy + r * Math.sin((a - 90) * Math.PI / 180)];
    const [x0, y0] = pt(a0), [x1, y1] = pt(a1);
    return `M${f2(x0)},${f2(y0)} A${r},${r} 0 ${a1 - a0 > 180 ? 1 : 0} 1 ${f2(x1)},${f2(y1)}`;
  }

  function donut(svg, o) {
    const S = o.size; size(svg, S, S);
    const r = (S - o.thickness) / 2, c = S / 2;
    if (o.track) el('circle', { cx: c, cy: c, r, fill: 'none', stroke: o.track, 'stroke-width': o.thickness }, svg);
    const total = o.segments.reduce((a, s) => a + s.value, 0);
    let a = 0;
    o.segments.forEach(s => {
      const span = (s.value / total) * 360;
      el('path', { d: arc(c, c, r, a + (o.gap || 0) / 2, a + span - (o.gap || 0) / 2), fill: 'none', stroke: s.color, 'stroke-width': o.thickness, 'stroke-linecap': o.round ? 'round' : 'butt' }, svg);
      a += span;
    });
  }

  function ring(svg, o) {
    const S = o.size; size(svg, S, S);
    const r = (S - o.thickness) / 2, c = S / 2;
    el('circle', { cx: c, cy: c, r, fill: 'none', stroke: o.track, 'stroke-width': o.thickness }, svg);
    const stroke = o.stops ? gradient(svg, o.stops, false) : o.color;
    el('path', { d: arc(c, c, r, 0, Math.max(0.01, o.value * 360 - 0.01)), fill: 'none', stroke, 'stroke-width': o.thickness, 'stroke-linecap': 'round' }, svg);
  }

  return { line, spark, bars, donut, ring, done: () => { window.__chartsDone = true; } };
})();
