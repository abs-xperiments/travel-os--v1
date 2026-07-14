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
