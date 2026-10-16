import sys
sys.stdout.reconfigure(encoding='utf-8')

content = open('static/app.js', 'r', encoding='utf-8').read()
idx = content.find('opt_ocr_format')
if idx == -1:
    idx = content.find('output_format')
print(content[idx:idx+1000])
