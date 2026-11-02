"""The AI operations: JSON commands that clear the canvas and add shapes.

They come from the AI Ops dialog and from the MCP server (``/mcp/push_ops``). This module only
turns them into shapes; who applies them decides how (see ``EditorState`` and ``push_ai_ops``).
"""

from __future__ import annotations

import json
import math
import uuid
from typing import Any


# What must be a number for a shape to be drawn at all.
NUMBERS = ("x", "y", "width", "height", "stroke_width", "end_x", "end_y")
# The operations that add a shape, by the name the AI is told.
OPERATIONS = ("clear", "addRect", "addEllipse", "addTriangle", "addLine", "addPath", "addText")
# What the AI may change of a shape.
CHANGEABLE = ("x", "y", "width", "height", "end_x", "end_y", "fill", "stroke", "stroke_width", "content", "font_size")


def _shape(op: dict, kind: str) -> dict:
    x = op.get("x", 0)
    y = op.get("y", 0)
    return {
        "id": str(op.get("id") or uuid.uuid4()),
        "type": kind,
        "x": x,
        "y": y,
        "width": 100,
        "height": 100,
        "fill": op.get("fill", "#000000"),
        "stroke": op.get("stroke", "none"),
        "stroke_width": op.get("stroke_width", 1),
        "end_x": 0,
        "end_y": 0,
        "content": "",
        "points": [],
        "path_data": "",
        "src": "",
    }


def _number(value: Any, op: str, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{op}: {field} must be a number") from None
    if not math.isfinite(number):
        raise ValueError(f"{op}: {field} must be a number")
    return number


def _points(points: Any) -> list[dict]:
    """A line's points as the editor keeps them, from [x, y] pairs or {"x", "y"} objects."""
    if not isinstance(points, list) or len(points) < 2:
        raise ValueError("path: points must list at least two points")
    out = []
    for point in points:
        x, y = (point.get("x"), point.get("y")) if isinstance(point, dict) else (point if isinstance(point, list) and len(point) == 2 else (None, None))
        out.append({"x": _number(x, "path", "x"), "y": _number(y, "path", "y")})
    return out


def _stroke(points: Any) -> dict:
    """The fields of a freehand line through these points (see ``newShape`` in the assets)."""
    points = _points(points)
    left, top = min(p["x"] for p in points), min(p["y"] for p in points)
    return {
        "points": points,
        "path_data": "M " + " L ".join(f"{p['x']:g} {p['y']:g}" for p in points),
        "x": left,
        "y": top,
        "width": max(p["x"] for p in points) - left,
        "height": max(p["y"] for p in points) - top,
    }


def covers(shapes: list[dict]) -> dict:
    """The box a drawing's shapes cover."""
    boxes = []
    for s in shapes:
        x, y = _number(s.get("x", 0), "shape", "x"), _number(s.get("y", 0), "shape", "y")
        if s.get("type") == "line":
            boxes.append((x, y, s.get("end_x", x), s.get("end_y", y)))
        elif s.get("type") == "text":  # about as wide as a character is tall, for each
            boxes.append((x, y, x + len(str(s.get("content") or "")) * s.get("height", 20), y + s.get("height", 20)))
        else:
            boxes.append((x, y, x + s.get("width", 0), y + s.get("height", 0)))
    left, top = min(min(b[0], b[2]) for b in boxes), min(min(b[1], b[3]) for b in boxes)
    right, bottom = max(max(b[0], b[2]) for b in boxes), max(max(b[1], b[3]) for b in boxes)
    return {"x": left, "y": top, "width": right - left, "height": bottom - top}


def changed(shape: dict, fields: dict) -> dict:
    """The fields to set on ``shape`` for what the AI asks: x, y move a whole line or stroke, width
    and height scale a stroke (ValueError, for the AI to read, when it can't be done)."""
    unknown = set(fields) - set(CHANGEABLE)
    if unknown:
        raise ValueError(f"these can't be changed: {sorted(unknown)} (these can: {', '.join(CHANGEABLE)})")
    kind = shape.get("type", "")
    out: dict[str, Any] = {}
    for key, value in fields.items():
        if key in ("fill", "stroke", "content"):
            out[key] = str(value)
        else:
            out[key] = _number(value, kind, key)
    if "font_size" in out:
        out["height"] = out.pop("font_size")
    dx = out.get("x", shape.get("x", 0)) - shape.get("x", 0)
    dy = out.get("y", shape.get("y", 0)) - shape.get("y", 0)
    if kind == "line":
        out.setdefault("end_x", shape.get("end_x", 0) + dx)
        out.setdefault("end_y", shape.get("end_y", 0) + dy)
    elif kind == "pencil":
        old_w, old_h = shape.get("width") or 0, shape.get("height") or 0
        sx = out.get("width", old_w) / old_w if old_w else 1
        sy = out.get("height", old_h) / old_h if old_h else 1
        x, y = out.get("x", shape.get("x", 0)), out.get("y", shape.get("y", 0))
        points = [{"x": x + (p["x"] - shape.get("x", 0)) * sx, "y": y + (p["y"] - shape.get("y", 0)) * sy} for p in shape.get("points") or []]
        if len(points) > 1:
            out.update(_stroke(points))
    return out


def parse(text: str) -> list[dict]:
    """The operations in a piece of JSON (ValueError when it isn't any)."""
    ops = json.loads(text)
    if not isinstance(ops, list):
        ops = [ops]
    if not all(isinstance(op, dict) for op in ops):
        raise ValueError("Each operation must be a JSON object")
    return ops


def run(ops: list[dict]) -> tuple[bool, list[dict]]:
    """What the operations do: ``(clear the canvas first, the shapes to add)``."""
    clear = False
    shapes: list[dict[str, Any]] = []
    for op in ops:
        op_type = op.get("op")

        if op_type == "clear":
            clear = True
            shapes = []

        elif op_type in ("addRect", "add_rectangle"):
            shape = _shape(op, "rectangle")
            shape["width"] = op.get("width", 100)
            shape["height"] = op.get("height", 100)
            shapes.append(shape)

        elif op_type in ("addEllipse", "add_ellipse"):
            shape = _shape(op, "ellipse")
            # Support rx/ry or width/height
            shape["width"] = _number(op["rx"], "ellipse", "rx") * 2 if "rx" in op else op.get("width", 100)
            shape["height"] = _number(op["ry"], "ellipse", "ry") * 2 if "ry" in op else op.get("height", 100)
            # If cx/cy provided, adjust x/y to top-left
            if "cx" in op:
                shape["x"] = _number(op["cx"], "ellipse", "cx") - _number(shape["width"], "ellipse", "width") / 2
            if "cy" in op:
                shape["y"] = _number(op["cy"], "ellipse", "cy") - _number(shape["height"], "ellipse", "height") / 2
            shapes.append(shape)

        elif op_type in ("addTriangle", "add_triangle"):
            shape = _shape(op, "triangle")
            shape["width"] = op.get("width", 100)
            shape["height"] = op.get("height", 100)
            shapes.append(shape)

        elif op_type in ("addText", "add_text"):
            shape = _shape(op, "text")
            shape["content"] = op.get("content", "Text")
            shape["height"] = op.get("font_size", 20)  # Map font_size to height for text
            shapes.append(shape)

        elif op_type in ("addLine", "add_line"):
            shape = _shape(op, "line")
            shape["stroke"] = op.get("stroke", "#000000")  # a line without one can't be seen
            shape["end_x"] = op.get("end_x", _number(shape["x"], "line", "x") + 100)
            shape["end_y"] = op.get("end_y", _number(shape["y"], "line", "y") + 100)
            shapes.append(shape)

        elif op_type in ("addPath", "add_path"):
            shape = _shape(op, "pencil")
            shape["fill"] = "none"
            shape["stroke"] = op.get("stroke", "#000000")
            shape.update(_stroke(op.get("points")))
            shapes.append(shape)

        else:
            raise ValueError(f"Unknown operation: {op_type} (there are {', '.join(OPERATIONS)})")
    for shape in shapes:
        for field in NUMBERS:
            shape[field] = _number(shape[field], shape["type"], field)
    return clear, shapes
