"""
Tests del golden set: validacion y recomendaciones esperadas por caso.

Los casos viven en data/golden_set/cases.json (casos de referencia:
normales y patologicos). Este test convierte cada caso en un Patient,
lo valida contra las referencias SCC/LATAM a la altitud del caso y
compara el resultado exacto con lo esperado.
"""
import json
from pathlib import Path

from src.core.recommendations import get_rule_based_recommendations
from src.core.validator import Validator
from src.models.colombian_reference import load_colombian_references
from src.models.patient import Patient, Sexo

GOLDEN_SET = Path(__file__).resolve().parents[1] / "data" / "golden_set" / "cases.json"


def _cargar_casos():
    with open(GOLDEN_SET, encoding="utf-8") as f:
        return json.load(f)["casos"]


def _build_patient(caso):
    patient = Patient()
    patient.sexo = Sexo.MASCULINO if caso["sexo"] == "M" else Sexo.FEMENINO
    for clave, valor in caso["valores"].items():
        setattr(patient, clave, valor)
    return patient


class TestGoldenSet:
    @staticmethod
    def _validar_caso(caso):
        patient = _build_patient(caso)
        refs = load_colombian_references(caso.get("altitud_msnm", 2640.0))
        validator = Validator(refs)
        resultados = validator.validate_patient(patient)
        anormales = {k for k, v in resultados.items() if v["normal"] is False}
        recomendaciones = get_rule_based_recommendations(
            validator.get_validation_table(patient)
        )
        esperado = caso["esperado"]
        return (
            anormales,
            set(esperado["anormales"]),
            recomendaciones,
            esperado["recomendaciones"],
        )

    def test_casos_coinciden_con_lo_esperado(self):
        for caso in _cargar_casos():
            anormales, anormales_esp, recs, recs_esp = self._validar_caso(caso)
            assert anormales == anormales_esp, (
                f"{caso['id']}: anormales {sorted(anormales)} != {sorted(anormales_esp)}"
            )
            assert recs == recs_esp, (
                f"{caso['id']}: recomendaciones {recs} != {recs_esp}"
            )

    def test_todos_los_casos_generan_recomendaciones_coherentes(self):
        """Cada caso anormal genera al menos una recomendacion y el sano ninguna."""
        for caso in _cargar_casos():
            anormales, _, recs, _ = self._validar_caso(caso)
            if not anormales:
                assert recs == [], f"{caso['id']}: caso sano no debe sugerir nada"
            else:
                assert recs, f"{caso['id']}: caso anormal sin recomendaciones"

    def test_regla_velocidad_insuficiencia_aortica_se_dispara(self):
        """Regresion: el sinonimo 'vel'->'velocidad' permite cubrir G005."""
        caso = next(c for c in _cargar_casos() if c["id"] == "G005")
        _, _, recs, _ = self._validar_caso(caso)
        assert any("Velocidad de insuficiencia aórtica" in r for r in recs)

    def test_ajuste_por_altitud_en_psap(self):
        """G008 (nivel del mar) marca PSAP anormal; G009 (2640 msnm) no."""
        g008 = next(c for c in _cargar_casos() if c["id"] == "G008")
        g009 = next(c for c in _cargar_casos() if c["id"] == "G009")
        anormales_008, *_ = self._validar_caso(g008)
        anormales_009, *_ = self._validar_caso(g009)
        assert "PSAP (mmHg)" in anormales_008
        assert anormales_009 == set()
