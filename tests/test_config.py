"""Tests de la configuracion (src.utils.config)."""
import os

import pytest
import yaml

from src.utils.config import (
    Config, load_config, get_data_root, _get_project_root, AIConfig,
)


@pytest.fixture
def config_file(tmp_path):
    """Escribe un config.yaml temporal con valores customizados."""
    data = {
        "secure_erase": False,
        "guide": "ase",
        "altitude_masl": 1500.0,
        "ai": {
            "enabled": False,
            "model": "llama3.2:3b",
            "timeout": "abc",  # invalido -> debe conservar el default
        },
    }
    path = tmp_path / "config.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f)
    return str(path)


class TestConfig:
    def test_defaults_sin_archivo(self):
        cfg = load_config("/no/existe/config.yaml")
        assert isinstance(cfg, Config)
        assert cfg.secure_erase is True
        assert cfg.guide == "colombian"
        assert cfg.altitude_masl == 2640.0

    def test_rutas_relativas_se_resuelven(self):
        cfg = load_config("/no/existe/config.yaml")
        assert os.path.isabs(cfg.log_file)
        assert os.path.isabs(cfg.user_input_dir)
        assert os.path.isabs(cfg.report_template)
        assert os.path.isabs(cfg.output_dir)

    def test_rutas_escritura_van_a_data_root(self):
        cfg = load_config("/no/existe/config.yaml")
        assert cfg.log_file.startswith(get_data_root())
        assert cfg.user_input_dir.startswith(get_data_root())
        assert cfg.output_dir.startswith(get_data_root())

    def test_rutas_lectura_van_a_project_root(self):
        cfg = load_config("/no/existe/config.yaml")
        root = _get_project_root()
        assert cfg.report_template.startswith(root)
        assert cfg.ase_path.startswith(root)

    def test_carga_archivo_personalizado(self, config_file):
        cfg = load_config(config_file)
        assert cfg.secure_erase is False
        assert cfg.guide == "ase"
        assert cfg.altitude_masl == 1500.0
        assert cfg.ai.enabled is False
        assert cfg.ai.model == "llama3.2:3b"
        # timeout invalido -> default
        assert cfg.ai.timeout == AIConfig.timeout

    def test_guia_invalida_se_normaliza(self, tmp_path):
        path = tmp_path / "config.yaml"
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump({"guide": "otra_cosa"}, f)
        cfg = load_config(str(path))
        assert cfg.guide == "colombian"

    def test_get_data_root_dev_es_project_root(self):
        assert get_data_root() == _get_project_root()
