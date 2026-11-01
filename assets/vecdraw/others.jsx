// The other people on the canvas: what their awareness says they are doing right now. None of it
// is the drawing, nothing here can be clicked except the chips of people out of view, and all of
// it goes away with them.
import React, { memo, useEffect, useState } from "react";
import { boxOf, pathOf, textOn } from "./geometry.js";

// A name stays up this long after its owner stops moving; the arrow stays.
const NAME_MS = 5000;
const EDGE = 12;

/** What someone is in the middle of drawing, in their colour. */
function Preview({ gesture, color }) {
  const { tool, x, y, ex, ey, points } = gesture;
  const style = { fill: color, fillOpacity: 0.15, stroke: color, strokeWidth: 2, strokeDasharray: "6 4" };
  const left = Math.min(x, ex);
  const top = Math.min(y, ey);
  const width = Math.abs(ex - x);
  const height = Math.abs(ey - y);
  if (tool === "rectangle") return <rect className="other-preview" x={left} y={top} width={width} height={height} {...style} />;
  if (tool === "ellipse") {
    return <ellipse className="other-preview" cx={left + width / 2} cy={top + height / 2} rx={width / 2} ry={height / 2} {...style} />;
  }
  if (tool === "triangle") {
    return <polygon className="other-preview" points={`${(x + ex) / 2},${y} ${x},${ey} ${ex},${ey}`} {...style} />;
  }
  if (tool === "line") return <line className="other-preview" x1={x} y1={y} x2={ex} y2={ey} stroke={color} strokeWidth={2} />;
  if (tool === "pencil" && points) {
    return <path className="other-preview" d={pathOf(points)} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />;
  }
  return null;
}

/** Inside the drawing's coordinates: outlines of what the others have selected, and what they
 * are drawing. `shapes` holds the shapes as they look now, gestures included. */
export function OthersOnDrawing({ others, shapes }) {
  return (
    <g pointerEvents="none">
      {others.map((person) => {
        const { clientId, gesture, selection, user } = person;
        const shape = selection ? shapes.get(selection) : null;
        const box = shape ? boxOf(shape) : null;
        return (
          <g key={clientId}>
            {box && (
              <rect
                className="other-selection"
                data-peer={user.peer}
                x={box.x - 4}
                y={box.y - 4}
                width={box.width + 8}
                height={box.height + 8}
                rx={3}
                fill="none"
                stroke={user.color}
                strokeWidth={2}
                strokeDasharray={gesture ? undefined : "6 4"}
              />
            )}
            {gesture && gesture.kind === "draw" && <Preview gesture={gesture} color={user.color} />}
          </g>
        );
      })}
    </g>
  );
}

function Tag({ color, children, className = "", ...rest }) {
  return (
    <span
      className={`inline-block px-1.5 rounded text-[11px] leading-[18px] font-semibold whitespace-nowrap shadow-sm ${className}`}
      style={{ background: color, color: textOn(color) }}
      {...rest}
    >
      {children}
    </span>
  );
}

/** Someone's pointer with their name. The name fades when they stop moving. */
const Cursor = memo(function Cursor({ peer, name, color, left, top, flash }) {
  const [moving, setMoving] = useState(true);
  useEffect(() => {
    setMoving(true);
    const timer = setTimeout(() => setMoving(false), NAME_MS);
    return () => clearTimeout(timer);
  }, [left, top]);
  return (
    <div
      className="other-cursor absolute top-0 left-0 pointer-events-none z-20"
      data-peer={peer}
      style={{ transform: `translate(${left}px, ${top}px)`, transition: "transform 80ms linear" }}
    >
      {flash && <span className="absolute -left-3 -top-3 w-8 h-8 rounded-full animate-ping" style={{ background: color, opacity: 0.4 }} />}
      <svg width="20" height="20" viewBox="0 0 20 20" className="block drop-shadow-sm">
        <path d="M2 2 L8 18 L11 11 L18 8 Z" fill={color} stroke="white" strokeWidth="1.5" strokeLinejoin="round" />
      </svg>
      <Tag color={color} className={`absolute left-4 top-4 transition-opacity duration-300 ${moving ? "opacity-100" : "opacity-0"}`}>
        {name}
      </Tag>
    </div>
  );
});

/** Where someone is, for a person who panned away: a chip at the edge of the canvas. */
function EdgeChip({ person, left, top, onJump }) {
  const { user } = person;
  return (
    <button
      type="button"
      className="other-edge absolute z-20 -translate-x-1/2 -translate-y-1/2 cursor-pointer"
      style={{ left, top }}
      data-peer={user.peer}
      title={`Go to ${user.name}`}
      onPointerDown={(e) => e.stopPropagation()}
      onClick={() => onJump(user.peer)}
    >
      <Tag color={user.color}>{user.name}</Tag>
    </button>
  );
}

function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}

/** Over the canvas, in screen coordinates: pointers, names on selections, and the chips. */
export function OthersOverCanvas({ others, shapes, pan, size, flash, onJump }) {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {others.map((person) => {
        const { clientId, cursor, selection, user } = person;
        const shape = selection ? shapes.get(selection) : null;
        const box = shape ? boxOf(shape) : null;
        const left = cursor ? cursor.x + pan.x : 0;
        const top = cursor ? cursor.y + pan.y : 0;
        const inView = cursor && left >= 0 && top >= 0 && left <= size.w && top <= size.h;
        return (
          <React.Fragment key={clientId}>
            {box && (
              <div className="other-flag absolute z-10" data-peer={user.peer} style={{ left: box.x + pan.x - 4, top: box.y + pan.y - 26 }}>
                <Tag color={user.color}>{user.name}</Tag>
              </div>
            )}
            {inView && <Cursor peer={user.peer} name={user.name} color={user.color} left={left} top={top} flash={flash === user.peer} />}
            {cursor && !inView && size.w > 0 && (
              <EdgeChip
                person={person}
                left={clamp(left, 40, size.w - 40)}
                top={clamp(top, EDGE, size.h - EDGE)}
                onJump={onJump}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
