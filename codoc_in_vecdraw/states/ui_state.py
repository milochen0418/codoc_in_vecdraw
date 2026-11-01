"""One tab's own part of the page: who it is, and the AI Ops dialog. Nothing in here is shared
with the other tabs on the drawing.
"""

from __future__ import annotations

import json
import random
import secrets

import reflex as rx

from codoc_in_vecdraw import ops, presence

try:
    from reflex_ddns_auth import AuthState
except ImportError:  # runs without sign-in: everyone is a guest
    AuthState = None


class UiState(rx.State):
    # Who this tab is: {"peer", "user", "name", "initials", "email", "avatar", "color"}.
    me: dict[str, str] = {}
    _peer: str = ""
    _guest: str = ""

    # --- AI Operations Interface ---
    ai_ops_json: str = ""
    is_ai_modal_open: bool = False
    is_ai_docs_open: bool = False

    async def _identify(self) -> None:
        """Who this tab is: the signed-in account (reflex_ddns_auth), else a guest."""
        email = name = avatar = ""
        if AuthState is not None:
            try:
                auth = await self.get_state(AuthState)
                if not auth._auth_loaded:
                    await auth.load_auth()
                if auth.is_logged_in:
                    email, name, avatar = auth.user_email, auth.user_name or auth.user_email, auth.user_avatar
            except Exception:  # noqa: BLE001 — a guest then
                pass
        if not self._peer:
            self._peer = secrets.token_hex(6)
        if email:
            user = email
        else:
            if not self._guest:
                self._guest = str(random.randint(1000, 9999))
            # A Relack guest is signed in with a nickname but no email: keep the nickname.
            user, name = f"guest-{self._guest}", name or f"Guest {self._guest}"
        me = {
            "peer": self._peer,
            "user": user,
            "name": name,
            "initials": presence.initials(name),
            "email": email,
            "avatar": avatar,
            "color": (self.me or {}).get("color", ""),
        }
        if me != self.me:
            self.me = me

    def _set_color(self, color: str) -> None:
        if self.me.get("color") != color:
            self.me = {**self.me, "color": color}

    async def _creator(self) -> dict:
        """Who a new drawing is by."""
        await self._identify()
        return {"name": self.me.get("name", ""), "email": self.me.get("email", "")}

    @rx.event
    def follow(self, peer: str):
        """Shows where someone is on the canvas."""
        return rx.call_script(f"window.vecdraw && window.vecdraw.follow({json.dumps(peer)})")

    @rx.event
    async def leave_room(self):
        """Back on the document list: the others stop seeing this tab, and it stops hearing about
        the drawing."""
        from codoc_in_vecdraw.states.editor_state import EditorState, push_later

        left = presence.leave(self.router.session.client_token)
        if left:
            push_later(left)
        editor = await self.get_state(EditorState)
        try:
            return await editor._unlink()
        except Exception:  # noqa: BLE001 — not linked
            return None

    @rx.event
    def toggle_ai_modal(self):
        self.is_ai_modal_open = not self.is_ai_modal_open

    @rx.event
    def toggle_ai_docs(self):
        self.is_ai_docs_open = not self.is_ai_docs_open

    @rx.event
    def set_ai_ops_json(self, value: str):
        self.ai_ops_json = value

    @rx.event
    def run_ai_ops(self):
        """Parse the operations in the dialog and do them in this browser, so that they are this
        person's change: the others get it like any other, and Undo takes it back."""
        try:
            clear, shapes = ops.run(ops.parse(self.ai_ops_json))
        except (ValueError, TypeError, KeyError) as e:
            return rx.toast.error(f"Error: {e}")
        # Close modal on success
        self.is_ai_modal_open = False
        changes = json.dumps({"clear": clear, "shapes": shapes})
        return [
            rx.call_script(f"window.vecdraw && window.vecdraw.apply({changes})"),
            rx.toast("AI Operations executed successfully"),
        ]
