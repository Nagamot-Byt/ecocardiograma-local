"""Tests unitarios para SecureDelete."""
import os
from src.core.secure_delete import secure_delete_file, secure_delete_directory, SecureDeleter


class TestSecureDelete:
    def test_secure_delete_file(self, tmp_path):
        filepath = tmp_path / "test_secret.txt"
        filepath.write_text("Datos clinicos sensibles")

        assert os.path.exists(filepath)
        result = secure_delete_file(str(filepath))
        assert result is True
        assert not os.path.exists(filepath)

    def test_secure_delete_nonexistent_file(self):
        result = secure_delete_file("/nonexistent/file.txt")
        assert result is True  # No existe, se considera exitoso

    def test_secure_delete_directory(self, tmp_path):
        # Crear archivos en directorio
        dir_path = tmp_path / "temp_data"
        dir_path.mkdir()
        (dir_path / "file1.txt").write_text("data1")
        (dir_path / "file2.txt").write_text("data2")

        removed = secure_delete_directory(str(dir_path))
        assert len(removed) == 2

    def test_secure_delete_empty_directory(self, tmp_path):
        dir_path = tmp_path / "empty"
        dir_path.mkdir()

        removed = secure_delete_directory(str(dir_path))
        assert len(removed) == 0

    def test_secure_deleter_clean_session(self, tmp_path):
        input_dir = tmp_path / "user_input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        # Crear archivos
        (input_dir / "data.xlsx").write_text("temp data")
        (output_dir / "report.pdf").write_text("report data")
        (output_dir / "report.html").write_text("temp html")

        deleter = SecureDeleter(str(input_dir), str(output_dir), enabled=True)
        result = deleter.clean_session()

        # HTML y PDF temporales del output y el input se borran de forma segura
        assert result["total"] == 3
        assert not (output_dir / "report.pdf").exists()
        assert not (output_dir / "report.html").exists()
        assert not (input_dir / "data.xlsx").exists()

    def test_secure_deleter_disabled(self, tmp_path):
        input_dir = tmp_path / "user_input"
        input_dir.mkdir()
        (input_dir / "data.xlsx").write_text("temp data")

        deleter = SecureDeleter(str(input_dir), str(tmp_path / "output"), enabled=False)
        result = deleter.clean_session()

        assert result["total"] == 0
        assert os.path.exists(input_dir / "data.xlsx")  # No se borra
