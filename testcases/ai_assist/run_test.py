"""E2E: the AI Hub's tools on a drawing. What the AI draws reaches an open tab and the store, and
the page tells the assistant what it shows. Calls the app's backend the way the hub does.

Needs the server run with DDNS_AUTH_SECRET and SERVICE_SUBDOMAIN=vecdraw, and both set here too.
"""

import json
import os
import sys
import time
import urllib.request

from playwright.sync_api import expect, sync_playwright
from reflex_ddns_auth.tools import call_token

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:3000").rstrip("/")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
HEADLESS = os.environ.get("HEADLESS", "1") != "0"
SHOTS = os.environ.get("OUTPUT_DIR", "")
DOC_ID = f"e2e-ai-{int(time.time())}"
SHAPES = '#shapes-layer [id^="shape-"]'


def call(name, **args):
    request = urllib.request.Request(
        f"{BACKEND_URL}/_ddns_tool/call/{name}",
        data=json.dumps({"args": args}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {call_token('vecdraw', 'assistant')}"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{BASE_URL}/doc/{DOC_ID}")
        expect(page.locator("#main-canvas")).to_be_visible(timeout=60000)
        expect(page.locator("#ai-assist")).to_be_visible()

        print("- the page says what it shows", flush=True)
        page.wait_for_function("() => window.__ddnsContext")
        words = page.evaluate("() => window.__ddnsContext()")
        assert f"room {DOC_ID}" in words and "from x 0" in words, words

        print("- what the AI draws appears, and it shows among the people", flush=True)
        done = call(
            "vecdraw.draw",
            room=DOC_ID,
            ops=[
                {"op": "addEllipse", "cx": 300, "cy": 250, "rx": 120, "ry": 100, "fill": "#f59e0b"},
                {"op": "addTriangle", "x": 200, "y": 110, "width": 60, "height": 70, "fill": "#f59e0b"},
                {"op": "addPath", "points": [[250, 280], [300, 300], [350, 280]], "stroke": "#111827", "stroke_width": 4},
                {"op": "addText", "x": 240, "y": 380, "content": "貓", "font_size": 40, "fill": "#111827"},
            ],
        )
        print("  ", str(done)[:160])
        ids = (done.get("result") or done)["ids"]
        expect(page.locator(SHAPES)).to_have_count(4, timeout=5000)
        expect(page.get_by_text("AI", exact=True).first).to_be_attached(timeout=8000)

        print("- a stroke the AI drew moves as a person's does", flush=True)
        call("vecdraw.change", room=DOC_ID, shapes=[{"id": ids[2], "x": 400}, {"id": ids[0], "fill": "#3b82f6"}])
        expect(page.locator(f'[id="shape-{ids[0]}"]')).to_have_attribute("fill", "#3b82f6", timeout=5000)
        assert " 400 " in " " + page.locator(f'[id="shape-{ids[2]}"]').get_attribute("d") + " "

        print("- the store has it", flush=True)
        time.sleep(2.5)
        page.reload()
        expect(page.locator(SHAPES)).to_have_count(4, timeout=30000)
        if SHOTS:
            page.screenshot(path=os.path.join(SHOTS, "ai_drew.png"))

        print("- remove", flush=True)
        call("vecdraw.remove", room=DOC_ID, everything=True)
        expect(page.locator(SHAPES)).to_have_count(0, timeout=5000)
        browser.close()
    print("PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: {e}")
        sys.exit(1)
