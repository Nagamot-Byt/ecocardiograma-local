"""
Configuracion de logging para la aplicacion.
Escribe logs en archivo local y en consola.
"""
import os
import logging
from logging.handlers import TimedRotatingFileHandler

from src.utils.config import get_data_root


class SecureTimedRotatingFileHandler(TimedRotatingFileHandler):
    """
    Igual que TimedRotatingFileHandler pero borra los respaldos rotados
    de forma segura (sobrescritura + truncado) antes de eliminarlos,
    para no dejar PHI recuperable en disco.
    """

    def getFilesToDelete(self):
        # Evitar que doRollover llame a os.remove directamente.
        return []

    def doRollover(self):
        # Capturar los archivos que la clase base habria eliminado,
        # rotar y luego borrarlos de forma segura.
        stale = TimedRotatingFileHandler.getFilesToDelete(self)
        rv = super().doRollover()
        for path in stale:
            try:
                from src.core.secure_delete import secure_delete_file

                secure_delete_file(path)
            except Exception:
                pass
        return rv


def setup_logger(log_file: str = None) -> logging.Logger:
    """
    Configura y retorna el logger principal de la aplicacion.
    Escribe en archivo y consola con rotacion diaria (7 copias de respaldo),
    de modo que el log nunca crece indefinidamente.
    """
    # En modo congelado el log va a %LOCALAPPDATA%\EcocardiogramaLocal\logs\app.log
    # (escribible sin importar donde se instale la aplicacion).
    if log_file is None:
        log_file = os.path.join(get_data_root(), "logs", "app.log")

    # Asegurar que el directorio de logs existe
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("ecocardiograma")
    logger.setLevel(logging.DEBUG)

    # Evitar handlers duplicados
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler de archivo con rotacion diaria (7 dias de retencion) y borrado seguro
    try:
        file_handler = SecureTimedRotatingFileHandler(
            log_file,
            when="midnight",
            backupCount=7,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (PermissionError, OSError):
        pass  # Si no se puede escribir, solo usamos consola

    # Handler de consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
