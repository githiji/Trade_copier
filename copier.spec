# -*- mode: python ; coding: utf-8 -*-

python_root = r'C:\Users\user\AppData\Local\Programs\Python\Python313'
tcl_root = python_root + r'\tcl'
dll_root = python_root + r'\DLLs'

a = Analysis(
    ['copier.py'],
    pathex=[],
    binaries=[
        (dll_root + r'\_tkinter.pyd', '.'),
        (dll_root + r'\tcl86t.dll', '.'),
        (dll_root + r'\tk86t.dll', '.'),
    ],
    datas=[
        ('trade_copier.ico', '.'),
        (python_root + r'\Lib\tkinter', 'tkinter'),
        (tcl_root + r'\tcl8.6', '_tcl_data'),
        (tcl_root + r'\tk8.6', '_tk_data'),
        (tcl_root + r'\tcl8', 'tcl8'),
        (tcl_root + r'\dde1.4', 'dde1.4'),
        (tcl_root + r'\reg1.3', 'reg1.3'),
    ],
    hiddenimports=['_tkinter', 'tkinter', 'gui', 'database', 'numpy', 'numpy.core._multiarray_umath', 'numpy.core.umath'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyi_rth_tkinter_fix.py'],
    excludes=[],
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
    name='copier',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon='trade_copier.ico',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
