"""
Recomendaciones por reglas basadas en la validacion.

Complementan la impresion clinica de la IA con sugerencias objetivas
derivadas de cada valor fuera de rango. NO constituyen un diagnostico:
solo orientan al medico tratante en la interpretacion del informe.
"""
import re
from typing import Dict, List

from src.utils.helpers import strip_accents


# Abreviaturas/normalizaciones de tokens (mismas convenciones que la pestana
# numerica y el validador). Valor -> reemplazos (varias palabras separadas por
# espacios).
_SINONIMOS = {
    "ddi": "diametro diastolico",
    "dsi": "diametro sistolico",
    "ppvi": "pared posterior",
    "sivi": "septum",
    "rvdi": "volumen diastolico",
    "rvsi": "volumen sistolico",
    "grad": "gradiente",
    "media": "medio",
    "max": "maximo",
    "vel": "velocidad",
    "insuf": "insuficiencia",
    "diam": "diametro",
    "ind": "indexada",
    "tad": "tapse",
    "mi": "mitral",
    "ao": "aortico",
    "ai": "auricula",
    "vd": "ventriculo derecho",
    "vi": "ventriculo izquierdo",
}


def _tokens(text: str) -> frozenset:
    """Normaliza una etiqueta a un conjunto de tokens comparables."""
    norm = strip_accents(text)
    norm = re.sub(r"\(.*?\)", " ", norm)   # quita unidades entre parentesis
    norm = re.sub(r"[^\w\s]", " ", norm)   # puntos, barras -> espacio
    tokens = set()
    for t in norm.split():
        if t in _SINONIMOS:
            tokens.update(_SINONIMOS[t].split())
        else:
            tokens.add(t)
    return frozenset(t for t in tokens if t)


# Cada regla: (tokens clave, recomendacion si bajo, recomendacion si elevado)
# Las claves son subconjuntos de los tokens del parametro (emparejamiento por
# subconjunto, igual que la pestana numerica).
_RULES = [
    (frozenset({"fevi"}),
     "FEVI reducida: valorar disfunción sistólica del ventrículo izquierdo y "
     "seguimiento ecocardiográfico.",
     "FEVI preservada."),
    (frozenset({"diametro", "diastolico"}),
     None,
     "Diámetro diastólico elevado: valorar dilatación del ventrículo izquierdo."),
    (frozenset({"diametro", "sistolico"}),
     None,
     "Diámetro sistólico elevado: valorar dilatación o disfunción del ventrículo "
     "izquierdo."),
    (frozenset({"pared", "posterior"}),
     None,
     "Grosor de pared posterior elevado: valorar hipertrofia ventricular izquierda."),
    (frozenset({"septum"}),
     None,
     "Septum interventricular engrosado: valorar hipertrofia ventricular izquierda."),
    (frozenset({"masa", "indexada"}),
     None,
     "Índice de masa ventricular elevado: valorar hipertrofia ventricular izquierda."),
    (frozenset({"masa"}),
     None,
     "Masa ventricular elevada: valorar hipertrofia ventricular izquierda."),
    (frozenset({"volumen", "diastolico"}),
     None,
     "Volumen diastólico elevado: valorar dilatación del ventrículo izquierdo."),
    (frozenset({"volumen", "sistolico"}),
     None,
     "Volumen sistólico elevado: valorar dilatación o disfunción del ventrículo "
     "izquierdo."),
    (frozenset({"diametro", "auricula"}),
     None,
     "Aurícula izquierda dilatada: valorar presiones de llenado y fibrilación "
     "auricular."),
    (frozenset({"volumen", "auricula"}),
     None,
     "Volumen auricular elevado: valorar dilatación de la aurícula izquierda."),
    (frozenset({"diametro", "ventriculo", "derecho"}),
     None,
     "Ventrículo derecho dilatado: valorar patología del ventrículo derecho."),
    (frozenset({"tapse"}),
     "TAPSE reducido: valorar función del ventrículo derecho.",
     None),
    (frozenset({"fsr"}),
     "FSR reducido: valorar función sistólica del ventrículo derecho.",
     None),
    (frozenset({"gradiente", "medio", "mitral"}),
     None,
     "Gradiente medio mitral elevado: valorar estenosis mitral."),
    (frozenset({"gradiente", "maximo", "mitral"}),
     None,
     "Gradiente máximo mitral elevado: valorar estenosis mitral."),
    (frozenset({"area", "mitral"}),
     "Área mitral reducida: valorar estenosis mitral.",
     None),
    (frozenset({"gradiente", "medio", "aortico"}),
     None,
     "Gradiente medio aórtico elevado: valorar estenosis aórtica."),
    (frozenset({"gradiente", "maximo", "aortico"}),
     None,
     "Gradiente máximo aórtico elevado: valorar estenosis aórtica."),
    (frozenset({"area", "aortico"}),
     "Área aórtica reducida: valorar estenosis aórtica.",
     None),
    (frozenset({"velocidad", "insuficiencia", "aortico"}),
     None,
     "Velocidad de insuficiencia aórtica elevada: valorar el grado de regurgitación."),
    (frozenset({"psap"}),
     "PSAP bajo: correlacionar clínicamente (puede reflejar baja presión de llenado).",
     "PSAP elevado: valorar hipertensión pulmonar (ajustado por altitud)."),
]


def _match_rule(param_tokens: frozenset):
    """Retorna la primera regla cuyos tokens sean subconjunto del parametro."""
    for tokens, low, high in _RULES:
        if tokens <= param_tokens:
            return low, high
    return None, None


def get_rule_based_recommendations(validation_rows: List[Dict]) -> List[str]:
    """
    Genera recomendaciones objetivas a partir de la tabla de validacion
    (lista de filas con parametro, valor, limite_inf, limite_sup, normal).

    Solo se consideran valores fuera de rango (normal == False). El texto es
    orientativo y no sustituye el criterio del medico.
    """
    recomendaciones = []

    for row in validation_rows:
        if row.get("normal") is not False:
            continue

        tokens = _tokens(row.get("parametro", ""))
        low_msg, high_msg = _match_rule(tokens)
        if not low_msg and not high_msg:
            continue

        valor = row.get("valor")
        limite_inf = row.get("limite_inf")
        # Determinar la direccion del valor anormal
        if low_msg and valor is not None and limite_inf is not None and valor < limite_inf:
            recomendaciones.append(low_msg)
        elif high_msg:
            recomendaciones.append(high_msg)

    # Deduplicar conservando el orden
    vistos = set()
    unicas = []
    for r in recomendaciones:
        if r not in vistos:
            vistos.add(r)
            unicas.append(r)
    return unicas
