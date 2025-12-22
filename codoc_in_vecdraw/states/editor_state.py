import reflex as rx
from typing import TypedDict, Any
import uuid
import copy
import random
import string
import dataclasses


@dataclasses.dataclass
class Point:
    x: int
    y: int


class Shape(TypedDict):
    id: str
    type: str
    x: int
    y: int
    width: int
    height: int
    fill: str
    stroke: str
    stroke_width: int
    end_x: int
    end_y: int


class EditorState(rx.SharedState):
    """State for the Vector Graphics Editor."""

    shapes: list[Shape] = []
    selected_shape_id: str = ""
    current_tool: str = "select"
    is_drawing: bool = False
    is_dragging: bool = False
    start_x: int = 0
    start_y: int = 0
    current_x: int = 0
    current_y: int = 0
    drag_offset_x: int = 0
    drag_offset_y: int = 0
    past: list[list[Shape]] = []
    future: list[list[Shape]] = []
    snapshot_shapes: list[Shape] = []
    room_id: str = ""
    offset_x: int = 96
    offset_y: int = 64

    @rx.event
    async def on_load(self):
        """Handle page load to join room if specified."""
        room_param = self.router.url.query_parameters.get("room")
        if room_param:
            self.room_id = room_param
            safe_token = room_param.replace("_", "-")
            await self._link_to(safe_token)

    @rx.event
    def create_room(self):
        """Generate a room ID, copy link, and redirect."""
        new_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        origin = self.router.headers.origin or "http://localhost:3000"
        full_url = f"{origin}/?room={new_id}"
        return [
            rx.set_clipboard(full_url),
            rx.toast("Link copied! Redirecting to new room..."),
            rx.redirect(f"/?room={new_id}"),
        ]

    @rx.event
    def copy_room_link(self):
        """Copy the current room link to clipboard."""
        origin = self.router.headers.origin or "http://localhost:3000"
        full_url = f"{origin}/?room={self.room_id}"
        return [rx.set_clipboard(full_url), rx.toast("Share link copied to clipboard")]

    @rx.var
    def selected_shape(self) -> Shape:
        """Return the currently selected shape or a default empty shape."""
        for shape in self.shapes:
            if shape["id"] == self.selected_shape_id:
                return shape
        return {
            "id": "",
            "type": "",
            "x": 0,
            "y": 0,
            "width": 0,
            "height": 0,
            "fill": "",
            "stroke": "",
            "stroke_width": 0,
            "end_x": 0,
            "end_y": 0,
        }

    def _save_to_history(self):
        """Save current state to history stack."""
        self.past.append(copy.deepcopy(self.shapes))
        self.future.clear()

    @rx.event
    def set_tool(self, tool: str):
        """Set the active drawing tool."""
        self.current_tool = tool
        self.selected_shape_id = ""

    @rx.event
    def handle_mouse_down(self, point: Point):
        """Handle mouse down on canvas."""
        x = point.x - self.offset_x
        y = point.y - self.offset_y
        self.start_x = x
        self.start_y = y
        self.current_x = x
        self.current_y = y
        if self.current_tool == "select":
            found_shape_id = ""
            for shape in reversed(self.shapes):
                if shape["type"] == "rectangle":
                    if (
                        shape["x"] <= x <= shape["x"] + shape["width"]
                        and shape["y"] <= y <= shape["y"] + shape["height"]
                    ):
                        found_shape_id = shape["id"]
                        break
                elif shape["type"] == "ellipse":
                    cx = shape["x"] + shape["width"] / 2
                    cy = shape["y"] + shape["height"] / 2
                    rx_val = shape["width"] / 2
                    ry_val = shape["height"] / 2
                    if (x - cx) ** 2 / rx_val**2 + (y - cy) ** 2 / ry_val**2 <= 1:
                        found_shape_id = shape["id"]
                        break
                elif shape["type"] == "line":
                    lx = min(shape["x"], shape["end_x"])
                    rx_ = max(shape["x"], shape["end_x"])
                    ty = min(shape["y"], shape["end_y"])
                    by = max(shape["y"], shape["end_y"])
                    if lx - 5 <= x <= rx_ + 5 and ty - 5 <= y <= by + 5:
                        found_shape_id = shape["id"]
                        break
            if found_shape_id:
                self.selected_shape_id = found_shape_id
                self.is_dragging = True
                self.drag_offset_x = x
                self.drag_offset_y = y
                self.snapshot_shapes = copy.deepcopy(self.shapes)
            else:
                self.selected_shape_id = ""
        else:
            self.is_drawing = True
            self.selected_shape_id = ""
            self.snapshot_shapes = copy.deepcopy(self.shapes)

    @rx.event
    def handle_mouse_move(self, data: list):
        """Handle mouse move on canvas (for dragging)."""
        if not data or len(data) < 2 or data[0] is None or data[1] is None:
            return
        x = int(data[0]) - self.offset_x
        y = int(data[1]) - self.offset_y
        self.current_x = x
        self.current_y = y
        if self.is_dragging and self.selected_shape_id:
            dx = x - self.drag_offset_x
            dy = y - self.drag_offset_y
            self.drag_offset_x = x
            self.drag_offset_y = y
            new_shapes = []
            for shape in self.shapes:
                if shape["id"] == self.selected_shape_id:
                    s = shape.copy()
                    s["x"] += dx
                    s["y"] += dy
                    if s["type"] == "line":
                        s["end_x"] += dx
                        s["end_y"] += dy
                    new_shapes.append(s)
                else:
                    new_shapes.append(shape)
            self.shapes = new_shapes

    @rx.event
    def handle_mouse_up(self, point: Point | None = None):
        """Handle mouse up on canvas."""
        if point:
            self.current_x = point.x - self.offset_x
            self.current_y = point.y - self.offset_y
        if self.is_drawing and self.current_tool != "select":
            x = min(self.start_x, self.current_x)
            y = min(self.start_y, self.current_y)
            width = abs(self.current_x - self.start_x)
            height = abs(self.current_y - self.start_y)
            if width > 2 or height > 2 or self.current_tool == "line":
                self.past.append(self.snapshot_shapes)
                self.future.clear()
                new_shape: Shape = {
                    "id": str(uuid.uuid4()),
                    "type": self.current_tool,
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                    "fill": "transparent" if self.current_tool == "line" else "#e9d5ff",
                    "stroke": "#7c3aed",
                    "stroke_width": 2,
                    "end_x": 0,
                    "end_y": 0,
                }
                if self.current_tool == "line":
                    new_shape["x"] = self.start_x
                    new_shape["y"] = self.start_y
                    new_shape["end_x"] = self.current_x
                    new_shape["end_y"] = self.current_y
                self.shapes.append(new_shape)
                self.selected_shape_id = new_shape["id"]
        elif self.is_dragging:
            if self.shapes != self.snapshot_shapes:
                self.past.append(self.snapshot_shapes)
                self.future.clear()
        self.is_drawing = False
        self.is_dragging = False
        self.snapshot_shapes = []

    @rx.event
    def select_shape(self, shape_id: str):
        """Select a specific shape."""
        if self.current_tool == "select":
            self.selected_shape_id = shape_id

    @rx.event
    def update_property(self, key: str, value: Any):
        """Update a property of the selected shape."""
        if not self.selected_shape_id:
            return
        self._save_to_history()
        new_shapes = []
        for shape in self.shapes:
            if shape["id"] == self.selected_shape_id:
                s = shape.copy()
                s[key] = value
                new_shapes.append(s)
            else:
                new_shapes.append(shape)
        self.shapes = new_shapes

    @rx.event
    def delete_selected(self):
        """Delete the currently selected shape."""
        if not self.selected_shape_id:
            return
        self._save_to_history()
        self.shapes = [s for s in self.shapes if s["id"] != self.selected_shape_id]
        self.selected_shape_id = ""

    @rx.event
    def undo(self):
        """Undo the last action."""
        if self.past:
            self.future.append(copy.deepcopy(self.shapes))
            self.shapes = self.past.pop()
            self.selected_shape_id = ""

    @rx.event
    def redo(self):
        """Redo the last undone action."""
        if self.future:
            self.past.append(copy.deepcopy(self.shapes))
            self.shapes = self.future.pop()
            self.selected_shape_id = ""