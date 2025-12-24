from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        # Launch browser in headful mode so the user can see it
        browser = p.chromium.launch(headless=False, slow_mo=1000)
        page = browser.new_page()
        
        # Capture console logs
        page.on("console", lambda msg: print(f"BROWSER CONSOLE: {msg.text}"))
        page.on("pageerror", lambda exc: print(f"BROWSER ERROR: {exc}"))
        
        print("Navigating to http://127.0.0.1:3000...")
        url = "http://127.0.0.1:3000"
        last_error = None
        for attempt in range(1, 16):
            try:
                page.goto(url, timeout=10000, wait_until="domcontentloaded")
                last_error = None
                break
            except Exception as e:
                last_error = e
                print(f"Error navigating (attempt {attempt}/15): {e}")
                time.sleep(2)

        if last_error is not None:
            print("Server never became reachable; stopping test.")
            browser.close()
            return

        print("Page loaded. Uploading image...")
        
        import os
        files_to_upload = []

        # 1. Create/Use dummy PNG
        png_path = "test_upload.png"
        if not os.path.exists(png_path):
            with open(png_path, "wb") as f:
                # Minimal valid PNG
                f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
        files_to_upload.append(png_path)

        # 2. Use existing JPEG if available
        jpg_path = "testcases/debug_image/jpg_test_file.jpg"
        if os.path.exists(jpg_path):
            files_to_upload.append(jpg_path)
        else:
            print(f"Warning: {jpg_path} not found, skipping.")

        # Handle file chooser
        try:
            with page.expect_file_chooser(timeout=5000) as fc_info:
                # Click the upload area. 
                # Reflex upload component usually wraps the input. We click the visible part.
                # Based on toolbar.py, the upload component has id="upload1"
                # But the click event might need to bubble up or hit the label.
                # Let's try clicking the div inside the upload component if possible, or just the component itself.
                page.locator("#upload1").click()
            
            file_chooser = fc_info.value
            file_chooser.set_files(files_to_upload)
            print(f"Files {files_to_upload} uploaded. Waiting for image to appear on canvas...")
        except Exception as e:
            print(f"Error during upload interaction: {e}")

        print("Waiting for SVG image...")
        # Wait for the SVG element to be present
        try:
            # Wait for an image tag inside the SVG
            page.wait_for_selector("svg image", timeout=3000)
            print("Success! <image> element found in SVG.")
        except Exception as e:
            print(f"Timeout waiting for <image> element: {e}")
            # print("Page content:")
            # print(page.content())
        
        # Take a screenshot regardless of success
        print("Taking screenshot...")
        try:
            page.screenshot(path="debug_screenshot.png")
            print("Screenshot saved to debug_screenshot.png")
        except Exception as e:
            print(f"Failed to take screenshot: {e}")

        # Inspect image elements
        print("\n--- Inspecting <image> elements ---")
        images = page.locator("image").all()
        
        if not images:
            print("No <image> elements found in the DOM.")
            
            # Check for the debug rect
            rects = page.locator('rect[fill="red"]').all()
            green_rects = page.locator('rect[fill="green"]').all()
            
            if green_rects:
                print(f"Found {len(green_rects)} debug GREEN rects! The SVG canvas is rendering correctly.")
            else:
                print("No debug GREEN rects found. The entire SVG canvas might be broken or not rendering.")

            if rects:
                print(f"Found {len(rects)} debug RED rects! The shape is being rendered, but the image tag is missing or invalid.")
            else:
                print("No debug RED rects found either. The shape is likely not in the list or rx.match is failing.")
                
            # Dump SVG content
            print("\n--- SVG Content Dump ---")
            try:
                svg_content = page.locator("svg").inner_html()
                print(svg_content[:1000] + "..." if len(svg_content) > 1000 else svg_content)
            except:
                print("Could not get SVG content. Dumping full page to page_dump.html")
                with open("page_dump.html", "w") as f:
                    f.write(page.content())
        
        for i, img in enumerate(images):
            print(f"\nImage #{i+1}:")
            bbox = img.bounding_box()
            print(f"  Bounding Box: {bbox}")
            
            # Get attributes
            href = img.get_attribute("href")
            xlink_href = img.get_attribute("xlink:href")
            x = img.get_attribute("x")
            y = img.get_attribute("y")
            width = img.get_attribute("width")
            height = img.get_attribute("height")
            style = img.get_attribute("style")
            class_name = img.get_attribute("class")
            
            print(f"  href: {href}")
            print(f"  xlink:href: {xlink_href}")
            print(f"  x: {x}, y: {y}")
            print(f"  width: {width}, height: {height}")
            print(f"  style: {style}")
            print(f"  class: {class_name}")
            
            # Check if visible
            is_visible = img.is_visible()
            print(f"  Playwright is_visible(): {is_visible}")

        print("Keeping browser open for 10 seconds for manual inspection...")
        time.sleep(10)
        browser.close()

if __name__ == "__main__":
    run()
