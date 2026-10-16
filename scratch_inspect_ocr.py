import sys
sys.stdout.reconfigure(encoding='utf-8')

content = open('server.py', 'r', encoding='utf-8').read()
idx = content.find('/api/process/ocr')
if idx != -1:
    print(content[idx-50:idx+2500])
