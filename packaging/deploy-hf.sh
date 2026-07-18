#!/usr/bin/env bash
# Deploy TripOS to Hugging Face Spaces (free Docker Space) — run from the repo root.
#
# One-time prerequisites:
#   pip install -U huggingface_hub          # provides the `hf` CLI
#   hf auth login                           # paste a WRITE token from
#                                           # https://huggingface.co/settings/tokens
#
# Then:  bash packaging/deploy-hf.sh
#
# What it does: verifies you're deploying the NEW code, creates the Space
# abs2k06/tripos if needed, pushes main to it, and prints the follow-ups
# (secrets + Google OAuth redirect). Re-running it just redeploys.
set -euo pipefail

SPACE="abs2k06/tripos"
URL="https://abs2k06-tripos.hf.space"

# Never ship the wrong code again — the tao-mvp lesson, automated.
grep -q "TripVoice" src/agent/templates/_voice_input.html \
  || { echo "✗ This checkout is OLD code (no TripVoice). Merge/checkout main first."; exit 1; }
grep -q "tripos_web" Dockerfile \
  || { echo "✗ Dockerfile doesn't serve tripos_web.py — pull latest main."; exit 1; }
echo "✓ New code verified"

hf auth whoami >/dev/null 2>&1 || { echo "✗ Not logged in: run  hf auth login"; exit 1; }

# Create the Space on first run via the Python API — stable across CLI versions
# (the `hf repo create` flags drift between releases; exist_ok makes this idempotent).
python3 -c "from huggingface_hub import create_repo; \
print(create_repo('$SPACE', repo_type='space', space_sdk='docker', exist_ok=True))"

git remote get-url space >/dev/null 2>&1 \
  || git remote add space "https://huggingface.co/spaces/$SPACE"
git push space main:main --force-with-lease 2>/dev/null || git push space main:main --force
echo "✓ Code pushed — the Space is building (watch: https://huggingface.co/spaces/$SPACE)"

cat <<EOF

NEXT (one-time, in the browser):
1. Secrets — https://huggingface.co/spaces/$SPACE/settings → Variables and secrets.
   Add each of these as a SECRET, values from your local .env:
     OPENROUTER_API_KEY, FAL_KEY, DATABASE_URL, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
     R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ACCOUNT_ID, R2_BUCKET, R2_PREFIX,
     R2_PUBLIC_BASE_URL, RESEND_API_KEY, RESEND_FROM, APP_PASSWORD, LOG_LEVEL
   Plus these two (as variables):
     APP_BASE_URL=$URL
     COOKIE_SECURE=true
2. Google OAuth — https://console.cloud.google.com/apis/credentials → your OAuth client →
   add authorized redirect URI:  $URL/auth/google/callback
3. Open $URL, hard-refresh once, and run packaging/SETUP-GUIDE.md's live QA.

Future deploys:  git push space main:main
EOF
