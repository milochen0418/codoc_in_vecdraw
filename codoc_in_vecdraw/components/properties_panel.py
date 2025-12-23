import reflex as rx
from codoc_in_vecdraw.states.editor_state import EditorState


def property_input(label: str, prop: str, type_: str = "text") -> rx.Component:
    """Helper to create a property input field."""
    return rx.el.div(
        rx.el.label(label, class_name="block text-xs font-medium text-gray-500 mb-1"),
        rx.el.input(
            type=type_,
            on_change=lambda val: EditorState.update_property(prop, val),
            class_name="w-full text-sm border border-gray-200 rounded-md px-2 py-1.5 focus:border-violet-500 focus:ring-1 focus:ring-violet-500 outline-none",
            default_value=EditorState.selected_shape[prop],
            key=EditorState.selected_shape["id"] + prop,
        ),
        class_name="mb-3",
    )


def properties_panel() -> rx.Component:
    """The right-side properties panel."""
    return rx.el.aside(
        rx.el.div(
            rx.el.h2(
                "Properties",
                class_name="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4",
            ),
            rx.cond(
                EditorState.selected_shape_id != "",
                rx.el.div(
                    rx.el.div(
                        rx.el.span("Type", class_name="text-xs text-gray-400"),
                        rx.el.span(
                            EditorState.selected_shape["type"],
                            class_name="text-sm font-medium capitalize",
                        ),
                        class_name="flex justify-between items-center mb-4 p-2 bg-gray-50 rounded-lg",
                    ),
                    property_input("Fill Color", "fill", "color"),
                    property_input("Stroke Color", "stroke", "color"),
                    rx.el.div(
                        rx.el.label(
                            "Stroke Width",
                            class_name="block text-xs font-medium text-gray-500 mb-1",
                        ),
                        rx.el.input(
                            type="range",
                            min="0",
                            max="20",
                            default_value=EditorState.selected_shape[
                                "stroke_width"
                            ].to_string(),
                            key=EditorState.selected_shape["id"],
                            on_change=lambda val: EditorState.update_property(
                                "stroke_width", val.to(int)
                            ).throttle(100),
                            class_name="w-full accent-violet-600",
                        ),
                        rx.el.div(
                            rx.el.span("0px"),
                            rx.el.span(
                                f"{EditorState.selected_shape['stroke_width']}px"
                            ),
                            rx.el.span("20px"),
                            class_name="flex justify-between text-[10px] text-gray-400 mt-1",
                        ),
                        class_name="mb-6",
                    ),
                    rx.el.button(
                        rx.icon("trash-2", class_name="w-4 h-4 mr-2"),
                        "Delete Shape",
                        on_click=EditorState.delete_selected,
                        class_name="flex items-center justify-center w-full px-4 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition-colors text-sm font-medium",
                    ),
                    class_name="animate-in fade-in slide-in-from-right-4 duration-200",
                ),
                rx.el.div(
                    rx.icon(
                        "mouse-pointer-click", class_name="w-8 h-8 text-gray-300 mb-2"
                    ),
                    rx.el.p(
                        "Select a shape to edit properties",
                        class_name="text-sm text-gray-400 text-center",
                    ),
                    class_name="flex flex-col items-center justify-center h-64",
                ),
            ),
            class_name="p-4",
        ),
        class_name="w-64 bg-white border-l border-gray-200 h-full flex-shrink-0 z-10 overflow-y-auto",
    )