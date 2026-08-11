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
     "FEVI reducida: valorar disfuncion sistolica del ventriculo izquierdo y "
     "seguimiento ecocardiografico.",
     "FEVI preservada."),
    (frozenset({"diametro", "diastolico"}),
     None,
     "Diametro diastolico elevado: valorar dilatacion del ventriculo izquierdo."),
    (frozenset({"diametro", "sistolico"}),
     None,
     "Diametro sistolico elevado: valorar dilatacion o disfuncion del ventriculo "
     "izquierdo."),
    (frozenset({"pared", "posterior"}),
     None,
     "Grosor de pared posterior elevado: valorar hipertrofia ventricular izquierda."),
    (frozenset({"septum"}),
     None,
     "Septum interventricular engrosado: valorar hipertrofia ventricular izquierda."),
    (frozenset({"masa", "indexada"}),
     None,
     "Indice de masa ventricular elevado: valorar hipertrofia ventricular izquierda."),
    (frozenset({"masa"}),
     None,
     "Masa ventricular elevada: valorar hipertrofia ventricular izquierda."),
    (frozenset({"volumen", "diastolico"}),
     None,
     "Volumen diastolico elevado: valorar dilatacion del ventriculo izquierdo."),
    (frozenset({"volumen", "sistolico"}),
     None,
     "Volumen sistolico elevado: valorar dilatacion o disfuncion del ventriculo "
     "izquierdo."),
    (frozenset({"diametro", "auricula"}),
     None,
     "Auricula izquierda dilatada: valorar presiones de llenado y fibrilacion "
     "auricular."),
    (frozenset({"volumen", "auricula"}),
     None,
     "Volumen auricular elevado: valorar dilatacion de la auricula izquierda."),
    (frozenset({"diametro", "ventriculo", "derecho"}),
     None,
     "Ventriculo derecho dilatado: valorar patologia del ventriculo derecho."),
    (frozenset({"tapse"}),
     "TAPSE reducido: valorar funcion del ventriculo derecho.",
     None),
    (frozenset({"fsr"}),
     "FSR reducido: valorar funcion sistolica del ventriculo derecho.",
     None),
    (frozenset({"gradiente", "medio", "mitral"}),
     None,
     "Gradiente medio mitral elevado: valorar estenosis mitral."),
    (frozenset({"gradiente", "maximo", "mitral"}),
     None,
     "Gradiente maximo mitral elevado: valorar estenosis mitral."),
    (frozenset({"area", "mitral"}),
     "Area mitral reducida: valorar estenosis mitral.",
     None),
    (frozenset({"gradiente", "medio", "aortico"}),
     None,
     "Gradiente medio aortico elevado: valorar estenosis aortica."),
    (frozenset({"gradiente", "maximo", "aortico"}),
     None,
     "Gradiente maximo aortico elevado: valorar estenosis aortica."),
    (frozenset({"area", "aortico"}),
     "Area aortica reducida: valorar estenosis aortica.",
     None),
    (frozenset({"velocidad", "insuficiencia", "aortico"}),
     None,
     "Velocidad de insuficiencia aortica elevada: valorar el grado de regurgitacion."),
    (frozenset({"psap"}),
     "PSAP bajo: correlacionar clinicamente (puede reflejar baja presion de llenado).",
     "PSAP elevado: valorar hipertension pulmonar (ajustado por altitud)."),
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
