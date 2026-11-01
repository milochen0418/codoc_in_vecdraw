// A drawing in this browser: its Y.Doc, connected to the server's copy over /_vecdraw/yjs/<id>
// (y-websocket protocol; see codoc_in_vecdraw/yjs_ws.py for the layout), and the awareness that
// tells the others what this browser is doing right now.
//
// What is in the Y.Doc is the drawing: everyone sees it and it is saved. What is in the awareness
// (`user`, `cursor`, `view`, `selection`, `gesture`) is a hint: the others draw it, and it goes
// away with this tab. The tool in your hand and the part of the canvas in view are in neither.
import * as Y from "yjs";
import { WebsocketProvider } from "y-websocket";
import { getBackendURL } from "$/utils/state";
import env from "$/env.json";

// The server's close code (codoc_in_vecdraw/yjs_ws.py): the drawing doesn't exist (any more).
const CLOSE_GONE = 4404;
// Changes made here carry this origin, so Undo takes back your own and nobody else's.
const MINE = "vecdraw-mine";
// A pointer's position goes out at most this often.
const SAY_MS = 40;

export function backendURL(path) {
  return new URL(path, getBackendURL(env.PING)).toString();
}

function wsBase() {
  return new URL("/_vecdraw/yjs", getBackendURL(env.EVENT)).toString();
}

export class Drawing {
  constructor(docId) {
    this.docId = docId;
    this.doc = new Y.Doc();
    this.shapes = this.doc.getMap("shapes");
    this.provider = new WebsocketProvider(wsBase(), docId, this.doc, {
      // Tabs of one browser sync through the server only.
      disableBc: true,
      maxBackoffTime: 5000,
      // Now and then ask for anything missed, not only when connecting.
      resyncInterval: 10000,
    });
    this.awareness = this.provider.awareness;
    // captureTimeout: the steps of one colour pick or slider drag are one Undo.
    this.undo = new Y.UndoManager(this.shapes, { trackedOrigins: new Set([MINE]), captureTimeout: 500 });

    // What the page reads; each is replaced when it changes, so React can compare.
    this.byId = new Map();
    this.list = [];
    this.others = [];
    this.status = "connecting";
    this.synced = false;
    this.history = { undo: false, redo: false };

    this.listeners = new Set();
    this.subscribe = this.subscribe.bind(this);
    this.pending = {};
    this.sayTimer = 0;

    this.shapes.observeDeep((events) => this.readShapes(events));
    this.awareness.on("change", () => this.readOthers());
    this.undo.on("stack-item-added", () => this.readHistory());
    this.undo.on("stack-item-popped", () => this.readHistory());
    this.provider.on("sync", (synced) => {
      if (synced) this.synced = true;
      this.notify();
    });
    this.provider.on("status", ({ status }) => {
      if (this.status === "gone") return;
      this.status = status;
      this.notify();
    });
    this.provider.on("connection-close", (event) => {
      if (!event || event.code !== CLOSE_GONE) return;
      this.status = "gone";
      this.provider.shouldConnect = false;
      this.notify();
    });
  }

  subscribe(fn) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  notify() {
    this.listeners.forEach((fn) => fn());
  }

  destroy() {
    clearTimeout(this.sayTimer);
    try { this.awareness.setLocalState(null); } catch (err) { /* closed */ }
    this.undo.destroy();
    this.provider.destroy();
    this.doc.destroy();
  }

  // ------------------------------------------------------------ reading

  readShapes(events) {
    events.forEach((event) => {
      if (event.target === this.shapes) {
        event.changes.keys.forEach((change, id) => {
          if (change.action === "delete") this.byId.delete(id);
          else this.byId.set(id, this.shapes.get(id).toJSON());
        });
      } else {
        const id = event.path[0];
        const shape = this.shapes.get(id);
        if (shape) this.byId.set(id, shape.toJSON());
      }
    });
    this.list = [...this.byId.values()].sort((a, b) => a.z - b.z || (a.id < b.id ? -1 : 1));
    this.notify();
  }

  readOthers() {
    const others = [];
    this.awareness.getStates().forEach((state, clientId) => {
      if (clientId !== this.doc.clientID && state.user) others.push({ clientId, ...state });
    });
    this.others = others;
    this.notify();
  }

  readHistory() {
    this.history = { undo: this.undo.undoStack.length > 0, redo: this.undo.redoStack.length > 0 };
    this.notify();
  }

  /** The drawing as it would be saved: plain shapes in drawing order. */
  plainShapes() {
    return this.list.map(({ z, ...shape }) => shape);
  }

  // ------------------------------------------------------------ changing the drawing

  change(fn) {
    this.doc.transact(fn, MINE);
  }

  add(shapes) {
    let z = this.list.length ? this.list[this.list.length - 1].z : 0;
    this.change(() => {
      shapes.forEach((shape) => {
        z += 1;
        this.shapes.set(shape.id, new Y.Map(Object.entries({ ...shape, z })));
      });
    });
  }

  update(id, fields) {
    const shape = this.shapes.get(id);
    if (!shape || !Object.keys(fields).length) return;
    this.change(() => Object.entries(fields).forEach(([key, value]) => shape.set(key, value)));
  }

  remove(id) {
    this.change(() => this.shapes.delete(id));
  }

  clear() {
    this.change(() => [...this.shapes.keys()].forEach((id) => this.shapes.delete(id)));
  }

  /** The next change is an Undo of its own. */
  endStep() {
    this.undo.stopCapturing();
  }

  // ------------------------------------------------------------ telling the others

  /** Who is here, as the others see them. */
  introduce(me) {
    if (me && me.peer) {
      this.sayNow({ user: { peer: me.peer, name: me.name, color: me.color || "#7c3aed" } });
    }
  }

  /** What this browser is doing; goes out with the next message (for what changes all the time). */
  say(fields) {
    Object.assign(this.pending, fields);
    if (!this.sayTimer) this.sayTimer = setTimeout(() => this.sayNow(), SAY_MS);
  }

  sayNow(fields) {
    clearTimeout(this.sayTimer);
    this.sayTimer = 0;
    const next = { ...this.awareness.getLocalState(), ...this.pending, ...fields };
    this.pending = {};
    this.awareness.setLocalState(next);
  }
}
