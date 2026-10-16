import sys
sys.stdout.reconfigure(encoding='utf-8')
from playwright.sync_api import sync_playwright
import os

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page()
    page.on("console", lambda msg: print(f"CONSOLE: [{msg.type}] {msg.text}"))
    page.on("pageerror", lambda err: print(f"PAGEERROR: {err}"))
    page.goto('http://127.0.0.1:8888')
    page.fill('#security-passkey-input', '258079')
    page.click('#btn-unlock-app')
    page.wait_for_timeout(500)
    page.click('.tool-card[data-tool-id="compress"]')
    page.wait_for_timeout(500)
    
    files = [os.path.abspath('sample_5pages.pdf'), os.path.abspath('test_wrap.pdf')]
    page.set_input_files('#file-input', files)
    page.wait_for_timeout(1000)
    
    print('files-view class:', page.get_attribute('#studio-files-view', 'class'))
    print('grid-view class:', page.get_attribute('#studio-grid-view', 'class'))
    print('studioViewMode:', page.evaluate('() => window.studioViewMode'))
    print('selectedFiles len:', page.evaluate('() => window.selectedFiles ? window.selectedFiles.length : -1'))
    b.close()
