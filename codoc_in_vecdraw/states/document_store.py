"""Persistent storage for vecdraw documents (one row per drawing).

Mirrors codoc_in_md's ``DocumentModel`` + ``DOCUMENTS_STORE`` facade: callers use the
dict-like store and never touch SQL. The model is a plain SQLModel table because
``rx.Model`` is deprecated since Reflex 0.9.2.
"""

import html
import json
import re
import time
import uuid
from typing import Optional, TypedDict
from urllib.parse import quote

import reflex as rx
import sqlmodel

DEFAULT_TITLE = "Untitled drawing"


class DocumentModel(sqlmodel.SQLModel, table=True):
    """A stored drawing; its shapes are kept as a JSON list in ``content``."""

    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    doc_id: str = sqlmodel.Field(index=True, unique=True)
    title: str = ""
    content: str = "[]"
    created_at: float = 0.0
    updated_at: float = 0.0
    version: int = 1


class Document(TypedDict):
    doc_id: str
    title: str
    shapes: list[dict]
    created_at: float
    updated_at: float
    version: int


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

    def save(
        self,
        doc_id: str,
        *,
        shapes: list[dict] | None = None,
        title: str | None = None,
    ) -> Document:
        """Create the document or update the given fields, bumping its version."""
        now = time.time()
        with rx.session() as session:
            row = self._find(session, doc_id)
            if row is None:
                row = DocumentModel(
                    doc_id=doc_id,
                    title=title or DEFAULT_TITLE,
                    content=json.dumps(shapes or []),
                    created_at=now,
                    updated_at=now,
                    version=1,
                )
            else:
                if shapes is not None:
                    row.content = json.dumps(shapes)
                if title is not None:
                    row.title = title
                row.updated_at = now
                row.version += 1
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._to_document(row)

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


DOCUMENTS_STORE = _DocumentStore()


def new_doc_id() -> str:
    """Generate a short id for a new document."""
    return uuid.uuid4().hex[:8]


def normalize_doc_id(raw: str) -> str:
    """Keep a doc id usable as a SharedState link token (letters, digits and '-')."""
    return re.sub(r"[^A-Za-z0-9-]+", "-", raw or "").strip("-")[:64]


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def render_thumbnail(shapes: list[dict]) -> str:
    """Render shapes as a small standalone SVG data URI for the document list.

    Uploaded images are drawn as placeholders: an <img>-embedded SVG cannot load them.
    """
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
            w = max(w, len(content) * size * 0.6)
            h = size
            elements.append(
                f'<text x="{x:g}" y="{y:g}" font-size="{size:g}" dominant-baseline="hanging" '
                f'font-family="sans-serif" fill="{fill}">{html.escape(content)}</text>'
            )
        elif kind == "image":
            elements.append(
                f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" fill="#e5e7eb" stroke="#9ca3af"/>'
            )
        else:
            continue
        boxes.append((x, y, x + w, y + h))
    if not boxes:
        return ""
    pad = 8
    min_x = min(b[0] for b in boxes) - pad
    min_y = min(b[1] for b in boxes) - pad
    width = max(b[2] for b in boxes) + pad - min_x
    height = max(b[3] for b in boxes) + pad - min_y
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{min_x:g} {min_y:g} {width:g} {height:g}" '
        f'preserveAspectRatio="xMidYMid meet">{"".join(elements)}</svg>'
    )
    return "data:image/svg+xml;charset=utf-8," + quote(svg)
