import sys

a = Analysis(
    ['snake.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/snakes', 'assets/snakes')],
    hiddenimports=[],
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
    name='Desktop Snake',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
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
    upx=False,
    upx_exclude=[],
    name='Desktop Snake',
)
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='Desktop Snake.app',
        icon=None,
        bundle_identifier='com.cyberhirsch.desktop-snake',
        info_plist={
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleName': 'Desktop Snake',
            'CFBundleDisplayName': 'Desktop Snake',
            'LSMinimumSystemVersion': '11.0.0',
            'NSHighResolutionCapable': True,
            'LSUIElement': True,
        },
    )
