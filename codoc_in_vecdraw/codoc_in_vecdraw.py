"""Codoc in Vecdraw: vector drawings, worked on together.

Pages: ``/`` lists the drawings (:mod:`.components.doc_list`); ``/doc/<id>`` is a drawing at its
own address, used together by everyone who opens it: they all see the same shapes, each with
their own tool and view, see each other's pointers and selections, see who is here, and can call
everyone.
"""

import asyncio
import contextlib
import json

import reflex as rx
from reflex_ddns_auth.intent import install_intent_host
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, PlainTextResponse, Response

from codoc_in_vecdraw import ai_tools, embed, link_preview, ops, presence, saving, yjs_ws
from codoc_in_vecdraw.call import CALLS_ENABLED
from codoc_in_vecdraw.components.canvas import editor_view
from codoc_in_vecdraw.components.doc_list import doc_list_page
from codoc_in_vecdraw.components.together import (
    BYE_PATH,
    call_keepalive,
    identity,
    incoming_call,
    page_hooks,
)
from codoc_in_vecdraw.components.topbar import topbar
from codoc_in_vecdraw.states.doc_list_state import DocListState
from codoc_in_vecdraw.states.document_store import (
    DOCUMENTS_STORE,
    IMAGE_NAME,
    IMAGE_TYPES,
    DocumentGone,
    image_extension,
    new_image_name,
    normalize_doc_id,
)
from codoc_in_vecdraw.states.editor_state import EditorState, document_gone, push_later
from codoc_in_vecdraw.states.ui_state import AuthState, UiState

# An image placed in a drawing can be this big.
MAX_IMAGE_BYTES = 25 * 1024 * 1024


def gone_page() -> rx.Component:
    """The drawing was deleted while it was open."""
    return rx.el.div(
        rx.el.header(
            rx.el.div(
                rx.icon("shapes", class_name="w-6 h-6 text-violet-600"),
                rx.el.span("Vecdraw", class_name="text-lg font-bold text-gray-800"),
                class_name="flex items-center gap-2",
            ),
            identity(),
            class_name="flex items-center justify-between px-6 h-16 bg-white border-b border-gray-200",
        ),
        rx.el.div(
            rx.icon("file-x", class_name="h-12 w-12 text-gray-300"),
            rx.el.p("This drawing was deleted.", id="gone", class_name="text-gray-600 font-medium"),
            rx.el.a(
                "My Documents",
                href="/",
                class_name="px-4 py-2 rounded-lg bg-violet-600 text-white text-sm font-medium hover:bg-violet-700",
            ),
            class_name="flex flex-col items-center gap-4 pt-32",
        ),
        class_name="h-screen bg-gray-50 font-['Inter']",
    )


def index() -> rx.Component:
    """Main editor interface."""
    return rx.cond(
        EditorState.gone,
        gone_page(),
        rx.el.main(
            rx.script(src="/export_canvas.js"),
            topbar(),
            editor_view(
                doc_id=EditorState.doc_id,
                me=UiState.me,
                key=EditorState.doc_id,
                class_name="relative flex flex-1 overflow-hidden",
            ),
            page_hooks(),
            incoming_call(),
            class_name="flex flex-col h-screen w-screen bg-white font-['Inter'] overflow-hidden",
        ),
    )


async def bye(request: Request) -> Response:
    """A closing tab's goodbye: the others on its drawing stop seeing it."""
    try:
        data = json.loads((await request.body())[:4096] or b"{}")
    except ValueError:
        return Response(status_code=400)
    token = str(data.get("token") or "") if isinstance(data, dict) else ""
    room = presence.leave(token) if token else ""
    if room:
        push_later(room)
    return Response(status_code=204)


async def upload_image(request: Request) -> Response:
    """An image placed in a drawing: the request's body is the file."""
    doc_id = request.path_params["doc_id"]
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > MAX_IMAGE_BYTES:
            return PlainTextResponse("this image is too big (25 MB at most)", status_code=413)
    ext = image_extension(bytes(data[:16]))
    if not ext:
        return PlainTextResponse("only PNG, JPEG, GIF and WebP images can be placed", status_code=415)
    name = new_image_name(ext)
    try:
        await asyncio.to_thread(DOCUMENTS_STORE.add_image, doc_id, name, bytes(data))
    except DocumentGone:
        return PlainTextResponse("this drawing was deleted", status_code=404)
    except Exception as e:  # noqa: BLE001 — out of space, say
        return PlainTextResponse(str(e), status_code=507)
    return JSONResponse({"src": name})


async def image(request: Request) -> Response:
    """An image of a drawing. Its name never changes for other content, so browsers keep it."""
    name = request.path_params["name"]
    path = await asyncio.to_thread(DOCUMENTS_STORE.image, request.path_params["doc_id"], name)
    if path is None or not IMAGE_NAME.match(name):
        return Response(status_code=404)
    return FileResponse(
        path,
        media_type=IMAGE_TYPES[name.rsplit(".", 1)[-1]],
        headers={"Cache-Control": "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"},
    )


@contextlib.asynccontextmanager
async def lifespan():
    """At shutdown: saves what waits to be saved."""
    try:
        yield
    finally:
        saving.flush()


app = rx.App(
    head_components=[
        rx.el.link(rel="preconnect", href="https://fonts.googleapis.com"),
        rx.el.link(rel="preconnect", href="https://fonts.gstatic.com", cross_origin=""),
        rx.el.link(
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap",
            rel="stylesheet",
        ),
    ],
)
_auth_on_load = [AuthState.load_auth] if AuthState is not None else []
app.add_page(
    doc_list_page,
    route="/",
    title="Documents | Codoc in Vecdraw",
    on_load=[*_auth_on_load, UiState.leave_room, DocListState.load_documents],
)
app.add_page(
    index,
    route="/doc/[document_id]",
    title="Vector Editor | Codoc in Vecdraw",
    on_load=[*_auth_on_load, EditorState.on_load],
)
# Dialogs of other apps (calls) on every page; a call goes on when you go back to the list.
install_intent_host(app)
if CALLS_ENABLED:
    app.extra_app_wraps[(8, "VecdrawCallKeepalive")] = lambda stateful: rx.fragment(call_keepalive())
app.register_lifespan_task(lifespan)

# The drawings' shapes, held by the server too: each change reaches the store a moment later.
yjs_ws.register_yjs_routes(app)


def _drawing_changed(doc_id: str) -> None:
    saving.changed(doc_id)
    embed.changed(doc_id)


yjs_ws.on_change = _drawing_changed
saving.on_gone = document_gone

# On re_ddns with an AI Hub: the hub's assistant may read drawings and draw on them.
ai_tools.register(app)

# What a link to a drawing shows in a chat app, and a drawing to look at on other apps' pages.
link_preview.register(app)
embed.register(app)

app._api.add_route(BYE_PATH, bye, methods=["POST"])
app._api.add_route("/_vecdraw/upload/{doc_id}", upload_image, methods=["POST"])
app._api.add_route("/_vecdraw/image/{doc_id}/{name}", image, methods=["GET"])


# --- MCP Integration API ---
async def push_ai_ops(request: Request) -> JSONResponse:
    """API endpoint for MCP server to push operations: they reach the drawing's room, and
    everyone on it, whether or not a browser has it open."""
    data = await request.json()
    # "room_id" is the field name used before documents had ids.
    doc_id = normalize_doc_id(data.get("doc_id") or data.get("room_id") or "") or "default"
    pushed = data.get("ops", [])
    if not pushed:
        return JSONResponse({"status": "ignored", "message": "No operations provided"})
    try:
        clear, shapes = ops.run(pushed)
    except (ValueError, TypeError, KeyError, AttributeError) as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)
    room = await yjs_ws.room(doc_id)
    if room is None:
        saving.revive(doc_id)
        await asyncio.to_thread(DOCUMENTS_STORE.create, doc_id)
        room = await yjs_ws.room(doc_id)
    if clear:
        room.clear()
    room.add(shapes)
    return JSONResponse({"status": "success", "message": f"Applied {len(pushed)} operations to document '{doc_id}'"})


# Use internal _api (Starlette app) to add route since app.api is not available in this version
app._api.add_route("/mcp/push_ops", push_ai_ops, methods=["POST"])
