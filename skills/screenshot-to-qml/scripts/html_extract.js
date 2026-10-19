() => {
  // Design-spec extraction from a rendered HTML page (used by html_to_spec.py).
  // Units: CSS px (design px at 1x). Works on any page: no data-* hints needed.
  const r2 = v => Math.round(v * 100) / 100;
  const box = b => [r2(b.x), r2(b.y), r2(b.width), r2(b.height)];
  const px = v => (v === 'normal' ? 'normal' : r2(parseFloat(v)));
  const firstFamily = f => f.split(',')[0].trim().replace(/^["']|["']$/g, '');

  // Chromium serializes oklch()/lab()/color() (Tailwind v4) as-is: turn every color into sRGB rgba()
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', { willReadFrequently: true });
  const toRGB = c => {
    if (!c || /^rgba?\(/.test(c) || c === 'transparent' || c === 'none') return c;
    cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = c; cx.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = cx.getImageData(0, 0, 1, 1).data;
    return a === 255 ? `rgb(${r}, ${g}, ${b})` : `rgba(${r}, ${g}, ${b}, ${Math.round(a / 255 * 1000) / 1000})`;
  };
  const colorsIn = s => (s ? s.replace(/(?:oklch|oklab|lab|lch|color)\([^)]*\)/g, m => toRGB(m)) : s);
  const transparent = c => !c || c === 'transparent' || /rgba\(.*,\s*0\)$/.test(c);
  const vw = innerWidth, vh = innerHeight;
  const visible = el => {
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') return false;
    for (let a = el; a && a !== document.documentElement; a = a.parentElement)   // opacity:0 on any ancestor
      if (parseFloat(getComputedStyle(a).opacity) === 0) return false;
    const b = el.getBoundingClientRect();
    return b.width > 0 && b.height > 0 && b.right > 0 && b.bottom > 0 && b.left < vw && b.top < vh;
  };
  const occluded = (el, r) => {
    const cy = r.top + r.height / 2;
    return [r.left + 2, r.left + r.width / 2, r.right - 2].every(x => {
      if (x < 0 || cy < 0 || x >= vw || cy >= vh) return true;
      const hit = document.elementFromPoint(x, cy);
      return hit && !(hit === el || el.contains(hit) || hit.contains(el));
    });
  };

  // ---- tokens: custom properties on :root (also inside @layer / @media / @supports)
  const rawTokens = {};
  const probe = document.createElement('div');
  document.body.appendChild(probe);
  const fontFaces = [];
  const walk = (rules, base) => {
    for (const rule of rules) {
      if (rule instanceof CSSFontFaceRule) {
        const src = rule.style.getPropertyValue('src');
        const urls = [...src.matchAll(/url\(\s*["']?([^"')]+)["']?\s*\)/g)].map(m => new URL(m[1], base).href);
        fontFaces.push({ family: rule.style.getPropertyValue('font-family').replace(/^["']|["']$/g, ''),
                         weight: rule.style.getPropertyValue('font-weight') || '400',
                         style: rule.style.getPropertyValue('font-style') || 'normal', urls });
        continue;
      }
      if (rule.cssRules && !(rule instanceof CSSStyleRule)) {
        if (rule.media && !matchMedia(rule.media.mediaText).matches) continue;
        walk(rule.cssRules, base);
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
  const unreadableSheets = [];
  for (const sheet of document.styleSheets) {
    let rules; try { rules = sheet.cssRules; } catch (e) { unreadableSheets.push(sheet.href || '(inline)'); continue; }
    walk(rules, sheet.href || document.baseURI);
  }
  probe.remove();

  // ---- which elements become nodes: painted boxes, controls, landmarks, list/table items
  const CONTROL = { BUTTON: 'Button', SELECT: 'ComboBox', TEXTAREA: 'TextArea', PROGRESS: 'ProgressBar', METER: 'ProgressBar', A: 'Link', LABEL: null };
  const INPUT = { checkbox: 'CheckBox', radio: 'RadioButton', range: 'Slider', number: 'SpinBox', button: 'Button', submit: 'Button', reset: 'Button', color: 'Button', file: 'Button' };
  const ARIA = { button: 'Button', switch: 'Switch', checkbox: 'CheckBox', radio: 'RadioButton', slider: 'Slider', tab: 'Tab', tablist: 'TabBar',
                 menuitem: 'MenuItem', option: 'ListItem', listbox: 'ListView', progressbar: 'ProgressBar', dialog: 'Popup', tooltip: 'ToolTip',
                 alert: 'Toast', status: 'Toast', navigation: 'Nav', searchbox: 'TextField', textbox: 'TextField', combobox: 'ComboBox', link: 'Link' };
  const LANDMARK = { HEADER: 'Header', NAV: 'Nav', MAIN: 'Main', ASIDE: 'Sidebar', FOOTER: 'Footer', SECTION: 'Section', ARTICLE: 'Card',
                     FORM: 'Form', TABLE: 'Table', THEAD: null, TR: 'TableRow', TH: 'HeaderCell', LI: 'ListItem', DIALOG: 'Popup' };
  const roleOf = el => {
    const aria = el.getAttribute('role');
    if (aria && ARIA[aria]) return ARIA[aria];
    if (el.tagName === 'INPUT') return INPUT[el.type] || 'TextField';
    if (el.tagName in CONTROL) return CONTROL[el.tagName];
    if (el.tagName in LANDMARK) return LANDMARK[el.tagName];
    if (el.tagName === 'svg' || el instanceof SVGElement) return 'Graphic';
    return null;
  };
  const paints = cs => !transparent(toRGB(cs.backgroundColor)) || cs.backgroundImage !== 'none' || cs.boxShadow !== 'none' ||
    ['Top', 'Right', 'Bottom', 'Left'].some(s => parseFloat(cs[`border${s}Width`]) > 0 && cs[`border${s}Style`] !== 'none' && !transparent(toRGB(cs[`border${s}Color`]))) ||
    (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0);
  const isIconSvg = el => el.tagName === 'svg' && (() => { const b = el.getBoundingClientRect(); return b.width <= 64 && b.height <= 64; })();
  // tag + first class: selected/hover variants of an item (extra or swapped utility classes) stay in the same model
  const keyClass = el => [...el.classList].find(c => !/^[a-z]{1,3}-|^\d|:|^(is-|has-|active$|selected$|current$|open$|checked$|disabled$)/.test(c)) || el.classList[0] || '';
  const signature = el => el.tagName + '.' + keyClass(el);
  const all = [...document.body.querySelectorAll('*')].filter(el => !el.closest('script,style,noscript,template,head') && !(el.closest('svg') && el.tagName !== 'svg'));
  // repeated children (same tag + classes, >= 3 and >= 60 % of the visible children) -> a model;
  // the container and all its items become nodes even when they paint nothing themselves
  const modelOf = new Map(), modelItems = new Set();
  for (const el of all) {
    if (el.tagName === 'svg' || el.tagName === 'TR' || !visible(el)) continue;     // cells of a row are columns, not a model
    const kids = [...el.children].filter(k => visible(k) && !isIconSvg(k) && !['SCRIPT', 'STYLE', 'BR'].includes(k.tagName));
    if (kids.length < 3) continue;
    const sig = {}; kids.forEach(k => { sig[signature(k)] = (sig[signature(k)] || 0) + 1; });
    const [top, cnt] = Object.entries(sig).sort((a, b) => b[1] - a[1])[0];
    if (cnt < 3 || cnt < kids.length * 0.6) continue;
    const items = kids.filter(k => signature(k) === top);
    modelOf.set(el, items);
    items.forEach(k => modelItems.add(k));
  }
  const nodeEls = all.filter(el => visible(el) && !isIconSvg(el) &&
    (paints(getComputedStyle(el)) || roleOf(el) || el.hasAttribute('role') || el.tagName === 'svg' || modelOf.has(el) || modelItems.has(el)));

  // ids: tag.firstClass (or tag), numbered when repeated
  const base = el => {
    const cls = keyClass(el);
    return (el.id ? el.id : el.tagName.toLowerCase() + (cls ? '.' + cls.replace(/[^\w-]/g, '_') : ''));
  };
  const counts = {}, idOf = new Map();
  nodeEls.forEach(el => { counts[base(el)] = (counts[base(el)] || 0) + 1; });
  const seen = {};
  nodeEls.forEach(el => { const b = base(el); idOf.set(el, counts[b] > 1 ? `${b}[${seen[b] = (seen[b] ?? -1) + 1}]` : b); });
  const ownerOf = el => { let p = el.parentElement; while (p && !idOf.has(p)) p = p.parentElement; return p ? idOf.get(p) : null; };

  const colorsUsed = {};
  const addColor = (c, where) => { if (transparent(c)) return; colorsUsed[c] = colorsUsed[c] || { count: 0, where: new Set() }; colorsUsed[c].count++; colorsUsed[c].where.add(where); };

  const stateOf = el => {
    const s = [];
    const a = n => el.getAttribute(n);
    if (el.checked || a('aria-checked') === 'true' || a('aria-pressed') === 'true') s.push('checked');
    if (el.indeterminate || a('aria-checked') === 'mixed') s.push('indeterminate');
    if (el.disabled || a('aria-disabled') === 'true') s.push('disabled');
    if (a('aria-selected') === 'true' || (a('aria-current') && a('aria-current') !== 'false')) s.push('selected');
    if (a('aria-expanded') === 'true') s.push('expanded');
    if (a('aria-invalid') === 'true') s.push('error');
    if (document.activeElement === el && el !== document.body) s.push('focused');
    if ((el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') && !el.value && el.placeholder) s.push('placeholder');
    if (el.open) s.push('open');
    return s;
  };

  const nodes = nodeEls.map(el => {
    const cs = getComputedStyle(el);
    const style = {};
    const bg = toRGB(cs.backgroundColor);
    if (!transparent(bg)) { style.fill = bg; addColor(bg, 'fill'); }
    if (cs.backgroundImage !== 'none') style.fillImage = colorsIn(cs.backgroundImage);
    const b0 = el.getBoundingClientRect();
    const cap = Math.min(b0.width, b0.height) / 2;       // CSS pill radii (9999px, calc(infinity*1px)) render as half the short side
    const radii = ['borderTopLeftRadius', 'borderTopRightRadius', 'borderBottomRightRadius', 'borderBottomLeftRadius'].map(k => r2(Math.min(parseFloat(cs[k]) || 0, cap)));
    if (radii.some(v => v)) style.radius = radii.every(v => v === radii[0]) ? radii[0] : radii;
    const sides = ['Top', 'Right', 'Bottom', 'Left'].map(s => ({ w: parseFloat(cs[`border${s}Width`]) || 0, c: toRGB(cs[`border${s}Color`]), s: cs[`border${s}Style`] }));
    if (sides.some(s => s.w && s.s !== 'none' && !transparent(s.c))) {
      const same = sides.every(s => s.w === sides[0].w && s.c === sides[0].c && s.s === sides[0].s);
      style.border = same ? { width: sides[0].w, color: sides[0].c, style: sides[0].s }
        : sides.map((s, i) => ({ side: ['top', 'right', 'bottom', 'left'][i], width: s.w, color: s.c, style: s.s })).filter(s => s.width && s.style !== 'none' && !transparent(s.color));
      sides.forEach(s => s.w && addColor(s.c, 'border'));
    }
    if (cs.boxShadow !== 'none') style.shadow = colorsIn(cs.boxShadow);
    if (parseFloat(cs.opacity) < 1) style.opacity = r2(parseFloat(cs.opacity));
    if (cs.backdropFilter && cs.backdropFilter !== 'none') style.backdropFilter = cs.backdropFilter;
    if (cs.filter !== 'none') style.filter = cs.filter;
    if (cs.transform !== 'none') style.transform = cs.transform;
    if (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth)) style.outline = { width: px(cs.outlineWidth), color: toRGB(cs.outlineColor), offset: px(cs.outlineOffset) };
    const layout = {};
    if (cs.display.includes('flex')) { layout.kind = 'flex'; layout.direction = cs.flexDirection; layout.gap = px(cs.flexDirection.startsWith('row') ? (cs.columnGap === 'normal' ? '0' : cs.columnGap) : (cs.rowGap === 'normal' ? '0' : cs.rowGap)); layout.justify = cs.justifyContent; layout.align = cs.alignItems; if (cs.flexWrap !== 'nowrap') layout.wrap = cs.flexWrap; }
    else if (cs.display.includes('grid')) { layout.kind = 'grid'; layout.columns = cs.gridTemplateColumns; layout.rows = cs.gridTemplateRows; layout.columnGap = px(cs.columnGap); layout.rowGap = px(cs.rowGap); }
    const pad = ['Top', 'Right', 'Bottom', 'Left'].map(s => r2(parseFloat(cs[`padding${s}`]) || 0));
    if (pad.some(v => v)) layout.padding = pad;
    if (cs.position === 'absolute' || cs.position === 'fixed' || cs.position === 'sticky') layout.position = cs.position;
    if (cs.overflow !== 'visible') layout.clip = true;
    const n = { id: idOf.get(el), role: roleOf(el), parent: ownerOf(el), bbox: box(b0), tag: el.tagName.toLowerCase(), style, layout, src: 'truth' };
    const st = stateOf(el);
    if (st.length) n.state = st;
    if (el.tagName === 'INPUT' && (el.type === 'range' || el.type === 'number')) n.value = String(el.value);
    else if (el.tagName === 'PROGRESS' || el.tagName === 'METER') n.value = String(r2(el.value / (el.max || 1)));
    else if (el.tagName === 'SELECT' && el.selectedOptions[0]) n.value = el.selectedOptions[0].text;
    else if (el.getAttribute('aria-valuenow')) n.value = el.getAttribute('aria-valuenow');
    if (modelOf.has(el)) {
      const items = modelOf.get(el);
      n.model = { name: idOf.get(el).replace(/[^\w]/g, '_') + 'Model', count: items.length, itemId: base(items[0]) };
    }
    return n;
  });

  // ---- text runs (DOM text nodes)
  const text = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const measure = document.createElement('canvas').getContext('2d');
  const lang = document.documentElement.lang || 'en';
  // an invalid lang attribute ("tr_TR") must not stop the extraction: fall back to the locale-free case map
  const upper = t => { try { return t.toLocaleUpperCase(lang.replace('_', '-')); } catch (e) { return t.toUpperCase(); } };
  const lower = t => { try { return t.toLocaleLowerCase(lang.replace('_', '-')); } catch (e) { return t.toLowerCase(); } };
  let tn;
  while ((tn = walker.nextNode())) {
    const raw = tn.textContent.replace(/\s+/g, ' ').trim();
    if (!raw) continue;
    const el = tn.parentElement;
    if (!el || el.closest('script,style,noscript,template,option')) continue;
    if (!visible(el)) continue;
    const cs = getComputedStyle(el);
    let string = raw;
    if (cs.textTransform === 'uppercase') string = upper(raw);
    else if (cs.textTransform === 'lowercase') string = lower(raw);
    else if (cs.textTransform === 'capitalize') string = raw.replace(/(^|\s)(\S)/g, (m, a, c) => a + upper(c));
    let rects;
    if (el instanceof SVGElement) rects = [el.getBoundingClientRect()];
    else {
      const lead = tn.data.match(/^\s*/)[0].length, trail = tn.data.match(/\s*$/)[0].length;
      const rg = document.createRange(); rg.setStart(tn, lead); rg.setEnd(tn, tn.data.length - trail);
      rects = [...rg.getClientRects()].filter(r => r.width > 0);
    }
    if (!rects.length || rects.every(r => occluded(el, r))) continue;
    const x0 = Math.min(...rects.map(r => r.left)), y0 = Math.min(...rects.map(r => r.top));
    const x1 = Math.max(...rects.map(r => r.right)), y1 = Math.max(...rects.map(r => r.bottom));
    const lines = new Set(rects.map(r => Math.round(r.top))).size;
    let baseline;
    if (!(el instanceof SVGElement)) {
      measure.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
      const fm = measure.measureText(string);
      baseline = r2(rects.reduce((a, r) => (r.top < a.top ? r : a)).top + fm.fontBoundingBoxAscent);
    }
    const clipText = cs.backgroundClip === 'text' || cs.webkitBackgroundClip === 'text';
    const color = toRGB(el instanceof SVGElement ? (cs.fill && cs.fill !== 'none' ? cs.fill : cs.color) : cs.color);
    addColor(color, 'text');
    const t = {
      string, owner: idOf.get(el) || ownerOf(el), bbox: [r2(x0), r2(y0), r2(x1 - x0), r2(y1 - y0)], ...(baseline !== undefined && { baseline }), lines,
      color, align: cs.textAlign,
      font: { family: firstFamily(cs.fontFamily), px: px(cs.fontSize), weight: parseInt(cs.fontWeight, 10),
              lineHeight: px(cs.lineHeight), letterSpacing: cs.letterSpacing === 'normal' ? 0 : px(cs.letterSpacing),
              italic: cs.fontStyle === 'italic', transform: cs.textTransform !== 'none' ? cs.textTransform : undefined,
              tabularNums: cs.fontVariantNumeric.includes('tabular') || undefined },
    };
    if (clipText) t.fillImage = colorsIn(cs.backgroundImage);          // gradient text
    if (cs.transform !== 'none' || cs.writingMode !== 'horizontal-tb') t.transform = cs.writingMode !== 'horizontal-tb' ? cs.writingMode : cs.transform;
    text.push(t);
  }

  // ---- form fields: value or placeholder, one line, vertically centered in the content box
  // date/time inputs are painted in the browser's locale format, not their value: read those from the image
  const textTypes = new Set(['text', 'search', 'email', 'url', 'tel', 'number', 'password']);
  for (const el of document.querySelectorAll('input, textarea, select')) {
    if (!visible(el)) continue;
    if (el.tagName === 'INPUT' && !textTypes.has(el.type)) continue;
    let string, pseudo = null;
    if (el.tagName === 'SELECT') string = el.selectedOptions[0] ? el.selectedOptions[0].text : '';
    else if (el.value) string = el.type === 'password' ? '•'.repeat(el.value.length) : el.value;
    else { string = el.placeholder || ''; pseudo = '::placeholder'; }
    const isArea = el.tagName === 'TEXTAREA';
    const paragraphs = isArea ? string.split('\n') : [string];
    string = string.replace(/\s+/g, ' ').trim();
    if (!string) continue;
    const cs = getComputedStyle(el), ps = pseudo ? getComputedStyle(el, pseudo) : cs;
    const r = el.getBoundingClientRect();
    const bl = parseFloat(cs.borderLeftWidth) + parseFloat(cs.paddingLeft), br = parseFloat(cs.borderRightWidth) + parseFloat(cs.paddingRight);
    const bt = parseFloat(cs.borderTopWidth) + parseFloat(cs.paddingTop), bb = parseFloat(cs.borderBottomWidth) + parseFloat(cs.paddingBottom);
    measure.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    measure.letterSpacing = cs.letterSpacing === 'normal' ? '0px' : cs.letterSpacing;
    const fm = measure.measureText('Hg');
    const asc = fm.fontBoundingBoxAscent, h = asc + fm.fontBoundingBoxDescent;
    const cw = r.width - bl - br, ch = r.height - bt - bb;
    const lh = parseFloat(cs.lineHeight);
    // a textarea wraps at its content width (greedy, by words, like the browser); an input is one line
    const lines = [];
    for (const para of paragraphs) {
      if (!isArea) { lines.push(string); break; }
      let cur = '';
      for (const word of para.split(/(\s+)/)) {
        const next = cur + word;
        if (cur.trim() && measure.measureText(next.trimEnd()).width > cw) { lines.push(cur.trimEnd()); cur = word.trimStart(); }
        else cur = next;
      }
      lines.push(cur.trimEnd());
    }
    const step = isNaN(lh) ? h : lh;
    const color = toRGB(ps.color);
    lines.forEach((ln, i) => {
      if (!ln.trim()) return;
      const w = measure.measureText(ln).width;
      let x = r.left + bl;
      if (cs.textAlign === 'center') x += (cw - w) / 2; else if (cs.textAlign === 'right' || cs.textAlign === 'end') x += cw - w;
      const y = r.top + bt + (isArea ? i * step + (step - h) / 2 - el.scrollTop : (ch - h) / 2);
      if (y + h > r.bottom - bb + 0.5 || occluded(el, { left: x, right: x + w, width: w, top: y, height: h })) return;
      addColor(color, 'text');
      text.push({
        string: ln.trim(), owner: idOf.get(el) || ownerOf(el), bbox: [r2(x), r2(y), r2(w), r2(h)], baseline: r2(y + asc), lines: 1,
        color, align: cs.textAlign, field: el.tagName.toLowerCase() + (pseudo ? ':placeholder' : ''),
        font: { family: firstFamily(cs.fontFamily), px: px(cs.fontSize), weight: parseInt(cs.fontWeight, 10),
                lineHeight: px(cs.lineHeight), letterSpacing: cs.letterSpacing === 'normal' ? 0 : px(cs.letterSpacing),
                italic: cs.fontStyle === 'italic', tabularNums: cs.fontVariantNumeric.includes('tabular') || undefined },
      });
    });
    measure.letterSpacing = '0px';
  }

  // ---- icons: small inline SVGs (markup kept for reuse), icon-font glyphs, images
  const icons = [];
  let iconN = 0;
  for (const el of document.querySelectorAll('svg')) {
    if (!visible(el) || !isIconSvg(el) || el.parentElement.closest('svg')) continue;
    const b = el.getBoundingClientRect();
    if (occluded(el, b)) continue;
    const cs = getComputedStyle(el);
    const color = toRGB(cs.color);
    addColor(color, 'icon');
    const o = { match: null, kind: 'svg', owner: ownerOf(el), bbox: box(b), color, file: `icons/i${iconN++}.svg`,
                svg: el.outerHTML.replace(/\s(class|style|data-[\w-]+|aria-[\w-]+)="[^"]*"/g, '') };
    const sw = el.getAttribute('stroke-width') || cs.strokeWidth;
    if (el.getAttribute('stroke') && el.getAttribute('stroke') !== 'none') o.strokeWidth = parseFloat(cs.strokeWidth) || parseFloat(sw);
    o.filled = el.getAttribute('fill') === 'currentColor';
    icons.push(o);
  }
  for (const el of document.querySelectorAll('i, span')) {
    if (!visible(el) || el.children.length) continue;
    const cs = getComputedStyle(el);
    const t = el.textContent.trim();
    const cp = t.codePointAt(0);
    if (!t || [...t].length !== 1 || !(cp >= 0xE000 && cp <= 0xF8FF) && !/icon|awesome|symbols|material/i.test(cs.fontFamily)) continue;
    const color = toRGB(cs.color);
    addColor(color, 'icon');
    icons.push({ match: null, kind: 'font-glyph', owner: ownerOf(el), bbox: box(el.getBoundingClientRect()), color,
                 codepoint: 'U+' + cp.toString(16).toUpperCase(), font: { family: firstFamily(cs.fontFamily), px: px(cs.fontSize), weight: parseInt(cs.fontWeight, 10) } });
  }
  for (const el of document.querySelectorAll('img')) {
    if (!visible(el)) continue;
    icons.push({ match: null, kind: 'raster', owner: ownerOf(el), bbox: box(el.getBoundingClientRect()), src: el.currentSrc || el.src,
                 natural: [el.naturalWidth, el.naturalHeight] });
  }

  const cu = Object.entries(colorsUsed).sort((a, b) => b[1].count - a[1].count).map(([c, v]) => ({ color: c, count: v.count, where: [...v.where] }));
  const loaded = [...document.fonts].map(f => ({ family: f.family.replace(/^["']|["']$/g, ''), weight: f.weight, style: f.style, status: f.status }));
  return { lang, title: document.title || null, rawTokens, fontFaces, loaded, unreadableSheets, nodes, text, icons, colorsUsed: cu };
}
