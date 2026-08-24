# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec para Ecocardiograma Local.
# Modo one-dir. Los archivos de lectura (configs, templates, referencias ASE)
# van dentro del dist; los datos de escritura (logs, user_input, output)
# se guardan en %LOCALAPPDATA%\EcocardiogramaLocal en modo congelado,
# de modo que la instalacion se mantiene de solo lectura.

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('configs/config.yaml', 'configs'),
        ('data/templates', 'data/templates'),
        ('data/ase_references', 'data/ase_references'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # WeasyPrint no funciona en Windows (requiere GTK) y su import se evita
    # en tiempo de ejecucion con _weasyprint_available(). Se excluye del build.
    excludes=['weasyprint', 'cryptography', 'tqdm'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='EcocardiogramaLocal',
    debug=False,
    bootloader_ignore_signals=False,
    # upx desactivado: puede corromper los bins de pandas/PyQt6 y ralentiza.
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/app.ico',
    version='version_info.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='EcocardiogramaLocal',
)

# macOS: ademas del one-dir se genera el bundle .app firmable (sin notarizar).
# El icono .icns se genera desde assets/app.ico con Pillow (multiplataforma).
import sys as _sys

if _sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='EcocardiogramaLocal.app',
        icon='assets/app.icns',
        bundle_identifier='com.ecocardiogramalocal.app',
        info_plist={
            'CFBundleName': 'Ecocardiograma Local',
            'CFBundleDisplayName': 'Ecocardiograma Local',
            'CFBundleShortVersionString': '1.0.5',
            'CFBundleVersion': '1.0.5',
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '11.0',
        },
    )
