"""Tests de los protocolos antifallo anadidos en la auditoria.

Cada test documenta el protocolo que verifica:
  P1. Normalizacion de datos de paciente de la IA (seguridad clinica).
  P2. Confianza 0.0 de la IA no se convierte en default.
  P3. Truncado cabeza+cola de la entrada al modelo local.
  P4. Reintento ante fallo transitorio de red con Ollama.
  P5. Verificacion de espacio en disco antes de descargar modelo.
  P6. Clamps de sanidad en la configuracion.
  P7. Copia a user_input sin sobrescribir copias previas.
  P8. Lectura TXT con codificacion Latin-1 heredada.
  P9. Limite de tamano unificado y configurable.
  P10. Excepthook global no aborta el proceso.
"""
import logging

import pytest

import src.core.ai_extractor as ae
from src.core.ai_extractor import (
    MAX_AI_INPUT_CHARS,
    _normalize_patient,
    extract_from_text,
    extract_text_from_file,
)
from src.utils.config import load_config
from src.utils.error_guard import install_excepthook, reset_error_guard
from src.utils.helpers import copy_to_user_input


class TestP1NormalizacionPacienteIA:
    def test_normalize_mapea_sexo_extendido(self):
        out = _normalize_patient({"sexo": "masculino"})
        assert out["sexo"] == "M"
        out = _normalize_patient({"sexo": "mujer"})
        assert out["sexo"] == "F"

    def test_normalize_rechaza_edad_imposible(self):
        assert _normalize_patient({"edad": "250"})["edad"] is None
        assert _normalize_patient({"edad": "5"})["edad"] is None
        assert _normalize_patient({"edad": "abc"})["edad"] is None
        assert _normalize_patient({"edad": "62.7"})["edad"] == "62"

    def test_extract_from_text_normaliza_salida_ia(self, monkeypatch):
        """Regresion: la IA devolvia 'masculino' y llegaba crudo al informe."""
        parsed = {
            "numericParams": [{"key": "fevi", "value": 60, "confidence": 0.8}],
            "patientData": {"sexo": "masculino", "edad": "abc", "fecha_estudio": "6-8-26"},
        }
        monkeypatch.setattr(
            ae, "ollama_extract", lambda *a, **k: (parsed, "ollama")
        )
        result = extract_from_text("FEVI (%) : 60", use_ai=True)
        assert result.patient_data["sexo"] == "M"  # antes quedaba "masculino"
        assert result.patient_data["edad"] is None  # basura descartada
        assert result.patient_data["fecha_estudio"] == "06/08/2026"


class TestP2ConfianzaCero:
    def test_confidence_cero_se_conserva(self):
        """Regresion: 'or 0.7' convertia una confianza explicita 0 en default."""
        out = ae._numeric_from_ai({
            "numericParams": [
                {"key": "fevi", "value": 60, "confidence": 0},
                {"key": "ddi", "value": 50},  # sin confianza -> default
            ],
        })
        assert out["fevi"] == (60.0, 0.0)
        assert out["ddi"] == (50.0, 0.7)

    def test_fusion_con_regex_toma_maximo(self, monkeypatch):
        """IA(0.85) vs regex(0.0): al coincidir valores gana la mayor confianza."""
        parsed = {"numericParams": [{"key": "fevi", "value": 60, "confidence": 0}]}
        monkeypatch.setattr(ae, "ollama_extract", lambda *a, **k: (parsed, "ollama"))
        result = extract_from_text("FEVI (%): 60", use_ai=True)
        assert result.numeric_params["fevi"] == 60
        assert result.numeric_confidence["fevi"] >= 0.7  # regex respalda el valor


class TestP3TruncadoModelo:
    def test_truncate_conserva_cabeza_y_cola(self):
        texto = "A" * 10000 + "MARCA-CENTRO" + "Z" * 10000
        out = ae._truncate_for_model(texto)
        assert len(out) <= MAX_AI_INPUT_CHARS + 64
        assert "[...fragmento omitido por longitud...]" in out
        assert out.startswith("A") and out.endswith("Z")

    def test_payload_enviado_al_modelo_es_acotado(self, monkeypatch):
        capturado = {}
        class _Resp:
            status_code = 200
            def json(self):
                return {"message": {"content": "{}"}}

        def fake_post(url, json=None, timeout=None):
            capturado.update(json=json)
            return _Resp()

        monkeypatch.setattr(ae.requests, "post", fake_post)
        monkeypatch.setattr(ae, "_server_ready", lambda *a, **k: True)
        monkeypatch.setattr(ae, "_model_available", lambda *a, **k: True)
        texto_grande = "DDI: 54 mm\n" * 4000  # ~48k caracteres
        extract_from_text(texto_grande, use_ai=True)
        contenido = capturado["json"]["messages"][1]["content"]
        assert len(contenido) < MAX_AI_INPUT_CHARS + 200


class TestP4ReintentoRed:
    def test_reintenta_y_recupera_fallo_transitorio(self, monkeypatch):
        llamadas = {"n": 0}

        class _Resp:
            status_code = 200
            def json(self):
                return {"message": {"content": "{}"}}

        def fake_post(url, json=None, timeout=None):
            llamadas["n"] += 1
            if llamadas["n"] == 1:
                raise ae.requests.ConnectionError("reset por peer")
            return _Resp()

        monkeypatch.setattr(ae.requests, "post", fake_post)
        monkeypatch.setattr(ae.time, "sleep", lambda s: None)
        resp = ae._post_chat_with_retry("http://x/api/chat", {}, read_timeout=5)
        assert resp.status_code == 200
        assert llamadas["n"] == 2

    def test_agota_intentos_y_propaga(self, monkeypatch):
        llamadas = {"n": 0}

        def fake_post(url, json=None, timeout=None):
            llamadas["n"] += 1
            raise ae.requests.ConnectionError("caido")

        monkeypatch.setattr(ae.requests, "post", fake_post)
        monkeypatch.setattr(ae.time, "sleep", lambda s: None)
        with pytest.raises(ae.requests.ConnectionError):
            ae._post_chat_with_retry("http://x/api/chat", {}, read_timeout=5)
        assert llamadas["n"] == 2

    def test_cancelacion_no_reintenta(self, monkeypatch):
        llamadas = {"n": 0}

        def fake_post(url, json=None, timeout=None):
            llamadas["n"] += 1
            raise ae.requests.ConnectionError("caido")

        monkeypatch.setattr(ae.requests, "post", fake_post)
        with pytest.raises(RuntimeError, match="cancelada"):
            ae._post_chat_with_retry(
                "http://x/api/chat", {}, read_timeout=5, cancel_cb=lambda: True
            )
        assert llamadas["n"] == 0


class TestP5EspacioDisco:
    def test_pull_abortado_sin_espacio(self, monkeypatch):
        import subprocess

        def _no_popen(*a, **k):  # Si se llama, el test falla
            raise AssertionError("Popen no debio ejecutarse sin espacio")

        monkeypatch.setattr(ae, "_find_ollama_exe", lambda: r"C:\fake\ollama.exe")
        monkeypatch.setattr(ae, "_disk_space_ok", lambda *a, **k: False)
        monkeypatch.setattr(subprocess, "Popen", _no_popen)
        assert ae._pull_model("http://127.0.0.1:9", "m") == "pull_failed"

    def test_medicion_fallida_permite_continuar(self, monkeypatch):
        """Si medir el disco falla, no se bloquea la descarga (fail-open)."""

        def roto(*a, **k):
            raise OSError("fs exotico")

        monkeypatch.setattr("shutil.disk_usage", roto)
        assert ae._disk_space_ok() is True

    def test_disco_lleno_detectado(self, tmp_path):
        # Un umbral imposible sobre un disco real => False (hay medicion)
        assert ae._disk_space_ok(str(tmp_path), required_gb=1e12) is False


class TestP6ClampsConfig:
    def _load_from_yaml(self, tmp_path, content):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(content, encoding="utf-8")
        return load_config(str(cfg_file))

    def test_altitud_negativa_clampeada(self, tmp_path):
        cfg = self._load_from_yaml(tmp_path, "altitude_masl: -500\n")
        assert cfg.altitude_masl == 0.0

    def test_altitud_absurda_clampeada(self, tmp_path):
        cfg = self._load_from_yaml(tmp_path, "altitude_masl: 99999\n")
        assert cfg.altitude_masl == 6000.0

    def test_max_file_mb_minimo_uno(self, tmp_path):
        cfg = self._load_from_yaml(tmp_path, "max_file_mb: 0\n")
        assert cfg.max_file_mb == 1

    def test_timeout_ia_acotado(self, tmp_path):
        cfg = self._load_from_yaml(tmp_path, "ai:\n  timeout: 999999\n")
        assert cfg.ai.timeout == 1800.0

    def test_yaml_roto_usa_defaults_y_registra_error(self, tmp_path, caplog):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("guide: [esto, no, es, valido\n", encoding="utf-8")
        with caplog.at_level(logging.ERROR, logger="ecocardiograma"):
            cfg = load_config(str(cfg_file))
        assert cfg.guide == "colombian"  # defaults
        assert any("config.yaml" in r.message for r in caplog.records)


class TestP7CopiaSinColision:
    def test_segunda_copia_no_sobrescribe(self, tmp_path):
        src_a = tmp_path / "informe.pdf"
        src_a.write_text("A", encoding="utf-8")
        dest_dir = tmp_path / "user_input"
        dest_dir.mkdir()

        d1 = copy_to_user_input(str(src_a), str(dest_dir))
        src_b = tmp_path / "sub"
        src_b.mkdir()
        otro = src_b / "informe.pdf"
        otro.write_text("B", encoding="utf-8")
        d2 = copy_to_user_input(str(otro), str(dest_dir))

        assert d1 != d2
        assert open(d1, encoding="utf-8").read() == "A"
        assert open(d2, encoding="utf-8").read() == "B"

    def test_copiar_el_mismo_archivo_es_idempotente(self, tmp_path):
        src = tmp_path / "doc.txt"
        src.write_text("x", encoding="utf-8")
        dest_dir = str(tmp_path / "ui")
        d1 = copy_to_user_input(str(src), dest_dir)
        d2 = copy_to_user_input(str(src), dest_dir)
        assert d1 == d2  # misma fuente: no crea variantes infinitas


class TestP8EncodingHeredado:
    def test_txt_latin1_se_decodifica(self, tmp_path):
        p = tmp_path / "informe_latin1.txt"
        # Bytes Latin-1: "Área" y "años" en Windows-1252/Latin-1
        p.write_bytes(b"FEVI: 55%\nEdad: 50 a\xf1os \xc1rea 4,2 cm2")
        text = extract_text_from_file(str(p))
        assert "55" in text
        assert "\xf1" in text  # decodificado, no reemplazado por '?'

    def test_utf8_sigue_funcionando(self, tmp_path):
        p = tmp_path / "informe_utf8.txt"
        p.write_text("DDI (mm): 54", encoding="utf-8")
        assert extract_text_from_file(str(p)) == "DDI (mm): 54"


class TestP9LimiteUnificado:
    def test_limite_personalizado_respeta_valor_inyectado(self, tmp_path):
        p = tmp_path / "chico.txt"
        p.write_text("ok", encoding="utf-8")
        with pytest.raises(ValueError, match="limite"):
            extract_text_from_file(str(p), max_bytes=1)

    def test_limite_por_defecto_vigente(self, tmp_path):
        p = tmp_path / "grande.bin"
        p.write_bytes(b"x" * (ae.MAX_EXTRACT_FILE_BYTES + 1))
        with pytest.raises(ValueError):
            extract_text_from_file(str(p))


class TestP10ExcepthookGlobal:
    def test_excepthook_registra_y_no_aborta(self, caplog):
        reset_error_guard()
        install_excepthook(allow_abort=False)
        try:
            with caplog.at_level(logging.ERROR, logger="ecocardiograma"):
                try:
                    raise ValueError("fallo de prueba controlado")
                except ValueError:
                    import sys as _sys
                    _sys.excepthook(*_sys.exc_info())
        finally:
            import sys as _sys
            _sys.excepthook = _sys.__excepthook__
        assert any("ValueError" in r.message for r in caplog.records)
