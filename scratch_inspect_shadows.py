import sys
sys.stdout.reconfigure(encoding='utf-8')

content = open('static/style.css', 'r', encoding='utf-8').read()
for line in content.splitlines():
    if '--shadow-card-hover' in line or '--shadow-md' in line:
        print(line)
