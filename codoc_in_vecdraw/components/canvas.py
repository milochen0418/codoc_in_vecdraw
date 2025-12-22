import reflex as rx
from codoc_in_vecdraw.states.editor_state import EditorState
from codoc_in_vecdraw.components.shapes import render_shape, render_preview
from reflex_mouse_track import mouse_track


def canvas() -> rx.Component:
    """The main drawing canvas area."""
    return mouse_track(
        rx.box(
            rx.el.div(
                class_name="absolute inset-0 opacity-[0.03] pointer-events-none",
                style={
                    "backgroundImage": "radial-gradient(circle, #000 1px, transparent 1px)",
                    "backgroundSize": "20px 20px",
                },
            ),
            rx.el.svg(
                rx.el.rect(
                    width="100%", height="100%", fill="transparent", id="canvas-bg"
                ),
                rx.el.g(
                    rx.foreach(EditorState.shapes, render_shape),
                    style={
                        "pointerEvents": rx.cond(EditorState.is_drawing, "none", "auto")
                    },
                ),
                rx.cond(EditorState.is_drawing, render_preview(), rx.fragment()),
                width="100%",
                height="100%",
                class_name="absolute inset-0 w-full h-full touch-none block",
                id="main-svg",
            ),
            class_name="w-full h-full",
            on_mouse_move=rx.call_script(
                "([event.clientX, event.clientY])",
                callback=EditorState.handle_mouse_move.throttle(20),
            ),
        ),
        id="main-canvas",
        class_name="relative flex-1 w-full h-full bg-gray-50 overflow-hidden touch-none",
        style={
            "cursor": rx.cond(
                EditorState.current_tool == "select", "default", "crosshair"
            )
        },
        on_mouse_down=EditorState.handle_mouse_down,
        on_mouse_up=EditorState.handle_mouse_up,
        on_mouse_leave=EditorState.handle_mouse_up,
    )