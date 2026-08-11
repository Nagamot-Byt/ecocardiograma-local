"""
Registro unico de parametros numericos del ecocardiograma.

Es la fuente de verdad para la definicion de los 22 campos numericos:
etiquetas (de pestana y de validacion), unidades, limites plausibles,
decimales y alias para la extraccion por reglas.

Consumidores:
  - ai_extractor.PARAM_SPECS  (extraccion regex/IA)
  - NumericTab.CAMPOS         (formulario editable)
  - Patient.get_numeric_fields (validacion e informes)
"""
from typing import Any, Dict, List, Tuple

NUMERIC_FIELDS: List[Dict[str, Any]] = [
    # key, label, validation_label, unit, min, max, decimals, aliases
    {"key": "ddi", "label": "DDI (Diam. Diast. VI)", "validation_label": "DDI (mm)",
     "unit": "mm", "min": 0, "max": 150, "decimals": 1,
     "aliases": ["ddi", "diastolico vi", "dia diast vi", "dia diastolico vi", "dd vi",
                 "diametro diastolico", "dvd", "lv dd", "lvedd"]},
    {"key": "dsi", "label": "DSI (Diam. Sist. VI)", "validation_label": "DSI (mm)",
     "unit": "mm", "min": 0, "max": 100, "decimals": 1,
     "aliases": ["dsi", "sistolico vi", "dia sist vi", "dia sistolico vi", "ds vi",
                 "diametro sistolico", "dvs", "lv sd", "lvesd"]},
    {"key": "ppvi", "label": "PPVI (Pared Post. VI)", "validation_label": "PPVI (mm)",
     "unit": "mm", "min": 0, "max": 30, "decimals": 1,
     "aliases": ["ppvi", "pared post", "pared posterior", "espesor pared posterior",
                 "grosor pared posterior", "lvpw"]},
    {"key": "sivi", "label": "SIVI (Septum IV)", "validation_label": "SIVI (mm)",
     "unit": "mm", "min": 0, "max": 30, "decimals": 1,
     "aliases": ["sivi", "septum interventricular", "septum", "tabique",
                 "espesor septal", "ivs", "tivs"]},
    {"key": "masa_vi", "label": "Masa VI", "validation_label": "Masa VI (g)",
     "unit": "g", "min": 0, "max": 500, "decimals": 0,
     "aliases": ["masa vi", "masa ventricular", "masa del vi", "masa ventricular izquierda", "lvm"]},
    {"key": "masa_vi_ind", "label": "Masa VI Indexada", "validation_label": "Masa VI ind. (g/m2)",
     "unit": "g/m2", "min": 0, "max": 300, "decimals": 0,
     "aliases": ["masa vi indexada", "masa indexada", "masa vi ind", "lvmi", "g/m2"]},
    {"key": "rvdi", "label": "Volumen Diast. VI", "validation_label": "RVDI (ml)",
     "unit": "ml", "min": 0, "max": 400, "decimals": 0,
     "aliases": ["volumen diastolico", "vol diastolico", "volumen diastolico vi",
                 "vol diast vi", "edv", "lvedv"]},
    {"key": "rvsi", "label": "Volumen Sist. VI", "validation_label": "RVSI (ml)",
     "unit": "ml", "min": 0, "max": 300, "decimals": 0,
     "aliases": ["volumen sistolico", "vol sistolico", "volumen sistolico vi",
                 "vol sist vi", "esv", "lvesv"]},
    {"key": "fevi", "label": "FEVI (Frac. Eyeccion)", "validation_label": "FEVI (%)",
     "unit": "%", "min": 0, "max": 100, "decimals": 1,
     "aliases": ["fevi", "fraccion de eyeccion", "fraccion eyeccion", "fe",
                 "lvef", "eyeccion"]},
    {"key": "diametro_ai", "label": "Diametro AI", "validation_label": "Diametro AI (mm)",
     "unit": "mm", "min": 0, "max": 100, "decimals": 1,
     "aliases": ["diametro ai", "diametro de ai", "auricula izquierda", "atrio izquierdo",
                 "la diametro", "lai", "diametro al"]},
    {"key": "volumen_ai", "label": "Volumen AI Index.", "validation_label": "Volumen AI ind. (ml/m2)",
     "unit": "ml/m2", "min": 0, "max": 100, "decimals": 1,
     "aliases": ["volumen ai", "volumen ai indexado", "volumen de ai", "volumen al",
                 "volumen al indexado", "lai indexado", "la volume", "ml/m2"]},
    {"key": "diametro_vd", "label": "Diametro VD", "validation_label": "Diametro VD (mm)",
     "unit": "mm", "min": 0, "max": 100, "decimals": 1,
     "aliases": ["diametro vd", "diametro del vd", "ventriculo derecho", "rv diametro", "rvd"]},
    {"key": "tad", "label": "TAPSE", "validation_label": "TAPSE (mm)",
     "unit": "mm", "min": 0, "max": 50, "decimals": 1,
     "aliases": ["tapse", "tad"]},
    {"key": "fsr", "label": "FSR (Frac. Sist. RV)", "validation_label": "FSR (%)",
     "unit": "%", "min": 0, "max": 100, "decimals": 1,
     "aliases": ["fsr", "fraccion sistolica vd", "fraccion sistolica del vd", "rv fs"]},
    {"key": "gradiente_media_mi", "label": "Gradiente Medio MI", "validation_label": "Grad. medio MI (mmHg)",
     "unit": "mmHg", "min": 0, "max": 100, "decimals": 1,
     "aliases": ["gradiente medio mitral", "gradiente medio mi", "grad medio mi",
                 "mg mitral", "mean gradient mi"]},
    {"key": "gradiente_max_mi", "label": "Gradiente Maximo MI", "validation_label": "Grad. max MI (mmHg)",
     "unit": "mmHg", "min": 0, "max": 200, "decimals": 1,
     "aliases": ["gradiente maximo mitral", "gradiente maximo mi", "grad max mi",
                 "pg mitral", "peak gradient mi"]},
    {"key": "area_mi", "label": "Area Valvular MI", "validation_label": "Area MI (cm2)",
     "unit": "cm2", "min": 0, "max": 10, "decimals": 2,
     "aliases": ["area mitral", "area valvular mitral", "area mi", "am", "mva"]},
    {"key": "gradiente_media_ao", "label": "Gradiente Medio AO", "validation_label": "Grad. medio AO (mmHg)",
     "unit": "mmHg", "min": 0, "max": 100, "decimals": 1,
     "aliases": ["gradiente medio aortico", "gradiente medio ao", "grad medio ao",
                 "mg aortico", "mean gradient ao"]},
    {"key": "gradiente_max_ao", "label": "Gradiente Maximo AO", "validation_label": "Grad. max AO (mmHg)",
     "unit": "mmHg", "min": 0, "max": 200, "decimals": 1,
     "aliases": ["gradiente maximo aortico", "gradiente maximo ao", "grad max ao",
                 "pg aortico", "peak gradient ao"]},
    {"key": "area_ao", "label": "Area Valvular AO", "validation_label": "Area AO (cm2)",
     "unit": "cm2", "min": 0, "max": 10, "decimals": 2,
     "aliases": ["area aortica", "area valvular aortica", "area ao", "ao", "ava"]},
    {"key": "velocidad_insuf_ao", "label": "Vel. Insuf. AO", "validation_label": "Vel. insuf. AO (m/s)",
     "unit": "m/s", "min": 0, "max": 10, "decimals": 2,
     "aliases": ["velocidad insuficiencia aortica", "velocidad insuf ao",
                 "vel insuf ao", "vmax ao", "ar velocity"]},
    {"key": "psap", "label": "PSAP", "validation_label": "PSAP (mmHg)",
     "unit": "mmHg", "min": 0, "max": 100, "decimals": 1,
     "aliases": ["psap", "presion sistolica pulmonar", "pap",
                 "presion arterial pulmonar", "spap"]},
]


def build_param_specs() -> Dict[str, Dict[str, Any]]:
    """Construye PARAM_SPECS (ai_extractor): clave -> {label, unit, min, max, aliases}."""
    return {
        f["key"]: {
            "label": f["label"],
            "unit": f["unit"],
            "min": f["min"],
            "max": f["max"],
            "aliases": list(f["aliases"]),
        }
        for f in NUMERIC_FIELDS
    }


def build_campos() -> Tuple[Tuple[str, str, str, int, int, int], ...]:
    """Construye CAMPOS (NumericTab): (key, label, unit, min, max, decimals)."""
    return tuple(
        (f["key"], f["label"], f["unit"], f["min"], f["max"], f["decimals"])
        for f in NUMERIC_FIELDS
    )


def get_field(key: str) -> Dict[str, Any]:
    """Retorna la definicion completa de un campo por clave."""
    for f in NUMERIC_FIELDS:
        if f["key"] == key:
            return f
    raise KeyError(f"Parametro no registrado: {key}")


def all_keys() -> Tuple[str, ...]:
    """Retorna las claves de todos los campos, en orden."""
    return tuple(f["key"] for f in NUMERIC_FIELDS)
