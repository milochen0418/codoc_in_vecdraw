"""The AI operations."""

import pytest

from codoc_in_vecdraw import ops


def test_shapes():
    clear, shapes = ops.run(
        [
            {"op": "addRect", "x": 1, "y": 2, "width": 3, "height": 4, "fill": "red", "id": "a"},
            {"op": "add_ellipse", "cx": 100, "cy": 100, "rx": 50, "ry": 25},
            {"op": "addText", "x": 5, "y": 6, "content": "Hi", "font_size": 18},
            {"op": "addLine", "x": 1, "y": 1, "end_x": 9, "end_y": 9, "stroke": "black"},
        ]
    )
    assert not clear
    assert [s["type"] for s in shapes] == ["rectangle", "ellipse", "text", "line"]
    assert shapes[0]["id"] == "a" and shapes[0]["fill"] == "red"
    assert (shapes[1]["x"], shapes[1]["y"], shapes[1]["width"], shapes[1]["height"]) == (50, 75, 100, 50)
    assert shapes[2]["content"] == "Hi" and shapes[2]["height"] == 18
    assert shapes[3]["end_x"] == 9
    assert len({s["id"] for s in shapes}) == 4


def test_clear_takes_what_came_before_it():
    clear, shapes = ops.run([{"op": "addRect"}, {"op": "clear"}, {"op": "addLine"}])
    assert clear and [s["type"] for s in shapes] == ["line"]


def test_a_mistake_is_said_out_loud():
    with pytest.raises(ValueError, match="Unknown operation: paint"):
        ops.run([{"op": "paint"}])
    with pytest.raises(ValueError):
        ops.parse("not json")
    with pytest.raises(ValueError):
        ops.parse("[1, 2]")


def test_numbers_must_be_numbers():
    assert ops.run([{"op": "addRect", "x": "12"}])[1][0]["x"] == 12
    with pytest.raises(ValueError, match="x must be a number"):
        ops.run([{"op": "addRect", "x": "left"}])
    with pytest.raises(ValueError, match="cx must be a number"):
        ops.run([{"op": "addEllipse", "cx": None}])


def test_one_operation_needs_no_list():
    assert ops.parse('{"op": "clear"}') == [{"op": "clear"}]
