"""
Vista previa del informe.
Muestra el informe generado (HTML) antes de exportar como PDF.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox,
    QTextBrowser, QTabWidget, QCheckBox,
)
from PyQt6.QtCore import pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices
import os
from src.utils.logger import setup_logger

logger = setup_logger()


class ReportPreview(QWidget):
    """Vista previa del informe ecocardiografico antes de la exportacion."""

    export_requested = pyqtSignal(str)  # Emitido con la ruta del PDF generado

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pdf_path = None
        self._html_path = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()

        self.btn_generar = QPushButton("Generar Informe")
        self.btn_generar.setStyleSheet(
            "QPushButton { background-color: #1a5276; color: white; "
            "padding: 8px 20px; font-weight: bold; border-radius: 4px; }"
            "QPushButton:hover { background-color: #2471a3; }"
        )
        toolbar.addWidget(self.btn_generar)

        self.btn_exportar_pdf = QPushButton("Exportar PDF")
        self.btn_exportar_pdf.setEnabled(False)
        self.btn_exportar_pdf.setStyleSheet(
            "QPushButton { background-color: #27ae60; color: white; "
            "padding: 8px 20px; font-weight: bold; border-radius: 4px; }"
            "QPushButton:hover { background-color: #2ecc71; }"
        )
        toolbar.addWidget(self.btn_exportar_pdf)

        self.btn_abrir = QPushButton("Abrir Archivo")
        self.btn_abrir.setEnabled(False)
        toolbar.addWidget(self.btn_abrir)

        self.btn_guardar_como = QPushButton("Guardar Como...")
        self.btn_guardar_como.setEnabled(False)
        toolbar.addWidget(self.btn_guardar_como)

        toolbar.addStretch()

        # Confirmacion de responsabilidad medica: habilita el boton Generar
        self.chk_disclaimer = QCheckBox(
            "Confirmo que la interpretacion clinica corresponde al medico tratante"
        )
        self.chk_disclaimer.setToolTip(
            "Debe marcarse para poder generar el informe."
        )
        self.chk_disclaimer.toggled.connect(self._on_disclaimer_toggled)
        toolbar.addWidget(self.chk_disclaimer)

        self.lbl_estado = QLabel("Listo para generar informe")
        self.lbl_estado.setStyleSheet("color: #555; font-style: italic;")
        toolbar.addWidget(self.lbl_estado)

        layout.addLayout(toolbar)

        # Tabs para vista previa
        self.tabs = QTabWidget()

        # Vista HTML
        self.browser_html = QTextBrowser()
        self.browser_html.setOpenExternalLinks(False)
        self.tabs.addTab(self.browser_html, "Vista Previa HTML")

        # Resumen de texto
        self.browser_resumen = QTextBrowser()
        self.browser_resumen.setOpenExternalLinks(False)
        self.tabs.addTab(self.browser_resumen, "Resumen Texto")

        layout.addWidget(self.tabs)

    def set_generar_callback(self, callback):
        """Conecta el boton de generar con el callback externo."""
        self.btn_generar.clicked.connect(callback)

    def init_buttons(self):
        """Inicializa las conexiones de los botones (llamar despues de set_generar_callback)."""
        self.btn_exportar_pdf.clicked.connect(self._on_export_pdf)
        self.btn_abrir.clicked.connect(self._on_open_file)
        self.btn_guardar_como.clicked.connect(self._on_save_as)
        self._on_disclaimer_toggled(self.chk_disclaimer.isChecked())

    def _on_disclaimer_toggled(self, checked: bool):
        """Habilita/deshabilita Generar segun la confirmacion de responsabilidad."""
        self.btn_generar.setEnabled(bool(checked))

    def display_html(self, html_content: str, html_path: str = None):
        """Muestra el contenido HTML en la vista previa."""
        self.browser_html.setHtml(html_content)
        self._html_path = html_path
        self.lbl_estado.setText("Informe generado correctamente")
        self.lbl_estado.setStyleSheet("color: #27ae60; font-weight: bold; font-style: italic;")

    def display_resumen(self, text: str):
        """Muestra el resumen de texto."""
        self.browser_resumen.setPlainText(text)

    def set_pdf_path(self, pdf_path: str):
        """Establece la ruta del PDF generado y habilita botones."""
        self._pdf_path = pdf_path
        self.btn_exportar_pdf.setEnabled(bool(pdf_path))
        self.btn_abrir.setEnabled(bool(pdf_path))
        self.btn_guardar_como.setEnabled(bool(pdf_path))

    def _on_export_pdf(self):
        """Exporta el PDF a la ubicacion elegida por el usuario."""
        if not self._pdf_path or not os.path.exists(self._pdf_path):
            QMessageBox.warning(self, "Error", "No se ha generado el informe PDF.")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Guardar Informe PDF", "",
            "Archivos PDF (*.pdf)"
        )
        if filepath:
            try:
                import shutil
                shutil.copy2(self._pdf_path, filepath)
                QMessageBox.information(
                    self, "Exito",
                    f"Informe exportado correctamente:\n{filepath}"
                )
                self.export_requested.emit(filepath)
            except Exception as e:
                QMessageBox.critical(
                    self, "Error",
                    f"No se pudo exportar el informe:\n{e}"
                )

    def _on_open_file(self):
        """Abre el archivo generado con la aplicacion del sistema."""
        if self._pdf_path and os.path.exists(self._pdf_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._pdf_path))

    def _on_save_as(self):
        """Guardar como (similar a export)."""
        self._on_export_pdf()

    def clear(self):
        """Limpia la vista previa."""
        self.browser_html.clear()
        self.browser_resumen.clear()
        self._pdf_path = None
        self._html_path = None
        self.btn_exportar_pdf.setEnabled(False)
        self.btn_abrir.setEnabled(False)
        self.btn_guardar_como.setEnabled(False)
        self.lbl_estado.setText("Listo para generar informe")
        self.lbl_estado.setStyleSheet("color: #555; font-style: italic;")
