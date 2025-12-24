from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=1000)
        page = browser.new_page()
        
        print("Navigating to http://127.0.0.1:3000...")
        try:
            page.goto("http://127.0.0.1:3000", timeout=10000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"Navigation failed: {e}")
            browser.close()
            return

        print("Page loaded. Selecting Text tool...")
        try:
            page.click('button[title="Text"]')
        except Exception as e:
            print(f"Failed to click Text tool: {e}")
            browser.close()
            return
        
        print("Clicking on canvas to create text...")
        try:
            # Click on the canvas to create text
            page.click('#main-svg', position={"x": 200, "y": 200})
        except Exception as e:
            print(f"Failed to click canvas: {e}")
        
        print("Waiting for text element...")
        try:
            # Wait for <text> element inside SVG
            page.wait_for_selector("svg text", timeout=3000)
            print("Success! <text> element found in SVG.")
        except Exception as e:
            print(f"Timeout waiting for <text> element: {e}")
            
        print("Taking screenshot...")
        page.screenshot(path="debug_text_screenshot.png")
        
        print("\n--- Inspecting <text> elements ---")
        texts = page.locator("svg text").all()
        
        if not texts:
            print("No <text> elements found.")
            # Dump SVG
            try:
                print("Dumping SVG content:")
                print(page.locator("svg").inner_html())
            except:
                print("Could not dump SVG. Dumping full page to page_dump_text.html")
                with open("page_dump_text.html", "w") as f:
                    f.write(page.content())
        else:
            for i, t in enumerate(texts):
                print(f"Text #{i+1}: {t.text_content()}")
                print(f"  Visible: {t.is_visible()}")
                print(f"  Box: {t.bounding_box()}")
                print(f"  Attributes: x={t.get_attribute('x')}, y={t.get_attribute('y')}, fill={t.get_attribute('fill')}")

        browser.close()

if __name__ == "__main__":
    run()
