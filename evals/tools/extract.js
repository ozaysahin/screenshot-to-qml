() => {
  // Ground-truth extraction from the live DOM. Units: CSS px (design px at 1x).
  const r2 = v => Math.round(v * 100) / 100;
  const box = b => [r2(b.x), r2(b.y), r2(b.width), r2(b.height)];
  const px = v => (v === 'normal' ? 'normal' : r2(parseFloat(v)));
  const transparent = c => !c || c === 'transparent' || /rgba\(.*,\s*0\)$/.test(c);
  // Chromium serializes oklch()/lab()/color() (Tailwind v4) as-is; turn every color into sRGB rgba()
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', { willReadFrequently: true });
  const toRGB = c => {
    if (!c || /^rgba?\(/.test(c) || c === 'transparent' || c === 'none') return c;
    cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = c; cx.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = cx.getImageData(0, 0, 1, 1).data;
    return a === 255 ? `rgb(${r}, ${g}, ${b})` : `rgba(${r}, ${g}, ${b}, ${Math.round(a / 255 * 1000) / 1000})`;
  };
  const colorsIn = s => (s ? s.replace(/(?:oklch|oklab|lab|lch|color)\([^)]*\)/g, m => toRGB(m)) : s);
  const firstFamily = f => f.split(',')[0].trim().replace(/^["']|["']$/g, '');
  const visible = el => {
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') return false;
    const b = el.getBoundingClientRect();
    return b.width > 0 && b.height > 0;
  };
  // hidden under another element (e.g. a list row behind an opaque tab bar): hit-test the left,
  // middle and right of the rect; ancestors do not count as occluders
  const occluded = (el, r) => {
    const cy = r.top + r.height / 2;
    return [r.left + 2, r.left + r.width / 2, r.right - 2].every(x => {
      if (x < 0 || cy < 0 || x >= innerWidth || cy >= innerHeight) return true;
      const hit = document.elementFromPoint(x, cy);
      return hit && !(hit === el || el.contains(hit) || hit.contains(el));
    });
  };

  // ---- tokens: custom properties declared on :root
  const rawTokens = {};
  const probe = document.createElement('div');
  document.body.appendChild(probe);
  // walks @layer / @media / @supports blocks too (Tailwind v4 puts its theme in `@layer theme { :root, :host { … } }`)
  const rootRules = rules => {
    for (const rule of rules) {
      if (rule.cssRules && !(rule instanceof CSSStyleRule)) {
        if (rule.media && !matchMedia(rule.media.mediaText).matches) continue;
        rootRules(rule.cssRules);
        continue;
      }
      if (!rule.selectorText || !rule.selectorText.split(',').some(sel => sel.trim() === ':root')) continue;
      for (const p of rule.style) {
        if (!p.startsWith('--')) continue;
        const raw = rule.style.getPropertyValue(p).trim();
        let color = null;
        if (CSS.supports('color', raw)) { probe.style.color = raw; color = toRGB(getComputedStyle(probe).color); }
        rawTokens[p] = { raw, color };
      }
    }
  };
  for (const sheet of document.styleSheets) {
    let rules; try { rules = sheet.cssRules; } catch (e) { continue; }
    rootRules(rules);
  }
  probe.remove();

  // ---- nodes
  const nodeEls = [...document.querySelectorAll('[data-node]')].filter(visible);
  const counts = {};
  nodeEls.forEach(el => { counts[el.dataset.node] = (counts[el.dataset.node] || 0) + 1; });
  const seen = {};
  const idOf = new Map();
  nodeEls.forEach(el => {
    const base = el.dataset.node;
    if (counts[base] > 1) { seen[base] = (seen[base] || 0); idOf.set(el, `${base}[${seen[base]++}]`); }
    else idOf.set(el, base);
  });
  const ownerOf = el => { let p = el.parentElement; while (p && !idOf.has(p)) p = p.parentElement; return p ? idOf.get(p) : null; };
  const colorsUsed = {};
  const addColor = (c, where) => { if (transparent(c)) return; colorsUsed[c] = colorsUsed[c] || { count: 0, where: new Set() }; colorsUsed[c].count++; colorsUsed[c].where.add(where); };

  const nodes = nodeEls.map(el => {
    const cs = getComputedStyle(el);
    const style = {};
    const bg = toRGB(cs.backgroundColor);
    if (!transparent(bg)) { style.fill = bg; addColor(bg, 'fill'); }
    if (cs.backgroundImage !== 'none') style.fillImage = colorsIn(cs.backgroundImage);
    const radii = ['borderTopLeftRadius', 'borderTopRightRadius', 'borderBottomRightRadius', 'borderBottomLeftRadius'].map(k => r2(parseFloat(cs[k]) || 0));
    if (radii.some(v => v)) style.radius = radii.every(v => v === radii[0]) ? radii[0] : radii;
    const sides = ['Top', 'Right', 'Bottom', 'Left'].map(s => ({ w: parseFloat(cs[`border${s}Width`]) || 0, c: toRGB(cs[`border${s}Color`]), s: cs[`border${s}Style`] }));
    if (sides.some(s => s.w && s.s !== 'none')) {
      const same = sides.every(s => s.w === sides[0].w && s.c === sides[0].c);
      style.border = same ? { width: sides[0].w, color: sides[0].c, style: sides[0].s }
        : sides.map((s, i) => ({ side: ['top', 'right', 'bottom', 'left'][i], width: s.w, color: s.c, style: s.s })).filter(s => s.width && s.style !== 'none');
      sides.forEach(s => s.w && addColor(s.c, 'border'));
    }
    if (cs.boxShadow !== 'none') style.shadow = colorsIn(cs.boxShadow);
    if (parseFloat(cs.opacity) < 1) style.opacity = r2(parseFloat(cs.opacity));
    if (cs.backdropFilter && cs.backdropFilter !== 'none') style.backdropFilter = cs.backdropFilter;
    if (cs.filter !== 'none') style.filter = cs.filter;
    if (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth)) style.outline = { width: px(cs.outlineWidth), color: toRGB(cs.outlineColor), offset: px(cs.outlineOffset) };
    const layout = {};
    if (cs.display.includes('flex')) { layout.kind = 'flex'; layout.direction = cs.flexDirection; layout.gap = px(cs.gap === 'normal' ? '0' : cs.columnGap !== 'normal' && cs.flexDirection.startsWith('row') ? cs.columnGap : cs.rowGap); layout.justify = cs.justifyContent; layout.align = cs.alignItems; if (cs.flexWrap !== 'nowrap') layout.wrap = cs.flexWrap; }
    else if (cs.display.includes('grid')) { layout.kind = 'grid'; layout.columns = cs.gridTemplateColumns; layout.rows = cs.gridTemplateRows; layout.columnGap = px(cs.columnGap); layout.rowGap = px(cs.rowGap); }
    const pad = ['Top', 'Right', 'Bottom', 'Left'].map(s => r2(parseFloat(cs[`padding${s}`]) || 0));
    if (pad.some(v => v)) layout.padding = pad;
    if (cs.position === 'absolute' || cs.position === 'fixed') layout.position = cs.position;
    if (cs.overflow !== 'visible') layout.clip = true;
    const n = { id: idOf.get(el), role: el.dataset.role || null, parent: ownerOf(el), bbox: box(el.getBoundingClientRect()), style, layout };
    if (el.dataset.state) n.state = el.dataset.state.split(/\s+/);
    if (el.dataset.model) {
      let items = [...el.querySelectorAll(':scope > [data-node]')];
      if (items.length) items = items.filter(i => i.dataset.node === items[0].dataset.node);
      n.model = { name: el.dataset.model, count: items.length, itemId: items[0] ? items[0].dataset.node : null };
    }
    if (el.dataset.value) n.value = el.dataset.value;
    return n;
  });

  // ---- text runs
  const text = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const measure = document.createElement('canvas').getContext('2d');
  const lang = document.documentElement.lang || 'tr';
  let tn;
  while ((tn = walker.nextNode())) {
    const raw = tn.textContent.replace(/\s+/g, ' ').trim();
    if (!raw) continue;
    const el = tn.parentElement;
    if (!el || el.closest('script,style,[data-icon]')) continue;
    if (!visible(el)) continue;
    const cs = getComputedStyle(el);
    let string = raw;
    if (cs.textTransform === 'uppercase') string = raw.toLocaleUpperCase(lang);
    else if (cs.textTransform === 'lowercase') string = raw.toLocaleLowerCase(lang);
    let rects;
    if (el instanceof SVGElement) rects = [el.getBoundingClientRect()];
    else {
      // trimmed range: leading/trailing whitespace is not part of the visible run
      const lead = tn.data.match(/^\s*/)[0].length, trail = tn.data.match(/\s*$/)[0].length;
      const rg = document.createRange(); rg.setStart(tn, lead); rg.setEnd(tn, tn.data.length - trail);
      rects = [...rg.getClientRects()].filter(r => r.width > 0);
    }
    if (!rects.length || rects.every(r => occluded(el, r))) continue;
    const x0 = Math.min(...rects.map(r => r.left)), y0 = Math.min(...rects.map(r => r.top));
    const x1 = Math.max(...rects.map(r => r.right)), y1 = Math.max(...rects.map(r => r.bottom));
    const lines = new Set(rects.map(r => Math.round(r.top))).size;
    // first-line baseline: content-area top + the first available font's ascent (same metrics the
    // inline box uses); lets scorers compare baselines instead of font-dependent box centers
    let baseline;
    if (!(el instanceof SVGElement)) {
      measure.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
      const fm = measure.measureText(string);
      const top = rects.reduce((a, r) => (r.top < a.top ? r : a)).top;
      baseline = r2(top + fm.fontBoundingBoxAscent);
    }
    const color = toRGB(el instanceof SVGElement ? (cs.fill && cs.fill !== 'none' ? cs.fill : cs.color) : cs.color);
    addColor(color, 'text');
    const lh = cs.lineHeight;
    text.push({
      string, owner: idOf.get(el) || ownerOf(el), bbox: [r2(x0), r2(y0), r2(x1 - x0), r2(y1 - y0)], ...(baseline !== undefined && { baseline }), lines,
      color, align: cs.textAlign,
      font: { family: firstFamily(cs.fontFamily), px: px(cs.fontSize), weight: parseInt(cs.fontWeight, 10),
              lineHeight: px(lh), letterSpacing: cs.letterSpacing === 'normal' ? 0 : px(cs.letterSpacing),
              italic: cs.fontStyle === 'italic', transform: cs.textTransform !== 'none' ? cs.textTransform : undefined,
              tabularNums: cs.fontVariantNumeric.includes('tabular') || undefined },
    });
  }

  // ---- form fields: a value or placeholder is not a DOM text node. One line, vertically centered
  // in the content box (Chromium's inner editor), start-aligned unless text-align says otherwise.
  const textTypes = new Set(['text', 'search', 'email', 'url', 'tel', 'number', 'password', 'date', 'time']);
  for (const el of document.querySelectorAll('input, textarea, select')) {
    if (!visible(el) || el.closest('[data-icon]')) continue;
    if (el.tagName === 'INPUT' && !textTypes.has(el.type)) continue;
    let string, pseudo = null;
    if (el.tagName === 'SELECT') string = el.selectedOptions[0] ? el.selectedOptions[0].text : '';
    else if (el.value) string = el.type === 'password' ? '\u2022'.repeat(el.value.length) : el.value;
    else { string = el.placeholder || ''; pseudo = '::placeholder'; }
    string = string.replace(/\s+/g, ' ').trim();
    if (!string) continue;
    const cs = getComputedStyle(el), ps = pseudo ? getComputedStyle(el, pseudo) : cs;
    const r = el.getBoundingClientRect();
    const bl = parseFloat(cs.borderLeftWidth) + parseFloat(cs.paddingLeft), br = parseFloat(cs.borderRightWidth) + parseFloat(cs.paddingRight);
    const bt = parseFloat(cs.borderTopWidth) + parseFloat(cs.paddingTop), bb = parseFloat(cs.borderBottomWidth) + parseFloat(cs.paddingBottom);
    measure.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    measure.letterSpacing = cs.letterSpacing === 'normal' ? '0px' : cs.letterSpacing;
    const fm = measure.measureText(string);
    measure.letterSpacing = '0px';
    const w = fm.width, asc = fm.fontBoundingBoxAscent, h = asc + fm.fontBoundingBoxDescent;
    const cw = r.width - bl - br, ch = r.height - bt - bb;
    let x = r.left + bl;
    if (cs.textAlign === 'center') x += (cw - w) / 2; else if (cs.textAlign === 'right' || cs.textAlign === 'end') x += cw - w;
    const lh = parseFloat(cs.lineHeight);
    const lineBox = el.tagName === 'TEXTAREA' ? (isNaN(lh) ? h : lh) : ch;
    const y = r.top + bt + (lineBox - h) / 2;
    if (occluded(el, { left: x, right: x + w, width: w, top: y, height: h })) continue;
    const color = toRGB(ps.color);
    addColor(color, 'text');
    text.push({
      string, owner: idOf.get(el) || ownerOf(el), bbox: [r2(x), r2(y), r2(w), r2(h)], baseline: r2(y + asc), lines: 1,
      color, align: cs.textAlign, field: el.tagName.toLowerCase() + (pseudo ? ':placeholder' : ''),
      font: { family: firstFamily(cs.fontFamily), px: px(cs.fontSize), weight: parseInt(cs.fontWeight, 10),
              lineHeight: px(cs.lineHeight), letterSpacing: cs.letterSpacing === 'normal' ? 0 : px(cs.letterSpacing),
              italic: cs.fontStyle === 'italic', tabularNums: cs.fontVariantNumeric.includes('tabular') || undefined },
    });
  }

  // ---- icons
  const icons = [...document.querySelectorAll('[data-icon]')].filter(el => visible(el) && !occluded(el, el.getBoundingClientRect())).map(el => {
    const cs = getComputedStyle(el);
    const isFont = !(el instanceof SVGElement);
    const color = toRGB(cs.color);
    addColor(color, 'icon');
    const o = { match: el.dataset.icon, owner: ownerOf(el), bbox: box(el.getBoundingClientRect()), color };
    if (isFont) {
      o.kind = 'font-glyph';
      o.codepoint = 'U+' + el.textContent.codePointAt(0).toString(16).toUpperCase();
      o.font = { family: firstFamily(cs.fontFamily), px: px(cs.fontSize), weight: parseInt(cs.fontWeight, 10) };
    } else {
      o.kind = 'svg';
      const sw = el.getAttribute('stroke-width');
      if (sw && el.getAttribute('stroke') !== 'none') o.strokeWidth = parseFloat(cs.strokeWidth) || parseFloat(sw);
      o.filled = el.getAttribute('fill') === 'currentColor';
    }
    return o;
  });

  const dataEl = document.getElementById('case-data');
  const data = dataEl ? JSON.parse(dataEl.textContent) : null;
  const cu = Object.entries(colorsUsed).sort((a, b) => b[1].count - a[1].count)
    .map(([c, v]) => ({ color: c, count: v.count, where: [...v.where] }));
  return { lang, rawTokens, nodes, text, icons, colorsUsed: cu, data };
}
