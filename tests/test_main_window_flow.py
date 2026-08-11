"""Tests de flujo de la ventana principal (requiere pytest-qt)."""
import os

import pytest

from PyQt6.QtWidgets import QMessageBox

from src.core.ai_extractor import ExtractionResult
from src.gui.main_window import MainWindow
from src.models.patient import Sexo


@pytest.fixture
def window(qtbot, tmp_path, monkeypatch):
    """Ventana principal con rutas de escritura aisladas en un directorio temporal."""
    from src.utils import config as config_mod

    cfg = config_mod.load_config()
    cfg.user_input_dir = str(tmp_path / "user_input")
    cfg.output_dir = str(tmp_path / "output")
    cfg.log_file = str(tmp_path / "logs" / "app.log")

    monkeypatch.setattr("src.gui.main_window.load_config", lambda: cfg)
    # Evitar consulta de red a Ollama y cajas modales bloqueantes en los tests
    monkeypatch.setattr(
        "src.gui.ai_tab.check_ollama",
        lambda base_url, timeout=2.0: (False, []),
    )
    monkeypatch.setattr(
        "src.gui.main_window.QMessageBox.information",
        lambda *a, **k: QMessageBox.StandardButton.Ok,
    )

    w = MainWindow()
    qtbot.addWidget(w)
    yield w
    w.close()


class TestMainWindowFlow:
    def test_generar_bloqueado_sin_disclaimer(self, window):
        w = window
        assert not w.report_tab.btn_generar.isEnabled()
        w.report_tab.chk_disclaimer.setChecked(True)
        assert w.report_tab.btn_generar.isEnabled()
        w.report_tab.chk_disclaimer.setChecked(False)
        assert not w.report_tab.btn_generar.isEnabled()

    def test_apply_extraction_conserva_sexo_seleccionado(self, window):
        w = window
        w.combo_sexo.setCurrentIndex(1)  # Femenino

        result = ExtractionResult(
            source="ollama+regex",
            model="qwen2.5:3b",
            numeric_params={"fevi": 55.0},
            numeric_confidence={"fevi": 0.9},
            confidence=0.9,
        )
        w._on_apply_extraction(result)

        # La IA no detecto sexo: debe conservarse el seleccionado en la UI
        assert w.patient.sexo == Sexo.FEMENINO
        assert w.combo_sexo.currentIndex() == 1
        assert w.patient.fevi == 55.0
        # Trazabilidad de la IA
        assert w.patient.ia_model == "qwen2.5:3b"
        assert w.patient.ia_source == "ollama+regex"
        assert w.patient.ia_confidence == 0.9

    def test_flujo_validar_y_generar(self, window):
        w = window
        w.numeric_tab._on_test_data()
        w.combo_sexo.setCurrentIndex(0)
        w._on_validate()

        w.report_tab.chk_disclaimer.setChecked(True)
        w._on_generate_report()

        assert w.report_tab._pdf_path is not None or w.report_tab._html_path is not None
        if w.report_tab._html_path:
            assert os.path.exists(w.report_tab._html_path)
