"""destination_intelligence — resolve ANY destination name into a plannable Destination.

This is the single entry point the planner uses instead of the old catalog lookup. It tries,
in order: (1) the fresh knowledge cache, (2) the registered providers by priority — the
curated catalog (instant) then web retrieval (global). It returns None ONLY if every provider,
including web retrieval, cannot identify the place. There is no "supported destinations" list.

Concurrent resolves for the SAME place share one in-flight retrieval (see `_in_flight`), so a
background prewarm and a build that overlap never pay for the same web research twice.

See README.md in this folder for a plain-English explanation and debugging guide.
"""

from __future__ import annotations

import asyncio

from agent.tripos import knowledge_cache, providers
from agent.tripos.models import Destination, TripBrief
from agent.tripos.provider_interfaces import slugify
from agent.tripos.provider_registry import registry

# One retrieval per place at a time: concurrent callers for the same slug await the same task.
_in_flight: dict[str, asyncio.Task[Destination | None]] = {}


async def resolve(query: str, brief: TripBrief | None = None) -> Destination | None:
    """Resolve a free-text destination to a typed Destination (cache -> catalog -> web).

    Returns None only if the place genuinely cannot be identified (e.g. a typo / made-up name).
    """
    providers.register_defaults(registry)  # idempotent — ensures providers exist
    slug = slugify(query)

    cached = await knowledge_cache.get(slug)
    if cached is not None:
        return cached

    task = _in_flight.get(slug)
    if task is None:
        task = asyncio.create_task(_resolve_uncached(query, brief))
        _in_flight[slug] = task
        task.add_done_callback(lambda _, s=slug: _in_flight.pop(s, None))
    return await task


async def _resolve_uncached(query: str, brief: TripBrief | None) -> Destination | None:
    """The miss path: walk the providers by priority and cache what web retrieval finds."""
    for provider in registry.get_all("destination"):
        dest = await provider.fetch(query, brief)
        if dest is not None:
            if provider.name != "catalog":  # catalog is already instant; cache the rest
                await knowledge_cache.put(dest)
            return dest
    return None
