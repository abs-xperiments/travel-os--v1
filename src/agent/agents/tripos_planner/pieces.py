"""The stream's vocabulary — one small home for StreamPiece so every module can speak it.

Lives in its own file (not streaming.py) because the per-turn channel (progress.py) also
produces pieces; keeping the type here avoids an import cycle between the two.
"""

from __future__ import annotations

from pydantic import BaseModel


class StreamPiece(BaseModel):
    """One item streamed to the web UI during a chat turn.

    kind="delta": a text chunk to render. kind="status": a transient progress note shown
    while a tool runs. kind="form": a questionnaire spec (JSON in `text`) for the UI to
    render. kind="done": end of the reply, carrying the serialized history to persist.
    """

    kind: str  # "delta" | "status" | "form" | "done"
    text: str = ""  # delta text, the status message, or the form spec JSON
    messages_json: str = ""  # full serialized history (when kind == "done"), for persistence
