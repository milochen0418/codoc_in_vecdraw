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
                    class_name="cursor-nw-resize",
                ),
                rx.el.rect(
                    x=shape["x"] + shape["width"] - 4,
                    y=shape["y"] - 4,
                    width=8,
                    height=8,
                    fill="white",
                    stroke="#7c3aed",
                    stroke_width=1,
                    class_name="cursor-ne-resize",
                ),
                rx.el.rect(
                    x=shape["x"] + shape["width"] - 4,
                    y=shape["y"] + shape["height"] - 4,
                    width=8,
                    height=8,
                    fill="white",
                    stroke="#7c3aed",
                    stroke_width=1,
                    class_name="cursor-se-resize",
                ),
                rx.el.rect(
                    x=shape["x"] - 4,
                    y=shape["y"] + shape["height"] - 4,
                    width=8,
                    height=8,
                    fill="white",
                    stroke="#7c3aed",
                    stroke_width=1,
                    class_name="cursor-sw-resize",
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
        (
            "triangle",
            rx.el.polygon(
                points=f"{shape['x'] + shape['width']/2},{shape['y']} {shape['x']},{shape['y'] + shape['height']} {shape['x'] + shape['width']},{shape['y'] + shape['height']}",
                **common_props,
            ),
        ),
        (
            "image",
            rx.el.image(
                tag="image",
                # Pass SVG attributes as custom_attrs to avoid validation/filtering by Img component
                # and to ensure they are passed to the DOM element.
                # Note: Reflex might still try to validate known props, so we use custom_attrs for safety.
                # However, custom_attrs usually takes a dict of strings.
                # Let's try passing them as direct args first, but if they were dropped, maybe they are not valid for Img.
                # Img has src, alt, etc. It does NOT have x, y, width, height (as simple props maybe?).
                # Actually width/height are valid for Img.
                # But href is NOT.
                # So let's use custom_attrs for href and others.
                custom_attrs={
                    "href": rx.get_upload_url(shape["src"]),
                    "x": shape["x"],
                    "y": shape["y"],
                    "width": shape["width"],
                    "height": shape["height"],
                    "preserveAspectRatio": "none",
                },
                class_name=rx.cond(
                    is_selected,
                    "cursor-move outline-none",
                    "cursor-pointer hover:opacity-80 transition-opacity",
                ),
            ),
        ),
        (
            "text",
            rx.el.text(
                shape["content"],
                x=shape["x"],
                y=shape["y"],
                font_size=shape["height"],
                fill=shape["fill"],
                dominant_baseline="hanging",
                class_name=rx.cond(
                    is_selected,
                    "cursor-move outline-none select-none",
                    "cursor-pointer hover:opacity-80 transition-opacity select-none",
                ),
                style={"userSelect": "none"},
            ),
        ),
        (
            "pencil",
            rx.el.path(
                d=shape["path_data"],
                fill="none",
                stroke=shape["stroke"],
                stroke_width=shape["stroke_width"],
                stroke_linecap="round",
                stroke_linejoin="round",
                class_name=rx.cond(
                    is_selected,
                    "cursor-move outline-none",
                    "cursor-pointer hover:opacity-80 transition-opacity",
                ),
            ),
        ),
        rx.fragment(),
    )
    return rx.el.g(shape_element, render_selection_overlay(shape), key=shape["id"])


def render_preview() -> rx.Component:
    """Render the preview of the shape currently being drawn."""
    return rx.cond(
        EditorState.is_drawing & (EditorState.current_tool != "select"),
        rx.match(
            EditorState.current_tool,
            (
                "rectangle",
                rx.el.rect(
                    x=rx.cond(
                        EditorState.start_x < EditorState.current_x,
                        EditorState.start_x,
                        EditorState.current_x,
                    ),
                    y=rx.cond(
                        EditorState.start_y < EditorState.current_y,
                        EditorState.start_y,
                        EditorState.current_y,
                    ),
                    width=abs(EditorState.current_x - EditorState.start_x),
                    height=abs(EditorState.current_y - EditorState.start_y),
                    fill="#e9d5ff",
                    stroke="#7c3aed",
                    stroke_width=2,
                    opacity=0.5,
                ),
            ),
            (
                "ellipse",
                rx.el.ellipse(
                    cx=(EditorState.start_x + EditorState.current_x) / 2,
                    cy=(EditorState.start_y + EditorState.current_y) / 2,
                    rx=abs(EditorState.current_x - EditorState.start_x) / 2,
                    ry=abs(EditorState.current_y - EditorState.start_y) / 2,
                    fill="#e9d5ff",
                    stroke="#7c3aed",
                    stroke_width=2,
                    opacity=0.5,
                ),
            ),
            (
                "line",
                rx.el.line(
                    x1=EditorState.start_x,
                    y1=EditorState.start_y,
                    x2=EditorState.current_x,
                    y2=EditorState.current_y,
                    stroke="#7c3aed",
                    stroke_width=2,
                    opacity=0.5,
                ),
            ),
            (
                "triangle",
                rx.el.polygon(
                    points=f"{(EditorState.start_x + EditorState.current_x)/2},{EditorState.start_y} {EditorState.start_x},{EditorState.current_y} {EditorState.current_x},{EditorState.current_y}",
                    fill="#e9d5ff",
                    stroke="#7c3aed",
                    stroke_width=2,
                    opacity=0.5,
                ),
            ),
            (
                "pencil",
                rx.el.path(
                    d=EditorState.current_path_string,
                    fill="none",
                    stroke="#7c3aed",
                    stroke_width=2,
                    opacity=0.5,
                ),
            ),
            rx.fragment(),
        ),
        rx.fragment(),
    )