"""
Borrado seguro de archivos temporales.
Sobrescribe archivos con datos aleatorios antes de eliminarlos,
para evitar recuperacion de datos clinicos.
"""
import os
from typing import List, Optional, Tuple
from src.utils.logger import setup_logger

logger = setup_logger()


# Numero de pasadas de sobrescritura
PASSES = 3


def secure_delete_file(filepath: str) -> bool:
    """
    Borra un archivo de forma segura:
    1. Lo sobrescribe con datos aleatorios N veces
    2. Lo trunca a tamano cero
    3. Lo elimina del sistema de archivos
    """
    if not os.path.exists(filepath):
        return True

    try:
        file_size = os.path.getsize(filepath)

        with open(filepath, "r+b") as f:
            for _ in range(PASSES):
                f.seek(0)
                # Generar datos aleatorios del tamano del archivo
                random_data = os.urandom(file_size)
                f.write(random_data)
                f.flush()
                os.fsync(f.fileno())

            # Truncar a cero
            f.seek(0)
            f.truncate(0)
            f.flush()
            os.fsync(f.fileno())

        # Eliminar
        os.remove(filepath)
        logger.debug(f"Archivo borrado de forma segura: {os.path.basename(filepath)}")
        return True

    except (PermissionError, OSError) as e:
        logger.warning(
            f"No se pudo borrar {os.path.basename(filepath)}: {e}. "
            "Intentando eliminacion normal."
        )
        try:
            os.remove(filepath)
        except OSError:
            pass
        return False


def secure_delete_directory(
    directory: str, extensions: Optional[Tuple[str, ...]] = None
) -> List[str]:
    """
    Borra de forma segura todos los archivos de un directorio.
    Si extensions no es None, solo borra archivos con esas extensiones.
    Retorna lista de archivos eliminados.
    """
    removed = []
    if not os.path.exists(directory):
        return removed

    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        if os.path.isfile(filepath):
            if extensions is not None and not filename.lower().endswith(extensions):
                continue
            if secure_delete_file(filepath):
                removed.append(filepath)
        elif os.path.isdir(filepath):
            # Recursion para subdirectorios
            sub = secure_delete_directory(filepath, extensions)
            removed.extend(sub)
            try:
                os.rmdir(filepath)
                removed.append(filepath)
            except OSError:
                pass

    logger.info(
        f"Directorio limpiado de forma segura: {os.path.basename(directory) or directory} "
        f"({len(removed)} archivos)"
    )
    return removed


class SecureDeleter:
    """Clase que gestiona el borrado seguro al cerrar sesion."""

    def __init__(self, user_input_dir: str, output_dir: str, enabled: bool = True):
        self.user_input_dir = user_input_dir
        self.output_dir = output_dir
        self.enabled = enabled

    def clean_session(self) -> dict:
        """
        Ejecuta la limpieza completa de sesion.
        Retorna un resumen de lo eliminado.
        """
        result = {
            "user_input": [],
            "output": [],
            "total": 0,
        }

        if not self.enabled:
            logger.info("Borrado seguro deshabilitado en configuracion")
            return result

        logger.info("Iniciando limpieza segura de sesion...")

        # Limpiar user_input (copias temporales de archivos cargados)
        if os.path.exists(self.user_input_dir):
            result["user_input"] = secure_delete_directory(self.user_input_dir)

        # Limpiar output: HTML y PDF temporales de la sesion. Los informes que
        # el usuario exporto a otra ubicacion son copias y no se ven afectados.
        if os.path.exists(self.output_dir):
            result["output"] = secure_delete_directory(
                self.output_dir, extensions=(".html", ".pdf")
            )

        result["total"] = len(result["user_input"]) + len(result["output"])
        logger.info(
            f"Limpieza completada: {len(result['user_input'])} archivos de input, "
            f"{len(result['output'])} archivos de output"
        )

        return result
