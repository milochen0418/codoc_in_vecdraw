"""A drawing reaches the store SAVE_DELAY seconds after it changes.

The shapes of an open drawing are its room's document (:mod:`codoc_in_vecdraw.yjs_ws`), which
changes with every stroke anyone finishes, and with the AI's operations. Writing the store each
time would revise the drawing's item for every little move, so a change schedules a save
SAVE_DELAY seconds later, and everything done until then goes in it. What is still unsaved when
the app stops is saved then (``flush``). A drawing deleted while people have it open is not
saved again (``forget``).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from codoc_in_vecdraw import yjs_ws
from codoc_in_vecdraw.states.document_store import DOCUMENTS_STORE, DocumentGone

logger = logging.getLogger(__name__)

SAVE_DELAY = 1.5

_timers: dict[str, asyncio.TimerHandle] = {}
_tasks: set[asyncio.Task] = set()
# One save at a time, so an older state can't land after a newer one.
_writing = asyncio.Lock()
# Drawings deleted while open: not saved any more.
gone: set[str] = set()
# Told when saving finds the drawing deleted elsewhere (set by the app: its room shows it).
on_gone: Callable[[str], Awaitable[None]] | None = None


def changed(doc_id: str) -> None:
    """The room's shapes changed: save them soon."""
    if doc_id in gone or doc_id in _timers:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # not on the server's loop: the next change, or flush(), saves it
        return
    _timers[doc_id] = loop.call_later(SAVE_DELAY, _start, doc_id)


def _start(doc_id: str) -> None:
    _timers.pop(doc_id, None)
    task = asyncio.create_task(save(doc_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def save(doc_id: str) -> None:
    async with _writing:
        room = yjs_ws.find(doc_id)
        if room is None or doc_id in gone:
            return
        try:
            await asyncio.to_thread(
                DOCUMENTS_STORE.save, doc_id, shapes=room.shape_list(), state=room.doc.get_update()
            )
        except DocumentGone:
            forget(doc_id)
            if on_gone is not None:
                await on_gone(doc_id)
        except Exception:  # noqa: BLE001 — kept in the room; the next change tries again
            logger.exception("Saving drawing %s failed", doc_id)


async def settle() -> None:
    """Saves now what waits to be saved (someone is about to read the store)."""
    for doc_id in list(_timers):
        _timers.pop(doc_id).cancel()
        await save(doc_id)


def forget(doc_id: str) -> None:
    """The drawing was deleted: drop what waits to be saved, and never save it again."""
    gone.add(doc_id)
    timer = _timers.pop(doc_id, None)
    if timer is not None:
        timer.cancel()


def revive(doc_id: str) -> None:
    """A drawing was made under an id that was deleted before."""
    gone.discard(doc_id)


def flush() -> None:
    """Saves now what waits to be saved (the app is stopping)."""
    for doc_id in list(_timers):
        _timers.pop(doc_id).cancel()
        room = yjs_ws.find(doc_id)
        if room is None or doc_id in gone:
            continue
        try:
            DOCUMENTS_STORE.save(doc_id, shapes=room.shape_list(), state=room.doc.get_update())
        except DocumentGone:
            gone.add(doc_id)
        except Exception:  # noqa: BLE001
            logger.exception("Saving drawing %s at shutdown failed", doc_id)
