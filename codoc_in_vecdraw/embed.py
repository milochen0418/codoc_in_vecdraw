"""A drawing on another app's page (a document in CoDoc in MD, say): to look at, not to change.

``GET /_vecdraw/embed/<id>`` is a small page of its own, not a Reflex page: it loads at once however
many a document holds, and has nothing to draw with: no state, no events, no room, so the person
isn't among the people on the drawing either. ``/_vecdraw/embed/<id>/live`` is the websocket that
carries the picture again whenever the drawing changes. Nothing here makes a drawing: an address
that leads nowhere stays one, whereas the drawing's own page would make it.
"""

from __future__ import annotations

import asyncio
import html
from typing import Callable

from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from codoc_in_vecdraw import yjs_ws
from codoc_in_vecdraw.states.document_store import render_svg

EMBED_PATH = "/_vecdraw/embed/{doc_id}"
LIVE_PATH = "/_vecdraw/embed/{doc_id}/live"
GONE = {"note": "This drawing isn't there any more.", "gone": True}
EMPTY = {"note": "This drawing is empty."}
# How much of a burst of changes (the AI drawing, say) runs together.
BURST = 0.05
# Seconds between looks at the store anyway: a drawing is also deleted without anyone on it.
LOOK_AGAIN = 30

_watchers: dict[str, set[Callable[[], None]]] = {}

PAGE_CSS = """
html { color-scheme: light; }
html, body, #drawing { height: 100%; }
body { margin: 0; background: #FFFFFF; overflow: hidden; }
#drawing svg { display: block; width: 100%; height: 100%; }
#note { padding: 12px; font: 13px system-ui, sans-serif; color: #6B7280; }
"""

# Says how tall it wants to be to the page around it, as a share of its width: the frame's width
# is that page's to know, because a browser runs nothing that measures in a frame out of sight.
# Draws the picture again each time it comes.
PAGE_JS = """
(() => {
  const box = document.getElementById("drawing");
  const tell = () => {
    if (window.parent === window) return;
    const svg = box.querySelector("svg");
    const view = svg && svg.viewBox.baseVal;
    const size = view && view.width ? {ratio: view.height / view.width} : {height: Math.ceil(box.firstElementChild.getBoundingClientRect().height)};
    window.parent.postMessage({type: "vecdraw-embed", ...size}, "*");
  };
  let gone = document.body.dataset.gone === "1";
  const show = (m) => {
    gone = !!m.gone;
    if (m.note) {
      box.innerHTML = "";
      const p = document.createElement("div");
      p.id = "note";
      p.textContent = m.note;
      box.appendChild(p);
    } else {
      box.innerHTML = m.svg;
    }
    tell();
  };
  const live = () => {
    const scheme = location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(scheme + "//" + location.host + location.pathname + "/live");
    ws.onmessage = (ev) => show(JSON.parse(ev.data));
    ws.onclose = () => { if (!gone) setTimeout(live, 2000); };
  };
  tell();
  if (!gone) live();
})();
"""


def changed(doc_id: str) -> None:
    """The drawing changed: the pages showing it get the new picture."""
    for wake in list(_watchers.get(doc_id, ())):
        wake()


async def _shown(doc_id: str) -> dict:
    """What the page shows of the drawing right now."""
    doc = await yjs_ws.current(doc_id)
    if doc is None:
        return GONE
    if not doc["shapes"]:
        return {**EMPTY, "title": doc["title"]}
    svg = await asyncio.to_thread(render_svg, doc["shapes"], f"/_vecdraw/image/{doc_id}/")
    return {"svg": svg, "title": doc["title"]}


def _page(shown: dict) -> str:
    body = f'<div id="note">{html.escape(shown["note"])}</div>' if "note" in shown else shown["svg"]
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{html.escape(shown.get("title", "Drawing"))}</title><style>{PAGE_CSS}</style></head>
<body{' data-gone="1"' if shown.get("gone") else ""}><div id="drawing">{body}</div>
<script>{PAGE_JS}</script></body></html>"""


async def page(request: Request) -> HTMLResponse:
    shown = await _shown(request.path_params["doc_id"])
    return HTMLResponse(_page(shown), status_code=404 if shown.get("gone") else 200, headers={"Cache-Control": "no-store"})


async def live(ws: WebSocket) -> None:
    """Sends the picture when it changes, for as long as the page is there."""
    await ws.accept()
    doc_id = ws.path_params["doc_id"]
    loop = asyncio.get_running_loop()
    fresh = asyncio.Event()

    def wake() -> None:
        loop.call_soon_threadsafe(fresh.set)

    async def closing() -> None:
        while (await ws.receive())["type"] != "websocket.disconnect":
            pass

    gone = asyncio.ensure_future(closing())
    _watchers.setdefault(doc_id, set()).add(wake)
    last = None
    try:
        while not gone.done():
            fresh.clear()
            shown = await _shown(doc_id)
            if shown != last:
                await ws.send_json(shown)
                last = shown
            if shown.get("gone"):
                await ws.close()
                break
            waiting = asyncio.ensure_future(fresh.wait())
            await asyncio.wait({gone, waiting}, timeout=LOOK_AGAIN, return_when=asyncio.FIRST_COMPLETED)
            waiting.cancel()
            await asyncio.sleep(BURST)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        watching = _watchers.get(doc_id, set())
        watching.discard(wake)
        if not watching:
            _watchers.pop(doc_id, None)
        gone.cancel()


ROUTES = [Route(EMBED_PATH, page, methods=["GET"]), WebSocketRoute(LIVE_PATH, live)]


def register(app) -> None:  # noqa: ANN001 - Reflex App
    """Offers a drawing to look at, for other apps' pages, on ``app``'s backend."""
    app._api.routes.extend(ROUTES)
