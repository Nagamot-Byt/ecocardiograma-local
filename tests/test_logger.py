"""Tests de la configuracion de logging (src.utils.logger)."""
import logging
import os

import pytest

from src.utils.logger import setup_logger, SecureTimedRotatingFileHandler


@pytest.fixture
def clean_logger():
    """Aisla el logger singleton 'ecocardiograma' entre tests."""
    logger = logging.getLogger("ecocardiograma")
    old_handlers = list(logger.handlers)
    old_level = logger.level
    logger.handlers = []
    logger.setLevel(logging.DEBUG)
    yield logger
    logger.handlers = old_handlers
    logger.setLevel(old_level)


class TestLogger:
    def test_setup_logger_crea_archivo(self, tmp_path, clean_logger):
        log_file = str(tmp_path / "logs" / "app.log")
        logger = setup_logger(log_file)
        logger.info("mensaje de prueba")

        assert os.path.exists(log_file)
        with open(log_file, "r", encoding="utf-8") as f:
            assert "mensaje de prueba" in f.read()

    def test_setup_logger_no_duplica_handlers(self, tmp_path, clean_logger):
        log_file = str(tmp_path / "logs" / "app.log")
        l1 = setup_logger(log_file)
        n_antes = len(l1.handlers)
        l2 = setup_logger(log_file)
        assert len(l2.handlers) == n_antes

    def test_handler_es_rotacion_segura(self, tmp_path, clean_logger):
        log_file = str(tmp_path / "logs" / "app.log")
        logger = setup_logger(log_file)
        file_handlers = [
            h for h in logger.handlers
            if isinstance(h, SecureTimedRotatingFileHandler)
        ]
        assert file_handlers, "Debe existir un SecureTimedRotatingFileHandler"
        # El borrado normal queda desactivado (getFilesToDelete vacio)
        assert file_handlers[0].getFilesToDelete() == []

    def test_setup_logger_sin_ruta_usa_data_root(self, clean_logger):
        logger = setup_logger()
        file_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.FileHandler)
        ]
        assert file_handlers
        log_path = file_handlers[0].baseFilename
        assert log_path.endswith("app.log")
