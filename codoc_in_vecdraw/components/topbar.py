import reflex as rx
from codoc_in_vecdraw.states.doc_list_state import DocListState
from codoc_in_vecdraw.states.editor_state import EditorState


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
            class_name="w-56 text-lg font-bold text-gray-800 bg-transparent border border-transparent rounded-md px-2 py-0.5 hover:border-gray-200 focus:border-violet-400 focus:ring-1 focus:ring-violet-400 outline-none",
        ),
        on_submit=EditorState.rename_from_form,
        reset_on_submit=False,
    )


def topbar() -> rx.Component:
    """The top navigation bar."""
    return rx.el.header(
        rx.el.div(
            rx.el.div(
                rx.el.a(
                    rx.icon("folder-open", class_name="w-4 h-4"),
                    "My Documents",
                    href="/",
                    class_name="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-100 transition-colors flex-shrink-0",
                ),
                rx.el.div(class_name="w-px h-6 bg-gray-200 mx-3 flex-shrink-0"),
                rx.icon("shapes", class_name="w-6 h-6 text-violet-600 mr-1 flex-shrink-0"),
                title_editor(),
                rx.el.span(
                    EditorState.doc_id,
                    title="Document ID",
                    class_name="text-xs font-mono text-gray-400",
                ),
                class_name="flex items-center min-w-0",
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.button(
                        rx.icon("undo-2", class_name="w-4 h-4"),
                        on_click=EditorState.undo,
                        disabled=~EditorState.past,
                        class_name="p-2 text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-30 disabled:hover:bg-transparent transition-colors",
                        title="Undo",
                    ),
                    rx.el.button(
                        rx.icon("redo-2", class_name="w-4 h-4"),
                        on_click=EditorState.redo,
                        disabled=~EditorState.future,
                        class_name="p-2 text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-30 disabled:hover:bg-transparent transition-colors",
                        title="Redo",
                    ),
                    class_name="flex items-center gap-1 mr-6 border-r border-gray-200 pr-4",
                ),
                rx.el.span(
                    f"Mode: ",
                    rx.el.span(
                        EditorState.current_tool, class_name="font-semibold capitalize"
                    ),
                    class_name="text-sm text-gray-500 mr-4",
                ),
                rx.el.button(
                    rx.icon("link", class_name="w-4 h-4 mr-2"),
                    "Copy Link",
                    on_click=[
                        rx.call_script(
                            "navigator.clipboard.writeText(window.location.origin + window.location.pathname)"
                        ),
                        rx.toast("Link copied: everyone who opens it edits this drawing with you"),
                    ],
                    title="Share this drawing for real-time co-editing",
                    class_name="flex items-center text-sm font-medium bg-violet-100 text-violet-700 px-3 py-1.5 rounded-lg hover:bg-violet-200 transition-colors mr-2",
                ),
                rx.menu.root(
                    rx.menu.trigger(
                        rx.el.button(
                            rx.icon("file", class_name="w-4 h-4 mr-2"),
                            "File",
                            class_name="flex items-center text-sm font-medium bg-gray-100 text-gray-700 px-3 py-1.5 rounded-lg hover:bg-gray-200 transition-colors mr-2",
                        ),
                    ),
                    rx.menu.content(
                        rx.menu.item("New drawing", on_click=DocListState.create_document),
                        rx.menu.item("Duplicate", on_click=EditorState.duplicate_document),
                    ),
                ),
                rx.el.button(
                    rx.icon("bot", class_name="w-4 h-4 mr-2"),
                    "AI Ops",
                    on_click=EditorState.toggle_ai_modal,
                    class_name="flex items-center text-sm font-medium bg-emerald-100 text-emerald-700 px-3 py-1.5 rounded-lg hover:bg-emerald-200 transition-colors mr-2",
                ),
                rx.menu.root(
                    rx.menu.trigger(
                        rx.el.button(
                            rx.icon("download", class_name="w-4 h-4 mr-2"),
                            "Export",
                            class_name="flex items-center text-sm font-medium bg-gray-900 text-white px-3 py-1.5 rounded-lg hover:bg-gray-800 transition-colors",
                        ),
                    ),
                    rx.menu.content(
                        rx.menu.item("Export as JSON", on_click=rx.call_script(f"window.exportJSON(atob('{EditorState.json_data_base64}'))")),
                        rx.menu.item("Export as SVG", on_click=rx.call_script("window.exportSVG()")),
                        rx.menu.item("Export as PNG", on_click=rx.call_script("window.exportPNG()")),
                    ),
                ),
                class_name="flex items-center",
            ),
            class_name="flex items-center justify-between px-6 py-3 h-16",
        ),
        rx.dialog.root(
            rx.dialog.content(
                rx.dialog.title("AI Operations"),
                rx.dialog.description("Paste JSON operations here to control the canvas."),
                rx.cond(
                    EditorState.is_ai_docs_open,
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
                    value=EditorState.ai_ops_json,
                    on_change=EditorState.set_ai_ops_json,
                    placeholder='[{"op": "addRect", "x": 10, "y": 10, "width": 100, "height": 100}]',
                    class_name="h-64 font-mono text-sm my-4",
                ),
                rx.flex(
                    rx.button("Docs", color_scheme="blue", variant="soft", on_click=EditorState.toggle_ai_docs),
                    rx.spacer(),
                    rx.dialog.close(
                        rx.button("Cancel", color_scheme="gray", variant="soft")
                    ),
                    rx.button("Run", on_click=EditorState.run_ai_ops),
                    spacing="3",
                    justify="end",
                    width="100%",
                ),
            ),
            open=EditorState.is_ai_modal_open,
            on_open_change=EditorState.toggle_ai_modal,
        ),
        class_name="bg-white border-b border-gray-200 flex-shrink-0 z-10",
    )