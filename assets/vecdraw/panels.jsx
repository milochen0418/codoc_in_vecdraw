// The tools on the left and the properties on the right: each person's own, so they live here and
// not in the shared room. Changing a property changes the drawing, for everyone.
import React, { useEffect, useRef, useState } from "react";
import {
  Circle,
  Hand,
  Image as ImageIcon,
  Minus,
  MousePointer2,
  MousePointerClick,
  Pencil,
  Redo2,
  Square,
  Trash2,
  Triangle,
  Type,
  Undo2,
} from "lucide-react";

const TOOLS = [
  ["select", "Select", MousePointer2],
  ["hand", "Pan", Hand],
  ["rectangle", "Rectangle", Square],
  ["ellipse", "Ellipse", Circle],
  ["triangle", "Triangle", Triangle],
  ["line", "Line", Minus],
  ["pencil", "Pencil", Pencil],
  ["text", "Text", Type],
];

const TOOL = "flex flex-col items-center justify-center p-2 md:p-3 rounded-xl transition-colors w-full";
const TOOL_OFF = "hover:bg-gray-100 text-gray-600";
const TOOL_ON = "bg-violet-100 text-violet-700";
const STEP = "flex-1 flex items-center justify-center p-2 text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-30 disabled:hover:bg-transparent transition-colors";
const LABEL = "block text-xs font-medium text-gray-500 mb-1";
const FIELD = "w-full text-sm border border-gray-200 rounded-md px-2 py-1.5 focus:border-violet-500 focus:ring-1 focus:ring-violet-500 outline-none";

export function Toolbar({ tool, onTool, canUndo, canRedo, onUndo, onRedo, onFiles }) {
  return (
    <aside className="w-14 md:w-24 bg-white border-r border-gray-200 h-full flex-shrink-0 z-10 flex flex-col overflow-y-auto">
      <div className="p-1 md:p-4 flex-1">
        <h2 className="hidden md:block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4 px-2">Tools</h2>
        <div className="flex flex-col gap-1 md:gap-2">
          {TOOLS.map(([name, label, Icon]) => (
            <button key={name} type="button" title={label} onClick={() => onTool(name)} className={`${TOOL} ${tool === name ? TOOL_ON : TOOL_OFF}`}>
              <Icon className="w-6 h-6 md:mb-1" />
              <span className="hidden md:inline text-xs font-medium">{label}</span>
            </button>
          ))}
          <label id="upload1" title="Image" className={`${TOOL} ${TOOL_OFF} cursor-pointer`}>
            <ImageIcon className="w-6 h-6 md:mb-1" />
            <span className="hidden md:inline text-xs font-medium">Image</span>
            <input
              type="file"
              multiple
              accept=".png,.jpg,.jpeg,.gif,.webp"
              className="sr-only"
              onChange={(e) => {
                onFiles([...e.target.files]);
                e.target.value = "";
              }}
            />
          </label>
        </div>
      </div>
      <div className="flex flex-col md:flex-row gap-1 px-1 md:px-3 py-2 md:py-3 border-t border-gray-100">
        <button type="button" title="Undo your last change" aria-label="Undo" disabled={!canUndo} onClick={onUndo} className={STEP}>
          <Undo2 className="w-4 h-4" />
        </button>
        <button type="button" title="Redo" aria-label="Redo" disabled={!canRedo} onClick={onRedo} className={STEP}>
          <Redo2 className="w-4 h-4" />
        </button>
      </div>
    </aside>
  );
}

/** A colour input can only show #rrggbb. */
function asHex(value) {
  return /^#[0-9a-fA-F]{6}$/.test(value || "") ? value : "#000000";
}

function ColorField({ label, value, onChange }) {
  return (
    <div className="mb-3">
      <label className="block">
        <span className={LABEL}>{label}</span>
        <input type="color" value={asHex(value)} onChange={(e) => onChange(e.target.value)} className={`${FIELD} h-9 cursor-pointer`} />
      </label>
    </div>
  );
}

function StrokeWidth({ value, onChange }) {
  return (
    <div className="mb-6">
      <label className="block">
        <span className={LABEL}>Stroke Width</span>
        <input type="range" min="0" max="20" value={value} onChange={(e) => onChange(Number(e.target.value))} className="w-full accent-violet-600" />
      </label>
      <div className="flex justify-between text-[10px] text-gray-400 mt-1">
        <span>0px</span>
        <span>{value}px</span>
        <span>20px</span>
      </div>
    </div>
  );
}

/** Text goes to the drawing as it is typed, but not the pieces of a Chinese or Japanese word
 * still being composed. */
function TextField({ label, value, onChange, inputRef }) {
  const [draft, setDraft] = useState(value);
  const composing = useRef(false);
  useEffect(() => {
    if (!composing.current) setDraft(value);
  }, [value]);
  return (
    <div className="mb-3">
      <label className="block">
        <span className={LABEL}>{label}</span>
        <input
          ref={inputRef}
          id="shape-content"
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value);
            if (!composing.current) onChange(e.target.value);
          }}
          onCompositionStart={() => { composing.current = true; }}
          onCompositionEnd={(e) => {
            composing.current = false;
            onChange(e.target.value);
          }}
          className={FIELD}
        />
      </label>
    </div>
  );
}

/** Who else has this shape selected. */
function AlsoHere({ people }) {
  if (!people.length) return null;
  return (
    <div id="also-here" className="flex items-center flex-wrap gap-1 mb-4 text-xs text-gray-500">
      <span>Also on this shape:</span>
      {people.map((p) => (
        <span key={p.clientId} className="inline-flex items-center gap-1 font-medium text-gray-700">
          <span className="w-2 h-2 rounded-full" style={{ background: p.user.color }} />
          {p.user.name}
        </span>
      ))}
    </div>
  );
}

export function Properties({ shape, tool, others, onChange, onDelete, textRef }) {
  const set = (key) => (value) => onChange(shape.id, { [key]: value });
  const also = shape ? others.filter((p) => p.selection === shape.id) : [];
  return (
    // On a small screen the panel comes over the canvas, only when you are selecting: not after
    // every shape you draw.
    <aside className={`${shape && tool === "select" ? "absolute inset-y-0 right-0 shadow-xl" : "hidden"} md:static md:block md:shadow-none w-64 bg-white border-l border-gray-200 h-full flex-shrink-0 z-30 overflow-y-auto`}>
      <div className="p-4">
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">Properties</h2>
        {shape ? (
          <div>
            <div className="flex justify-between items-center mb-4 p-2 bg-gray-50 rounded-lg">
              <span className="text-xs text-gray-400">Type</span>
              <span className="text-sm font-medium capitalize">{shape.type}</span>
            </div>
            <AlsoHere people={also} />
            {shape.type === "text" && (
              <>
                <TextField key={shape.id} label="Text Content" value={shape.content} onChange={set("content")} inputRef={textRef} />
                <ColorField label="Text Color" value={shape.fill} onChange={set("fill")} />
              </>
            )}
            {(shape.type === "line" || shape.type === "pencil") && (
              <>
                <ColorField label="Stroke Color" value={shape.stroke} onChange={set("stroke")} />
                <StrokeWidth value={shape.stroke_width} onChange={set("stroke_width")} />
              </>
            )}
            {(shape.type === "rectangle" || shape.type === "ellipse" || shape.type === "triangle") && (
              <>
                <ColorField label="Fill Color" value={shape.fill} onChange={set("fill")} />
                <ColorField label="Stroke Color" value={shape.stroke} onChange={set("stroke")} />
                <StrokeWidth value={shape.stroke_width} onChange={set("stroke_width")} />
              </>
            )}
            <button
              type="button"
              onClick={onDelete}
              className="flex items-center justify-center w-full px-4 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition-colors text-sm font-medium"
            >
              <Trash2 className="w-4 h-4 mr-2" />
              Delete Shape
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-64">
            <MousePointerClick className="w-8 h-8 text-gray-300 mb-2" />
            <p className="text-sm text-gray-400 text-center">Select a shape to edit properties</p>
          </div>
        )}
      </div>
    </aside>
  );
}
