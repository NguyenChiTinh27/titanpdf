import os
import re
from collections import Counter

def test_app_js():
    with open('static/app.js', encoding='utf-8') as f:
        js = f.read()

    # Check TOOLS
    tools_start = js.find('const TOOLS = [')
    tools_end = js.find('// App State', tools_start)
    tools_block = js[tools_start:tools_end]

    ids = re.findall(r'id:\s*["\']([^"\']+)["\']', tools_block)
    cats = re.findall(r'category:\s*["\']([^"\']+)["\']', tools_block)

    print(f"Total tools: {len(ids)}")
    assert len(ids) == 32, f"Expected 32 tools, found {len(ids)}"
    assert len(cats) == 32, f"Expected 32 categories, found {len(cats)}"

    cat_counts = Counter(cats)
    print("Category breakdown:", dict(cat_counts))
    assert cat_counts["organize"] == 8, f"organize: {cat_counts['organize']} != 8"
    assert cat_counts["convert"] == 9, f"convert: {cat_counts['convert']} != 9"
    assert cat_counts["security"] == 7, f"security: {cat_counts['security']} != 7"
    assert cat_counts["optimize"] == 3, f"optimize: {cat_counts['optimize']} != 3"
    assert cat_counts["ai"] == 5, f"ai: {cat_counts['ai']} != 5"

    # Check data-category attribute set in renderToolCards
    assert 'card.setAttribute("data-category", tool.category)' in js
    assert 'badge-ai' in js

    # Check Theme switcher functions
    assert 'function setTheme(themeName)' in js
    assert 'function toggleTheme()' in js
    assert 'window.setTheme = setTheme' in js
    assert 'window.toggleTheme = toggleTheme' in js
    print("[PASS] app.js verified completely!")

def test_index_html():
    with open('static/index.html', encoding='utf-8') as f:
        html = f.read()

    # Favicon
    assert 'icons/hse_avatar.jpg' in html, "Favicon or HSE Avatar image link missing in html"
    assert '<link rel="icon" type="image/jpeg" href="icons/hse_avatar.jpg">' in html

    # Preload script
    assert 'localStorage.getItem("luv_theme")' in html
    assert 'document.documentElement.setAttribute("data-theme"' in html

    # Security gate
    assert 'security-gate' in html
    assert 'security-avatar-wrapper' in html
    assert 'security-hse-avatar' in html
    assert 'security-passkey-input' in html
    assert 'btn-unlock-app' in html
    assert 'btn-quick-unlock' in html
    assert 'quickUnlock()' in html

    # Navbar
    assert 'navbar-brand' in html
    assert 'brand-avatar-box' in html
    assert 'navbar-hse-avatar' in html
    assert 'theme-switcher-btn' in html
    assert 'theme-btn-label' in html

    # Hero
    assert 'hero-brand-companion' in html
    assert 'hero-hse-avatar' in html

    # Segmented control
    assert 'data-cat="all"' in html
    assert 'data-cat="organize"' in html
    assert 'data-cat="convert"' in html
    assert 'data-cat="security"' in html
    assert 'data-cat="optimize"' in html
    assert 'data-cat="ai"' in html
    print("[PASS] index.html verified completely!")

def test_style_css():
    with open('static/style.css', encoding='utf-8') as f:
        css = f.read()

    assert ':root[data-theme="vibrant"]' in css
    assert '--vibrant-lime: #84cc16;' in css
    assert '--vibrant-orange: #f97316;' in css
    assert '--vibrant-cyan: #06b6d4;' in css
    assert '--vibrant-violet: #8b5cf6;' in css
    assert '--vibrant-pink: #ec4899;' in css

    assert '[data-category="organize"]' in css
    assert '[data-category="convert"]' in css
    assert '[data-category="security"]' in css
    assert '[data-category="optimize"]' in css
    assert '[data-category="ai"]' in css

    assert 'glowRing' in css
    assert 'pulseGlow' in css
    assert 'brand-avatar-box' in css
    assert 'navbar-hse-avatar' in css
    assert 'security-avatar-wrapper' in css
    assert 'security-hse-avatar' in css
    assert 'btn-theme-switcher' in css
    assert 'badge-ai' in css
    print("[PASS] style.css verified completely!")

if __name__ == '__main__':
    test_app_js()
    test_index_html()
    test_style_css()
    print("ALL M1 VERIFICATIONS PASSED!")
