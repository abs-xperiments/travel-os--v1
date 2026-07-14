# TravelOS — Manual Steps Guide (the only things I can't do from the sandbox)

*Packaging Studio · 2026-07-15. Everything else was done autonomously; these four steps need
your hands because they touch your Mac's git state, your live services, and your Railway account.*

## Step 1 — Commit the work (2 minutes)

The Cowork sandbox can't delete files in your folder, so a stale git lock file blocks
commits from my side. On your Mac:

```bash
cd ~/travel\ os/travel-os--v1
bash packaging/commit-phases.sh
```

This clears the lock, switches to the `packaging/premium-experience` branch, and lands
clean, phase-scoped commits. Nothing is pushed until you say so.

## Step 2 — Live QA run (10 minutes)

The sandbox can't run the app (your `.venv` is macOS-built, and the app connects to the
production Neon DB on startup). Run it locally:

```bash
uv run fastapi dev src/agent/tripos_web.py
```

Then check, in order:
1. Open http://localhost:8000 — you should get the train splash, then the golden-hour
   world (sky matches your local time; try `document.documentElement.dataset.sky='night'`
   in DevTools console to preview other skies).
2. Sign in and plan a real trip (e.g. "Plan 5 days in Kerala"). Verify: journey-checkpoint
   progress notes → streamed reply → **the journal reveal** (cover, day chapters, day
   navigator) once the itinerary finishes.
3. The questionnaire: ask something vague ("plan me a trip") and confirm the chips/form
   still work and compose into a message.
4. Click **Download PDF** (header or journal footer) → print preview should show the formal
   document with ONLY the final itinerary, no chat. Check page breaks look clean.
5. Narrow the window to phone width — day navigator should stick, nothing overflows.
6. DevTools → Rendering → "Emulate prefers-reduced-motion" — world should still, app
   should stay fully usable.

If anything looks off, tell me what you saw — I'll fix it before deploy.

## Step 3 — Deploy (5 minutes)

Railway CLI is authenticated on your machine, not mine:

```bash
git push -u origin packaging/premium-experience   # or merge to main first, your call
railway up
railway logs    # watch for a clean boot
```

No new environment variables are needed — this release is presentation-only.
Note for installed-PWA users: the service worker was bumped to `tripos-v2`, so the new
design arrives on their second visit after deploy (that's expected stale-while-revalidate
behavior).

## Step 4 — Hand me the keys for production verification (1 minute)

Once deployed, paste me the production URL in chat. With your Claude-in-Chrome extension
I'll walk the live site end-to-end (visual inspection, responsive checks, console errors,
and the Lighthouse/axe passes that complete Phase 8's QA gates) and report honestly.

## Deferred by decision (no action needed)

- **Sound system** — shipping synthesized ambience would cheapen the brand; when you want
  it, we'll source real recordings (wind/birds/station) and I'll build the opt-in player.
- **WebGL world v2** — the CSS world hits the bar for launch; Three.js-via-CDN is scoped
  in ROADMAP Phase 7 when you want more depth.
- **OG/social share image** — worth a designed 1200×630 asset before public launch; I can
  generate candidates with an image model whenever you want to pick one.
- **Structured itinerary output + shareable trip pages** — both need logic changes; parked
  as ROADMAP "standing suggestions" until you explicitly approve.
