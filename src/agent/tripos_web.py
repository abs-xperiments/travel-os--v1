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

import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from loguru import logger

from agent.agents.tripos_planner import planner_agent
from agent.config import get_settings
from agent.logging_setup import setup_logging
from agent.services import db
from agent.tripos import trip_store

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))

AUTH_COOKIE = "tripos_auth"  # holds the app password once logged in
SESSION_COOKIE = "tripos_session"  # holds the current trip id

GREETING = (
    "Hi! I'm **TripOS**, your travel planner for destinations across India. ✈️\n\n"
    "Tell me about your trip — where you're starting from, how many days, who's coming, "
    "your budget, and what you enjoy — or just say **discover** if you're not sure where "
    "to go yet."
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    applied = await trip_store.init_db()
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
        {"greeting": GREETING, "transcript": trip.transcript if trip else []},
    )
    _remember_session(response, trip_id)
    return response


@app.post("/chat")
async def chat(request: Request, message: Annotated[str, Form()]) -> Response:
    """Run one conversation turn, persist it, and return the bubbles as an HTMX fragment."""
    trip_id = await trip_store.ensure_trip(request.cookies.get(SESSION_COOKIE))
    history = await trip_store.load_agent_messages(trip_id)
    try:
        result = await planner_agent.run(message, message_history=history)
        reply = result.output
        await trip_store.append_turn(trip_id, message, reply, result.all_messages_json().decode())
    except Exception:
        logger.exception("planner run failed for trip {}", trip_id)
        reply = "Sorry — I hit a problem just now. Could you try rephrasing that?"

    response = templates.TemplateResponse(
        request, "_turn.html", {"user_message": message, "reply": reply}
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
        request, "chat.html", {"greeting": GREETING, "transcript": trip.transcript}
    )
    _remember_session(response, trip_id)
    return response


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
