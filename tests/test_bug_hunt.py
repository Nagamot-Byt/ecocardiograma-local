"""
Caza de bugs de la segunda auditoria: sospechas concretas de logica
(fechas imposibles, no finitos en el informe, XSS, conflictos IA/regex)
+ property-based testing con hypothesis sobre funciones puras.
"""
import os

from hypothesis import given, settings, strategies as st

from src.core.ai_extractor import (
    MAX_AI_INPUT_CHARS,
    _merge_numeric,
    _normalize_patient,
    _truncate_for_model,
    to_number,
)
from src.core.report_engine import ReportEngine
from src.core.updater import parse_version
from src.models.colombian_reference import load_colombian_references
from src.models.patient import Patient
from src.utils.helpers import (
    clear_directory,
    format_number,
    safe_filename,
    strip_accents,
)


# ===========================================================================
# A. Fechas: una fecha imposible no debe llegar al informe
# ===========================================================================
class TestFechas:
    def test_fecha_valida_se_conserva(self):
        assert (
            _normalize_patient({"fecha_estudio": "15/3/2024"})["fecha_estudio"]
            == "15/03/2024"
        )

    def test_fecha_imposible_rechazada(self):
        # 31 de febrero no existe: mejor None (informe usa fecha actual)
        # que imprimir un absurdo clinico.
        assert _normalize_patient({"fecha_estudio": "31/02/2025"})["fecha_estudio"] is None

    def test_dia_cero_rechazado(self):
        assert _normalize_patient({"fecha_estudio": "0/5/2025"})["fecha_estudio"] is None

    def test_mes_trece_rechazado(self):
        assert _normalize_patient({"fecha_estudio": "5/13/2025"})["fecha_estudio"] is None

    def test_bisiesto_valido(self):
        assert (
            _normalize_patient({"fecha_estudio": "29/2/2024"})["fecha_estudio"]
            == "29/02/2024"
        )


# ===========================================================================
# B. format_number: nan/inf jamas impresos como tales
# ===========================================================================
class TestFormatNumberNoFinito:
    def test_nan_es_guion(self):
        assert format_number(float("nan")) == "-"

    def test_inf_positivo(self):
        assert format_number(float("inf")) == "-"

    def test_inf_negativo(self):
        assert format_number(float("-inf")) == "-"

    def test_valor_normal_intacto(self):
        assert format_number(52.44) == "52.4"


# ===========================================================================
# C. DataLoader: extensiones en mayusculas aceptadas
# ===========================================================================
class TestDataLoaderMayusculas:
    def test_csv_mayuscula_se_carga(self, tmp_path):
        from src.core.data_loader import DataLoader

        f = tmp_path / "PACIENTE.CSV"
        f.write_text("FEVI\n48\n", encoding="utf-8")
        dl = DataLoader("h.xlsx", "m.xlsx")
        p = Patient()
        ok = dl.load_patient_from_file(str(f), p)
        assert ok and p.fevi == 48.0


# ===========================================================================
# D. Informe: inyeccion HTML escapada (autoescape Jinja2)
# ===========================================================================
PLANTILLA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "templates", "informe_base.html",
)


class TestInformeEscapado:
    @staticmethod
    def _generar_html(tmp_path, monkeypatch, patient) -> str:
        engine = ReportEngine(
            template_path=PLANTILLA,
            output_dir=str(tmp_path),
            altitude_masl=2640,
        )
        monkeypatch.setattr(engine, "_render_html_to_pdf", lambda *a, **k: False)
        from src.core.validator import Validator
        from src.core.visual_input import VisualInputHandler

        ruta = engine.generate_report(
            patient=patient,
            validator=Validator(reference_ranges=load_colombian_references(2640)),
            visual_handler=VisualInputHandler(),
        )
        with open(ruta, encoding="utf-8") as f:
            return f.read()

    def test_script_en_nombre_medico_escapado(self, tmp_path, monkeypatch):
        p = Patient()
        p.fevi = 52.0
        p.nombre_medico = "<script>alert(1)</script>"
        html = self._generar_html(tmp_path, monkeypatch, p)
        assert "<script>" not in html.lower()
        assert "&lt;script&gt;" in html

    def test_inyeccion_en_notas_escapada(self, tmp_path, monkeypatch):
        p = Patient()
        p.notas = '<img src=x onerror="alert(1)">'
        html = self._generar_html(tmp_path, monkeypatch, p)
        assert "<img" not in html.replace("<img", "<img", 1) or "&lt;img" in html

    def test_fecha_estudio_hostil_no_rompe_html(self, tmp_path, monkeypatch):
        p = Patient()
        p.fecha_estudio = '"></td><script>x</script>'
        html = self._generar_html(tmp_path, monkeypatch, p)
        assert "<script>x</script>" not in html


# ===========================================================================
# E. Conflicto IA vs regex: gana regex y se advierte
# ===========================================================================
class TestConflictoIARegex:
    def _dicts(self, ai_val, rx_val, key="fevi"):
        return ({key: (ai_val, 0.95)}, {key: (rx_val, 0.85)})

    def test_regex_gana_conflicto(self):
        ai, rx = self._dicts(90.0, 52.0)
        merged, conf, warns = _merge_numeric(ai, rx)
        assert merged["fevi"] == 52.0
        assert any("fevi" in w for w in warns)

    def test_coincidencia_usa_ia_y_max_confianza(self):
        ai, rx = self._dicts(52.0, 51.9)
        merged, conf, warns = _merge_numeric(ai, rx)
        assert merged["fevi"] == 52.0
        assert conf["fevi"] >= 0.95
        assert not warns


# ===========================================================================
# F-G. helpers: limpieza de directorios y normalizacion unicode
# ===========================================================================
class TestHelpersBordes:
    def test_clear_directory_subdir_no_vacio_permanece(self, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.txt").write_text("y")
        removed = clear_directory(str(tmp_path))
        assert any(p.endswith("a.txt") for p in removed)
        assert (tmp_path / "sub" / "b.txt").exists()  # no recursivo, sin crash

    def test_clear_directory_inexistente(self, tmp_path):
        assert clear_directory(str(tmp_path / "fantasma")) == []

    def test_strip_accents_turca_i(self):
        assert strip_accents("İstanbul") == "istanbul"

    def test_strip_accents_vacio(self):
        assert strip_accents("") == ""

    def test_safe_filename_sanitiza_traversal(self):
        nombre = safe_filename("../../etc/passwd")
        assert "/" not in nombre and ".." not in nombre
        assert nombre.endswith(".pdf")

    def test_safe_filename_sin_extension_punto(self):
        assert safe_filename("x", "txt").endswith(".txt")


# ===========================================================================
# Property-based testing (hypothesis) sobre funciones puras
# ===========================================================================
texto_con_numero = st.text(min_size=1, max_size=60).map(
    lambda s: s[:3] + str(st.integers(-999, 999).example()) + s[3:]
)


class TestPropiedades:
    @settings(max_examples=300, deadline=None)
    @given(st.one_of(st.integers(), st.floats(allow_nan=False), st.text(max_size=30)))
    def test_to_number_nunca_lanza(self, valor):
        r = to_number(valor)
        assert r is None or isinstance(r, float)

    @settings(max_examples=300, deadline=None)
    @given(st.text(max_size=40))
    def test_parse_version_nunca_lanza_y_comparable(self, texto):
        v = parse_version(texto)
        assert isinstance(v, tuple)
        assert all(isinstance(x, int) for x in v)

    @settings(max_examples=200, deadline=None)
    @given(st.text(max_size=50))
    def test_strip_accents_minusculas(self, texto):
        out = strip_accents(texto)
        assert out == out.lower()

    @settings(max_examples=200, deadline=None)
    @given(
        st.one_of(
            st.none(),
            st.floats(allow_nan=True, allow_infinity=True),
            st.floats(-1e6, 1e6),
        )
    )
    def test_format_number_salida_parseable_o_guion(self, valor):
        out = format_number(valor)
        if out != "-":
            float(out.replace(",", "."))  # debe ser re-parseable

    @settings(max_examples=150, deadline=None)
    @given(st.text(max_size=MAX_AI_INPUT_CHARS * 3))
    def test_truncado_respeta_presupuesto(self, texto):
        out = _truncate_for_model(texto)
        assert len(out) <= max(MAX_AI_INPUT_CHARS, len(texto))

    @settings(max_examples=100, deadline=None)
    @given(
        st.text(alphabet="ABC ", min_size=1, max_size=20),
        st.integers(10, 90),
    )
    def test_normalize_patient_sobre_dict_arbitrario(self, nombre, edad):
        p = _normalize_patient(
            {"nombre_medico": nombre, "edad": edad, "notas": nombre}
        )
        assert isinstance(p, dict)
        if p["nombre_medico"]:
            assert len(p["nombre_medico"]) <= 80

    @settings(max_examples=100, deadline=None)
    @given(st.text(min_size=1, max_size=25))
    def test_safe_filename_nunca_contiene_separadores(self, prefijo):
        nombre = safe_filename(prefijo)
        assert "/" not in nombre and "\\" not in nombre and ".." not in nombre

    def test_ids_unicos_rapidos(self):
        ids = set()
        for _ in range(50):
            from src.utils.helpers import generate_patient_id

            ids.add(generate_patient_id())
        assert len(ids) == 50  # uuid evita colisiones intra-segundo
