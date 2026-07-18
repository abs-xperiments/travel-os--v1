# Container image for deploying this project (e.g. to Railway).
#
# Uses the official uv image (Python 3.12 + uv). Dependencies install in their own
# layer so rebuilds are fast. Secrets are NOT baked in — set them as environment
# variables on your host (Railway dashboard); .env is gitignored AND dockerignored.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# 1) Install dependencies first (cached unless pyproject.toml / uv.lock change).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 2) Copy the source and install the project itself.
COPY . .
RUN uv sync --frozen --no-dev

# Run everything from the project's virtualenv.
ENV PATH="/app/.venv/bin:$PATH"

# Hugging Face Spaces compatibility (2026-07-16):
# - Spaces run the container as a non-root user (uid 1000): the log directory must be
#   writable, and HOME must point somewhere writable for library caches.
# - Spaces route traffic to the port in the README's `app_port` (7860). `fastapi run`
#   reads PORT from the environment, so we default it here; hosts that inject their own
#   PORT at runtime (e.g. Railway) still override this default.
RUN mkdir -p logs && chmod -R 777 logs
ENV HOME=/tmp
ENV PORT=7860
EXPOSE 7860

# Serve the TripOS web app (the product). Hosts with start-command overrides (e.g.
# railway.toml) may point elsewhere; on Docker-CMD hosts like HF Spaces this is the app.
CMD ["fastapi", "run", "src/agent/tripos_web.py"]
