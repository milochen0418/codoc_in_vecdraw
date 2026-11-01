"""The AI operations: JSON commands that clear the canvas and add shapes.

They come from the AI Ops dialog and from the MCP server (``/mcp/push_ops``). This module only
turns them into shapes; who applies them decides how (see ``EditorState`` and ``push_ai_ops``).
"""

from __future__ import annotations

import json
import uuid
from typing import Any


# What must be a number for a shape to be drawn at all.
NUMBERS = ("x", "y", "width", "height", "stroke_width", "end_x", "end_y")


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
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{op}: {field} must be a number") from None


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

        elif op_type in ("addText", "add_text"):
            shape = _shape(op, "text")
            shape["content"] = op.get("content", "Text")
            shape["height"] = op.get("font_size", 20)  # Map font_size to height for text
            shapes.append(shape)

        elif op_type in ("addLine", "add_line"):
            shape = _shape(op, "line")
            shape["end_x"] = op.get("end_x", _number(shape["x"], "line", "x") + 100)
            shape["end_y"] = op.get("end_y", _number(shape["y"], "line", "y") + 100)
            shapes.append(shape)

        else:
            raise ValueError(f"Unknown operation: {op_type}")
    for shape in shapes:
        for field in NUMBERS:
            shape[field] = _number(shape[field], shape["type"], field)
    return clear, shapes
