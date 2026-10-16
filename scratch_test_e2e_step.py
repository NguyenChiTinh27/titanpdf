import sys
sys.stdout.reconfigure(encoding='utf-8')
from playwright.sync_api import sync_playwright
import os, time, shutil

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
from tests.fixtures import create_blank_pdf

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 850})
    page.on("console", lambda msg: print(f"CONSOLE: [{msg.type}] {msg.text}"))
    page.on("pageerror", lambda err: print(f"PAGEERROR: {err}"))
    page.goto('http://127.0.0.1:8888')
    page.fill("#security-passkey-input", "258079")
    page.click("#btn-unlock-app")
    page.wait_for_timeout(500)

    tool_card = page.query_selector('.tool-card[data-tool-id="compress"]')
    tool_card.click()
    page.wait_for_timeout(500)

    temp_dir = os.path.join(PROJECT_ROOT, "temp", "e2e_batch_test")
    os.makedirs(temp_dir, exist_ok=True)
    test_paths = []
    for idx in range(1, 4):
        fpath = os.path.join(temp_dir, f"doc_batch_{idx}.pdf")
        with open(fpath, "wb") as f:
            f.write(create_blank_pdf(num_pages=1, text=f"Trang kiểm thử {idx}"))
        test_paths.append(fpath)

    page.set_input_files("#file-input", test_paths)
    page.wait_for_timeout(500)

    cards = page.query_selector_all(".multi-file-card")
    print(f"Cards before remove: {len(cards)}")
    remove_btn = cards[0].query_selector(".btn-card-remove")
    remove_btn.click()
    page.wait_for_timeout(300)

    cards_after = page.query_selector_all(".multi-file-card")
    print(f"Cards after remove: {len(cards_after)}")

    btn_process = page.query_selector("#btn-process")
    print("Clicking btn_process...")
    btn_process.click()

    t0 = time.time()
    banner = page.wait_for_selector("#batch-complete-banner:not(.hidden)", timeout=15000)
    print(f"Banner found in {time.time()-t0:.2f}s! Visible: {banner.is_visible()}")
    browser.close()
