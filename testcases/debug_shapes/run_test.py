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

        print("Page loaded. Selecting Rectangle tool...")
        try:
            # Assuming there is a button for Rectangle. 
            # Based on shapes.py/toolbar.py, usually it sets tool to 'rect'
            # Let's look for a button with title "Rectangle" or similar
            page.click('button[title="Rectangle"]')
        except Exception as e:
            print(f"Failed to click Rectangle tool: {e}")
            browser.close()
            return
        
        print("Drawing a rectangle...")
        try:
            # Drag from (100, 100) to (300, 300)
            page.mouse.move(100, 100)
            page.mouse.down()
            page.mouse.move(300, 300)
            page.mouse.up()
        except Exception as e:
            print(f"Failed to draw: {e}")
        
        print("Waiting for rectangle element...")
        try:
            # Wait for <rect> element inside SVG (excluding the bg rect)
            # The bg rect usually has id="canvas-bg" or similar.
            # We want a new rect.
            # Let's wait for any rect that is NOT the background.
            # Or just count rects.
            page.wait_for_timeout(1000) # Give it a moment to render
            rects = page.locator("svg rect").all()
            print(f"Found {len(rects)} rects.")
            
            # Filter out background if needed. 
            # Usually user shapes are appended.
            found_new_rect = False
            for r in rects:
                id_attr = r.get_attribute("id")
                if id_attr != "canvas-bg" and id_attr != "debug-green-rect":
                    print(f"Found user rect: {r}")
                    found_new_rect = True
                    break
            
            if found_new_rect:
                print("Success! User rectangle found.")
            else:
                print("Failure: No user rectangle found.")
                exit(1)

        except Exception as e:
            print(f"Error checking rects: {e}")
            exit(1)
            
        print("Taking screenshot...")
        page.screenshot(path="debug_shapes_screenshot.png")
        
        browser.close()

if __name__ == "__main__":
    run()
