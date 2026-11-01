"""A drawing's room: the server's copy of the shapes, saving it, and surviving a restart."""

import asyncio

from pycrdt import Doc, Map

from codoc_in_vecdraw import saving, yjs_ws
from codoc_in_vecdraw.yjs_ws import Room

RECT = {"id": "r", "type": "rectangle", "x": 10, "y": 20, "width": 100, "height": 50, "fill": "#ff0000", "stroke": "none", "stroke_width": 0, "points": []}
STROKE = {"id": "p", "type": "pencil", "x": 0, "y": 0, "width": 3, "height": 3, "points": [{"x": 0, "y": 0}, {"x": 3, "y": 3}], "path_data": "M 0 0 L 3 3"}


def browser_edit(room: Room, doc_id: str, **fields) -> None:
    """A change made in a browser's copy of the document, reaching the server."""
    theirs = Doc()
    theirs.apply_update(room.doc.get_update())
    shapes = theirs.get(yjs_ws.SHAPES, type=Map)
    for key, value in fields.items():
        shapes[doc_id][key] = value
    room.doc.apply_update(theirs.get_update(room.doc.get_state()))


def test_shapes_come_back_as_they_went_in():
    room = Room("d", shapes=[RECT, STROKE])
    assert room.shape_list() == [RECT, STROKE]
    assert isinstance(room.shape_list()[0]["x"], int)  # not the 10.0 Yjs hands back


def test_shapes_keep_their_order():
    room = Room("d", shapes=[STROKE, RECT])
    assert [s["id"] for s in room.shape_list()] == ["p", "r"]
    room.add([{**RECT, "id": "a"}])
    assert [s["id"] for s in room.shape_list()] == ["p", "r", "a"]


def test_clearing():
    room = Room("d", shapes=[RECT])
    room.clear()
    assert room.shape_list() == []


def test_two_people_change_different_fields_of_a_shape():
    room = Room("d", shapes=[RECT])
    browser_edit(room, "r", fill="#00ff00")
    browser_edit(room, "r", x=99)
    shape = room.shape_list()[0]
    assert shape["fill"] == "#00ff00" and shape["x"] == 99


def test_history_survives_a_restart():
    """A tab that stayed open still holds the same document as the server after a restart: what
    it did reaches the server, and nothing comes twice."""
    room = Room("d", shapes=[RECT])
    tab = Doc()
    tab.apply_update(room.doc.get_update())
    tab_shapes = tab.get(yjs_ws.SHAPES, type=Map)

    restarted = Room("d", state=room.doc.get_update())
    assert restarted.shape_list() == [RECT]

    tab_shapes["r"]["x"] = 500  # done while the server was away
    restarted.doc.apply_update(tab.get_update(restarted.doc.get_state()))
    restarted.add([STROKE])
    tab.apply_update(restarted.doc.get_update(tab.get_state()))

    assert [s["id"] for s in restarted.shape_list()] == ["r", "p"]
    assert restarted.shape_list()[0]["x"] == 500
    assert sorted(tab_shapes.to_py()) == ["p", "r"]


def test_a_stale_copy_from_before_a_lost_history_doubles_nothing():
    """A document built again from the stored shapes is another document: merging one with it
    can pick either version of a shape, but the same shape never comes twice."""
    first = Room("d", shapes=[RECT, STROKE])
    second = Room("d", shapes=[RECT, STROKE])
    second.doc.apply_update(first.doc.get_update())
    assert sorted(s["id"] for s in second.shape_list()) == ["p", "r"]


def test_a_history_that_cant_be_read_falls_back_on_the_shapes():
    room = Room("d", state=b"not a yjs update", shapes=[RECT])
    assert room.shape_list() == [RECT]


def test_opening_a_drawing_changes_nothing_in_the_store(store, monkeypatch):
    monkeypatch.setattr(yjs_ws, "on_change", saving.changed)

    async def run():
        store.create("d", shapes=[RECT])
        await yjs_ws.room("d")
        assert not saving._timers

    asyncio.run(run())
    assert store.items.get(store.items.ref("d"), remote=False).revision == 1


def test_a_change_is_saved_once_after_a_pause(store, monkeypatch):
    monkeypatch.setattr(saving, "SAVE_DELAY", 0.02)
    monkeypatch.setattr(yjs_ws, "on_change", saving.changed)

    async def run():
        store.create("d")
        room = await yjs_ws.room("d")
        room.add([RECT])
        room.add([STROKE])
        await asyncio.sleep(0.1)
        while saving._tasks:
            await asyncio.sleep(0.01)

    asyncio.run(run())
    assert [s["id"] for s in store.get("d")["shapes"]] == ["r", "p"]
    item = store.items.get(store.items.ref("d"), remote=False)
    assert item.revision == 2  # published, then one save for both changes


def test_someone_reading_the_store_gets_what_waits_to_be_saved(store, monkeypatch):
    monkeypatch.setattr(saving, "SAVE_DELAY", 60)
    monkeypatch.setattr(yjs_ws, "on_change", saving.changed)

    async def run():
        store.create("d")
        room = await yjs_ws.room("d")
        room.add([RECT])
        await saving.settle()

    asyncio.run(run())
    assert store.get("d")["shapes"] == [RECT]


def test_a_room_starts_from_what_was_stored(store):
    async def run():
        store.create("d", shapes=[RECT])
        first = await yjs_ws.room("d")
        assert first.shape_list() == [RECT]
        store.save("d", state=first.doc.get_update())
        yjs_ws._rooms.clear()
        again = await yjs_ws.room("d")
        assert again.doc.get_state() == first.doc.get_state()
        assert await yjs_ws.room("no-such-drawing") is None

    asyncio.run(run())


def test_a_drawing_deleted_elsewhere_is_noticed(store, monkeypatch):
    told = []

    async def on_gone(doc_id):
        told.append(doc_id)

    monkeypatch.setattr(saving, "on_gone", on_gone)

    async def run():
        store.create("d")
        room = await yjs_ws.room("d")
        del store["d"]
        room.add([RECT])
        await saving.save("d")

    asyncio.run(run())
    assert told == ["d"] and "d" in saving.gone


def test_nothing_is_saved_after_a_delete(store, monkeypatch):
    async def run():
        store.create("d")
        room = await yjs_ws.room("d")
        saving.forget("d")
        room.add([RECT])
        await saving.save("d")

    asyncio.run(run())
    assert store.get("d")["shapes"] == []


def test_flush_saves_what_waits(store, monkeypatch):
    monkeypatch.setattr(saving, "SAVE_DELAY", 60)
    monkeypatch.setattr(yjs_ws, "on_change", saving.changed)

    async def run():
        store.create("d")
        room = await yjs_ws.room("d")
        room.add([RECT])
        assert "d" in saving._timers
        saving.flush()

    asyncio.run(run())
    assert store.get("d")["shapes"] == [RECT]
