/* ============================================================================
   Worldscape scenery v8 — the finalized fantasy (realistic digital painting).
   Region order (world z, camera flies +z → −z):
     SNOW PEAKS (z 250…40) → LIVING FOREST (−60…−240) → NIGHT METROPOLIS
     (−250…−370) → BEACH SHORE (−370…−450) → OPEN SEA (< −450) → the genie.
   Craft rules: the camera flies LOW so the world towers (v7's flaw was a high
   camera over small trees = flat green); regions blend via overlapping
   smoothsteps so every transition is a diffusion, never a cut; variation over
   repetition; instancing for anything > ~10.
   ========================================================================== */

import * as THREE from 'three';

/* ------------------------------------------------------------------ noise */
function hash(x, z) { const s = Math.sin(x * 127.1 + z * 311.7) * 43758.5453; return s - Math.floor(s); }
function noise(x, z) {
  const xi = Math.floor(x), zi = Math.floor(z), xf = x - xi, zf = z - zi;
  const u = xf * xf * (3 - 2 * xf), v = zf * zf * (3 - 2 * zf);
  const a = hash(xi, zi), b = hash(xi + 1, zi), c = hash(xi, zi + 1), d = hash(xi + 1, zi + 1);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}
export function fbm(x, z) {
  let f = 0, amp = 0.5, fr = 1;
  for (let i = 0; i < 4; i++) { f += amp * noise(x * fr, z * fr); amp *= 0.5; fr *= 2; }
  return f;
}
const S = THREE.MathUtils.smoothstep;

/* The one height function. A flight corridor is carved near x=0 through the
   peaks so the camera weaves BETWEEN summits instead of floating above them. */
export function ground(x, z) {
  let h = fbm(x * 0.012 + 7, z * 0.012 + 3) * 22
        + Math.max(0, fbm(x * 0.004, z * 0.004) - 0.5) * 40;
  const snowK = S(z, -40, 40);                                  // full snow for z ≥ 40
  h += snowK * (26 + fbm(x * 0.018 + 3, z * 0.018) * 70
        + Math.max(0, fbm(x * 0.006 + 9, z * 0.006) - 0.45) * 95);
  h -= snowK * Math.exp(-(x * x) / (2 * 38 * 38)) * 52;          // the corridor
  const cityK = S(z, -250, -290) * (1 - S(z, -360, -395));
  h = h * (1 - cityK) + 1.6 * cityK;                             // the city plain
  const beachK = S(z, -365, -432);
  h = h * (1 - beachK) + 1.0 * beachK;                           // land melts to sand
  return Math.max(0.4, h);
}
export const snowAmount = (z) => S(z, -40, 40);

export const C = {
  ink: 0x151735, inkHi: 0x2b3060, gold: 0xf0b95e, ember: 0xe0834a,
  teal: 0x5fd4c8, snow: 0xfff5e6, ice: 0xcfe2f4, leaf: 0x3f9d7a,
  leafDeep: 0x27775e, moss: 0x557a4a, sea: 0x1f6d8c, wood: 0x6e4a32,
  sand: 0xeacf9d, fur: 0x8a5a3a, spirit: 0x7fd8cf,
};
export const flat = (color, extra) => new THREE.MeshStandardMaterial(
  Object.assign({ color, flatShading: true, roughness: 0.9, metalness: 0 }, extra));

export function radialTexture(inner, outer) {
  const cv = document.createElement('canvas'); cv.width = cv.height = 128;
  const ctx = cv.getContext('2d');
  const rg = ctx.createRadialGradient(64, 64, 6, 64, 64, 62);
  rg.addColorStop(0, inner); rg.addColorStop(1, outer);
  ctx.fillStyle = rg; ctx.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(cv);
}

/* ---------------------------------------------------------------- terrain */
export function terrain() {
  const geo = new THREE.PlaneGeometry(680, 860, 130, 160);
  geo.rotateX(-Math.PI / 2);
  const pos = geo.attributes.position, colors = [], col = new THREE.Color();
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), z = pos.getZ(i) - 120;               // mesh centered z=-120
    const h = ground(x, z);
    pos.setY(i, h);
    const sK = snowAmount(z);
    if (sK > 0.45) col.setHex(h > 14 ? C.snow : C.ice).lerp(new THREE.Color(C.inkHi), h > 34 ? 0 : 0.15);
    else if (z < -360 && h < 6) col.setHex(C.sand);
    else if (h > 26) col.setHex(C.inkHi);
    else if (h > 4) {                                            // painted forest floor
      col.setHex(C.leafDeep)
        .lerp(new THREE.Color(C.moss), hash(x, z) * 0.7)
        .lerp(new THREE.Color(C.leaf), hash(z, x) * 0.35);
    } else col.setHex(C.teal).lerp(new THREE.Color(C.ink), 0.5);
    colors.push(col.r, col.g, col.b);
  }
  geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  geo.computeVertexNormals();
  const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
    vertexColors: true, flatShading: true, roughness: 0.95 }));
  m.position.set(0, 0, -120);
  return m;
}
export function ocean() {
  const geo = new THREE.PlaneGeometry(1100, 520, 44, 24);
  geo.rotateX(-Math.PI / 2);
  const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
    color: C.sea, transparent: true, opacity: 0.92, roughness: 0.3,
    metalness: 0.35, flatShading: true, side: THREE.DoubleSide }));
  m.position.set(0, 0.7, -640);
  m.userData.base = Float32Array.from(geo.attributes.position.array);
  return m;
}
/* Surf: two soft foam bands breathing against the sand. */
export function foam() {
  const g = new THREE.Group();
  for (let i = 0; i < 2; i++) {
    const band = new THREE.Mesh(new THREE.PlaneGeometry(300, 3.2 - i),
      new THREE.MeshBasicMaterial({ color: 0xfdf6ea, transparent: true,
        opacity: 0.32 - i * 0.1, depthWrite: false }));
    band.rotation.x = -Math.PI / 2;
    band.position.set(0, 1.15, -434 - i * 6);
    band.userData.ph = i * 2.1;
    g.add(band);
  }
  return g;
}

/* ------------------------------------------------ the living forest ------ */
/* Tall, lush, close to the camera — the world should tower, not carpet. */
export function forest(count) {
  const g = new THREE.Group();
  const species = [
    { geo: mergeCones([[3.2, 7, 0], [2.4, 5.6, 3.4], [1.5, 4.2, 6.6]]), share: 0.4 },
    { geo: canopyGeo(), share: 0.42 },
    { geo: mergeCones([[4.2, 11, 0], [3.0, 8.5, 5.5], [1.8, 6, 10.5]]), share: 0.18, big: 1.7 },
  ];
  const col = new THREE.Color(), M = new THREE.Matrix4(), q = new THREE.Quaternion(),
    s = new THREE.Vector3(), e = new THREE.Euler();
  species.forEach((sp) => {
    const n = Math.round(count * sp.share);
    const mesh = new THREE.InstancedMesh(sp.geo, flat(0xffffff), n);
    let placed = 0, guard = 0;
    while (placed < n && guard++ < n * 25) {
      // Hug the flight corridor so trees fill the frame: |x| ≤ 110, weighted inward.
      const x = (Math.random() - 0.5) * 220 * (0.35 + Math.random() * 0.65);
      const z = -65 - Math.random() * 175;
      if (fbm(x * 0.03 + 40, z * 0.03) > 0.64) continue;         // clearings for the deer
      const h = ground(x, z);
      if (h < 3 || h > 26) continue;
      const k = (1.5 + Math.random() * 1.9) * (sp.big || 1);     // TALL — v7 was half this
      s.set(k * (0.85 + Math.random() * 0.3), k * (0.85 + Math.random() * 0.5), k * (0.85 + Math.random() * 0.3));
      e.set(0, Math.random() * Math.PI * 2, (Math.random() - 0.5) * 0.05);
      q.setFromEuler(e);
      M.compose(new THREE.Vector3(x, h, z), q, s);
      mesh.setMatrixAt(placed, M);
      col.setHex(C.leafDeep).lerp(
        new THREE.Color(Math.random() < 0.5 ? C.leaf : C.teal), Math.random() * 0.5);
      mesh.setColorAt(placed, col);
      placed++;
    }
    mesh.count = placed;
    g.add(mesh);
  });
  return g;
}
function mergeCones(list) {
  const geos = list.map(([r, h, y]) => {
    const c = new THREE.ConeGeometry(r, h, 7);
    c.translate(0, y + h / 2 + 0.8, 0);
    return c;
  });
  return mergeGeos(geos);
}
function canopyGeo() {
  const trunk = new THREE.CylinderGeometry(0.4, 0.65, 3.4, 5);
  trunk.translate(0, 1.7, 0);
  const c1 = new THREE.IcosahedronGeometry(3.1, 1); c1.scale(1, 0.85, 1); c1.translate(0, 5.4, 0);
  const c2 = new THREE.IcosahedronGeometry(2.0, 1); c2.scale(1, 0.8, 1); c2.translate(2, 4.4, 0.7);
  const c3 = new THREE.IcosahedronGeometry(1.7, 1); c3.scale(1, 0.8, 1); c3.translate(-1.7, 4.6, -0.6);
  return mergeGeos([trunk, c1, c2, c3]);
}
function mergeGeos(geos) {
  let total = 0;
  const parts = geos.map((g) => { const n = g.toNonIndexed(); total += n.attributes.position.count; return n; });
  const pos = new Float32Array(total * 3), norm = new Float32Array(total * 3);
  let o = 0;
  parts.forEach((p) => {
    pos.set(p.attributes.position.array, o * 3);
    norm.set(p.attributes.normal.array, o * 3);
    o += p.attributes.position.count;
  });
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('normal', new THREE.BufferAttribute(norm, 3));
  return geo;
}
/* Deer in the clearings — quiet life discovered, not displayed. */
export function deer(spots) {
  const g = new THREE.Group();
  spots.forEach(([x, z], i) => {
    const one = new THREE.Group();
    const mat = flat(C.fur, { roughness: 1 });
    const body = new THREE.Mesh(new THREE.SphereGeometry(1.1, 8, 6), mat);
    body.scale.set(1.6, 1, 0.8); body.position.y = 1.6;
    const headG = new THREE.Group();
    const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.36, 1.5, 5), mat);
    neck.position.set(1.55, 2.5, 0); neck.rotation.z = -0.5;
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.5, 7, 6), mat);
    head.scale.set(1.35, 0.85, 0.8); head.position.set(2.15, 3.05, 0);
    headG.add(neck, head);
    one.add(body, headG);
    for (let l = 0; l < 4; l++) {
      const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.11, 1.7, 4), mat);
      leg.position.set((l % 2 ? 0.9 : -0.9), 0.85, (l < 2 ? 0.45 : -0.45));
      one.add(leg);
    }
    const h = ground(x, z);
    one.position.set(x, h, z);
    one.rotation.y = Math.random() * Math.PI * 2;
    one.userData = { headG, ph: i * 1.9 };
    g.add(one);
  });
  return g;
}
export function glowPlants(n, tex) {
  const pts = [], colors = [];
  const cA = new THREE.Color(0x9fe8dc), cB = new THREE.Color(0xf0b95e);
  for (let i = 0; i < n; i++) {
    const x = (Math.random() - 0.5) * 200, z = -70 - Math.random() * 165;
    pts.push(x, ground(x, z) + 0.6 + Math.random() * 1.2, z);
    const c = Math.random() < 0.7 ? cA : cB;
    colors.push(c.r, c.g, c.b);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  return new THREE.Points(geo, new THREE.PointsMaterial({
    vertexColors: true, size: 1.1, map: tex, transparent: true, opacity: 0.7,
    blending: THREE.AdditiveBlending, depthWrite: false }));
}

/* ------------------------------------------------------- the snow start -- */
export function snowfall(n) {
  const pts = [];
  for (let i = 0; i < n; i++)
    pts.push((Math.random() - 0.5) * 320, 20 + Math.random() * 90, 20 + Math.random() * 230);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  const p = new THREE.Points(geo, new THREE.PointsMaterial({
    color: 0xffffff, size: 0.9, transparent: true, opacity: 0, depthWrite: false }));
  p.userData.base = Float32Array.from(pts);
  return p;
}
export function trekkers(n) {
  const g = new THREE.Group();
  const mat = new THREE.MeshBasicMaterial({ color: 0x10122a });
  const packMat = new THREE.MeshBasicMaterial({ color: 0xc2513f });
  for (let i = 0; i < n; i++) {
    const one = new THREE.Group();
    const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.28, 0.9, 2, 5), mat);
    const pack = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.5, 0.22), packMat);
    pack.position.set(0, 0.15, -0.3);
    one.add(body, pack);
    one.userData.off = i * 0.09;
    g.add(one);
  }
  return g;
}
export const TRAIL = new THREE.CatmullRomCurve3(
  [[-58, 150], [-24, 144], [8, 154], [42, 146], [76, 156]].map(([x, z]) =>
    new THREE.Vector3(x, ground(x, z) + 0.8, z)));

/* --------------------------------------------- the dream metropolis ------ */
function windowTexture() {
  const cv = document.createElement('canvas'); cv.width = 64; cv.height = 128;
  const ctx = cv.getContext('2d');
  ctx.fillStyle = '#0c0e22'; ctx.fillRect(0, 0, 64, 128);
  for (let y = 6; y < 122; y += 9) for (let x = 6; x < 58; x += 10) {
    if (Math.random() < 0.55) {
      ctx.fillStyle = Math.random() < 0.8 ? 'rgba(240,185,94,.9)' : 'rgba(120,220,210,.9)';
      ctx.fillRect(x, y, 5, 4);
    }
  }
  const t = new THREE.CanvasTexture(cv);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}
export function city(nTowers) {
  const g = new THREE.Group();
  const mat = new THREE.MeshStandardMaterial({
    color: 0x1a1d3d, flatShading: true, roughness: 0.7,
    emissive: 0xffffff, emissiveMap: windowTexture(), emissiveIntensity: 0.9 });
  const towers = new THREE.InstancedMesh(new THREE.BoxGeometry(6, 1, 6), mat, nTowers);
  const M = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3();
  const col = new THREE.Color();
  let placed = 0, guard = 0;
  while (placed < nTowers && guard++ < nTowers * 20) {
    const x = (Math.random() - 0.5) * 260, z = -262 - Math.random() * 95;
    if (Math.abs(x) < 9 && placed % 3) continue;                 // the avenue we fly down
    const h = 10 + Math.pow(Math.random(), 2.2) * 58;
    s.set(0.7 + Math.random() * 1.1, h, 0.7 + Math.random() * 1.1);
    M.compose(new THREE.Vector3(x, ground(x, z) + h / 2, z), q, s);
    towers.setMatrixAt(placed, M);
    col.setHSL(0.62 + Math.random() * 0.1, 0.35, 0.16 + Math.random() * 0.1);
    towers.setColorAt(placed, col);
    placed++;
  }
  towers.count = placed;
  g.add(towers);
  const glowTex = radialTexture('rgba(240,185,94,.9)', 'rgba(240,185,94,0)');
  [[-40, 82, -300], [22, 96, -330], [70, 70, -285]].forEach(([x, h, z]) => {
    const spire = new THREE.Mesh(new THREE.CylinderGeometry(1.4, 3.2, h, 6), mat);
    spire.position.set(x, ground(x, z) + h / 2, z);
    const beacon = new THREE.Sprite(new THREE.SpriteMaterial({
      map: glowTex, transparent: true, opacity: 0.85,
      blending: THREE.AdditiveBlending, depthWrite: false }));
    beacon.scale.setScalar(14);
    beacon.position.set(x, ground(x, z) + h + 4, z);
    g.add(spire, beacon);
  });
  const haze = new THREE.Sprite(new THREE.SpriteMaterial({
    map: radialTexture('rgba(240,185,94,.28)', 'rgba(140,120,255,0)'),
    transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
  haze.scale.set(330, 115, 1);
  haze.position.set(0, 42, -312);
  g.add(haze);
  return g;
}
export function trams(n, tex) {
  const g = new THREE.Group();
  for (let i = 0; i < n; i++) {
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({
      map: tex, transparent: true, opacity: 0.9,
      blending: THREE.AdditiveBlending, depthWrite: false,
      color: i % 3 ? 0xf0b95e : 0x7ddcd2 }));
    sp.scale.setScalar(2.6);
    sp.userData = { lane: 26 + (i % 3) * 14, speed: 6 + Math.random() * 6,
      off: Math.random() * 400, dir: i % 2 ? 1 : -1 };
    g.add(sp);
  }
  return g;
}

/* ----------------------------------------------------- the beach ---------- */
export function palm() {
  const g = new THREE.Group();
  const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.6, 9, 5), flat(C.wood));
  trunk.rotation.z = 0.18; trunk.position.y = 4.5;
  g.add(trunk);
  for (let i = 0; i < 6; i++) {
    const leaf = new THREE.Mesh(new THREE.PlaneGeometry(6.5, 1.6),
      flat(C.leaf, { side: THREE.DoubleSide }));
    leaf.position.set(0.9, 9, 0);
    leaf.rotation.set(-0.5 + Math.random() * 0.2, (i / 6) * Math.PI * 2, 0.5);
    g.add(leaf);
  }
  return g;
}

/* --------------------------------------------------------- the genie ----- */
/* The traveler's genie: a luminous spirit rising from the sea — welcoming
   arms, a swirling wisp instead of legs, gold at the waist, sparks around. */
export function genie() {
  const g = new THREE.Group();
  const skin = new THREE.MeshStandardMaterial({
    color: C.spirit, emissive: 0x2fb3a5, emissiveIntensity: 0.65,
    flatShading: true, roughness: 0.5 });
  const tail = new THREE.Mesh(new THREE.ConeGeometry(1.5, 6, 8), new THREE.MeshBasicMaterial({
    color: C.teal, transparent: true, opacity: 0.75 }));
  tail.rotation.x = Math.PI; tail.position.y = -3.4;
  const torso = new THREE.Mesh(new THREE.SphereGeometry(1.5, 10, 8), skin);
  torso.scale.set(1, 1.25, 0.85);
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.82, 10, 8), skin);
  head.position.y = 2.35;
  const sash = new THREE.Mesh(new THREE.TorusGeometry(1.35, 0.28, 6, 14), flat(C.gold));
  sash.rotation.x = Math.PI / 2; sash.position.y = -1.15;
  const armL = new THREE.Mesh(new THREE.CapsuleGeometry(0.3, 1.6, 2, 6), skin);
  armL.position.set(-1.7, 1.0, 0.3); armL.rotation.z = 0.9;      // arms open in welcome
  const armR = armL.clone(); armR.position.x = 1.7; armR.rotation.z = -0.9;
  const aura = new THREE.Sprite(new THREE.SpriteMaterial({
    map: radialTexture('rgba(127,216,207,.55)', 'rgba(240,185,94,0)'),
    transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
  aura.scale.setScalar(17);
  const sparkPts = [];
  for (let i = 0; i < 10; i++) sparkPts.push(0, 0, 0);
  const sparks = new THREE.Points(new THREE.BufferGeometry()
    .setAttribute('position', new THREE.Float32BufferAttribute(sparkPts, 3)),
    new THREE.PointsMaterial({ color: C.gold, size: 0.6,
      map: radialTexture('rgba(255,222,150,1)', 'rgba(255,222,150,0)'),
      transparent: true, opacity: 0.95, blending: THREE.AdditiveBlending, depthWrite: false }));
  g.add(tail, torso, head, sash, armL, armR, aura, sparks);
  g.userData.sparks = sparks;
  return g;
}
export function bubbles(n, tex) {
  const pts = [];
  for (let i = 0; i < n; i++)
    pts.push((Math.random() - 0.5) * 16, -18 + Math.random() * 22, (Math.random() - 0.5) * 10);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  const p = new THREE.Points(geo, new THREE.PointsMaterial({
    color: 0xbfeee6, size: 0.7, map: tex, transparent: true, opacity: 0,
    blending: THREE.AdditiveBlending, depthWrite: false }));
  p.userData.base = Float32Array.from(pts);
  return p;
}

/* --------------------------------------------------------- shared life --- */
export function flyers(n, color, size) {
  const g = new THREE.Group();
  const mat = new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide });
  for (let i = 0; i < n; i++) {
    const w = new THREE.Mesh(new THREE.PlaneGeometry(size, size * 0.2), mat);
    w.position.set((i % 3) * 3 - 3, -(Math.floor(i / 3)) * 1.4, i * 0.6);
    w.userData.ph = Math.random() * Math.PI * 2;
    g.add(w);
  }
  return g;
}
export function train() {
  const g = new THREE.Group();
  const winMat = new THREE.MeshBasicMaterial({ color: C.gold });
  for (let i = 0; i < 5; i++) {
    const car = new THREE.Mesh(new THREE.BoxGeometry(6, 2.4, 2.4), flat(C.inkHi));
    car.position.x = -i * 7;
    const win = new THREE.Mesh(new THREE.BoxGeometry(4.6, 0.7, 2.5), winMat);
    win.position.set(-i * 7, 0.35, 0);
    g.add(car, win);
  }
  return g;
}
export function viaduct() {
  const g = new THREE.Group();
  const mat = flat(C.inkHi, { roughness: 1 });
  g.add(new THREE.Mesh(new THREE.BoxGeometry(220, 1.6, 4), mat));
  for (let i = -5; i <= 5; i++) {
    const pier = new THREE.Mesh(new THREE.BoxGeometry(2.4, 26, 3), mat);
    pier.position.set(i * 20, -13.5, 0);
    const arch = new THREE.Mesh(new THREE.TorusGeometry(6.5, 1.1, 6, 12, Math.PI), mat);
    arch.position.set(i * 20 + 10, -14, 0);
    g.add(pier, arch);
  }
  return g;
}
export function aurora() {
  const geo = new THREE.PlaneGeometry(460, 100, 90, 1);
  const cv = document.createElement('canvas'); cv.width = 8; cv.height = 128;
  const ctx = cv.getContext('2d');
  const lg = ctx.createLinearGradient(0, 0, 0, 128);
  lg.addColorStop(0, 'rgba(120,255,214,0)'); lg.addColorStop(0.35, 'rgba(120,255,214,.55)');
  lg.addColorStop(0.7, 'rgba(140,120,255,.35)'); lg.addColorStop(1, 'rgba(140,120,255,0)');
  ctx.fillStyle = lg; ctx.fillRect(0, 0, 8, 128);
  const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({
    map: new THREE.CanvasTexture(cv), transparent: true, opacity: 0,
    blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
  m.position.set(0, 130, -740);
  m.userData.base = Float32Array.from(geo.attributes.position.array);
  return m;
}
export function fireflies(n, tex) {
  const pts = [];
  for (let i = 0; i < n; i++)
    pts.push((Math.random() - 0.5) * 180, 8 + Math.random() * 20, -70 - Math.random() * 160);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  const p = new THREE.Points(geo, new THREE.PointsMaterial({
    color: C.gold, size: 1.6, map: tex, transparent: true, opacity: 0.85,
    blending: THREE.AdditiveBlending, depthWrite: false }));
  p.userData.base = Float32Array.from(pts);
  return p;
}
export function cloud(tex) {
  const g = new THREE.Group();
  const n = 4 + Math.floor(Math.random() * 3);
  for (let i = 0; i < n; i++) {
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({
      map: tex, transparent: true, opacity: 0.16 + Math.random() * 0.14, depthWrite: false }));
    const w = 26 + Math.random() * 34;
    sp.scale.set(w * (1.5 + Math.random() * 0.8), w * (0.4 + Math.random() * 0.25), 1);
    sp.position.set((i - n / 2) * 14 + Math.random() * 8, (Math.random() - 0.5) * 6, (Math.random() - 0.5) * 10);
    g.add(sp);
  }
  return g;
}
