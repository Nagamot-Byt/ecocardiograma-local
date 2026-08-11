"""
Evaluacion de la exactitud de la extraccion contra casos golden.

Mide, por campo numerico: aciertos (match dentro de tolerancia), cobertura
(cuantos de los esperados se extrajeron) y MAE (error absoluto medio) entre
el valor esperado y el extraido. Tambien reporta falsos positivos (parametros
extraidos que no estaban en el caso de referencia).

El runner oficial esta en scripts/evaluate_extraction.py; este modulo contiene
la logica reutilizable y testeable.
"""
from dataclasses import dataclass, field
from typing import Dict, List

from src.core.ai_extractor import _values_close, extract_from_text

# Tolerancia para considerar un valor extraido como correcto (misma que la
# aplicacion usa al fusionar resultados de IA y regex).
TOLERANCIA_RELATIVA = 0.05
TOLERANCIA_ABS = 0.5

DEFAULT_BASE_URL = "http://localhost:11434"


@dataclass
class CasoResultado:
    """Resultado de la evaluacion de un caso individual."""
    id: str
    nombre: str = ""
    params_ok: int = 0
    total_esperados: int = 0
    faltantes: List[str] = field(default_factory=list)
    errores: List[str] = field(default_factory=list)
    falsos_positivos: List[str] = field(default_factory=list)
    extraido: Dict[str, float] = field(default_factory=dict)

    @property
    def exactitud(self) -> float:
        return (self.params_ok / self.total_esperados) if self.total_esperados else 1.0


def _coinciden(a: float, b: float) -> bool:
    return a is not None and b is not None and _values_close(
        a, b, TOLERANCIA_RELATIVA, TOLERANCIA_ABS
    )


def evaluar_caso(caso: dict, use_ai: bool = False,
                 base_url: str = DEFAULT_BASE_URL) -> CasoResultado:
    """Extrae un caso (texto + esperado) y lo compara con lo extraido."""
    resultado = extract_from_text(
        caso.get("texto", ""), use_ai=use_ai, base_url=base_url
    )
    extraido = resultado.numeric_params
    esperado = caso.get("esperado", {})

    cr = CasoResultado(
        id=caso.get("id", "?"),
        nombre=caso.get("nombre", ""),
        total_esperados=len(esperado),
        extraido=dict(extraido),
    )
    for clave, val_esp in esperado.items():
        val_ext = extraido.get(clave)
        if val_ext is None:
            cr.faltantes.append(clave)
        elif _coinciden(val_ext, float(val_esp)):
            cr.params_ok += 1
        else:
            cr.errores.append(f"{clave}: esperado {val_esp} != extraido {val_ext}")

    cr.falsos_positivos = sorted(k for k in extraido if k not in esperado)
    return cr


def evaluar_casos(casos: List[dict], use_ai: bool = False,
                  base_url: str = DEFAULT_BASE_URL) -> dict:
    """Evalua una lista de casos y agrega metricas globales y por campo."""
    por_caso = [evaluar_caso(c, use_ai=use_ai, base_url=base_url) for c in casos]

    total_esperados = sum(c.total_esperados for c in por_caso)
    total_aciertos = sum(c.params_ok for c in por_caso)
    total_faltantes = sum(len(c.faltantes) for c in por_caso)

    por_campo: Dict[str, dict] = {}
    errores_por_campo: Dict[str, List[float]] = {}
    for caso, cr in zip(casos, por_caso):
        for clave, val_esp in caso.get("esperado", {}).items():
            info = por_campo.setdefault(clave, {"esperados": 0, "aciertos": 0})
            info["esperados"] += 1
            val_ext = cr.extraido.get(clave)
            if val_ext is not None and _coinciden(val_ext, float(val_esp)):
                info["aciertos"] += 1
            if val_ext is not None:
                errores_por_campo.setdefault(clave, []).append(abs(val_ext - float(val_esp)))

    for clave, info in por_campo.items():
        errores = errores_por_campo.get(clave, [])
        info["exactitud"] = (info["aciertos"] / info["esperados"]) if info["esperados"] else 0.0
        info["mae"] = (sum(errores) / len(errores)) if errores else None

    return {
        "total_casos": len(casos),
        "use_ai": use_ai,
        "total_parametros": total_esperados,
        "exactitud_global": (total_aciertos / total_esperados) if total_esperados else 1.0,
        "cobertura_global": (
            1.0 - (total_faltantes / total_esperados)
        ) if total_esperados else 1.0,
        "por_campo": por_campo,
        "por_caso": [
            {
                "id": c.id,
                "nombre": c.nombre,
                "exactitud": c.exactitud,
                "params_ok": c.params_ok,
                "total_esperados": c.total_esperados,
                "faltantes": c.faltantes,
                "errores": c.errores,
                "falsos_positivos": c.falsos_positivos,
            }
            for c in por_caso
        ],
    }


def cargar_casos(directorio: str) -> List[dict]:
    """Carga todos los casos golden (*.json) de un directorio, ordenados por id."""
    import json
    from pathlib import Path

    casos = []
    for path in sorted(Path(directorio).glob("*.json")):
        with open(path, encoding="utf-8") as f:
            casos.append(json.load(f))
    return casos
