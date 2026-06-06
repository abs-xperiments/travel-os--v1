"""TripOS web UI — a browser chat with the planner agent.

Run it locally with auto-reload:

    uv run fastapi dev src/agent/tripos_web.py

Server-rendered: FastAPI + Jinja2 + HTMX + Tailwind, all via CDN — no JavaScript build step.
The chat agent and its tools are exactly the ones the CLI uses (agents/tripos_planner.py);
this file is just the web "UX".

Conversations are persisted in Neon via `trip_store`, so they survive restarts, can be
reopened from their own URL (/trip/{id}), and appear in a saved-trips list (/trips).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger

from agent import web_auth
from agent.agents.tripos_planner import stream_reply
from agent.config import get_settings
from agent.logging_setup import setup_logging
from agent.services import db
from agent.tripos import accounts, knowledge_cache, trip_intelligence, trip_store

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))

SESSION_COOKIE = "tripos_session"  # holds the current trip id (NOT the auth session)

GREETING = (
    "Hi! I'm **TripOS**, your AI travel planner for destinations **anywhere in the world**. 🌍\n\n"
    "Tell me about your trip — where you'd like to go (or say **discover** if you're not sure), "
    "where you're starting from, how many days, who's coming, your budget, and what you enjoy."
)

# Example prompts shown on a fresh chat (domestic + international) to signal global coverage.
EXAMPLES = [
    "Plan a 5-day trip to Kerala",
    "Build an 8-day Japan itinerary",
    "Suggest a honeymoon in Bali",
    "Plan a budget trip to Vietnam",
    "Create a 10-day Europe itinerary",
    "Ideas for a 6-day family vacation",
]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    settings = get_settings()
    if settings.app_base_url.startswith("https") and not settings.cookie_secure:
        logger.warning(
            "APP_BASE_URL is https but COOKIE_SECURE is false — session cookies would be "
            "sent over plain http too. Set COOKIE_SECURE=true in production!"
        )
    # Order matters: accounts' migration 005 alters tripos_trips (created by trip_store's 001).
    applied = (
        await trip_store.init_db()
        + await accounts.init_db()
        + await knowledge_cache.init_db()
        + await trip_intelligence.init_db()
    )
    if applied:
        logger.info("applied migrations: {}", applied)
    yield
    await db.close_pool()


app = FastAPI(title="TripOS", lifespan=lifespan)


def _remember_session(response: Response, trip_id: str) -> None:
    response.set_cookie(
        SESSION_COOKIE, trip_id, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30
    )


@app.middleware("http")
async def resolve_user(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Attach the signed-in user (or None) to every request.

    Authentication is plumbing, never a wall: pages render for everyone; the routes that
    touch user data check `request.state.user` themselves (and the trip queries are
    user-scoped in SQL regardless — defense in depth).
    """
    request.state.user = None
    raw = request.cookies.get(web_auth.SID_COOKIE)
    if raw:
        try:
            request.state.user = await accounts.resolve_session(raw)
        except Exception:
            logger.exception("session resolve failed — continuing logged out")
    return await call_next(request)


app.include_router(web_auth.router)
app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")


@app.get("/sw.js")
async def service_worker() -> FileResponse:
    """Served from the root so the service worker's scope covers the whole app."""
    return FileResponse(HERE / "static" / "sw.js", media_type="application/javascript")


@app.get("/")
async def index(request: Request) -> Response:
    """The chatbot IS the landing page — logged out it's browsable, sending needs sign-in.

    Trips are created lazily on the first authed message (never on page views), so this
    only LOADS an existing owned trip when the cookie points at one.
    """
    user = request.state.user
    trip = None
    trip_id = request.cookies.get(SESSION_COOKIE)
    if user is not None and trip_id:
        trip = await trip_store.get_trip(trip_id, user.id)
    return templates.TemplateResponse(
        request,
        "chat.html",
        {
            "greeting": GREETING,
            "transcript": trip.transcript if trip else [],
            "trip_id": trip.id if trip else "",
            "examples": EXAMPLES,
            "user": user,
        },
    )


@app.post("/chat/stream")
async def chat_stream(request: Request, message: Annotated[str, Form()]) -> Response:
    """Stream the assistant's reply as Server-Sent Events; persist the turn once it completes.

    Each event is `data: {"t": "<delta>"}` (a text chunk), then a final `data: {"done": true}`.
    Errors come back as `data: {"error": "..."}`. If the client disconnects (e.g. the user
    sends another message), the generator is cancelled and the partial turn is simply not saved.
    """
    user = request.state.user
    if user is None:  # sending is the gate — the chat itself is free to explore
        return JSONResponse(
            {"auth": "Sign in to start planning and save your trips."}, status_code=401
        )
    trip_id = await trip_store.ensure_owned_trip(request.cookies.get(SESSION_COOKIE), user.id)
    history = await trip_store.load_agent_messages(trip_id, user.id)

    async def events() -> AsyncIterator[str]:
        parts: list[str] = []
        try:
            async for piece in stream_reply(message, history):
                if piece.kind == "delta":
                    parts.append(piece.text)
                    yield f"data: {json.dumps({'t': piece.text})}\n\n"
                elif piece.kind == "status":  # transient progress while a tool runs
                    yield f"data: {json.dumps({'status': piece.text})}\n\n"
                elif piece.kind == "form":  # questionnaire spec — transient, like statuses
                    yield f"data: {json.dumps({'form': json.loads(piece.text)})}\n\n"
                elif piece.kind == "done":
                    await trip_store.append_turn(
                        trip_id, user.id, message, "".join(parts), piece.messages_json
                    )
                    yield f"data: {json.dumps({'done': True})}\n\n"
        except asyncio.CancelledError:
            raise  # client went away / sent a new message — stop quietly, don't persist
        except Exception:
            logger.exception("stream failed for trip {}", trip_id)
            err = json.dumps({"error": "Something went wrong generating that reply."})
            yield f"data: {err}\n\n"

    response = StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
    _remember_session(response, trip_id)
    return response


@app.get("/trip/{trip_id}")
async def open_trip(request: Request, trip_id: str) -> Response:
    """Reopen one of YOUR saved trips. A foreign trip is a 404 — indistinguishable from
    one that never existed (trips are private to their owner)."""
    user = request.state.user
    if user is None:
        return RedirectResponse("/login", status_code=303)
    trip = await trip_store.get_trip(trip_id, user.id)
    if trip is None:
        return HTMLResponse("Trip not found", status_code=404)
    response = templates.TemplateResponse(
        request,
        "chat.html",
        {
            "greeting": GREETING,
            "transcript": trip.transcript,
            "trip_id": trip_id,
            "examples": EXAMPLES,
            "user": user,
        },
    )
    _remember_session(response, trip_id)
    return response


@app.get("/trip/{trip_id}/print")
async def print_trip(request: Request, trip_id: str) -> Response:
    """A clean, print-optimized page — owner-only, like every trip view."""
    user = request.state.user
    if user is None:
        return RedirectResponse("/login", status_code=303)
    trip = await trip_store.get_trip(trip_id, user.id)
    if trip is None:
        return HTMLResponse("Trip not found", status_code=404)
    return templates.TemplateResponse(
        request,
        "print.html",
        {"trip_id": trip_id, "title": trip.title, "transcript": trip.transcript},
    )


@app.get("/trips")
async def trips(request: Request) -> Response:
    """The saved-trips dashboard — only ever YOUR trips."""
    user = request.state.user
    if user is None:
        return RedirectResponse("/login", status_code=303)
    recent = await trip_store.list_recent(user.id)
    return templates.TemplateResponse(request, "trips.html", {"trips": recent, "user": user})


@app.get("/reset")
async def reset() -> Response:
    """Start a fresh conversation (forget the current trip cookie)."""
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response
