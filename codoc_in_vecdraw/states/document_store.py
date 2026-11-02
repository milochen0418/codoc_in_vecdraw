"""Where drawings are kept.

Mirrors codoc_in_md's ``DocumentModel`` + ``DOCUMENTS_STORE`` facade: callers use the
dict-like store and never touch SQL. The model is a plain SQLModel table because
``rx.Model`` is deprecated since Reflex 0.9.2.

On a local run a drawing is one row of the database, and its images are files in Reflex's
upload folder. Installed from re_ddns's App Store, the app is given the shared collection
``drawings`` (re_ddns's Owned Collections; the catalog entry declares it and the install sets
``DDNS_COLLECTIONS_ROOT``) and each drawing is an item of it instead, of kind ``drawing.vector``:

    drawing.json    the shapes, the same list "Export as JSON" gives
    drawing.svg     the same picture, for anyone who just wants to look at it
    drawing.yjs     the document with its edit history, which only this app reads
    images/<name>   the images placed in the drawing

with the title and the creator in the manifest and a PNG as the item's preview. A drawing is
published once and then revised in place, so its item always holds the drawing as it is now.
Any app given the collection can read the drawings, and the App Store's storage page lists them.

The drawing people are working on lives in its room (:mod:`codoc_in_vecdraw.yjs_ws`) and reaches
the store a moment after each change (:mod:`codoc_in_vecdraw.saving`).
"""

import html
import io
import json
import os
import re
import shutil
import sys
import threading
import time
import unicodedata
import uuid
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable, Optional, TypedDict
from urllib.parse import quote

import reflex as rx
import sqlalchemy as sa
import sqlmodel

try:  # on re_ddns: the drawings as items of a shared collection (_ItemDocumentStore)
    from reflex_ddns_auth.collections import Collection, ItemNotFound
    from reflex_ddns_auth.collections.refs import valid_item_id
except ImportError:
    Collection = ItemNotFound = valid_item_id = None

DEFAULT_TITLE = "Untitled drawing"

# The App Store gives the app this collection (its catalog entry declares it); every drawing is
# then an item of it, of this kind.
COLLECTION = "drawings"
KIND = "drawing.vector"
DOC_FILE = "drawing.json"
SVG_FILE = "drawing.svg"
STATE_FILE = "drawing.yjs"
IMAGE_FOLDER = "images"

# An image placed in a drawing: a generated name, and only pictures a browser shows as pictures.
IMAGE_NAME = re.compile(r"^[0-9a-f-]{8,64}\.(png|jpg|jpeg|gif|webp)$")
IMAGE_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}


class DocumentGone(Exception):
    """The stored drawing was deleted (here, or on re_ddns's storage page)."""


class DocumentModel(sqlmodel.SQLModel, table=True):
    """A stored drawing; its shapes are kept as a JSON list in ``content``."""

    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    doc_id: str = sqlmodel.Field(index=True, unique=True)
    title: str = ""
    content: str = "[]"
    created_at: float = 0.0
    updated_at: float = 0.0
    version: int = 1
    created_by_email: str = ""
    created_by_name: str = ""
    # The document with its edit history (see STATE_FILE).
    state: bytes | None = sqlmodel.Field(default=None, sa_column=sa.Column(sa.LargeBinary))


class Document(TypedDict):
    doc_id: str
    title: str
    shapes: list[dict]
    created_at: float
    updated_at: float
    version: int
    created_by_email: str
    created_by_name: str


class _DocumentStore:
    """Dict-like facade backed by the database.

    Swap out the implementation here to switch databases.
    """

    @staticmethod
    def _to_document(row: DocumentModel) -> Document:
        try:
            shapes = json.loads(row.content or "[]")
        except json.JSONDecodeError:
            shapes = []
        return Document(
            doc_id=row.doc_id,
            title=row.title or DEFAULT_TITLE,
            shapes=shapes if isinstance(shapes, list) else [],
            created_at=row.created_at,
            updated_at=row.updated_at,
            version=row.version,
            created_by_email=row.created_by_email,
            created_by_name=row.created_by_name,
        )

    @staticmethod
    def _find(session: sqlmodel.Session, doc_id: str) -> Optional[DocumentModel]:
        return session.exec(
            sqlmodel.select(DocumentModel).where(DocumentModel.doc_id == doc_id)
        ).first()

    def get(self, doc_id: str) -> Optional[Document]:
        with rx.session() as session:
            row = self._find(session, doc_id)
            return self._to_document(row) if row else None

    def __contains__(self, doc_id: str) -> bool:
        return self.get(doc_id) is not None

    def state(self, doc_id: str) -> Optional[bytes]:
        """The document with its edit history; None when only its shapes are stored."""
        with rx.session() as session:
            row = self._find(session, doc_id)
            return row.state if row else None

    def create(
        self,
        doc_id: str,
        *,
        shapes: list[dict] | None = None,
        title: str | None = None,
        creator: dict | None = None,
    ) -> Document:
        """A new drawing."""
        creator = creator or {}
        now = time.time()
        with rx.session() as session:
            row = DocumentModel(
                doc_id=doc_id,
                title=title or DEFAULT_TITLE,
                content=json.dumps(shapes or []),
                created_at=now,
                updated_at=now,
                version=1,
                created_by_email=creator.get("email", ""),
                created_by_name=creator.get("name", ""),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._to_document(row)

    def save(
        self,
        doc_id: str,
        *,
        shapes: list[dict] | None = None,
        title: str | None = None,
        state: bytes | None = None,
    ) -> None:
        """Updates the given fields of a drawing, bumping its version (DocumentGone when it was
        deleted)."""
        with rx.session() as session:
            row = self._find(session, doc_id)
            if row is None:
                raise DocumentGone(doc_id)
            if shapes is not None:
                row.content = json.dumps(shapes)
            if title is not None:
                row.title = title
            if state is not None:
                row.state = state
            row.updated_at = time.time()
            row.version += 1
            session.add(row)
            session.commit()

    def __delitem__(self, doc_id: str):
        with rx.session() as session:
            row = self._find(session, doc_id)
            if row:
                session.delete(row)
                session.commit()

    def values(self) -> list[Document]:
        """Return all documents, most-recently-updated first."""
        with rx.session() as session:
            rows = session.exec(
                sqlmodel.select(DocumentModel).order_by(DocumentModel.updated_at.desc())
            ).all()
            return [self._to_document(r) for r in rows]

    def clear(self):
        """Delete every document."""
        with rx.session() as session:
            for row in session.exec(sqlmodel.select(DocumentModel)).all():
                session.delete(row)
            session.commit()

    def add_image(self, doc_id: str, name: str, data: bytes) -> None:
        if doc_id not in self:
            raise DocumentGone(doc_id)
        path = rx.get_upload_dir() / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def image(self, doc_id: str, name: str) -> Optional[Path]:
        """An image of the drawing, as a file."""
        path = rx.get_upload_dir() / name
        return path if IMAGE_NAME.match(name) and path.is_file() else None

    def copy_images(self, source: str, target: str, names: Iterable[str]) -> None:
        """Gives a new drawing the images of another (the upload folder holds them for all)."""


class _ItemDocumentStore:
    """The drawings as items of a shared collection (re_ddns's Owned Collections).

    Drawing ``<doc_id>`` is the item ``drawings:<app>/<doc_id>`` (see the top of this module).
    Same interface as :class:`_DocumentStore`.
    """

    def __init__(self, items):
        self.items = items
        self.lock = threading.RLock()  # one write or delete at a time

    def _item(self, doc_id: str):
        """The drawing's item in our own folder (not a copy from another host), or None."""
        if not valid_item_id(doc_id):
            return None
        item = self.items.get(self.items.ref(doc_id), remote=False)
        return item if item is not None and item.kind == KIND and not item.replica else None

    @staticmethod
    def _to_document(item) -> Optional[Document]:
        try:
            shapes = json.loads(item.primary.read_bytes()) if item.primary else []
        except (OSError, ValueError):
            return None
        meta = item.meta
        return Document(
            doc_id=item.id,
            title=item.title or DEFAULT_TITLE,
            shapes=shapes if isinstance(shapes, list) else [],
            created_at=_timestamp(item.created_at),
            updated_at=_timestamp(item.updated_at),
            version=item.revision,
            created_by_email=str(meta.get("created_by_email") or ""),
            created_by_name=str(meta.get("created_by_name") or ""),
        )

    def get(self, doc_id: str) -> Optional[Document]:
        item = self._item(doc_id)
        return self._to_document(item) if item is not None else None

    def __contains__(self, doc_id: str) -> bool:
        return self._item(doc_id) is not None

    def state(self, doc_id: str) -> Optional[bytes]:
        item = self._item(doc_id)
        path = item.file(STATE_FILE) if item is not None else None
        return path.read_bytes() if path is not None and path.is_file() else None

    def _files(self, doc_id: str, target, shapes: list[dict]) -> None:
        """Writes what the shapes are stored as into a publish or a revision."""
        with target.open(DOC_FILE) as fh:
            fh.write(json.dumps(shapes, ensure_ascii=False).encode("utf-8"))
        with target.open(SVG_FILE) as fh:
            fh.write(render_svg(shapes, image_href=f"{IMAGE_FOLDER}/").encode("utf-8"))
        target.set_thumbnail(render_png(shapes, lambda name: self.image(doc_id, name)))

    def create(
        self,
        doc_id: str,
        *,
        shapes: list[dict] | None = None,
        title: str | None = None,
        creator: dict | None = None,
    ) -> Document:
        creator = creator or {}
        shapes = shapes or []
        meta = {
            "shapes": len(shapes),
            "created_by_email": creator.get("email", ""),
            "created_by_name": creator.get("name", ""),
        }
        with self.lock:
            with self.items.publish(
                doc_id, kind=KIND, primary=DOC_FILE, title=title or DEFAULT_TITLE, meta=meta
            ) as item:
                self._files(doc_id, item, shapes)
        return self.get(doc_id)

    def save(
        self,
        doc_id: str,
        *,
        shapes: list[dict] | None = None,
        title: str | None = None,
        state: bytes | None = None,
    ) -> None:
        with self.lock:
            item = self._item(doc_id)
            if item is None:
                raise DocumentGone(doc_id)
            meta = None if shapes is None else {**item.meta, "shapes": len(shapes)}
            try:
                with self.items.revise(doc_id, title=title, meta=meta) as rev:
                    if shapes is not None:
                        self._files(doc_id, rev, shapes)
                    if state is not None:
                        with rev.open(STATE_FILE) as fh:
                            fh.write(state)
            except ItemNotFound:
                raise DocumentGone(doc_id)

    def __delitem__(self, doc_id: str):
        with self.lock:
            self.items.remove(doc_id)

    def values(self) -> list[Document]:
        """Return all documents, most-recently-updated first."""
        docs: list[Document] = []
        # Copies fetched from another host are that host's drawings, not ours.
        for item in self.items.items(kind=KIND, remote=False):
            if item.owner == self.items.app_id and not item.replica:
                doc = self._to_document(item)
                if doc is not None:
                    docs.append(doc)
        return sorted(docs, key=lambda d: d["updated_at"], reverse=True)

    def clear(self):
        """Delete every document."""
        for doc in self.values():
            del self[doc["doc_id"]]

    def add_image(self, doc_id: str, name: str, data: bytes) -> None:
        with self.lock:
            try:
                with self.items.revise(doc_id) as rev:
                    with rev.open(f"{IMAGE_FOLDER}/{name}") as fh:
                        fh.write(data)
            except ItemNotFound:
                raise DocumentGone(doc_id)

    def image(self, doc_id: str, name: str) -> Optional[Path]:
        item = self._item(doc_id)
        path = item.file(f"{IMAGE_FOLDER}/{name}") if item is not None and IMAGE_NAME.match(name) else None
        return path if path is not None and path.is_file() else None

    def copy_images(self, source: str, target: str, names: Iterable[str]) -> None:
        files = [(name, self.image(source, name)) for name in names]
        with self.lock:
            with self.items.revise(target) as rev:
                for name, path in files:
                    if path is not None:
                        rev.add_file(path, f"{IMAGE_FOLDER}/{name}")


def _timestamp(iso: str) -> float:
    try:
        return datetime.fromisoformat(iso).timestamp()
    except (TypeError, ValueError):
        return 0.0


def _make_store():
    """The drawings as items of the shared collection when re_ddns gave the app one, else in
    the database (``db_url`` in rxconfig.py)."""
    if os.environ.get("DDNS_COLLECTIONS_ROOT") and Collection is not None:
        if hasattr(Collection, "revise"):
            return _ItemDocumentStore(Collection(COLLECTION))
        print("Vecdraw: this reflex_ddns_auth can't revise items; drawings stay in the database", file=sys.stderr)
    return _DocumentStore()


DOCUMENTS_STORE = _make_store()


def new_doc_id() -> str:
    """Generate a short id for a new document."""
    return uuid.uuid4().hex[:8]


def new_image_name(ext: str) -> str:
    """The name an image gets in its drawing."""
    return f"{uuid.uuid4()}.{ext}"


def image_extension(data: bytes) -> str:
    """What kind of picture these bytes are ("" when none we keep)."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return ""


def normalize_doc_id(raw: str) -> str:
    """Keep a doc id usable as a SharedState link token (letters, digits and '-')."""
    return re.sub(r"[^A-Za-z0-9-]+", "-", raw or "").strip("-")[:64]


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _text_width(content: str, size: float) -> float:
    """About how wide a line of text is: Chinese and the like take a whole em per letter."""
    return sum(size if unicodedata.east_asian_width(c) in "WF" else size * 0.6 for c in content)


def _svg(shapes: list[dict], image_href: str | None) -> tuple[list[str], list[tuple[float, float, float, float]]]:
    """The shapes as SVG elements, and the box of each."""
    elements: list[str] = []
    boxes: list[tuple[float, float, float, float]] = []
    for s in shapes:
        kind = s.get("type")
        x, y = _num(s.get("x")), _num(s.get("y"))
        w, h = _num(s.get("width")), _num(s.get("height"))
        fill = html.escape(str(s.get("fill") or "none"), quote=True)
        stroke = html.escape(str(s.get("stroke") or "none"), quote=True)
        sw = _num(s.get("stroke_width"), 1)
        paint = f'fill="{fill}" stroke="{stroke}" stroke-width="{sw:g}"'
        if kind == "rectangle":
            elements.append(f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" {paint}/>')
        elif kind == "ellipse":
            elements.append(
                f'<ellipse cx="{x + w / 2:g}" cy="{y + h / 2:g}" rx="{w / 2:g}" ry="{h / 2:g}" {paint}/>'
            )
        elif kind == "triangle":
            elements.append(
                f'<polygon points="{x + w / 2:g},{y:g} {x:g},{y + h:g} {x + w:g},{y + h:g}" {paint}/>'
            )
        elif kind == "line":
            ex, ey = _num(s.get("end_x")), _num(s.get("end_y"))
            elements.append(
                f'<line x1="{x:g}" y1="{y:g}" x2="{ex:g}" y2="{ey:g}" stroke="{stroke}" stroke-width="{sw:g}"/>'
            )
            boxes.append((min(x, ex), min(y, ey), max(x, ex), max(y, ey)))
            continue
        elif kind == "pencil":
            d = html.escape(str(s.get("path_data") or ""), quote=True)
            elements.append(
                f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{sw:g}" '
                'stroke-linecap="round" stroke-linejoin="round"/>'
            )
        elif kind == "text":
            content = str(s.get("content") or "")
            size = h or 20
            w = max(w, _text_width(content, size))
            h = size
            elements.append(
                f'<text x="{x:g}" y="{y:g}" font-size="{size:g}" dominant-baseline="hanging" '
                f'font-family="sans-serif" fill="{fill}">{html.escape(content)}</text>'
            )
        elif kind == "image":
            src = html.escape(str(s.get("src") or ""), quote=True)
            if image_href is None:
                elements.append(
                    f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" fill="#e5e7eb" stroke="#9ca3af"/>'
                )
            else:
                elements.append(
                    f'<image href="{image_href}{src}" x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" '
                    'preserveAspectRatio="none"/>'
                )
        else:
            continue
        boxes.append((x, y, x + w, y + h))
    return elements, boxes


def render_svg(shapes: list[dict], image_href: str | None = None) -> str:
    """The shapes as a standalone SVG. ``image_href`` is where it finds the drawing's images;
    without one they are drawn as placeholders."""
    elements, boxes = _svg(shapes, image_href)
    if not boxes:
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"/>'
    pad = 8
    min_x = min(b[0] for b in boxes) - pad
    min_y = min(b[1] for b in boxes) - pad
    width = max(b[2] for b in boxes) + pad - min_x
    height = max(b[3] for b in boxes) + pad - min_y
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{min_x:g} {min_y:g} {width:g} {height:g}" '
        f'preserveAspectRatio="xMidYMid meet">{"".join(elements)}</svg>'
    )


def render_thumbnail(shapes: list[dict]) -> str:
    """Render shapes as a small standalone SVG data URI for the document list.

    Uploaded images are drawn as placeholders: an <img>-embedded SVG cannot load them.
    """
    if not _svg(shapes, None)[1]:
        return ""
    return "data:image/svg+xml;charset=utf-8," + quote(render_svg(shapes))


# Pillow reads rgba() only with a whole number for the alpha.
_RGBA = re.compile(r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)")


def _color(value) -> tuple | None:
    """A shape's colour for Pillow; None when it paints nothing."""
    from PIL import ImageColor

    text = str(value or "").strip()
    if not text or text in ("none", "transparent"):
        return None
    see_through = _RGBA.fullmatch(text)
    if see_through:
        red, green, blue, alpha = see_through.groups()
        return int(red), int(green), int(blue), round(min(float(alpha), 1) * 255)
    try:
        return ImageColor.getrgb(text)
    except ValueError:
        return None


# The preview on the storage page.
PREVIEW_SIZE = (480, 300)

# A font with Chinese, Japanese and Korean in it, with the index of the Traditional Chinese one
# where a file holds several (apt-packages.txt installs the first; the others are a Mac's).
TEXT_FONTS = (
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 3),
    ("/System/Library/Fonts/STHeiti Medium.ttc", 0),
    ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0),
)
# Where a line of text sits under its top, in em: what the editor's "hanging" baseline comes to.
TEXT_BASELINE = 0.8


@lru_cache(maxsize=1)
def _text_font() -> tuple[str, int] | None:
    return next((font for font in TEXT_FONTS if os.path.isfile(font[0])), None)


def _font_for(content: str, size: float):
    """A font to write this text with at this size; None when there is none that has its letters
    (Pillow's own has only English ones)."""
    from PIL import ImageFont

    if size < 6:
        return None
    found = _text_font()
    if found is not None:
        return ImageFont.truetype(found[0], size, index=found[1])
    return ImageFont.load_default(size=size) if content.isascii() else None


def render_png(
    shapes: list[dict],
    image_file: Callable[[str], Optional[Path]] | None = None,
    picture_size: tuple[int, int] = PREVIEW_SIZE,
) -> bytes:
    """A small PNG of the drawing, for the storage page (it shows no SVG) and for the AI to see,
    drawn with Pillow so that it needs no browser: drawings also change without one."""
    from PIL import Image, ImageDraw

    scale_up = 2  # drawn big and scaled down, for smooth edges
    width, height = picture_size[0] * scale_up, picture_size[1] * scale_up
    picture = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(picture, "RGBA")  # "RGBA": a see-through colour lets what is below show
    boxes = _svg(shapes, None)[1]
    if boxes:
        min_x, min_y = min(b[0] for b in boxes), min(b[1] for b in boxes)
        box_w = max(max(b[2] for b in boxes) - min_x, 1)
        box_h = max(max(b[3] for b in boxes) - min_y, 1)
        pad = 12 * scale_up
        scale = min((width - 2 * pad) / box_w, (height - 2 * pad) / box_h)
        left = (width - box_w * scale) / 2
        top = (height - box_h * scale) / 2

        def px(x: float, y: float) -> tuple[float, float]:
            return left + (x - min_x) * scale, top + (y - min_y) * scale

        for s in shapes:
            kind = s.get("type")
            x, y = _num(s.get("x")), _num(s.get("y"))
            w, h = _num(s.get("width")), _num(s.get("height"))
            fill, stroke = _color(s.get("fill")), _color(s.get("stroke"))
            line = max(1, round(_num(s.get("stroke_width"), 1) * scale)) if stroke else 0
            x0, y0 = px(x, y)
            x1, y1 = px(x + w, y + h)
            if kind == "rectangle" and x1 > x0 and y1 > y0:
                draw.rectangle((x0, y0, x1, y1), fill=fill, outline=stroke, width=line)
            elif kind == "ellipse" and x1 > x0 and y1 > y0:
                draw.ellipse((x0, y0, x1, y1), fill=fill, outline=stroke, width=line)
            elif kind == "triangle":
                points = [px(x + w / 2, y), px(x, y + h), px(x + w, y + h)]
                draw.polygon(points, fill=fill, outline=stroke, width=line)
            elif kind == "line" and stroke:
                draw.line((x0, y0, *px(_num(s.get("end_x")), _num(s.get("end_y")))), fill=stroke, width=line)
            elif kind == "pencil" and stroke:
                points = [px(_num(p.get("x")), _num(p.get("y"))) for p in s.get("points") or []]
                if len(points) > 1:
                    draw.line(points, fill=stroke, width=line, joint="curve")
            elif kind == "text":
                content = str(s.get("content") or "")
                size = (h or 20) * scale
                font = _font_for(content, size)
                if font is not None:
                    draw.text((x0, y0 + size * TEXT_BASELINE), content, fill=fill or "black", font=font, anchor="ls")
                else:  # a bar where the text is
                    draw.rectangle((x0, y0, x0 + _text_width(content, size), y0 + size * 0.8), fill="#d1d5db")
            elif kind == "image" and x1 > x0 and y1 > y0:
                box = (int(x0), int(y0), int(x1), int(y1))
                path = image_file(str(s.get("src") or "")) if image_file else None
                try:
                    with Image.open(path) as source:
                        photo = source.convert("RGB").resize((box[2] - box[0], box[3] - box[1]))
                    picture.paste(photo, box[:2])
                except (OSError, ValueError, AttributeError, TypeError):
                    draw.rectangle(box, fill="#e5e7eb", outline="#9ca3af", width=scale_up)
    output = io.BytesIO()
    picture.resize(picture_size, Image.Resampling.LANCZOS).save(output, "PNG", optimize=True)
    return output.getvalue()
