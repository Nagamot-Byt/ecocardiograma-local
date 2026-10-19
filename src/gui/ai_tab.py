"""
Pestana de IA local.
Carga un archivo (PDF/TXT) o texto pegado, extrae los datos con la IA local
(Ollama, < 7B) y permite aplicarlos al informe.
"""
import os

from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog, QTextEdit, QPlainTextEdit,
    QComboBox, QCheckBox, QMessageBox, QSplitter,
)

from src.core.ai_extractor import (
    ExtractionResult, check_ollama, extract_from_text,
    PARAM_SPECS,
)
from src.utils.logger import setup_logger

logger = setup_logger()


class ExtractWorker(QThread):
    """Ejecuta la extraccion en un hilo separado para no congelar la UI."""

    finished_ok = pyqtSignal(object)
    finished_error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, text, use_ai, model, base_url, guide, ai_timeout,
                 auto_start_ollama=True, pull_model=True):
        super().__init__()
        self.text = text
        self.use_ai = use_ai
        self.model = model
        self.base_url = base_url
        self.guide = guide
        self.ai_timeout = ai_timeout
        self.auto_start_ollama = auto_start_ollama
        self.pull_model = pull_model
        self._cancel = False

    def request_cancel(self):
        """Pide al hilo que abandone operaciones largas (p. ej. descarga de modelo)."""
        self._cancel = True

    def _is_cancelled(self) -> bool:
        return self._cancel

    def run(self):
        try:
            result = extract_from_text(
                self.text, use_ai=self.use_ai, model=self.model,
                base_url=self.base_url, guide=self.guide,
                ai_timeout=self.ai_timeout,
                auto_start_ollama=self.auto_start_ollama,
                pull_model=self.pull_model,
                progress_cb=self.progress.emit,
                cancel_cb=self._is_cancelled,
            )
            self.finished_ok.emit(result)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error en hilo de extraccion: {e}")
            self.finished_error.emit(str(e))


class FileLoadWorker(QThread):
    """Lee un archivo (PDF/TXT/imagen con OCR) en segundo plano."""

    loaded = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, filepath, parent=None, max_bytes=None):
        super().__init__(parent)
        self.filepath = filepath
        self.max_bytes = max_bytes  # Unificado con config.max_file_mb

    def run(self):
        try:
            from src.core.ai_extractor import extract_text_from_file
            text = extract_text_from_file(self.filepath, max_bytes=self.max_bytes)
            self.loaded.emit(text)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error leyendo archivo: {e}")
            self.failed.emit(str(e))


class OllamaStatusWorker(QThread):
    """Verifica Ollama fuera del hilo de UI: nunca congela la ventana."""

    checked = pyqtSignal(bool, list)

    def __init__(self, base_url: str, parent=None):
        super().__init__(parent)
        self.base_url = base_url

    def run(self):
        try:
            ok, models = check_ollama(self.base_url, timeout=2.0)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Chequeo de Ollama fallo: {e}")
            ok, models = False, []
        self.checked.emit(ok, models)


class AITab(QWidget):
    """Pestana para extraccion de datos con IA local."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._apply_callback = None
        self._last_result: ExtractionResult | None = None
        self._worker = None
        self._load_worker = None
        self._ollama_worker = None
        self._build_ui()
        # El chequeo de Ollama corre en un hilo: la ventana aparece al instante
        # y ninguna latencia de red local congela la UI.
        QTimer.singleShot(0, self._refresh_ollama_status)

    # ── UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Toolbar superior
        toolbar = QHBoxLayout()
        self.btn_cargar = QPushButton("Cargar PDF / TXT / Imagen")
        self.btn_cargar.clicked.connect(self._on_load_file)
        toolbar.addWidget(self.btn_cargar)

        self.btn_pegar = QPushButton("Pegar Texto")
        self.btn_pegar.clicked.connect(self._on_paste)
        toolbar.addWidget(self.btn_pegar)

        self.btn_limpiar = QPushButton("Limpiar")
        self.btn_limpiar.clicked.connect(self._on_clear)
        toolbar.addWidget(self.btn_limpiar)

        toolbar.addStretch()

        self.lbl_ollama = QLabel("Verificando Ollama...")
        self.lbl_ollama.setStyleSheet("color: #888; font-style: italic;")
        toolbar.addWidget(self.lbl_ollama)
        layout.addLayout(toolbar)

        # Splitter: texto de entrada | resultados
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Panel izquierdo: texto
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("Texto del ecocardiograma (editable):"))
        self.txt_input = QPlainTextEdit()
        self.txt_input.setPlaceholderText(
            "Pegue aqui el texto del informe, o cargue un archivo PDF/TXT/imagen..."
        )
        left_layout.addWidget(self.txt_input)

        options = QHBoxLayout()
        self.chk_use_ai = QCheckBox("Usar IA local (Ollama)")
        # El switch maestro ai.enabled (config.yaml) manda: si desactiva la
        # IA, el checkbox nace apagado y no hay arranque automatico.
        self.chk_use_ai.setChecked(
            bool(self.config.ai.use_ai and self.config.ai.enabled)
        )
        options.addWidget(self.chk_use_ai)

        options.addWidget(QLabel("Modelo:"))
        self.combo_model = QComboBox()
        self.combo_model.setEditable(True)
        self.combo_model.addItem(self.config.ai.model)
        options.addWidget(self.combo_model)
        options.addStretch()
        left_layout.addLayout(options)

        self.btn_extraer = QPushButton("Extraer Datos con IA")
        self.btn_extraer.setObjectName("primary")
        self.btn_extraer.clicked.connect(self._on_extract)
        left_layout.addWidget(self.btn_extraer)

        # Panel derecho: resultados
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_resultado = QLabel("Resultado de la extraccion:")
        right_layout.addWidget(self.lbl_resultado)

        self.txt_resultado = QTextEdit()
        self.txt_resultado.setReadOnly(True)
        right_layout.addWidget(self.txt_resultado, 1)

        self.btn_aplicar = QPushButton("Aplicar al Informe")
        self.btn_aplicar.setEnabled(False)
        self.btn_aplicar.setObjectName("success")
        self.btn_aplicar.clicked.connect(self._on_apply)
        right_layout.addWidget(self.btn_aplicar)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([450, 450])
        layout.addWidget(splitter, 1)

        self.lbl_pista = QLabel(
            "Sugerencia: extraiga los datos, revise el resultado y pulse "
            "'Aplicar al Informe'. Luego valide en la pestaña de datos numericos."
        )
        self.lbl_pista.setStyleSheet("color: #777; font-style: italic;")
        layout.addWidget(self.lbl_pista)

    # ── Acciones de UI ─────────────────────────────────────────────────

    def _refresh_ollama_status(self):
        """Lanza el chequeo asincrono del estado de Ollama (si no hay uno en curso)."""
        worker = self._ollama_worker
        if worker is not None and worker.isRunning():
            return  # Ya hay una consulta en curso; evitar solapamiento
        worker = OllamaStatusWorker(self.config.ai.base_url)
        worker.checked.connect(self._on_ollama_status)
        # Limpiar la referencia ANTES de destruir el objeto C++ (orden garantizado
        # por conexion): evita 'wrapped C/C++ object has been deleted' al reconsultar.
        worker.finished.connect(self._on_ollama_check_finished)
        worker.finished.connect(worker.deleteLater)
        self.lbl_ollama.setText("Verificando Ollama...")
        self.lbl_ollama.setStyleSheet("color: #888; font-style: italic;")
        self._ollama_worker = worker
        worker.start()

    def _on_ollama_check_finished(self):
        self._ollama_worker = None

    def _on_ollama_status(self, ok: bool, models: list):
        """Aplica el resultado del chequeo de Ollama a la UI."""
        if ok:
            # No reordenar el modelo configurado al inicio de la lista
            existing = [self.combo_model.itemText(i) for i in range(self.combo_model.count())]
            for m in models:
                if m not in existing:
                    self.combo_model.addItem(m)
            self.lbl_ollama.setText(f"Ollama conectado - {len(models)} modelo(s)")
            self.lbl_ollama.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self.lbl_ollama.setText(
                "Ollama no responde ahora. Se iniciara automaticamente al "
                "extraer (si esta instalado); si no, se usara por reglas."
            )
            self.lbl_ollama.setStyleSheet("color: #c0392b; font-weight: bold;")

    def _on_load_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Cargar Ecocardiograma", "",
            "PDF (*.pdf);;Imagen (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)"
            ";;Texto (*.txt);;CSV (*.csv);;Todos (*.*)"
        )
        if not filepath:
            return

        # Limite de tamano de archivo (evita OCR/lectura de documentos enormes)
        try:
            size = os.path.getsize(filepath)
        except OSError:
            size = 0
        max_bytes = self.config.max_file_mb * 1024 * 1024
        if size > max_bytes:
            QMessageBox.warning(
                self, "Archivo muy grande",
                f"El archivo supera el limite de {self.config.max_file_mb} MB "
                f"({size / (1024 * 1024):.1f} MB). No se cargara."
            )
            return

        # La lectura (OCR de imagenes, pypdf) corre en segundo plano
        self.btn_cargar.setEnabled(False)
        self.btn_cargar.setText("Leyendo archivo...")
        self._load_worker = FileLoadWorker(
            filepath, max_bytes=self.config.max_file_mb * 1024 * 1024
        )
        self._load_worker.loaded.connect(self._on_file_loaded)
        self._load_worker.failed.connect(self._on_file_load_failed)
        self._load_worker.start()

    def _on_file_loaded(self, text: str):
        self._restore_load_button()
        if not text.strip():
            QMessageBox.warning(
                self, "Sin texto",
                "No se pudo extraer texto del archivo. "
                "Para imagenes se requiere Tesseract OCR instalado; "
                "para PDF escaneados use una imagen o un PDF con texto."
            )
        self.txt_input.setPlainText(text)

    def _on_file_load_failed(self, error: str):
        self._restore_load_button()
        QMessageBox.critical(self, "Error", f"No se pudo leer el archivo:\n{error}")

    def _restore_load_button(self):
        self.btn_cargar.setEnabled(True)
        self.btn_cargar.setText("Cargar PDF / TXT / Imagen")

    def _on_paste(self):
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.txt_input.setPlainText(text)

    def _on_clear(self):
        self.txt_input.clear()
        self.txt_resultado.clear()
        self._last_result = None
        self.btn_aplicar.setEnabled(False)
        self.lbl_resultado.setText("Resultado de la extraccion:")

    def _on_extract(self):
        text = self.txt_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(
                self, "Sin texto",
                "Cargue un archivo o pegue el texto del ecocardiograma."
            )
            return

        self.btn_extraer.setEnabled(False)
        self.btn_extraer.setText("Extrayendo... (puede tardar)")
        self.lbl_resultado.setText("Extrayendo datos...")

        self._worker = ExtractWorker(
            text=text,
            use_ai=self.chk_use_ai.isChecked(),
            model=self.combo_model.currentText().strip() or self.config.ai.model,
            base_url=self.config.ai.base_url,
            guide=self.config.guide,
            ai_timeout=self.config.ai.timeout,
            auto_start_ollama=self.config.ai.auto_start,
            pull_model=self.config.ai.pull_model,
        )
        self._worker.finished_ok.connect(self._on_extract_done)
        self._worker.finished_error.connect(self._on_extract_error)
        self._worker.progress.connect(self.lbl_resultado.setText)
        self._worker.start()

    def _on_extract_done(self, result: ExtractionResult):
        self._last_result = result
        self.btn_extraer.setEnabled(True)
        self.btn_extraer.setText("Extraer Datos con IA")
        self.btn_aplicar.setEnabled(True)

        lines = []
        lines.append(f"Origen: {result.source}  |  Modelo: {result.model}")
        lines.append(f"Confianza media: {result.confidence * 100:.0f}%  |  "
                     f"Tiempo: {result.processing_time:.1f}s")
        lines.append("")

        lines.append("=== PARAMETROS NUMERICOS ===")
        if result.numeric_params:
            for key, value in result.numeric_params.items():
                spec = PARAM_SPECS.get(key, {})
                conf = result.numeric_confidence.get(key, 0)
                lines.append(
                    f"  {spec.get('label', key):<28} {value:>8} {spec.get('unit', ''):<6}"
                    f" (conf {conf:.0%})"
                )
        else:
            lines.append("  (ninguno detectado)")

        lines.append("")
        lines.append("=== HALLAZGOS VISUALES ===")
        for field in ["insuficiencia_mitral", "insuficiencia_aortica",
                      "insuficiencia_tricuspidea", "insuficiencia_pulmonar",
                      "derrame_pericardico", "contractilidad"]:
            lines.append(f"  {field:<28} {result.visual_data.get(field, 'No')}")
        if result.visual_data.get("segmentos_afectados"):
            lines.append(f"  Segmentos: {result.visual_data['segmentos_afectados']}")
        if result.visual_data.get("observaciones_visuales"):
            lines.append(f"  Observaciones: {result.visual_data['observaciones_visuales']}")

        lines.append("")
        lines.append("=== DATOS DEL PACIENTE ===")
        pd = result.patient_data
        sexo = {"M": "Masculino", "F": "Femenino"}.get(pd.get("sexo"), "No detectado")
        lines.append(f"  Sexo: {sexo}")
        lines.append(f"  Edad: {pd.get('edad') or '-'}")
        lines.append(f"  Medico: {pd.get('nombre_medico') or '-'}")
        lines.append(f"  Fecha estudio: {pd.get('fecha_estudio') or '-'}")
        if pd.get("notas"):
            lines.append(f"  Notas: {pd['notas']}")

        if result.clinical_impression:
            lines.append("")
            lines.append("=== IMPRESION CLINICA (IA) ===")
            lines.append(f"  {result.clinical_impression}")

        lines.append("")
        if result.warnings:
            lines.append("=== ADVERTENCIAS ===")
            for w in result.warnings:
                lines.append(f"  - {w}")
        else:
            lines.append("Sin advertencias.")

        self.txt_resultado.setPlainText("\n".join(lines))
        self.lbl_resultado.setText(
            f"Extraccion completada - {len(result.numeric_params)} parametros "
            f"({result.source})"
        )
        # Refrescar el estado de Ollama (modelos disponibles / reconexion)
        self._refresh_ollama_status()

    def _on_extract_error(self, error: str):
        self.btn_extraer.setEnabled(True)
        self.btn_extraer.setText("Extraer Datos con IA")
        self.lbl_resultado.setText("Error durante la extraccion")
        QMessageBox.critical(self, "Error de extraccion", error)

    def _on_apply(self):
        if self._last_result is None:
            return
        if self._apply_callback:
            self._apply_callback(self._last_result)
        else:
            QMessageBox.warning(self, "Aviso", "No hay un informe activo.")

    # ── API para MainWindow ────────────────────────────────────────────

    def set_on_apply(self, callback):
        """Establece el callback que aplica el resultado al informe."""
        self._apply_callback = callback

    def shutdown(self, extract_timeout_ms: int = 20000, load_timeout_ms: int = 5000):
        """Detiene los hilos de trabajo de forma cooperativa al cerrar la app.

        Primero pide la cancelacion (aborta una descarga de modelo en curso) y
        luego espera un tiempo de gracia acotado por hilo: la lectura de
        archivos es rapida (5 s) y la extraccion puede estar generando con el
        modelo (20 s). Si un hilo aun esta activo, se registra una advertencia
        en lugar de destruir el QThread a medias.
        """
        for worker in (self._load_worker, self._worker):
            cancel = getattr(worker, "request_cancel", None)
            if worker is not None and cancel is not None:
                cancel()
        for name, worker, grace in (
            ("carga", self._load_worker, load_timeout_ms),
            ("extraccion", self._worker, extract_timeout_ms),
        ):
            if worker is not None and worker.isRunning():
                if not worker.wait(grace):
                    logger.warning(
                        f"Hilo de {name} sigue trabajando al cerrar la app "
                        "(posible generacion del modelo en curso)."
                    )
        # El chequeo de estado de Ollama es corto: esperar su finalizacion
        ollama_w = self._ollama_worker
        if ollama_w is not None and ollama_w.isRunning():
            ollama_w.wait(3000)
