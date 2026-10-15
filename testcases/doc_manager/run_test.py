"""E2E: document manager – create, rename, draw, persist, co-edit, list, search, delete."""

import os
import re
import sys
import time

from playwright.sync_api import expect, sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:3000").rstrip("/")
HEADLESS = os.environ.get("HEADLESS", "1") != "0"
TITLE = f"E2E drawing {int(time.time())}"
SHAPE_RECTS = '#main-svg rect[id^="shape-"]'
SHAPE_ELLIPSES = '#main-svg ellipse[id^="shape-"]'


def drag(page, x1, y1, x2, y2):
    box = page.locator("#main-canvas").bounding_box()
    page.mouse.move(box["x"] + x1, box["y"] + y1)
    page.mouse.down()
    page.mouse.move(box["x"] + x2, box["y"] + y2, steps=8)
    page.mouse.up()


def step(msg):
    print(f"- {msg}", flush=True)


def run(created: list[str]):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        step(f"Open the document manager at {BASE_URL}/")
        page.goto(BASE_URL + "/", wait_until="domcontentloaded", timeout=60000)
        expect(page.get_by_role("heading", name="Document Manager")).to_be_visible(timeout=30000)

        step("New Document opens a fresh drawing at /doc/<id>")
        page.get_by_role("button", name="New Document").click()
        page.wait_for_url(re.compile(r"/doc/[0-9a-f]{8}$"), timeout=30000)
        doc_id = page.url.rsplit("/", 1)[-1]
        created.append(doc_id)
        expect(page.locator("#doc-title")).to_have_value("Untitled drawing", timeout=30000)

        step(f"Rename it to {TITLE!r}")
        page.locator("#doc-title").fill(TITLE)
        page.locator("#doc-title").press("Enter")
        expect(page.locator("#doc-title")).to_have_value(TITLE, timeout=10000)

        step("Draw a rectangle")
        page.click('button[title="Rectangle"]')
        drag(page, 200, 150, 350, 260)
        expect(page.locator(SHAPE_RECTS)).to_have_count(1, timeout=10000)

        step("Reload: the drawing and its title were saved")
        page.reload(wait_until="domcontentloaded")
        expect(page.locator(SHAPE_RECTS)).to_have_count(1, timeout=30000)
        expect(page.locator("#doc-title")).to_have_value(TITLE)

        step("A second browser on the same URL co-edits the drawing")
        other = browser.new_context(viewport={"width": 1400, "height": 900}).new_page()
        other.goto(page.url, wait_until="domcontentloaded", timeout=60000)
        expect(other.locator(SHAPE_RECTS)).to_have_count(1, timeout=30000)
        page.click('button[title="Ellipse"]')
        drag(page, 450, 150, 560, 240)
        expect(other.locator(SHAPE_ELLIPSES)).to_have_count(1, timeout=15000)
        other.context.close()

        step("The drawing is listed in My Documents with its title, shape count and preview")
        page.get_by_role("link", name="My Documents").click()
        row = page.locator("tbody tr", has_text=doc_id)
        expect(row).to_contain_text(TITLE, timeout=30000)
        expect(row).to_contain_text("2 shapes")
        expect(row.locator("img")).to_have_count(1)

        step("Search finds it by title")
        search = page.locator("#doc-list-search")
        search.fill(TITLE)
        expect(page.locator("tbody tr")).to_have_count(1, timeout=10000)
        search.fill("no-such-drawing-xyz")
        expect(page.get_by_text("No documents match these filters")).to_be_visible(timeout=10000)
        page.get_by_role("button", name="Reset filters").first.click()

        step("Delete it (after confirming)")
        page.locator("tbody tr", has_text=doc_id).get_by_title("Delete document").click()
        page.get_by_role("alertdialog").get_by_role("button", name="Delete").click()
        expect(page.locator("tbody tr", has_text=doc_id)).to_have_count(0, timeout=10000)
        created.remove(doc_id)

        assert not errors, f"uncaught page errors: {errors}"
        browser.close()


def main() -> int:
    created: list[str] = []
    try:
        run(created)
        print("Success! Document manager flow works.")
        return 0
    except Exception as e:
        print(f"Failure: {e}")
        return 1
    finally:
        # Don't leave test documents behind when a step failed before deleting them.
        if created:
            from codoc_in_vecdraw.states.document_store import DOCUMENTS_STORE

            for doc_id in created:
                del DOCUMENTS_STORE[doc_id]


if __name__ == "__main__":
    sys.exit(main())
