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
    """Formatea un numero float a string con decimales. Retorna '-' si es None."""
    if value is None:
        return "-"
    try:
        return f"{float(value):.{decimals}f}"
    except (ValueError, TypeError):
        return "-"


def ensure_dir(path: str) -> None:
    """Crea un directorio si no existe."""
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def safe_filename(prefix: str, extension: str = ".pdf") -> str:
    """Genera un nombre de archivo seguro con timestamp."""
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
    """
    import shutil

    ensure_dir(user_input_dir)
    dest = os.path.join(user_input_dir, os.path.basename(filepath))
    shutil.copy2(filepath, dest)
    return dest
