import asyncio
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
from playwright.async_api import async_playwright

async def verify_all():
    print("Starting Comprehensive E2E Verification Suite...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 850})
        page = await context.new_page()

        console_errors = []
        page.on('pageerror', lambda err: console_errors.append(str(err)))

        # TEST 1: Manual typing '258079' + Click Unlock button
        print("[TEST 1] Manual typing 258079...")
        await page.goto('http://127.0.0.1:8888')
        gate = await page.query_selector('#security-gate')
        assert await gate.is_visible(), "Gate should be visible initially"
        
        inp = await page.query_selector('#security-passkey-input')
        await inp.fill('258079')
        btn = await page.query_selector('#btn-unlock-app')
        await btn.click()
        await page.wait_for_timeout(400)
        
        gate_visible = await gate.is_visible()
        print(f"  Gate visible after submit: {gate_visible}")
        assert not gate_visible, "Gate must be hidden after 258079"
        cards = await page.query_selector_all('.tool-card')
        print(f"  Tool cards visible: {len(cards)}")
        assert len(cards) in (27, 31, 32, 33), f"Expected 27, 31, 32 or 33 cards, found {len(cards)}"
        await page.screenshot(path='e2e_test1_typed_unlock.png')
        print("  [PASS] Test 1 passed cleanly")

        # TEST 2: One-click Quick Unlock button
        print("[TEST 2] One-click Quick Unlock button...")
        await page.evaluate("localStorage.clear(); sessionStorage.clear(); location.reload();")
        await page.wait_for_timeout(600)
        gate = await page.query_selector('#security-gate')
        assert await gate.is_visible(), "Gate should be re-locked after storage clear"
        
        btn_quick = await page.query_selector('#btn-quick-unlock')
        assert btn_quick is not None, "Quick unlock button must exist"
        await btn_quick.click()
        await page.wait_for_timeout(400)
        gate_visible = await gate.is_visible()
        print(f"  Gate visible after quick unlock: {gate_visible}")
        assert not gate_visible, "Gate must be hidden after quick unlock"
        await page.screenshot(path='e2e_test2_quick_unlock.png')
        print("  [PASS] Test 2 passed cleanly")

        # TEST 3: Pressing Enter key
        print("[TEST 3] Pressing Enter key...")
        await page.evaluate("localStorage.clear(); sessionStorage.clear(); location.reload();")
        await page.wait_for_timeout(600)
        inp = await page.query_selector('#security-passkey-input')
        await inp.fill('258079')
        await inp.press('Enter')
        await page.wait_for_timeout(400)
        gate_visible = await gate.is_visible()
        print(f"  Gate visible after Enter key: {gate_visible}")
        assert not gate_visible, "Gate must be hidden after Enter key"
        await page.screenshot(path='e2e_test3_enter_unlock.png')
        print("  [PASS] Test 3 passed cleanly")

        # TEST 4: Unicode full-width digits
        print("[TEST 4] Unicode full-width digits...")
        await page.evaluate("localStorage.clear(); sessionStorage.clear(); location.reload();")
        await page.wait_for_timeout(600)
        inp = await page.query_selector('#security-passkey-input')
        await inp.fill('２５８０７９')
        btn = await page.query_selector('#btn-unlock-app')
        await btn.click()
        await page.wait_for_timeout(400)
        gate_visible = await gate.is_visible()
        print(f"  Gate visible after full-width digits: {gate_visible}")
        assert not gate_visible, "Gate must be hidden after full-width digits"
        await page.screenshot(path='e2e_test4_unicode_unlock.png')
        print("  [PASS] Test 4 passed cleanly")

        # TEST 5: License key format
        print("[TEST 5] License key format...")
        await page.evaluate("localStorage.clear(); sessionStorage.clear(); location.reload();")
        await page.wait_for_timeout(600)
        inp = await page.query_selector('#security-passkey-input')
        await inp.fill('LUV-PDF-1234-5678-ABCD')
        btn = await page.query_selector('#btn-unlock-app')
        await btn.click()
        await page.wait_for_timeout(400)
        gate_visible = await gate.is_visible()
        print(f"  Gate visible after license key: {gate_visible}")
        assert not gate_visible, "Gate must be hidden after license key"
        await page.screenshot(path='e2e_test5_license_unlock.png')
        print("  [PASS] Test 5 passed cleanly")

        # TEST 6: Page refresh persistence
        print("[TEST 6] Page refresh persistence...")
        await page.reload()
        await page.wait_for_timeout(400)
        gate_visible = await gate.is_visible()
        print(f"  Gate visible after reload: {gate_visible}")
        assert not gate_visible, "Gate must stay hidden on reload"
        await page.screenshot(path='e2e_test6_reload_persisted.png')
        print("  [PASS] Test 6 passed cleanly")

        # TEST 7: Tool 27 (DOC-TRAN) launch
        print("[TEST 7] Tool 27 (DOC-TRAN) launch...")
        tool27 = await page.query_selector('.tool-card[data-tool-id="interlinear-translate"]')
        assert tool27 is not None, "Tool 27 card must exist"
        await tool27.click()
        await page.wait_for_timeout(500)
        
        ws_el = await page.query_selector('#workspace-view')
        ws_visible = await ws_el.is_visible() if ws_el else False
        print(f"  Workspace view visible: {ws_visible}")
        assert ws_visible, "Workspace view must open"
        
        ws_title = await (await page.query_selector('#ws-title')).inner_text()
        print(f"  Workspace title: {ws_title}")
        assert 'DOC-TRAN' in ws_title or 'Song ngữ' in ws_title, "Workspace title must match Tool 27"
        await page.screenshot(path='e2e_test7_tool27_workspace.png')
        print("  [PASS] Test 7 passed cleanly")

        print(f"\nPage Errors caught: {len(console_errors)}")
        for err in console_errors:
            print(f"  ERROR: {err}")
        assert len(console_errors) == 0, "Must have zero page errors"

        await browser.close()
        print("\n>>> ALL 7 END-TO-END SCENARIOS VERIFIED 100% SUCCEEDED! <<<")

if __name__ == '__main__':
    asyncio.run(verify_all())
