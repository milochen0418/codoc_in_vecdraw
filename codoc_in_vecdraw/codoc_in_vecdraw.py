import reflex as rx
from codoc_in_vecdraw.components.toolbar import toolbar
from codoc_in_vecdraw.components.topbar import topbar
from codoc_in_vecdraw.components.canvas import canvas
from codoc_in_vecdraw.components.properties_panel import properties_panel
from codoc_in_vecdraw.components.doc_list import doc_list_page
from codoc_in_vecdraw.states.doc_list_state import DocListState
from codoc_in_vecdraw.states.document_store import normalize_doc_id
from codoc_in_vecdraw.states.editor_state import EditorState, PENDING_AI_OPS
from fastapi import Request


def index() -> rx.Component:
    """Main editor interface."""
    return rx.el.main(
        rx.script(src="/export_canvas.js"),
        # Poll for AI ops every 1 second
        rx.moment(interval=1000, on_change=EditorState.check_pending_ai_ops, display="none"),
        topbar(),
        rx.el.div(
            toolbar(),
            canvas(),
            properties_panel(),
            class_name="flex flex-1 overflow-hidden",
        ),
        class_name="flex flex-col h-screen w-screen bg-white font-['Inter'] overflow-hidden",
    )


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
app.add_page(
    doc_list_page,
    route="/",
    title="Documents | Codoc in Vecdraw",
    on_load=DocListState.load_documents,
)
app.add_page(
    index,
    route="/doc/[document_id]",
    title="Vector Editor | Codoc in Vecdraw",
    on_load=EditorState.on_load,
)

# --- MCP Integration API ---
async def push_ai_ops(request: Request):
    """API endpoint for MCP server to push operations."""
    data = await request.json()
    # "room_id" is the field name used before documents had ids.
    doc_id = normalize_doc_id(data.get("doc_id") or data.get("room_id") or "") or "default"
    ops = data.get("ops", [])

    if ops:
        PENDING_AI_OPS[doc_id].extend(ops)
        return {"status": "success", "message": f"Queued {len(ops)} operations for document '{doc_id}'"}
    return {"status": "ignored", "message": "No operations provided"}

# Use internal _api (Starlette app) to add route since app.api is not available in this version
from starlette.responses import JSONResponse
async def push_ai_ops_wrapper(request):
    res = await push_ai_ops(request)
    return JSONResponse(res)

app._api.add_route("/mcp/push_ops", push_ai_ops_wrapper, methods=["POST"])