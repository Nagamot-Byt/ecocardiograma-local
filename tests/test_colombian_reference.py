"""Tests unitarios para los rangos de referencia colombianos (SCC/LATAM)."""
import pytest
from src.models.colombian_reference import (
    load_colombian_references, COLOMBIAN_RANGES, GUIDE_NAME,
    psap_upper_limit, DEFAULT_ALTITUDE_MASL,
)
from src.models.patient import Sexo


@pytest.fixture
def col_ranges():
    return load_colombian_references()


class TestColombianReferences:
    def test_load_all_params(self, col_ranges):
        assert len(COLOMBIAN_RANGES) == 22
        for sexo in (Sexo.MASCULINO, Sexo.FEMENINO):
            rangos = col_ranges.get_all_ranges(sexo)
            assert len(rangos) == 22

    def test_guide_name(self):
        assert "Colombianas" in GUIDE_NAME

    def test_validar_ddi_hombre_normal(self, col_ranges):
        res = col_ranges.validate_value(Sexo.MASCULINO, "DDI (mm)", 50.0)
        assert res["normal"] is True

    def test_validar_ddi_hombre_alto_colombiano(self, col_ranges):
        # 57 mm es normal en ASE (hasta 58) pero elevado en colombiano (hasta 56)
        res = col_ranges.validate_value(Sexo.MASCULINO, "DDI (mm)", 57.0)
        assert res["normal"] is False
        assert "Elevado" in res["mensaje"]

    def test_validar_psap_altitud(self, col_ranges):
        # Por defecto se usa la altitud de Bogota (2640 msnm), donde el limite
        # superior normal de PSAP sube a ~38 mmHg: 33 es normal.
        res = col_ranges.validate_value(Sexo.MASCULINO, "PSAP (mmHg)", 33.0)
        assert res["normal"] is True
        res = col_ranges.validate_value(Sexo.MASCULINO, "PSAP (mmHg)", 38.0)
        assert res["normal"] is True
        res = col_ranges.validate_value(Sexo.MASCULINO, "PSAP (mmHg)", 42.0)
        assert res["normal"] is False
        assert "Elevado" in res["mensaje"]

    def test_validar_psap_nivel_del_mar(self):
        # A nivel del mar el limite se mantiene en 30 mmHg (33 es elevado)
        ranges = load_colombian_references(altitude_masl=0.0)
        res = ranges.validate_value(Sexo.MASCULINO, "PSAP (mmHg)", 33.0)
        assert res["normal"] is False
        assert "Elevado" in res["mensaje"]

    def test_psap_upper_limit(self):
        assert psap_upper_limit(0.0) == 30.0
        # Bogota: ~30 + 2640/330 = 38.0
        assert psap_upper_limit(DEFAULT_ALTITUDE_MASL) == 38.0
        assert psap_upper_limit(-10) == 30.0  # valores negativos se tratan como 0

    def test_validar_fevi_femenino(self, col_ranges):
        # FEVI 53% es normal en ASE femenino (54) no, es bajo: limite 55 colombiano
        res = col_ranges.validate_value(Sexo.FEMENINO, "FEVI (%)", 53.0)
        assert res["normal"] is False
        assert "Bajo" in res["mensaje"]

    def test_validar_tapse_femenino(self, col_ranges):
        # TAPSE 16 mm es normal colombiano para mujer (>=16)
        res = col_ranges.validate_value(Sexo.FEMENINO, "TAPSE (mm)", 16.0)
        assert res["normal"] is True

    def test_validar_parametro_desconocido(self, col_ranges):
        res = col_ranges.validate_value(Sexo.MASCULINO, "Inexistente", 10.0)
        assert res["normal"] is None
