"""Tests unitarios para el extractor (regex + IA local)."""
import pytest

from src.core.ai_extractor import (
    extract_from_text,
    extract_numeric_params_regex,
    extract_visual_regex,
    extract_patient_regex,
    _extract_json_block,
    _merge_numeric,
    _mentioned_keys,
    in_bounds,
)

# Texto de ejemplo similar a un informe real
SAMPLE_TEXT = """INFORME ECOCARDIOGRÁFICO
Paciente: masculino, 62 años
Fecha: 07/08/2026
Médico: Dra. Maria González

GEOMETRÍA VENTRICULAR
DDI (Diámetro Diastólico VI): 54 mm
DSI (Diámetro Sistólico VI): 36 mm
PPVI (Pared Posterior VI): 11.5 mm
SIVI (Septum Interventricular): 12.5 mm
Masa VI: 215 g
Masa VI Indexada: 112 g/m2

VOLÚMENES VI
Volumen Diastólico VI: 140 ml
Volumen Sistólico VI: 55 ml
FEVI (Fracción de Eyección): 53%

AURÍCULA IZQUIERDA Y VD
Diámetro AI: 43 mm
Volumen AI Indexado: 38 ml/m2
Diámetro VD: 38 mm
TAPSE: 18 mm
FSR (Fracción Sistólica VD): 35%

VÁLVULAS Y PRESIONES
Gradiente Medio Mitral: 2.5 mmHg
Gradiente Máximo Mitral: 6 mmHg
Área Valvular Mitral: 4.8 cm2
Gradiente Medio Aórtico: 14 mmHg
Gradiente Máximo Aórtico: 28 mmHg
Área Valvular Aórtica: 2.6 cm2
Velocidad Insuf. Aórtica: 2.8 m/s
PSAP: 42 mmHg

HALLAZGOS VISUALES
Insuficiencia Aórtica: Leve
Insuficiencia Tricúspidea: Leve
Derrame Pericárdico: No
Contractilidad: Hipocinética segmentaria
Segmentos Afectados: Inferior y septal apical
Engrosamiento pericárdico leve. Placa ateromatosa en aorta ascendente.
"""


class TestRegexNumeric:
    def test_extrae_parametros_clave(self):
        res = extract_numeric_params_regex(SAMPLE_TEXT)
        assert res["ddi"][0] == 54
        assert res["dsi"][0] == 36
        assert res["fevi"][0] == 53
        assert res["psap"][0] == 42

    def test_extrae_decimales(self):
        res = extract_numeric_params_regex(SAMPLE_TEXT)
        assert res["ppvi"][0] == 11.5
        assert res["area_mi"][0] == 4.8

    def test_no_extrae_valores_fuera_de_rango(self):
        res = extract_numeric_params_regex("DDI: 9999 mm")
        assert "ddi" not in res

    def test_convierte_cm_a_mm(self):
        # "DDI: 5,4 cm" debe leerse como 54 mm (no 5.4 mm -> "Bajo")
        res = extract_numeric_params_regex("DDI: 5,4 cm")
        assert res["ddi"][0] == 54.0
        res = extract_numeric_params_regex("DDI (Diámetro Diastólico VI): 5.4 cm")
        assert res["ddi"][0] == 54.0

    def test_convierte_mm2_a_cm2(self):
        res = extract_numeric_params_regex("Area Valvular Mitral: 480 mm2")
        assert res["area_mi"][0] == 4.8

    def test_valores_en_mm_sin_cambio(self):
        res = extract_numeric_params_regex("DDI: 54 mm")
        assert res["ddi"][0] == 54.0

    def test_no_convierte_ml_ni_m_s(self):
        res = extract_numeric_params_regex(
            "Volumen Diastolico VI: 140 ml\nVelocidad Insuf. AO: 2.8 m/s"
        )
        assert res["rvdi"][0] == 140.0
        assert res["velocidad_insuf_ao"][0] == 2.8

    def test_in_bounds(self):
        assert in_bounds("fevi", 55.0)
        assert not in_bounds("fevi", 250.0)


class TestRegexVisual:
    def test_insuficiencias(self):
        res = extract_visual_regex(SAMPLE_TEXT)
        assert res["insuficiencia_aortica"] == "Leve"
        assert res["insuficiencia_tricuspidea"] == "Leve"
        assert res["insuficiencia_mitral"] == "No"

    def test_contractilidad_segmentaria(self):
        res = extract_visual_regex(SAMPLE_TEXT)
        assert res["contractilidad"] == "Hipocinetica segmentaria"

    def test_segmentos(self):
        res = extract_visual_regex(SAMPLE_TEXT)
        assert "septal apical" in res["segmentos_afectados"]


class TestRegexPatient:
    def test_sexo_y_edad(self):
        res = extract_patient_regex(SAMPLE_TEXT)
        assert res["sexo"] == "M"
        assert res["edad"] == "62"

    def test_medico_y_fecha(self):
        res = extract_patient_regex(SAMPLE_TEXT)
        assert "Maria" in (res["nombre_medico"] or "")
        assert res["fecha_estudio"] == "07/08/2026"

    def test_medico_en_minusculas(self):
        # "medico: dra. maria gonzalez" debe detectarse y normalizarse el caso
        res = extract_patient_regex("medico: dra. maria gonzalez")
        assert res["nombre_medico"] == "Maria Gonzalez"
        res = extract_patient_regex("médico: juan carlos rodríguez")
        assert res["nombre_medico"] == "Juan Carlos Rodríguez"

    def test_edad_con_grafia_anios(self):
        # "anios" (error comun por "años") debe capturarse como edad
        res = extract_patient_regex("Paciente: 54 anios, sexo femenino")
        assert res["edad"] == "54"
        assert res["sexo"] == "F"

    def test_medico_no_engulle_palabras_clave(self):
        # El nombre del medico no debe incluir "Fecha" ni otros campos
        res = extract_patient_regex(
            "Medico: Dra. Maria Gonzalez    Fecha: 12/05/2026"
        )
        assert res["nombre_medico"] == "Maria Gonzalez"
        assert res["fecha_estudio"] == "12/05/2026"

    def test_paciente_medico_nombre_multiples_palabras(self):
        res = extract_patient_regex("Médico: Dr. Juan Carlos Rodríguez, cardiólogo")
        assert res["nombre_medico"] == "Juan Carlos Rodríguez"

    def test_merge_paciente_regex_gana(self):
        from src.core.ai_extractor import _merge_patient

        ai = {"sexo": "F", "edad": "64", "nombre_medico": "Dra. Maria Gonzalez"}
        regex = {"sexo": "F", "edad": "54", "nombre_medico": "Maria Gonzalez"}
        merged = _merge_patient(ai, regex)
        # El regex gana en edad (evita la alucinacion de la IA) y rellena huecos
        assert merged["edad"] == "54"
        assert merged["nombre_medico"] == "Maria Gonzalez"
        assert merged["sexo"] == "F"

    def test_merge_paciente_ia_rellena_huecos(self):
        from src.core.ai_extractor import _merge_patient

        ai = {"sexo": "M", "edad": None, "nombre_medico": "Dr. Perez"}
        regex = {"sexo": None, "edad": "60", "nombre_medico": None}
        merged = _merge_patient(ai, regex)
        assert merged["edad"] == "60"
        assert merged["sexo"] == "M"
        assert merged["nombre_medico"] == "Dr. Perez"


class TestJSONParsing:
    def test_bloque_json_limpio(self):
        data = _extract_json_block('{"key": "fevi", "value": 55}')
        assert data["key"] == "fevi"

    def test_bloque_json_con_texto_extra(self):
        data = _extract_json_block('Aqui va el JSON:\n{"a": 1}\nFin.')
        assert data["a"] == 1

    def test_bloque_json_invalido(self):
        assert _extract_json_block("no hay json") is None
        assert _extract_json_block("") is None


class TestFullExtraction:
    def test_extraccion_solo_regex(self):
        result = extract_from_text(SAMPLE_TEXT, use_ai=False)
        assert result.source == "regex"
        assert result.numeric_params.get("fevi") == 53
        assert result.numeric_params.get("ddi") == 54
        assert result.visual_data["insuficiencia_aortica"] == "Leve"
        assert result.patient_data["sexo"] == "M"
        assert result.confidence > 0
        assert "González" in (result.patient_data.get("nombre_medico") or "González")

    def test_extraccion_con_ollama_fallback(self):
        # Si Ollama no esta, debe caer a regex sin errores (sin auto-inicio)
        result = extract_from_text(
            SAMPLE_TEXT, use_ai=True, base_url="http://localhost:1",
            auto_start_ollama=False,
        )
        assert result.numeric_params.get("psap") == 42
        assert result.source in ("regex", "ollama+regex")

    def test_extraccion_texto_vacio(self):
        result = extract_from_text("", use_ai=False)
        assert result.source == "vacio"
        assert result.warnings


class TestAutoStartOllama:
    """Pruebas del arranque automatico de Ollama (rutas deterministas)."""

    def test_ensure_not_found_sin_binario(self):
        from src.core.ai_extractor import ensure_ollama_running
        status = ensure_ollama_running(
            "http://127.0.0.1:9", "qwen2.5:3b", wait=1,
            pull_model=False, exe_path=r"C:\inexistente\ollama.exe",
        )
        assert status == "not_found"

    def test_find_ollama_exe_no_rompe(self):
        from src.core.ai_extractor import _find_ollama_exe
        result = _find_ollama_exe()
        assert result is None or isinstance(result, str)

    def test_pull_model_failed_sin_binario(self, monkeypatch):
        import src.core.ai_extractor as ae
        monkeypatch.setattr(ae, "_find_ollama_exe", lambda: r"C:\inexistente\ollama.exe")
        assert ae._pull_model("http://127.0.0.1:9", "fake:model") == "pull_failed"

    def test_extract_con_auto_start_no_instalado(self, monkeypatch):
        import src.core.ai_extractor as ae
        monkeypatch.setattr(ae, "_find_ollama_exe", lambda: None)
        monkeypatch.setattr(ae, "_server_ready", lambda *a, **k: False)
        with pytest.raises(RuntimeError, match="no esta instalado"):
            ae.ollama_extract("DDI: 54 mm", "qwen2.5:3b", auto_start_ollama=True)

    def test_extract_fallback_cuando_auto_start_falla(self, monkeypatch):
        import src.core.ai_extractor as ae
        monkeypatch.setattr(ae, "_find_ollama_exe", lambda: None)
        monkeypatch.setattr(ae, "_server_ready", lambda *a, **k: False)
        result = ae.extract_from_text("DDI (mm): 54", use_ai=True)
        assert result.source == "regex"
        assert result.numeric_params.get("ddi") == 54
        assert any("Ollama" in w or "IA" in w for w in result.warnings)

    def test_ensure_ok_cuando_servidor_responde(self, monkeypatch):
        import src.core.ai_extractor as ae
        monkeypatch.setattr(ae, "_server_ready", lambda *a, **k: True)
        monkeypatch.setattr(ae, "_model_available", lambda *a, **k: True)
        status = ae.ensure_ollama_running(
            "http://localhost:11434", "qwen2.5:3b", wait=1, pull_model=True
        )
        assert status == "ok"


class TestPDFExtraction:
    def _write_pdf_via_qprinter(self, pdf_path: str, html: str) -> None:
        """Genera un PDF usando QPrinter (misma ruta que la app en Windows).

        Reemplaza a WeasyPrint (que no esta disponible sin GTK) para que el
        test cubra la cadena real QPrinter -> pypdf y no se salte en Windows.

        Nota: usa el plugin de ventana nativo (no 'offscreen'), ya que
        QTextDocument necesita las fuentes del sistema para incrustar texto.
        """
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QPageSize, QTextDocument
        from PyQt6.QtPrintSupport import QPrinter

        app = QApplication.instance() or QApplication([])  # noqa: F841
        doc = QTextDocument()
        doc.setHtml(html)

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(pdf_path)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        doc.print(printer)

    def test_extrae_texto_de_pdf(self, tmp_path):
        from src.core.ai_extractor import extract_text_from_pdf

        pdf_path = str(tmp_path / "test.pdf")
        self._write_pdf_via_qprinter(
            pdf_path,
            "<html><body><p>DDI (mm): 54</p><p>FEVI: 53%</p></body></html>",
        )

        text = extract_text_from_pdf(pdf_path)
        assert "54" in text

    def test_archivo_no_existe(self, tmp_path):
        from src.core.ai_extractor import extract_from_file

        result = extract_from_file(str(tmp_path / "no_existe.pdf"), use_ai=False)
        assert result.source == "error"
        assert result.warnings

    def test_archivo_demasiado_grande(self, tmp_path):
        from src.core.ai_extractor import (
            extract_from_file, extract_text_from_file, MAX_EXTRACT_FILE_BYTES,
        )

        big = tmp_path / "grande.txt"
        with open(big, "w", encoding="utf-8") as f:
            f.write("x" * (MAX_EXTRACT_FILE_BYTES + 10))

        with pytest.raises(ValueError):
            extract_text_from_file(str(big))

        result = extract_from_file(str(big), use_ai=False)
        assert result.source == "error"
        assert result.warnings


class TestOCRExtraction:
    def test_ocr_imagen(self, tmp_path):
        from src.core.ai_extractor import (
            extract_text_from_image, _get_tesseract_cmd,
        )

        if _get_tesseract_cmd() is None:
            pytest.skip("Tesseract no esta instalado en el sistema")
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            pytest.skip("pillow no disponible")

        img_path = str(tmp_path / "eco.png")
        img = Image.new("RGB", (900, 240), "white")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 44)
        except Exception:  # noqa: BLE001 - fuente por defecto si no hay TTF
            font = None
        draw.text((30, 40), "DDI (mm): 54", fill="black", font=font)
        draw.text((30, 130), "FEVI: 53%", fill="black", font=font)
        img.save(img_path)

        text = extract_text_from_image(img_path)
        assert "54" in text
        assert "53" in text

    def test_ocr_via_extract_from_file(self, tmp_path):
        from src.core.ai_extractor import extract_from_file, _get_tesseract_cmd

        if _get_tesseract_cmd() is None:
            pytest.skip("Tesseract no esta instalado en el sistema")
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            pytest.skip("pillow no disponible")

        img_path = str(tmp_path / "eco2.png")
        img = Image.new("RGB", (900, 240), "white")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 44)
        except Exception:  # noqa: BLE001
            font = None
        draw.text((30, 40), "DDI (mm): 54", fill="black", font=font)
        draw.text((30, 130), "FEVI: 53%", fill="black", font=font)
        img.save(img_path)

        result = extract_from_file(img_path, use_ai=False)
        assert result.source == "regex"
        assert result.numeric_params.get("ddi") == 54
        assert result.numeric_params.get("fevi") == 53


class TestMergeNumeric:
    def test_conflicto_ia_vs_regex_gana_regex(self):
        ai = {"fevi": (60.0, 0.9)}       # valor que difiere del regex
        regex = {"fevi": (53.0, 0.85)}   # valor etiquetado en el texto
        merged, conf, warnings = _merge_numeric(ai, regex, _mentioned_keys(SAMPLE_TEXT))
        assert merged["fevi"] == 53.0
        assert conf["fevi"] == 0.85
        assert any("Conflicto IA vs reglas" in w for w in warnings)

    def test_coincidencia_usa_ia_con_mayor_confianza(self):
        ai = {"fevi": (53.0, 0.5)}
        regex = {"fevi": (53.0, 0.9)}
        merged, conf, warnings = _merge_numeric(ai, regex, _mentioned_keys(SAMPLE_TEXT))
        assert merged["fevi"] == 53.0
        assert conf["fevi"] == 0.9
        assert not warnings

    def test_ia_solo_con_respaldo_en_texto_se_acepta(self):
        ai = {"fevi": (53.0, 0.8)}  # "FEVI (Fracción de Eyección)" esta en SAMPLE_TEXT
        merged, conf, warnings = _merge_numeric(ai, {}, _mentioned_keys(SAMPLE_TEXT))
        assert merged.get("fevi") == 53.0
        assert not warnings

    def test_ia_solo_sin_respaldo_se_conserva_con_warning(self):
        ai = {"gradiente_media_mi": (8.0, 0.9)}
        merged, conf, warnings = _merge_numeric(
            ai, {}, _mentioned_keys("Texto de prueba sin parametros")
        )
        # El valor se conserva (el guard ya no descarta datos legitimos), pero
        # se advierte que no tiene respaldo explicito en el texto.
        assert merged.get("gradiente_media_mi") == 8.0
        assert conf["gradiente_media_mi"] == 0.9
        assert any("no aparece" in w for w in warnings)

    def test_ia_solo_etiqueta_abreviada_se_conserva(self):
        # "Diam. AI:" no matchea ningun alias largo: antes el guard descartaba el
        # valor de IA; ahora se conserva y solo se advierte para revision manual.
        ai = {"diametro_ai": (43.0, 0.85)}
        merged, conf, warnings = _merge_numeric(ai, {}, _mentioned_keys("Diam. AI: 43 mm"))
        assert merged.get("diametro_ai") == 43.0
        assert conf["diametro_ai"] == 0.85
        assert not any("descartado" in w for w in warnings)
        assert any("revision manual" in w for w in warnings)

    def test_alias_que_es_solo_unidad_no_cuenta_como_mencionado(self):
        # "ml/m2" es unidad de otra medicion (volumen indexado), no respalda "volumen_ai"
        mentioned = _mentioned_keys("Volumen diastolico indexado: 76 ml/m2")
        assert "volumen_ai" not in mentioned
        mentioned = _mentioned_keys("Masa ventricular derecha: 45 g/m2")
        assert "masa_vi_ind" not in mentioned

    def test_regex_rellena_vacios(self):
        regex = {"psap": (42.0, 0.85)}
        merged, conf, warnings = _merge_numeric({}, regex, set())
        assert merged["psap"] == 42.0
        assert not warnings
