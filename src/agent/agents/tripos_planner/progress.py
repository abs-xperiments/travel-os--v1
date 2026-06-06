"""Honest, live progress for long tool runs — the ✓-checklist the traveler watches.

`stream_reply` activates a Reporter per chat turn (through a ContextVar, which asyncio tasks
inherit), and tool code reports stages through the module-level helpers below — which simply
no-op when no reporter is active (CLI runs, tests). Every change re-renders the FULL block;
the UI replaces the status line wholesale, so each event is the complete current checklist:

    Building your trip…
    ✓ Destination intelligence
    ✓ Stays, food & weather
    • Selecting stops, days & budget…

The honesty contract (docs/policy.md): a line gets its ✓ only when that work actually
completed — never theatrical progress.
"""

from __future__ import annotations

import asyncio
from contextvars import ContextVar, Token

_DONE = "✓"
_PENDING = "•"


class Reporter:
    """One chat turn's checklist: ordered lines, each pending (•) or done (✓)."""

    def __init__(self, queue: asyncio.Queue[str]) -> None:
        self._queue = queue
        self.title = ""  # set by streaming when a tool starts (e.g. "Building your trip…")
        self._lines: list[list] = []  # [label, done] pairs, in display order
        self._current_step: str | None = None  # the line step() will auto-complete

    def _emit(self) -> None:
        parts = [self.title] if self.title else []
        for label, done in self._lines:
            parts.append(f"{_DONE} {label}" if done else f"{_PENDING} {label}…")
        self._queue.put_nowait("\n".join(parts))

    def begin(self, label: str) -> None:
        """Add a pending line (for work that's now genuinely underway)."""
        self._lines.append([label, False])
        self._emit()

    def finish(self, label: str) -> None:
        """Tick the first pending line with this label — call when the work COMPLETED."""
        for line in self._lines:
            if line[0] == label and not line[1]:
                line[1] = True
                break
        self._emit()

    def step(self, label: str) -> None:
        """Sequential stage: completes the previous step (if any), then begins this one."""
        if self._current_step is not None:
            self.finish(self._current_step)
        self._current_step = label
        self.begin(label)

    def complete(self) -> None:
        """Tick everything still pending — call once the tool's work is fully done."""
        changed = False
        for line in self._lines:
            if not line[1]:
                line[1] = True
                changed = True
        self._current_step = None
        if changed:
            self._emit()


_reporter: ContextVar[Reporter | None] = ContextVar("tripos_progress_reporter", default=None)


def activate(queue: asyncio.Queue[str]) -> tuple[Reporter, Token]:
    """Install a Reporter for this turn; returns it plus the token for deactivate()."""
    reporter = Reporter(queue)
    return reporter, _reporter.set(reporter)


def deactivate(token: Token) -> None:
    _reporter.reset(token)


# ---- the helpers tool code calls (safe no-ops when no reporter is active) ----


def begin(label: str) -> None:
    if (r := _reporter.get()) is not None:
        r.begin(label)


def finish(label: str) -> None:
    if (r := _reporter.get()) is not None:
        r.finish(label)


def step(label: str) -> None:
    if (r := _reporter.get()) is not None:
        r.step(label)


def complete() -> None:
    if (r := _reporter.get()) is not None:
        r.complete()
