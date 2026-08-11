"""
Modelo de datos del paciente.
Almacena toda la informacion del paciente: datos demograficos,
resultados numericos del ecocardiograma y hallazgos visuales.
"""
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from src.models.param_registry import NUMERIC_FIELDS


class Sexo(Enum):
    MASCULINO = "M"
    FEMENINO = "F"


@dataclass
class Patient:
    """Representa un paciente con sus datos y resultados ecocardiograficos."""
    id: str = ""
    sexo: Sexo = Sexo.MASCULINO
    edad: Optional[int] = None

    # --- Geometria ventricular izquierda (VI) ---
    ddi: Optional[float] = None       # Diametro diastolico del VI (mm)
    dsi: Optional[float] = None       # Diametro sistolico del VI (mm)
    ppvi: Optional[float] = None      # Grosor pared posterior VI (mm)
    sivi: Optional[float] = None      # Septum interventricular (mm)
    masa_vi: Optional[float] = None   # Masa del VI (g)
    masa_vi_ind: Optional[float] = None  # Masa del VI indexada (g/m2)
    rvdi: Optional[float] = None      # Volumen diastolico del VI (ml)
    rvsi: Optional[float] = None      # Volumen sistolico del VI (ml)
    fevi: Optional[float] = None      # Fraccion de eyeccion del VI (%)

    # --- Auricula izquierda (AI) ---
    diametro_ai: Optional[float] = None  # Diametro anteroposterior de AI (mm)
    volumen_ai: Optional[float] = None   # Volumen de AI indexado (ml/m2)

    # --- Ventriculo derecho (VD) ---
    diametro_vd: Optional[float] = None  # Diametro basal del VD (mm)
    tad: Optional[float] = None          # TAPSE (mm)
    fsr: Optional[float] = None          # Fasciculo Sistolicio del VD (%)

    # --- Valvulas y flujo ---
    gradiente_media_mi: Optional[float] = None   # Gradiente medio mitral (mmHg)
    gradiente_max_mi: Optional[float] = None     # Gradiente maximo mitral (mmHg)
    area_mi: Optional[float] = None               # Area valvular mitral (cm2)
    gradiente_media_ao: Optional[float] = None   # Gradiente medio aortico (mmHg)
    gradiente_max_ao: Optional[float] = None     # Gradiente maximo aortico (mmHg)
    area_ao: Optional[float] = None               # Area valvular aortica (cm2)
    velocidad_insuf_ao: Optional[float] = None    # Velocidad insuficiencia aortica (m/s)

    # --- Presiones ---
    psap: Optional[float] = None  # Presion sistolica arteria pulmonar (mmHg)

    # --- Hallazgos visuales (no se validan automaticamente) ---
    insuficiencia_mitral: str = ""        # Grado: leve / moderada / severa / no
    insuficiencia_aortica: str = ""       # Grado: leve / moderada / severa / no
    insuficiencia_tricuspidea: str = ""   # Grado: leve / moderada / severa / no
    insuficiencia_pulmonar: str = ""      # Grado: leve / moderada / severa / no
    derrame_pericardico: str = ""         # si / no / minimo / moderado / severo
    contractilidad: str = ""              # normal / hipocinetica / acinetica / discinetica
    segmentos_afectados: str = ""          # Descripcion libre de segmentos
    observaciones_visuales: str = ""       # Texto libre de hallazgos adicionales

    # --- Metadata ---
    nombre_medico: str = ""
    fecha_estudio: str = ""
    notas: str = ""
    impresion_clinica: str = ""  # Generada por la IA local
    recomendaciones: list = field(default_factory=list)

    # --- Trazabilidad de la IA ---
    ia_model: str = ""                 # Modelo de IA usado en la extraccion
    ia_source: str = ""                # Fuente del resultado (ollama / regex / golden)
    ia_confidence: Optional[float] = None  # Confianza media (0-1)

    def get_numeric_fields(self) -> dict:
        """Retorna un diccionario con todos los campos numericos y sus valores."""
        campos = {f["validation_label"]: getattr(self, f["key"]) for f in NUMERIC_FIELDS}
        return {k: v for k, v in campos.items() if v is not None}

    def get_visual_fields(self) -> dict:
        """Retorna un diccionario con los hallazgos visuales."""
        campos = {
            "Insuficiencia Mitral": self.insuficiencia_mitral,
            "Insuficiencia Aortica": self.insuficiencia_aortica,
            "Insuficiencia Tricuspidea": self.insuficiencia_tricuspidea,
            "Insuficiencia Pulmonar": self.insuficiencia_pulmonar,
            "Derrame Pericardico": self.derrame_pericardico,
            "Contractilidad": self.contractilidad,
            "Segmentos Afectados": self.segmentos_afectados,
            "Observaciones Visuales": self.observaciones_visuales,
        }
        return {k: v for k, v in campos.items() if v}
