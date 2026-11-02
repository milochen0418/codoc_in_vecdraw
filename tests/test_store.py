"""A drawing as an item of the shared collection: what the storage page and other apps get."""

import io
import json

import pytest
from PIL import Image

from codoc_in_vecdraw.states.document_store import (
    DOC_FILE,
    KIND,
    SVG_FILE,
    DocumentGone,
    image_extension,
    render_png,
    render_svg,
    render_thumbnail,
)

RECT = {"id": "r", "type": "rectangle", "x": 10, "y": 20, "width": 100, "height": 50, "fill": "#ff0000", "stroke": "#000000", "stroke_width": 2}
TEXT = {"id": "t", "type": "text", "x": 10, "y": 90, "width": 100, "height": 20, "fill": "#000000", "content": "<hello>"}
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"


def item(store, doc_id):
    return store.items.get(store.items.ref(doc_id), remote=False)


def test_a_new_drawing_is_an_item(store):
    doc = store.create("abc", title="Plan", creator={"name": "Milo", "email": "m@x"})
    assert doc["title"] == "Plan" and doc["shapes"] == [] and doc["created_by_name"] == "Milo"
    it = item(store, "abc")
    assert it.kind == KIND and it.primary.name == DOC_FILE and it.title == "Plan"
    assert it.meta == {"shapes": 0, "created_by_email": "m@x", "created_by_name": "Milo"}
    assert it.thumbnail is not None


def test_saving_revises_the_same_item(store):
    store.create("abc", creator={"name": "Milo"})
    store.save("abc", shapes=[RECT, TEXT], state=b"history")
    it = item(store, "abc")
    assert it.revision == 2
    assert json.loads(it.file(DOC_FILE).read_text()) == [RECT, TEXT]
    assert "<rect " in it.file(SVG_FILE).read_text() and "&lt;hello&gt;" in it.file(SVG_FILE).read_text()
    assert it.meta["shapes"] == 2 and it.meta["created_by_name"] == "Milo"
    assert store.get("abc")["shapes"] == [RECT, TEXT]
    assert store.state("abc") == b"history"
    assert [d["doc_id"] for d in store.values()] == ["abc"]


def test_renaming_leaves_the_shapes(store):
    store.create("abc", shapes=[RECT])
    store.save("abc", title="New name")
    doc = store.get("abc")
    assert doc["title"] == "New name" and doc["shapes"] == [RECT]


def test_saving_a_deleted_drawing_says_so(store):
    store.create("abc")
    del store["abc"]
    assert "abc" not in store and store.get("abc") is None
    with pytest.raises(DocumentGone):
        store.save("abc", shapes=[RECT])
    with pytest.raises(DocumentGone):
        store.add_image("abc", "11111111-2222.png", PNG)


def test_an_id_that_names_no_item_is_no_drawing(store):
    assert store.get("..") is None and store.state("..") is None
    assert store.image("..", "11111111-2222.png") is None


def test_images_live_in_the_item_and_go_with_a_copy(store):
    store.create("abc")
    name = "11111111-2222-3333-4444-555555555555.png"
    store.add_image("abc", name, PNG)
    assert store.image("abc", name).read_bytes() == PNG
    assert store.image("abc", "../../evil.png") is None
    assert store.image("abc", "11111111-2222-3333-4444-000000000000.png") is None

    picture = {"id": "i", "type": "image", "x": 0, "y": 0, "width": 40, "height": 40, "src": name}
    store.save("abc", shapes=[picture])
    assert f'href="images/{name}"' in item(store, "abc").file(SVG_FILE).read_text()

    store.create("copy", shapes=[picture])
    store.copy_images("abc", "copy", [name])
    assert store.image("copy", name).read_bytes() == PNG


def test_svg_and_previews():
    assert render_thumbnail([]) == ""
    assert render_thumbnail([RECT]).startswith("data:image/svg+xml")
    svg = render_svg([RECT, {"id": "l", "type": "line", "x": 0, "y": 0, "end_x": 5, "end_y": 5, "stroke": "red"}])
    assert svg.count("<rect") == 1 and svg.count("<line") == 1


def test_preview_is_a_picture_of_the_shapes():
    pencil = {"id": "p", "type": "pencil", "x": 0, "y": 0, "width": 50, "height": 50, "stroke": "#00ff00", "stroke_width": 3, "points": [{"x": 0, "y": 0}, {"x": 50, "y": 50}]}
    weird = {"id": "w", "type": "ellipse", "x": 0, "y": 0, "width": 0, "height": 0, "fill": "not a colour"}
    text = {"id": "c", "type": "text", "x": 0, "y": 60, "height": 12, "content": "中文"}
    missing = {"id": "m", "type": "image", "x": 0, "y": 80, "width": 40, "height": 40, "src": "gone.png"}
    picture = Image.open(io.BytesIO(render_png([RECT, pencil, weird, text, missing])))
    assert picture.format == "PNG" and picture.size == (480, 300)
    assert (255, 0, 0) in {c for _, c in picture.convert("RGB").getcolors(maxcolors=1 << 20)}


def test_preview_of_an_empty_drawing():
    assert Image.open(io.BytesIO(render_png([]))).size == (480, 300)


def test_kinds_of_images():
    assert image_extension(PNG) == "png"
    assert image_extension(b"\xff\xd8\xff\xe0....") == "jpg"
    assert image_extension(b"GIF89a....") == "gif"
    assert image_extension(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "webp"
    assert image_extension(b"<svg xmlns=") == ""


def test_a_see_through_colour_lets_what_is_below_show():
    over = {**RECT, "id": "o", "fill": "rgba(0,0,255,0.5)", "stroke": "none", "stroke_width": 0}
    below = {**RECT, "fill": "#ff0000", "stroke": "none", "stroke_width": 0}
    picture = Image.open(io.BytesIO(render_png([below, over]))).convert("RGB")
    red, green, blue = picture.getpixel((240, 150))
    assert 120 < red < 135 and green == 0 and 120 < blue < 135
