"""The editor itself: a local React component (``assets/vecdraw/editor.jsx``) wrapped for Reflex.

The tools, the canvas and the properties work in the browser: each person's own pointer, tool and
view shouldn't wait for the network or reach anyone else. The JSX files are plain assets (Reflex
copies ``assets/`` into the frontend), imported by ``importable_path`` as Cellora's notebook is.
The other modules sit next to it and are imported relatively, and the npm packages they import
are installed through ``lib_dependencies``.
"""

import reflex as rx

_JS = rx.asset("vecdraw/editor.jsx")
for _name in ("doc.js", "geometry.js", "others.jsx", "panels.jsx"):
    rx.asset(f"vecdraw/{_name}")


class VecdrawEditor(rx.Component):
    library = _JS.importable_path
    tag = "VecdrawEditor"
    lib_dependencies: list[str] = ["yjs@13.6.33", "y-websocket@3.1.0", "y-protocols@1.0.7", "lib0@0.2.119"]

    doc_id: rx.Var[str]
    # This tab: {"peer", "name", "color", ...}; how the others see its pointer and selection.
    me: rx.Var[dict]


editor_view = VecdrawEditor.create
