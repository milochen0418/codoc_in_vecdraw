import asyncio

import pytest
from PIL import Image
from io import BytesIO
import base64

from reflex_ddns_auth.tools import IMAGE_KEY, ToolContext

from codoc_in_vecdraw import ai_tools, ops, presence, saving, yjs_ws

CTX = ToolContext(user="assistant", caller="ai-hub")
CAT = [
    {"op": "addEllipse", "cx": 100, "cy": 100, "rx": 40, "ry": 40, "fill": "#f59e0b"},
    {"op": "addPath", "points": [[10, 20], [30, 5], [50, 20]], "stroke": "red"},
    {"op": "addLine", "x": 0, "y": 0, "end_x": 10, "end_y": 10},
    {"op": "addText", "x": 1, "y": 2, "content": "貓", "font_size": 30},
]


@pytest.fixture
def drawing(store, monkeypatch):
    monkeypatch.setattr(ai_tools, "push_later", lambda room: None)
    monkeypatch.setattr(ai_tools, "DOCUMENTS_STORE", store)
    monkeypatch.setattr(presence, "_rooms", {})
    store.create("cat", title="Cat")
    return "cat"


def run(coro):
    async def go():
        result = await coro
        for timer in saving._timers.values():
            timer.cancel()
        saving._timers.clear()
        return result

    return asyncio.run(go())


def test_draw_adds_shapes_and_the_ai_is_there(drawing):
    done = run(ai_tools.draw(CTX, drawing, CAT))
    assert done["added"] == 4
    read = run(ai_tools.read(CTX, drawing))
    assert [s["type"] for s in read["shapes"]] == ["ellipse", "pencil", "line", "text"]
    assert read["shapes"][1]["points"] == 3 and "path_data" not in read["shapes"][1]
    assert read["shapes"][2]["stroke"] == "#000000"  # a line is always visible
    assert read["shapes"][3]["font_size"] == 30
    assert read["covers"]["width"] > 0
    assert [t["name"] for t in presence.tabs(drawing)] == ["AI"]
    assert presence.users_on(drawing) == []  # a call doesn't ring it


def test_a_path_is_a_stroke_the_editor_can_move():
    _, [shape] = ops.run([{"op": "addPath", "points": [[10, 20], {"x": 30, "y": 5}]}])
    assert shape["type"] == "pencil" and shape["fill"] == "none"
    assert (shape["x"], shape["y"], shape["width"], shape["height"]) == (10, 5, 20, 15)
    assert shape["path_data"] == "M 10 20 L 30 5"


@pytest.mark.parametrize("bad", [[], [{"op": "clear"}], [{"op": "paint"}], [{"op": "addPath", "points": [[1, 2]]}]])
def test_draw_refuses_what_it_should(drawing, bad):
    with pytest.raises(ValueError):
        run(ai_tools.draw(CTX, drawing, bad))


def test_change_moves_whole_shapes(drawing):
    ids = run(ai_tools.draw(CTX, drawing, CAT))["ids"]
    run(ai_tools.change(CTX, drawing, [
        {"id": ids[0], "fill": "#000"},
        {"id": ids[1], "x": 110, "width": 80},
        {"id": ids[2], "x": 5},
        {"id": ids[3], "font_size": 12, "content": "狗"},
    ]))
    shapes = {s["id"]: s for s in yjs_ws.find(drawing).shape_list()}
    assert shapes[ids[0]]["fill"] == "#000"
    assert shapes[ids[1]]["points"][0] == {"x": 110, "y": 20} and shapes[ids[1]]["points"][1]["x"] == 150
    assert (shapes[ids[2]]["x"], shapes[ids[2]]["end_x"]) == (5, 15)
    assert (shapes[ids[3]]["height"], shapes[ids[3]]["content"]) == (12, "狗")
    with pytest.raises(ValueError, match="no shape"):
        run(ai_tools.change(CTX, drawing, [{"id": "x", "fill": "red"}]))
    with pytest.raises(ValueError, match="can't be changed"):
        run(ai_tools.change(CTX, drawing, [{"id": ids[0], "src": "x"}]))


def test_remove(drawing):
    ids = run(ai_tools.draw(CTX, drawing, CAT))["ids"]
    assert run(ai_tools.remove(CTX, drawing, ids=ids[:1]))["removed"] == 1
    with pytest.raises(ValueError):
        run(ai_tools.remove(CTX, drawing, ids=["nope"]))
    with pytest.raises(ValueError):
        run(ai_tools.remove(CTX, drawing))
    assert run(ai_tools.remove(CTX, drawing, everything=True))["removed"] == 3
    assert run(ai_tools.read(CTX, drawing))["count"] == 0


def test_snapshot_is_a_picture(drawing):
    assert "message" in run(ai_tools.snapshot(CTX, drawing))
    run(ai_tools.draw(CTX, drawing, CAT))
    shot = run(ai_tools.snapshot(CTX, drawing))
    assert shot[IMAGE_KEY]
    assert Image.open(BytesIO(base64.b64decode(shot["data"]))).size == ai_tools.SNAPSHOT_SIZE


def test_create_and_list(drawing):
    made = run(ai_tools.create(CTX, "  A   dog ", CAT))
    listed = run(ai_tools.list_drawings(CTX))["drawings"]
    assert {"room": made["room"], "title": "A dog", "shapes": 4, "created_by": "AI"} in listed
    with pytest.raises(ValueError, match="no drawing"):
        run(ai_tools.read(CTX, "missing"))
