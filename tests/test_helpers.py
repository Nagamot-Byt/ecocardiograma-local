"""Tests de las utilidades generales (src.utils.helpers)."""
import os

from src.utils.helpers import (
    strip_accents, generate_patient_id, format_number, ensure_dir,
    safe_filename, clear_directory, copy_to_user_input,
)


class TestHelpers:
    def test_strip_accents(self):
        assert strip_accents("EcoCARDIograma") == "ecocardiograma"
        assert strip_accents("FEVI (%)") == "fevi (%)"
        assert strip_accents("ÁéÍóÚ") == "aeiou"

    def test_generate_patient_id_formato(self):
        pid = generate_patient_id()
        assert pid.startswith("PAC-")
        assert len(pid) > len("PAC-")

    def test_format_number(self):
        assert format_number(60.0) == "60.0"
        assert format_number(60.123, decimals=2) == "60.12"
        assert format_number(None) == "-"
        assert format_number("no") == "-"

    def test_ensure_dir_crea(self, tmp_path):
        d = str(tmp_path / "a" / "b")
        ensure_dir(d)
        assert os.path.isdir(d)
        ensure_dir(d)  # idempotente

    def test_safe_filename(self):
        name = safe_filename("informe", ".pdf")
        assert name.startswith("informe_")
        assert name.endswith(".pdf")

    def test_clear_directory(self, tmp_path):
        d = tmp_path / "out"
        d.mkdir()
        (d / "a.txt").write_text("x", encoding="utf-8")
        (d / "b.pdf").write_text("y", encoding="utf-8")
        removed = clear_directory(str(d))
        assert len(removed) == 2
        assert os.listdir(d) == []

    def test_clear_directory_inexistente(self):
        assert clear_directory("/no/existe") == []

    def test_copy_to_user_input(self, tmp_path):
        src = tmp_path / "informe.pdf"
        src.write_text("contenido", encoding="utf-8")
        dest_dir = str(tmp_path / "user_input")
        dest = copy_to_user_input(str(src), dest_dir)
        assert os.path.exists(dest)
        assert os.path.dirname(dest) == dest_dir
        with open(dest, "r", encoding="utf-8") as f:
            assert f.read() == "contenido"
