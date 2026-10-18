"""
Comprehensive End-to-End Playwright RBAC Frontend Verification Suite
Covers Milestones M2, M3, M4, M5, M6
"""

import asyncio
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from playwright.async_api import async_playwright, expect

BASE_URL = "http://127.0.0.1:8888"

async def test_frontend_rbac():
    print("=" * 60)
    print("STARTING FRONTEND RBAC (M2 - M6) PLAYWRIGHT VERIFICATION")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        # Listen to dialogs to auto-accept alerts
        dialog_messages = []
        page.on("dialog", lambda dialog: asyncio.create_task(handle_dialog(dialog, dialog_messages)))

        # ---------------------------------------------------------------------
        # TEST M2: Security Gate Guest Unlock & Topbar Role Badges
        # ---------------------------------------------------------------------
        print("\n[M2.1] Testing Security Gate Guest Mode Unlock...")
        await page.goto(BASE_URL)
        await page.wait_for_load_state("networkidle")

        # Security gate should initially be visible
        gate = page.locator("#security-gate")
        await expect(gate).to_be_visible()

        # Verify #btn-guest-mode exists
        btn_guest = page.locator("#btn-guest-mode")
        await expect(btn_guest).to_be_visible()

        # Click guest mode
        await btn_guest.click()
        await page.wait_for_timeout(1000)

        # Gate should now be hidden
        await expect(gate).to_be_hidden()

        # Check role on body
        role_attr = await page.evaluate("() => document.body.getAttribute('data-role')")
        session_role = await page.evaluate("() => sessionStorage.getItem('luv_user_role')")
        print(f"  Body data-role: {role_attr}, sessionStorage: {session_role}")
        assert role_attr == "guest", f"Expected body data-role to be 'guest', got {role_attr}"
        assert session_role == "guest", f"Expected session role to be 'guest', got {session_role}"

        # Check topbar auth controls for Guest
        topbar_guest = page.locator("#topbar-guest-controls")
        topbar_owner = page.locator("#topbar-owner-controls")
        await expect(topbar_guest).to_be_visible()
        await expect(topbar_owner).to_be_hidden()

        guest_badge_text = await page.locator("#topbar-guest-badge").text_content()
        print(f"  Guest badge: '{guest_badge_text.strip()}'")
        assert "Khách" in guest_badge_text

        btn_switch = page.locator("#btn-switch-to-owner")
        await expect(btn_switch).to_be_visible()
        print("  [PASS] M2.1 Guest Mode Gate Unlock and Topbar Badges Verified.")

        # ---------------------------------------------------------------------
        # TEST M2.2: Switch to Owner / Lock App
        # ---------------------------------------------------------------------
        print("\n[M2.2] Testing Switch to Owner / Lock App...")
        await btn_switch.click()
        await page.wait_for_timeout(500)

        # Gate should reappear
        await expect(gate).to_be_visible()

        # Unlock as Owner using quick unlock
        btn_quick = page.locator("#btn-quick-unlock")
        await btn_quick.click()
        await page.wait_for_timeout(500)
        await expect(gate).to_be_hidden()

        owner_role = await page.evaluate("() => document.body.getAttribute('data-role')")
        print(f"  Owner unlocked, data-role: {owner_role}")
        assert owner_role == "owner"

        await expect(topbar_owner).to_be_visible()
        await expect(topbar_guest).to_be_hidden()
        print("  [PASS] M2.2 Switch to Owner & Return to Gate Verified.")

        # ---------------------------------------------------------------------
        # TEST M3: Security Modal Guest Profile, Devices & Permissions
        # ---------------------------------------------------------------------
        # ---------------------------------------------------------------------
        # TEST M3: Security Modal Tabs, Guest Profile & Granular 35 Tools Matrix
        # ---------------------------------------------------------------------
        print("\n[M3.1] Testing Security Settings Modal Tabs & Granular 35-Tool Permissions...")
        btn_modal = page.locator("#btn-open-security-modal")
        await btn_modal.click()
        await page.wait_for_timeout(500)

        modal = page.locator("#security-settings-modal")
        await expect(modal).to_be_visible()

        # Verify Tab 1 (Auth)
        tab_auth_btn = page.locator("#sec-tab-btn-auth")
        tab_guest_btn = page.locator("#sec-tab-btn-guest")
        tab_tools_btn = page.locator("#sec-tab-btn-tools")
        await expect(tab_auth_btn).to_be_visible()
        await expect(tab_guest_btn).to_be_visible()
        await expect(tab_tools_btn).to_be_visible()

        # Switch to Tab 2 (Guest Profile)
        await tab_guest_btn.click()
        await page.wait_for_timeout(300)
        name_inp = page.locator("#guest-name-input")
        blocked_switch = page.locator("#guest-blocked-switch")
        max_visits = page.locator("#guest-max-visits-input")
        max_devices = page.locator("#guest-max-devices-input")
        await expect(name_inp).to_be_visible()
        await expect(blocked_switch).to_be_attached()
        await expect(max_visits).to_be_visible()
        await expect(max_devices).to_be_visible()
        print("  [PASS] Tab 2 (Guest Profile & Devices) verified visible.")

        # Switch to Tab 3 (Granular 35 Tools)
        await tab_tools_btn.click()
        await page.wait_for_timeout(300)

        # Count individual tool checkboxes
        tool_count = await page.locator(".guest-tool-chk").count()
        print(f"  Total individual tool checkboxes rendered: {tool_count}")
        assert tool_count == 36, f"Expected 36 tools, found {tool_count}"

        # Capture screenshot of Modal Tab 3 to verify no text clipping
        screenshot_path = "C:/Users/ntc27/.gemini/antigravity/brain/9166a9f1-2c38-41c5-967b-79b51c7e5cf6/e2e_granular_tools_modal.png"
        await page.screenshot(path=screenshot_path)
        print(f"  [SCREENSHOT] Saved modal screenshot to: {screenshot_path}")

        # -------------------------------------------------------------
        # TEST GRANULAR ISOLATION: Turn OFF all tools, enable ONLY 'merge'
        # -------------------------------------------------------------
        print("  Testing 1-Tool-Only Permission Isolation (Allow ONLY 'merge')...")
        await page.evaluate("() => window.toggleAllSecTools(false)")
        await page.locator("#perm-tool-merge").check()
        await page.locator("#btn-save-guest-perms").click()
        await page.wait_for_timeout(500)

        # Close modal
        close_btn = page.locator("#btn-close-security-modal")
        await close_btn.click()
        await page.wait_for_timeout(300)
        await expect(modal).to_be_hidden()

        # Switch to guest mode
        await page.locator("#btn-topbar-lock").click()
        await page.wait_for_timeout(300)
        await page.locator("#btn-guest-mode").click()
        await page.wait_for_timeout(500)

        # Verify only 'merge' is allowed in Guest permissions
        is_merge_allowed = await page.evaluate("() => window.isToolAllowedForGuest('merge')")
        is_split_allowed = await page.evaluate("() => window.isToolAllowedForGuest('split')")
        is_compress_allowed = await page.evaluate("() => window.isToolAllowedForGuest('compress')")
        print(f"  Guest permission state -> merge: {is_merge_allowed}, split: {is_split_allowed}, compress: {is_compress_allowed}")
        assert is_merge_allowed == True, "Expected 'merge' to be allowed"
        assert is_split_allowed == False, "Expected 'split' to be blocked"
        assert is_compress_allowed == False, "Expected 'compress' to be blocked"

        # Try to open 'split' as guest -> should trigger blocked alert
        dialog_messages.clear()
        await page.evaluate("() => window.openTool('split')")
        await page.wait_for_timeout(300)
        print(f"  Dialog when clicking blocked tool: {dialog_messages}")
        assert any("bị khóa" in msg for msg in dialog_messages), "Expected alert when clicking blocked tool"

        # Try to open 'merge' as guest -> should open workspace successfully!
        await page.evaluate("() => window.openTool('merge')")
        await page.wait_for_timeout(500)
        ws_title = await page.locator("#ws-title").text_content()
        print(f"  Opened 'merge' workspace title: '{ws_title.strip()}'")
        assert "Ghép PDF" in ws_title

        # Back to Home view
        await page.evaluate("() => { if (window.closeWorkspace) window.closeWorkspace(); }")
        await page.wait_for_timeout(300)

        # Switch back to owner mode and restore needed permissions for M4-M6
        await page.locator("#btn-switch-to-owner").click()
        await page.wait_for_timeout(300)
        await page.locator("#btn-quick-unlock").click()
        await page.wait_for_timeout(500)

        # Re-open modal and re-enable tools + pro tools
        await page.locator("#btn-open-security-modal").click()
        await page.wait_for_timeout(500)
        await page.locator("#sec-tab-btn-tools").click()
        await page.wait_for_timeout(300)
        await page.evaluate("() => window.toggleAllSecTools(true)")
        await page.locator("#btn-save-guest-perms").click()
        await page.wait_for_timeout(500)
        await page.locator("#btn-close-security-modal").click()
        await page.wait_for_timeout(300)
        print("  [PASS] M3.1 Granular 1-Tool-Only Permission & Tabbed Modal Verified 100%.")

        # ---------------------------------------------------------------------
        # TEST M4: DeepSeek Key Masking in Guest Mode
        # ---------------------------------------------------------------------
        print("\n[M4] Testing DeepSeek Key Masking in Guest Mode...")
        # Switch to guest mode
        await page.locator("#btn-topbar-lock").click()
        await page.wait_for_timeout(300)
        await page.locator("#btn-guest-mode").click()
        await page.wait_for_timeout(500)

        # Open OCR tool where opt-deepseek-key is rendered
        await page.evaluate("() => window.openTool('ocr')")
        await page.wait_for_timeout(500)

        # Check masked key in settings / options
        masked_val = await page.locator("#opt-deepseek-key").input_value()
        is_disabled = await page.locator("#opt-deepseek-key").is_disabled()
        is_readonly = await page.locator("#opt-deepseek-key").is_editable() == False
        print(f"  #opt-deepseek-key value: '{masked_val}', disabled: {is_disabled}, readonly: {is_readonly}")
        assert masked_val == "••••••••••••••••", f"Expected masked key, got {masked_val}"
        assert is_disabled or is_readonly

        # Save button and visibility toggle should be hidden
        save_key_btn = page.locator("#btn-save-deepseek-key")
        toggle_vis_btn = page.locator("#btn-toggle-key-visibility")
        save_btn_visible = await save_key_btn.is_visible()
        toggle_vis_visible = await toggle_vis_btn.is_visible()
        print(f"  Save key button visible: {save_btn_visible}, Toggle vis visible: {toggle_vis_visible}")
        assert not save_btn_visible, "Save DeepSeek key button must be hidden for guest"
        assert not toggle_vis_visible, "Toggle key visibility button must be hidden for guest"
        print("  [PASS] M4 DeepSeek Key Masking & Protection Verified.")

        # ---------------------------------------------------------------------
        # TEST M5: Read-Only MSDS Intelligence Enforcement
        # ---------------------------------------------------------------------
        print("\n[M5] Testing Read-Only MSDS Intelligence Enforcement...")
        # Switch to AI Studio / MSDS tab
        await page.evaluate("() => { window.switchMainTab('ai-studio', 'msds'); if (window.renderMsdsFilteredTable && window.ALL_MSDS_CHEMICALS_CACHE) window.renderMsdsFilteredTable(window.ALL_MSDS_CHEMICALS_CACHE); }")
        await page.wait_for_timeout(1000)

        # Verify mutation controls are hidden
        intake_drawer = page.locator("#msds-intake-drawer")
        btn_analyze = page.locator("#btn-run-msds-analyze")
        gdrive_sync = page.locator("#btn-msds-gdrive-sync")
        btn_del_all = page.locator("#btn-clear-cil")

        intake_visible = await intake_drawer.is_visible()
        analyze_visible = await btn_analyze.is_visible()
        gdrive_visible = await gdrive_sync.is_visible()
        del_all_visible = await btn_del_all.is_visible()
        print(f"  Intake drawer visible: {intake_visible}, Analyze btn visible: {analyze_visible}, GDrive sync visible: {gdrive_visible}, Delete all visible: {del_all_visible}")
        assert not intake_visible, "MSDS Intake Drawer must be hidden for guest"
        assert not analyze_visible, "MSDS Run Analyze button must be hidden for guest"
        assert not gdrive_visible, "MSDS GDrive sync must be hidden for guest"
        assert not del_all_visible, "MSDS Delete all button must be hidden for guest"

        # Verify table row delete buttons are hidden/absent
        del_row_count = await page.locator(".msds-btn-del-row:visible").count()
        print(f"  Number of visible row delete buttons: {del_row_count}")
        assert del_row_count == 0, "No row delete buttons should be rendered or visible for guest"

        # Verify read-only export/view buttons exist
        view_card_count = await page.locator(".msds-btn-view-card").count()
        qr_btn_count = await page.locator(".msds-btn-qr-row").count()
        label_btn_count = await page.locator(".msds-btn-label-row").count()
        docx_btn_count = await page.locator(".msds-btn-export-docx").count()
        print(f"  View card buttons: {view_card_count}, QR buttons: {qr_btn_count}, Label buttons: {label_btn_count}, Docx buttons: {docx_btn_count}")
        assert view_card_count > 0, "Guest must retain access to View Safety Cards"
        assert qr_btn_count > 0, "Guest must retain access to QR Codes"
        assert label_btn_count > 0, "Guest must retain access to GHS Label printing"
        assert docx_btn_count > 0, "Guest must retain access to Word Docx Export"
        print("  [PASS] M5 Read-Only MSDS Intelligence Enforcement Verified.")

        # ---------------------------------------------------------------------
        # TEST M6: Read-Only Monthly Inventory (NXT) Enforcement
        # ---------------------------------------------------------------------
        print("\n[M6] Testing Read-Only Monthly Inventory (NXT) Enforcement...")
        # Switch to Monthly Inventory tab
        await page.evaluate("() => window.switchMainTab('monthly-inventory')")
        await page.wait_for_timeout(1000)

        # Check mutation buttons are hidden via CSS
        create_period_btn = page.locator("#nxt-btn-create-period")
        add_cil_btn = page.locator("#nxt-btn-add-chemicals-cil")
        record_trans_btn = page.locator("#nxt-btn-record-transaction")
        roll_forward_btn = page.locator("#nxt-btn-roll-forward")
        lock_toggle_btn = page.locator("#nxt-btn-lock-toggle")

        assert not await create_period_btn.is_visible(), "Create Period button must be hidden for guest"
        assert not await add_cil_btn.is_visible(), "Add Chemical from CIL button must be hidden for guest"
        assert not await record_trans_btn.is_visible(), "Record Transaction button must be hidden for guest"
        assert not await roll_forward_btn.is_visible(), "Roll Forward button must be hidden for guest"
        assert not await lock_toggle_btn.is_visible(), "Lock Toggle button must be hidden for guest"

        # Check export buttons ARE visible
        export_excel_btn = page.locator("#nxt-btn-export-excel")
        export_pdf_btn = page.locator("#nxt-btn-export-pdf")
        print_btn = page.locator("#nxt-btn-print-report")
        await expect(export_excel_btn).to_be_visible()
        await expect(export_pdf_btn).to_be_visible()
        await expect(print_btn).to_be_visible()

        # Check inputs in grid are disabled / non-editable
        num_inputs = page.locator(".nxt-num-input")
        input_count = await num_inputs.count()
        print(f"  Grid numeric inputs found: {input_count}")
        if input_count > 0:
            first_disabled = await num_inputs.first.is_disabled()
            print(f"  First input disabled: {first_disabled}")
            assert first_disabled, "Grid inputs must be disabled for guest"

        # Check action cell shows 'Chỉ xem' instead of save/delete buttons
        save_mini_count = await page.locator(".nxt-btn-mini-save:visible").count()
        danger_mini_count = await page.locator(".nxt-btn-mini-danger:visible").count()
        print(f"  Visible mini-save buttons: {save_mini_count}, Visible mini-danger buttons: {danger_mini_count}")
        assert save_mini_count == 0, "No save buttons should be visible in grid for guest"
        assert danger_mini_count == 0, "No delete buttons should be visible in grid for guest"
        print("  [PASS] M6 Read-Only Monthly Inventory (NXT) Enforcement Verified.")

        # ---------------------------------------------------------------------
        # TEST Permission Block Enforcement
        # ---------------------------------------------------------------------
        print("\n[M3.2] Testing Dynamic Permission Blocking (Tool Groups)...")
        # Unlock as owner to modify permissions
        await page.locator("#btn-switch-to-owner").click()
        await page.wait_for_timeout(300)
        await page.locator("#btn-quick-unlock").click()
        await page.wait_for_timeout(500)

        # Disable 'msds' permission via backend API to test permission enforcement
        import urllib.request
        import json

        perms_req = urllib.request.Request(
            f"{BASE_URL}/api/auth/guest-permissions",
            data=json.dumps({"tool_groups": {"basic_pdf": True, "pro_tools": True, "studios": True, "legal": True, "msds": False, "monthly_inventory": True}}).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer 258079", "X-Titan-Session": "verified"},
            method="POST"
        )
        with urllib.request.urlopen(perms_req) as resp:
            print("  Disabled MSDS permission for guest, response:", resp.status)

        # Switch back to guest mode
        await page.locator("#btn-topbar-lock").click()
        await page.wait_for_timeout(300)
        await page.locator("#btn-guest-mode").click()
        await page.wait_for_timeout(800)

        # Refresh guest permissions cache in browser
        await page.evaluate("async () => { if (window.loadAndApplyGuestPermissions) await window.loadAndApplyGuestPermissions(); }")
        await page.wait_for_timeout(400)

        # Try to switch to MSDS tab
        dialog_messages.clear()
        await page.evaluate("() => window.switchMainTab('msds')")
        await page.wait_for_timeout(500)

        print(f"  Dialog messages triggered: {dialog_messages}")
        assert any("bị khóa" in msg or "không có quyền" in msg for msg in dialog_messages), "Expected permission denied alert when accessing disabled MSDS tab"

        # Restore permissions back to all True
        restore_req = urllib.request.Request(
            f"{BASE_URL}/api/auth/guest-permissions",
            data=json.dumps({"tool_groups": {"basic_pdf": True, "pro_tools": True, "studios": True, "legal": True, "msds": True, "monthly_inventory": True}}).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer 258079", "X-Titan-Session": "verified"},
            method="POST"
        )
        with urllib.request.urlopen(restore_req) as resp:
            print("  Restored all permissions for guest, response:", resp.status)
        print("  [PASS] Dynamic Permission Blocking Verified.")

        await browser.close()

    print("\n" + "=" * 60)
    print("ALL FRONTEND RBAC (M2 - M6) TESTS PASSED 100% SUCCESFULLY!")
    print("=" * 60)

async def handle_dialog(dialog, messages):
    messages.append(dialog.message)
    await dialog.accept()

if __name__ == "__main__":
    asyncio.run(test_frontend_rbac())
