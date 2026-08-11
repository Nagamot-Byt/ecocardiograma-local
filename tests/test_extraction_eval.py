"""Tests del runner de exactitud de extraccion (src.core.extraction_eval)."""
from pathlib import Path

from src.core.extraction_eval import (
    cargar_casos,
    evaluar_caso,
    evaluar_casos,
)

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "data" / "golden_extraction"


def _casos_muestra():
    return cargar_casos(str(GOLDEN_DIR))


class TestEvaluacionExtraccion:
    def test_casos_muestra_extraen_el_100_por_ciento(self):
        reporte = evaluar_casos(_casos_muestra(), use_ai=False)
        assert reporte["total_casos"] == 3
        assert reporte["exactitud_global"] == 1.0
        assert reporte["cobertura_global"] == 1.0
        assert all(c["exactitud"] == 1.0 for c in reporte["por_caso"])

    def test_reporte_incluye_metricas_por_campo(self):
        reporte = evaluar_casos(_casos_muestra(), use_ai=False)
        assert "por_campo" in reporte
        assert "fevi" in reporte["por_campo"]
        fevi = reporte["por_campo"]["fevi"]
        assert fevi["esperados"] == 3
        assert fevi["aciertos"] == 3
        assert fevi["mae"] == 0.0

    def test_detecta_valor_incorrecto(self):
        caso = {
            "id": "X",
            "nombre": "FEVI mal esperada",
            "texto": "FEVI: 62 %",
            "esperado": {"fevi": 40},
        }
        res = evaluar_caso(caso, use_ai=False)
        assert res.params_ok == 0
        assert res.total_esperados == 1
        assert res.errores and "fevi" in res.errores[0]

    def test_detecta_parametro_faltante(self):
        caso = {
            "id": "Y",
            "nombre": "Campo ausente en el texto",
            "texto": "FEVI: 62 %",
            "esperado": {"fevi": 62, "masa_vi": 180},
        }
        res = evaluar_caso(caso, use_ai=False)
        assert res.params_ok == 1
        assert res.faltantes == ["masa_vi"]

    def test_tolerancia_absorbe_pequenas_diferencias(self):
        caso = {
            "id": "Z",
            "nombre": "Valor con redondeo",
            "texto": "PSAP: 31 mmHg",
            "esperado": {"psap": 30.9},
        }
        res = evaluar_caso(caso, use_ai=False)
        assert res.params_ok == 1
