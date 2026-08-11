"""
Rangos de referencia ecocardiograficos colombianos (SCC/LATAM).

Basados en:
- Sociedad Colombiana de Cardiologia (SCC)
- Guias latinoamericanas de ecocardiografia
- Estudios de referencia de la Clinica Shaio, Fundacion Cardioinfantil y Hospital Militar
- Ajustes por altitud (Bogota ~2,640 msnm afecta PSAP y volumenes)

Los nombres de parametro coinciden con las claves usadas por
Patient.get_numeric_fields() para ser validados sin cambios en el core.
"""
from typing import Dict, Tuple, Optional

from src.models.reference_range import ReferenceRange, ReferenceRanges
from src.models.patient import Sexo

# Cada parametro: nombre_visual -> (limite_inf_H, limite_sup_H, limite_inf_M, limite_sup_M, unidad)
# None indica que no hay limite para ese sexo/lado.
COLOMBIAN_RANGES: Dict[str, Tuple[Optional[float], Optional[float],
                                  Optional[float], Optional[float], str]] = {
    # --- Geometria ventricular izquierda ---
    "DDI (mm)":                (42.0, 56.0, 38.0, 50.0, "mm"),
    "DSI (mm)":                (23.0, 37.0, 21.0, 33.0, "mm"),
    "PPVI (mm)":               (8.0, 10.5, 7.0, 9.5, "mm"),
    "SIVI (mm)":               (8.0, 11.5, 7.0, 10.5, "mm"),
    "Masa VI (g)":             (None, 220.0, None, 155.0, "g"),
    "Masa VI ind. (g/m2)":     (None, 110.0, None, 88.0, "g/m2"),
    # --- Volumenes VI ---
    "RVDI (ml)":               (62.0, 145.0, 46.0, 115.0, "ml"),
    "RVSI (ml)":               (22.0, 58.0, 15.0, 48.0, "ml"),
    "FEVI (%)":                (54.0, 72.0, 55.0, 74.0, "%"),
    # --- Auricula izquierda ---
    "Diametro AI (mm)":        (None, 39.0, None, 37.0, "mm"),
    "Volumen AI ind. (ml/m2)": (None, 32.0, None, 32.0, "ml/m2"),
    # --- Ventriculo derecho ---
    "Diametro VD (mm)":        (None, 41.0, None, 39.0, "mm"),
    "TAPSE (mm)":              (17.0, None, 16.0, None, "mm"),
    "FSR (%)":                 (33.0, None, 33.0, None, "%"),
    # --- Valvula mitral ---
    "Grad. medio MI (mmHg)":   (None, 5.0, None, 5.0, "mmHg"),
    "Grad. max MI (mmHg)":     (None, 10.0, None, 10.0, "mmHg"),
    "Area MI (cm2)":           (4.0, None, 4.0, None, "cm2"),
    # --- Valvula aortica ---
    "Grad. medio AO (mmHg)":   (None, 12.0, None, 12.0, "mmHg"),
    "Grad. max AO (mmHg)":     (None, 20.0, None, 20.0, "mmHg"),
    "Area AO (cm2)":           (3.0, None, 2.5, None, "cm2"),
    "Vel. insuf. AO (m/s)":    (None, 2.5, None, 2.4, "m/s"),
    # --- Presiones ---
    "PSAP (mmHg)":             (None, 30.0, None, 30.0, "mmHg"),
}

GUIDE_NAME = "Guias Colombianas SCC/LATAM"

# Altitud por defecto: Bogota (msnm). La altitud elevada incrementa la presion
# arterial pulmonar fisiologica, por lo que el limite superior de PSAP se ajusta.
DEFAULT_ALTITUDE_MASL = 2640.0


def psap_upper_limit(altitude_masl: float = 0.0, base: float = 30.0) -> float:
    """Limite superior de PSAP (mmHg) ajustado por altitud.

    Aproximacion clinica: ~1 mmHg adicional por cada 330 msnm sobre el nivel
    del mar (referencia base 30 mmHg, guia colombiana).
    """
    try:
        altitude = max(float(altitude_masl), 0.0)
    except (TypeError, ValueError):
        altitude = 0.0
    return round(base + altitude / 330.0, 1)


def load_colombian_references(altitude_masl: float = DEFAULT_ALTITUDE_MASL) -> ReferenceRanges:
    """Construye un ReferenceRanges con los rangos colombianos en memoria.

    Con ``altitude_masl`` > 0 se ajusta el limite superior de PSAP al valor
    fisiologico esperado en esa altitud (ver ``psap_upper_limit``).
    """
    ranges = ReferenceRanges()
    psap_max = psap_upper_limit(altitude_masl)

    for param, (li_h, ls_h, li_m, ls_m, unidad) in COLOMBIAN_RANGES.items():
        if param == "PSAP (mmHg)":
            ls_h = psap_max
            ls_m = psap_max
        ranges._rangos[Sexo.MASCULINO][param] = ReferenceRange(
            parametro=param, limite_inferior=li_h, limite_superior=ls_h, unidad=unidad
        )
        ranges._rangos[Sexo.FEMENINO][param] = ReferenceRange(
            parametro=param, limite_inferior=li_m, limite_superior=ls_m, unidad=unidad
        )

    return ranges
