import re

html = open('static/index.html', encoding='utf-8').read()
js = open('static/app.js', encoding='utf-8').read()

html_ids = set(re.findall(r'id=["\']([a-zA-Z0-9_-]+)["\']', html))
js_ids = set(re.findall(r'id=["\']([a-zA-Z0-9_-]+)["\']', js))
queried_ids = set(re.findall(r'document\.getElementById\(["\']([a-zA-Z0-9_-]+)["\']\)', js))

unresolved = queried_ids - (html_ids | js_ids)
print("Unresolved queried IDs:", unresolved)
