import re

content = open('server.py', 'r', encoding='utf-8').read()
routes = re.findall(r'@app\.(get|post|put|delete)\(["\']([^"\']+)["\']', content)
print(f"Total routes found: {len(routes)}")
for method, path in routes:
    print(f"{method.upper():<6} {path}")
