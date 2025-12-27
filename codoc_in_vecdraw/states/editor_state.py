import reflex as rx
from typing import TypedDict, Any
import uuid
import copy
import random
import string
import json
import base64
import dataclasses
from collections import defaultdict

# Global store for pending AI operations
# Key: room_id (str), Value: list of op dicts
PENDING_AI_OPS = defaultdict(list)

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
    content: str
    points: list[dict[str, int]]
    path_data: str
    src: str


class EditorState(rx.SharedState):
    """State for the Vector Graphics Editor."""

    shapes: list[Shape] = []
    selected_shape_id: str = ""
    current_tool: str = "select"
    is_drawing: bool = False
    is_dragging: bool = False
    is_panning: bool = False
    active_handle: str = ""
    start_x: int = 0
    start_y: int = 0
    current_x: int = 0
    current_y: int = 0
    drag_offset_x: int = 0
    drag_offset_y: int = 0
    pan_x: int = 0
    pan_y: int = 0
    current_points: list[dict[str, int]] = []
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
            "content": "",
            "points": [],
            "path_data": "",
            "src": "",
        }

    @rx.var
    def current_path_string(self) -> str:
        """Generate SVG path data for the current pencil drawing."""
        if not self.current_points:
            return ""
        
        # Start with Move to first point
        d = f"M {self.current_points[0]['x']} {self.current_points[0]['y']}"
        
        # Line to subsequent points
        for p in self.current_points[1:]:
            d += f" L {p['x']} {p['y']}"
            
        return d

    def _get_handle_under_point(self, x: int, y: int, shape: Shape) -> str:
        """Check if a point is over a resize handle."""
        if not shape:
            return ""
            
        # Handle size is roughly 8x8 (radius 4 or rect 8x8 centered)
        # Let's use a hit radius of 6 for easier clicking
        hit_r = 6
        
        if shape["type"] == "line":
            # Start point
            if abs(x - shape["x"]) <= hit_r and abs(y - shape["y"]) <= hit_r:
                return "start"
            # End point
            if abs(x - shape["end_x"]) <= hit_r and abs(y - shape["end_y"]) <= hit_r:
                return "end"
        else:
            # Rectangle / Ellipse handles
            # NW
            if abs(x - shape["x"]) <= hit_r and abs(y - shape["y"]) <= hit_r:
                return "nw"
            # NE
            if abs(x - (shape["x"] + shape["width"])) <= hit_r and abs(y - shape["y"]) <= hit_r:
                return "ne"
            # SE
            if abs(x - (shape["x"] + shape["width"])) <= hit_r and abs(y - (shape["y"] + shape["height"])) <= hit_r:
                return "se"
            # SW
            if abs(x - shape["x"]) <= hit_r and abs(y - (shape["y"] + shape["height"])) <= hit_r:
                return "sw"
                
        return ""

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
    def handle_mouse_down(self, point: dict[str, int]):
        """Handle mouse down on canvas."""
        # Debug logging
        print(f"Mouse Down: {point}")
        
        # Ensure point is a dictionary and has x, y
        if not isinstance(point, dict) or "x" not in point or "y" not in point:
            print("Invalid point data")
            return
            
        if point["x"] is None or point["y"] is None:
            print("Point coordinates are None")
            return

        raw_x = point["x"]
        raw_y = point["y"]
        
        if self.current_tool == "hand":
            self.is_panning = True
            self.start_x = raw_x
            self.start_y = raw_y
            return

        # Adjust for panning
        x = raw_x - self.pan_x
        y = raw_y - self.pan_y
        
        print(f"Click at: {x}, {y} (Raw: {point['x']}, {point['y']})")
        print(f"Selected Shape ID: {self.selected_shape_id}")
        
        self.start_x = x
        self.start_y = y
        self.current_x = x
        self.current_y = y
        
        # Check if we clicked a handle of the selected shape
        if self.selected_shape_id:
            selected_shape = next((s for s in self.shapes if s["id"] == self.selected_shape_id), None)
            if selected_shape:
                print(f"Checking handles for shape: {selected_shape}")
                handle = self._get_handle_under_point(x, y, selected_shape)
                print(f"Handle found: {handle}")
                
                if handle:
                    self.active_handle = handle
                    self.is_dragging = True
                    self.snapshot_shapes = copy.deepcopy(self.shapes)
                    self.drag_offset_x = x
                    self.drag_offset_y = y
                    return

        if self.current_tool == "select":
            found_shape_id = ""
            for shape in reversed(self.shapes):
                if shape["type"] in ["rectangle", "image", "text", "triangle", "pencil"]:
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
        elif self.current_tool == "text":
            self._save_to_history()
            new_shape: Shape = {
                "id": str(uuid.uuid4()),
                "type": "text",
                "x": x,
                "y": y,
                "width": 100,
                "height": 30,
                "fill": "#000000",
                "stroke": "none",
                "stroke_width": 0,
                "end_x": 0,
                "end_y": 0,
                "content": "Double click to edit",
                "points": [],
                "path_data": "",
                "src": "",
            }
            self.shapes.append(new_shape)
            self.selected_shape_id = new_shape["id"]
            self.set_tool("select")
        elif self.current_tool == "pencil":
            self.is_drawing = True
            self.selected_shape_id = ""
            self.snapshot_shapes = copy.deepcopy(self.shapes)
            self.current_points = [{"x": x, "y": y}]
        else:
            self.is_drawing = True
            self.selected_shape_id = ""
            self.snapshot_shapes = copy.deepcopy(self.shapes)

    @rx.event
    def handle_mouse_move(self, data: dict[str, int]):
        """Handle mouse move on canvas (for dragging)."""
        # Ensure data is valid
        if not data or not isinstance(data, dict) or "x" not in data or "y" not in data:
            return
            
        if data["x"] is None or data["y"] is None:
            return

        raw_x = data["x"]
        raw_y = data["y"]
        
        if self.is_panning:
            dx = raw_x - self.start_x
            dy = raw_y - self.start_y
            self.pan_x += dx
            self.pan_y += dy
            self.start_x = raw_x
            self.start_y = raw_y
            return

        x = raw_x - self.pan_x
        y = raw_y - self.pan_y
        self.current_x = x
        self.current_y = y
        
        if self.is_drawing and self.current_tool == "pencil":
            self.current_points.append({"x": x, "y": y})
            return

        # Debug log for dragging state
        if self.is_dragging:
            # print(f"Dragging active: handle={self.active_handle}, shape={self.selected_shape_id}")
            pass
        
        if self.is_dragging and self.selected_shape_id:
            # Log only when actually dragging/resizing
            if self.active_handle:
                print(f"Resizing: Handle={self.active_handle}, Pos=({x}, {y})")
            else:
                print(f"Dragging: Pos=({x}, {y})")

            dx = x - self.drag_offset_x
            dy = y - self.drag_offset_y
            self.drag_offset_x = x
            self.drag_offset_y = y
            
            new_shapes = []
            for shape in self.shapes:
                if shape["id"] == self.selected_shape_id:
                    s = shape.copy()
                    
                    if self.active_handle:
                        # Handle resizing
                        if s["type"] == "line":
                            if self.active_handle == "start":
                                s["x"] += dx
                                s["y"] += dy
                            elif self.active_handle == "end":
                                s["end_x"] += dx
                                s["end_y"] += dy
                        else:
                            # Rectangle / Ellipse / Triangle / Image / Text resizing
                            if "n" in self.active_handle:
                                s["y"] += dy
                                s["height"] -= dy
                            if "s" in self.active_handle:
                                s["height"] += dy
                            if "w" in self.active_handle:
                                s["x"] += dx
                                s["width"] -= dx
                            if "e" in self.active_handle:
                                s["width"] += dx
                                
                            # Handle negative dimensions (flipping)
                            if s["width"] < 0:
                                s["width"] = abs(s["width"])
                                s["x"] -= s["width"]
                                # Flip handle horizontally
                                self.active_handle = self.active_handle.translate(str.maketrans("we", "ew"))
                                
                            if s["height"] < 0:
                                s["height"] = abs(s["height"])
                                s["y"] -= s["height"]
                                # Flip handle vertically
                                self.active_handle = self.active_handle.translate(str.maketrans("ns", "sn"))
                    else:
                        # Handle moving
                        s["x"] += dx
                        s["y"] += dy
                        if s["type"] == "line":
                            s["end_x"] += dx
                            s["end_y"] += dy
                        elif s["type"] == "pencil":
                            # Move all points
                            for p in s["points"]:
                                p["x"] += dx
                                p["y"] += dy
                            # Recompute path_data
                            d = f"M {s['points'][0]['x']} {s['points'][0]['y']}"
                            for p in s['points'][1:]:
                                d += f" L {p['x']} {p['y']}"
                            s["path_data"] = d
                            
                    new_shapes.append(s)
                else:
                    new_shapes.append(shape)
            self.shapes = new_shapes

    @rx.event
    def handle_mouse_up(self, point: dict[str, int] | None = None):
        """Handle mouse up on canvas."""
        print("Mouse Up")
        if point and isinstance(point, dict) and "x" in point and "y" in point:
            if point["x"] is not None and point["y"] is not None:
                # Adjust for panning if not panning tool (though mouse up usually just ends things)
                # But we need current_x/y to be correct for shape creation
                raw_x = point["x"]
                raw_y = point["y"]
                if not self.is_panning:
                    self.current_x = raw_x - self.pan_x
                    self.current_y = raw_y - self.pan_y
            
        if self.is_panning:
            self.is_panning = False
            return

        # Reset active handle and dragging state
        self.active_handle = ""
        self.is_dragging = False
        
        if self.is_drawing and self.current_tool != "select":
            # Ensure coordinates are valid integers
            start_x = self.start_x if self.start_x is not None else 0
            start_y = self.start_y if self.start_y is not None else 0
            current_x = self.current_x if self.current_x is not None else 0
            current_y = self.current_y if self.current_y is not None else 0
            
            x = min(start_x, current_x)
            y = min(start_y, current_y)
            width = abs(current_x - start_x)
            height = abs(current_y - start_y)
            
            if self.current_tool == "pencil":
                if len(self.current_points) > 1:
                    self.past.append(self.snapshot_shapes)
                    self.future.clear()
                    # Calculate bounding box for pencil
                    xs = [p["x"] for p in self.current_points]
                    ys = [p["y"] for p in self.current_points]
                    min_x, max_x = min(xs), max(xs)
                    min_y, max_y = min(ys), max(ys)
                    
                    # Compute path data
                    d = f"M {self.current_points[0]['x']} {self.current_points[0]['y']}"
                    for p in self.current_points[1:]:
                        d += f" L {p['x']} {p['y']}"
                    
                    new_shape: Shape = {
                        "id": str(uuid.uuid4()),
                        "type": "pencil",
                        "x": min_x,
                        "y": min_y,
                        "width": max_x - min_x,
                        "height": max_y - min_y,
                        "fill": "none",
                        "stroke": "#7c3aed",
                        "stroke_width": 2,
                        "end_x": 0,
                        "end_y": 0,
                        "content": "",
                        "points": self.current_points,
                        "path_data": d,
                        "src": "",
                    }
                    self.shapes.append(new_shape)
                    self.selected_shape_id = new_shape["id"]
            elif width > 2 or height > 2 or self.current_tool == "line":
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
                    "content": "",
                    "points": [],
                    "path_data": "",
                    "src": "",
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
        self.current_points = []

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

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        """Handle image upload."""
        for file in files:
            upload_data = await file.read()
            # Generate a safe filename using UUID to avoid encoding issues
            ext = file.filename.split(".")[-1] if "." in file.filename else "png"
            safe_filename = f"{uuid.uuid4()}.{ext}"
            
            outfile = rx.get_upload_dir() / safe_filename
            with open(outfile, "wb") as f:
                f.write(upload_data)
            
            # Add image shape
            self._save_to_history()
            print(f"DEBUG: Adding image shape for {safe_filename}")
            new_shape: Shape = {
                "id": str(uuid.uuid4()),
                "type": "image",
                "x": 100 - self.pan_x,
                "y": 100 - self.pan_y,
                "width": 200,
                "height": 200,
                "fill": "none",
                "stroke": "none",
                "stroke_width": 0,
                "end_x": 0,
                "end_y": 0,
                "content": "",
                "points": [],
                "path_data": "",
                "src": safe_filename,
            }
            # Explicitly reassign shapes to ensure state update triggers
            self.shapes = self.shapes + [new_shape]
            self.selected_shape_id = new_shape["id"]

    # --- AI Operations Interface ---
    
    ai_ops_json: str = ""
    is_ai_modal_open: bool = False
    is_ai_docs_open: bool = False

    @rx.event
    def toggle_ai_modal(self):
        self.is_ai_modal_open = not self.is_ai_modal_open

    @rx.event
    def toggle_ai_docs(self):
        self.is_ai_docs_open = not self.is_ai_docs_open

    @rx.event
    def set_ai_ops_json(self, value: str):
        self.ai_ops_json = value

    @rx.event
    def run_ai_ops(self):
        """Parse and execute AI operations from JSON."""
        import json
        try:
            ops = json.loads(self.ai_ops_json)
            if not isinstance(ops, list):
                ops = [ops]
            
            self._save_to_history()
            
            for op in ops:
                op_type = op.get("op")
                
                if op_type == "clear":
                    self.shapes = []
                    continue
                
                # Common properties
                shape_id = op.get("id", str(uuid.uuid4()))
                x = op.get("x", 0)
                y = op.get("y", 0)
                fill = op.get("fill", "#000000")
                stroke = op.get("stroke", "none")
                stroke_width = op.get("stroke_width", 1)
                
                new_shape: Shape = {
                    "id": shape_id,
                    "type": "rectangle", # default
                    "x": x,
                    "y": y,
                    "width": 100,
                    "height": 100,
                    "fill": fill,
                    "stroke": stroke,
                    "stroke_width": stroke_width,
                    "end_x": 0,
                    "end_y": 0,
                    "content": "",
                    "points": [],
                    "path_data": "",
                    "src": "",
                }

                if op_type == "addRect" or op_type == "add_rectangle":
                    new_shape["type"] = "rectangle"
                    new_shape["width"] = op.get("width", 100)
                    new_shape["height"] = op.get("height", 100)
                
                elif op_type == "addEllipse" or op_type == "add_ellipse":
                    new_shape["type"] = "ellipse"
                    # Support rx/ry or width/height
                    if "rx" in op:
                        new_shape["width"] = op["rx"] * 2
                    else:
                        new_shape["width"] = op.get("width", 100)
                        
                    if "ry" in op:
                        new_shape["height"] = op["ry"] * 2
                    else:
                        new_shape["height"] = op.get("height", 100)
                        
                    # If cx/cy provided, adjust x/y to top-left
                    if "cx" in op:
                        new_shape["x"] = op["cx"] - new_shape["width"] / 2
                    if "cy" in op:
                        new_shape["y"] = op["cy"] - new_shape["height"] / 2

                elif op_type == "addText" or op_type == "add_text":
                    new_shape["type"] = "text"
                    new_shape["content"] = op.get("content", "Text")
                    new_shape["height"] = op.get("font_size", 20) # Map font_size to height for text
                    
                elif op_type == "addLine" or op_type == "add_line":
                    new_shape["type"] = "line"
                    new_shape["end_x"] = op.get("end_x", x + 100)
                    new_shape["end_y"] = op.get("end_y", y + 100)
                
                self.shapes.append(new_shape)
            
            # Close modal on success
            self.is_ai_modal_open = False
            rx.toast("AI Operations executed successfully")
            
        except Exception as e:
            print(f"Error executing AI ops: {e}")
            rx.toast(f"Error: {str(e)}")

    @rx.var
    def json_data_base64(self) -> str:
        """Get the Base64 encoded JSON representation of the current shapes."""
        json_str = json.dumps(self.shapes)
        return base64.b64encode(json_str.encode("utf-8")).decode("utf-8")

    @rx.event
    def check_pending_ai_ops(self):
        """Poll for pending AI operations from external sources (MCP)."""
        # Use current room_id or "default" if empty
        target_room = self.room_id if self.room_id else "default"
        
        if target_room in PENDING_AI_OPS and PENDING_AI_OPS[target_room]:
            ops = PENDING_AI_OPS[target_room]
            # Clear the pending list immediately to avoid double processing
            # Note: In a multi-threaded env this might need locking, but for Reflex/FastAPI simple usage this is usually fine
            # We copy and clear
            ops_to_run = list(ops)
            PENDING_AI_OPS[target_room].clear()
            
            # Reuse the logic from run_ai_ops but without the JSON parsing part
            # We can just set the JSON string and call run_ai_ops, or refactor.
            # Let's refactor slightly or just construct the JSON string to reuse existing logic for simplicity
            import json
            self.ai_ops_json = json.dumps(ops_to_run)
            return self.run_ai_ops()