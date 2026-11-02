"""A drawing's room: what everybody on /doc/<id> sees around the canvas, pushed to all of them.

``EditorState`` is a Reflex ``SharedState``: every tab on a drawing links its state to the
drawing's id. The shapes are not in it: they travel in the room's Yjs document
(:mod:`codoc_in_vecdraw.yjs_ws`), straight between the browsers and the server, and reach the
store from there (:mod:`codoc_in_vecdraw.saving`). Tools, the part of the canvas in view and
what someone selected are each person's own: they live in the browser
(``assets/vecdraw/editor.jsx``), and the others get a hint of them through the document's
awareness. What is left for this room is what the page draws with Reflex: the title, the people
on the drawing, and its call.
"""

import asyncio
import json
import logging

import reflex as rx
from reflex_ddns_auth import rooms

from codoc_in_vecdraw import call, embed, presence, saving, yjs_ws
from codoc_in_vecdraw.states.document_store import (
    DEFAULT_TITLE,
    DOCUMENTS_STORE,
    DocumentGone,
    new_doc_id,
    normalize_doc_id,
)
from codoc_in_vecdraw.states.ui_state import UiState

logger = logging.getLogger(__name__)

_tasks: set[asyncio.Task] = set()
_opening = asyncio.Lock()


class EditorState(rx.SharedState):
    """State around the Vector Graphics Editor."""

    doc_id: str = ""
    doc_title: str = ""
    # The drawing was deleted while people had it open.
    gone: bool = False
    # One entry per tab on the drawing: {"id", "user", "name", "avatar", "color"}.
    peers: list[dict[str, str]] = []
    # The drawing's call (codoc_in_vecdraw.call): how many are in it, who is ringing everyone
    # (while it rings), the people it rings (those here when it started), and who joined or
    # declined.
    call_count: int = 0
    call_ringing_from: str = ""
    call_invited: list[str] = []
    call_responded: list[str] = []

    @rx.var
    def people(self) -> list[dict[str, str]]:
        """One entry per person: several tabs of one person count once."""
        out: list[dict[str, str]] = []
        seen = set()
        for p in self.peers:
            user = p.get("user") or p.get("id")
            if user in seen:
                continue
            seen.add(user)
            name = p.get("name", "") or "?"
            out.append(
                {
                    "id": p.get("id", ""),
                    "user": user,
                    "name": name,
                    "initials": presence.initials(name),
                    "color": p.get("color", ""),
                    "avatar": p.get("avatar", ""),
                }
            )
        return out

    @rx.var
    def people_count(self) -> int:
        return len({p.get("user") or p.get("id") for p in self.peers})

    @rx.event
    async def on_load(self):
        """Open /doc/<doc_id>; every client on the same document shares this state."""
        raw_id = self.router.url.path.rstrip("/").rsplit("/", 1)[-1]
        doc_id = normalize_doc_id(raw_id)
        if not doc_id:
            return rx.redirect("/")
        if doc_id != raw_id:
            return rx.redirect(f"/doc/{doc_id}")
        ui = await self.get_state(UiState)
        await ui._identify()
        # One at a time: two people can open a new link at the same moment.
        async with _opening:
            stored = await asyncio.to_thread(DOCUMENTS_STORE.get, doc_id)
            if stored is None:
                # As in codoc_in_md, opening /doc/<id> creates the document. The server may still
                # hold a room of that id: its drawing was deleted on the storage page.
                await yjs_ws.close(doc_id)
                saving.revive(doc_id)
                creator = await ui._creator()
                stored = await asyncio.to_thread(DOCUMENTS_STORE.create, doc_id, creator=creator)
        # Set the document on the linked (shared) state, not on this private one.
        doc = await self._link_to(doc_id)
        doc.doc_id = doc_id
        doc.doc_title = stored["title"]
        doc.gone = False
        # What this event changes reaches only this tab: Reflex passes a room's changes on to its
        # other tabs from events that start out linked. The others hear about this tab in this
        # follow-up event.
        return [EditorState.join_room, _page_title(stored["title"])]

    async def _here(self) -> tuple[UiState, str]:
        """This tab's own state and the drawing it is on ("" when it is on none)."""
        ui = await self.get_state(UiState)
        room = self.doc_id
        if not room or self._linked_to != room:
            return ui, ""
        return ui, room

    @rx.event
    async def join_room(self):
        """Shows this tab among the people on the drawing, to everyone on it."""
        ui, room = await self._here()
        if not room:
            return
        me = ui.me
        left, color = presence.join(room, ui.router.session.client_token, me["peer"], me["user"], me["name"], me.get("avatar", ""))
        ui._set_color(color)
        presence.prune(room)
        publish(self, room)
        if left:
            push_later(left)

    @rx.event
    async def ping(self):
        """Still here (every 5 s): keeps this tab among the people on the drawing and drops the
        tabs gone."""
        ui, room = await self._here()
        if not room:
            return
        token = ui.router.session.client_token
        if not presence.touch(room, token):
            # Back after a restart, or after being dropped as idle.
            await ui._identify()
            me = ui.me
            _, color = presence.join(room, token, me["peer"], me["user"], me["name"], me.get("avatar", ""))
            ui._set_color(color)
        presence.prune(room)
        publish(self, room)

    async def _rename(self, title: str):
        title = " ".join((title or "").split())[:100] or DEFAULT_TITLE
        if not self.doc_id or title == self.doc_title:
            return None
        try:
            await asyncio.to_thread(DOCUMENTS_STORE.save, self.doc_id, title=title)
        except DocumentGone:
            # This event is in the room already, and holds it: no document_gone() from here.
            saving.forget(self.doc_id)
            await yjs_ws.close(self.doc_id)
            self.gone = True
            return None
        self.doc_title = title
        return _page_title(title)

    @rx.event
    async def rename_document(self, title: str):
        """Rename the document (title input lost focus)."""
        return await self._rename(title)

    @rx.event
    async def rename_from_form(self, form_data: dict):
        """Rename the document (Enter pressed in the title input)."""
        return await self._rename(form_data.get("title", ""))

    @rx.event
    async def duplicate_document(self):
        """Copy this drawing into a new document and open it."""
        if not self.doc_id:
            return None
        room = await yjs_ws.room(self.doc_id)
        if room is None:
            return None
        ui = await self.get_state(UiState)
        new_id = new_doc_id()
        shapes = room.shape_list()
        await asyncio.to_thread(
            DOCUMENTS_STORE.create,
            new_id,
            shapes=shapes,
            title=f"{self.doc_title} (copy)"[:100],
            creator=await ui._creator(),
        )
        images = [s.get("src") for s in shapes if s.get("type") == "image"]
        if images:
            await asyncio.to_thread(DOCUMENTS_STORE.copy_images, self.doc_id, new_id, images)
        return rx.redirect(f"/doc/{new_id}")


def _page_title(title: str):
    return rx.call_script(f"document.title = {json.dumps(title + ' | Codoc in Vecdraw')}")


def publish(editor: EditorState, room: str) -> None:
    """Shows who is on the drawing, and its call, to everyone on it (only what changed)."""
    peers = presence.tabs(room)
    if list(editor.peers) != peers:
        editor.peers = peers
    call.sync_room(editor, room)


def push_later(room: str) -> None:
    """``publish``, from outside the tabs' own events."""
    task = asyncio.create_task(push(room))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def push(room: str) -> None:
    try:
        async with rooms.change(EditorState, room) as editor:
            publish(editor, room)
    except Exception as e:  # noqa: BLE001
        logger.warning("Cannot show the people of drawing %s: %s", room, e)


async def document_gone(doc_id: str) -> None:
    """The drawing was deleted while people had it open: they see so, and it isn't saved again."""
    saving.forget(doc_id)
    await yjs_ws.close(doc_id)
    embed.changed(doc_id)
    try:
        async with rooms.change(EditorState, doc_id) as editor:
            editor.gone = True
    except Exception as e:  # noqa: BLE001
        logger.warning("Cannot tell drawing %s it was deleted: %s", doc_id, e)
