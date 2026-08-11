"""
Configuracion de la aplicacion.
Lee config.yaml y provee los parametros centralizados.
"""
import os
import sys

import yaml
from dataclasses import dataclass, field


@dataclass
class AIConfig:
    """Configuracion del motor de IA local (Ollama)."""
    enabled: bool = True
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:3b"
    timeout: float = 300.0
    use_ai: bool = True  # Si es False, se usa solo extraccion por regex
    auto_start: bool = True  # Iniciar Ollama automaticamente si no responde
    pull_model: bool = True  # Descargar el modelo la primera vez si no existe


@dataclass
class UpdateConfig:
    """Configuracion del verificador de actualizaciones (GitHub Releases)."""
    enabled: bool = False  # Con repo vacio o deshabilitado, el chequeo no se hace
    repo: str = ""         # "usuario/repositorio" en GitHub


@dataclass
class Config:
    """Estructura de configuracion centralizada."""
    base_dir: str = "./data"
    ase_path: str = "./data/ase_references"
    report_template: str = "./data/templates/informe_base.html"
    log_file: str = "./logs/app.log"
    secure_erase: bool = True
    user_input_dir: str = "./data/user_input"
    output_dir: str = "./data/output"
    hombres_file: str = "./data/ase_references/hombres.xlsx"
    mujeres_file: str = "./data/ase_references/mujeres.xlsx"
    guide: str = "colombian"  # "colombian" | "ase"
    altitude_masl: float = 2640.0  # Altitud de la ciudad (ajusta PSAP en guia colombiana)
    max_file_mb: int = 20  # Limite de tamano de archivos a cargar (PDF/TXT/imagen)
    ai: AIConfig = field(default_factory=AIConfig)
    update: UpdateConfig = field(default_factory=UpdateConfig)


def _get_project_root() -> str:
    """Retorna la raiz del proyecto (3 niveles arriba de config.py)."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_data_root() -> str:
    """
    Directorio de escritura para datos en tiempo de ejecucion
    (logs, user_input, output).

    En modo congelado (PyInstaller) se usa %LOCALAPPDATA%\\EcocardiogramaLocal
    para no depender de permisos de la carpeta de instalacion.
    En desarrollo es la raiz del proyecto.
    """
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "EcocardiogramaLocal")
    return _get_project_root()


def _build_ai_config(data: dict) -> AIConfig:
    """Construye AIConfig desde un diccionario (con valores por defecto)."""
    ai = AIConfig()
    ai_data = data.get("ai", {}) or {}
    ai.enabled = bool(ai_data.get("enabled", ai.enabled))
    ai.base_url = str(ai_data.get("base_url", ai.base_url))
    ai.model = str(ai_data.get("model", ai.model))
    try:
        ai.timeout = float(ai_data.get("timeout", ai.timeout))
    except (ValueError, TypeError):
        ai.timeout = AIConfig.timeout
    ai.use_ai = bool(ai_data.get("use_ai", ai.use_ai))
    ai.auto_start = bool(ai_data.get("auto_start", ai.auto_start))
    ai.pull_model = bool(ai_data.get("pull_model", ai.pull_model))
    return ai


def _build_update_config(data: dict) -> UpdateConfig:
    """Construye UpdateConfig desde un diccionario (con valores por defecto)."""
    upd = UpdateConfig()
    upd_data = data.get("update", {}) or {}
    upd.enabled = bool(upd_data.get("enabled", upd.enabled))
    upd.repo = str(upd_data.get("repo", upd.repo)).strip()
    return upd


def load_config(config_path: str = None) -> Config:
    """
    Carga la configuracion desde config.yaml.
    Si no existe el archivo, retorna valores por defecto.
    """
    project_root = _get_project_root()

    if config_path is None:
        config_path = os.path.join(project_root, "configs", "config.yaml")

    cfg = Config()

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            cfg.base_dir = data.get("base_dir", cfg.base_dir)
            cfg.ase_path = data.get("ase_path", cfg.ase_path)
            cfg.report_template = data.get("report_template", cfg.report_template)
            cfg.log_file = data.get("log_file", cfg.log_file)
            cfg.secure_erase = data.get("secure_erase", cfg.secure_erase)
            cfg.user_input_dir = data.get("user_input_dir", cfg.user_input_dir)
            cfg.output_dir = data.get("output_dir", cfg.output_dir)
            cfg.hombres_file = data.get("hombres_file", cfg.hombres_file)
            cfg.mujeres_file = data.get("mujeres_file", cfg.mujeres_file)
            cfg.guide = data.get("guide", cfg.guide)
            try:
                cfg.altitude_masl = float(data.get("altitude_masl", cfg.altitude_masl))
            except (ValueError, TypeError):
                pass  # Mantener el valor por defecto
            try:
                cfg.max_file_mb = int(data.get("max_file_mb", cfg.max_file_mb))
            except (ValueError, TypeError):
                pass  # Mantener el valor por defecto
            cfg.ai = _build_ai_config(data)
            cfg.update = _build_update_config(data)
        except Exception:
            pass  # Usar valores por defecto

    # Resolver rutas: solo lectura contra la raiz del proyecto (_internal en modo
    # congelado) y rutas de escritura contra el data root (%LOCALAPPDATA%).
    project_root = _get_project_root()
    data_root = get_data_root()
    for attr in [
        "base_dir", "ase_path", "report_template", "hombres_file", "mujeres_file",
    ]:
        val = getattr(cfg, attr)
        if val and not os.path.isabs(val):
            setattr(cfg, attr, os.path.normpath(os.path.join(project_root, val)))
    for attr in ["log_file", "user_input_dir", "output_dir"]:
        val = getattr(cfg, attr)
        if val and not os.path.isabs(val):
            setattr(cfg, attr, os.path.normpath(os.path.join(data_root, val)))

    # Normalizar guia
    if cfg.guide not in ("colombian", "ase"):
        cfg.guide = "colombian"

    return cfg
