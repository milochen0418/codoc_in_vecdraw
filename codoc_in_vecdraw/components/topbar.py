import reflex as rx
from codoc_in_vecdraw.states.editor_state import EditorState


def topbar() -> rx.Component:
    """The top navigation bar."""
    return rx.el.header(
        rx.el.div(
            rx.el.div(
                rx.icon("shapes", class_name="w-6 h-6 text-violet-600 mr-2"),
                rx.el.h1("Vector Editor", class_name="text-lg font-bold text-gray-800"),
                class_name="flex items-center",
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
                rx.cond(
                    EditorState.room_id != "",
                    rx.fragment(
                        rx.el.div(
                            rx.el.span("Room: ", class_name="text-gray-500"),
                            rx.el.span(
                                EditorState.room_id,
                                class_name="font-mono font-bold ml-1",
                            ),
                            class_name="text-xs mr-3 px-2 py-1 bg-gray-100 rounded border border-gray-200",
                        ),
                        rx.el.button(
                            rx.icon("link", class_name="w-4 h-4 mr-2"),
                            "Copy Link",
                            on_click=EditorState.copy_room_link,
                            class_name="flex items-center text-sm font-medium bg-violet-100 text-violet-700 px-3 py-1.5 rounded-lg hover:bg-violet-200 transition-colors mr-2",
                        ),
                    ),
                    rx.el.button(
                        rx.icon("share-2", class_name="w-4 h-4 mr-2"),
                        "Share Link",
                        on_click=EditorState.create_room,
                        class_name="flex items-center text-sm font-medium bg-violet-600 text-white px-3 py-1.5 rounded-lg hover:bg-violet-700 transition-colors mr-2",
                    ),
                ),
                rx.el.button(
                    rx.icon("bot", class_name="w-4 h-4 mr-2"),
                    "AI Ops",
                    on_click=EditorState.toggle_ai_modal,
                    class_name="flex items-center text-sm font-medium bg-emerald-100 text-emerald-700 px-3 py-1.5 rounded-lg hover:bg-emerald-200 transition-colors mr-2",
                ),
                rx.el.button(
                    rx.icon("download", class_name="w-4 h-4 mr-2"),
                    "Export",
                    class_name="flex items-center text-sm font-medium bg-gray-900 text-white px-3 py-1.5 rounded-lg hover:bg-gray-800 transition-colors",
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