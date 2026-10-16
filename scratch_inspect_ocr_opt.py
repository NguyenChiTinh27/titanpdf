import sys, re
sys.stdout.reconfigure(encoding='utf-8')

content = open('static/app.js', 'r', encoding='utf-8').read()
idx = content.find("case 'ocr':")
if idx == -1:
    idx = content.find('case "ocr":')
print(content[idx:idx+1500])
