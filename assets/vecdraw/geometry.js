// Shapes as plain objects: making them, and what a gesture does to them. No React, no Yjs, so the
// same code draws your own gesture, draws someone else's, and works out what it changes.
//
// A shape has the fields below (the same as a saved drawing's JSON), plus `z` once it is in the
// document. Text keeps its font size in `height`.

const NEW_SHAPE = {
  id: "",
  type: "",
  x: 0,
  y: 0,
  width: 0,
  height: 0,
  fill: "none",
  stroke: "none",
  stroke_width: 0,
  end_x: 0,
  end_y: 0,
  content: "",
  points: [],
  path_data: "",
  src: "",
};

export function newId() {
  return crypto.randomUUID ? crypto.randomUUID() : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

export function newShape(fields) {
  return { ...NEW_SHAPE, id: newId(), ...fields };
}

export const SHAPE_STYLE = { fill: "#e9d5ff", stroke: "#7c3aed", stroke_width: 2 };

export function pathOf(points) {
  if (!points || !points.length) return "";
  return `M ${points[0].x} ${points[0].y}` + points.slice(1).map((p) => ` L ${p.x} ${p.y}`).join("");
}

/** At most `max` of the points, evenly spread, keeping the last: a long stroke as a hint. */
export function thin(points, max) {
  if (points.length <= max) return points;
  const step = (points.length - 1) / (max - 1);
  return Array.from({ length: max }, (_, i) => points[Math.round(i * step)]);
}

/** The box two corners make. */
export function boxBetween(ax, ay, bx, by) {
  return { x: Math.min(ax, bx), y: Math.min(ay, by), width: Math.abs(bx - ax), height: Math.abs(by - ay) };
}

function moved(shape, dx, dy) {
  const next = { ...shape, x: shape.x + dx, y: shape.y + dy };
  if (shape.type === "line") {
    next.end_x = shape.end_x + dx;
    next.end_y = shape.end_y + dy;
  } else if (shape.type === "pencil") {
    next.points = shape.points.map((p) => ({ x: p.x + dx, y: p.y + dy }));
    next.path_data = pathOf(next.points);
  }
  return next;
}

function boxed(shape, box) {
  const next = { ...shape, ...box };
  if (shape.type === "pencil") {
    const sx = shape.width ? box.width / shape.width : 1;
    const sy = shape.height ? box.height / shape.height : 1;
    next.points = shape.points.map((p) => ({
      x: Math.round(box.x + (p.x - shape.x) * sx),
      y: Math.round(box.y + (p.y - shape.y) * sy),
    }));
    next.path_data = pathOf(next.points);
  }
  return next;
}

/** The box a corner's drag gives; dragging past the opposite corner flips it. */
export function resizedBox(shape, handle, dx, dy) {
  let left = shape.x;
  let top = shape.y;
  let right = shape.x + shape.width;
  let bottom = shape.y + shape.height;
  if (handle.includes("n")) top += dy;
  if (handle.includes("s")) bottom += dy;
  if (handle.includes("w")) left += dx;
  if (handle.includes("e")) right += dx;
  return boxBetween(left, top, right, bottom);
}

/** The shape as it looks during a gesture on it (the same object when it isn't about this one). */
export function patched(shape, gesture) {
  if (!gesture || gesture.id !== shape.id) return shape;
  if (gesture.kind === "move") return moved(shape, gesture.dx, gesture.dy);
  if (gesture.kind === "resize") {
    if (gesture.line) return { ...shape, ...gesture.line };
    if (gesture.box) return boxed(shape, gesture.box);
  }
  return shape;
}

/** The fields that differ between two versions of a shape. */
export function changes(before, after) {
  const out = {};
  Object.keys(after).forEach((key) => {
    const a = before[key];
    const b = after[key];
    if (a !== b && JSON.stringify(a) !== JSON.stringify(b)) out[key] = b;
  });
  return out;
}

let measuring = null;

function textWidth(text, size) {
  if (typeof document === "undefined") return text.length * size * 0.6;
  measuring = measuring || document.createElement("canvas").getContext("2d");
  measuring.font = `${size}px Inter, sans-serif`;
  return measuring.measureText(text).width;
}

/** What a shape covers on the canvas. */
export function boxOf(shape) {
  if (shape.type === "line") return boxBetween(shape.x, shape.y, shape.end_x, shape.end_y);
  if (shape.type === "text") {
    return { x: shape.x, y: shape.y, width: Math.max(textWidth(shape.content || "", shape.height), 8), height: shape.height };
  }
  return { x: shape.x, y: shape.y, width: shape.width, height: shape.height };
}

/** Readable text on a person's colour. */
export function textOn(hex) {
  const n = parseInt((hex || "#000000").slice(1), 16);
  const lin = (v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  const lum = 0.2126 * lin(n >> 16) + 0.7152 * lin((n >> 8) & 255) + 0.0722 * lin(n & 255);
  return lum > 0.3 ? "#111827" : "#ffffff";
}
