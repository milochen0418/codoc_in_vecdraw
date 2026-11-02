"""A drawing on another app's page: a page to look at, and what keeps it up to date."""

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from codoc_in_vecdraw import embed, yjs_ws
from codoc_in_vecdraw.states.editor_state import document_gone

RECT = {"id": "r", "type": "rectangle", "x": 0, "y": 0, "width": 300, "height": 200, "fill": "#ff0000", "stroke": "none", "stroke_width": 0}
PHOTO = {"id": "p", "type": "image", "x": 0, "y": 0, "width": 30, "height": 20, "src": "ab12cd34-0000.png"}


@pytest.fixture
def client(store, monkeypatch):
    monkeypatch.setattr(yjs_ws, "on_change", embed.changed)
    monkeypatch.setattr(embed, "BURST", 0)
    return TestClient(Starlette(routes=embed.ROUTES))


async def _add(room, shape):
    room.add([shape])


async def _clear(room):
    room.clear()


def test_the_page_shows_the_drawing(store, client):
    store.create("abc", title="Floor <plan>", shapes=[RECT, PHOTO])
    r = client.get("/_vecdraw/embed/abc")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    assert "<svg " in r.text and "<rect " in r.text and "Floor &lt;plan&gt;" in r.text
    assert 'href="/_vecdraw/image/abc/ab12cd34-0000.png"' in r.text


def test_the_page_is_nothing_to_draw_with(store, client):
    store.create("abc", shapes=[RECT])
    assert "yjs" not in client.get("/_vecdraw/embed/abc").text.lower()
    assert yjs_ws.find("abc") is None  # no room: nobody joined the drawing


def test_an_empty_drawing_says_so(store, client):
    store.create("abc")
    r = client.get("/_vecdraw/embed/abc")
    assert r.status_code == 200 and "This drawing is empty." in r.text


def test_an_address_leading_nowhere_stays_one(store, client):
    r = client.get("/_vecdraw/embed/nowhere")
    assert r.status_code == 404 and "there any more" in r.text
    assert "nowhere" not in store
    with client.websocket_connect("/_vecdraw/embed/nowhere/live") as ws:
        assert ws.receive_json()["gone"]


def test_the_picture_follows_the_drawing_and_stays_unsaved(store, client):
    store.create("abc", shapes=[RECT])
    with client, client.websocket_connect("/_vecdraw/embed/abc/live") as ws:
        assert ws.receive_json()["svg"].count("<rect ") == 1
        room = client.portal.call(yjs_ws.room, "abc")
        client.portal.call(_add, room, {**RECT, "id": "b", "x": 400})
        assert ws.receive_json()["svg"].count("<rect ") == 2
        client.portal.call(_clear, room)
        assert ws.receive_json()["note"] == "This drawing is empty."
    assert len(store.get("abc")["shapes"]) == 1  # the saving's business, not the page's
    assert not embed._watchers


def test_a_drawing_deleted_ends_the_page(store, client):
    store.create("abc", shapes=[RECT])
    with client, client.websocket_connect("/_vecdraw/embed/abc/live") as ws:
        ws.receive_json()
        del store["abc"]
        client.portal.call(document_gone, "abc")
        assert ws.receive_json()["gone"]
