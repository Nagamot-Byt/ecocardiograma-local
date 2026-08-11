"""Tests para el emparejamiento campo<->resultado de validacion en la pestana numerica."""

from src.gui.numeric_tab import NumericTab


def _instance():
    # No se requiere un QWidget real para probar la logica de emparejamiento
    return NumericTab.__new__(NumericTab)


LABELS = [
    "DDI (mm)", "DSI (mm)", "PPVI (mm)", "SIVI (mm)", "Masa VI (g)",
    "Masa VI ind. (g/m2)", "RVDI (ml)", "RVSI (ml)", "FEVI (%)",
    "Diametro AI (mm)", "Volumen AI ind. (ml/m2)", "Diametro VD (mm)",
    "TAPSE (mm)", "FSR (%)", "Grad. medio MI (mmHg)", "Grad. max MI (mmHg)",
    "Area MI (cm2)", "Grad. medio AO (mmHg)", "Grad. max AO (mmHg)",
    "Area AO (cm2)", "Vel. insuf. AO (m/s)", "PSAP (mmHg)",
]

ATTRS = [
    "ddi", "dsi", "ppvi", "sivi", "masa_vi", "masa_vi_ind", "rvdi", "rvsi",
    "fevi", "diametro_ai", "volumen_ai", "diametro_vd", "tad", "fsr",
    "gradiente_media_mi", "gradiente_max_mi", "area_mi",
    "gradiente_media_ao", "gradiente_max_ao", "area_ao",
    "velocidad_insuf_ao", "psap",
]


class TestAttrMatchesParam:
    def test_todos_los_campos_encuentran_resultado(self):
        nt = _instance()
        results = {label: {"normal": True, "mensaje": "x"} for label in LABELS}
        for attr in ATTRS:
            assert nt._find_validation_result(attr, results) is not None, attr

    def test_gradiente_medio_mi(self):
        # Labels abreviados ("Grad." / "medio") deben matchear el attr completo
        nt = _instance()
        results = {label: {"normal": False, "mensaje": "x"} for label in LABELS}
        for attr in ["gradiente_media_mi", "gradiente_max_mi",
                     "gradiente_media_ao", "gradiente_max_ao",
                     "velocidad_insuf_ao"]:
            assert nt._find_validation_result(attr, results)["normal"] is False

    def test_masa_vi_no_colisiona_con_masa_vi_indexada(self):
        nt = _instance()
        results = {
            "Masa VI (g)": {"normal": True, "mensaje": "a"},
            "Masa VI ind. (g/m2)": {"normal": False, "mensaje": "b"},
        }
        # masa_vi debe matchear "Masa VI (g)" (normal), no la version indexada
        assert nt._find_validation_result("masa_vi", results)["normal"] is True
        assert nt._find_validation_result("masa_vi_ind", results)["normal"] is False

    def test_tad_matchea_tapse(self):
        nt = _instance()
        results = {"TAPSE (mm)": {"normal": False, "mensaje": "x"}}
        assert nt._find_validation_result("tad", results)["normal"] is False

    def test_sin_resultado_devuelve_none(self):
        nt = _instance()
        assert nt._find_validation_result("fevi", {}) is None
