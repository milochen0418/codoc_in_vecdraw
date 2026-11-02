// Vecdraw's editor: the tools, the canvas and the properties.
//
// The page around it (title, people, calls, export) is Reflex. This component works in the browser,
// so that your own drawing never waits for the network:
//
//   the drawing      the shapes, in the document (doc.js): everyone sees them, and they are saved
//   what you do now  your pointer, what you selected, the shape you are dragging or drawing: a
//                    hint for the others in the awareness, turned into a change of the drawing
//                    only when you let go, so nobody saves half a gesture and Esc can take it back
//   what is yours    the tool in your hand and the part of the canvas in view: nobody else's
//                    business, and they don't move for anyone else
//
// The page reaches it through window.vecdraw ({follow, apply, exportShapes}).
import React, { memo, useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { toast } from "sonner";
import { Drawing, backendURL } from "./doc.js";
import { SHAPE_STYLE, boxBetween, boxOf, changes, newShape, pathOf, patched, resizedBox, thin } from "./geometry.js";
import { OthersOnDrawing, OthersOverCanvas } from "./others.jsx";
import { Properties, Toolbar } from "./panels.jsx";

const HANDLE_SIZE = 8;
// A press that moves less than this is a click.
const DRAG_PX = 3;
const DOUBLE_CLICK_MS = 400;
// The most points of a stroke the others get while it is being drawn.
const HINT_POINTS = 300;
const GLIDE_MS = 240;
const MAX_IMAGE_WIDTH = 320;

function useDrawing(drawing, read) {
  return useSyncExternalStore(drawing.subscribe, () => read(drawing), () => read(drawing));
}

function imageURL(docId, src) {
  return backendURL(`/_vecdraw/image/${docId}/${encodeURIComponent(src)}`);
}

// ------------------------------------------------------------ the shapes

const ShapeView = memo(function ShapeView({ shape, docId, selected }) {
  const props = {
    id: `shape-${shape.id}`,
    "data-shape": shape.id,
    className: selected ? "cursor-move outline-none" : "cursor-pointer hover:opacity-80 transition-opacity",
  };
  const paint = { fill: shape.fill, stroke: shape.stroke, strokeWidth: shape.stroke_width };
  switch (shape.type) {
    case "rectangle":
      return <rect {...props} {...paint} pointerEvents="all" x={shape.x} y={shape.y} width={shape.width} height={shape.height} />;
    case "ellipse":
      return (
        <ellipse
          {...props}
          {...paint}
          pointerEvents="all"
          cx={shape.x + shape.width / 2}
          cy={shape.y + shape.height / 2}
          rx={shape.width / 2}
          ry={shape.height / 2}
        />
      );
    case "triangle":
      return (
        <polygon
          {...props}
          {...paint}
          pointerEvents="all"
          points={`${shape.x + shape.width / 2},${shape.y} ${shape.x},${shape.y + shape.height} ${shape.x + shape.width},${shape.y + shape.height}`}
        />
      );
    case "line":
      return (
        <g>
          <line {...props} {...paint} x1={shape.x} y1={shape.y} x2={shape.end_x} y2={shape.end_y} />
          <line data-hit="1" data-shape={shape.id} className={props.className} x1={shape.x} y1={shape.y} x2={shape.end_x} y2={shape.end_y} stroke="transparent" strokeWidth={Math.max(shape.stroke_width, 12)} />
        </g>
      );
    case "pencil":
      return (
        <g>
          <path {...props} d={shape.path_data} fill="none" stroke={shape.stroke} strokeWidth={shape.stroke_width} strokeLinecap="round" strokeLinejoin="round" />
          <path data-hit="1" data-shape={shape.id} className={props.className} d={shape.path_data} fill="none" stroke="transparent" strokeWidth={Math.max(shape.stroke_width, 12)} />
        </g>
      );
    case "text": {
      const box = boxOf(shape);
      return (
        <g>
          <rect data-hit="1" data-shape={shape.id} className={props.className} x={box.x} y={box.y} width={box.width} height={box.height} fill="transparent" />
          <text {...props} x={shape.x} y={shape.y} fontSize={shape.height} fontFamily="Inter, sans-serif" fill={shape.fill} dominantBaseline="hanging" pointerEvents="none" style={{ userSelect: "none" }}>
            {shape.content}
          </text>
        </g>
      );
    }
    case "image":
      return <image {...props} href={imageURL(docId, shape.src)} x={shape.x} y={shape.y} width={shape.width} height={shape.height} preserveAspectRatio="none" />;
    default:
      return null;
  }
});

/** The shape you are drawing, as you draw it. */
function MyPreview({ gesture }) {
  const { tool, x, y, ex, ey, points } = gesture;
  const style = { fill: SHAPE_STYLE.fill, stroke: SHAPE_STYLE.stroke, strokeWidth: SHAPE_STYLE.stroke_width, opacity: 0.5 };
  const box = boxBetween(x, y, ex, ey);
  if (tool === "rectangle") return <rect {...box} {...style} />;
  if (tool === "ellipse") {
    return <ellipse cx={box.x + box.width / 2} cy={box.y + box.height / 2} rx={box.width / 2} ry={box.height / 2} {...style} />;
  }
  if (tool === "triangle") return <polygon points={`${(x + ex) / 2},${y} ${x},${ey} ${ex},${ey}`} {...style} />;
  if (tool === "line") return <line x1={x} y1={y} x2={ex} y2={ey} stroke={style.stroke} strokeWidth={style.strokeWidth} opacity={0.5} />;
  if (tool === "pencil") return <path d={pathOf(points)} fill="none" stroke={style.stroke} strokeWidth={style.strokeWidth} opacity={0.5} />;
  return null;
}

function Handle({ x, y, name, round, cursor }) {
  // The handle you see is small; the one you grab is bigger.
  return (
    <g data-handle={name} style={{ cursor }}>
      <rect x={x - 7} y={y - 7} width={14} height={14} fill="transparent" />
      {round ? (
        <circle cx={x} cy={y} r={4} fill="white" stroke="#7c3aed" strokeWidth={2} pointerEvents="none" />
      ) : (
        <rect x={x - HANDLE_SIZE / 2} y={y - HANDLE_SIZE / 2} width={HANDLE_SIZE} height={HANDLE_SIZE} fill="white" stroke="#7c3aed" pointerEvents="none" />
      )}
    </g>
  );
}

/** The outline and handles of your own selection: only you see these. */
function MySelection({ shape }) {
  if (shape.type === "line") {
    return (
      <g id="my-selection">
        <Handle x={shape.x} y={shape.y} name="start" round cursor="move" />
        <Handle x={shape.end_x} y={shape.end_y} name="end" round cursor="move" />
      </g>
    );
  }
  const box = boxOf(shape);
  const right = box.x + box.width;
  const bottom = box.y + box.height;
  return (
    <g id="my-selection">
      <rect x={box.x - 2} y={box.y - 2} width={box.width + 4} height={box.height + 4} fill="none" stroke="#7c3aed" strokeDasharray="4,4" pointerEvents="none" />
      <Handle x={box.x} y={box.y} name="nw" cursor="nw-resize" />
      <Handle x={right} y={box.y} name="ne" cursor="ne-resize" />
      <Handle x={right} y={bottom} name="se" cursor="se-resize" />
      <Handle x={box.x} y={bottom} name="sw" cursor="sw-resize" />
    </g>
  );
}

// ------------------------------------------------------------ the editor

/** What the others get of a gesture. */
function hint(gesture) {
  if (gesture.kind === "draw") {
    const { kind, tool, x, y, ex, ey, points } = gesture;
    return { kind, tool, x, y, ex, ey, points: tool === "pencil" ? thin(points, HINT_POINTS) : undefined };
  }
  if (gesture.kind === "move") return { kind: "move", id: gesture.id, dx: gesture.dx, dy: gesture.dy };
  if (gesture.kind === "resize") return { kind: "resize", id: gesture.id, box: gesture.box, line: gesture.line };
  return null;
}

function naturalSize(file) {
  return createImageBitmap(file).then(
    (bitmap) => {
      const size = { width: bitmap.width, height: bitmap.height };
      bitmap.close();
      return size;
    },
    () => ({ width: 200, height: 200 }),
  );
}

function Workspace({ drawing, docId }) {
  const shapes = useDrawing(drawing, (d) => d.list);
  const others = useDrawing(drawing, (d) => d.others);
  const status = useDrawing(drawing, (d) => d.status);
  const synced = useDrawing(drawing, (d) => d.synced);
  const history = useDrawing(drawing, (d) => d.history);

  const [tool, setTool] = useState("select");
  const [selectedId, setSelectedId] = useState("");
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [gesture, setGesture] = useState(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [flash, setFlash] = useState("");

  const canvasRef = useRef(null);
  const textRef = useRef(null);
  // The latest of these, for handlers that outlive a render.
  const now = useRef({});
  now.current = { tool, selectedId, pan, size, gesture };
  const lastClick = useRef({ id: "", at: 0 });
  const pointerId = useRef(null);

  const select = useCallback((id) => {
    setSelectedId(id);
    drawing.sayNow({ selection: id });
  }, [drawing]);

  const startGesture = useCallback((g) => {
    now.current.gesture = g;
    setGesture(g);
  }, []);

  const changeGesture = useCallback((g) => {
    now.current.gesture = g;
    setGesture(g);
    drawing.say({ gesture: hint(g) });
  }, [drawing]);

  const endGesture = useCallback(() => {
    now.current.gesture = null;
    setGesture(null);
    drawing.sayNow({ gesture: null });
  }, [drawing]);

  // A shape selected here can be deleted by someone else (or by Undo).
  useEffect(() => {
    if (selectedId && !drawing.byId.has(selectedId)) select("");
  }, [shapes, selectedId, drawing, select]);

  // ---------------------------------------------------- the shapes as they look right now

  const gestures = useMemo(() => {
    const all = others.map((o) => o.gesture).filter((g) => g && g.id);
    if (gesture && gesture.id && gesture.moved) all.push(hint(gesture));
    return all;
  }, [others, gesture]);

  const view = useMemo(
    () => (gestures.length ? shapes.map((s) => gestures.reduce(patched, s)) : shapes),
    [shapes, gestures],
  );
  const viewById = useMemo(() => new Map(view.map((s) => [s.id, s])), [view]);
  const selected = viewById.get(selectedId) || null;

  // ---------------------------------------------------- the view

  useEffect(() => {
    const canvas = canvasRef.current;
    const observer = new ResizeObserver(() => setSize({ w: canvas.clientWidth, h: canvas.clientHeight }));
    observer.observe(canvas);
    return () => observer.disconnect();
  }, []);

  // Where you are looking, so that someone who clicks your face finds you off the canvas too.
  useEffect(() => {
    drawing.say({ view: { x: Math.round(size.w / 2 - pan.x), y: Math.round(size.h / 2 - pan.y) } });
  }, [drawing, pan, size]);

  const glide = useCallback((target) => {
    const from = now.current.pan;
    const start = performance.now();
    const step = (time) => {
      const t = Math.min(1, (time - start) / GLIDE_MS);
      const ease = t * (2 - t);
      setPan({ x: from.x + (target.x - from.x) * ease, y: from.y + (target.y - from.y) * ease });
      if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, []);

  const follow = useCallback((peer) => {
    const person = drawing.others.find((o) => o.user.peer === peer);
    const at = person && (person.cursor || person.view);
    if (!at) return;
    const { w, h } = now.current.size;
    glide({ x: Math.round(w / 2 - at.x), y: Math.round(h / 2 - at.y) });
    setFlash(peer);
    setTimeout(() => setFlash(""), 1500);
  }, [drawing, glide]);

  // ---------------------------------------------------- the pointer

  const toCanvas = useCallback((e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    const { pan: p } = now.current;
    return { x: Math.round(e.clientX - rect.left - p.x), y: Math.round(e.clientY - rect.top - p.y) };
  }, []);

  const onPointerDown = (e) => {
    if (e.button !== 0 || now.current.gesture) return;
    canvasRef.current.setPointerCapture(e.pointerId);
    pointerId.current = e.pointerId;
    const p = toCanvas(e);
    const { tool: active, selectedId: mine } = now.current;

    if (active === "hand") {
      startGesture({ kind: "pan", startX: e.clientX, startY: e.clientY, from: now.current.pan });
      return;
    }

    if (active === "select") {
      const handle = e.target.closest && e.target.closest("[data-handle]");
      const shape = mine && drawing.byId.get(mine);
      if (handle && shape) {
        startGesture({ kind: "resize", id: mine, handle: handle.dataset.handle, startX: p.x, startY: p.y, moved: false });
        return;
      }
      const hit = e.target.closest && e.target.closest("[data-shape]");
      if (!hit) {
        select("");
        return;
      }
      const id = hit.dataset.shape;
      select(id);
      const clicked = lastClick.current;
      const twice = clicked.id === id && performance.now() - clicked.at < DOUBLE_CLICK_MS;
      lastClick.current = { id, at: performance.now() };
      if (twice && drawing.byId.get(id).type === "text") {
        // Text is edited in the properties panel.
        setTimeout(() => textRef.current && textRef.current.select(), 0);
        return;
      }
      startGesture({ kind: "move", id, startX: p.x, startY: p.y, dx: 0, dy: 0, moved: false });
      return;
    }

    if (active === "text") {
      const shape = newShape({ type: "text", x: p.x, y: p.y, width: 100, height: 30, fill: "#000000", content: "Double click to edit" });
      drawing.endStep();
      drawing.add([shape]);
      setTool("select");
      select(shape.id);
      return;
    }

    select("");
    changeGesture({ kind: "draw", tool: active, x: p.x, y: p.y, ex: p.x, ey: p.y, points: [{ x: p.x, y: p.y }] });
  };

  const onPointerMove = (e) => {
    const p = toCanvas(e);
    const g = now.current.gesture;
    // A second finger on the screen isn't another gesture.
    if (g && e.pointerId !== pointerId.current) return;
    drawing.say({ cursor: p });
    if (!g) return;
    if (g.kind === "pan") {
      setPan({ x: g.from.x + e.clientX - g.startX, y: g.from.y + e.clientY - g.startY });
    } else if (g.kind === "draw") {
      const points = g.tool === "pencil" ? [...g.points, p] : g.points;
      changeGesture({ ...g, ex: p.x, ey: p.y, points });
    } else {
      const dx = p.x - g.startX;
      const dy = p.y - g.startY;
      if (!g.moved && Math.abs(dx) < DRAG_PX && Math.abs(dy) < DRAG_PX) return;
      const shape = drawing.byId.get(g.id);
      if (!shape) return;
      if (g.kind === "move") {
        changeGesture({ ...g, dx, dy, moved: true });
      } else if (shape.type === "line") {
        const moved = g.handle === "start" ? { x: shape.x + dx, y: shape.y + dy } : { end_x: shape.end_x + dx, end_y: shape.end_y + dy };
        changeGesture({ ...g, line: moved, moved: true });
      } else {
        changeGesture({ ...g, box: resizedBox(shape, g.handle, dx, dy), moved: true });
      }
    }
  };

  /** The gesture ends: what it did becomes a change of the drawing, for everyone. */
  const finish = (cancelled) => {
    const g = now.current.gesture;
    if (!g) return;
    if (!cancelled && g.kind === "draw") {
      const made = madeBy(g);
      if (made) {
        drawing.endStep();
        drawing.add([made]);
        select(made.id);
      }
    } else if (!cancelled && g.moved) {
      const shape = drawing.byId.get(g.id);
      if (shape) {
        drawing.endStep();
        drawing.update(g.id, changes(shape, patched(shape, hint(g))));
      }
    }
    endGesture();
  };

  const madeBy = (g) => {
    if (g.tool === "pencil") {
      if (g.points.length < 2) return null;
      const xs = g.points.map((p) => p.x);
      const ys = g.points.map((p) => p.y);
      const box = boxBetween(Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys));
      return newShape({ type: "pencil", ...box, fill: "none", stroke: SHAPE_STYLE.stroke, stroke_width: SHAPE_STYLE.stroke_width, points: g.points, path_data: pathOf(g.points) });
    }
    const box = boxBetween(g.x, g.y, g.ex, g.ey);
    if (box.width <= 2 && box.height <= 2) return null;
    if (g.tool === "line") {
      return newShape({ type: "line", x: g.x, y: g.y, end_x: g.ex, end_y: g.ey, ...{ width: box.width, height: box.height }, fill: "transparent", stroke: SHAPE_STYLE.stroke, stroke_width: SHAPE_STYLE.stroke_width });
    }
    return newShape({ type: g.tool, ...box, ...SHAPE_STYLE });
  };

  const onPointerUp = (e) => {
    const g = now.current.gesture;
    if (g && e.pointerId !== pointerId.current) return;
    if (g && g.kind === "draw") {
      // The last move may not have reached onPointerMove.
      const p = toCanvas(e);
      g.ex = p.x;
      g.ey = p.y;
    }
    finish(false);
  };

  const onWheel = (e) => {
    setPan((p) => ({ x: p.x - e.deltaX, y: p.y - e.deltaY }));
  };

  // ---------------------------------------------------- doing things

  const chooseTool = (name) => {
    setTool(name);
    select("");
  };

  const undo = useCallback(() => drawing.undo.undo(), [drawing]);
  const redo = useCallback(() => drawing.undo.redo(), [drawing]);

  const deleteSelected = useCallback(() => {
    const id = now.current.selectedId;
    if (!id) return;
    drawing.endStep();
    drawing.remove(id);
    select("");
  }, [drawing, select]);

  const placeImages = async (files) => {
    const { size: view, pan: p } = now.current;
    let offset = 0;
    for (const file of files) {
      const natural = await naturalSize(file);
      const scale = Math.min(1, MAX_IMAGE_WIDTH / natural.width);
      const width = Math.round(natural.width * scale);
      const height = Math.round(natural.height * scale);
      let response;
      try {
        response = await fetch(backendURL(`/_vecdraw/upload/${docId}`), { method: "POST", body: file });
      } catch (err) {
        toast.error(`${file.name} could not be uploaded`);
        continue;
      }
      if (!response.ok) {
        const reason = await response.text();
        toast.error(`${file.name}: ${reason || "could not be uploaded"}`);
        continue;
      }
      const { src } = await response.json();
      const shape = newShape({
        type: "image",
        x: Math.round(view.w / 2 - width / 2 - p.x + offset),
        y: Math.round(view.h / 2 - height / 2 - p.y + offset),
        width,
        height,
        src,
      });
      offset += 24;
      drawing.endStep();
      drawing.add([shape]);
      select(shape.id);
    }
  };

  useEffect(() => {
    const onKey = (e) => {
      const el = e.target;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable)) return;
      const key = e.key.toLowerCase();
      if ((e.metaKey || e.ctrlKey) && key === "z") {
        e.preventDefault();
        if (e.shiftKey) redo();
        else undo();
      } else if ((e.metaKey || e.ctrlKey) && key === "y") {
        e.preventDefault();
        redo();
      } else if (e.key === "Delete" || e.key === "Backspace") {
        if (now.current.selectedId && !now.current.gesture) {
          e.preventDefault();
          deleteSelected();
        }
      } else if (e.key === "Escape") {
        if (now.current.gesture) {
          endGesture();
        } else {
          select("");
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [undo, redo, deleteSelected, endGesture, select]);

  // A pointer that left the canvas, or a tab put away, isn't anywhere on the canvas.
  useEffect(() => {
    const onHide = () => {
      if (document.hidden) drawing.sayNow({ cursor: null });
    };
    document.addEventListener("visibilitychange", onHide);
    return () => document.removeEventListener("visibilitychange", onHide);
  }, [drawing]);

  useEffect(() => {
    window.vecdraw = {
      follow,
      apply({ clear, shapes: added }) {
        drawing.endStep();
        drawing.change(() => {
          if (clear) drawing.clear();
          drawing.add(added);
        });
      },
      exportShapes: () => JSON.stringify(drawing.plainShapes()),
    };
    return () => {
      delete window.vecdraw;
    };
  }, [drawing, follow]);

  // The AI Hub's dialogs ask the page what it shows (reflex_ddns_auth.intent): new shapes go
  // where the person is looking, and "this" means the selected shape.
  useEffect(() => {
    window.__ddnsContext = () => {
      const { pan: p, size: s, selectedId: id } = now.current;
      const left = Math.round(-p.x);
      const top = Math.round(-p.y);
      const shape = drawing.byId.get(id);
      const words = [
        `The drawing (room ${docId}) has ${drawing.list.length} shapes.`,
        `The part of the canvas in view runs from x ${left} to ${left + Math.round(s.w)} and from y ${top} to ${top + Math.round(s.h)}.`,
      ];
      if (shape) words.push(`The selected shape is the ${shape.type} ${shape.id}.`);
      return words.join(" ");
    };
    return () => {
      delete window.__ddnsContext;
    };
  }, [drawing, docId]);

  // ---------------------------------------------------- the page

  const cursor = tool === "hand" ? (gesture ? "grabbing" : "grab") : tool === "select" ? "default" : "crosshair";

  return (
    <>
      <Toolbar
        tool={tool}
        onTool={chooseTool}
        canUndo={history.undo}
        canRedo={history.redo}
        onUndo={undo}
        onRedo={redo}
        onFiles={placeImages}
      />
      <div
        ref={canvasRef}
        id="main-canvas"
        className="relative flex-1 w-full h-full bg-gray-50 overflow-hidden overscroll-none touch-none select-none"
        style={{ cursor }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={() => finish(true)}
        onPointerLeave={() => drawing.sayNow({ cursor: null })}
        onWheel={onWheel}
      >
        <div
          className="absolute inset-0 opacity-[0.03] pointer-events-none"
          style={{
            backgroundImage: "radial-gradient(circle, #000 1px, transparent 1px)",
            backgroundSize: "20px 20px",
            backgroundPosition: `${pan.x}px ${pan.y}px`,
          }}
        />
        <svg id="main-svg" className="absolute inset-0 w-full h-full touch-none block" width="100%" height="100%">
          <rect id="canvas-bg" width="100%" height="100%" fill="transparent" />
          <g transform={`translate(${pan.x} ${pan.y})`}>
            {/* The shapes under a tool that draws aren't things to click. */}
            <g id="shapes-layer" style={{ pointerEvents: tool === "select" && !gesture ? "auto" : "none" }}>
              {view.map((shape) => (
                <ShapeView key={shape.id} shape={shape} docId={docId} selected={shape.id === selectedId} />
              ))}
            </g>
            <OthersOnDrawing others={others} shapes={viewById} />
            {gesture && gesture.kind === "draw" && <MyPreview gesture={gesture} />}
            {selected && tool === "select" && <MySelection shape={selected} />}
          </g>
        </svg>
        <OthersOverCanvas others={others} shapes={viewById} pan={pan} size={size} flash={flash} onJump={follow} />
        {status === "gone" ? (
          <Notice>This drawing was deleted, so nothing here is saved any more.</Notice>
        ) : !synced ? (
          <Notice>Loading the drawing…</Notice>
        ) : status !== "connected" ? (
          <Notice>Reconnecting… what you draw is sent when you are back.</Notice>
        ) : null}
      </div>
      <Properties
        shape={selected}
        tool={tool}
        others={others}
        onChange={(id, fields) => drawing.update(id, fields)}
        onDelete={deleteSelected}
        textRef={textRef}
      />
    </>
  );
}

function Notice({ children }) {
  return (
    <div id="sync-notice" className="absolute top-3 left-1/2 -translate-x-1/2 z-30 px-3 py-1 rounded-full bg-gray-900/80 text-white text-xs pointer-events-none">
      {children}
    </div>
  );
}

export function VecdrawEditor({ docId, me, className }) {
  const [drawing, setDrawing] = useState(null);

  useEffect(() => {
    if (!docId) return undefined;
    const opened = new Drawing(docId);
    setDrawing(opened);
    return () => {
      setDrawing(null);
      opened.destroy();
    };
  }, [docId]);

  const { peer, name, color } = me || {};
  useEffect(() => {
    if (drawing) drawing.introduce({ peer, name, color });
  }, [drawing, peer, name, color]);

  return <div className={className}>{drawing && <Workspace drawing={drawing} docId={docId} />}</div>;
}
