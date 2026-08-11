"""Tests unitarios para Validator."""
import pytest
from src.core.validator import Validator
from src.models.reference_range import ReferenceRanges, ReferenceRange
from src.models.patient import Patient, Sexo


@pytest.fixture
def validator_with_ranges():
    """Crea un validator con rangos de prueba."""
    ranges = ReferenceRanges()
    # Agregar rangos manualmente para pruebas
    ranges._rangos[Sexo.MASCULINO]["DDI (mm)"] = ReferenceRange(
        parametro="DDI (mm)", limite_inferior=42, limite_superior=58, unidad="mm"
    )
    ranges._rangos[Sexo.MASCULINO]["FEVI (%)"] = ReferenceRange(
        parametro="FEVI (%)", limite_inferior=52, limite_superior=72, unidad="%"
    )
    ranges._rangos[Sexo.MASCULINO]["PSAP (mmHg)"] = ReferenceRange(
        parametro="PSAP (mmHg)", limite_inferior=None, limite_superior=35, unidad="mmHg"
    )
    ranges._rangos[Sexo.FEMENINO]["DDI (mm)"] = ReferenceRange(
        parametro="DDI (mm)", limite_inferior=38, limite_superior=52, unidad="mm"
    )
    return Validator(ranges)


class TestValidator:
    def test_validate_patient_normal(self, validator_with_ranges):
        patient = Patient(sexo=Sexo.MASCULINO, ddi=50.0, fevi=60.0, psap=30.0)
        results = validator_with_ranges.validate_patient(patient)

        assert results["DDI (mm)"]["normal"] is True
        assert results["FEVI (%)"]["normal"] is True
        assert results["PSAP (mmHg)"]["normal"] is True

    def test_validate_patient_abnormal(self, validator_with_ranges):
        patient = Patient(sexo=Sexo.MASCULINO, ddi=40.0, fevi=75.0, psap=40.0)
        results = validator_with_ranges.validate_patient(patient)

        assert results["DDI (mm)"]["normal"] is False
        assert results["FEVI (%)"]["normal"] is False
        assert results["PSAP (mmHg)"]["normal"] is False

    def test_validate_patient_femenino(self, validator_with_ranges):
        patient = Patient(sexo=Sexo.FEMENINO, ddi=45.0)
        results = validator_with_ranges.validate_patient(patient)

        assert results["DDI (mm)"]["normal"] is True

    def test_get_summary_all_normal(self, validator_with_ranges):
        patient = Patient(sexo=Sexo.MASCULINO, ddi=50.0, fevi=60.0)
        summary = validator_with_ranges.get_summary(patient)

        assert any("Todos los valores" in s for s in summary)

    def test_get_summary_with_abnormal(self, validator_with_ranges):
        patient = Patient(sexo=Sexo.MASCULINO, ddi=40.0, fevi=75.0)
        summary = validator_with_ranges.get_summary(patient)

        assert len(summary) == 2  # Dos valores fuera de rango

    def test_get_validation_table(self, validator_with_ranges):
        patient = Patient(sexo=Sexo.MASCULINO, ddi=50.0)
        table = validator_with_ranges.get_validation_table(patient)

        assert len(table) == 1
        assert table[0]["parametro"] == "DDI (mm)"
        assert table[0]["valor"] == 50.0
        assert table[0]["limite_inf"] == 42
        assert table[0]["limite_sup"] == 58
