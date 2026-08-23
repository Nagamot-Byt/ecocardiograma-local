"""
Bateria adversaria / fuzz de la auditoria final.

Objetivo: romper el sistema con entradas hostiles que la suite regular
no contempla (basura binaria, tipos equivocados, limites exactos,
doble invocacion, recursos ausentes). Cada test documenta el ToT:
que se ataca, como falla mal si no hay blindaje.
"""
import os

import pytest

from src.core.ai_extractor import (
    MAX_AI_INPUT_CHARS,
    _normalize_patient,
    _truncate_for_model,
    extract_from_text,
    extract_text_from_file,
    in_bounds,
    to_number,
)
from src.core.recommendations import get_rule_based_recommendations
from src.core.secure_delete import SecureDeleter, secure_delete_file
from src.core.updater import check_for_updates, parse_version, version_es_mayor
from src.utils.config import load_config
from src.utils.error_guard import set_dialogs_enabled
from src.utils.helpers import copy_to_user_input


# ---------------------------------------------------------------------------
# to_number con basura tipada
# ---------------------------------------------------------------------------
class TestToNumberHostil:
    def test_none(self):
        assert to_number(None) is None

    def test_vacio_y_espacios(self):
        assert to_number("") is None
        assert to_number("   ") is None

    def test_letras_puras(self):
        assert to_number("abc") is None
        assert to_number("FEVI") is None

    def test_digito_embebido_en_basura(self):
        # El regex extrae el primer numero aunque venga sucio
        assert to_number("FEVI: 47%") == 47.0

    def test_nan_no_se_propaga_como_valido(self):
        val = to_number(float("nan"))
        assert val is not None  # isinstance float pasa directo...
        assert val != val  # ...pero sigue siendo NaN (incomparable)

    def test_inf(self):
        assert to_number(float("inf")) == float("inf")

    def test_booleanos(self):
        # bool es int en Python; True->1.0 es aceptable pero debe ser float
        assert to_number(True) == 1.0

    def test_lista_y_dict(self):
        assert to_number([1, 2]) is None or isinstance(to_number([1, 2]), float)
        r = to_number({"a": 1})
        assert r is None or isinstance(r, float)


# ---------------------------------------------------------------------------
# in_bounds con valores no finitos y claves desconocidas
# ---------------------------------------------------------------------------
class TestInBoundsHostil:
    def test_clave_desconocida(self):
        assert in_bounds("no_existe", 5.0) is False

    def test_nan_fuera_de_limites(self):
        assert in_bounds("fevi", float("nan")) is False

    def test_inf_fuera_de_limites(self):
        assert in_bounds("fevi", float("inf")) is False
        assert in_bounds("fevi", float("-inf")) is False


# ---------------------------------------------------------------------------
# _normalize_patient con estructuras rotas
# ---------------------------------------------------------------------------
class TestNormalizePatientHostil:
    def test_dict_vacio(self):
        p = _normalize_patient({})
        assert p["sexo"] is None and p["edad"] is None

    def test_none_devuelve_esqueleto(self):
        p = _normalize_patient(None)
        assert set(p) >= {"sexo", "edad"}

    def test_sexo_variante_con_espacios(self):
        assert _normalize_patient({"sexo": "  masculino "})["sexo"] == "M"

    def test_sexo_entero_no_crashea(self):
        assert _normalize_patient({"sexo": 123})["sexo"] is None

    def test_edad_limite_inferior_rechazada(self):
        assert _normalize_patient({"edad": 9})["edad"] is None

    def test_edad_limite_superior_rechazada(self):
        assert _normalize_patient({"edad": 110})["edad"] is None

    def test_edad_textual(self):
        assert _normalize_patient({"edad": "67 anos"})["edad"] == "67"

    def test_medico_truncado_a_80(self):
        p = _normalize_patient({"nombre_medico": "X" * 500})
        assert len(p["nombre_medico"]) == 80

    def test_campos_con_estructura_rara_no_crashean(self):
        raw = {"sexo": ["M"], "edad": {"a": 1}, "notas": ("tupla",), "fecha_estudio": None}
        p = _normalize_patient(raw)  # solo debe no lanzar
        assert isinstance(p, dict)

    def test_fecha_formatos_sucios(self):
        assert _normalize_patient({"fecha_estudio": "3/7/25"})["fecha_estudio"] == "03/07/2025"
        assert _normalize_patient({"fecha_estudio": "garbage"})["fecha_estudio"] is None


# ---------------------------------------------------------------------------
# extract_text_from_file con archivos hostiles
# ---------------------------------------------------------------------------
class TestExtractArchivoHostil:
    def test_archivo_vacio(self, tmp_path):
        f = tmp_path / "vacio.txt"
        f.write_bytes(b"")
        assert extract_text_from_file(str(f)) == ""

    def test_binario_puro_txt(self, tmp_path):
        f = tmp_path / "bin.txt"
        f.write_bytes(bytes(range(256)) * 10)
        texto = extract_text_from_file(str(f))  # no debe lanzar
        assert isinstance(texto, str)

    def test_latin1_acentos(self, tmp_path):
        f = tmp_path / "lat.txt"
        f.write_bytes("FEVI 52%, derrame m\xednimo".encode("latin-1"))
        assert "mínimo" in extract_text_from_file(str(f))

    def test_max_bytes_superado_lanza_valueerror(self, tmp_path):
        f = tmp_path / "grande.txt"
        f.write_bytes(b"x" * 100)
        with pytest.raises(ValueError):
            extract_text_from_file(str(f), max_bytes=10)

    def test_directorio_en_lugar_de_archivo(self, tmp_path):
        # getsize sobre dir funciona; open fallara -> comportamiento definido
        with pytest.raises(Exception):
            extract_text_from_file(str(tmp_path))

    def test_pdf_truncado_retorna_error_controlado(self, tmp_path):
        from src.core.ai_extractor import extract_from_file

        f = tmp_path / "roto.pdf"
        f.write_bytes(b"%PDF-1.4 truncado a proposito")
        r = extract_from_file(str(f), use_ai=False)
        assert r.source == "error" and r.warnings  # capa alta degrada sin crash

    def test_extension_mayuscula(self, tmp_path):
        f = tmp_path / "DOC.TXT"
        f.write_text("hola")
        assert extract_text_from_file(str(f)) == "hola"


# ---------------------------------------------------------------------------
# updater: versiones malformadas
# ---------------------------------------------------------------------------
class TestUpdaterVersiones:
    def test_v_prefijo_diez_vs_nueve(self):
        assert version_es_mayor("v1.0.10", "1.0.9") is True

    def test_igualdad_con_padding_distinto(self):
        assert version_es_mayor("1.0", "1.0.0") is False

    def test_garbage_ambas(self):
        assert version_es_mayor("abc", "") is False

    def test_garbage_remota_no_actualiza(self):
        r = check_for_updates(current_version="1.0.4", repo="", timeout=1)
        assert r["disponible"] is False and r["error"] is None

    def test_tag_name_diccionario_no_crashea(self, monkeypatch):
        import src.core.updater as up

        monkeypatch.setattr(up, "_get_json", lambda url, timeout: {"tag_name": {"mal": 1}})
        r = up.check_for_updates(current_version="9.9.9", repo="x/y")
        assert r["disponible"] is False

    def test_tag_name_null(self, monkeypatch):
        import src.core.updater as up

        monkeypatch.setattr(up, "_get_json", lambda url, timeout: {"tag_name": None})
        r = up.check_for_updates(current_version="1.0.4", repo="x/y")
        assert r["disponible"] is False and r["error"]

    def test_respuesta_no_dict(self, monkeypatch):
        import src.core.updater as up

        monkeypatch.setattr(up, "_get_json", lambda url, timeout: [1, 2, 3])
        r = up.check_for_updates(current_version="1.0.4", repo="x/y")
        assert r["disponible"] is False


# ---------------------------------------------------------------------------
# config hostil
# ---------------------------------------------------------------------------
class TestConfigHostil:
    def test_yaml_con_tabs(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("gui:\n\ttheme: dark\n")
        cfg = load_config(str(cfg_file))  # registra error pero no lanza
        assert cfg is not None

    def test_tipos_equivocados_mantienen_default_o_clampean(self, tmp_path):
        # Las claves son de nivel raiz; un tipo invalido conserva el default
        # y el clamp acota los valores extremos.
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("altitude_masl: alto\nmax_file_mb: -50\n")
        cfg = load_config(str(cfg_file))
        assert cfg.altitude_masl == 2640.0  # default conservado
        assert cfg.max_file_mb == 1  # clamp inferior

    def test_valores_extremos_se_clampean(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("altitude_masl: 99999\nmax_file_mb: 99999\n")
        cfg = load_config(str(cfg_file))
        assert cfg.altitude_masl == 6000.0
        assert cfg.max_file_mb == 500

    def test_config_vacia_da_defaults(self, tmp_path):
        cfg = load_config(str(tmp_path / "noexiste.yaml"))
        assert cfg.max_file_mb > 0

    def test_yaml_raiz_escalar(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("solo_un_string\n")
        assert load_config(str(cfg_file)) is not None


# ---------------------------------------------------------------------------
# borrado seguro con recursos hostiles
# ---------------------------------------------------------------------------
class TestBorradoSeguroHostil:
    def test_archivo_inexistente_true(self, tmp_path):
        assert secure_delete_file(str(tmp_path / "fantasma.pdf")) is True

    def test_directorio_no_crashea(self, tmp_path):
        d = tmp_path / "subdir"
        d.mkdir()
        resultado = secure_delete_file(str(d))
        assert isinstance(resultado, bool)

    def test_archivo_solo_lectura(self, tmp_path):
        f = tmp_path / "ro.pdf"
        f.write_bytes(b"ph")
        os.chmod(f, 0o444)
        try:
            # El borrado seguro degrada: sobrescritura falla -> eliminacion
            # normal (posible porque el directorio padre es escribible).
            resultado = secure_delete_file(str(f))
            assert isinstance(resultado, bool)
        finally:
            if os.path.exists(f):  # puede haber sido eliminado por el fallback
                os.chmod(f, 0o644)

    def test_clean_session_dirs_inexistentes(self, tmp_path):
        mgr = SecureDeleter(str(tmp_path / "ni"), str(tmp_path / "nf"))
        res = mgr.clean_session()  # no debe lanzar
        assert set(res) >= {"user_input", "output"}


# ---------------------------------------------------------------------------
# copias sin colision: nombres hostiles y cadenas de colision
# ---------------------------------------------------------------------------
class TestCopiasHostiles:
    def test_nombre_unicode(self, tmp_path):
        src = tmp_path / "informe_ñoño_eco #1.txt"
        src.write_text("contenido")
        dest = copy_to_user_input(str(src), str(tmp_path / "ui"))
        assert os.path.exists(dest) and "ñoño" in os.path.basename(dest)

    def test_cadena_de_tres_colisiones(self, tmp_path):
        ui = tmp_path / "ui"
        for i, contenido in enumerate(["A", "B", "C"], start=1):
            src = tmp_path / f"s{i}" / "eco.txt"
            src.parent.mkdir()
            src.write_text(contenido)
            dest = copy_to_user_input(str(src), str(ui))
            (tmp_path / "ultimo").write_text(dest)
        nombres = {p.name for p in ui.iterdir()}
        assert len(nombres) == 3  # eco + eco_N sin sobrescritura

    def test_recarga_mismo_contenido_idempotente(self, tmp_path):
        ui = tmp_path / "ui"
        src = tmp_path / "eco.txt"
        src.write_text("igual")
        d1 = copy_to_user_input(str(src), str(ui))
        d2 = copy_to_user_input(str(src), str(ui))
        assert d1 == d2 and len(list(ui.iterdir())) == 1


# ---------------------------------------------------------------------------
# truncado para el modelo
# ---------------------------------------------------------------------------
class TestTruncadoModelo:
    def test_texto_corto_intacto(self):
        t = "FEVI 52%" * 10
        assert _truncate_for_model(t) == t

    def test_texto_largo_al_limite(self):
        t = "D" * (MAX_AI_INPUT_CHARS * 3)
        out = _truncate_for_model(t)
        assert len(out) <= MAX_AI_INPUT_CHARS
        assert out.startswith("D") and "INICIO" not in out

    def test_preserva_cola_del_informe(self):
        cola = "FIRMADO POR DR. PRUEBA FINAL 1234"
        t = "x" * (MAX_AI_INPUT_CHARS * 2) + cola
        assert cola in _truncate_for_model(t)


# ---------------------------------------------------------------------------
# IA mockeada que devuelve JSON roto (fences, listas, ruido)
# ---------------------------------------------------------------------------
class TestIAResponsesRotas:
    @staticmethod
    def _mock(monkeypatch, content):
        import src.core.ai_extractor as ae

        # Igual que test_hardening: hay que atravesar el chequeo de
        # disponibilidad para llegar al POST mockeado.
        monkeypatch.setattr(ae, "_server_ready", lambda *a, **k: True)

        class R:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"message": {"content": content}}

        monkeypatch.setattr(ae, "_post_chat_with_retry", lambda *a, **k: R())

    def _texto_base(self):
        return "ECOCARDIOGRAMA DOPPLER\nPaciente: PRUEBA FZZ\nFEVI (Teichholz): 52 %\nDDVI: 46 mm"

    def test_json_con_fences_y_ruido(self, monkeypatch):
        self._mock(monkeypatch, '```json\n{"patientData": {"sexo": "M"}}\n```')
        r = extract_from_text(self._texto_base(), use_ai=True)
        assert r.patient_data.get("sexo") == "M"

    def test_lista_en_veces_de_dict(self, monkeypatch):
        self._mock(monkeypatch, '[{"patientData": {"sexo": "M"}}]')
        r = extract_from_text(self._texto_base(), use_ai=True)
        # debe caer a regex sin crash
        assert isinstance(r.numeric_params, dict)

    def test_numeric_items_no_dict(self, monkeypatch):
        self._mock(
            monkeypatch,
            '{"numericParams": ["FEVI", null, 42, {"key":"fevi","value":"55"}]}',
        )
        r = extract_from_text(self._texto_base(), use_ai=True)
        assert r.numeric_params.get("fevi") == 55.0 or r.warnings

    def test_respuesta_vacia_del_modelo(self, monkeypatch):
        self._mock(monkeypatch, "")
        r = extract_from_text(self._texto_base(), use_ai=True)
        assert r.numeric_params  # regex rescata los datos

    def test_json_con_valores_null_en_todos_los_campos(self, monkeypatch):
        self._mock(
            monkeypatch,
            '{"patientData":{"sexo":null,"edad":null},"numericParams":[{"key":null,"value":null}],"visualData":null}',
        )
        r = extract_from_text(self._texto_base(), use_ai=True)
        assert isinstance(r.visual_data, dict)


# ---------------------------------------------------------------------------
# recomendaciones y validador con filas extremas
# ---------------------------------------------------------------------------
class TestRecomendacionesExtremas:
    def test_filas_vacias(self):
        assert get_rule_based_recommendations([]) == []

    def test_filas_basura_no_crashean(self):
        rows = [{"parametro": None}, {}, {"hallazgo": 123}]
        recs = get_rule_based_recommendations(rows)  # no lanzar
        assert isinstance(recs, list)


# ---------------------------------------------------------------------------
# GUI offscreen: doble invocacion y cierre repetido
# ---------------------------------------------------------------------------
@pytest.fixture()
def gui_aislado(tmp_path, monkeypatch):
    """Entorno GUI aislado (patron env_aislado de test_e2e_flow)."""
    from PyQt6.QtWidgets import QMessageBox

    from src.utils import config as config_mod

    cfg = config_mod.load_config()
    cfg.user_input_dir = str(tmp_path / "user_input")
    cfg.output_dir = str(tmp_path / "output")
    cfg.log_file = str(tmp_path / "logs" / "app.log")
    os.makedirs(cfg.user_input_dir, exist_ok=True)
    os.makedirs(cfg.output_dir, exist_ok=True)
    monkeypatch.setattr("src.gui.main_window.load_config", lambda: cfg)
    # Hermeticidad P11: la pestaña IA no debe sondear el Ollama real de la maquina
    monkeypatch.setattr(
        "src.gui.ai_tab.check_ollama",
        lambda base_url, timeout=2.0: (False, []),
    )
    monkeypatch.setattr(
        "src.gui.main_window.QMessageBox.information",
        lambda *a, **k: QMessageBox.StandardButton.Ok,
    )
    monkeypatch.setattr(
        "src.gui.main_window.QMessageBox.warning",
        lambda *a, **k: QMessageBox.StandardButton.Ok,
    )
    return cfg


@pytest.mark.qt_no_exception_capture
class TestGuiDobleInvocacion:
    def test_update_check_dos_veces_un_solo_worker(
        self, qtbot, monkeypatch, gui_aislado
    ):
        import threading

        from src.gui.main_window import MainWindow

        llamadas = []
        bloqueo = threading.Event()

        def fake_check(*a, **k):
            llamadas.append(1)
            bloqueo.wait(timeout=5)  # worker vivo mientras verificamos el guard
            return {"disponible": False, "version_remota": "", "error": None}

        monkeypatch.setattr("src.gui.main_window.check_for_updates", fake_check)
        gui_aislado.update.enabled = True
        gui_aislado.update.repo = "x/y"
        w = MainWindow()
        qtbot.addWidget(w)
        try:
            w._start_update_check(manual=True)
            qtbot.waitUntil(lambda: len(llamadas) == 1, timeout=5000)
            w._start_update_check(manual=True)  # solapamiento: guard debe frenarlo
            assert len(llamadas) == 1
        finally:
            bloqueo.set()
            qtbot.waitUntil(
                lambda: getattr(w, "_update_worker", None) is None, timeout=5000
            )
            w.close()

    def test_shutdown_doble_idempotente(self, qtbot, gui_aislado):
        from src.gui.main_window import MainWindow

        w = MainWindow()
        qtbot.addWidget(w)
        tab_ia = getattr(w, "ai_tab", None)
        if tab_ia is not None and hasattr(tab_ia, "shutdown"):
            tab_ia.shutdown()
            tab_ia.shutdown()  # doble apagado no debe lanzar
        w.close()

    def test_close_event_doble(self, qtbot, gui_aislado):
        from PyQt6.QtGui import QCloseEvent

        from src.gui.main_window import MainWindow

        w = MainWindow()
        qtbot.addWidget(w)
        e1, e2 = QCloseEvent(), QCloseEvent()
        w.closeEvent(e1)
        w.closeEvent(e2)  # cierre repetido no debe lanzar
        assert isinstance(e2, QCloseEvent)


# ---------------------------------------------------------------------------
# error_guard: excepciones encadenadas sin dialogos
# ---------------------------------------------------------------------------
class TestErrorGuardEncadenado:
    def test_diez_excepciones_seguidas_no_crashean(self):
        import sys

        from src.utils.error_guard import install_excepthook, uninstall_excepthook

        set_dialogs_enabled(False)
        install_excepthook()
        hook = sys.excepthook  # referencia directa: no pasa por el capturador de pytest
        try:
            for _ in range(10):
                hook(RuntimeError, RuntimeError("fuzz"), None)  # no debe lanzar
        finally:
            uninstall_excepthook()

    def test_uninstall_restaura_hook_original(self):
        import sys

        from src.utils.error_guard import install_excepthook, uninstall_excepthook

        original = sys.excepthook
        set_dialogs_enabled(False)
        try:
            install_excepthook()
            assert sys.excepthook is not original
            uninstall_excepthook()
            assert sys.excepthook is original
        finally:
            uninstall_excepthook()


# ---------------------------------------------------------------------------
# validador con paciente extremo
# ---------------------------------------------------------------------------
class TestValidadorPacienteExtremo:
    @staticmethod
    def _validator():
        from src.core.validator import Validator
        from src.models.colombian_reference import load_colombian_references

        return Validator(reference_ranges=load_colombian_references(2640))

    def test_valores_absurdos_en_todos_los_campos(self):
        from src.models.patient import Patient

        p = Patient()
        for campo in p.get_numeric_fields():
            setattr(p, campo, 10**9)  # absurdo deliberado
        resultado = self._validator().validate_patient(p)  # no debe lanzar
        assert isinstance(resultado, dict)

    def test_valores_negativos(self):
        from src.models.patient import Patient

        p = Patient()
        for campo in p.get_numeric_fields():
            setattr(p, campo, -1)
        resultado = self._validator().validate_patient(p)
        assert isinstance(resultado, dict)


# ---------------------------------------------------------------------------
# parse_version extrema
# ---------------------------------------------------------------------------
class TestParseVersionExtrema:
    def test_tipos_no_string(self):
        assert parse_version(None) == (0,)
        assert parse_version([1, 2]) == (0,)

    def test_numeros_negativos_ignorados(self):
        assert parse_version("-1.2") == (1, 2)  # regex captura 1.2

    def test_version_larga(self):
        assert parse_version("v1.2.3.4.5") == (1, 2, 3, 4, 5)
