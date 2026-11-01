"""What shows that a drawing is worked on together: who is here (round, in their colour, as in
CoDoc in MD), who you are, Call everyone, an incoming call, and the page's heartbeat and goodbye.
"""

from __future__ import annotations

import reflex as rx

from codoc_in_vecdraw.call import CALLS_ENABLED, CallState
from codoc_in_vecdraw.states.editor_state import EditorState
from codoc_in_vecdraw.states.ui_state import AuthState, UiState

BYE_PATH = "/_vecdraw/bye"
BUTTON = "flex items-center gap-2 text-sm font-medium px-3 py-1.5 rounded-lg transition-colors whitespace-nowrap"


def face(name: rx.Var, initials: rx.Var, avatar: rx.Var, color: rx.Var, size: str = "h-8 w-8") -> rx.Component:
    """A person's circle: their picture, else their initials, ringed in their colour."""
    ring = {"borderColor": color}
    return rx.cond(
        avatar != "",
        rx.image(src=avatar, alt=name, class_name=f"{size} rounded-full border-2 object-cover bg-gray-100", style=ring),
        rx.el.span(
            initials,
            class_name=f"{size} rounded-full border-2 flex items-center justify-center text-[11px] font-bold text-white",
            style={**ring, "backgroundColor": color},
        ),
    )


def person(p) -> rx.Component:
    """Someone on the drawing; their name shows under the circle on hover, and a click shows where
    they are on the canvas."""
    return rx.el.button(
        face(p["name"], p["initials"], p["avatar"], p["color"]),
        rx.el.span(
            p["name"],
            class_name="absolute top-full mt-1.5 left-1/2 -translate-x-1/2 px-2 py-1 rounded bg-gray-900 text-white text-xs whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-20",
        ),
        on_click=UiState.follow(p["id"]),
        type="button",
        title=p["name"],
        custom_attrs={"data-name": p["name"]},
        class_name="doc-person group relative shrink-0 rounded-full hover:z-10 hover:scale-110 transition-transform",
    )


def presence() -> rx.Component:
    return rx.el.div(
        rx.el.div(rx.foreach(EditorState.people, person), class_name="flex items-center -space-x-2"),
        rx.el.span(
            EditorState.people_count.to(str) + " here",
            id="people-count",
            class_name="hidden xl:inline text-xs text-gray-500 whitespace-nowrap",
        ),
        id="presence",
        class_name="flex items-center gap-2 flex-shrink-0",
    )


def identity() -> rx.Component:
    """Who you are here, and signing in or out (with reflex_ddns_auth)."""
    me = UiState.me
    mine = rx.el.div(
        face(me["name"], me["initials"], me["avatar"], me["color"], size="h-7 w-7"),
        rx.el.span(me["name"], id="me-name", class_name="hidden 2xl:inline text-sm font-medium text-gray-700 max-w-[9rem] truncate"),
        class_name="flex items-center gap-2",
    )
    if AuthState is None:
        return mine
    link = "px-2 py-1 text-xs font-medium rounded-md transition-colors whitespace-nowrap"
    return rx.el.div(
        mine,
        rx.cond(
            AuthState.is_logged_in,
            rx.el.a("Logout", href=AuthState.logout_url, class_name=f"{link} text-gray-500 hover:text-red-600 hover:bg-red-50"),
            rx.el.a("Login", href=AuthState.login_url, class_name=f"{link} text-white bg-violet-600 hover:bg-violet-700"),
        ),
        class_name="flex items-center gap-1.5",
    )


def call_button() -> rx.Component:
    """Call everyone on the drawing, or join its call while one is in progress."""
    if not CALLS_ENABLED:
        return rx.fragment()
    return rx.cond(
        EditorState.call_count > 0,
        rx.el.button(
            rx.icon("phone-call", class_name="w-4 h-4"),
            rx.el.span("Join call · ", EditorState.call_count),
            on_click=CallState.join_call,
            id="call-join",
            title="Join the call of the people on this drawing",
            class_name=f"{BUTTON} bg-emerald-600 hover:bg-emerald-700 text-white",
        ),
        rx.el.button(
            rx.icon("phone", class_name="w-4 h-4"),
            rx.el.span("Call everyone", class_name="hidden lg:inline"),
            on_click=CallState.join_call,
            id="call-everyone",
            title="Call everyone on this drawing",
            aria_label="Call everyone",
            class_name=f"{BUTTON} bg-emerald-100 hover:bg-emerald-200 text-emerald-700",
        ),
    )


def incoming_call() -> rx.Component:
    """Someone called everyone on the drawing: accept or decline."""
    if not CALLS_ENABLED:
        return rx.fragment()
    me = UiState.me["user"]
    rung = (
        (EditorState.call_ringing_from != "")
        & EditorState.call_invited.contains(me)
        & ~EditorState.call_responded.contains(me)
    )
    round_button = "p-2.5 rounded-full flex cursor-pointer border-0"
    # Above the intent dialog (z-index 1000), so a call can be answered from inside another.
    return rx.cond(
        rung,
        rx.el.div(
            rx.el.div(
                rx.icon("phone-incoming", class_name="h-5 w-5 text-white"),
                class_name="h-10 w-10 rounded-full bg-emerald-500 flex items-center justify-center shrink-0 animate-pulse",
            ),
            rx.el.div(
                rx.el.span("Incoming call", class_name="text-[11px] font-semibold uppercase tracking-wider text-emerald-600"),
                rx.el.span(EditorState.call_ringing_from, class_name="text-sm font-bold text-gray-900 truncate"),
                rx.el.span("is calling everyone on this drawing", class_name="text-xs text-gray-500"),
                class_name="flex flex-col min-w-0 flex-1",
            ),
            rx.el.button(
                rx.icon("phone-off", class_name="h-4 w-4"),
                on_click=CallState.decline_call,
                title="Decline",
                aria_label="Decline",
                class_name=f"{round_button} bg-red-100 text-red-600 hover:bg-red-200",
            ),
            rx.el.button(
                rx.icon("phone", class_name="h-4 w-4"),
                on_click=CallState.join_call,
                title="Accept",
                aria_label="Accept",
                class_name=f"{round_button} bg-emerald-600 text-white hover:bg-emerald-700",
            ),
            role="alertdialog",
            aria_label="Incoming call",
            class_name="fixed bottom-6 right-4 sm:right-6 z-[1001] w-[min(21rem,calc(100vw-2rem))] flex items-center gap-3 p-3 rounded-2xl bg-white border border-gray-200 shadow-2xl",
        ),
    )


_CALL_HEARTBEAT_JS = """
if (window.__vecdrawCallHb) clearInterval(window.__vecdrawCallHb);
window.__vecdrawCallHb = setInterval(function () {
    var el = document.getElementById('call-heartbeat-trigger');
    if (!el) { clearInterval(window.__vecdrawCallHb); window.__vecdrawCallHb = null; return; }
    el.click();
}, 3000);
"""


@rx.memo
def call_keepalive() -> rx.Component:
    """While in a call, keep its heartbeat going on every page (the call runs in the app-wide
    intent dialogs, so it outlives the drawing page)."""
    return rx.cond(
        CallState.current_room != "",
        rx.el.button(
            id="call-heartbeat-trigger",
            on_click=CallState.heartbeat,
            on_mount=rx.call_script(_CALL_HEARTBEAT_JS),
            tab_index=-1,
            aria_hidden="true",
            class_name="sr-only",
        ),
    )


_PRESENCE_JS = f"""
if (window.__vecdrawPing) clearInterval(window.__vecdrawPing);
window.__vecdrawPing = setInterval(function () {{
    var el = document.getElementById('doc-ping');
    if (!el) {{ clearInterval(window.__vecdrawPing); window.__vecdrawPing = null; return; }}
    el.click();
}}, 5000);
if (!window.__vecdrawBye) {{
    // Closing or reloading the tab: the others stop seeing it at once (otherwise it takes
    // the server a few missed pings to notice). A beacon, because a websocket message doesn't
    // get out of a page that is going away. It goes to the backend's address, which the page
    // put on the button (Reflex's own helpers are renamed in a prod build, so this script
    // can't call them), with the tab's token as Reflex keeps it.
    window.__vecdrawBye = function () {{
        var el = document.getElementById('doc-ping');
        var token = window.sessionStorage.getItem('token');
        if (!el || !token || !navigator.sendBeacon) return;
        try {{
            var url = new URL('{BYE_PATH}', el.dataset.backend);
            navigator.sendBeacon(url.toString(), JSON.stringify({{ token: token }}));
        }} catch (e) {{}}
    }};
    window.addEventListener('pagehide', window.__vecdrawBye);
}}
"""


def page_hooks() -> rx.Component:
    """Still here: a ping every 5 s keeps this tab among the people on the drawing."""
    return rx.el.button(
        id="doc-ping",
        on_click=EditorState.ping,
        on_mount=rx.call_script(_PRESENCE_JS),
        # Any URL on the backend, as Reflex builds it in the browser (behind a proxy: on the
        # page's host); the goodbye goes to the same host.
        custom_attrs={"data-backend": rx.get_upload_url("")},
        tab_index=-1,
        aria_hidden="true",
        class_name="sr-only",
    )
