"""Tests de las recomendaciones por reglas (src.core.recommendations)."""
from src.core.recommendations import get_rule_based_recommendations


def _fila(parametro, valor, li=None, ls=None, normal=False):
    return {
        "parametro": parametro,
        "valor": valor,
        "limite_inf": li,
        "limite_sup": ls,
        "normal": normal,
    }


class TestRuleBasedRecommendations:
    def test_fevi_bajo_sugiere_disfuncion_sistolica(self):
        filas = [_fila("FEVI (%)", 40.0, li=52.0)]
        recs = get_rule_based_recommendations(filas)
        assert any("FEVI reducida" in r for r in recs)

    def test_psap_alto_sugiere_hipertension_pulmonar(self):
        filas = [_fila("PSAP (mmHg)", 48.0, ls=38.0)]
        recs = get_rule_based_recommendations(filas)
        assert any("hipertensión pulmonar" in r for r in recs)

    def test_area_ao_baja_sugiere_estenosis_aortica(self):
        filas = [_fila("Area AO (cm2)", 1.2, li=2.5)]
        recs = get_rule_based_recommendations(filas)
        assert any("estenosis aórtica" in r for r in recs)

    def test_gradiente_mitral_alto_sugiere_estenosis_mitral(self):
        filas = [_fila("Grad. medio MI (mmHg)", 14.0, ls=5.0)]
        recs = get_rule_based_recommendations(filas)
        assert any("estenosis mitral" in r for r in recs)

    def test_tap_se_bajo_sugiere_funcion_vd(self):
        filas = [_fila("TAPSE (mm)", 14.0, li=17.0)]
        recs = get_rule_based_recommendations(filas)
        assert any("TAPSE reducido" in r for r in recs)

    def test_valores_normales_no_generan_recomendaciones(self):
        filas = [_fila("FEVI (%)", 60.0, li=52.0, normal=True)]
        assert get_rule_based_recommendations(filas) == []

    def test_dedup_evita_repetidos_exactos(self):
        filas = [
            _fila("FEVI (%)", 40.0, li=52.0),
            _fila("FEVI (%)", 39.0, li=52.0),
        ]
        recs = get_rule_based_recommendations(filas)
        assert len(recs) == 1

    def test_valores_sin_regla_no_se_incluyen(self):
        filas = [_fila("Parametro Desconocido XYZ", 10.0, ls=5.0)]
        assert get_rule_based_recommendations(filas) == []
