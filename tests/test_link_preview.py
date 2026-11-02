"""What a link to a drawing shows in a chat app: a page of Open Graph tags and a picture."""

import io
import re

import pytest
from PIL import Image
from starlette.applications import Starlette
from starlette.testclient import TestClient

from codoc_in_vecdraw import link_preview, yjs_ws
from codoc_in_vecdraw.link_preview import PICTURE_SIZE, describe, page
from codoc_in_vecdraw.states.document_store import render_png

RECT = {"id": "r", "type": "rectangle", "x": 0, "y": 0, "width": 300, "height": 200, "fill": "#ff0000", "stroke": "none", "stroke_width": 0}
LABEL = {"id": "t", "type": "text", "x": 20, "y": 20, "height": 40, "fill": "#000000", "content": "吧台 <Bar>"}
HEADERS = {"x-forwarded-proto": "https", "x-forwarded-host": "vecdraw.example.com"}


@pytest.fixture
def client(store):
    return TestClient(Starlette(routes=link_preview.ROUTES))


def meta(body, name):
    return re.search(rf'<meta property="{name}" content="([^"]*)"', body).group(1)


def test_the_page_tells_about_the_drawing(store, client):
    store.create("abc", title="Floor <plan>", shapes=[RECT, LABEL], creator={"name": "Mia", "email": "mia@example.com"})
    r = client.get("/_vecdraw/og/abc", headers=HEADERS)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert meta(r.text, "og:title") == "Floor &lt;plan&gt;"
    assert meta(r.text, "og:url") == "https://vecdraw.example.com/doc/abc"
    assert meta(r.text, "og:image") == "https://vecdraw.example.com/_vecdraw/og/abc/image.png"
    assert meta(r.text, "og:description").startswith("A drawing by Mia. 吧台 &lt;Bar&gt;.")
    assert "url=https://vecdraw.example.com/doc/abc" in r.text
    assert "mia@example.com" not in r.text


def test_the_picture_fills_the_card_with_the_drawing(store, client):
    store.create("abc", shapes=[RECT])
    r = client.get("/_vecdraw/og/abc/image.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    picture = Image.open(io.BytesIO(r.content)).convert("RGB")
    assert picture.size == PICTURE_SIZE
    assert picture.getpixel((450, 300)) == (255, 0, 0)


def test_the_card_shows_the_drawing_as_it_is_now(store, client):
    store.create("abc", shapes=[RECT])
    with client:
        room = client.portal.call(yjs_ws.room, "abc")
        client.portal.call(lambda: _add(room, {**LABEL, "id": "b"}))
        assert "吧台" in meta(client.get("/_vecdraw/og/abc").text, "og:description")
    assert len(store.get("abc")["shapes"]) == 1  # looking saved nothing


async def _add(room, shape):
    room.add([shape])


def test_a_card_sent_before_anyone_drew_gets_the_picture_later(store, client):
    store.create("abc")
    body = client.get("/_vecdraw/og/abc").text
    assert meta(body, "og:image").endswith("/_vecdraw/og/abc/image.png")
    assert client.get("/_vecdraw/og/abc/image.png").status_code == 200


def test_an_address_leading_nowhere_stays_one(store, client):
    assert client.get("/_vecdraw/og/nowhere").status_code == 404
    assert client.get("/_vecdraw/og/nowhere/image.png").status_code == 404
    assert "nowhere" not in store


def test_the_words_on_a_long_drawing_are_cut():
    words = [{"type": "text", "content": "word " * 40}]
    text = describe({"shapes": words, "created_by_name": ""})
    assert text.startswith("A drawing. word") and "…" in text and text.endswith("draws on it together.")


def test_a_title_cant_leave_its_tag():
    doc = {"title": '"><script>alert(1)</script>', "shapes": [], "created_by_name": ""}
    assert "<script>" not in page("https://x/doc/a", "https://x/p.png", doc)


def black(image):
    """Whether any pixel of the picture is pure black."""
    return (0, 0, 0) in {colour for _, colour in image.getcolors(1 << 24)}


def test_text_in_any_language_is_written_when_a_font_has_it(monkeypatch):
    def picture():
        return Image.open(io.BytesIO(render_png([RECT, LABEL], picture_size=PICTURE_SIZE))).convert("RGB")

    from codoc_in_vecdraw.states import document_store

    document_store._text_font.cache_clear()
    monkeypatch.setattr(document_store, "TEXT_FONTS", ())
    bar = picture()
    document_store._text_font.cache_clear()
    monkeypatch.undo()
    if document_store._text_font() is None:
        pytest.skip("no font with Chinese on this machine")
    written = picture()
    document_store._text_font.cache_clear()
    assert not black(bar) and black(written)
