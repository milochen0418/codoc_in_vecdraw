"""Each drawing's shapes, held by the server as one more peer of the browsers.

A drawing's shapes are a Yjs document (pycrdt here, as in Cellora's notebooks and Codoc in CAD).
Every browser keeps a copy and syncs it with the server's over ``/_vecdraw/yjs/<doc id>`` (the
y-websocket protocol), and the server passes each change on to the drawing's other browsers. So
a change appears on your own screen at once and merges with what the others do at the same
moment. Because it holds a copy itself, the server can change the drawing too (the AI's
operations reach everyone the way a person's change does) and can save it with nobody's browser
open.

Layout of the document (``assets/vecdraw/doc.js`` reads and writes the same):

    shapes   Map, shape id -> Map of the shape's fields (see ``Shape`` in the assets), plus ``z``:
             shapes are drawn in the order of ``z``, then of their id

One Map per shape means two people can change different fields of a shape at once, and the same
shape can never be in the document twice.

A room starts from the stored document with its edit history (``state``), so a restart of the
server changes nothing for a tab that stays open: the tab and the server still hold the same
document, and whatever the tab has that the server doesn't reach it when they sync. A drawing
nobody changed yet has no history stored (opening it changes nothing in the store) and starts from
its shapes.

Every change of the shapes is told to ``on_change`` (set by the app: the saving).

Awareness goes through the same socket: what each browser is doing right now (its pointer, what
it selected, what it is drawing), which nobody saves. The server remembers which awareness
clients each socket announced, so a closing socket takes them away for the others.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from pycrdt import (
    Awareness,
    Decoder,
    Doc,
    Encoder,
    Map,
    YMessageType,
    create_awareness_message,
    create_sync_message,
    create_update_message,
    handle_sync_message,
    read_message,
)
from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from codoc_in_vecdraw.states.document_store import DOCUMENTS_STORE

logger = logging.getLogger(__name__)

SHAPES = "shapes"
# A browser this far behind is closed; it reconnects and syncs from scratch.
MAX_PENDING = 2000
# The close code telling a browser the drawing isn't there (any more): it stops reconnecting.
CLOSE_GONE = 4404

# Told of every change of a room's shapes, with the drawing's id (set by the app).
on_change: Callable[[str], None] | None = None


class _Client:
    """A browser's socket in a room, with its own queue of messages to send."""

    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        # The awareness clients this socket announced: Yjs clientID -> latest clock.
        self.aware: dict[int, int] = {}
        self.task: asyncio.Task | None = None

    def send(self, data: bytes) -> None:
        if self.queue.qsize() > MAX_PENDING:
            self.queue.put_nowait(None)
            return
        self.queue.put_nowait(data)

    async def run(self) -> None:
        while True:
            data = await self.queue.get()
            if data is None:
                try:
                    await self.ws.close(code=1013)
                except Exception:  # noqa: BLE001
                    pass
                return
            try:
                await self.ws.send_bytes(data)
            except Exception:  # noqa: BLE001
                return


class Room:
    """A drawing's shapes, and the browsers on it."""

    def __init__(self, doc_id: str, state: bytes | None = None, shapes: list[dict] | None = None) -> None:
        self.id = doc_id
        self.doc = Doc()
        self.shapes = self.doc.get(SHAPES, type=Map)
        if not self._restore(state) and shapes:
            self.add(shapes)
        self.clients: dict[WebSocket, _Client] = {}
        self.awareness = Awareness(self.doc)
        self.awareness.set_local_state(None)  # the server itself is nobody
        self._origin: WebSocket | None = None
        self.doc.observe(self._on_update)

    def _restore(self, state: bytes | None) -> bool:
        """Starts from the stored history; False when there is none that can be read (the stored
        shapes are the drawing then)."""
        if not state:
            return False
        try:
            self.doc.apply_update(state)
            return True
        except Exception as e:  # noqa: BLE001
            logger.warning("yjs-ws: room %s: unreadable history, starting from its shapes: %s", self.id, e)
            return False

    def shape_list(self) -> list[dict]:
        """The shapes as they are stored: in drawing order, with whole numbers as such."""
        shapes = list((self.shapes.to_py() or {}).values())
        shapes.sort(key=lambda s: (s.get("z", 0), s.get("id", "")))
        return [{k: _whole(v) for k, v in s.items() if k != "z"} for s in shapes]

    def add(self, shapes: list[dict]) -> None:
        """Puts shapes on top of the drawing."""
        with self.doc.transaction():
            z = max((s.get("z", 0) for s in (self.shapes.to_py() or {}).values()), default=0)
            for shape in shapes:
                z += 1
                self.shapes[shape["id"]] = Map({**shape, "z": z})

    def change(self, changes: dict[str, dict]) -> None:
        """Sets fields of shapes: shape id -> its new fields."""
        with self.doc.transaction():
            for shape_id, fields in changes.items():
                shape = self.shapes[shape_id]
                for key, value in fields.items():
                    shape[key] = value

    def remove(self, ids: list[str]) -> None:
        """Takes these shapes off the drawing."""
        with self.doc.transaction():
            for shape_id in set(ids):
                del self.shapes[shape_id]

    def clear(self) -> None:
        """Takes every shape off the drawing."""
        self.shapes.clear()

    def _on_update(self, event: Any) -> None:
        message = create_update_message(event.update)
        for ws, client in list(self.clients.items()):
            if ws is not self._origin:
                client.send(message)
        if on_change is not None:
            try:
                on_change(self.id)
            except Exception:  # noqa: BLE001
                logger.exception("yjs-ws: room %s: on_change failed", self.id)

    async def serve(self, ws: WebSocket) -> None:
        """One browser's socket, from its first sync until it closes."""
        client = _Client(ws)
        self.clients[ws] = client
        client.task = asyncio.create_task(client.run())
        client.send(create_sync_message(self.doc))
        others = [cid for cid in self.awareness.states if cid != self.awareness.client_id]
        if others:
            client.send(create_awareness_message(self.awareness.encode_awareness_update(others)))
        try:
            while True:
                data = await ws.receive_bytes()
                if not data:
                    continue
                kind = data[0]
                if kind == YMessageType.SYNC:
                    self._origin = ws
                    try:
                        reply = handle_sync_message(data[1:], self.doc)
                    except Exception as e:  # noqa: BLE001
                        logger.warning("yjs-ws: room %s: bad sync message: %s", self.id, e)
                        reply = None
                    finally:
                        self._origin = None
                    if reply is not None:
                        client.send(reply)
                elif kind == YMessageType.AWARENESS:
                    self._awareness(client, data)
                elif kind == 3:  # y-websocket's "query awareness": send everyone's
                    ids = [cid for cid in self.awareness.states if cid != self.awareness.client_id]
                    if ids:
                        client.send(create_awareness_message(self.awareness.encode_awareness_update(ids)))
        except (WebSocketDisconnect, RuntimeError):  # closed, or receive after close
            pass
        except Exception as e:  # noqa: BLE001
            logger.warning("yjs-ws: room %s: socket error: %s", self.id, e)
        finally:
            self.clients.pop(ws, None)
            client.queue.put_nowait(None)
            self._goodbye(client)

    def _awareness(self, client: _Client, data: bytes) -> None:
        try:
            update = read_message(data[1:])
            for cid, clock, here in _awareness_entries(update):
                if here:
                    client.aware[cid] = clock
                else:
                    client.aware.pop(cid, None)
            self.awareness.apply_awareness_update(update, client.ws)
        except Exception as e:  # noqa: BLE001
            logger.warning("yjs-ws: room %s: bad awareness message: %s", self.id, e)
            return
        for other in list(self.clients.values()):
            if other is not client:
                other.send(data)

    def _goodbye(self, client: _Client) -> None:
        """The socket closed: its browser's pointer and selection go away for the others."""
        if not client.aware:
            return
        message = create_awareness_message(_awareness_null(client.aware))
        try:
            self.awareness.remove_awareness_states(list(client.aware), "closed")
        except Exception:  # noqa: BLE001
            pass
        for other in list(self.clients.values()):
            other.send(message)


_rooms: dict[str, Room] = {}
_opening = asyncio.Lock()


def find(doc_id: str) -> Room | None:
    """The drawing's room, when the server holds it."""
    return _rooms.get(doc_id)


async def room(doc_id: str) -> Room | None:
    """The drawing's room, read from the store when nobody has opened it since the server started;
    None when there is no such drawing."""
    r = _rooms.get(doc_id)
    if r is not None:
        return r
    async with _opening:
        r = _rooms.get(doc_id)
        if r is not None:
            return r
        stored = await asyncio.to_thread(DOCUMENTS_STORE.get, doc_id)
        if stored is None:
            return None
        state = await asyncio.to_thread(DOCUMENTS_STORE.state, doc_id)
        r = _rooms[doc_id] = Room(doc_id, state, stored["shapes"])
    return r


async def close(doc_id: str) -> None:
    """The drawing was deleted: its browsers are told, and the server forgets it."""
    r = _rooms.pop(doc_id, None)
    if r is None:
        return
    for ws in list(r.clients):
        try:
            await ws.close(code=CLOSE_GONE)
        except Exception:  # noqa: BLE001
            pass


async def _yjs_ws_endpoint(websocket: WebSocket) -> None:
    """Handle a single Yjs WebSocket connection."""
    doc_id: str = websocket.path_params.get("doc_id", "")
    await websocket.accept()
    r = await room(doc_id) if doc_id else None
    if r is None:
        await websocket.close(code=CLOSE_GONE)
        return
    await r.serve(websocket)


def register_yjs_routes(app) -> None:  # noqa: ANN001 - Reflex App
    """Register the ``/_vecdraw/yjs/{doc_id}`` WebSocket endpoint on the backend."""
    app._api.routes.append(WebSocketRoute("/_vecdraw/yjs/{doc_id}", _yjs_ws_endpoint))


# ------------------------------------------------------------ helpers


def _whole(value: Any) -> Any:
    """Yjs numbers come back as floats: 5.0 is the 5 that was stored."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, list):
        return [_whole(v) for v in value]
    if isinstance(value, dict):
        return {k: _whole(v) for k, v in value.items()}
    return value


def _awareness_entries(update: bytes) -> list[tuple[int, int, bool]]:
    """(clientID, clock, still here) for each client of an awareness update."""
    decoder = Decoder(update)
    out = []
    for _ in range(decoder.read_var_uint()):
        cid = decoder.read_var_uint()
        clock = decoder.read_var_uint()
        state = decoder.read_var_string()
        out.append((cid, clock, bool(state) and state != "null"))
    return out


def _awareness_null(clients: dict[int, int]) -> bytes:
    """An awareness update saying these clients left: state null, clock + 1."""
    encoder = Encoder()
    encoder.write_var_uint(len(clients))
    for cid, clock in clients.items():
        encoder.write_var_uint(cid)
        encoder.write_var_uint(clock + 1)
        encoder.write_var_string("null")
    return encoder.to_bytes()
