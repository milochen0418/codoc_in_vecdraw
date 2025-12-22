import reflex as rx
from codoc_in_vecdraw.components.toolbar import toolbar
from codoc_in_vecdraw.components.topbar import topbar
from codoc_in_vecdraw.components.canvas import canvas
from codoc_in_vecdraw.components.properties_panel import properties_panel
from codoc_in_vecdraw.states.editor_state import EditorState


def index() -> rx.Component:
    """Main editor interface."""
    return rx.el.main(
        topbar(),
        rx.el.div(
            toolbar(),
            canvas(),
            properties_panel(),
            class_name="flex flex-1 overflow-hidden",
        ),
        class_name="flex flex-col h-screen w-screen bg-white font-['Inter'] overflow-hidden",
    )


app = rx.App(
    theme=rx.theme(appearance="light"),
    head_components=[
        rx.el.link(rel="preconnect", href="https://fonts.googleapis.com"),
        rx.el.link(rel="preconnect", href="https://fonts.gstatic.com", cross_origin=""),
        rx.el.link(
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap",
            rel="stylesheet",
        ),
    ],
)
app.add_page(index, route="/", on_load=EditorState.on_load)