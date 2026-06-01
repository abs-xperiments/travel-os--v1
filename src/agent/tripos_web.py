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
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from loguru import logger

from agent.agents.tripos_planner import stream_reply
from agent.config import get_settings
from agent.logging_setup import setup_logging
from agent.services import db
from agent.tripos import knowledge_cache, trip_store

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))

AUTH_COOKIE = "tripos_auth"  # holds the app password once logged in
SESSION_COOKIE = "tripos_session"  # holds the current trip id

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
    applied = await trip_store.init_db() + await knowledge_cache.init_db()
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
async def password_gate(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """If APP_PASSWORD is set, require login before any page (no password = open, for dev)."""
    password = get_settings().app_password
    if password and request.url.path != "/login":
        cookie = request.cookies.get(AUTH_COOKIE, "")
        if not secrets.compare_digest(cookie, password):
            return RedirectResponse("/login", status_code=303)
    return await call_next(request)


@app.get("/login")
async def login_form(request: Request) -> Response:
    if not get_settings().app_password:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": False})


@app.post("/login")
async def login(request: Request, password: Annotated[str, Form()]) -> Response:
    expected = get_settings().app_password or ""
    if expected and secrets.compare_digest(password, expected):
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(
            AUTH_COOKIE, password, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 7
        )
        return response
    return templates.TemplateResponse(request, "login.html", {"error": True}, status_code=401)


@app.get("/")
async def index(request: Request) -> Response:
    trip_id = await trip_store.ensure_trip(request.cookies.get(SESSION_COOKIE))
    trip = await trip_store.get_trip(trip_id)
    response = templates.TemplateResponse(
        request,
        "chat.html",
        {
            "greeting": GREETING,
            "transcript": trip.transcript if trip else [],
            "trip_id": trip_id,
            "examples": EXAMPLES,
        },
    )
    _remember_session(response, trip_id)
    return response


@app.post("/chat/stream")
async def chat_stream(request: Request, message: Annotated[str, Form()]) -> StreamingResponse:
    """Stream the assistant's reply as Server-Sent Events; persist the turn once it completes.

    Each event is `data: {"t": "<delta>"}` (a text chunk), then a final `data: {"done": true}`.
    Errors come back as `data: {"error": "..."}`. If the client disconnects (e.g. the user
    sends another message), the generator is cancelled and the partial turn is simply not saved.
    """
    trip_id = await trip_store.ensure_trip(request.cookies.get(SESSION_COOKIE))
    history = await trip_store.load_agent_messages(trip_id)

    async def events() -> AsyncIterator[str]:
        parts: list[str] = []
        try:
            async for piece in stream_reply(message, history):
                if piece.kind == "delta":
                    parts.append(piece.text)
                    yield f"data: {json.dumps({'t': piece.text})}\n\n"
                elif piece.kind == "status":  # transient progress while a tool runs
                    yield f"data: {json.dumps({'status': piece.text})}\n\n"
                else:  # done
                    await trip_store.append_turn(
                        trip_id, message, "".join(parts), piece.messages_json
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
    """Reopen a saved trip from its URL (also the shareable link) and continue it."""
    trip = await trip_store.get_trip(trip_id)
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
        },
    )
    _remember_session(response, trip_id)
    return response


@app.get("/trip/{trip_id}/print")
async def print_trip(request: Request, trip_id: str) -> Response:
    """A clean, print-optimized page — use the browser's 'Save as PDF' to export."""
    trip = await trip_store.get_trip(trip_id)
    if trip is None:
        return HTMLResponse("Trip not found", status_code=404)
    return templates.TemplateResponse(
        request,
        "print.html",
        {"trip_id": trip_id, "title": trip.title, "transcript": trip.transcript},
    )


@app.get("/trips")
async def trips(request: Request) -> Response:
    """The saved-trips dashboard."""
    recent = await trip_store.list_recent()
    return templates.TemplateResponse(request, "trips.html", {"trips": recent})


@app.get("/reset")
async def reset() -> Response:
    """Start a fresh conversation (forget the current trip cookie)."""
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response
