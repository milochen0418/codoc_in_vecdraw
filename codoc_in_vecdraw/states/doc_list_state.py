"""State for the document manager page (/)."""

import datetime
import time
from typing import TypedDict

import reflex as rx

from codoc_in_vecdraw.states.document_store import (
    DOCUMENTS_STORE,
    new_doc_id,
    normalize_doc_id,
    render_thumbnail,
)

SEARCH_INPUT_ID = "doc-list-search"


class DocListItem(TypedDict):
    doc_id: str
    title: str
    updated_at: float
    formatted_time: str
    shape_count: int
    is_empty: bool
    snippet: str
    thumbnail: str


class DocListState(rx.State):
    """Lists the stored drawings with search, filters and delete actions."""

    # Filtered + sorted view shown in the table.
    documents: list[DocListItem] = []
    total_count: int = 0
    empty_count: int = 0

    # Filters
    search: str = ""
    time_filter: str = "any"  # any | today | 7d | 30d | older
    sort_by: str = "updated_desc"  # updated_desc | updated_asc | title_asc | title_desc
    only_empty: bool = False

    _all_docs: list[DocListItem] = []
    _texts: dict[str, str] = {}  # text-shape contents per doc, for search

    @rx.var
    def has_active_filters(self) -> bool:
        return bool(self.search.strip() or self.time_filter != "any" or self.only_empty)

    @rx.event
    def load_documents(self):
        """Load all documents from the store, then apply the current filters."""
        # Share links used to be /?room=<id>; that room is now the document /doc/<id>.
        room = normalize_doc_id(self.router.url.query_parameters.get("room", ""))
        if room:
            return rx.redirect(f"/doc/{room}")
        self._reload()

    def _reload(self):
        all_docs: list[DocListItem] = []
        texts: dict[str, str] = {}
        for d in DOCUMENTS_STORE.values():
            shapes = d["shapes"]
            all_docs.append(
                DocListItem(
                    doc_id=d["doc_id"],
                    title=d["title"],
                    updated_at=d["updated_at"],
                    formatted_time=(
                        datetime.datetime.fromtimestamp(d["updated_at"]).strftime("%Y-%m-%d %H:%M")
                        if d["updated_at"] > 0
                        else ""
                    ),
                    shape_count=len(shapes),
                    is_empty=not shapes,
                    snippet="",
                    thumbnail=render_thumbnail(shapes),
                )
            )
            texts[d["doc_id"]] = " ".join(
                str(s.get("content", "")) for s in shapes if s.get("type") == "text"
            )
        self._all_docs = all_docs
        self._texts = texts
        self.total_count = len(all_docs)
        self.empty_count = sum(1 for d in all_docs if d["is_empty"])
        self._apply_filters()

    def _apply_filters(self):
        now = time.time()
        day = 86400
        start_of_today = time.mktime(time.localtime(now)[:3] + (0, 0, 0, 0, 0, -1))
        query = self.search.strip().lower()

        result: list[DocListItem] = []
        for d in self._all_docs:
            ts = d["updated_at"]
            if self.time_filter == "today" and ts < start_of_today:
                continue
            if self.time_filter == "7d" and ts < now - 7 * day:
                continue
            if self.time_filter == "30d" and ts < now - 30 * day:
                continue
            if self.time_filter == "older" and ts >= now - 30 * day:
                continue

            if self.only_empty and not d["is_empty"]:
                continue

            snippet = ""
            if query and query not in f"{d['title']} {d['doc_id']}".lower():
                text = self._texts.get(d["doc_id"], "")
                pos = text.lower().find(query)
                if pos < 0:
                    continue
                start = max(0, pos - 40)
                end = min(len(text), pos + len(query) + 60)
                snippet = ("…" if start > 0 else "") + text[start:end] + ("…" if end < len(text) else "")
            result.append({**d, "snippet": snippet})

        if self.sort_by == "updated_asc":
            result.sort(key=lambda d: d["updated_at"])
        elif self.sort_by == "title_asc":
            result.sort(key=lambda d: d["title"].lower())
        elif self.sort_by == "title_desc":
            result.sort(key=lambda d: d["title"].lower(), reverse=True)
        else:
            result.sort(key=lambda d: d["updated_at"], reverse=True)
        self.documents = result

    @rx.event
    def set_search(self, value: str):
        self.search = value
        self._apply_filters()

    @rx.event
    def set_time_filter(self, value: str):
        self.time_filter = value
        self._apply_filters()

    @rx.event
    def set_sort_by(self, value: str):
        self.sort_by = value
        self._apply_filters()

    @rx.event
    def toggle_only_empty(self):
        self.only_empty = not self.only_empty
        self._apply_filters()

    @rx.event
    def clear_search(self):
        self.search = ""
        self._apply_filters()
        # The search box is uncontrolled, so clear its DOM value explicitly.
        return rx.set_value(SEARCH_INPUT_ID, "")

    @rx.event
    def reset_filters(self):
        self.search = ""
        self.time_filter = "any"
        self.only_empty = False
        self._apply_filters()
        return rx.set_value(SEARCH_INPUT_ID, "")

    @rx.event
    def create_document(self):
        """Create an empty drawing and open it."""
        doc_id = new_doc_id()
        DOCUMENTS_STORE.save(doc_id)
        return rx.redirect(f"/doc/{doc_id}")

    @rx.event
    def delete_document(self, doc_id: str):
        """Delete a single document and refresh the list."""
        del DOCUMENTS_STORE[doc_id]
        self._reload()

    @rx.event
    def delete_filtered_documents(self):
        """Delete every document in the current filtered view."""
        for d in self.documents:
            del DOCUMENTS_STORE[d["doc_id"]]
        self._reload()

    @rx.event
    def clear_all_documents(self):
        """Delete ALL documents."""
        DOCUMENTS_STORE.clear()
        self._reload()
