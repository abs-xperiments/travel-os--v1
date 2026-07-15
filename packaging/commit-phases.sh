#!/usr/bin/env bash
# Packaging Studio — run this on your Mac from the repo root (travel-os--v1).
# A stale .git/HEAD.lock (created when the sandbox couldn't unlink files) blocks
# committing from the Cowork sandbox; clear it and commit the delivered phases.
set -euo pipefail

rm -f .git/HEAD.lock .git/index.lock
git checkout packaging/premium-experience

git add src/agent/static/theme.css src/agent/static/journal.css src/agent/templates/
git commit -m "feat(ui): Golden Hour Atlas design system + living-world shell

Phase 3+4: OKLCH token layer, Fraunces/Inter type, glass components,
route-line + passport-stamp motifs, time-of-day sky with drifting clouds,
stars, terrain parallax and a rare passing plane (all CSS, reduced-motion
safe). Every screen reskinned; chat SSE + questionnaire behavior unchanged."

git add src/agent/static/itinerary.js
git commit -m "feat(ui): the Travel Journal — itineraries become day-chapter journals

Phase 5: finished itinerary replies transform client-side into a journal
(cover, day chapters on a route spine, sticky day nav, budget/tips spreads).
Clone-based transform: any parse failure leaves the original markdown
untouched. Planner output and SSE contract untouched."

git add src/agent/templates/print.html src/agent/static/sw.js src/agent/static/manifest.webmanifest
git commit -m "feat(export): formal A4 PDF of the final itinerary only + PWA asset freshness

Phase 6: print.html is a premium travel-agency document — cover page,
intelligent page breaks, print-safe colors. It exports ONLY the latest
reply that parses as a complete itinerary; the conversation never prints.
sw.js: tripos-v2 + stale-while-revalidate so deployed theme assets can't
go stale on installed PWAs; manifest colors match the new ink."

# Note: theme.css and chat.html Phase 7 changes are already staged in the first
# commit above (same files) — kept as one coherent design-system commit.

git add packaging/ journal.md CLAUDE.md
git commit -m "docs(packaging): phases 2-8 — strategy, decisions, phase log, audits, preview

Experience strategy + 100-idea backlog, design decisions, phase log,
WCAG contrast audit results (13/13 AA), journal entries, setup guide, and
packaging/preview.html (open locally to review the design + journal
transform on a sample itinerary)."

echo
echo "Phases 2-8 committed. Review with: git log --oneline -6"
echo "When happy:  git push -u origin packaging/premium-experience"

# World v7 — the narrative journey (supersedes v6 world files).
git add src/agent/static/worldscape.js src/agent/static/worldscape-scenery.js src/agent/static/worldscape.css src/agent/templates/chat.html packaging/ journal.md 2>/dev/null || true
git commit -m "feat(ui): the narrative journey — explore, discover, meet TripOS, plan

World v7: islands, balloon and the landing greeting bubble removed; a
handcrafted three-species forest with glowing undergrowth and clearings;
a snow-mountain chapter with tiny trekkers on a ridge trail; the dream
metropolis (instanced glowing towers, beacon spires, aerial trams)
replaces the lake; the flight dips beneath the ocean where the deep veil
becomes the planning theme's ink and a mythical diver-guide rises through
bubbles to introduce TripOS — three staged lines, one Begin button.
Engine/scenery split (316+401 lines), instancing throughout, LOW-tier
degradation; skip/Escape land instantly; scroll-to-end triggers the
meeting. No build step, zero image assets." --allow-empty


# Tap-In v2 — agent-behavior changes isolated from UI changes.
git add src/agent/agents/tripos_planner/prompt.py src/agent/agents/tripos_planner/questionnaire.py docs/scenarios.md
git commit -m "feat(agent): Tap-In everywhere — destination-only gathers via cards; meals + linked recommendations

Destination-only messages ('Switzerland') now explicitly call
request_trip_details — never text questions. Pace/accommodation options
carry one-line meanings; new 'meals' bank field shapes budget planning;
every recommended stay/restaurant name becomes a Google-search markdown
link (name+city). Scenarios added — run live before deploy."

git add src/agent/templates/ src/agent/static/theme.css
git commit -m "feat(ui)+fix(ui): exact-date range with live day count, extras + mic, PDF per destination

The When card is two date pickers (no month-only/flexible) that auto-fill
and live-update 'How many days?'; every form ends with an 'anything else'
free-text + dictation section; calendar icons visible on ink
(color-scheme + inverted indicator); avatars fall back to the initial on
load error; external links open safely in new tabs. print.html exports
the final itinerary per distinct destination with Journey dividers and
page breaks — iterations collapse, real multi-trip chats export fully."

echo "All phases committed. Review: git log --oneline -10 · push when happy."

git add src/agent/templates/_voice_input.html src/agent/templates/chat.html src/agent/static/theme.css src/agent/static/sw.js packaging/ journal.md
git commit -m "fix(ui): one dictation engine (TripVoice) + visible calendar glyph

The questionnaire's extras mic duplicated text (naive per-event appending
— the exact bug the chat mic already solved). The chat mic's transcript
architecture is now a reusable window.TripVoice engine (rebuild from the
engine's results list, cumulative merge, pause-session commits,
edit-intent stop, mute/unmute) and BOTH mics run through it; chat mic
behavior unchanged. Calendar icon: color-scheme:dark draws a light glyph
natively — the earlier invert() flipped it back to dark; filter removed,
gold chip backdrop added. SW cache bumped to tripos-v3 so stale CSS
can't mask the fixes."

git add src/agent/agents/tripos_planner/prompt.py
git commit -m "fix(agent): never invent URLs — search-links for stays, eateries and uncertain permits

A Manali plan generated a nonexistent permit domain. New hard policy:
stays/eateries always link to Google search; attractions link only when
certain (or search-link); permits/official bookings search-link to
'X permit official' unless the official URL is certain. Accuracy beats
appearing complete."

git add src/agent/static/worldscape.js src/agent/static/worldscape-scenery.js src/agent/templates/chat.html packaging/ journal.md
git commit -m "feat(ui): World v8 — the finalized fantasy flight

Snow peaks first, camera weaving LOW between summits (corridor carved in
the heightfield; trekkers + steam train live here); diffuses into a
forest of towering trees with grazing deer; into the night metropolis
down its avenue; onto a palm shore with breathing surf; skims the waves,
slips under — and the traveler's genie rises (luminous spirit, open arms,
wisp tail, orbiting sparks) to introduce TripOS. All transitions are
overlapping smoothsteps in one heightfield with position-lerped light —
diffusions, never cuts. Bold narrative chapters only."
