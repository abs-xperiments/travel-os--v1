"""TripOS web UI — a browser chat with the planner agent.

Run it locally with auto-reload:

    uv run fastapi dev src/agent/tripos_web.py

Server-rendered: FastAPI + Jinja2 + HTMX + Tailwind, all via CDN — no JavaScript build step.
The chat agent and its tools are exactly the ones the CLI uses (agents/tripos_planner.py);
this file is just the web "UX".

Conversation history is kept IN MEMORY per browser session for now (a simple dict). The next
module moves it into Neon Postgres so trips survive restarts and can be saved/reopened.
"""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from loguru import logger

from agent.agents.tripos_planner import planner_agent
from agent.config import get_settings
from agent.logging_setup import setup_logging

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))

AUTH_COOKIE = "tripos_auth"  # holds the app password once logged in
SESSION_COOKIE = "tripos_session"  # identifies a browser's conversation

GREETING = (
    "Hi! I'm **TripOS**, your travel planner for destinations across India. ✈️\n\n"
    "Tell me about your trip — where you're starting from, how many days, who's coming, "
    "your budget, and what you enjoy — or just say **discover** if you're not sure where "
    "to go yet."
)

# In-memory conversation history per session id. TEMPORARY: the persistence module will
# move this into Neon so conversations survive a restart and trips can be saved/reopened.
_SESSIONS: dict[str, list] = {}

setup_logging()
app = FastAPI(title="TripOS")


def _remember_session(response: Response, session_id: str) -> None:
    response.set_cookie(
        SESSION_COOKIE, session_id, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 7
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
    session_id = request.cookies.get(SESSION_COOKIE) or uuid4().hex
    _SESSIONS.setdefault(session_id, [])
    response = templates.TemplateResponse(request, "chat.html", {"greeting": GREETING})
    _remember_session(response, session_id)
    return response


@app.post("/chat")
async def chat(request: Request, message: Annotated[str, Form()]) -> Response:
    """Run one conversation turn and return the user + assistant bubbles as an HTMX fragment."""
    session_id = request.cookies.get(SESSION_COOKIE) or uuid4().hex
    history = _SESSIONS.setdefault(session_id, [])
    try:
        result = await planner_agent.run(message, message_history=history)
        _SESSIONS[session_id] = result.all_messages()
        reply = result.output
    except Exception:
        logger.exception("planner run failed for session {}", session_id)
        reply = "Sorry — I hit a problem just now. Could you try rephrasing that?"

    response = templates.TemplateResponse(
        request, "_turn.html", {"user_message": message, "reply": reply}
    )
    _remember_session(response, session_id)
    return response


@app.get("/reset")
async def reset(request: Request) -> Response:
    """Start a fresh conversation."""
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        _SESSIONS.pop(session_id, None)
    return RedirectResponse("/", status_code=303)
