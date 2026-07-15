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

## Added 2026-07-15 (product-review fixes) — MUST-RUN live QA

These two behaviors can only be verified with the app running (`uv run fastapi dev
src/agent/tripos_web.py`):
1. **Bare discover → cards:** send just "discover". Expected: the interactive questionnaire
   cards appear immediately (origin, when, days, group, budget, interests — destination
   echoed as "Open to ideas"), ONE warm sentence, no questions in text. Submit → 3–5 ranked
   destination ideas built from your answers.
2. **Constrained discover unchanged:** send "where should I go for 5 days in December,
   beaches, under ₹40k". Expected: immediate ideas, NO questionnaire.
3. **Profile menu:** open it on a trip with a long itinerary — it must sit above every
   message and the sticky day navigator; Escape closes it.
4. **Reading comfort:** while a long plan streams, scroll UP — the view must stay where you
   put it (no yanking); scroll back down and it resumes following.
5. **Chapters:** click a day heading in the journal — it folds smoothly; print preview
   always shows every chapter unfolded.

## Added 2026-07-15 (Tap-In v2) — MUST-RUN live QA additions

6. **Destination-only → cards:** send just "Switzerland". Expected: the questionnaire cards
   appear immediately, destination echoed in the header, ZERO questions in text.
7. **Known prefs never re-asked:** send "Switzerland with my wife in August, we love
   trains". Expected: the cards skip who's-travelling and when; the header echoes them.
8. **Dates → days:** pick From/To dates in the card — "How many days?" fills itself and
   re-updates when you change either date; the calendar icon is clearly visible.
9. **Anything else + mic:** type or dictate an extra preference ("we're celebrating our
   anniversary") — after submit, the built plan should visibly honor it.
10. **Linked recommendations:** in a built plan or "best homestays in Munnar" ask, every
    stay/eatery name opens a Google search for it in a new tab.
11. **Multi-destination PDF:** plan Kerala fully, then say "actually plan Bali instead" and
    finish; Download PDF → ONLY Bali. Then in a new trip plan two different full
    itineraries → PDF contains both with "Journey 1 of 2 / 2 of 2" dividers.

## Added 2026-07-15 (bug-fix round) — re-verify these two

12. **Extras dictation:** in any questionnaire, tap "🎤 Speak" and say a full sentence with
    pauses ("I want the trip… to be extremely good"). Expected: the sentence appears ONCE,
    live, with a "● Listening… tap to stop" state; tapping again (or tapping into the text,
    or submitting) stops it. Repeat on your phone — mobile engines are where the old bug
    lived.
13. **Calendar glyph:** the From/To date fields show a clearly visible calendar icon on a
    soft gold chip (hover brightens it). If you still see nothing: hard-refresh once —
    the service worker serves the previous CSS for exactly one visit after a deploy.

## Added 2026-07-16 (World v8, FINAL) — the finalized fantasy, review checklist

Open `packaging/preview-worldscape.html` and scroll SLOWLY:
1. You start LOW between snow walls — peaks tower on both sides, snow falls, trekkers walk
   a ridge, the train steams across a snowy viaduct. Cold blue light.
2. The snow diffuses into the living forest — trees tower OVER you (no flat green!), deer
   graze in the clearings (watch their heads dip), fireflies and glowing plants at dusk.
3. The forest thins into the night metropolis — you fly straight down the avenue between
   glowing towers; trams glide overhead; night has fallen seamlessly.
4. The city gives way to the shore — palms, sand, two foam lines breathing on the beach.
5. You skim the waves, slip beneath — and the traveler's genie rises in light and sparks;
   "Hi, I'm TripOS…"; Begin lands in the chat.
6. Every transition should feel like a diffusion — if any seam feels like a cut, tell me
   which one. Skip/Escape land instantly from anywhere.

Also verify (URL policy, live app): ask for a Manali plan mentioning Rohtang — the permit
text must link to a Google search ("Rohtang Pass permit official"), never an invented
domain; every stay/eatery name opens a Google search in a new tab.

