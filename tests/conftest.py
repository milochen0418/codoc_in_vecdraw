import pytest
from reflex_ddns_auth.collections import Collection

from codoc_in_vecdraw import saving, yjs_ws
from codoc_in_vecdraw.states import document_store
from codoc_in_vecdraw.states.document_store import _ItemDocumentStore


@pytest.fixture
def store(tmp_path, monkeypatch):
    """The drawings as items of a collection in a temporary folder, as on re_ddns."""
    items = _ItemDocumentStore(Collection("drawings", root=tmp_path, app_id="vecdraw"))
    monkeypatch.setattr(document_store, "DOCUMENTS_STORE", items)
    monkeypatch.setattr(yjs_ws, "DOCUMENTS_STORE", items)
    monkeypatch.setattr(saving, "DOCUMENTS_STORE", items)
    monkeypatch.setattr(yjs_ws, "_rooms", {})
    monkeypatch.setattr(saving, "gone", set())
    return items
