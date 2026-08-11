"""Tests del verificador de actualizaciones (src.core.updater)."""
import src.core.updater as updater


class TestParseVersion:
    def test_version_simple(self):
        assert updater.parse_version("1.0.3") == (1, 0, 3)

    def test_version_con_v_prefijo(self):
        assert updater.parse_version("v1.2.3") == (1, 2, 3)

    def test_version_vacia(self):
        assert updater.parse_version("") == (0,)

    def test_version_no_numerica(self):
        assert updater.parse_version("abc") == (0,)

    def test_version_con_sufijo(self):
        assert updater.parse_version("1.0.3-beta.2") == (1, 0, 3)


class TestVersionEsMayor:
    def test_estrictamente_mayor(self):
        assert updater.version_es_mayor("1.0.3", "1.0.2") is True

    def test_igual_no_es_mayor(self):
        assert updater.version_es_mayor("1.0.3", "1.0.3") is False

    def test_menor_no_es_mayor(self):
        assert updater.version_es_mayor("1.0.2", "1.0.3") is False

    def test_mayor_mayor_minor(self):
        assert updater.version_es_mayor("2.0.0", "1.9.9") is True

    def test_remota_invalida_no_es_mayor(self):
        assert updater.version_es_mayor("abc", "1.0.3") is False


class TestCheckForUpdates:
    def test_sin_repo_no_consulta(self, monkeypatch):
        def _explode(*args, **kwargs):
            raise AssertionError("No se debe consultar la red sin repo configurado")

        monkeypatch.setattr(updater, "fetch_latest_release", _explode)
        resultado = updater.check_for_updates("1.0.3", repo="")
        assert resultado["disponible"] is False
        assert resultado["version_remota"] == ""
        assert resultado["error"] is None

    def test_sin_conexion_devuelve_error(self, monkeypatch):
        monkeypatch.setattr(updater, "fetch_latest_release", lambda repo, timeout=10.0: None)
        resultado = updater.check_for_updates("1.0.3", repo="alguien/eco")
        assert resultado["disponible"] is False
        assert resultado["error"]

    def test_hay_version_nueva(self, monkeypatch):
        monkeypatch.setattr(
            updater, "fetch_latest_release", lambda repo, timeout=10.0: "v2.0.0"
        )
        resultado = updater.check_for_updates("1.0.3", repo="alguien/eco")
        assert resultado["disponible"] is True
        assert resultado["version_remota"] == "2.0.0"
        assert resultado["error"] is None

    def test_misma_version_no_es_actualizacion(self, monkeypatch):
        monkeypatch.setattr(
            updater, "fetch_latest_release", lambda repo, timeout=10.0: "1.0.3"
        )
        resultado = updater.check_for_updates("1.0.3", repo="alguien/eco")
        assert resultado["disponible"] is False
        assert resultado["error"] is None

    def test_version_remota_menor_no_es_actualizacion(self, monkeypatch):
        monkeypatch.setattr(
            updater, "fetch_latest_release", lambda repo, timeout=10.0: "0.9.0"
        )
        resultado = updater.check_for_updates("1.0.3", repo="alguien/eco")
        assert resultado["disponible"] is False
        assert resultado["error"] is None
