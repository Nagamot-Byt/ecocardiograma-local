"""Verifica que la version de la app este sincronizada en todos los ficheros.

Fuente unica de verdad: APP_VERSION en src/core/version.py.

Comprueba pyproject.toml, ecocardiograma.spec (info_plist de macOS),
installer/ecocardiograma.iss, version_info.txt (metadatos del exe de
Windows), docs/GUIA_DE_USO.md y README.md.

Uso (desde la raiz del proyecto):
    python scripts/check_version.py

Sale con codigo 1 si alguna version no coincide; 0 si todo esta alineado.
Se ejecuta en CI (ci.yml) y en el pipeline de release (release.yml).
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (fichero, patron con un grupo de captura para la version, descripcion)
CHECKS = [
    ("pyproject.toml", r'(?m)^version = "([^"]+)"', "project.version"),
    ("ecocardiograma.spec", r"'CFBundleShortVersionString':\s*'([^']+)'", "info_plist (macOS)"),
    ("ecocardiograma.spec", r"'CFBundleVersion':\s*'([^']+)'", "info_plist bundle (macOS)"),
    ("installer/ecocardiograma.iss", r'#define MyAppVersion "([^"]+)"', "Inno Setup"),
    ("version_info.txt", r"StringStruct\('FileVersion',\s*'([0-9.]+)'", "FileVersion (exe Windows)"),
    ("version_info.txt", r"StringStruct\('ProductVersion',\s*'([0-9.]+)'", "ProductVersion (exe Windows)"),
    ("docs/GUIA_DE_USO.md", r"\*\*Versi[oó]n\s+([0-9][0-9.]*)\b", "guia de uso del cliente"),
    ("README.md", r"\*\*Ultima version: v([0-9][0-9.]*)\*\*", "seccion instalador del README"),
]


def get_app_version() -> str:
    source = (ROOT / "src" / "core" / "version.py").read_text(encoding="utf-8")
    match = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', source)
    if not match:
        print("ERROR: no se pudo leer APP_VERSION de src/core/version.py")
        sys.exit(1)
    return match.group(1)


def main() -> int:
    expected = get_app_version()
    errors = []

    for relpath, pattern, label in CHECKS:
        path = ROOT / relpath
        if not path.exists():
            errors.append(f"{relpath}: fichero no encontrado")
            continue
        match = re.search(pattern, path.read_text(encoding="utf-8"))
        if not match:
            errors.append(f"{relpath}: no se encontro la version ({label})")
            continue
        found = match.group(1)
        # version_info.txt usa el formato x.y.z.w
        if found != expected and found != f"{expected}.0":
            errors.append(f"{relpath}: {found} != {expected} ({label})")

    if errors:
        print(f"VERSION DESALINEADA (APP_VERSION = {expected}):")
        for error in errors:
            print(f"  - {error}")
        print("Sincroniza todos los ficheros con src/core/version.py.")
        return 1

    print(f"Version sincronizada en todos los ficheros: {expected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
