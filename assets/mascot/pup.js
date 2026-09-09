/* research-council mascot. Original pixel design, drawn from code on a 64x48 grid.
 *
 * One file, two homes:
 *   browser  <script src="pup.js">  ->  window.Pup
 *   node     node assets/mascot/pup.js --frames  ->  JSON on stdout (scripts/mascot_gif.py reads it)
 *
 * Nothing here touches the DOM. Every frame is a grid of palette indices; index 0 is the
 * background. Randomness is seeded, so the same frame number always draws the same pixels.
 */
(function (root) {
  'use strict';
  const W = 64, H = 48, GROUND = 38;
  const PALETTE = {
    bg: '#212226', line: '#17171b', white: '#f7f5ef', shade: '#d7d3c6', shadeD: '#b9b4a5',
    dirt: '#7d5236', dirtD: '#4a2e1d', dirtL: '#9c6a45', bone: '#f2e8cd', boneD: '#cfc09a',
    pink: '#e8798f', star: '#ffd15c', paper: '#efece2', rule: '#a9a49a', collar: '#f0a83a'
  };
  const NAMES = Object.keys(PALETTE);
  const C = {}; NAMES.forEach((n, i) => { C[n] = i; });

  /* ---------- seeded random (mulberry32) ---------- */
  let seed = 1;
  function rnd() {
    seed |= 0; seed = seed + 0x6D2B79F5 | 0;
    let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  }

  /* ---------- pixel helpers ---------- */
  const grid = () => Array.from({ length: H }, () => new Array(W).fill(0));
  function px(g, x, y, c) { x = Math.round(x); y = Math.round(y); if (x >= 0 && x < W && y >= 0 && y < H) g[y][x] = c; }
  function ell(g, cx, cy, rx, ry, c) {
    for (let y = Math.floor(cy - ry); y <= Math.ceil(cy + ry); y++)
      for (let x = Math.floor(cx - rx); x <= Math.ceil(cx + rx); x++) {
        const dx = (x - cx) / rx, dy = (y - cy) / ry; if (dx * dx + dy * dy <= 1) px(g, x, y, c);
      }
  }
  function rect(g, x, y, w, h, c) { for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) px(g, x + i, y + j, c); }
  /* fur: outline, white fill, then two shade bands on the lower-right so the pup reads as round */
  function fur(g, cx, cy, rx, ry) {
    ell(g, cx, cy, rx + 1, ry + 1, C.line);
    ell(g, cx, cy, rx, ry, C.white);
    const ox = cx - 1.1, oy = cy - 1.2, orx = Math.max(0.6, rx - 1.1), ory = Math.max(0.6, ry - 1.1);
    const dx2 = cx - 2.0, dy2 = cy - 2.2, drx = Math.max(0.6, rx - 1.6), dry = Math.max(0.6, ry - 1.6);
    for (let y = Math.floor(cy - ry); y <= Math.ceil(cy + ry); y++)
      for (let x = Math.floor(cx - rx); x <= Math.ceil(cx + rx); x++) {
        const dx = (x - cx) / rx, dy = (y - cy) / ry; if (dx * dx + dy * dy > 1) continue;
        const ex = (x - ox) / orx, ey = (y - oy) / ory;
        if (ex * ex + ey * ey > 1) {
          const fx = (x - dx2) / drx, fy = (y - dy2) / dry;
          px(g, x, y, fx * fx + fy * fy > 1 && y > cy ? C.shadeD : C.shade);
        }
      }
  }
  function limb(g, x, top, w, h) {
    if (h < 1) return;
    rect(g, x - 1, top - 1, w + 2, h + 2, C.line);
    rect(g, x, top, w, h, C.white); rect(g, x + w - 1, top, 1, h, C.shade); rect(g, x + w - 1, top + h - 4, 1, 2, C.shadeD);
    rect(g, x - 1, top + h - 2, w + 3, 2, C.line);
    rect(g, x, top + h - 2, w + 1, 1, C.white);
    px(g, x + 1, top + h - 1, C.line); px(g, x + 3, top + h - 1, C.line);
  }

  /* ---------- parts ---------- */
  function tail(g, bx, by, wag) {
    const pts = []; let a = 3.45 + wag * 0.22, x = bx, y = by;
    for (let k = 0; k < 9; k++) { a += 0.38; x += Math.cos(a) * 1.35; y += Math.sin(a) * 1.35; pts.push([x, y]); }
    for (const [p, q] of pts) ell(g, p, q, 2.1, 2.1, C.line);
    for (const [p, q] of pts) ell(g, p, q, 1.1, 1.1, C.white);
    for (const [p, q] of pts) px(g, p + 1, q + 1, C.shade);
  }
  function ear(g, hx, hy, a, len) {
    const seg = []; for (let k = 1; k <= 3; k++) seg.push([hx + Math.cos(a) * k * len, hy + Math.sin(a) * k * len, 3.3 - k * 0.45]);
    for (const [x, y, r] of seg) ell(g, x, y, r + 1, r + 1, C.line);
    for (const [x, y, r] of seg) { ell(g, x, y, r, r, C.white); ell(g, x + 0.6, y + 0.8, r - 1.2, r - 1.2, C.shade); ell(g, x + 1.1, y + 1.3, r - 2.0, r - 2.0, C.shadeD); }
  }
  function bone(g, cx, cy, ang) {
    const co = Math.cos(ang), si = Math.sin(ang);
    const R = (u, v) => [cx + u * co - v * si, cy + u * si + v * co];
    const knobs = [[-4, -1.7], [-4, 1.7], [4, -1.7], [4, 1.7]].map(([u, v]) => R(u, v));
    const shaft = []; for (let t = -4; t <= 4; t += 0.6) shaft.push(R(t, 0));
    for (const [x, y] of knobs) ell(g, x, y, 2.6, 2.6, C.line);
    for (const [x, y] of shaft) ell(g, x, y, 2.1, 2.1, C.line);
    for (const [x, y] of knobs) ell(g, x, y, 1.6, 1.6, C.bone);
    for (const [x, y] of shaft) ell(g, x, y, 1.1, 1.1, C.bone);
    const [sx, sy] = R(0, 0.9); ell(g, sx, sy, 1.4, 0.8, C.boneD);
  }
  function paper(g, x, y) {
    rect(g, x, y + 1, 11, 8, C.dirtD);                       // cast shadow
    rect(g, x - 1, y - 1, 11, 9, C.line); rect(g, x, y, 9, 7, C.paper);
    rect(g, x + 1, y + 1, 7, 1, C.rule); rect(g, x + 1, y + 3, 5, 1, C.rule); rect(g, x + 1, y + 5, 6, 1, C.rule);
  }
  /* 5-row pixel glyphs for the WOO! shout */
  const GLYPH = {
    W: ['X...X', 'X...X', 'X.X.X', 'X.X.X', '.X.X.'],
    O: ['XXX', 'X.X', 'X.X', 'X.X', 'XXX'],
    '!': ['X', 'X', 'X', '.', 'X']
  };
  function text(g, x, y, str) {
    for (const ch of str) {
      const rows = GLYPH[ch]; const w = rows[0].length;
      for (let j = 0; j < 5; j++) for (let i = 0; i < w; i++) if (rows[j][i] === 'X') {
        for (let oy = -1; oy <= 1; oy++) for (let ox = -1; ox <= 1; ox++) px(g, x + i + ox, y + j + oy, C.line);
      }
      for (let j = 0; j < 5; j++) for (let i = 0; i < w; i++) if (rows[j][i] === 'X') px(g, x + i, y + j, C.star);
      x += w + 1;
    }
  }

  /* ---------- dog ---------- */
  function dog(g, s) {
    const bx = s.bx, by = s.by, hx = s.hx, hy = s.hy;
    ell(g, bx + 1, GROUND + 1, 11 - s.lift * 0.5, 1.8, C.dirtD);          // contact shadow
    ell(g, hx + 2, GROUND + 1, 5, 1.2, C.dirtD);                        // head shadow
    limb(g, bx - 9, by + 1, 4, GROUND - by - 1 - s.pawB);                // back leg
    tail(g, bx - 8, by - 3, s.wag);
    ear(g, hx - 6, hy - 4, s.earA, 2.3);                                 // far ear
    fur(g, bx, by, s.brx, s.bry);                                        // body
    limb(g, bx + 2, by + 1, 4, GROUND - by - 1 - s.pawL);
    limb(g, bx + 7, by + 2, 4, GROUND - by - 2 - s.pawR);
    fur(g, hx, hy, s.hrx, s.hry);                                        // head
    ell(g, hx - 4, hy - s.hry + 1.5, 3.2, 1.1, C.shade);                 // ear cast shadow on head
    const sx = hx + Math.cos(s.snout) * (s.hrx - 1), sy = hy + Math.sin(s.snout) * (s.hry - 1);
    fur(g, sx, sy, 3.4, 2.8);                                            // snout
    const nx = sx + Math.cos(s.snout) * 2.6, ny = sy + Math.sin(s.snout) * 2.2;
    ell(g, nx, ny, 1.6, 1.3, C.line); px(g, nx - 1, ny - 1, C.shadeD);
    ell(g, hx - 1, hy + s.hry - 0.5, 4.6, 1.4, C.collar);                // collar
    px(g, hx + 3, hy + s.hry + 0.4, C.line);
    const ex1 = hx - 3, ey1 = hy - 1.5, ex2 = hx + 3.5, ey2 = hy - 0.5;   // eyes
    if (s.blink) { rect(g, ex1 - 1, ey1, 3, 1, C.line); rect(g, ex2 - 1, ey2, 3, 1, C.line); }
    else {
      ell(g, ex1, ey1, s.eye, s.eye + 0.3, C.line); ell(g, ex2, ey2, s.eye, s.eye + 0.3, C.line);
      px(g, ex1 - 1, ey1 - 1, C.white); px(g, ex2 - 1, ey2 - 1, C.white);
    }
    const mx = sx - 0.5, my = sy + 2.6;                                  // mouth
    if (s.mouth === 'open') { ell(g, mx, my, 2.6, 2.2, C.line); ell(g, mx, my + 0.6, 1.5, 1.2, C.pink); }
    else if (s.mouth === 'o') { ell(g, mx, my, 1.5, 1.6, C.line); px(g, mx, my, C.pink); }
    else { rect(g, mx - 2, my, 3, 1, C.line); px(g, mx + 1, my - 1, C.line); px(g, mx + 2, my, C.line); }
    if (s.puff) for (const p of s.puff) px(g, p[0], p[1], C.white);
  }

  /* ---------- world ---------- */
  function world(g, st) {
    rect(g, 0, GROUND, W, H - GROUND, C.dirt);
    rect(g, 0, GROUND, W, 1, C.dirtL);
    for (let x = 0; x < W; x += 3) px(g, x, GROUND + 3, C.dirtD);
    for (let x = 2; x < W; x += 7) px(g, x, GROUND + 6, C.dirtD);
    for (let x = 5; x < W; x += 9) px(g, x, GROUND + 8, C.dirtL);
    if (st.hole > 0) { ell(g, 48, GROUND, st.hole + 1.5, st.hole * 0.55 + 1, C.dirtD); rect(g, 48 - st.hole, GROUND - 1, st.hole * 2, 1, C.dirtD); }
    if (st.mound > 0) { ell(g, 58, GROUND, st.mound, st.mound * 0.5, C.dirtL); ell(g, 58, GROUND + 1, st.mound - 1, st.mound * 0.4, C.dirt); ell(g, 59, GROUND + 1, st.mound - 1.5, st.mound * 0.3, C.dirtD); }
  }

  /* ---------- particles ---------- */
  let parts = [];
  function spawnDirt() {
    for (let k = 0; k < 3; k++) parts.push({ x: 47 + rnd() * 3, y: GROUND - 1, vx: -(1.2 + rnd() * 1.9), vy: -(1.9 + rnd() * 1.6), life: 14 + rnd() * 6, c: rnd() < 0.4 ? C.dirtL : C.dirt });
  }
  function spawnDust(cx, cy, n, c) {
    for (let k = 0; k < n; k++) { const a = Math.PI + rnd() * Math.PI; parts.push({ x: cx, y: cy, vx: Math.cos(a) * (1.4 + rnd() * 1.6), vy: Math.sin(a) * (0.9 + rnd() * 1.2), life: 9 + rnd() * 6, c: c }); }
  }
  function stepParts() {
    for (const p of parts) { p.vy += 0.42; p.x += p.vx; p.y += p.vy; p.life--; if (p.y > GROUND - 0.5) { p.y = GROUND - 0.5; p.vy *= -0.32; p.vx *= 0.6; } }
    parts = parts.filter(p => p.life > 0);
  }
  function drawParts(g) { for (const p of parts) px(g, p.x, p.y, p.life < 4 ? C.dirtD : p.c); }

  /* ---------- timing ---------- */
  const eOut = t => 1 - Math.pow(1 - t, 3), eIn = t => t * t;
  const eBack = t => { const c = 2.2; return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); };
  const base = () => ({ bx: 22, by: 29, hx: 34, hy: 17, brx: 11, bry: 7, hrx: 9, hry: 8, eye: 1.4, blink: false, mouth: 'flat', snout: 0.15, earA: 1.5, wag: 0, pawL: 0, pawR: 0, pawB: 0, lift: 0, puff: null });

  let hist = [];                                   // head history for ear follow-through
  function lagAngle(fallback) {
    if (hist.length < 4) return fallback; const a = hist[hist.length - 4], b = hist[hist.length - 1];
    const dx = b[0] - a[0], dy = b[1] - a[1]; return fallback + Math.max(-0.5, Math.min(0.5, -dx * 0.10 - dy * 0.06));
  }

  const PHASES = [
    { name: 'idle', n: 20, st: { hole: 0, mound: 0 }, pose(i) {
      const s = base(); const b = Math.sin(i * 0.42);
      s.by = 29 + Math.round(b * 0.5); s.hy = 17 + Math.round(Math.sin(i * 0.42 - 0.6) * 0.9); s.bry = 7 + (b > 0.6 ? 0.4 : 0);
      s.wag = Math.sin(i * 0.85) * 1.6; s.blink = (i === 12 || i === 13); s.earA = lagAngle(1.55); return s; } },

    { name: 'sniff', n: 24, st: { hole: 0, mound: 0 }, pose(i) {
      const s = base();
      const dn = eOut(Math.min(1, i / 6)); s.hy = 17 + 11 * dn; s.hx = 34 + 5 * dn; s.snout = 0.15 + 0.55 * dn; s.by = 29 + 1.2 * dn; s.bry = 7 - 0.5 * dn;
      const sweep = i > 6 ? Math.sin((i - 6) * 0.55) : 0; s.hx += sweep * 4; s.hy += Math.abs(sweep) * -1;
      s.mouth = 'o'; s.wag = Math.sin(i * 0.7) * 1.1; s.earA = lagAngle(1.75);
      if (i > 6) s.puff = [[s.hx + 9, s.hy + 2], [s.hx + 11 + (i % 2), s.hy], [s.hx + 10, s.hy + 4 + (i % 2)]];
      s.blink = (i === 20); return s; } },

    { name: 'dig', n: 30, st: { hole: 0, mound: 0 }, pose(i, st) {
      const s = base();
      s.hx = 39; s.hy = 28; s.snout = 0.7; s.by = 30; s.bry = 6.4; s.brx = 11.4; s.mouth = 'o'; s.earA = lagAngle(2.05);
      const fast = i % 2 === 0; s.pawL = fast ? 5 : 0; s.pawR = fast ? 0 : 5; s.lift = 1;
      s.by += fast ? -0.6 : 0.4; s.wag = Math.sin(i * 1.3) * 2.2;
      if (i > 2 && i % 2 === 0) { spawnDirt(); st.hole = Math.min(6, st.hole + 0.42); st.mound = Math.min(5, st.mound + 0.34); }
      return s; } },

    { name: 'found', n: 22, st: { hole: 6, mound: 5 }, pose(i) {
      const s = base(); const t = Math.min(1, i / 7);
      s.hy = 17 - 4 * eBack(t); s.hx = 34 - 3 * t; s.by = 29 - 2 * t; s.bry = 7 + 0.8 * t; s.brx = 11 - 0.5 * t;
      s.eye = 2.1; s.mouth = 'open'; s.snout = -0.15; s.earA = lagAngle(1.15) - 0.5 * t; s.wag = Math.sin(i * 1.15) * 2.4;
      if (i === 1) spawnDust(48, GROUND - 1, 10, C.dirtL);
      s.bone = { x: 48, y: GROUND - 1 - 26 * eOut(t), a: i * 0.55 };
      s.stars = i > 4 ? [[42, 4 + (i % 2)], [55, 7 - (i % 2)], [48, 2]].filter((_, k) => (i + k) % 3 !== 0) : null;
      s.woo = i >= 3 && i < 18; return s; } },

    { name: 'drop', n: 26, st: { hole: 6, mound: 5 }, pose(i) {
      const s = base();
      s.hx = 34 + 3; s.hy = 17 + 3; s.snout = 0.45; s.mouth = 'flat'; s.earA = lagAngle(1.6); s.wag = i > 16 ? Math.sin(i * 1.1) * 2.4 : 0.4;
      const T = 13; let by, ang;
      if (i < T) { const t = i / T; by = (GROUND - 27) + (GROUND - 6 - (GROUND - 27)) * eIn(t); ang = i * 0.42; }
      else { const k = i - T; ang = 0; by = [GROUND - 6, GROUND - 8.5, GROUND - 6.5, GROUND - 7.5, GROUND - 6.5, GROUND - 7, GROUND - 6.5][Math.min(k, 6)]; }
      if (i === T) spawnDust(14, GROUND - 3, 9, C.shade);
      s.bone = { x: i < T ? 48 - 34 * eIn(i / T) : 14, y: by, a: ang };
      s.paper = [9, GROUND - 8];
      if (i > 16) { s.mouth = 'open'; s.eye = 1.8; }
      s.blink = (i === 22); return s; } }
  ];
  const TOTAL = PHASES.reduce((a, p) => a + p.n, 0);

  function compose(pose, st, shake) {
    const g = grid(); world(g, st);
    if (pose.paper) paper(g, pose.paper[0], pose.paper[1]);
    drawParts(g); dog(g, pose);
    if (pose.bone) bone(g, pose.bone.x, pose.bone.y, pose.bone.a);
    if (pose.stars) for (const [x, y] of pose.stars) { px(g, x, y, C.star); px(g, x - 1, y, C.star); px(g, x + 1, y, C.star); px(g, x, y - 1, C.star); px(g, x, y + 1, C.star); }
    if (pose.woo) text(g, 40, 3, 'WOO!');
    if (shake) { for (const row of g) { if (shake > 0) { row.pop(); row.unshift(0); } else { row.shift(); row.push(0); } } }
    return g;
  }

  /* ---------- loop: the state machine, shared by browser and node ---------- */
  function Loop() {
    this.phase = 0; this.frame = 0; this.st = { hole: 0, mound: 0 }; this.enter(0);
  }
  Loop.prototype.enter = function (i) {
    this.phase = i; this.frame = 0; parts = []; hist = []; seed = 7 + i; this.st = Object.assign({}, PHASES[i].st);
  };
  Loop.prototype.advance = function () {
    this.frame++;
    if (this.frame >= PHASES[this.phase].n) this.enter((this.phase + 1) % PHASES.length);
    stepParts();
  };
  /* Returns the composed grid for the current frame. Pose must be computed exactly once per frame
   * because dig spawns dirt as a side effect of pose(). */
  Loop.prototype.render = function () {
    const ph = PHASES[this.phase];
    const p = ph.pose(this.frame, this.st);
    hist.push([p.hx, p.hy]); if (hist.length > 8) hist.shift();
    const shake = ph.name === 'dig' && this.frame % 2 === 0 ? (this.frame % 4 === 0 ? 1 : -1) : 0;
    return { grid: compose(p, this.st, shake), phase: ph.name, frame: this.frame };
  };
  /* Standalone key frame for a phase, used by the sprite sheet. */
  function keyFrame(phaseIndex, frameIndex) {
    const keepP = parts, keepH = hist, keepS = seed;
    const lp = new Loop(); lp.enter(phaseIndex);
    let out = lp.render();
    for (let k = 0; k < frameIndex; k++) { lp.advance(); out = lp.render(); }
    parts = keepP; hist = keepH; seed = keepS;
    return out;
  }
  /* Every frame of one full cycle, deterministic. */
  function allFrames() {
    const lp = new Loop(); const out = [];
    for (let k = 0; k < TOTAL; k++) { out.push(lp.render()); lp.advance(); }
    return out;
  }
  /* Paint a grid onto a 2d canvas context at integer scale. */
  function paint(ctx, g, sc, palette) {
    palette = palette || PALETTE;
    const colors = NAMES.map(n => palette[n] || PALETTE[n]);
    ctx.imageSmoothingEnabled = false;
    ctx.fillStyle = colors[0]; ctx.fillRect(0, 0, W * sc, H * sc);
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { const c = g[y][x]; if (c) { ctx.fillStyle = colors[c]; ctx.fillRect(x * sc, y * sc, sc, sc); } }
  }

  const Pup = { W, H, GROUND, PALETTE, NAMES, PHASES, TOTAL, STEP_MS: 105, KEY: [6, 14, 9, 12, 20], Loop, keyFrame, allFrames, paint };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = Pup;
    if (typeof require !== 'undefined' && require.main === module && process.argv.includes('--frames')) {
      const frames = allFrames().map(f => ({ phase: f.phase, rows: f.grid.map(r => r.join(',')) }));
      process.stdout.write(JSON.stringify({ w: W, h: H, step_ms: 105, palette: NAMES.map(n => PALETTE[n]), frames }));
    }
  } else { root.Pup = Pup; }
})(typeof window !== 'undefined' ? window : globalThis);
