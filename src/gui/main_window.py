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
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QPropertyAnimation, QEasingCurve, QSettings

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

# Hoja de estilos global
STYLESHEET = """
QMainWindow {
    background-color: #f8f9fa;
}
QFrame#header {
    background: #1a5276;
    padding: 10px;
    border-radius: 6px;
}
QLabel#title {
    color: white;
    font-size: 16pt;
    font-weight: bold;
}
QLabel#version {
    color: #aed6f1;
    font-size: 9pt;
}
QLabel#sexo {
    color: white;
    font-size: 11pt;
}
QLabel#patient_id {
    color: #aed6f1;
    font-size: 9pt;
}
QLabel#live_status {
    font-size: 10pt;
    color: #555;
}
QLabel#estado {
    color: #555;
    font-style: italic;
}
QLabel {
    color: #333;
    font-size: 11pt;
}
QStatusBar {
    font-size: 10pt;
}
QPushButton {
    font-size: 11pt;
    border-radius: 4px;
}
QPushButton:disabled {
    background-color: #b0b7bd;
    color: white;
}
QPushButton#primary:disabled, QPushButton#success:disabled,
QPushButton#warning:disabled, QPushButton#danger:disabled {
    background-color: #b0b7bd;
    color: white;
}
QPushButton#primary {
    background-color: #1a5276;
    color: white;
    padding: 6px 16px;
    font-weight: bold;
}
QPushButton#primary:hover {
    background-color: #2471a3;
}
QPushButton#success {
    background-color: #27ae60;
    color: white;
    padding: 6px 16px;
    font-weight: bold;
}
QPushButton#success:hover {
    background-color: #2ecc71;
}
QPushButton#warning {
    background-color: #f39c12;
    color: white;
    padding: 6px 16px;
    font-weight: bold;
}
QPushButton#danger {
    background-color: #c0392b;
    color: white;
    padding: 6px 16px;
    font-weight: bold;
}
QTabBar::tab {
    padding: 8px 20px;
    font-size: 11pt;
}
QTabBar::tab:selected {
    font-weight: bold;
}
QComboBox {
    padding: 4px 10px;
    font-size: 11pt;
    min-width: 120px;
}
QDoubleSpinBox {
    font-size: 11pt;
    min-width: 120px;
}
"""

# Estilos de focus states del modo claro
FOCUS_STYLESHEET = (
    "QLineEdit:focus { border: 2px solid #1a5276; background-color: #e8f0fe; } "
    "QDoubleSpinBox:focus { border: 2px solid #1a5276; background-color: #e8f0fe; } "
    "QComboBox:focus { border: 2px solid #1a5276; background-color: #e8f0fe; }"
)

# Focus states del modo oscuro: fondo oscuro, nunca el azul claro
FOCUS_DARK_STYLESHEET = (
    "QLineEdit:focus { border: 2px solid #2471a3; background-color: #1e1e1e; } "
    "QDoubleSpinBox:focus { border: 2px solid #2471a3; background-color: #1e1e1e; } "
    "QComboBox:focus { border: 2px solid #2471a3; background-color: #1e1e1e; }"
)

# Capa del modo oscuro: tema general + contenedores. Se concatena DESPUES de
# STYLESHEET, asi que gana en las declaraciones en conflicto de igual
# especificidad. Los colores de marca (#primary, #header...) se conservan.
DARK_STYLESHEET = """
QMainWindow {
    background-color: #2b2b2b;
}
QLabel {
    color: #f0f0f0;
}
QLabel#live_status {
    color: #aaaaaa;
}
QLabel#estado {
    color: #aaaaaa;
}
QPushButton {
    background-color: #3d3d3d;
    color: white;
}
QPushButton:focus {
    border: 2px solid #1a5276;
    background-color: #4a4a4a;
}
QPushButton:disabled,
QPushButton#primary:disabled, QPushButton#success:disabled,
QPushButton#warning:disabled, QPushButton#danger:disabled {
    background-color: #4a4a4a;
    color: #9a9a9a;
}
QCheckBox, QRadioButton {
    color: #f0f0f0;
}
QGroupBox {
    color: #f0f0f0;
    border: 1px solid #4a4a4a;
    margin-top: 12px;
    padding-top: 16px;
}
QGroupBox::title {
    color: #aed6f1;
    subcontrol-origin: margin;
    left: 8px;
    padding: 0px 4px;
}
QMenuBar {
    background-color: #2b2b2b;
    color: #f0f0f0;
}
QMenuBar::item:selected {
    background-color: #1a5276;
}
QMenu {
    background-color: #333333;
    color: #f0f0f0;
    border: 1px solid #4a4a4a;
}
QMenu::item:selected {
    background-color: #1a5276;
}
QMenu::separator {
    height: 1px;
    background: #4a4a4a;
}
QToolTip {
    background-color: #333333;
    color: #f0f0f0;
    border: 1px solid #4a4a4a;
}
QStatusBar {
    color: #f0f0f0;
}
QLineEdit, QTextEdit, QTextBrowser, QPlainTextEdit {
    background-color: #1e1e1e;
    color: #f0f0f0;
    border: 1px solid #4a4a4a;
}
QSpinBox, QDoubleSpinBox {
    background-color: #1e1e1e;
    color: #f0f0f0;
    border: 1px solid #4a4a4a;
    border-radius: 3px;
}
QComboBox {
    background-color: #1e1e1e;
    color: #f0f0f0;
    border: 1px solid #4a4a4a;
    border-radius: 3px;
}
QComboBox QAbstractItemView {
    background-color: #1e1e1e;
    color: #f0f0f0;
    selection-background-color: #1a5276;
    selection-color: white;
}
QTabWidget::pane {
    border: 1px solid #4a4a4a;
    background-color: #2b2b2b;
}
QTabBar::tab {
    background-color: #3d3d3d;
    color: #f0f0f0;
}
QTabBar::tab:selected {
    background-color: #1a5276;
    color: white;
}
QTabBar::tab:!selected {
    color: #c0c0c0;
}
QTableWidget, QTableView, QTreeView, QListView {
    background-color: #1e1e1e;
    color: #f0f0f0;
    gridline-color: #4a4a4a;
    alternate-background-color: #262626;
}
QHeaderView::section {
    background-color: #3d3d3d;
    color: #f0f0f0;
    border: 1px solid #4a4a4a;
    padding: 4px;
}
QAbstractItemView::item:selected {
    background-color: #1a5276;
    color: white;
}
QScrollBar:vertical {
    background-color: #2b2b2b;
    width: 12px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #555555;
    border-radius: 5px;
    min-height: 24px;
}
QScrollBar:horizontal {
    background-color: #2b2b2b;
    height: 12px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background-color: #555555;
    border-radius: 5px;
    min-width: 24px;
}
QScrollBar::add-line, QScrollBar::sub-line,
QScrollBar::add-page, QScrollBar::sub-page {
    background: none;
}
QMessageBox {
    background-color: #2b2b2b;
}
QSplitter::handle {
    background-color: #4a4a4a;
}
"""

class UpdateCheckWorker(QThread):
    """Consulta GitHub Releases en un hilo para no congelar la UI."""

    finished_check = pyqtSignal(dict)

    def __init__(self, repo: str, current_version: str, timeout: float = 4.0):
        super().__init__()
        self.repo = repo
        self.current_version = current_version
        self.timeout = timeout
        self._cancelado = False

    def request_cancel(self):
        """Pide no emitir el resultado (cancelacion cooperativa).

        No interrumpe la peticion en vuelo (urllib no lo permite), pero el
        hilo no emite la senal si la ventana ya empezo a cerrarse. Con el
        timeout corto, la espera de closeEvent cubre toda la vida util del
        hilo y terminate() queda como ultimo recurso inalcanzable.
        """
        self._cancelado = True

    def run(self):
        resultado = check_for_updates(
            current_version=self.current_version,
            repo=self.repo,
            timeout=self.timeout,
        )
        if not self._cancelado:
            self.finished_check.emit(resultado)


def get_guide_name(guide: str) -> str:
    """Nombre legible de la guia de referencia activa."""
    if guide == "ase":
        return "Guías ASE 2023"
    return GUIDE_NAME


class ValidarButton(QPushButton):
    """Boton 'Validar' con transicion animada al entrar/salir el raton.

    La animacion vive en enterEvent/leaveEvent reales de la subclase.
    Antes se parcheaban esos metodos sobre la instancia (btn.enterEvent =
    lambda ...), algo que Qt no invoca de forma fiable y que oculta el
    comportamiento a cualquier test o lector del codigo.
    """

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.anim = QPropertyAnimation(self, b"styleSheet", self)
        self.anim.setDuration(150)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._style_normal = ""
        self._style_hover = ""

    def set_animation_styles(self, normal: str, hover: str) -> None:
        """Define los estilos normal/hover y aplica el normal."""
        self._style_normal = normal
        self._style_hover = hover
        self.setStyleSheet(normal)

    def _fade_to(self, style: str) -> None:
        if not style:
            return
        self.anim.stop()
        self.anim.setStartValue(self.styleSheet())
        self.anim.setEndValue(style)
        self.anim.start()

    def enterEvent(self, event):
        super().enterEvent(event)
        self._fade_to(self._style_hover)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._fade_to(self._style_normal)


class MainWindow(QMainWindow):
    """Ventana principal de la aplicacion Ecocardiograma Local."""

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.patient = Patient()
        self.patient.id = generate_patient_id()
        self.dark_mode = False
        self._show_welcome = True

        # Cargar preferencias de QSettings
        settings = QSettings()
        self.dark_mode = settings.value("dark_mode", False, type=bool)
        
        # Aplicar tema si es oscuro (se aplica al final de _build_ui vía
        # _apply_theme, porque setStyleSheet posterior lo sobrescribiria)

        # Accesos directos de teclado
        self.acceso_nuevo = QAction("Nuevo paciente", self)
        self.acceso_nuevo.setShortcut("Ctrl+N")
        self.acceso_nuevo.triggered.connect(self._on_new_patient)

        self.acceso_cargar = QAction("Cargar datos", self)
        self.acceso_cargar.setShortcut("Ctrl+O")
        self.acceso_cargar.triggered.connect(self._on_load_file)

        self.acceso_validar = QAction("Validar ahora", self)
        self.acceso_validar.setShortcut("F5")
        self.acceso_validar.triggered.connect(self._on_validate)

        self.acceso_tema = QAction("Modo tema", self)
        self.acceso_tema.setShortcut("Ctrl+T")
        self.acceso_tema.triggered.connect(self._on_toggle_theme_shortcut)

        # Estilos de focus (claro/oscuro) aplicados en _apply_theme()

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
        self._apply_theme()
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

        self.act_tema = QAction("Modo Oscuro", self, checkable=True)
        self.act_tema.setChecked(self.dark_mode)
        self.act_tema.setToolTip("Alternar entre modo claro y modo oscuro")
        self.act_tema.toggled.connect(self._on_toggle_theme)
        menu_ayuda.addAction(self.act_tema)

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

        # Header (estilos en STYLESHEET via objectName)
        header = QFrame()
        header.setFrameShape(QFrame.Shape.StyledPanel)
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)

        title_lbl = QLabel("ECOCARDIOGRAMA LOCAL")
        title_lbl.setObjectName("title")
        header_layout.addWidget(title_lbl)

        ver_lbl = QLabel(f"v{APP_VERSION}")
        ver_lbl.setObjectName("version")
        header_layout.addWidget(ver_lbl)

        header_layout.addStretch()

        # Selector de sexo
        sexo_lbl = QLabel("Sexo del Paciente:")
        sexo_lbl.setObjectName("sexo")
        header_layout.addWidget(sexo_lbl)

        self.combo_sexo = QComboBox()
        self.combo_sexo.addItems(["Masculino", "Femenino"])
        self.combo_sexo.setAccessibleName("Sexo del Paciente")
        self.combo_sexo.setAccessibleDescription("Seleccione el sexo del paciente para rangos de validacion")
        self.combo_sexo.setToolTip("Seleccionar sexo del paciente para rangos de validacion")
        header_layout.addWidget(self.combo_sexo)

        # ID del paciente
        id_lbl = QLabel(f"ID: {self.patient.id}")
        id_lbl.setObjectName("patient_id")
        header_layout.addWidget(id_lbl)
        self.lbl_id = id_lbl

        header_layout.addStretch()

        btn_validar = ValidarButton("Validar Datos")
        btn_validar.set_animation_styles(
            "QPushButton { background: #f39c12; color: white; "
            "padding: 6px 16px; font-weight: bold; border-radius: 4px; } "
            "QPushButton:hover { background: #e67e22; } "
            "QPushButton:pressed { background: #d35400; }",
            "QPushButton { background: #e67e22; color: white; "
            "padding: 6px 16px; font-weight: bold; border-radius: 4px; }",
        )
        btn_validar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_validar.setAccessibleName("Validar Datos")
        btn_validar.setAccessibleDescription("Valida los datos actuales contra los rangos de referencia")
        btn_validar.setToolTip("Valida los datos actuales contra los rangos de referencia (F5)")
        # Alias de la animacion (referencia historica usada en tests/UI)
        self.btn_validar_anim = btn_validar.anim

        header_layout.addWidget(btn_validar)
        self.btn_validar = btn_validar

        main_layout.addWidget(header)

        # Tabs principales (estilos de tab en STYLESHEET)
        self.tabs = QTabWidget()

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

        # Orden de tabulacion explicito: cabecera -> contenido
        QWidget.setTabOrder(self.combo_sexo, self.btn_validar)
        QWidget.setTabOrder(self.btn_validar, self.tabs)

        # Status bar
        self.statusBar().showMessage(
            "Listo. Extraiga los datos con IA o ingrese los datos manualmente y valide."
        )

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

    def _apply_theme(self):
        """Aplica la hoja combinada: base + modo oscuro (si aplica) + focus."""
        partes = [STYLESHEET]
        if self.dark_mode:
            partes.append(DARK_STYLESHEET)
            partes.append(FOCUS_DARK_STYLESHEET)
        else:
            partes.append(FOCUS_STYLESHEET)
        self.setStyleSheet(" ".join(partes))
        if hasattr(self, "act_tema"):
            self.act_tema.setText("Modo Claro" if self.dark_mode else "Modo Oscuro")

    def _on_toggle_theme_shortcut(self):
        """Acceso directo Ctrl+T para alternar tema."""
        self.act_tema.setChecked(not self.act_tema.isChecked())

    def _on_toggle_theme(self, checked: bool):
        """Alternar entre modo claro y modo oscuro."""
        self.dark_mode = checked
        settings = QSettings()
        settings.setValue("dark_mode", checked)
        self._apply_theme()

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
            try:
                dest = copy_to_user_input(filepath, self.config.user_input_dir)
            except OSError as e:
                QMessageBox.critical(
                    self, "Error",
                    f"No se pudo copiar el archivo a la sesion:\n{e}"
                )
                logger.error(f"Fallo copiando archivo a user_input: {e}")
                return
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

    def show_welcome_if_first_time(self):
        """Asistente de bienvenida: se muestra SOLO en la primera ejecucion.

        Se invoca desde main.py (nunca desde __init__) para no interferir
        con la creacion de la ventana ni con la suite de tests.
        """
        if not self._show_welcome:
            return
        settings = QSettings()
        if settings.value("onboarding_done", False, type=bool):
            return
        QMessageBox.information(
            self, "Bienvenido - Guia rapida",
            "<b>Como usar la aplicacion (4 pasos):</b>"
            "<ol>"
            "<li>Ingrese los <b>datos numericos</b> "
            "(o pulse 'Datos de prueba' para ver un ejemplo).</li>"
            "<li>Registre los <b>hallazgos visuales</b>.</li>"
            "<li>Opcional: use la pestana <b>IA</b> para extraccion "
            "automatica del informe.</li>"
            "<li><b>Valide</b> los datos y genere el <b>informe PDF</b>.</li>"
            "</ol>"
            "<b>Atajos de teclado:</b> Ctrl+N nuevo paciente · "
            "Ctrl+O cargar datos · F5 validar · Ctrl+T modo oscuro"
        )
        settings.setValue("onboarding_done", True)

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
        """Lanza la consulta de actualizaciones en un hilo (silenciosa o manual).

        Antifallo: si ya hay una verificacion en curso no se lanza otra
        (evita solapamiento y el GC del hilo anterior mientras corre, que
        abortaria con 'QThread: Destroyed while thread is still running').
        """
        worker = getattr(self, "_update_worker", None)
        if worker is not None and worker.isRunning():
            if manual:
                self.statusBar().showMessage(
                    "Ya hay una verificacion de actualizaciones en curso...", 3000
                )
            return
        worker = UpdateCheckWorker(self.config.update.repo, APP_VERSION)
        worker.finished_check.connect(
            lambda resultado, m=manual: self._on_update_result(resultado, m)
        )
        # Limpiar la referencia ANTES de destruir el objeto C++ (orden garantizado
        # por conexion): evita 'wrapped C/C++ object has been deleted' en reconsultas.
        worker.finished.connect(self._on_update_worker_finished)
        worker.finished.connect(worker.deleteLater)
        self.statusBar().showMessage("Buscando actualizaciones...")
        self._update_worker = worker
        worker.start()

    def _on_update_worker_finished(self):
        self._update_worker = None

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
        """Manejo de cierre resiliente: cada etapa antifallo es independiente.

        Ningun fallo aqui debe impedir que las etapas posteriores se ejecuten:
        el borrado seguro es lo ultimo y SIEMPRE se intenta.
        """
        # 1. Detener hilos de extraccion/lectura de la pestana IA
        try:
            self.ai_tab.shutdown()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Advertencia deteniendo hilos de IA al cerrar: {e}")
        # 2. Esperar al hilo de verificacion de actualizaciones si sigue corriendo
        try:
            worker = getattr(self, "_update_worker", None)
            if worker is not None:
                # Cancelacion cooperativa: el hilo no emitira el resultado.
                # (Defensivo con getattr: dobles de test pueden no tenerlo.)
                cancelar = getattr(worker, "request_cancel", None)
                if callable(cancelar):
                    cancelar()
                # Desconectar ANTES de esperar: si la senal 'finished_check'
                # se entregara despues de destruir la ventana, el slot
                # accederia a un widget ya eliminado (RuntimeError de Qt).
                for senal in ("finished_check", "finished"):
                    try:
                        getattr(worker, senal).disconnect()
                    except (TypeError, RuntimeError):
                        pass
                if worker.isRunning():
                    # La peticion HTTP tiene timeout corto: esta espera cubre
                    # toda su vida util en condiciones normales.
                    if not worker.wait(4000):
                        # Ultimo recurso: Qt aborta el proceso si el QThread
                        # sigue corriendo al destruir la ventana; se aborta el
                        # hilo (proceso a punto de salir) antes que dejar crashear.
                        logger.warning(
                            "Hilo de actualizaciones no termino a tiempo; "
                            "se aborta para evitar el cierre inseguro de Qt."
                        )
                        worker.terminate()
                        worker.wait(1000)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Advertencia esperando hilo de actualizaciones: {e}")
        # 3. Limpieza segura de temporales (critica: contiene PHI potencial)
        try:
            self.secure_deleter.clean_session()
            logger.info("Aplicacion cerrada. Sesion limpiada.")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Limpieza de sesion fallo al cerrar: {e}")
        event.accept()
