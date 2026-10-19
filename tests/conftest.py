"""Fixtures globales de la suite.

Hermeticidad (protocolo antifallo de testing): en una maquina de desarrollo
CON Ollama real instalado y corriendo, cualquier test que llame a
extract_from_text(use_ai=True) sin mock dispararia el arranque automatico e
incluso una descarga real del modelo (~2 GB). En CI pasa desapercibido porque
no hay Ollama; en equipos locales no.

El fixture autouse aislara el motor de IA para TODOS los tests:
  - _server_ready -> False: nunca se cree que hay servidor local.
  - _find_ollama_exe -> None: nunca se lance binario ni `ollama pull`.
Resultado determinista: ensure_ollama_running devuelve "not_found" ->
RuntimeError controlada -> extraccion por regex. Ningun test toca la red ni
los procesos del sistema.

Un test que necesite otro comportamiento lo sobreescribe con su propio
monkeypatch (se aplica despues del autouse y su teardown restaura primero).
"""
import pytest

import src.core.ai_extractor as ae
from src.utils import error_guard


@pytest.fixture(scope="session", autouse=True)
def aislar_qsettings(tmp_path_factory):
    """Ningun test toca las preferencias reales del usuario.

    Los tests construyen QSettings() sin organizacion ni aplicacion, asi que
    PyQt escribe en ~/.config/Unknown Organization.conf del desarrollador (o
    en el registro en Windows). Se redirige todo a un directorio temporal de
    la sesion con formato INI en las tres plataformas.
    """
    from PyQt6.QtCore import QSettings

    formato = QSettings.Format.IniFormat
    anterior = QSettings.defaultFormat()
    QSettings.setDefaultFormat(formato)
    QSettings.setPath(
        formato, QSettings.Scope.UserScope, str(tmp_path_factory.mktemp("qsettings"))
    )
    yield
    QSettings.setDefaultFormat(anterior)


@pytest.fixture(autouse=True)
def aislar_ollama(monkeypatch):
    monkeypatch.setattr(ae, "_server_ready", lambda *a, **k: False)
    monkeypatch.setattr(ae, "_find_ollama_exe", lambda: None)
    # Ningun dialogo modal del protocolo antifallo dentro de tests
    error_guard.set_dialogs_enabled(False)
    yield


@pytest.fixture(autouse=True)
def aislar_updater(monkeypatch):
    """Ningun test consulta GitHub: el worker de la GUI responde al instante.

    Sin esto, MainWindow lanza un UpdateCheckWorker real (config.update
    habilitado) que consulta api.github.com; si la ventana se destruye con
    el hilo aun corriendo, Qt aborta el proceso. Solo se parchea el nombre
    importado por la GUI: los tests de logica interna de updater.py siguen
    ejercitando la funcion real (con fetch_latest_release mockeado).
    """
    respuesta = {"disponible": False, "version_remota": "", "error": None}
    monkeypatch.setattr(
        "src.gui.main_window.check_for_updates", lambda *a, **k: dict(respuesta)
    )
    yield


@pytest.fixture(autouse=True)
def aislar_ollama_status_worker(monkeypatch):
    """Ningun test arranca el hilo real de chequeo de Ollama de la GUI.

    Cada MainWindow lanza un OllamaStatusWorker (QThread) via
    QTimer.singleShot(0, _refresh_ollama_status). Si un test sobrescribe
    tab._ollama_worker (p. ej. con un doble) mientras ese hilo aun corre,
    CPython destruye el QThread vivo y Qt aborta el proceso
    ('QThread: Destroyed while thread is still running').

    Se sustituye por una version que hereda las senales pero cuyo start()
    no crea hilo: los tests de logica de OllamaStatusWorker.run() usan la
    clase real importada al inicio del modulo de test y no se ven afectados.
    """
    from PyQt6.QtCore import QThread, pyqtSignal

    class _NoopOllamaStatusWorker(QThread):
        checked = pyqtSignal(bool, list)

        def __init__(self, base_url, parent=None):
            super().__init__(parent)
            self.base_url = base_url

        def start(self, priority=None):  # noqa: ARG002 - firma compatible con QThread
            return None

        def run(self):
            return None

    monkeypatch.setattr("src.gui.ai_tab.OllamaStatusWorker", _NoopOllamaStatusWorker)
    yield
