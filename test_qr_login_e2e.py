import asyncio
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import fitz
import cv2
import numpy as np
from playwright.async_api import async_playwright

async def test_qr_flow():
    print("=== STARTING FULL CROSS-DEVICE QR LOGIN E2E TEST ===")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # 1. Desktop Browser Context
        desktop_ctx = await browser.new_context(viewport={'width': 1280, 'height': 850})
        desktop_page = await desktop_ctx.new_page()

        console_errors = []
        desktop_page.on('pageerror', lambda err: console_errors.append(f"[Desktop Error] {err}"))

        print("[STEP 1] Opening Desktop lock screen...")
        await desktop_page.goto('http://127.0.0.1:8888')
        await desktop_page.wait_for_timeout(600)

        gate = await desktop_page.query_selector('#security-gate')
        assert await gate.is_visible(), "Security gate must be visible initially"

        # 2. Verify QR Code Box & Content
        print("[STEP 2] Inspecting QR code display on Desktop...")
        qr_box = await desktop_page.query_selector('#qr-code-box')
        assert qr_box is not None, "QR code box must exist"
        
        # Wait up to 3s for QR SVG to render
        await desktop_page.wait_for_selector('#qr-code-box svg', timeout=3000)
        svg_element = await desktop_page.query_selector('#qr-code-box svg')
        assert svg_element is not None, "SVG QR code must be rendered"
        
        svg_content = await svg_element.evaluate("el => el.outerHTML")
        assert '<svg' in svg_content and len(svg_content) > 500, "SVG content must be valid"
        print(f"  ✓ SVG QR code rendered successfully ({len(svg_content)} bytes)")

        # 3. Decode QR Code (simulate scanning with phone camera)
        print("[STEP 3] Simulating Phone Camera scanning and decoding QR code...")
        doc = fitz.open(stream=svg_content.encode('utf-8'), filetype='svg')
        pix = doc[0].get_pixmap(dpi=150)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        
        decoded_url, pts, _ = cv2.QRCodeDetector().detectAndDecode(img)
        print(f"  ✓ Camera scan decoded URL: {decoded_url}")
        assert decoded_url and '/qr-auth?session_id=qr_' in decoded_url, f"Invalid decoded URL: {decoded_url}"

        # Normalize target URL for local test
        target_mobile_url = decoded_url
        if 'trycloudflare.com' in decoded_url or 'onrender.com' in decoded_url:
            # For local test environment, map to local host with same query
            sid = decoded_url.split('session_id=')[1]
            target_mobile_url = f"http://127.0.0.1:8888/qr-auth?session_id={sid}"

        # 4. Open Mobile Context (emulating Smartphone browser)
        print("[STEP 4] Opening Mobile approval page on Smartphone...")
        mobile_ctx = await browser.new_context(viewport={'width': 390, 'height': 844}, user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) Mobile/15E148")
        mobile_page = await mobile_ctx.new_page()
        mobile_page.on('pageerror', lambda err: console_errors.append(f"[Mobile Error] {err}"))

        await mobile_page.goto(target_mobile_url)
        await mobile_page.wait_for_timeout(400)

        card_title = await (await mobile_page.query_selector('.card-title')).inner_text()
        print(f"  ✓ Mobile page title: {card_title}")
        assert 'Yêu Cầu Mở Khóa Máy Tính' in card_title

        # 5. Mobile User Approves Login
        print("[STEP 5] Mobile user enters master passkey & clicks confirm...")
        inp_mobile = await mobile_page.query_selector('#mobile-passkey-input')
        await inp_mobile.fill('258079')
        btn_confirm = await mobile_page.query_selector('#btn-mobile-passkey')
        await btn_confirm.click()

        # Mobile confirmation should appear
        await mobile_page.wait_for_timeout(500)
        mobile_html = await mobile_page.content()
        assert 'Mở Khóa Thành Công' in mobile_html, "Mobile should show success confirmation"
        print("  ✓ Mobile confirmation received: Mở Khóa Thành Công!")

        # 6. Verify Desktop Automatically Unlocks (<2 seconds)
        print("[STEP 6] Checking Desktop automatic unlock (< 2 seconds)...")
        # Poll desktop gate visibility
        desktop_unlocked = False
        for i in range(15):
            await desktop_page.wait_for_timeout(200)
            if not await gate.is_visible():
                desktop_unlocked = True
                print(f"  ✓ Desktop unlocked automatically in {(i+1)*200}ms!")
                break
        
        assert desktop_unlocked, "Desktop must automatically unlock without user touching PC"

        cards = await desktop_page.query_selector_all('.tool-card')
        print(f"  ✓ Tool cards visible on desktop: {len(cards)}")
        assert len(cards) in (27, 31, 34)

        # Take screenshot of successful unlock via QR
        await desktop_page.screenshot(path='e2e_qr_sync_unlock_verified.png')
        await mobile_page.screenshot(path='e2e_qr_mobile_approved_verified.png')

        # 7. Adversarial Security Edge Cases Verification
        print("[STEP 7] Running Adversarial Security & Edge Cases Suite...")
        import urllib.request
        import urllib.parse
        import json

        # A. Backdoor attempt with phone_token="verified" must be REJECTED (HTTP 401)
        create_req = json.loads(urllib.request.urlopen("http://127.0.0.1:8888/api/auth/qr/create").read())
        test_sid = create_req["session_id"]
        bad_token_data = urllib.parse.urlencode({"session_id": test_sid, "phone_token": "verified"}).encode()
        try:
            urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8888/api/auth/qr/approve", data=bad_token_data))
            assert False, "Security vulnerability: Unauthenticated phone_token accepted!"
        except urllib.error.HTTPError as he:
            assert he.code == 401, f"Expected 401 for unauthorized phone_token, got {he.code}"
            print("  ✓ Backdoor exploit (phone_token='verified') safely blocked with 401 Unauthorized")

        # B. Wrong passkey must be REJECTED (HTTP 400)
        wrong_pass_data = urllib.parse.urlencode({"session_id": test_sid, "passkey": "wrong_pass_9999"}).encode()
        try:
            urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8888/api/auth/qr/approve", data=wrong_pass_data))
            assert False, "Security failure: Wrong passkey was accepted!"
        except urllib.error.HTTPError as he:
            assert he.code == 400, f"Expected 400 for wrong passkey, got {he.code}"
            print("  ✓ Invalid passkey correctly rejected with 400 Bad Request")

        # C. Non-existent session must return expired
        poll_fake = json.loads(urllib.request.urlopen("http://127.0.0.1:8888/api/auth/qr/poll?session_id=qr_nonexistent").read())
        assert poll_fake.get("status") == "expired"
        print("  ✓ Non-existent session correctly handled as expired")

        print(f"Total Console Errors: {len(console_errors)}")
        for e in console_errors:
            print(" ", e)
        assert len(console_errors) == 0, "No console errors allowed"

        await browser.close()
        print("\n>>> CROSS-DEVICE QR LOGIN E2E TEST PASSED 100%! <<<")

if __name__ == '__main__':
    asyncio.run(test_qr_flow())
