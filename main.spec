# -*- mode: python ; coding: utf-8 -*-

import sys
import os

block_cipher = None

# Add the current directory to the path for imports
a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Include any data files your app needs
        # ('data_folder', 'data_folder'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui', 
        'PySide6.QtWidgets',
        'xml.etree.ElementTree',
        'json',
        'subprocess',
        'os',
        'sys',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'PIL.ImageTk',
        'setuptools',
        'distutils',
        'email',
        'http',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
        'requests',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Filter out unnecessary files
a.binaries = [x for x in a.binaries if not x[0].startswith(('tcl', 'tk'))]
a.datas = [x for x in a.datas if not x[0].startswith(('tcl', 'tk'))]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MSFSExeXmlManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True if you need console for debugging
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
    version='version_info.txt' if os.path.exists('version_info.txt') else None,
)