# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\ntc27\\OneDrive\\文件\\TitanPDF\\app_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\ntc27\\OneDrive\\文件\\TitanPDF\\static', 'static'), ('C:\\Users\\ntc27\\OneDrive\\文件\\TitanPDF\\core', 'core')],
    hiddenimports=['uvicorn', 'uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto', 'uvicorn.lifespan.on', 'multipart', 'fitz', 'openpyxl', 'docx', 'pptx', 'pdf2docx', 'requests', 'pythoncom', 'win32com', 'win32com.client', 'lxml'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LUV-PDF',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='C:\\Users\\ntc27\\OneDrive\\文件\\TitanPDF\\app_icon.ico',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LUV-PDF',
)
