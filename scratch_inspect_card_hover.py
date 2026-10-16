import sys
sys.stdout.reconfigure(encoding='utf-8')

content = open('static/style.css', 'r', encoding='utf-8').read()
idx = content.find('.tool-card:hover')
print(content[idx:idx+300])
