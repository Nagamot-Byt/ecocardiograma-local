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
