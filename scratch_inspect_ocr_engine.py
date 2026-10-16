import sys
sys.stdout.reconfigure(encoding='utf-8')

content = open('core/engine.py', 'r', encoding='utf-8').read()
idx = content.find('def ocr_pdf')
print(content[idx:idx+1500])
