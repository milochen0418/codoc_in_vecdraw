"""What a link to a drawing shows where it is sent: its title, a line about it and its picture.

/doc/<id> is the app's page, the same for every drawing, so a chat app that unfurls links (Relack)
reads a drawing's Open Graph tags from /_vecdraw/og/<id> instead, as it does for CoDoc in MD's
documents. Nothing here makes a drawing: an address that leads nowhere stays one, whereas the
drawing's own page would make it.

The picture is always the drawing as it is now, so a card in an old message follows the drawing.
"""

from __future__ import annotations

import asyncio
import html

from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.routing import Route

from codoc_in_vecdraw import yjs_ws
from codoc_in_vecdraw.states.document_store import DOCUMENTS_STORE, Document, render_png

SITE_NAME = "Codoc in VecDraw"
# 3:2, the most of a picture Relack's card shows, at twice the card's size.
PICTURE_SIZE = (900, 600)
OG_PATH = "/_vecdraw/og/{doc_id}"
PICTURE_PATH = "/_vecdraw/og/{doc_id}/image.png"
# Of the words on a drawing, as many as the card has room for.
WORDS_MAX = 100


def _public_base_url(request: Request) -> str:
    """The address the link was sent with (behind nginx, from its headers)."""
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto.split(',')[0].strip()}://{host.split(',')[0].strip()}"


def describe(doc: Document) -> str:
    """The card's line, e.g. "A drawing by Mia. Bar · Door. Everyone who opens the link ...". It
    stays in the message while the picture follows the drawing, so it counts nothing."""
    text = f"A drawing by {doc['created_by_name']}." if doc["created_by_name"] else "A drawing."
    words = " · ".join(str(s.get("content") or "").strip() for s in doc["shapes"] if s.get("type") == "text" and s.get("content"))
    if words:
        text += f" {words[:WORDS_MAX].rstrip()}{'…' if len(words) > WORDS_MAX else '.'}"
    return text + " Everyone who opens the link draws on it together."


def page(url: str, picture_url: str, doc: Document) -> str:
    """The Open Graph page of the drawing at `url` (its /doc/<id>); people go on there."""
    e = html.escape
    title, text = doc["title"], describe(doc)
    meta = {
        "og:type": "website",
        "og:site_name": SITE_NAME,
        "og:title": title,
        "og:description": text,
        "og:url": url,
        "og:image": picture_url,
        "og:image:type": "image/png",
        "og:image:width": str(PICTURE_SIZE[0]),
        "og:image:height": str(PICTURE_SIZE[1]),
    }
    tags = "".join(f'<meta property="{k}" content="{e(v)}"/>' for k, v in meta.items())
    return (
        "<!doctype html><html><head><meta charset='utf-8'/>"
        f"<title>{e(title)} | {SITE_NAME}</title>"
        f'<meta name="description" content="{e(text)}"/>'
        f'<meta name="twitter:card" content="summary_large_image"/>{tags}'
        f'<link rel="canonical" href="{e(url)}"/>'
        f'<meta http-equiv="refresh" content="0; url={e(url)}"/>'
        f'</head><body><a href="{e(url)}">{e(title)}</a></body></html>'
    )


async def og_page(request: Request) -> Response:
    doc_id = request.path_params["doc_id"]
    doc = await yjs_ws.current(doc_id)
    if doc is None:
        return HTMLResponse("<!doctype html><title>No such drawing</title>", status_code=404)
    base = _public_base_url(request)
    body = page(f"{base}/doc/{doc_id}", base + PICTURE_PATH.format(doc_id=doc_id), doc)
    return HTMLResponse(body, headers={"Cache-Control": "public, max-age=60"})


async def og_picture(request: Request) -> Response:
    doc_id = request.path_params["doc_id"]
    doc = await yjs_ws.current(doc_id)
    if doc is None:
        return Response(status_code=404)
    body = await asyncio.to_thread(render_png, doc["shapes"], lambda name: DOCUMENTS_STORE.image(doc_id, name), PICTURE_SIZE)
    return Response(body, media_type="image/png", headers={"Cache-Control": "public, max-age=60"})


ROUTES = [Route(OG_PATH, og_page, methods=["GET"]), Route(PICTURE_PATH, og_picture, methods=["GET"])]


def register(app) -> None:  # noqa: ANN001 - Reflex App
    """Offers a drawing's Open Graph tags and picture on ``app``'s backend."""
    app._api.routes.extend(ROUTES)
