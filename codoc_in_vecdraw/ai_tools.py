"""What the AI Hub's assistant may do with drawings: tools (``reflex_ddns_auth.tools``) that read
them, and tools that draw on them.

``room`` is the drawing's id (``/doc/<room>``); the assistant passes the one it was opened from.

The AI works like one more person on a drawing: it shows among the people there while it works,
and its shapes reach everyone through the room's document (``yjs_ws``), which also saves them, with
or without a browser open. A person's Undo doesn't reach another's change, so what can't be put
right by drawing again waits for the person's Accept: changing and removing shapes are ``danger``
tools, adding is not.
"""

from __future__ import annotations

import asyncio
import hashlib

import reflex as rx
from reflex_ddns_auth.tools import ToolContext, image, tool

from codoc_in_vecdraw import ops as operations
from codoc_in_vecdraw import presence, saving, yjs_ws
from codoc_in_vecdraw.states.document_store import DEFAULT_TITLE, DOCUMENTS_STORE, new_doc_id, normalize_doc_id, render_png
from codoc_in_vecdraw.states.editor_state import push_later

ROOM = "The drawing's id, as in /doc/<id>: the one the assistant was opened from (vecdraw.list_drawings lists them)."
OPS = "The shapes to add, bottom one first: objects with an `op`, as the guide shows."
SUMMARY = "One sentence, in the person's language, saying what this does: they read it before they accept."

# What one call may carry or return.
MAX_OPS = 2000
MAX_LISTED = 500
LIST_MAX = 50
# What the AI sees of a drawing.
SNAPSHOT_SIZE = (960, 600)

GUIDE = """\
This is a shared vector drawing; each drawing is a room (/doc/<room>). People may be drawing in it right now, and they see what you do at once. Draw it yourself with these tools rather than telling the person what to do.
Answer in the language the person writes in, and write the words you draw in it too. Traditional Chinese stays Traditional Chinese, never Simplified.
The canvas has no zoom. x grows to the right and y grows downward, in pixels.
Before adding to a drawing that has shapes, call vecdraw_read so that yours land beside them, not on top. A message may begin with what the person's page shows: the part of the canvas in view and the selected shape. Put new shapes inside that view, and "this" means the selected shape.
vecdraw_draw adds shapes on top of the others, the first op at the bottom. Put all the shapes of a picture in one call. Each op is one of:
- {"op": "addRect", "x": 100, "y": 100, "width": 200, "height": 120, "fill": "#fde68a", "stroke": "#92400e", "stroke_width": 2}
- {"op": "addEllipse", "cx": 300, "cy": 200, "rx": 80, "ry": 50, "fill": "#60a5fa"}: a circle has rx equal to ry
- {"op": "addTriangle", "x": 100, "y": 100, "width": 200, "height": 120, "fill": "#34d399"}: pointing up, inside that box
- {"op": "addLine", "x": 100, "y": 100, "end_x": 300, "end_y": 180, "stroke": "#111827", "stroke_width": 3}
- {"op": "addPath", "points": [[100, 100], [150, 60], [200, 100]], "stroke": "#111827", "stroke_width": 3}: a freehand line through the points, never filled; curves need many close points
- {"op": "addText", "x": 100, "y": 100, "content": "Hello", "font_size": 24, "fill": "#111827"}: x, y is its top left corner
x, y of a rectangle, triangle or line is its top left corner or start. Colours are CSS colours; "none" means no fill or no outline. A shape left without `fill` is black, so give every shape its colour. Build a thing out of many simple shapes, from the back to the front, and work out the coordinates so that the parts touch.
vecdraw_snapshot shows you the drawing, scaled to fit, so look at what you drew and fix what is off. Text this picture has no letters for shows as a grey bar: that is only the picture, people see the text.
vecdraw_change and vecdraw_remove wait for the person's Accept in this chat, because Undo can't take back your changes. Take the ids from vecdraw_read. When the person rejects a change, nothing changed: ask what they want instead.
vecdraw_create makes a new drawing; don't use it for a change to this one."""


def _who(ctx: ToolContext) -> str:
    """How the AI shows on a drawing: the AI Hub's own assistant is just "AI", an agent connected
    with a token of its own goes by that token's name."""
    return f"AI · {ctx.user}" if ctx.user and ctx.user not in ("assistant", "companion") else "AI"


def _show_ai(ctx: ToolContext, room: str) -> None:
    """The AI is on the drawing: among its people, until it has stopped for a while."""
    user = f"{presence.AI_PREFIX}{ctx.user}"
    peer = "ai-" + hashlib.sha1(user.encode("utf-8")).hexdigest()[:8]
    presence.join(room, user, peer, user, _who(ctx))
    push_later(room)


async def _room(room: str) -> yjs_ws.Room:
    """The drawing's room (else ValueError, for the AI to read)."""
    doc_id = normalize_doc_id((room or "").strip())
    found = await yjs_ws.room(doc_id) if doc_id and doc_id not in saving.gone else None
    if found is None:
        raise ValueError(f"there is no drawing {room!r}: vecdraw.list_drawings lists them, vecdraw.create makes one")
    return found


def _shapes(pushed: list[dict]) -> list[dict]:
    """The shapes the AI's operations add (ValueError, for the AI to read, when they can't be)."""
    if not pushed:
        raise ValueError("ops is empty: nothing to draw")
    if len(pushed) > MAX_OPS:
        raise ValueError(f"at most {MAX_OPS} ops in one call")
    clear, shapes = operations.run(pushed)
    if clear:
        raise ValueError("the clear op isn't for this tool: vecdraw.remove takes shapes away")
    return shapes


def _told(shape: dict) -> dict:
    """A shape as the AI reads it: what it needs of it, without the empty fields and long paths."""
    out = {k: v for k, v in shape.items() if k not in ("points", "path_data", "src") and v not in ("", [])}
    if shape.get("type") != "line":
        out.pop("end_x", None), out.pop("end_y", None)
    if shape.get("type") == "text":
        out["font_size"] = out.pop("height", 0)
        out.pop("width", None)
    if shape.get("type") == "pencil":
        out["points"] = len(shape.get("points") or [])
    return out


async def guide(ctx: ToolContext) -> dict:
    """Read this first: how the canvas works, and how to draw on it."""
    return {"guide": GUIDE}


async def list_drawings(ctx: ToolContext) -> dict:
    """The drawings, the most recently changed first: their ids ("room"), titles and sizes."""
    docs = await asyncio.to_thread(DOCUMENTS_STORE.values)
    docs = sorted(docs, key=lambda d: d["updated_at"], reverse=True)
    return {
        "drawings": [
            {"room": d["doc_id"], "title": d["title"], "shapes": len(d["shapes"]), "created_by": d["created_by_name"]}
            for d in docs[:LIST_MAX]
        ]
    }


async def read(ctx: ToolContext, room: str) -> dict:
    """The shapes on the drawing as it is right now, bottom one first, and the box they cover."""
    drawing = await _room(room)
    shapes = drawing.shape_list()
    out = {"room": drawing.id, "count": len(shapes), "shapes": [_told(s) for s in shapes[-MAX_LISTED:]]}
    if len(shapes) > MAX_LISTED:
        out["note"] = f"Only the top {MAX_LISTED} shapes are listed."
    if shapes:
        out["covers"] = operations.covers(shapes)
    return out


async def draw(ctx: ToolContext, room: str, ops: list[dict]) -> dict:
    """Adds shapes on top of the drawing; everyone on it sees them at once."""
    shapes = _shapes(ops)
    drawing = await _room(room)
    _show_ai(ctx, drawing.id)
    drawing.add(shapes)
    return {"room": drawing.id, "added": len(shapes), "ids": [s["id"] for s in shapes[:MAX_LISTED]]}


async def change(ctx: ToolContext, room: str, shapes: list[dict], summary: str = "") -> dict:
    """Changes shapes on the drawing: their place, size, colours, outline or text."""
    drawing = await _room(room)
    current = {s["id"]: s for s in drawing.shape_list()}
    changes = {}
    for fields in shapes:
        fields = dict(fields)
        shape_id = str(fields.pop("id", ""))
        if shape_id not in current:
            raise ValueError(f"there is no shape {shape_id!r} on this drawing: vecdraw.read lists them")
        changes[shape_id] = operations.changed(current[shape_id], fields)
    _show_ai(ctx, drawing.id)
    drawing.change(changes)
    return {"room": drawing.id, "changed": len(changes)}


async def remove(ctx: ToolContext, room: str, ids: list[str] | None = None, everything: bool = False, summary: str = "") -> dict:
    """Takes shapes off the drawing: those in ``ids``, or with everything true, all of them."""
    drawing = await _room(room)
    if everything:
        count = len(drawing.shapes)
        _show_ai(ctx, drawing.id)
        drawing.clear()
        return {"room": drawing.id, "removed": count}
    missing = [i for i in ids or [] if i not in drawing.shapes]
    if missing or not ids:
        raise ValueError(f"no such shapes: {missing or 'none given'}; vecdraw.read lists them")
    _show_ai(ctx, drawing.id)
    drawing.remove(ids)
    return {"room": drawing.id, "removed": len(set(ids))}


async def snapshot(ctx: ToolContext, room: str):
    """A picture of the whole drawing, scaled to fit: check that it looks as intended."""
    drawing = await _room(room)
    shapes = drawing.shape_list()
    if not shapes:
        return {"room": drawing.id, "message": "The drawing is empty."}
    data = await asyncio.to_thread(render_png, shapes, lambda name: DOCUMENTS_STORE.image(drawing.id, name), SNAPSHOT_SIZE)
    return image(data)


async def create(ctx: ToolContext, title: str, ops: list[dict] | None = None) -> dict:
    """Makes a new drawing (with these shapes, or empty) and returns its id ("room")."""
    shapes = _shapes(ops) if ops else []
    doc_id = new_doc_id()
    title = " ".join((title or "").split())[:100] or DEFAULT_TITLE
    await asyncio.to_thread(DOCUMENTS_STORE.create, doc_id, shapes=shapes, title=title, creator={"name": _who(ctx), "email": ""})
    return {"room": doc_id, "title": title, "address": f"/doc/{doc_id}"}


def register(app: rx.App) -> None:
    """Offers the drawing tools on ``app``'s backend."""
    tool(app, "vecdraw.guide", title="How to draw here")(guide)
    tool(app, "vecdraw.list_drawings", title="List the drawings")(list_drawings)
    tool(app, "vecdraw.read", title="Read a drawing's shapes", params={"room": ROOM})(read)
    tool(app, "vecdraw.draw", title="Add shapes", kind="write", params={"room": ROOM, "ops": OPS})(draw)
    tool(
        app,
        "vecdraw.change",
        title="Change shapes",
        kind="danger",
        params={
            "room": ROOM,
            "shapes": "One object per shape: its `id` and the fields to change, of x, y, width, height, end_x, end_y, fill, stroke, stroke_width, content, font_size.",
            "summary": SUMMARY,
        },
    )(change)
    tool(
        app,
        "vecdraw.remove",
        title="Remove shapes",
        kind="danger",
        params={"room": ROOM, "ids": "The ids of the shapes to remove.", "everything": "Remove every shape.", "summary": SUMMARY},
    )(remove)
    tool(app, "vecdraw.snapshot", title="Look at the drawing", params={"room": ROOM})(snapshot)
    tool(
        app,
        "vecdraw.create",
        title="Make a new drawing",
        kind="write",
        params={"title": "The drawing's title.", "ops": "Its first shapes, as for vecdraw.draw."},
    )(create)
