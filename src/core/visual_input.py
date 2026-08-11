"""
Manejo de campos de hallazgos visuales.
Provee opciones predefinidas y procesa la entrada del usuario.
"""
from typing import Dict, List
from src.models.patient import Patient
from src.utils.logger import setup_logger

logger = setup_logger()


# Opciones predefinidas para cada campo visual
OPCIONES_INSUFICIENCIA = ["No", "Leve", "Moderada", "Severa", "Grave"]
OPCIONES_DERRAME = ["No", "Minimo", "Moderado", "Severo", "Grave"]
OPCIONES_CONTRACTILIDAD = [
    "Normal",
    "Hipocinetica generalizada",
    "Hipocinetica segmentaria",
    "Acinetica",
    "Discinetica",
]


class VisualInputHandler:
    """Administra los campos de hallazgos visuales del ecocardiograma."""

    def __init__(self):
        self.fields_config = self._build_fields_config()

    def _build_fields_config(self) -> Dict[str, dict]:
        """Define la configuracion de cada campo visual."""
        return {
            "insuficiencia_mitral": {
                "label": "Insuficiencia Mitral",
                "type": "combo",
                "options": OPCIONES_INSUFICIENCIA,
                "default": "No",
            },
            "insuficiencia_aortica": {
                "label": "Insuficiencia Aortica",
                "type": "combo",
                "options": OPCIONES_INSUFICIENCIA,
                "default": "No",
            },
            "insuficiencia_tricuspidea": {
                "label": "Insuficiencia Tricuspidea",
                "type": "combo",
                "options": OPCIONES_INSUFICIENCIA,
                "default": "No",
            },
            "insuficiencia_pulmonar": {
                "label": "Insuficiencia Pulmonar",
                "type": "combo",
                "options": OPCIONES_INSUFICIENCIA,
                "default": "No",
            },
            "derrame_pericardico": {
                "label": "Derrame Pericardico",
                "type": "combo",
                "options": OPCIONES_DERRAME,
                "default": "No",
            },
            "contractilidad": {
                "label": "Contractilidad",
                "type": "combo",
                "options": OPCIONES_CONTRACTILIDAD,
                "default": "Normal",
            },
            "segmentos_afectados": {
                "label": "Segmentos Afectados",
                "type": "text",
                "placeholder": "Ej: anterior, septal apical...",
            },
            "observaciones_visuales": {
                "label": "Observaciones Visuales",
                "type": "text_multiline",
                "placeholder": "Hallazgos adicionales...",
            },
        }

    def get_fields_config(self) -> Dict[str, dict]:
        """Retorna la configuracion de todos los campos visuales."""
        return self.fields_config

    def get_options_for_field(self, field_name: str) -> List[str]:
        """Retorna las opciones disponibles para un campo combo."""
        field = self.fields_config.get(field_name, {})
        return field.get("options", [])

    def save_to_patient(self, patient: Patient, values: Dict[str, str]) -> None:
        """Guarda los valores visuales en el objeto Patient."""
        for field_name, value in values.items():
            if hasattr(patient, field_name):
                setattr(patient, field_name, str(value).strip())

        logger.info("Hallazgos visuales guardados en el paciente")

    def load_from_patient(self, patient: Patient) -> Dict[str, str]:
        """Carga los valores visuales desde el objeto Patient."""
        values = {}
        for field_name in self.fields_config:
            values[field_name] = getattr(patient, field_name, "")
        return values

    def get_summary(self, patient: Patient) -> List[str]:
        """Retorna un resumen de hallazgos visuales relevantes."""
        visual = patient.get_visual_fields()
        relevantes = []

        for nombre, valor in visual.items():
            if valor and valor.lower() != "no" and valor.lower() != "normal":
                relevantes.append(f"  - {nombre}: {valor}")

        if not relevantes:
            relevantes.append("  Sin hallazgos visuales significativos.")

        return relevantes
