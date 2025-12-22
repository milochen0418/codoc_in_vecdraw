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
                    rx.icon("download", class_name="w-4 h-4 mr-2"),
                    "Export",
                    class_name="flex items-center text-sm font-medium bg-gray-900 text-white px-3 py-1.5 rounded-lg hover:bg-gray-800 transition-colors",
                ),
                class_name="flex items-center",
            ),
            class_name="flex items-center justify-between px-6 py-3 h-16",
        ),
        class_name="bg-white border-b border-gray-200 flex-shrink-0 z-10",
    )