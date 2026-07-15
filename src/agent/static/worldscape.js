/* ============================================================================
   TripOS Worldscape v8 — the finalized fantasy flight.

   One seamless painted journey, low and close so the world towers:
   SNOW PEAKS (you weave between summits; trekkers on a ridge; a train steams
   across a snowy viaduct) —diffuses into— the LIVING FOREST (tall lush trees
   over the camera, deer in the clearings, fireflies, glowing undergrowth)
   —diffuses into— the NIGHT METROPOLIS (you fly the avenue between glowing
   towers) —diffuses into— the BEACH (palms, surf foam, you cross the shore)
   —onto the open SEA (you skim the waves, then slip under) — where the
   TRAVELER'S GENIE rises in light and sparks, and TripOS introduces itself.
   Begin lands in the chat. Bold narrative only; nothing else interrupts.

   Scenery builders live in worldscape-scenery.js. Guards unchanged:
   skip/Escape land instantly; reduced-motion / Save-Data / no-WebGL never
   mount; scroll-to-end triggers the meeting; any error yields the product.
   ========================================================================== */

import * as THREE from 'three';
import {
  C, ground, snowAmount, terrain, ocean, foam, forest, deer, glowPlants,
  snowfall, trekkers, TRAIL, city, trams, palm, genie, bubbles, flyers,
  train, viaduct, aurora, fireflies, cloud, radialTexture,
} from './worldscape-scenery.js';

const LOW = (navigator.deviceMemory || 8) < 4;

export function start(overlay, onDone) {
  const canvas = overlay.querySelector('canvas');
  const scroller = overlay.querySelector('.ws-scroll');
  const sections = Array.from(overlay.querySelectorAll('.ws-section'));
  const hint = overlay.querySelector('.ws-hint');
  const night = overlay.querySelector('.ws-night');
  const deep = overlay.querySelector('.ws-deep');
  const meetEl = overlay.querySelector('.ws-meet');

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: !LOW, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, LOW ? 1.25 : 1.6));
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x2a2450, 0.0026);
  const cam = new THREE.PerspectiveCamera(54, 1, 0.1, 1400);

  const hemi = new THREE.HemisphereLight(0xffe4b0, 0x1a1e42, 1.0);
  scene.add(hemi);
  const sun = new THREE.DirectionalLight(0xffca7a, 1.2);
  sun.position.set(-60, 45, -140); scene.add(sun);
  const sunGlow = new THREE.Sprite(new THREE.SpriteMaterial({
    map: radialTexture('rgba(255,214,140,.95)', 'rgba(255,140,60,0)'),
    transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
  sunGlow.scale.setScalar(170); sunGlow.position.set(-150, 46, -420); scene.add(sunGlow);

  /* -------------------------------------------------------- the five acts */
  scene.add(terrain());
  const sea = ocean(); scene.add(sea);
  const surf = foam(); scene.add(surf);
  scene.add(forest(LOW ? 110 : 220));
  const herd = deer([[16, -118], [21, -123], [-19, -168], [26, -196], [-9, -208]]);
  scene.add(herd);
  const softTex = radialTexture('rgba(253,246,234,.85)', 'rgba(253,246,234,0)');
  const glows = LOW ? null : glowPlants(90, softTex); if (glows) scene.add(glows);
  const snow = snowfall(LOW ? 180 : 440); scene.add(snow);
  const hikers = trekkers(5); scene.add(hikers);
  scene.add(city(LOW ? 55 : 95));
  const cabs = trams(LOW ? 3 : 7, softTex); scene.add(cabs);
  for (let i = 0; i < 8; i++) {
    const p = palm();
    const x = -80 + i * 22 + Math.random() * 10;
    const z = -398 - Math.random() * 26;
    p.position.set(x, ground(x, z), z);
    p.rotation.y = Math.random() * Math.PI * 2;
    scene.add(p);
  }
  const aur = aurora(); scene.add(aur);
  const flies = LOW ? null : fireflies(60, softTex); if (flies) scene.add(flies);
  const flock = flyers(7, C.ink, 2.6); flock.position.set(-30, 30, -100); scene.add(flock);
  const butterflies = flyers(5, C.ember, 1.1);
  butterflies.position.set(-14, 12, -140); scene.add(butterflies);
  const via = viaduct(); via.position.set(0, 24, 120); scene.add(via);
  const tr = train(); tr.position.set(60, 26.4, 120); scene.add(tr);

  const clouds = [];
  for (let i = 0; i < (LOW ? 6 : 10); i++) {
    const c = cloud(softTex);
    c.position.set((Math.random() - 0.5) * 460, 50 + Math.random() * 60, -420 + Math.random() * 640);
    c.userData.v = 0.6 + Math.random();
    clouds.push(c); scene.add(c);
  }
  const steam = [];
  for (let i = 0; i < 10; i++) {
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: softTex, transparent: true, opacity: 0, depthWrite: false }));
    sp.userData.life = -1; steam.push(sp); scene.add(sp);
  }
  const meteor = new THREE.Sprite(new THREE.SpriteMaterial({
    map: softTex, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
  meteor.scale.set(26, 1.6, 1); scene.add(meteor);
  let meteorLife = -1, nextMeteor = 8 + Math.random() * 10;

  // Beneath the waves: the traveler's genie and their sparks; a whale far off.
  const spirit = genie(); spirit.position.set(0, -34, -548); spirit.visible = false;
  scene.add(spirit);
  const spiritBubbles = bubbles(LOW ? 30 : 70, softTex);
  spiritBubbles.position.set(0, -10, -548); scene.add(spiritBubbles);
  const whale = new THREE.Mesh(new THREE.SphereGeometry(6, 10, 8),
    new THREE.MeshBasicMaterial({ color: 0x0e2038, transparent: true, opacity: 0.7 }));
  whale.scale.set(2.2, 0.8, 0.9); whale.position.set(-60, -16, -590); scene.add(whale);

  /* -------------------------- the path: low, weaving, always inside the world */
  const path = new THREE.CatmullRomCurve3([
    new THREE.Vector3(0, 46, 252),
    new THREE.Vector3(16, 38, 170),      // between the snow walls
    new THREE.Vector3(-16, 24, 84),
    new THREE.Vector3(8, 13, -32),       // trees begin to tower
    new THREE.Vector3(-11, 12, -132),    // past the deer clearings
    new THREE.Vector3(7, 15, -226),      // forest thins, city glow ahead
    new THREE.Vector3(0, 23, -300),      // down the avenue
    new THREE.Vector3(0, 12, -382),      // toward the shore
    new THREE.Vector3(0, 6, -430),       // crossing the beach
    new THREE.Vector3(0, 3.2, -478),     // skimming the waves
    new THREE.Vector3(0, -7, -525),      // beneath
  ]);
  const looks = [
    new THREE.Vector3(0, 42, 160), new THREE.Vector3(0, 26, 70),
    new THREE.Vector3(0, 14, -20), new THREE.Vector3(0, 12, -110),
    new THREE.Vector3(4, 10, -200), new THREE.Vector3(0, 18, -290),
    new THREE.Vector3(0, 12, -370), new THREE.Vector3(0, 6, -430),
    new THREE.Vector3(0, 2.5, -490), new THREE.Vector3(0, -6, -545),
  ];

  let progress = 0, target = 0, done = false, raf = 0, ready = false;
  let meeting = false, meetT = 0, steamClock = 0;

  function onScroll() {
    if (meeting) return;
    const max = scroller.scrollHeight - scroller.clientHeight;
    target = max > 0 ? scroller.scrollTop / max : 1;
    if (max - scroller.scrollTop < 4) meet();
  }
  scroller.addEventListener('scroll', onScroll, { passive: true });

  function meet() {
    if (meeting || done) return;
    meeting = true;
    target = 1;
    scroller.style.pointerEvents = 'none';
    spirit.visible = true;
    setTimeout(() => { if (meetEl) meetEl.hidden = false; }, 2400);
  }

  function resize() {
    const w = overlay.clientWidth, h = overlay.clientHeight;
    renderer.setSize(w, h, false);
    cam.aspect = w / h; cam.updateProjectionMatrix();
  }
  window.addEventListener('resize', resize);
  resize();

  const lookA = new THREE.Vector3(), pos = new THREE.Vector3(), tan = new THREE.Vector3();
  const trailP = new THREE.Vector3(), trailN = new THREE.Vector3();
  const clock = new THREE.Clock();

  function frame() {
    if (done) return;
    raf = requestAnimationFrame(frame);
    const dt = Math.min(clock.getDelta(), 0.05);
    const t = clock.elapsedTime;
    progress += (target - progress) * (1 - Math.pow(0.01, dt));

    const p = Math.min(progress, 1);
    path.getPointAt(p, pos);
    cam.position.copy(pos);
    const seg = Math.min(p * (looks.length - 1), looks.length - 1.0001);
    const i = Math.floor(seg), f = seg - i;
    lookA.lerpVectors(looks[i], looks[Math.min(i + 1, looks.length - 1)], f);
    cam.lookAt(lookA);
    path.getTangentAt(p, tan);
    cam.rotateZ(THREE.MathUtils.clamp(-tan.x * 0.35, -0.12, 0.12));
    cam.position.y += Math.sin(t * 0.9) * (meeting ? 0.12 : 0.3);
    cam.fov = 54 + Math.sin(t * 0.23) * 0.7; cam.updateProjectionMatrix();

    // One light arc, no cuts: cold alpine blue -> warm forest gold ->
    // neon night over the city -> moonlit sea. Everything lerps by position.
    const camZ = cam.position.z;
    const coldK = snowAmount(camZ);                      // cold where the snow is
    hemi.color.setHex(0xffe4b0).lerp(new THREE.Color(0xcfe4ff), coldK * 0.9);
    hemi.intensity = 1.0 + coldK * 0.18;
    const nightAmt = THREE.MathUtils.smoothstep(p, 0.40, 0.62);   // night falls at the city
    if (night) night.style.opacity = (nightAmt * 0.82).toFixed(2);
    sunGlow.material.opacity = (1 - nightAmt * 0.9) * (1 - coldK * 0.55);
    sun.intensity = 1.2 - nightAmt * 0.7;
    aur.material.opacity = Math.max(0, nightAmt - 0.35) * 1.3;
    if (aur.material.opacity > 0.01) {
      const ap = aur.geometry.attributes.position, base = aur.userData.base;
      for (let k = 0; k < ap.count; k++)
        ap.setY(k, base[k * 3 + 1] + Math.sin(t * 0.7 + base[k * 3] * 0.06) * 7
          + Math.sin(t * 0.31 + base[k * 3] * 0.021) * 10);
      ap.needsUpdate = true;
    }
    const deepK = THREE.MathUtils.smoothstep(-cam.position.y, -2, 6);
    if (deep) deep.style.opacity = (Math.max(deepK * 0.8, meeting ? 0.94 : 0)).toFixed(2);

    // Snow falls where the peaks are; flakes drift and wrap.
    const snowK = coldK;
    snow.material.opacity = snowK * 0.9;
    if (snowK > 0.02) {
      const spz = snow.geometry.attributes.position, base = snow.userData.base;
      for (let k = 0; k < spz.count; k++) {
        let y = spz.getY(k) - (6 + (k % 5)) * dt;
        if (y < 4) y = 95 + Math.random() * 10;
        spz.setY(k, y);
        spz.setX(k, base[k * 3] + Math.sin(t * 0.7 + k) * 1.4);
      }
      spz.needsUpdate = true;
    }
    hikers.children.forEach((one) => {
      const u = (t * 0.006 + one.userData.off) % 1;
      TRAIL.getPointAt(u, trailP);
      TRAIL.getPointAt(Math.min(u + 0.01, 1), trailN);
      one.position.copy(trailP);
      one.position.y += 0.55 + Math.abs(Math.sin(t * 5 + one.userData.off * 60)) * 0.06;
      one.lookAt(trailN.x, one.position.y, trailN.z);
    });
    // Deer graze: heads dip and lift on their own slow clocks.
    herd.children.forEach((one) => {
      one.userData.headG.rotation.z = Math.max(0, Math.sin(t * 0.35 + one.userData.ph)) * 0.55;
    });
    cabs.children.forEach((sp) => {
      const d = sp.userData;
      const x = ((t * d.speed + d.off) % 520) * d.dir + (d.dir > 0 ? -260 : 260);
      sp.position.set(x, d.lane, -312 + Math.sin(x * 0.02 + d.lane) * 26);
    });

    flock.children.forEach((w) => { w.scale.y = 0.4 + Math.abs(Math.sin(t * 6 + w.userData.ph)); });
    flock.position.x += 2.7 * dt; if (flock.position.x > 90) flock.position.x = -110;
    butterflies.children.forEach((w) => { w.scale.y = 0.3 + Math.abs(Math.sin(t * 9 + w.userData.ph)); });
    butterflies.position.x += Math.sin(t * 0.4) * 0.06;
    tr.position.x -= 21 * dt; if (tr.position.x < -140) tr.position.x = 150;
    steamClock += dt;
    if (steamClock > 0.24) {
      steamClock = 0;
      const sp = steam.find((s) => s.userData.life < 0);
      if (sp) { sp.userData.life = 0; sp.position.set(tr.position.x + 2, 29, 120); sp.scale.setScalar(2.5); }
    }
    steam.forEach((sp) => {
      if (sp.userData.life < 0) return;
      sp.userData.life += dt;
      const l = sp.userData.life / 2.2;
      if (l >= 1) { sp.userData.life = -1; sp.material.opacity = 0; return; }
      sp.position.y += 5.5 * dt; sp.position.x += 2.5 * dt;
      sp.scale.setScalar(2.5 + l * 9);
      sp.material.opacity = 0.5 * (1 - l);
    });
    nextMeteor -= dt;
    if (nextMeteor <= 0 && meteorLife < 0 && nightAmt > 0.3) {
      meteorLife = 0;
      meteor.position.set(60 + Math.random() * 80, 150 + Math.random() * 30, -600);
      meteor.material.rotation = -0.5;
    }
    if (meteorLife >= 0) {
      meteorLife += dt;
      const l = meteorLife / 0.9;
      if (l >= 1) { meteorLife = -1; meteor.material.opacity = 0; nextMeteor = 9 + Math.random() * 14; }
      else { meteor.position.x -= 150 * dt; meteor.position.y -= 70 * dt;
        meteor.material.opacity = Math.sin(l * Math.PI) * 0.9; }
    }
    if (flies) {
      flies.material.opacity = (0.25 + nightAmt * 0.55) * (0.6 + 0.4 * Math.abs(Math.sin(t * 0.9)));
      const fp = flies.geometry.attributes.position, base = flies.userData.base;
      for (let k = 0; k < fp.count; k++) {
        fp.setX(k, base[k * 3] + Math.sin(t * 0.6 + k) * 1.6);
        fp.setY(k, base[k * 3 + 1] + Math.sin(t * 0.8 + k * 2.1) * 1.1);
      }
      fp.needsUpdate = true;
    }
    if (glows) glows.material.opacity = 0.35 + 0.4 * Math.abs(Math.sin(t * 0.5));
    const wp = sea.geometry.attributes.position, wb = sea.userData.base;
    for (let k = 0; k < wp.count; k += 2)
      wp.setY(k, wb[k * 3 + 1] + Math.sin(t * 0.7 + wb[k * 3] * 0.2 + wb[k * 3 + 2] * 0.09) * 0.8);
    wp.needsUpdate = true;
    surf.children.forEach((band) => {                      // the tide breathes
      band.position.z = -434 - band.userData.ph * 3 + Math.sin(t * 0.5 + band.userData.ph) * 2.4;
      band.material.opacity = 0.18 + 0.16 * Math.abs(Math.sin(t * 0.5 + band.userData.ph));
    });
    clouds.forEach((c) => { c.position.x += c.userData.v * 1.6 * dt; if (c.position.x > 280) c.position.x = -280; });
    whale.position.x += 1.6 * dt; if (whale.position.x > 80) whale.position.x = -120;
    whale.position.y = -16 + Math.sin(t * 0.3) * 1.5;

    // The meeting: the genie rises in light, arms open, sparks orbiting.
    if (meeting) {
      meetT += dt;
      const rise = THREE.MathUtils.smoothstep(meetT, 0.2, 3.0);
      spirit.position.y = -34 + rise * 24.5;               // up to just below the gaze
      spirit.rotation.y = Math.sin(t * 0.4) * 0.22;
      spirit.position.x = Math.sin(t * 0.5) * 0.5;
      const sp = spirit.userData.sparks.geometry.attributes.position;
      for (let k = 0; k < sp.count; k++) {
        const a = t * 0.9 + (k / sp.count) * Math.PI * 2;
        sp.setXYZ(k, Math.cos(a) * 3.4, Math.sin(t * 0.7 + k) * 2.6, Math.sin(a) * 3.4);
      }
      sp.needsUpdate = true;
      spiritBubbles.material.opacity = Math.min(meetT * 0.6, 0.8) * (1 - rise * 0.3);
      const bp = spiritBubbles.geometry.attributes.position, bb = spiritBubbles.userData.base;
      for (let k = 0; k < bp.count; k++) {
        let y = bp.getY(k) + (3 + (k % 4)) * dt;
        if (y > 6) y = -18;
        bp.setY(k, y);
        bp.setX(k, bb[k * 3] + Math.sin(t * 1.2 + k) * 0.5);
      }
      bp.needsUpdate = true;
    }

    // Bold narrative only — chapters surface at their own coordinates.
    sections.forEach((s) => {
      const center = parseFloat(s.dataset.at || '0');
      const d = Math.abs(progress - center);
      const o = meeting ? 0 : Math.max(0, 1 - d * 6.5);
      s.style.opacity = o.toFixed(3);
      s.style.transform = 'translateY(calc(-50% + ' + ((progress - center) * -260).toFixed(1) + 'px))';
      s.classList.toggle('ws-near', o > 0.55);
    });
    if (hint) hint.style.opacity = progress < 0.04 ? 1 : 0;

    renderer.render(scene, cam);
    if (!ready) { ready = true; overlay.classList.add('ws-ready'); }
  }
  frame();

  function finish() {
    if (done) return;
    done = true;
    cancelAnimationFrame(raf);
    window.removeEventListener('resize', resize);
    overlay.classList.add('ws-leaving');
    setTimeout(() => { renderer.dispose(); overlay.remove(); if (onDone) onDone(); }, 750);
  }

  return { finish, meet };
}
