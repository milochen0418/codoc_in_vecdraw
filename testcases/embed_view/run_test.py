"""E2E: what other apps show of a drawing: the link's card and the page to look at.

1. The Open Graph page and the picture of a drawing, and none of an address that leads nowhere.
2. The page to look at, in a frame on another page: it shows the drawing and says its shape.
3. Someone draws: the frame shows it, with no reload, and nobody more is on the drawing.
4. The drawing is deleted: the frame says so.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:3000").rstrip("/")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
HEADLESS = os.environ.get("HEADLESS", "1") != "0"
IGNORE_HTTPS = os.environ.get("IGNORE_HTTPS_ERRORS", "") == "1"
HOST_RULES = os.environ.get("HOST_RESOLVER_RULES", "")
DOC_ID = f"e2e-embed-{int(time.time())}"


def step(msg):
    print(f"- {msg}", flush=True)


def get(path):
    with urllib.request.urlopen(BACKEND_URL + path, timeout=10) as r:
        return r.status, r.headers.get("content-type", ""), r.read()


def drag(page, x1, y1, x2, y2):
    box = page.locator("#main-canvas").bounding_box()
    page.mouse.move(box["x"] + x1, box["y"] + y1)
    page.mouse.down()
    page.mouse.move(box["x"] + x2, box["y"] + y2, steps=8)
    page.mouse.up()


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, args=[f"--host-resolver-rules={HOST_RULES}"] if HOST_RULES else [])
        options = {"viewport": {"width": 1280, "height": 720}, "ignore_https_errors": IGNORE_HTTPS}
        editor = browser.new_context(**options).new_page()
        reader = browser.new_context(**options).new_page()
        editor.goto(f"{BASE_URL}/doc/{DOC_ID}")
        editor.wait_for_selector("#main-canvas", timeout=60000)
        editor.wait_for_function("() => window.vecdraw", timeout=60000)
        editor.click('button[title="Rectangle"]')
        drag(editor, 100, 100, 400, 300)
        editor.wait_for_timeout(300)

        step("The card: Open Graph tags and a picture")
        status, kind, body = get(f"/_vecdraw/og/{DOC_ID}")
        text = body.decode()
        assert status == 200 and "html" in kind and "og:title" in text and f"/doc/{DOC_ID}" in text, text[:400]
        status, kind, body = get(f"/_vecdraw/og/{DOC_ID}/image.png")
        assert status == 200 and kind == "image/png" and body[:4] == b"\x89PNG"
        try:
            get("/_vecdraw/og/no-such-drawing")
            raise AssertionError("an address leading nowhere got a card")
        except urllib.error.HTTPError as e:
            assert e.code == 404

        step("The page to look at, in a frame on another page")
        reader.goto(f"{BACKEND_URL}/ping")
        reader.evaluate("""(src) => { window.said = []; window.loads = 0;
            window.addEventListener('message', (e) => window.said.push(e.data));
            const f = document.createElement('iframe');
            f.src = src;
            f.style.cssText = 'width:600px;height:400px;border:0';
            f.onload = () => { window.loads += 1; };
            document.body.appendChild(f); }""", f"{BACKEND_URL}/_vecdraw/embed/{DOC_ID}")
        frame = None
        for _ in range(100):
            frame = next((f for f in reader.frames if "/_vecdraw/embed/" in f.url), None)
            if frame:
                break
            reader.wait_for_timeout(100)
        frame.wait_for_selector("svg rect", timeout=10000)

        step("Someone draws: the frame shows it, with no reload")
        editor.click('button[title="Ellipse"]')
        t0 = time.time()
        drag(editor, 300, 200, 600, 420)
        frame.wait_for_selector("svg ellipse", timeout=8000)
        print(f"  in the frame after {(time.time() - t0) * 1000:.0f} ms")
        assert reader.evaluate("window.loads") == 1, "the frame reloaded"
        reader.wait_for_function("window.said.some((m) => m.type === 'vecdraw-embed' && m.ratio > 0)", timeout=5000)
        assert editor.get_by_text("1 here").count() == 1, "reading the drawing put someone on it"

        step("The drawing is deleted: the frame says so")
        editor.goto(f"{BASE_URL}/")
        row = editor.locator("tbody tr", has_text=DOC_ID)
        row.wait_for(timeout=30000)
        row.get_by_title("Delete document").click()
        editor.get_by_role("alertdialog").get_by_role("button", name="Delete").click()
        frame.wait_for_selector("#note", timeout=8000)
        assert "there any more" in frame.locator("#note").inner_text()
        browser.close()
    print("Success! What other apps show of a drawing works.")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)
