import reflex as rx
from codoc_in_vecdraw.states.editor_state import EditorState
from codoc_in_vecdraw.components.shapes import render_shape, render_preview
from reflex_mouse_track import mouse_track

GET_COORDS_SCRIPT = """
(function() {
    var elem = document.getElementById('main-canvas');
    if (!elem) return {x: 0, y: 0};
    var rect = elem.getBoundingClientRect();
    var e = window.event;
    if (!e) {
        // Try to find event in arguments if window.event is missing (Firefox)
        try { e = arguments[0]; } catch(err) {}
    }
    if (!e) return {x: 0, y: 0};
    
    return {
        x: Math.round(e.clientX - rect.left),
        y: Math.round(e.clientY - rect.top)
    };
})()
"""

def canvas() -> rx.Component:
    """The main drawing canvas area."""
    return rx.box(
        rx.box(
            rx.el.div(
                class_name="absolute inset-0 opacity-[0.03] pointer-events-none",
                style={
                    "backgroundImage": "radial-gradient(circle, #000 1px, transparent 1px)",
                    "backgroundSize": "20px 20px",
                    "backgroundPosition": f"{EditorState.pan_x}px {EditorState.pan_y}px",
                },
            ),
            rx.el.svg(
                rx.el.rect(
                    width="100%", height="100%", fill="transparent", id="canvas-bg"
                ),
                rx.el.g(
                    rx.foreach(EditorState.shapes, render_shape),
                    rx.cond(EditorState.is_drawing, render_preview(), rx.fragment()),
                    style={
                        "pointerEvents": rx.cond(EditorState.is_drawing, "none", "auto"),
                        "transform": f"translate({EditorState.pan_x}px, {EditorState.pan_y}px)",
                    },
                ),
                width="100%",
                height="100%",
                class_name="absolute inset-0 w-full h-full touch-none block",
                id="main-svg",
            ),
            class_name="w-full h-full",
        ),
        id="main-canvas",
        class_name="relative flex-1 w-full h-full bg-gray-50 overflow-hidden touch-none",
        style={
            "cursor": rx.cond(
                EditorState.current_tool == "hand",
                rx.cond(EditorState.is_panning, "grabbing", "grab"),
                rx.cond(
                    EditorState.current_tool == "select", "default", "crosshair"
                )
            )
        },
        on_mouse_down=rx.call_script(GET_COORDS_SCRIPT, callback=EditorState.handle_mouse_down),
        on_mouse_move=rx.call_script(GET_COORDS_SCRIPT, callback=EditorState.handle_mouse_move),
        on_mouse_up=rx.call_script(GET_COORDS_SCRIPT, callback=EditorState.handle_mouse_up),
        on_mouse_leave=rx.call_script(GET_COORDS_SCRIPT, callback=EditorState.handle_mouse_up),
    )