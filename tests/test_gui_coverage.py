"""Tests de cobertura dirigida: caminos sin cubrir en GUI y utilidades.

Cubre los branches restantes de main_window, numeric_tab, report_preview,
ai_tab, error_guard, logger, updater, config, param_registry,
reference_range, helpers y colombian_reference para alcanzar >= 90%.
"""
import logging
import os
import sys
from types import SimpleNamespace

import pytest

from PyQt6.QtWidgets import (
    QApplication, QMessageBox, QFileDialog, QInputDialog, QFrame, QLabel,
)
from PyQt6.QtCore import QSettings

from src.core.ai_extractor import ExtractionResult
from src.gui.main_window import (
    MainWindow, UpdateCheckWorker, ValidarButton, get_guide_name,
)
from src.gui.numeric_tab import NumericTab
from src.gui.report_preview import ReportPreview
from src.gui.ai_tab import ExtractWorker, FileLoadWorker, OllamaStatusWorker
from src.models.patient import Sexo


@pytest.fixture
def dialogs(monkeypatch):
    """Intercepta TODOS los dialogos modales y los registra (offscreen)."""
    log = []
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *a, **k: log.append(("question", a)) or QMessageBox.StandardButton.Yes,
    )
    for name in ("information", "critical", "warning", "about"):
        monkeypatch.setattr(
            QMessageBox, name,
            lambda *a, _n=name, **k: log.append((_n, a)),
        )
    return log


@pytest.fixture
def window(qtbot, tmp_path, monkeypatch, dialogs):
    """MainWindow con rutas aisladas y dialogos interceptados."""
    from src.utils import config as config_mod

    cfg = config_mod.load_config()
    cfg.user_input_dir = str(tmp_path / "user_input")
    cfg.output_dir = str(tmp_path / "output")
    cfg.log_file = str(tmp_path / "logs" / "app.log")

    monkeypatch.setattr("src.gui.main_window.load_config", lambda: cfg)
    monkeypatch.setattr(
        "src.gui.ai_tab.check_ollama",
        lambda base_url, timeout=2.0: (False, []),
    )

    w = MainWindow()
    qtbot.addWidget(w)
    yield w
    w.close()


# ── MainWindow: validacion, extraccion IA, sesion ───────────────────────


class TestMainWindowValidacion:
    def test_validate_todos_normales(self, window, monkeypatch):
        monkeypatch.setattr(
            window.validator, "validate_patient",
            lambda p: {"fevi": {"normal": True}},
        )
        monkeypatch.setattr(window.validator, "get_summary", lambda p: ["ok"])
        window.numeric_tab._on_test_data()
        window._on_validate()
        assert "Todos los valores" in window.statusBar().currentMessage()

    def test_on_sexo_changed_masculino(self, window):
        window.combo_sexo.setCurrentIndex(0)
        assert window.patient.sexo == Sexo.MASCULINO

    def test_apply_extraction_vacio(self, window, dialogs):
        before = window.patient
        window._on_apply_extraction(None)
        assert window.patient is before  # retorno temprano
        window._on_apply_extraction(ExtractionResult(source="x"))
        assert any(d[0] == "information" for d in dialogs)

    def test_apply_extraction_completo(self, window, dialogs):
        window.combo_sexo.setCurrentIndex(1)
        result = ExtractionResult(
            source="ollama",
            model="qwen2.5:3b",
            numeric_params={"fevi": 40.0, "campo_inexistente": 1.0},
            visual_data={"derrame_pericardico": "Si", "campo_fantasma": "x"},
            patient_data={
                "sexo": "M",
                "edad": "abc",          # fuerza el branch de ValueError
                "nombre_medico": "Dr. Prueba",
                "fecha_estudio": "2026-01-01",
                "notas": "nota clinica",
            },
            clinical_impression="impresion IA",
            recommendations=["rec1"],
            confidence=0.9,
        )
        window._on_apply_extraction(result)

        assert window.patient.sexo == Sexo.MASCULINO
        assert window.combo_sexo.currentIndex() == 0
        assert window.patient.nombre_medico == "Dr. Prueba"
        assert window.patient.notas == "nota clinica"
        assert window.patient.impresion_clinica == "impresion IA"
        assert window.patient.recomendaciones == ["rec1"]
        assert window.patient.fevi == 40.0
        assert "Extraccion aplicada" in window.statusBar().currentMessage()


class TestMainWindowInformesYSesion:
    def test_generate_report_error(self, window, monkeypatch, dialogs):
        def boom(*a, **k):
            raise RuntimeError("fallo motor de informe")

        monkeypatch.setattr(window.report_engine, "generate_report", boom)
        window._on_generate_report()
        assert any(d[0] == "critical" for d in dialogs)

    def test_clean_session(self, window, dialogs):
        window._on_clean_session()
        assert any(d[0] == "question" for d in dialogs)
        assert any(d[0] == "information" for d in dialogs)

    def test_on_load_file_exitoso(self, window, monkeypatch, dialogs, tmp_path):
        src = tmp_path / "datos.xlsx"
        src.write_bytes(b"fake")
        monkeypatch.setattr(
            QFileDialog, "getOpenFileName", lambda *a, **k: (str(src), "")
        )
        monkeypatch.setattr(NumericTab, "load_from_file", lambda self, p, row=0: True)
        window._on_load_file()
        assert any(d[0] == "information" for d in dialogs)

    def test_on_load_file_falla_lectura(self, window, monkeypatch, dialogs, tmp_path):
        src = tmp_path / "datos.xlsx"
        src.write_bytes(b"fake")
        monkeypatch.setattr(
            QFileDialog, "getOpenFileName", lambda *a, **k: (str(src), "")
        )
        monkeypatch.setattr(NumericTab, "load_from_file", lambda self, p, row=0: False)
        window._on_load_file()
        assert any(d[0] == "warning" for d in dialogs)

    def test_on_load_file_error_copia(self, window, monkeypatch, dialogs, tmp_path):
        src = tmp_path / "datos.xlsx"
        src.write_bytes(b"fake")
        monkeypatch.setattr(
            QFileDialog, "getOpenFileName", lambda *a, **k: (str(src), "")
        )

        def boom(*a, **k):
            raise OSError("disco lleno")

        monkeypatch.setattr("src.gui.main_window.copy_to_user_input", boom)
        window._on_load_file()
        assert any(d[0] == "critical" for d in dialogs)

    def test_close_event_antifallo(self, window):
        def boom(*a, **k):
            raise RuntimeError("fallo")

        window.ai_tab.shutdown = boom

        class FakeWorker:
            def isRunning(self):
                return True

            def wait(self, ms):
                raise RuntimeError("timeout")

        window._update_worker = FakeWorker()
        window.secure_deleter.clean_session = boom

        accepted = []
        window.closeEvent(SimpleNamespace(accept=lambda: accepted.append(True)))
        assert accepted == [True]


class TestMainWindowAyudaYTema:
    def test_show_about(self, window, dialogs):
        window._show_about()
        assert any(d[0] == "about" for d in dialogs)

    def test_check_updates_deshabilitado(self, window, dialogs):
        window.config.update.enabled = False
        window._on_check_updates()
        assert any(d[0] == "information" for d in dialogs)
        window.config.update.enabled = True

    def test_update_result_branches(self, window, dialogs):
        window._on_update_result({"error": "sin red"}, manual=True)
        assert any(d[0] == "warning" for d in dialogs)

        window._on_update_result(
            {"disponible": True, "version_remota": "99.0.0"}, manual=True
        )
        assert any(
            d[0] == "information" and "99.0.0" in str(d[1]) for d in dialogs
        )

        window._on_update_result({"disponible": False}, manual=True)
        window._on_update_result({"disponible": False}, manual=False)
        assert "Sin actualizaciones" in window.statusBar().currentMessage()

    def test_start_update_check_solapado(self, window):
        class FakeRunning:
            def isRunning(self):
                return True

        window._update_worker = FakeRunning()
        window._start_update_check(manual=True)
        assert "curso" in window.statusBar().currentMessage()
        window._start_update_check(manual=False)
        window._update_worker = None

    def test_update_worker_run(self, monkeypatch):
        monkeypatch.setattr(
            "src.gui.main_window.check_for_updates",
            lambda **k: {"disponible": False, "version_remota": "", "error": None},
        )
        resultados = []
        worker = UpdateCheckWorker("owner/repo", "v1.0.0")
        worker.finished_check.connect(resultados.append)
        worker.run()
        assert resultados and resultados[0]["disponible"] is False

    def test_get_guide_name_ase(self):
        assert get_guide_name("ase") == "Guías ASE 2023"
        assert get_guide_name("colombian") == get_guide_name("otra")

    def test_init_modo_oscuro(self, window):
        settings = QSettings()
        settings.setValue("dark_mode", True)
        try:
            w2 = MainWindow()
            assert w2.dark_mode is True
            assert "2b2b2b" in w2.styleSheet()
            assert w2.act_tema.isChecked()
            w2.close()
        finally:
            settings.setValue("dark_mode", False)

    # ── P2: tema, objectNames, cancelacion de worker y QSettings ──────────

    def test_tema_claro_aplica_hoja_base(self, window):
        hoja = window.styleSheet()
        assert "QFrame#header" in hoja
        assert "QPushButton#primary" in hoja
        assert "QStatusBar" in hoja
        assert "2b2b2b" not in hoja

    def test_tema_oscuro_cubre_contenedores(self, window):
        window._on_toggle_theme(True)
        try:
            hoja = window.styleSheet()
            assert "2b2b2b" in hoja
            for selector in (
                "QGroupBox", "QTabWidget::pane", "QScrollBar:vertical",
                "QLineEdit", "QHeaderView::section", "QMenu", "QToolTip",
            ):
                assert selector in hoja
            # Los focus del modo oscuro no usan el azul claro del modo claro
            assert "QLineEdit:focus { border: 2px solid #2471a3" in hoja
        finally:
            window._on_toggle_theme(False)
        assert "QLineEdit:focus { border: 2px solid #1a5276" in window.styleSheet()

    def test_objectnames_tematizados(self, window):
        assert window.findChild(QFrame, "header") is not None
        assert window.findChild(QLabel, "title") is not None
        assert window.findChild(QLabel, "version") is not None
        assert window.findChild(QLabel, "patient_id") is window.lbl_id
        assert window.numeric_tab.live_status.objectName() == "live_status"
        assert window.report_tab.lbl_estado.objectName() == "estado"

    def test_botones_de_pestanas_usan_clases_del_tema(self, window):
        botones = {
            window.ai_tab.btn_extraer: "primary",
            window.ai_tab.btn_aplicar: "success",
            window.report_tab.btn_generar: "primary",
            window.report_tab.btn_exportar_pdf: "success",
        }
        for boton, clase in botones.items():
            assert boton.objectName() == clase
            assert boton.styleSheet() == ""

    def test_btn_validar_subclase_sin_parche(self, window):
        assert isinstance(window.btn_validar, ValidarButton)
        # Ya no se parchean metodos sobre la instancia
        assert "enterEvent" not in vars(window.btn_validar)
        assert "leaveEvent" not in vars(window.btn_validar)
        assert window.btn_validar_anim.targetObject() is window.btn_validar
        window.btn_validar.enterEvent(None)
        assert "#e67e22" in window.btn_validar_anim.endValue()
        window.btn_validar.leaveEvent(None)
        assert "#f39c12" in window.btn_validar_anim.endValue()
        window.btn_validar_anim.stop()

    def test_update_worker_cancelado_no_emite(self, monkeypatch):
        monkeypatch.setattr(
            "src.gui.main_window.check_for_updates",
            lambda **k: {"disponible": True, "version_remota": "99.0.0"},
        )
        resultados = []
        worker = UpdateCheckWorker("owner/repo", "v1.0.0")
        worker.finished_check.connect(resultados.append)
        worker.request_cancel()
        worker.run()
        assert resultados == []

    def test_close_event_cancela_worker_de_updates(self, window):
        class FakeSignal:
            def disconnect(self):
                pass

        class FakeWorker:
            def __init__(self):
                self.cancelado = False
                self.finished_check = FakeSignal()
                self.finished = FakeSignal()

            def request_cancel(self):
                self.cancelado = True

            def isRunning(self):
                return False

        fake = FakeWorker()
        window._update_worker = fake
        window.closeEvent(SimpleNamespace(accept=lambda: None))
        assert fake.cancelado is True

    def test_qsettings_de_tests_aislado_de_la_config_real(self):
        ruta = QSettings().fileName()
        assert "qsettings" in ruta
        assert os.path.expanduser("~/.config") not in ruta

    def test_init_guia_por_archivos(self, tmp_path, monkeypatch, qtbot, dialogs):
        from src.utils import config as config_mod

        cfg = config_mod.load_config()
        cfg.guide = "ase"
        cfg.user_input_dir = str(tmp_path / "ui")
        cfg.output_dir = str(tmp_path / "out")
        monkeypatch.setattr("src.gui.main_window.load_config", lambda: cfg)
        monkeypatch.setattr(
            "src.gui.ai_tab.check_ollama",
            lambda *a, **k: (False, []),
        )
        w = MainWindow()
        qtbot.addWidget(w)
        assert w.reference_ranges is not None
        w.close()

    def test_cleanup_stale_session_sin_secure_erase(self, window):
        window.config.secure_erase = False
        window._cleanup_stale_session()  # branch de retorno temprano
        window.config.secure_erase = True

    def test_cleanup_stale_session_congelado(self, window, monkeypatch, dialogs, tmp_path):
        # Forzar temporales previos + modo PyInstaller para el dialogo informativo
        os.makedirs(window.config.user_input_dir, exist_ok=True)
        stale = os.path.join(window.config.user_input_dir, "viejo.html")
        with open(stale, "w", encoding="utf-8") as f:
            f.write("<html></html>")
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        window._cleanup_stale_session()
        assert any(
            d[0] == "information" and "Sesion anterior" in str(d[1])
            for d in dialogs
        )
        monkeypatch.delattr(sys, "frozen")

    def test_btn_validar_anim_enter_leave(self, window):
        window.btn_validar.enterEvent(None)
        window.btn_validar.leaveEvent(None)
        window.btn_validar_anim.stop()

    def test_onboarding_primera_ejecucion(self, window, dialogs):
        settings = QSettings()
        settings.setValue("onboarding_done", False)
        try:
            window.show_welcome_if_first_time()
            assert any(
                d[0] == "information" and "Guia rapida" in str(d[1])
                for d in dialogs
            )
            assert settings.value("onboarding_done", type=bool) is True

            # Segunda visita: no se repite el asistente
            total = len(dialogs)
            window.show_welcome_if_first_time()
            assert len(dialogs) == total
        finally:
            settings.setValue("onboarding_done", False)

    def test_tab_order_explicito(self, window):
        # La cadena de tabulacion esta definida sin errores de Qt

        assert window.combo_sexo is not None
        assert window.btn_validar is not None
        # NumericTab encadena todos sus spinboxes
        spins = list(window.numeric_tab.spinbox_map.values())
        assert len(spins) >= 20


# ── NumericTab: ficheros, plantilla, seleccion de fila ──────────────────


class TestNumericTabFicheros:
    def test_on_load_file_exitoso(self, monkeypatch, tmp_path):
        tab = NumericTab()
        src = tmp_path / "datos.csv"
        src.write_text("FEVI;55")
        monkeypatch.setattr(
            QFileDialog, "getOpenFileName", lambda *a, **k: (str(src), "")
        )
        cargados = []
        monkeypatch.setattr(
            tab, "load_from_file", lambda p: cargados.append(p) or True
        )
        tab._on_load_file()
        assert cargados

    def test_on_load_file_copia_falla(self, monkeypatch, tmp_path):
        tab = NumericTab()
        src = tmp_path / "datos.csv"
        src.write_text("FEVI;55")
        monkeypatch.setattr(
            QFileDialog, "getOpenFileName", lambda *a, **k: (str(src), "")
        )

        def boom(*a, **k):
            raise OSError("sin permisos")

        monkeypatch.setattr("src.utils.helpers.copy_to_user_input", boom)
        cargados = []
        monkeypatch.setattr(tab, "load_from_file", lambda p: cargados.append(p) or True)
        tab._on_load_file()
        assert cargados == [str(src)]  # fallback al archivo original

    def test_on_load_file_cancelado(self, monkeypatch):
        tab = NumericTab()
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
        tab._on_load_file()  # no debe fallar ni cargar nada

    def test_download_template_ok(self, monkeypatch, tmp_path, dialogs):
        tab = NumericTab()
        dest = str(tmp_path / "plantilla.xlsx")
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName", lambda *a, **k: (dest, "")
        )
        tab._on_download_template()
        assert os.path.exists(dest)

    def test_download_template_cancelado(self, monkeypatch):
        tab = NumericTab()
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
        tab._on_download_template()

    def test_download_template_error(self, monkeypatch, tmp_path, dialogs):
        import openpyxl

        tab = NumericTab()
        dest = str(tmp_path / "plantilla.xlsx")
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName", lambda *a, **k: (dest, "")
        )

        def boom(*a, **k):
            raise RuntimeError("openpyxl roto")

        monkeypatch.setattr(openpyxl, "Workbook", boom)
        tab._on_download_template()

    def test_load_from_file_varias_filas(self, monkeypatch, tmp_path):
        """2 filas -> dialogo de seleccion; fila 2 se recarga explicita."""
        from openpyxl import Workbook
        from src.core.data_loader import DataLoader

        filepath = str(tmp_path / "pacientes.xlsx")
        columnas = DataLoader.template_columns()
        wb = Workbook()
        ws = wb.active
        for col, (nombre, ejemplo) in enumerate(columnas.items(), start=1):
            ws.cell(row=1, column=col, value=nombre)
            ws.cell(row=2, column=col, value=ejemplo)
            ws.cell(row=3, column=col, value=ejemplo)
        wb.save(filepath)

        tab = NumericTab()
        recargas = []
        monkeypatch.setattr(
            tab, "load_from_file",
            lambda fp, row=0: recargas.append(row) or True,
        )
        # Sustituye el dialogo y verifica la recarga de la fila 2
        monkeypatch.setattr(
            QInputDialog, "getItem",
            lambda *a, **k: ("Fila 2", True),
        )
        tab._last_row_count = 2
        tab._ask_row_selection(filepath)
        assert recargas == [1]

    def test_ask_row_selection_cancelado(self, monkeypatch):
        tab = NumericTab()
        monkeypatch.setattr(QInputDialog, "getItem", lambda *a, **k: ("Fila 1", False))
        tab._last_row_count = 3
        tab._ask_row_selection("/no/importa.xlsx")  # cancel: sin recarga

    def test_highlight_match_por_subconjunto(self, window):
        tab = window.numeric_tab
        # "Volumen AI ind." contiene los tokens de "volumen_ai" -> subset
        res = tab._find_validation_result(
            "volumen_ai", {"Volumen AI ind. (ml/m2)": {"normal": True}}
        )
        assert res == {"normal": True}
        assert NumericTab._attr_matches_param(
            "volumen_ai", "Volumen AI Indexada (ml/m2)", exact=False
        )
        assert not NumericTab._attr_matches_param("fevi", "", exact=False)


# ── ReportPreview: exportar / abrir / guardar como ──────────────────────


class TestReportPreviewExport:
    @pytest.fixture
    def preview(self, qtbot, tmp_path):
        p = ReportPreview()
        qtbot.addWidget(p)
        return p

    def test_export_sin_pdf(self, preview, dialogs):
        preview._on_export_pdf()
        assert any(d[0] == "warning" for d in dialogs)

    def test_export_pdf_ok(self, preview, tmp_path, monkeypatch, dialogs):
        origen = tmp_path / "informe.pdf"
        origen.write_bytes(b"%PDF-1.4 fake")
        preview.set_pdf_path(str(origen))
        destino = tmp_path / "exportado.pdf"
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName", lambda *a, **k: (str(destino), "")
        )
        emitidos = []
        preview.export_requested.connect(emitidos.append)
        preview._on_export_pdf()
        assert destino.exists()
        assert emitidos == [str(destino)]
        assert any(d[0] == "information" for d in dialogs)

    def test_export_pdf_error_copia(self, preview, tmp_path, monkeypatch, dialogs):
        origen = tmp_path / "informe.pdf"
        origen.write_bytes(b"%PDF-1.4 fake")
        preview.set_pdf_path(str(origen))
        monkeypatch.setattr(
            QFileDialog,
            "getSaveFileName",
            lambda *a, **k: (str(tmp_path / "no" / "sub" / "x.pdf"), ""),
        )
        preview._on_export_pdf()
        assert any(d[0] == "critical" for d in dialogs)

    def test_save_as_delega_en_export(self, preview, tmp_path, monkeypatch, dialogs):
        origen = tmp_path / "informe.pdf"
        origen.write_bytes(b"%PDF-1.4 fake")
        preview.set_pdf_path(str(origen))
        destino = tmp_path / "guardado.pdf"
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName", lambda *a, **k: (str(destino), "")
        )
        preview._on_save_as()
        assert destino.exists()

    def test_open_file(self, preview, tmp_path, monkeypatch):
        llamadas = []
        monkeypatch.setattr(
            "src.gui.report_preview.QDesktopServices.openUrl",
            lambda url: llamadas.append(url) or True,
        )
        preview._on_open_file()  # sin pdf -> no hace nada
        assert llamadas == []

        f = tmp_path / "informe.pdf"
        f.write_bytes(b"%PDF")
        preview.set_pdf_path(str(f))
        preview._on_open_file()
        assert len(llamadas) == 1


# ── AITab: workers, carga de archivo, resultado y aplicacion ────────────


class TestAITabWorkers:
    def test_extract_worker_ok(self, monkeypatch):
        import src.gui.ai_tab as ai_mod

        monkeypatch.setattr(
            ai_mod, "extract_from_text",
            lambda text, **k: ExtractionResult(source="regex", numeric_params={"fevi": 55.0}),
        )
        resultados = []
        worker = ExtractWorker(
            text="texto", use_ai=False, model="m",
            base_url="http://localhost:11434", guide="colombian", ai_timeout=5,
        )
        worker.finished_ok.connect(resultados.append)
        worker.run()
        assert resultados and resultados[0].source == "regex"

    def test_extract_worker_error(self, monkeypatch):
        import src.gui.ai_tab as ai_mod

        def boom(*a, **k):
            raise RuntimeError("extraccion rota")

        monkeypatch.setattr(ai_mod, "extract_from_text", boom)
        errores = []
        worker = ExtractWorker(
            text="texto", use_ai=False, model="m",
            base_url="http://localhost:11434", guide="colombian", ai_timeout=5,
        )
        worker.finished_error.connect(errores.append)
        worker.run()
        assert errores and "extraccion rota" in errores[0]

    def test_extract_worker_cancel(self):
        worker = ExtractWorker(
            text="texto", use_ai=False, model="m",
            base_url="http://localhost:11434", guide="colombian", ai_timeout=5,
        )
        assert worker._is_cancelled() is False
        worker.request_cancel()
        assert worker._is_cancelled() is True

    def test_file_load_worker_ok(self, tmp_path):
        f = tmp_path / "info.txt"
        f.write_text("contenido del eco")
        textos = []
        worker = FileLoadWorker(str(f))
        worker.loaded.connect(textos.append)
        worker.run()
        assert textos == ["contenido del eco"]

    def test_file_load_worker_error(self, tmp_path):
        errores = []
        worker = FileLoadWorker(str(tmp_path / "no_existe.txt"))
        worker.failed.connect(errores.append)
        worker.run()
        assert errores

    def test_ollama_worker_ok(self, monkeypatch):
        import src.gui.ai_tab as ai_mod

        monkeypatch.setattr(
            ai_mod, "check_ollama", lambda url, timeout=2.0: (True, ["m1"])
        )
        salidas = []
        worker = OllamaStatusWorker("http://localhost:11434")
        worker.checked.connect(lambda ok, models: salidas.append((ok, models)))
        worker.run()
        assert salidas == [(True, ["m1"])]

    def test_ollama_worker_excepcion(self, monkeypatch):
        import src.gui.ai_tab as ai_mod

        def boom(*a, **k):
            raise RuntimeError("sin red")

        monkeypatch.setattr(ai_mod, "check_ollama", boom)
        salidas = []
        worker = OllamaStatusWorker("http://localhost:11434")
        worker.checked.connect(lambda ok, models: salidas.append((ok, models)))
        worker.run()
        assert salidas == [(False, [])]


class TestAITabUI:
    def test_paste_y_clear(self, window):
        tab = window.ai_tab
        QApplication.clipboard().setText("texto del portapapeles")
        tab._on_paste()
        assert "portapapeles" in tab.txt_input.toPlainText()
        tab._on_clear()
        assert tab.txt_input.toPlainText() == ""
        assert not tab.btn_aplicar.isEnabled()

    def test_extract_sin_texto(self, window, dialogs):
        tab = window.ai_tab
        tab.txt_input.clear()
        tab._on_extract()
        assert tab.btn_extraer.isEnabled()
        assert any(d[0] == "warning" for d in dialogs)

    def test_extract_done_rico(self, window):
        tab = window.ai_tab
        result = ExtractionResult(
            source="ollama",
            model="qwen2.5:3b",
            numeric_params={"fevi": 55.0},
            numeric_confidence={"fevi": 0.9},
            confidence=0.8,
            processing_time=1.2,
            visual_data={
                "derrame_pericardico": "Si",
                "segmentos_afectados": "anteroseptal",
                "observaciones_visuales": "algo leve",
            },
            patient_data={
                "sexo": "M",
                "edad": "45",
                "nombre_medico": "Dra. X",
                "fecha_estudio": "2026-01-01",
                "notas": "nota IA",
            },
            clinical_impression="correlacion clinica",
            warnings=["advertencia 1"],
        )
        tab._on_extract_done(result)
        texto = tab.txt_resultado.toPlainText()
        assert "FEVI" in texto
        assert "Segmentos:" in texto
        assert "Observaciones:" in texto
        assert "Notas:" in texto
        assert "IMPRESION CLINICA" in texto
        assert "ADVERTENCIAS" in texto
        assert tab.btn_aplicar.isEnabled()
        assert tab.btn_extraer.isEnabled()

        # Camino sin parametros ni advertencias
        tab._on_extract_done(ExtractionResult(source="regex"))
        texto2 = tab.txt_resultado.toPlainText()
        assert "(ninguno detectado)" in texto2
        assert "Sin advertencias." in texto2

    def test_extract_error(self, window, dialogs):
        tab = window.ai_tab
        tab._on_extract_error("fallo grave")
        assert tab.btn_extraer.isEnabled()
        assert "Error" in tab.lbl_resultado.text()
        assert any(d[0] == "critical" for d in dialogs)

    def test_apply_branches(self, window, dialogs):
        tab = window.ai_tab
        tab._last_result = None
        tab._on_apply()  # retorno temprano

        tab._last_result = ExtractionResult(source="x")
        tab._apply_callback = None
        tab._on_apply()
        assert any(d[0] == "warning" for d in dialogs)

        aplicados = []
        tab.set_on_apply(aplicados.append)
        tab._on_apply()
        assert aplicados and aplicados[0].source == "x"

    def test_load_file_cancelado(self, window, monkeypatch):
        tab = window.ai_tab
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
        tab._on_load_file()

    def test_load_file_demasiado_grande(self, window, monkeypatch, tmp_path, dialogs):
        tab = window.ai_tab
        tab.config.max_file_mb = 0
        f = tmp_path / "grande.txt"
        f.write_text("x")
        monkeypatch.setattr(
            QFileDialog, "getOpenFileName", lambda *a, **k: (str(f), "")
        )
        tab._on_load_file()
        assert any(d[0] == "warning" for d in dialogs)
        tab.config.max_file_mb = 20

    def test_load_file_ruta_inexistente(self, window, monkeypatch, tmp_path, dialogs):
        """getsize falla (OSError) y la lectura posterior también."""
        tab = window.ai_tab
        monkeypatch.setattr(
            QFileDialog, "getOpenFileName",
            lambda *a, **k: (str(tmp_path / "fantasma.txt"), ""),
        )
        monkeypatch.setattr(FileLoadWorker, "start", lambda self: self.run())
        tab._on_load_file()
        assert any(d[0] == "critical" for d in dialogs)

    def test_load_file_exitoso(self, window, monkeypatch, tmp_path):
        tab = window.ai_tab
        f = tmp_path / "eco.txt"
        f.write_text("FEVI 55 por ciento")
        monkeypatch.setattr(
            QFileDialog, "getOpenFileName", lambda *a, **k: (str(f), "")
        )
        monkeypatch.setattr(FileLoadWorker, "start", lambda self: self.run())
        tab._on_load_file()
        assert "FEVI 55" in tab.txt_input.toPlainText()

    def test_load_file_sin_texto_extraible(self, window, monkeypatch, tmp_path, dialogs):
        tab = window.ai_tab
        f = tmp_path / "vacio.txt"
        f.write_text("   \n  ")
        monkeypatch.setattr(
            QFileDialog, "getOpenFileName", lambda *a, **k: (str(f), "")
        )
        monkeypatch.setattr(FileLoadWorker, "start", lambda self: self.run())
        tab._on_load_file()
        assert any(d[0] == "warning" for d in dialogs)

    def test_ollama_status_ui(self, window):
        tab = window.ai_tab

        class FakeRunning:
            def isRunning(self):
                return True

        tab._ollama_worker = FakeRunning()
        tab._refresh_ollama_status()  # solapado -> retorno temprano

        tab._on_ollama_status(True, ["modelo-nuevo"])
        assert "modelo-nuevo" in [
            tab.combo_model.itemText(i) for i in range(tab.combo_model.count())
        ]
        assert "conectado" in tab.lbl_ollama.text()

        tab._on_ollama_status(False, [])
        assert "no responde" in tab.lbl_ollama.text()
        tab._ollama_worker = None

    def test_shutdown_con_hilos_activos(self, window):
        tab = window.ai_tab

        class FakeWorker:
            def request_cancel(self):
                pass

            def isRunning(self):
                return True

            def wait(self, ms):
                return False

        tab._worker = FakeWorker()
        tab._load_worker = FakeWorker()
        tab._ollama_worker = FakeWorker()
        tab.shutdown()  # ramas de advertencia por hilo tardado
        tab._worker = None
        tab._load_worker = None
        tab._ollama_worker = None


# ── error_guard ─────────────────────────────────────────────────────────


class TestErrorGuard:
    def test_show_error_dialog_flujo_completo(self, monkeypatch):
        from src.utils import error_guard

        ejecuciones = []
        monkeypatch.setattr(QMessageBox, "exec", lambda self: ejecuciones.append(True))
        error_guard.set_dialogs_enabled(True)
        try:
            error_guard.reset_error_guard()
            error_guard._show_error_dialog("Titulo", "Mensaje")
            assert ejecuciones == [True]

            # Tras alcanzar el limite solo se registra en log (sin exec)
            for _ in range(error_guard._MAX_ERROR_DIALOGS + 5):
                error_guard._show_error_dialog("T", "M")
            assert len(ejecuciones) == error_guard._MAX_ERROR_DIALOGS
        finally:
            error_guard.reset_error_guard()
            error_guard.set_dialogs_enabled(False)

    def test_show_error_dialog_deshabilitado(self):
        from src.utils import error_guard

        error_guard.set_dialogs_enabled(False)
        error_guard._show_error_dialog("T", "M")  # retorno temprano sin app/dialogo
        assert error_guard._state["dialogs"] == 0

    def test_install_uninstall_hook(self):
        from src.utils import error_guard

        original = sys.excepthook
        try:
            error_guard.install_excepthook()
            hook = sys.excepthook
            assert hook is not original
            # Instalar dos veces no pisa el hook original guardado
            error_guard.install_excepthook()
            assert sys.excepthook is not original
            assert error_guard._original_hook["hook"] is original
        finally:
            error_guard.uninstall_excepthook()
        assert sys.excepthook is original

    def test_hook_keyboard_interrupt(self):
        from src.utils import error_guard

        original = sys.excepthook
        try:
            error_guard.install_excepthook()
            # Debe delegar en __excepthook__ sin registrar dialogo
            sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
        finally:
            error_guard.uninstall_excepthook()
        assert sys.excepthook is original

    def test_hook_allow_abort(self):
        from src.utils import error_guard

        original = sys.excepthook
        try:
            error_guard.install_excepthook(allow_abort=True)
            sys.excepthook(ValueError, ValueError("boom"), None)
        finally:
            error_guard.uninstall_excepthook()
        assert sys.excepthook is original

    def test_hook_sin_abort(self):
        from src.utils import error_guard

        original = sys.excepthook
        try:
            error_guard.install_excepthook(allow_abort=False)
            sys.excepthook(ValueError, ValueError("boom"), None)
        finally:
            error_guard.uninstall_excepthook()
        assert sys.excepthook is original


# ── logger ──────────────────────────────────────────────────────────────


class TestLoggerSecureRollover:
    @pytest.fixture
    def clean_logger(self):
        logger = logging.getLogger("ecocardiograma")
        old_handlers = list(logger.handlers)
        old_level = logger.level
        logger.handlers = []
        logger.setLevel(logging.DEBUG)
        yield logger
        logger.handlers = old_handlers
        logger.setLevel(old_level)

    def test_do_rollover_borra_rotados(self, tmp_path, clean_logger, monkeypatch):
        from src.utils.logger import SecureTimedRotatingFileHandler
        import src.utils.logger as logger_mod

        log_file = str(tmp_path / "app.log")
        handler = SecureTimedRotatingFileHandler(
            log_file, when="midnight", backupCount=7, encoding="utf-8"
        )
        stale = tmp_path / "app.log.2020-01-01"
        stale.write_text("potencial phi")
        monkeypatch.setattr(
            logger_mod.TimedRotatingFileHandler,
            "getFilesToDelete",
            lambda self: [str(stale)],
        )
        handler.doRollover()
        assert not stale.exists()
        handler.close()

    def test_setup_logger_archivo_invalido(self, clean_logger, tmp_path):
        from src.utils.logger import setup_logger

        # Un directorio como "archivo de log" -> OSError capturado, solo consola
        directorio = tmp_path / "es_un_directorio"
        directorio.mkdir()
        logger = setup_logger(str(directorio))
        logger.info("sigue funcionando")
        assert logger.handlers


# ── updater ─────────────────────────────────────────────────────────────


class TestUpdaterInternos:
    class _Respuesta:
        def __init__(self, data: bytes):
            self._data = data

        def read(self):
            return self._data

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def test_get_json_url_no_oficial(self, monkeypatch):
        from src.core import updater

        llamadas = []
        monkeypatch.setattr(
            updater.urllib.request, "urlopen", lambda *a, **k: llamadas.append(1)
        )
        assert updater._get_json("http://ejemplo.com/api", 1.0) is None
        assert updater._get_json("https://evil.example.com/x", 1.0) is None
        assert llamadas == []

    def test_get_json_ok(self, monkeypatch):
        from src.core import updater

        monkeypatch.setattr(
            updater.urllib.request, "urlopen",
            lambda *a, **k: self._Respuesta(b'{"tag_name": "v9.9.9"}'),
        )
        data = updater._get_json("https://api.github.com/repos/a/b/releases/latest", 1.0)
        assert data == {"tag_name": "v9.9.9"}

    def test_get_json_respuesta_no_dict(self, monkeypatch):
        from src.core import updater

        monkeypatch.setattr(
            updater.urllib.request, "urlopen",
            lambda *a, **k: self._Respuesta(b"[1, 2, 3]"),
        )
        data = updater._get_json("https://api.github.com/repos/a/b/releases/latest", 1.0)
        assert data is None

    def test_get_json_excepcion_red(self, monkeypatch):
        from src.core import updater

        def boom(*a, **k):
            raise OSError("sin conexion")

        monkeypatch.setattr(updater.urllib.request, "urlopen", boom)
        data = updater._get_json("https://api.github.com/repos/a/b/releases/latest", 1.0)
        assert data is None


# ── config ──────────────────────────────────────────────────────────────


class TestConfigResiliencia:
    def test_yaml_sintaxis_invalida(self, tmp_path):
        from src.utils.config import load_config

        archivo = tmp_path / "config.yaml"
        archivo.write_text("guia: [sin cerrar\n  - ", encoding="utf-8")
        cfg = load_config(str(archivo))
        assert cfg is not None  # defaults en lugar de excepcion

    def test_yaml_estructura_invalida(self, tmp_path):
        from src.utils.config import load_config

        archivo = tmp_path / "config.yaml"
        archivo.write_text("- solo\n- una lista\n", encoding="utf-8")
        cfg = load_config(str(archivo))
        assert cfg is not None

    def test_get_data_root_congelado(self, monkeypatch, tmp_path):
        import src.utils.config as config_mod

        monkeypatch.setattr(sys, "frozen", True, raising=False)

        monkeypatch.setattr(sys, "platform", "darwin")
        assert "Application Support" in config_mod.get_data_root()

        # Rama Windows: se decide por os.name (sys.platform deja de ser darwin)
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(os, "name", "nt")
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
        assert config_mod.get_data_root().startswith(str(tmp_path))

        monkeypatch.setattr(os, "name", "posix")
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
        assert config_mod.get_data_root().startswith(str(tmp_path / "xdg"))


# ── param_registry / reference_range / helpers / colombian_reference ────


class TestParamRegistry:
    def test_get_field_inexistente(self):
        from src.models.param_registry import all_keys, get_field

        with pytest.raises(KeyError):
            get_field("parametro_que_no_existe")
        assert "fevi" in all_keys()
        assert len(all_keys()) >= 20


class TestReferenceRangesExcel:
    def _escribir_excel(self, path, filas):
        import pandas as pd

        pd.DataFrame(filas).to_excel(path, index=False)
        return str(path)

    def test_load_from_excel_y_branches(self, tmp_path):
        from src.models.reference_range import ReferenceRanges

        hombres = self._escribir_excel(
            tmp_path / "h.xlsx",
            {
                "Parametro": ["FEVI", "", "Masa VI"],
                "Limite_Inferior": ["abc", 50, 90],      # "abc" -> None
                "Limite_Superior": [70, "xyz", float("nan")],  # "xyz"/NaN -> None
                "Unidad": ["%", "g", "g"],
            },
        )
        mujeres = self._escribir_excel(
            tmp_path / "m.xlsx",
            {"Parametro": ["FEVI"], "Limite_Inferior": [55],
             "Limite_Superior": [75], "Unidad": ["%"]},
        )

        rr = ReferenceRanges()
        rr.load_from_excel(hombres, mujeres)
        rango = rr.get_range(Sexo.MASCULINO, "FEVI")
        assert rango is not None and rango.limite_superior == 70
        # Conversiones fallidas -> None
        mala = rr.get_range(Sexo.MASCULINO, "Masa VI")
        assert mala.limite_inferior == 90 and mala.limite_superior is None
        # Fila sin parametro ignorada
        assert rr.get_range(Sexo.MASCULINO, "") is None
        assert rr.get_range(Sexo.FEMENINO, "FEVI") is not None

    def test_load_from_excel_archivo_invalido(self, tmp_path):
        from src.models.reference_range import ReferenceRanges

        rr = ReferenceRanges()
        with pytest.raises(ValueError):
            rr.load_from_excel(
                str(tmp_path / "no_existe.xlsx"), str(tmp_path / "tampoco.xlsx")
            )


class TestHelpersSueltos:
    def test_clear_directory_con_subdirectorio(self, tmp_path):
        from src.utils.helpers import clear_directory

        d = tmp_path / "datos"
        (d / "sub").mkdir(parents=True)
        (d / "archivo.txt").write_text("x")
        removidos = clear_directory(str(d))
        assert any("archivo.txt" in r for r in removidos)
        assert any(os.sep + "sub" in r for r in removidos)

    def test_clear_directory_inexistente(self, tmp_path):
        from src.utils.helpers import clear_directory

        assert clear_directory(str(tmp_path / "nada")) == []

    def test_files_equal_archivos_inexistentes(self):
        from src.utils.helpers import _files_equal

        assert _files_equal("/no/existe/a", "/no/existe/b") is False


class TestColombianReference:
    def test_psap_limit_altitud_invalida(self):
        from src.models.colombian_reference import psap_upper_limit

        assert psap_upper_limit("no_numero") == 30.0
        assert psap_upper_limit(None) == 30.0
        assert psap_upper_limit(-100) == 30.0
        assert psap_upper_limit(2640) == pytest.approx(38.0, abs=0.1)
