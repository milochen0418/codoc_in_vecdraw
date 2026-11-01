"""E2E: two people on one drawing. What is shared, what is each person's own, and what each sees
of the other.

Everyone's tool, view, selection handles, dialogs and undo stay their own. The shapes and the
title are the same for all. Of each other they see: pointers with names, selections, shapes being
dragged or drawn, who is here. (`Call everyone` needs a call app: see README.)
"""

import json
import os
import re
import sys
import time
import urllib.request

from playwright.sync_api import expect, sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:3000").rstrip("/")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
HEADLESS = os.environ.get("HEADLESS", "1") != "0"
IGNORE_HTTPS = os.environ.get("IGNORE_HTTPS_ERRORS", "") == "1"
HOST_RULES = os.environ.get("HOST_RESOLVER_RULES", "")
SHOTS = os.environ.get("OUTPUT_DIR", "")
DOC_ID = f"e2e-together-{int(time.time())}"
DOC_URL = f"{BASE_URL}/doc/{DOC_ID}"
RECTS = '#main-svg rect[id^="shape-"]'
ELLIPSES = '#main-svg ellipse[id^="shape-"]'
ANY_SHAPE = '#shapes-layer [id^="shape-"]'


def step(msg):
    print(f"- {msg}", flush=True)


def at(page, x, y):
    box = page.locator("#main-canvas").bounding_box()
    return box["x"] + x, box["y"] + y


def hover(page, x, y):
    page.mouse.move(*at(page, x, y), steps=3)


def press(page, x, y):
    page.mouse.move(*at(page, x, y))
    page.mouse.down()


def drag(page, x1, y1, x2, y2):
    press(page, x1, y1)
    page.mouse.move(*at(page, x2, y2), steps=8)
    page.mouse.up()


def tool(page, name):
    page.click(f'button[title="{name}"]')


def tool_on(page, name):
    return "bg-violet-100" in page.locator(f'button[title="{name}"]').get_attribute("class")


def shot(page, name):
    if SHOTS:
        page.screenshot(path=os.path.join(SHOTS, f"together_{name}.png"))


def rect_x(page):
    return float(page.locator(RECTS).first.get_attribute("x"))


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, args=[f"--host-resolver-rules={HOST_RULES}"] if HOST_RULES else [])
        size = {"width": 1400, "height": 860}
        ann = browser.new_context(viewport=size, ignore_https_errors=IGNORE_HTTPS).new_page()
        bob = browser.new_context(viewport=size, ignore_https_errors=IGNORE_HTTPS).new_page()
        errors: list[str] = []
        for page in (ann, bob):
            # Reflex's own error reporter trips over errors without an error object.
            page.on("pageerror", lambda e: errors.append(str(e)) if "window.onerror" not in (e.stack or "") else None)

        step("Both open the same link; each sees two people here")
        ann.goto(DOC_URL, wait_until="domcontentloaded", timeout=120000)
        bob.goto(DOC_URL, wait_until="domcontentloaded", timeout=120000)
        for page in (ann, bob):
            expect(page.locator("#people-count")).to_have_text("2 here", timeout=60000)
            expect(page.locator(".doc-person")).to_have_count(2)
        expect(ann.locator("#sync-notice")).to_have_count(0, timeout=30000)
        expect(bob.locator("#sync-notice")).to_have_count(0, timeout=30000)
        expect(ann.locator("#call-everyone")).to_be_visible()

        step("A tool is each person's own")
        tool(ann, "Rectangle")
        assert tool_on(ann, "Rectangle") and tool_on(bob, "Select"), "Ann's tool changed Bob's"

        step("While Ann draws, Bob sees the shape coming in her colour, not yet as a shape")
        press(ann, 200, 150)
        ann.mouse.move(*at(ann, 300, 220), steps=4)
        expect(bob.locator(".other-preview")).to_have_count(1, timeout=5000)
        expect(bob.locator(RECTS)).to_have_count(0)
        ann.mouse.move(*at(ann, 350, 260), steps=4)
        ann.mouse.up()

        step("When she lets go it is a shape for both, and the hint is gone")
        expect(bob.locator(RECTS)).to_have_count(1, timeout=5000)
        expect(ann.locator(RECTS)).to_have_count(1)
        expect(bob.locator(".other-preview")).to_have_count(0, timeout=5000)

        step("Bob sees Ann's pointer with her name")
        hover(ann, 500, 300)
        name = ann.locator("#me-name").text_content()
        cursor = bob.locator(".other-cursor")
        expect(cursor).to_have_count(1, timeout=5000)
        expect(cursor).to_contain_text(name)
        hover(ann, 520, 340)
        time.sleep(0.4)
        box = cursor.bounding_box()
        want = at(bob, 520, 340)
        assert abs(box["x"] - want[0]) < 6 and abs(box["y"] - want[1]) < 6, f"pointer at {box}, not {want}"

        step("Her pointer goes when it leaves the canvas")
        ann.mouse.move(700, 20)
        expect(cursor).to_have_count(0, timeout=5000)

        step("Her selection shows to Bob as an outline with her name; the handles are hers alone")
        tool(ann, "Select")
        ann.mouse.click(*at(ann, 275, 205))
        expect(ann.locator("#my-selection")).to_have_count(1, timeout=5000)
        expect(bob.locator("#my-selection")).to_have_count(0)
        expect(bob.locator(".other-selection")).to_have_count(1, timeout=5000)
        expect(bob.locator(".other-flag")).to_contain_text(name)
        expect(ann.locator(".other-selection")).to_have_count(0)
        shot(bob, "selection")

        step("A shape being dragged moves live for Bob, and Esc puts it back for both")
        before = rect_x(bob)
        press(ann, 275, 205)
        ann.mouse.move(*at(ann, 375, 305), steps=6)
        expect(bob.locator(RECTS)).to_have_attribute("x", str(int(before + 100)), timeout=5000)
        ann.keyboard.press("Escape")
        ann.mouse.up()
        expect(bob.locator(RECTS)).to_have_attribute("x", str(int(before)), timeout=5000)
        expect(ann.locator(RECTS)).to_have_attribute("x", str(int(before)), timeout=5000)

        step("A finished drag is a change for both")
        drag(ann, 275, 205, 325, 225)
        expect(bob.locator(RECTS)).to_have_attribute("x", str(int(before + 50)), timeout=5000)

        step("When Bob selects the same shape, each is told about the other")
        bob.mouse.click(*at(bob, 325, 225))
        expect(bob.locator("#also-here")).to_contain_text(name, timeout=5000)
        expect(ann.locator("#also-here")).to_be_visible(timeout=5000)

        step("A property Bob changes shows to Ann at once, in the panel too")
        bob.locator('input[type="color"]').first.evaluate(
            """(el) => {
                const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                set.call(el, '#ff0000');
                el.dispatchEvent(new Event('input', { bubbles: true }));
            }"""
        )
        expect(ann.locator(RECTS)).to_have_attribute("fill", "#ff0000", timeout=5000)
        expect(ann.locator('input[type="color"]').first).to_have_value("#ff0000", timeout=5000)
        bob.keyboard.press("Escape")

        step("Undo takes back your own change, not someone else's")
        bob.mouse.click(*at(bob, 1000, 700))
        tool(bob, "Ellipse")
        drag(bob, 500, 150, 610, 240)
        expect(ann.locator(ELLIPSES)).to_have_count(1, timeout=5000)
        ann.get_by_role("button", name="Undo").click()  # Ann's last change: her drag
        expect(ann.locator(RECTS)).to_have_attribute("x", str(int(before)), timeout=5000)
        expect(bob.locator(RECTS)).to_have_attribute("x", str(int(before)), timeout=5000)
        expect(ann.locator(ELLIPSES)).to_have_count(1)
        expect(bob.locator(RECTS)).to_have_attribute("fill", "#ff0000")  # and Bob's colour stays
        ann.get_by_role("button", name="Redo").click()
        expect(bob.locator(RECTS)).to_have_attribute("x", str(int(before + 50)), timeout=5000)

        step("The view is each person's own")
        tool(ann, "Pan")
        drag(ann, 800, 500, 650, 420)
        tool(ann, "Select")
        ann_view = ann.locator("#shapes-layer").evaluate("el => el.parentElement.getAttribute('transform')")
        bob_view = bob.locator("#shapes-layer").evaluate("el => el.parentElement.getAttribute('transform')")
        assert ann_view != "translate(0 0)" and bob_view == "translate(0 0)", (ann_view, bob_view)

        step("A pointer stays on the same spot of the drawing, whatever each one's view")
        hover(bob, 300, 300)
        cursor = ann.locator(".other-cursor")
        expect(cursor).to_have_count(1, timeout=5000)
        time.sleep(0.4)
        box = cursor.bounding_box()
        want = at(ann, 300 - 150, 300 - 80)
        assert abs(box["x"] - want[0]) < 6 and abs(box["y"] - want[1]) < 6, f"pointer at {box}, not {want}"

        step("Someone out of view shows as a chip at the edge, and clicking a face goes to them")
        hover(bob, 1020, 780)
        tool(ann, "Pan")
        drag(ann, 300, 500, 900, 500)
        tool(ann, "Select")
        hover(bob, 30, 760)
        expect(ann.locator(".other-edge")).to_have_count(1, timeout=5000)
        shot(ann, "edge_chip")
        hover(ann, 500, 300)
        ann.mouse.move(700, 20)
        ann.locator(f'.doc-person:not([data-name="{name}"])').click()
        expect(ann.locator(".other-edge")).to_have_count(0, timeout=5000)
        expect(ann.locator(".other-cursor")).to_have_count(1, timeout=5000)

        step("The AI dialog is each person's own; what it draws is for everyone, and Undo takes it back")
        ann.get_by_role("button", name="AI Ops").click()
        expect(ann.get_by_role("dialog")).to_be_visible(timeout=5000)
        time.sleep(0.5)
        expect(bob.get_by_role("dialog")).to_have_count(0)
        ann.get_by_role("dialog").locator("textarea").fill('[{"op":"addEllipse","cx":700,"cy":500,"rx":40,"ry":40,"fill":"blue"}]')
        ann.get_by_role("button", name="Run").click()
        expect(bob.locator(ELLIPSES)).to_have_count(2, timeout=5000)
        ann.get_by_role("button", name="Undo").click()
        expect(bob.locator(ELLIPSES)).to_have_count(1, timeout=5000)

        step("Deleting: the Delete key, and a selection someone else's delete clears")
        tool(bob, "Select")
        bob.mouse.click(*at(bob, 555, 195))
        expect(bob.locator("#my-selection")).to_have_count(1, timeout=5000)
        ann.locator(f'.doc-person:not([data-name="{name}"])').click()  # Ann goes to where Bob is
        time.sleep(0.5)
        ann_ellipse = ann.locator(ELLIPSES).bounding_box()
        ann.mouse.click(ann_ellipse["x"] + 40, ann_ellipse["y"] + 40)
        expect(ann.locator("#also-here")).to_be_visible(timeout=5000)
        hover(ann, 10, 10)
        ann.keyboard.press("Delete")
        expect(bob.locator(ELLIPSES)).to_have_count(0, timeout=5000)
        expect(bob.locator("#my-selection")).to_have_count(0, timeout=5000)

        step("The title is shared")
        bob.locator("#doc-title").fill("Our plan")
        bob.locator("#doc-title").press("Enter")
        expect(ann.locator("#doc-title")).to_have_value("Our plan", timeout=5000)

        step("The drawing is saved a moment after a change")
        time.sleep(2.5)
        bob.reload(wait_until="domcontentloaded")
        expect(bob.locator(RECTS)).to_have_count(1, timeout=60000)
        expect(bob.locator(RECTS)).to_have_attribute("fill", "#ff0000")
        expect(bob.locator("#doc-title")).to_have_value("Our plan", timeout=30000)

        step("The AI's operations from outside reach everyone, with no browser needed")
        request = urllib.request.Request(
            f"{BACKEND_URL}/mcp/push_ops",
            data=json.dumps({"doc_id": DOC_ID, "ops": [{"op": "addText", "x": 60, "y": 60, "content": "From MCP"}]}).encode(),
            headers={"Content-Type": "application/json"},
        )
        if not IGNORE_HTTPS:
            assert json.load(urllib.request.urlopen(request))["status"] == "success"
            expect(ann.locator("#main-svg text")).to_contain_text("From MCP", timeout=5000)

        step("The list shows who is on the drawing")
        bob.get_by_role("link", name="My Documents").click()
        row = bob.locator("tbody tr", has_text=DOC_ID)
        expect(row).to_contain_text("Our plan", timeout=30000)
        expect(row).to_contain_text("1 here", timeout=15000)

        step("Whoever leaves is gone for the others at once")
        expect(ann.locator("#people-count")).to_have_text("1 here", timeout=10000)
        expect(ann.locator(".other-cursor")).to_have_count(0, timeout=5000)

        step("A drawing deleted from the list shows as deleted to whoever has it open")
        row.get_by_title("Delete document").click()
        bob.get_by_role("alertdialog").get_by_role("button", name="Delete").click()
        expect(ann.locator("#gone")).to_be_visible(timeout=10000)

        assert not errors, f"uncaught page errors: {errors}"
        browser.close()


def main() -> int:
    try:
        run()
        print("Success! Working together works.")
        return 0
    except Exception as e:
        print(f"Failure: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
