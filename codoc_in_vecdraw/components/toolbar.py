import reflex as rx
from codoc_in_vecdraw.states.editor_state import EditorState


def tool_button(icon_name: str, tool_name: str, label: str) -> rx.Component:
    """A generic tool button for the sidebar."""
    is_active = EditorState.current_tool == tool_name
    return rx.el.button(
        rx.icon(icon_name, class_name="w-6 h-6 mb-1"),
        rx.el.span(label, class_name="text-xs font-medium"),
        on_click=lambda: EditorState.set_tool(tool_name),
        class_name=rx.cond(
            is_active,
            "flex flex-col items-center justify-center p-3 rounded-xl bg-violet-100 text-violet-700 transition-colors w-full",
            "flex flex-col items-center justify-center p-3 rounded-xl hover:bg-gray-100 text-gray-600 transition-colors w-full",
        ),
        title=label,
    )


def toolbar() -> rx.Component:
    """The left sidebar toolbar containing drawing tools."""
    return rx.el.aside(
        rx.el.div(
            rx.el.h2(
                "Tools",
                class_name="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4 px-2",
            ),
            rx.el.div(
                tool_button("mouse-pointer-2", "select", "Select"),
                tool_button("square", "rectangle", "Rectangle"),
                tool_button("circle", "ellipse", "Ellipse"),
                tool_button("minus", "line", "Line"),
                class_name="flex flex-col gap-2",
            ),
            class_name="p-4",
        ),
        class_name="w-24 bg-white border-r border-gray-200 h-full flex-shrink-0 z-10",
    )