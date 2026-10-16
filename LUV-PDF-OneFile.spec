# -*- mode: python ; coding: utf-8 -*-
import os

proj_dir = os.path.abspath(SPECPATH)

a = Analysis(
    [os.path.join(proj_dir, 'app_launcher.py')],
    pathex=[proj_dir],
    binaries=[],
    datas=[
        (os.path.join(proj_dir, 'static'), 'static'),
        (os.path.join(proj_dir, 'core'), 'core'),
        (os.path.join(proj_dir, 'settings.json'), '.'),
        (os.path.join(proj_dir, 'app_icon.ico'), '.')
    ],
    hiddenimports=[
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto',
        'uvicorn.lifespan.on',
        'multipart',
        'fitz',
        'openpyxl',
        'docx',
        'pptx',
        'pdf2docx',
        'requests',
        'pythoncom',
        'win32com',
        'win32com.client',
        'lxml',
        'pypdf',
        'PIL',
        'reportlab'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LUV-PDF-Portable',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(proj_dir, 'app_icon.ico'),
)
