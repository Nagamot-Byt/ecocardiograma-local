"""
Ventana principal de la aplicacion.
Orquesta el flujo: datos del paciente, validacion, generacion de informes.
"""
import os
import sys

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QComboBox,
    QFileDialog, QMessageBox, QFrame,
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import QThread, pyqtSignal

from src.models.patient import Patient, Sexo
from src.models.colombian_reference import load_colombian_references, GUIDE_NAME
from src.utils.config import load_config
from src.utils.logger import setup_logger
from src.utils.helpers import generate_patient_id, ensure_dir, copy_to_user_input
from src.core.data_loader import DataLoader
from src.core.validator import Validator
from src.core.visual_input import VisualInputHandler
from src.core.report_engine import ReportEngine
from src.core.secure_delete import SecureDeleter
from src.core.recommendations import get_rule_based_recommendations
from src.core.updater import check_for_updates
from src.gui.numeric_tab import NumericTab
from src.gui.visual_tab import VisualTab
from src.gui.report_preview import ReportPreview
from src.gui.ai_tab import AITab
from src.core.version import APP_NAME, APP_VERSION

logger = setup_logger()


class UpdateCheckWorker(QThread):
    """Consulta GitHub Releases en un hilo para no congelar la UI."""

    finished_check = pyqtSignal(dict)

    def __init__(self, repo: str, current_version: str, timeout: float = 8.0):
        super().__init__()
        self.repo = repo
        self.current_version = current_version
        self.timeout = timeout

    def run(self):
        resultado = check_for_updates(
            current_version=self.current_version,
            repo=self.repo,
            timeout=self.timeout,
        )
        self.finished_check.emit(resultado)


def get_guide_name(guide: str) -> str:
    """Nombre legible de la guia de referencia activa."""
    if guide == "ase":
        return "Guías ASE 2023"
    return GUIDE_NAME


class MainWindow(QMainWindow):
    """Ventana principal de la aplicacion Ecocardiograma Local."""

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.patient = Patient()
        self.patient.id = generate_patient_id()

        # Componentes de negocio
        if self.config.guide == "colombian":
            self.data_loader = None
            self.reference_ranges = load_colombian_references(self.config.altitude_masl)
            logger.info(
                f"Referencias cargadas: {get_guide_name('colombian')} "
                f"(altitud {self.config.altitude_masl:.0f} msnm)"
            )
        else:
            self.data_loader = DataLoader(
                self.config.hombres_file, self.config.mujeres_file
            )
            self.data_loader.load_references()
            self.reference_ranges = self.data_loader.reference_ranges

        self.validator = Validator(self.reference_ranges)
        self.visual_handler = VisualInputHandler()
        self.report_engine = ReportEngine(
            self.config.report_template, self.config.output_dir,
            guide_name=get_guide_name(self.config.guide),
            altitude_masl=self.config.altitude_masl if self.config.guide == "colombian" else None,
        )
        self.secure_deleter = SecureDeleter(
            self.config.user_input_dir,
            self.config.output_dir,
            self.config.secure_erase,
        )

        # Asegurar directorios
        ensure_dir(self.config.user_input_dir)
        ensure_dir(self.config.output_dir)

        self._build_ui()
        self._connect_signals()
        self._cleanup_stale_session()

        # Chequeo silencioso de actualizaciones al arrancar (si esta habilitado)
        if self.config.update.enabled and self.config.update.repo:
            self._start_update_check(manual=False)

    def _cleanup_stale_session(self):
        """Elimina temporales de una sesion anterior que quedo sin limpiar (crash)."""
        if not self.config.secure_erase:
            return
        result = self.secure_deleter.clean_session()
        total = result["total"]
        if total:
            if getattr(sys, "frozen", False):
                QMessageBox.information(
                    self, "Sesion anterior",
                    f"Se eliminaron {total} archivo(s) temporales de una sesion "
                    "anterior que no se cerro correctamente."
                )
            logger.info(f"Temporales de sesion anterior limpiados al iniciar: {total}")

    def _build_ui(self):
        self.setWindowTitle(f"{APP_NAME} - Informes Offline v{APP_VERSION}")
        self.setMinimumSize(1100, 750)

        # Menu bar
        menubar = self.menuBar()

        # Menu Archivo
        menu_archivo = menubar.addMenu("Archivo")

        act_nuevo = QAction("Nuevo Paciente", self)
        act_nuevo.triggered.connect(self._on_new_patient)
        menu_archivo.addAction(act_nuevo)

        act_cargar = QAction("Cargar Datos (.xlsx/.csv)", self)
        act_cargar.triggered.connect(self._on_load_file)
        menu_archivo.addAction(act_cargar)

        act_limpiar = QAction("Limpiar Sesion", self)
        act_limpiar.triggered.connect(self._on_clean_session)
        menu_archivo.addAction(act_limpiar)

        menu_archivo.addSeparator()

        act_salir = QAction("Salir", self)
        act_salir.triggered.connect(self.close)
        menu_archivo.addAction(act_salir)

        # Menu Ayuda
        menu_ayuda = menubar.addMenu("Ayuda")

        act_actualizar = QAction("Buscar Actualizaciones...", self)
        act_actualizar.triggered.connect(self._on_check_updates)
        menu_ayuda.addAction(act_actualizar)

        menu_ayuda.addSeparator()

        act_acerca = QAction("Acerca de", self)
        act_acerca.triggered.connect(self._show_about)
        menu_ayuda.addAction(act_acerca)

        # Widget central
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # Header
        header = QFrame()
        header.setFrameShape(QFrame.Shape.StyledPanel)
        header.setStyleSheet(
            "QFrame { background: #1a5276; padding: 10px; border-radius: 6px; }"
        )
        header_layout = QHBoxLayout(header)

        title_lbl = QLabel("ECOCARDIOGRAMA LOCAL")
        title_lbl.setStyleSheet(
            "color: white; font-size: 16pt; font-weight: bold;"
        )
        header_layout.addWidget(title_lbl)

        ver_lbl = QLabel(f"v{APP_VERSION}")
        ver_lbl.setStyleSheet("color: #aed6f1; font-size: 9pt;")
        header_layout.addWidget(ver_lbl)

        header_layout.addStretch()

        # Selector de sexo
        sexo_lbl = QLabel("Sexo del Paciente:")
        sexo_lbl.setStyleSheet("color: white; font-size: 11pt;")
        header_layout.addWidget(sexo_lbl)

        self.combo_sexo = QComboBox()
        self.combo_sexo.addItems(["Masculino", "Femenino"])
        self.combo_sexo.setStyleSheet(
            "QComboBox { padding: 4px 10px; font-size: 11pt; min-width: 120px; }"
        )
        header_layout.addWidget(self.combo_sexo)

        # ID del paciente
        id_lbl = QLabel(f"ID: {self.patient.id}")
        id_lbl.setStyleSheet("color: #aed6f1; font-size: 9pt;")
        header_layout.addWidget(id_lbl)
        self.lbl_id = id_lbl

        header_layout.addStretch()

        btn_validar = QPushButton("Validar Datos")
        btn_validar.setStyleSheet(
            "QPushButton { background: #f39c12; color: white; "
            "padding: 6px 16px; font-weight: bold; border-radius: 4px; }"
        )
        header_layout.addWidget(btn_validar)
        self.btn_validar = btn_validar

        main_layout.addWidget(header)

        # Tabs principales
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabBar::tab { padding: 8px 20px; font-size: 11pt; }"
            "QTabBar::tab:selected { font-weight: bold; }"
        )

        # Tab 1: Datos Numericos
        self.numeric_tab = NumericTab()
        self.tabs.addTab(self.numeric_tab, "Datos Numericos")

        # Tab 2: Hallazgos Visuales
        self.visual_tab = VisualTab()
        self.tabs.addTab(self.visual_tab, "Hallazgos Visuales")

        # Tab 3: IA - extraccion automatica
        self.ai_tab = AITab(self.config)
        self.tabs.addTab(self.ai_tab, "IA - Lectura")

        # Tab 4: Informe / Vista Previa
        self.report_tab = ReportPreview()
        self.report_tab.set_generar_callback(self._on_generate_report)
        self.report_tab.init_buttons()
        self.tabs.addTab(self.report_tab, "Informe")

        main_layout.addWidget(self.tabs)

        # Status bar
        self.statusBar().showMessage(
            "Listo. Extraiga los datos con IA o ingrese los datos manualmente y valide."
        )
        self.statusBar().setStyleSheet("font-size: 10pt;")

    def _connect_signals(self):
        """Conecta las senales de la UI con los metodos correspondientes."""
        self.combo_sexo.currentIndexChanged.connect(self._on_sexo_changed)
        self.btn_validar.clicked.connect(self._on_validate)
        self.numeric_tab.data_changed.connect(self._on_data_changed)
        self.visual_tab.data_changed.connect(self._on_data_changed)
        self.ai_tab.set_on_apply(self._on_apply_extraction)

    def _on_sexo_changed(self, index: int):
        """Maneja el cambio de sexo del paciente."""
        if index == 0:
            self.patient.sexo = Sexo.MASCULINO
        else:
            self.patient.sexo = Sexo.FEMENINO
        logger.info("Sexo del paciente actualizado")

    def _on_data_changed(self):
        """Maneja cambios en los datos (invalida la vista previa y recalcula en vivo)."""
        self.statusBar().showMessage(
            "Datos modificados. Valide antes de generar el informe."
        )
        self.report_tab.clear()
        self._recalcular_vivo()

    def _recalcular_vivo(self):
        """
        Recalcula la validacion y las sugerencias por reglas al editar datos,
        sin generar informe. Usa un Patient temporal para no alterar el actual.
        """
        scratch = Patient()
        scratch.sexo = (
            Sexo.MASCULINO if self.combo_sexo.currentIndex() == 0 else Sexo.FEMENINO
        )
        self.numeric_tab.apply_to_patient(scratch)
        self.visual_tab.apply_to_patient(scratch)

        tabla = self.validator.get_validation_table(scratch)
        self.numeric_tab.highlight_validation(
            {fila["parametro"]: {"normal": fila["normal"]} for fila in tabla}
        )

        n_anormales = sum(1 for fila in tabla if fila["normal"] is False)
        if n_anormales:
            recs = get_rule_based_recommendations(tabla)
            texto = f"{n_anormales} valor(es) fuera de rango"
            if recs:
                texto += f" - {len(recs)} sugerencia(s) de seguimiento"
            self.numeric_tab.set_live_status(texto, warn=True)
        else:
            self.numeric_tab.set_live_status(
                "Todos los valores dentro de rango normal", warn=False
            )

    def _on_validate(self):
        """Valida los datos actuales contra los rangos ASE."""
        # Recoger datos de ambas pestanas
        self.numeric_tab.apply_to_patient(self.patient)
        self.visual_tab.apply_to_patient(self.patient)

        # Validar
        resultados = self.validator.validate_patient(self.patient)

        # Aplicar colores a la pestana numerica
        self.numeric_tab.highlight_validation(resultados)

        # Generar resumen
        summary = self.validator.get_summary(self.patient)
        visual_summary = self.visual_handler.get_summary(self.patient)

        full_summary = "=== VALIDACION DE DATOS ===\n\n"
        full_summary += "Valores:\n"
        for item in summary:
            full_summary += item + "\n"
        full_summary += "\nHallazgos Visuales:\n"
        for item in visual_summary:
            full_summary += item + "\n"

        self.report_tab.display_resumen(full_summary)
        self.tabs.setCurrentIndex(3)  # Cambiar a tab de informe (0 num, 1 visual, 2 IA, 3 informe)
        self.statusBar().showMessage("Validacion completada. Revise los resultados.")

        n_anormales = sum(1 for r in resultados.values() if r["normal"] is False)
        if n_anormales > 0:
            self.statusBar().setStyleSheet(
                "font-size: 10pt; color: #c0392b; font-weight: bold;"
            )
            self.statusBar().showMessage(
                f"VALIDACION: {n_anormales} valor(es) fuera de rango"
            )
        else:
            self.statusBar().setStyleSheet(
                "font-size: 10pt; color: #27ae60; font-weight: bold;"
            )
            self.statusBar().showMessage(
                "VALIDACION: Todos los valores dentro de rango normal"
            )

    def _on_apply_extraction(self, result):
        """Aplica el resultado de la extraccion IA al paciente y a las pestanas."""
        if not result or not result.numeric_params:
            QMessageBox.information(
                self, "Sin datos",
                "La extraccion no produjo parametros para aplicar.\n"
                "Revise el texto cargado e intente nuevamente."
            )
            return

        # Reiniciar paciente con los datos extraidos, conservando el sexo
        # seleccionado en la UI (la IA puede no detectarlo).
        sexo_actual = (
            Sexo.MASCULINO if self.combo_sexo.currentIndex() == 0 else Sexo.FEMENINO
        )
        self.patient = Patient()
        self.patient.id = generate_patient_id()
        self.patient.sexo = sexo_actual
        self.lbl_id.setText(f"ID: {self.patient.id}")

        # Parametros numericos
        for key, value in result.numeric_params.items():
            if hasattr(self.patient, key):
                setattr(self.patient, key, value)

        # Hallazgos visuales
        for field, value in result.visual_data.items():
            if hasattr(self.patient, field):
                setattr(self.patient, field, value)

        # Datos del paciente
        pd = result.patient_data or {}
        if pd.get("sexo"):
            self.patient.sexo = Sexo.MASCULINO if pd["sexo"] == "M" else Sexo.FEMENINO
            self.combo_sexo.setCurrentIndex(0 if pd["sexo"] == "M" else 1)
        if pd.get("edad"):
            try:
                self.patient.edad = int(float(pd["edad"]))
            except (ValueError, TypeError):
                pass
        if pd.get("nombre_medico"):
            self.patient.nombre_medico = pd["nombre_medico"]
        if pd.get("fecha_estudio"):
            self.patient.fecha_estudio = pd["fecha_estudio"]
        if pd.get("notas"):
            self.patient.notas = pd["notas"]
        if result.clinical_impression:
            self.patient.impresion_clinica = result.clinical_impression
        if result.recommendations:
            self.patient.recomendaciones = list(result.recommendations)

        # Trazabilidad de la IA en el informe
        self.patient.ia_model = getattr(result, "model", "") or ""
        self.patient.ia_source = getattr(result, "source", "") or ""
        conf = getattr(result, "confidence", None)
        self.patient.ia_confidence = conf if isinstance(conf, (int, float)) else None

        # Campos numericos que quedaron sin extraer
        from src.models.param_registry import NUMERIC_FIELDS

        presentes = {
            f["validation_label"]
            for f in NUMERIC_FIELDS
            if getattr(self.patient, f["key"], None) is not None
        }
        faltantes = len(NUMERIC_FIELDS) - len(presentes)

        # Reflejar en las pestanas
        self.numeric_tab._on_clear()
        self.numeric_tab.populate_from_patient(self.patient)
        self.visual_tab.populate_from_patient(self.patient)
        self.report_tab.clear()

        self.statusBar().setStyleSheet("font-size: 10pt; color: #1a5276; font-weight: bold;")
        aviso_faltantes = (
            f" Faltan {faltantes} campos." if faltantes else " Todos los campos registrados."
        )
        self.statusBar().showMessage(
            f"Extraccion aplicada: {len(result.numeric_params)} parametros "
            f"({result.source}).{aviso_faltantes} Revise y valide los datos.", 10000
        )
        self.tabs.setCurrentIndex(0)  # Ir a datos numericos (0 num, 1 visual, 2 IA, 3 informe)
        logger.info("Extraccion aplicada al informe")

    def _on_generate_report(self):
        """Genera el informe PDF."""
        # Recoger datos
        self.numeric_tab.apply_to_patient(self.patient)
        self.visual_tab.apply_to_patient(self.patient)

        try:
            pdf_path = self.report_engine.generate_report(
                self.patient, self.validator, self.visual_handler
            )

            # Leer el HTML generado para vista previa
            if pdf_path.endswith(".pdf"):
                html_path = pdf_path.replace(".pdf", ".html")
            else:
                html_path = pdf_path  # Ya es HTML (fallback sin WeasyPrint)

            if os.path.exists(html_path):
                with open(html_path, "r", encoding="utf-8") as f:
                    html_content = f.read()
                self.report_tab.display_html(html_content, html_path)

            # Solo reportar como PDF si efectivamente es un PDF
            if pdf_path.endswith(".pdf"):
                self.report_tab.set_pdf_path(pdf_path)
            else:
                self.report_tab.set_pdf_path(None)
                self.report_tab.lbl_estado.setText(
                    "WeasyPrint no disponible. Solo se genero HTML."
                )
                self.report_tab.lbl_estado.setStyleSheet(
                    "color: #e67e22; font-weight: bold; font-style: italic;"
                )
            self.statusBar().showMessage(
                f"Informe generado: {os.path.basename(pdf_path)}", 10000
            )
            logger.info(f"Informe generado exitosamente: {os.path.basename(pdf_path)}")

        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"No se pudo generar el informe:\n{e}"
            )
            logger.error(f"Error generando informe: {e}")

    def _on_load_file(self):
        """Carga datos desde un archivo externo."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Cargar Datos", "",
            "Archivos Excel (*.xlsx);;Archivos CSV (*.csv);;Todos (*.*)"
        )
        if filepath:
            # Copiar al directorio user_input
            dest = copy_to_user_input(filepath, self.config.user_input_dir)
            try:
                logger.info(f"Archivo copiado a user_input: {os.path.basename(dest)}")
            except Exception as e:  # pragma: no cover
                logger.warning(f"No se pudo copiar archivo: {e}")

            # Cargar en la pestana numerica
            success = self.numeric_tab.load_from_file(dest)
            if success:
                QMessageBox.information(
                    self, "Exito",
                    "Datos cargados correctamente."
                )
            else:
                QMessageBox.warning(
                    self, "Aviso",
                    "No se pudieron cargar datos del archivo.\n"
                    "Verifique el formato y los nombres de columnas."
                )

    def _on_new_patient(self):
        """Reinicia todos los datos para un nuevo paciente."""
        reply = QMessageBox.question(
            self, "Nuevo Paciente",
            "Se limpiaran todos los datos actuales.\nContinuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.patient = Patient()
            self.patient.id = generate_patient_id()
            self.lbl_id.setText(f"ID: {self.patient.id}")
            self.numeric_tab._on_clear()
            self.numeric_tab.clear_highlights()
            self.visual_tab._on_clear()
            self.report_tab.clear()
            self.statusBar().showMessage("Nuevo paciente iniciado.")
            self.statusBar().setStyleSheet("font-size: 10pt;")
            logger.info("Nuevo paciente creado")

    def _on_clean_session(self):
        """Ejecuta la limpieza segura de la sesion."""
        reply = QMessageBox.question(
            self, "Limpiar Sesion",
            "Se eliminaran de forma segura los HTML/PDF temporales de la sesion.\n"
            "Los informes ya exportados NO se veran afectados.\n\nContinuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            result = self.secure_deleter.clean_session()
            QMessageBox.information(
                self, "Sesion Limpiada",
                f"Archivos eliminados:\n"
                f"  - Input: {len(result['user_input'])}\n"
                f"  - Output: {len(result['output'])}\n"
                f"  - Total: {result['total']}"
            )
            logger.info(
                f"Sesion limpiada: {result['total']} archivos "
                f"({len(result['user_input'])} input, {len(result['output'])} output)"
            )

    def _show_about(self):
        QMessageBox.about(
            self, "Acerca de Ecocardiograma Local",
            "<h3>Ecocardiograma Local</h3>"
            "<p>Asistente inteligente que lee tu ecocardiograma, extrae los datos "
            "automaticamente con IA local, los valida con parametros colombianos "
            "y genera un informe profesional listo para usar.</p>"
            "<p><b>Caracteristicas:</b></p>"
            "<ul>"
            "<li>Extraccion automatica de datos con IA local (Ollama, modelo &lt; 7B)</li>"
            "<li>Lectura de PDF, TXT y CSV; OCR para imagenes (requiere Tesseract)</li>"
            "<li>Validacion contra guias Colombianas SCC/LATAM y ASE por sexo</li>"
            "<li>PSAP ajustado por altitud de la ciudad</li>"
            "<li>Impresion clinica y recomendaciones generadas por la IA</li>"
            "<li>Generacion de informes PDF profesionales</li>"
            "<li>100% offline - sin llamadas a APIs externas</li>"
            "<li>Borrado seguro de datos temporales</li>"
            "</ul>"
            "<p><b>Guia activa:</b> " + get_guide_name(self.config.guide) + "</p>"
            f"<p><b>Version:</b> {APP_VERSION}</p>"
        )

    def _on_check_updates(self):
        """Busca actualizaciones a pedido del usuario (menu Ayuda)."""
        if not self.config.update.enabled or not self.config.update.repo:
            QMessageBox.information(
                self, "Actualizaciones",
                "La verificacion de actualizaciones esta deshabilitada.\n"
                "Configure 'update.repo' en configs/config.yaml para activarla."
            )
            return
        self._start_update_check(manual=True)

    def _start_update_check(self, manual: bool):
        """Lanza la consulta de actualizaciones en un hilo (silenciosa o manual)."""
        worker = UpdateCheckWorker(self.config.update.repo, APP_VERSION)
        worker.finished_check.connect(
            lambda resultado, m=manual: self._on_update_result(resultado, m)
        )
        self.statusBar().showMessage("Buscando actualizaciones...")
        self._update_worker = worker
        worker.start()

    def _on_update_result(self, resultado: dict, manual: bool):
        if resultado.get("error"):
            if manual:
                QMessageBox.warning(self, "Actualizaciones", resultado["error"])
            self.statusBar().showMessage("No se pudo verificar actualizaciones.", 5000)
            return
        if resultado["disponible"]:
            QMessageBox.information(
                self, "Actualizacion disponible",
                f"Hay una version nueva: v{resultado['version_remota']}\n"
                f"Version instalada: v{APP_VERSION}\n\n"
                "Descarguela desde las releases del proyecto e instale sobre esta version."
            )
            self.statusBar().showMessage(
                f"Actualizacion v{resultado['version_remota']} disponible", 10000
            )
        elif manual:
            QMessageBox.information(
                self, "Actualizaciones",
                f"Ya tiene la version mas reciente (v{APP_VERSION})."
            )
            self.statusBar().showMessage("Sin actualizaciones disponibles.", 5000)

    def closeEvent(self, event):
        """Maneja el cierre de la ventana: detiene hilos y limpia datos temporales."""
        # Esperar a que terminen los hilos de extraccion/lectura de la pestana IA
        self.ai_tab.shutdown()
        # Esperar al hilo de verificacion de actualizaciones si sigue corriendo
        worker = getattr(self, "_update_worker", None)
        if worker is not None and worker.isRunning():
            worker.wait(2000)
        # Limpiar sesion al cerrar
        self.secure_deleter.clean_session()
        logger.info("Aplicacion cerrada. Sesion limpiada.")
        event.accept()
