"""
Pestana de hallazgos visuales.
Formulario con combos y campos de texto para hallazgos no numericos.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QComboBox, QLineEdit, QTextEdit,
    QPushButton,
)
from PyQt6.QtCore import pyqtSignal
from typing import Dict
import re
from src.models.patient import Patient
from src.core.visual_input import VisualInputHandler


class VisualTab(QWidget):
    """Pestana para el ingreso de hallazgos visuales del ecocardiograma."""

    data_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.handler = VisualInputHandler()
        self.combo_map: Dict[str, QComboBox] = {}
        self.text_map: Dict[str, QTextEdit] = {}
        self.line_map: Dict[str, QLineEdit] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        self.btn_limpiar = QPushButton("Limpiar Visual")
        self.btn_limpiar.clicked.connect(self._on_clear)
        toolbar.addWidget(self.btn_limpiar)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Informacion del paciente
        info_group = QGroupBox("Informacion del Paciente")
        info_layout = QFormLayout()

        self.input_nombre = QLineEdit()
        self.input_nombre.setPlaceholderText("Nombre del medico")
        info_layout.addRow("Medico:", self.input_nombre)

        self.input_edad = QLineEdit()
        self.input_edad.setPlaceholderText("Edad (opcional, solo informativa)")
        info_layout.addRow("Edad:", self.input_edad)

        self.input_fecha = QLineEdit()
        self.input_fecha.setPlaceholderText("DD/MM/AAAA")
        info_layout.addRow("Fecha Estudio:", self.input_fecha)

        self.input_notas = QLineEdit()
        self.input_notas.setPlaceholderText("Notas adicionales")
        info_layout.addRow("Notas:", self.input_notas)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Valvulopatias
        valv_group = QGroupBox("Insuficiencias Valvulares")
        valv_layout = QFormLayout()

        campos_valvulares = [
            "insuficiencia_mitral",
            "insuficiencia_aortica",
            "insuficiencia_tricuspidea",
            "insuficiencia_pulmonar",
        ]
        for field_name in campos_valvulares:
            config = self.handler.get_fields_config()[field_name]
            combo = QComboBox()
            combo.addItems(config["options"])
            combo.setCurrentText(config["default"])
            combo.currentTextChanged.connect(lambda: self.data_changed.emit())
            self.combo_map[field_name] = combo
            valv_layout.addRow(config["label"] + ":", combo)

        valv_group.setLayout(valv_layout)
        layout.addWidget(valv_group)

        # Contractilidad y derrame
        contr_group = QGroupBox("Contractilidad y Derrame")
        contr_layout = QFormLayout()

        for field_name in ["derrame_pericardico", "contractilidad"]:
            config = self.handler.get_fields_config()[field_name]
            combo = QComboBox()
            combo.addItems(config["options"])
            combo.setCurrentText(config["default"])
            combo.currentTextChanged.connect(lambda: self.data_changed.emit())
            self.combo_map[field_name] = combo
            contr_layout.addRow(config["label"] + ":", combo)

        # Segmentos afectados
        seg_config = self.handler.get_fields_config()["segmentos_afectados"]
        self.input_segmentos = QLineEdit(seg_config.get("placeholder", ""))
        self.input_segmentos.textChanged.connect(lambda: self.data_changed.emit())
        self.line_map["segmentos_afectados"] = self.input_segmentos
        contr_layout.addRow(seg_config["label"] + ":", self.input_segmentos)

        contr_group.setLayout(contr_layout)
        layout.addWidget(contr_group)

        # Observaciones
        obs_group = QGroupBox("Observaciones Adicionales")
        obs_layout = QVBoxLayout()
        self.text_observaciones = QTextEdit()
        self.text_observaciones.setPlaceholderText(
            "Ingrese hallazgos visuales adicionales..."
        )
        self.text_observaciones.setMaximumHeight(100)
        self.text_observaciones.textChanged.connect(lambda: self.data_changed.emit())
        self.text_map["observaciones_visuales"] = self.text_observaciones
        obs_layout.addWidget(self.text_observaciones)
        obs_group.setLayout(obs_layout)
        layout.addWidget(obs_group)

        layout.addStretch()

    def _on_clear(self):
        """Limpia todos los campos visuales a sus valores por defecto."""
        for field_name, combo in self.combo_map.items():
            config = self.handler.get_fields_config().get(field_name, {})
            default = config.get("default", "No")
            combo.setCurrentText(default)

        for line_edit in self.line_map.values():
            line_edit.clear()

        for text_edit in self.text_map.values():
            text_edit.clear()

        self.input_nombre.clear()
        self.input_edad.clear()
        self.input_fecha.clear()
        self.input_notas.clear()
        self.data_changed.emit()

    def apply_to_patient(self, patient: Patient):
        """Aplica los valores de la interfaz al objeto Patient."""
        values = {}

        for field_name, combo in self.combo_map.items():
            values[field_name] = combo.currentText()

        for field_name, line_edit in self.line_map.items():
            values[field_name] = line_edit.text().strip()

        for field_name, text_edit in self.text_map.items():
            values[field_name] = text_edit.toPlainText().strip()

        self.handler.save_to_patient(patient, values)

        # Campos de informacion
        patient.nombre_medico = self.input_nombre.text().strip()
        texto_edad = self.input_edad.text().strip()
        if texto_edad:
            m = re.search(r"\d{1,3}", texto_edad)
            patient.edad = int(m.group()) if m else None
        else:
            patient.edad = None
        patient.fecha_estudio = self.input_fecha.text().strip()
        patient.notas = self.input_notas.text().strip()

    def populate_from_patient(self, patient: Patient):
        """Llena la interfaz con los datos de un objeto Patient."""
        visual_values = self.handler.load_from_patient(patient)

        for field_name, combo in self.combo_map.items():
            val = visual_values.get(field_name, "No")
            idx = combo.findText(val)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        for field_name, line_edit in self.line_map.items():
            line_edit.setText(visual_values.get(field_name, ""))

        for field_name, text_edit in self.text_map.items():
            text_edit.setPlainText(visual_values.get(field_name, ""))

        self.input_nombre.setText(patient.nombre_medico or "")
        self.input_edad.setText(str(patient.edad) if patient.edad else "")
        self.input_fecha.setText(patient.fecha_estudio or "")
        self.input_notas.setText(patient.notas or "")
