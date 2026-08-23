"""
Funciones auxiliares de uso general.
"""
import unicodedata
import uuid
import os
from typing import Optional
from datetime import datetime


def strip_accents(text: str) -> str:
    """Elimina acentos y normaliza a minusculas, sin caracteres especiales."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.lower()


def generate_patient_id() -> str:
    """Genera un ID unico para el paciente."""
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    uid = str(uuid.uuid4())[:6].upper()
    return f"PAC-{ts}-{uid}"


def format_number(value: Optional[float], decimals: int = 1) -> str:
    """Formatea un numero float a string con decimales. Retorna '-' si es None.

    Los valores no finitos (nan/inf) tambien se representan como '-': nunca
    deben llegar al informe medico como 'nan' o 'inf'.
    """
    if value is None:
        return "-"
    try:
        value = float(value)
    except (ValueError, TypeError):
        return "-"
    if value != value or value in (float("inf"), float("-inf")):  # nan / +-inf
        return "-"
    return f"{value:.{decimals}f}"


def ensure_dir(path: str) -> None:
    """Crea un directorio si no existe."""
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def safe_filename(prefix: str, extension: str = ".pdf") -> str:
    """Genera un nombre de archivo seguro con timestamp.

    Antifallo: el prefijo se sanitiza (sin separadores de ruta ni caracteres
    problematicos) para que nunca pueda inyectar rutas relativas.
    """
    import re as _re

    prefix = _re.sub(r"[^\w\-]+", "_", str(prefix)).strip("_") or "archivo"
    if not extension.startswith("."):
        extension = "." + extension
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    uid = str(uuid.uuid4())[:4]
    return f"{prefix}_{ts}_{uid}{extension}"


def clear_directory(directory: str) -> list:
    """
    Elimina todos los archivos dentro de un directorio.
    Retorna la lista de archivos eliminados.
    """
    removed = []
    if not os.path.exists(directory):
        return removed
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        try:
            if os.path.isfile(filepath):
                os.remove(filepath)
                removed.append(filepath)
            elif os.path.isdir(filepath):
                os.rmdir(filepath)
                removed.append(filepath)
        except OSError:
            pass
    return removed


def copy_to_user_input(filepath: str, user_input_dir: str) -> str:
    """
    Copia un archivo (PDF/TXT/imagen) al directorio user_input,
    de modo que la sesion trabaje siempre sobre una copia local.
    Retorna la ruta de la copia.

    Antifallo: si ya existe una copia con el mismo nombre pero de contenido
    distinto (p. ej. dos informes llamados 'informe.pdf'), la nueva se guarda
    con un sufijo incremental. Recargar el MISMO archivo es idempotente.
    """
    import shutil

    ensure_dir(user_input_dir)
    dest = os.path.join(user_input_dir, os.path.basename(filepath))
    if (
        os.path.exists(dest)
        and os.path.abspath(dest) != os.path.abspath(filepath)
        and not _files_equal(filepath, dest)
    ):
        base, ext = os.path.splitext(dest)
        n = 1
        while os.path.exists(dest) and not _files_equal(filepath, dest):
            dest = f"{base}_{n}{ext}"
            n += 1
    shutil.copy2(filepath, dest)
    return dest


def _files_equal(a: str, b: str) -> bool:
    """Compara dos archivos por contenido (False si alguno no existe)."""
    import filecmp

    try:
        return filecmp.cmp(a, b, shallow=False)
    except OSError:
        return False
