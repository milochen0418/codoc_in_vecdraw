import reflex as rx
from reflex_ddns_auth.intent import Intent
from reflex_ddns_auth.tools import own_app

from codoc_in_vecdraw.components.together import call_button, identity, presence
from codoc_in_vecdraw.states.doc_list_state import DocListState
from codoc_in_vecdraw.states.editor_state import EditorState
from codoc_in_vecdraw.states.ui_state import UiState

_BUTTON = "flex items-center flex-shrink-0 whitespace-nowrap text-sm font-medium px-3 py-1.5 rounded-lg transition-colors"


def title_editor() -> rx.Component:
    """Inline-editable document title; saved on Enter or when the input loses focus."""
    return rx.el.form(
        rx.el.input(
            id="doc-title",
            name="title",
            default_value=EditorState.doc_title,
            # Remount when a collaborator renames the document.
            key=EditorState.doc_id + ":" + EditorState.doc_title,
            on_blur=EditorState.rename_document,
            placeholder="Untitled drawing",
            title="Rename this drawing",
            class_name="w-32 lg:w-44 2xl:w-56 text-lg font-bold text-gray-800 bg-transparent border border-transparent rounded-md px-2 py-0.5 hover:border-gray-200 focus:border-violet-400 focus:ring-1 focus:ring-violet-400 outline-none",
        ),
        on_submit=EditorState.rename_from_form,
        reset_on_submit=False,
    )


def share_button() -> rx.Component:
    return rx.el.button(
        rx.icon("link", class_name="w-4 h-4 xl:mr-2"),
        rx.el.span("Copy Link", class_name="hidden xl:inline"),
        on_click=[
            rx.call_script(
                "navigator.clipboard.writeText(window.location.origin + window.location.pathname)"
            ),
            rx.toast("Link copied: everyone who opens it edits this drawing with you"),
        ],
        id="share-link",
        title="Share this drawing for real-time co-editing",
        class_name=f"{_BUTTON} bg-violet-100 text-violet-700 hover:bg-violet-200",
    )


def assistant_button() -> rx.Component:
    """Opens the AI Hub's assistant on this drawing (the ``ai.assist`` intent), in a dialog that
    stays open beside it. Only the platform has an AI Hub."""
    if not own_app():
        return rx.fragment()
    return rx.el.button(
        rx.icon("sparkles", class_name="w-4 h-4 xl:mr-2"),
        rx.el.span("AI Assistant", class_name="hidden xl:inline"),
        on_click=Intent.start(None, "ai.assist", keep_alive=True, single=True, label="AI assistant", in_app=own_app(), room=EditorState.doc_id),
        id="ai-assist",
        title="Tell the AI what to draw on this drawing",
        class_name=f"{_BUTTON} bg-violet-600 text-white hover:bg-violet-700",
    )


def topbar() -> rx.Component:
    """The top navigation bar."""
    return rx.el.header(
        rx.el.div(
            rx.el.div(
                rx.el.a(
                    rx.icon("folder-open", class_name="w-4 h-4"),
                    rx.el.span("My Documents", class_name="hidden xl:inline"),
                    href="/",
                    title="My Documents",
                    class_name="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-100 transition-colors flex-shrink-0",
                ),
                rx.el.div(class_name="hidden lg:block w-px h-6 bg-gray-200 mx-3 flex-shrink-0"),
                rx.icon("shapes", class_name="hidden lg:block w-6 h-6 text-violet-600 mr-1 flex-shrink-0"),
                title_editor(),
                class_name="flex items-center min-w-0 flex-shrink-0",
            ),
            rx.el.div(
                presence(),
                call_button(),
                share_button(),
                rx.el.div(class_name="w-px h-6 bg-gray-200 flex-shrink-0"),
                rx.menu.root(
                    rx.menu.trigger(
                        rx.el.button(
                            rx.icon("file", class_name="w-4 h-4 2xl:mr-2"),
                            rx.el.span("File", class_name="hidden 2xl:inline"),
                            title="File",
                            class_name=f"{_BUTTON} bg-gray-100 text-gray-700 hover:bg-gray-200",
                        ),
                    ),
                    rx.menu.content(
                        rx.menu.item("New drawing", on_click=DocListState.create_document),
                        rx.menu.item("Duplicate", on_click=EditorState.duplicate_document),
                    ),
                ),
                assistant_button(),
                rx.el.button(
                    rx.icon("bot", class_name="w-4 h-4 2xl:mr-2"),
                    rx.el.span("AI Ops", class_name="hidden 2xl:inline"),
                    on_click=UiState.toggle_ai_modal,
                    title="AI Ops",
                    class_name=f"{_BUTTON} bg-emerald-100 text-emerald-700 hover:bg-emerald-200",
                ),
                rx.menu.root(
                    rx.menu.trigger(
                        rx.el.button(
                            rx.icon("download", class_name="w-4 h-4 xl:mr-2"),
                            rx.el.span("Export", class_name="hidden xl:inline"),
                            title="Export",
                            class_name=f"{_BUTTON} bg-gray-900 text-white hover:bg-gray-800",
                        ),
                    ),
                    rx.menu.content(
                        rx.menu.item("Export as JSON", on_click=rx.call_script("window.exportJSON(window.vecdraw.exportShapes())")),
                        rx.menu.item("Export as SVG", on_click=rx.call_script("window.exportSVG()")),
                        rx.menu.item("Export as PNG", on_click=rx.call_script("window.exportPNG()")),
                    ),
                ),
                rx.el.div(class_name="w-px h-6 bg-gray-200 flex-shrink-0"),
                identity(),
                class_name="flex items-center gap-2 min-w-0 overflow-x-auto",
            ),
            class_name="flex items-center justify-between gap-4 px-3 lg:px-6 py-3 h-16",
        ),
        rx.dialog.root(
            rx.dialog.content(
                rx.dialog.title("AI Operations"),
                rx.dialog.description("Paste JSON operations here to control the canvas."),
                rx.cond(
                    UiState.is_ai_docs_open,
                    rx.box(
                        rx.markdown("""
### Supported Operations

*   **addRect**: `{"op": "addRect", "x": 10, "y": 10, "width": 100, "height": 100, "fill": "red", "stroke": "black"}`
*   **addEllipse**: `{"op": "addEllipse", "cx": 100, "cy": 100, "rx": 50, "ry": 50, "fill": "blue"}`
*   **addText**: `{"op": "addText", "x": 10, "y": 10, "content": "Hello", "font_size": 20, "fill": "black"}`
*   **addLine**: `{"op": "addLine", "x": 10, "y": 10, "end_x": 100, "end_y": 100, "stroke": "black", "stroke_width": 2}`
*   **clear**: `{"op": "clear"}`
                        """),
                        class_name="p-4 bg-gray-50 rounded-md mb-4 text-sm overflow-y-auto max-h-60 border border-gray-200",
                    ),
                ),
                rx.text_area(
                    value=UiState.ai_ops_json,
                    on_change=UiState.set_ai_ops_json,
                    placeholder='[{"op": "addRect", "x": 10, "y": 10, "width": 100, "height": 100}]',
                    class_name="h-64 font-mono text-sm my-4",
                ),
                rx.flex(
                    rx.button("Docs", color_scheme="blue", variant="soft", on_click=UiState.toggle_ai_docs),
                    rx.spacer(),
                    rx.dialog.close(
                        rx.button("Cancel", color_scheme="gray", variant="soft")
                    ),
                    rx.button("Run", on_click=UiState.run_ai_ops),
                    spacing="3",
                    justify="end",
                    width="100%",
                ),
            ),
            open=UiState.is_ai_modal_open,
            on_open_change=UiState.toggle_ai_modal,
        ),
        class_name="bg-white border-b border-gray-200 flex-shrink-0 z-10",
    )
