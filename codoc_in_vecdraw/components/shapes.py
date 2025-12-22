import reflex as rx
from codoc_in_vecdraw.states.editor_state import Shape, EditorState


def render_selection_overlay(shape: Shape) -> rx.Component:
    """Render the selection handles and border for a selected shape."""
    return rx.cond(
        shape["id"] == EditorState.selected_shape_id,
        rx.match(
            shape["type"],
            (
                "line",
                rx.fragment(
                    rx.el.circle(
                        cx=shape["x"],
                        cy=shape["y"],
                        r=4,
                        fill="white",
                        stroke="#7c3aed",
                        stroke_width=2,
                        class_name="cursor-move",
                    ),
                    rx.el.circle(
                        cx=shape["end_x"],
                        cy=shape["end_y"],
                        r=4,
                        fill="white",
                        stroke="#7c3aed",
                        stroke_width=2,
                        class_name="cursor-move",
                    ),
                ),
            ),
            rx.fragment(
                rx.el.rect(
                    x=shape["x"] - 2,
                    y=shape["y"] - 2,
                    width=shape["width"] + 4,
                    height=shape["height"] + 4,
                    fill="none",
                    stroke="#7c3aed",
                    stroke_width=1,
                    stroke_dasharray="4,4",
                    pointer_events="none",
                ),
                rx.el.rect(
                    x=shape["x"] - 4,
                    y=shape["y"] - 4,
                    width=8,
                    height=8,
                    fill="white",
                    stroke="#7c3aed",
                    stroke_width=1,
                ),
                rx.el.rect(
                    x=shape["x"] + shape["width"] - 4,
                    y=shape["y"] - 4,
                    width=8,
                    height=8,
                    fill="white",
                    stroke="#7c3aed",
                    stroke_width=1,
                ),
                rx.el.rect(
                    x=shape["x"] + shape["width"] - 4,
                    y=shape["y"] + shape["height"] - 4,
                    width=8,
                    height=8,
                    fill="white",
                    stroke="#7c3aed",
                    stroke_width=1,
                ),
                rx.el.rect(
                    x=shape["x"] - 4,
                    y=shape["y"] + shape["height"] - 4,
                    width=8,
                    height=8,
                    fill="white",
                    stroke="#7c3aed",
                    stroke_width=1,
                ),
            ),
        ),
        rx.fragment(),
    )


def render_shape(shape: Shape) -> rx.Component:
    """Render a single shape based on its type."""
    is_selected = shape["id"] == EditorState.selected_shape_id
    common_props = {
        "id": f"shape-{shape['id']}",
        "stroke": shape["stroke"],
        "stroke_width": shape["stroke_width"],
        "fill": shape["fill"],
        "class_name": rx.cond(
            is_selected,
            "cursor-move outline-none",
            "cursor-pointer hover:opacity-80 transition-opacity",
        ),
    }
    shape_element = rx.match(
        shape["type"],
        (
            "rectangle",
            rx.el.rect(
                x=shape["x"],
                y=shape["y"],
                width=shape["width"],
                height=shape["height"],
                **common_props,
            ),
        ),
        (
            "ellipse",
            rx.el.ellipse(
                cx=shape["x"] + shape["width"] / 2,
                cy=shape["y"] + shape["height"] / 2,
                rx=shape["width"] / 2,
                ry=shape["height"] / 2,
                **common_props,
            ),
        ),
        (
            "line",
            rx.el.line(
                x1=shape["x"],
                y1=shape["y"],
                x2=shape["end_x"],
                y2=shape["end_y"],
                **common_props,
            ),
        ),
        rx.fragment(),
    )
    return rx.el.g(shape_element, render_selection_overlay(shape), key=shape["id"])


def render_preview() -> rx.Component:
    """Render the preview of the shape currently being drawn."""
    return rx.fragment()