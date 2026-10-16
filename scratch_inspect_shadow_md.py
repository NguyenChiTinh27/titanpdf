import sys
sys.stdout.reconfigure(encoding='utf-8')

content = open('static/style.css', 'r', encoding='utf-8').read()
idx = content.find('var(--shadow-md)')
print(content[idx-100:idx+150])
