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


@pytest.fixture(autouse=True)
def aislar_ollama(monkeypatch):
    monkeypatch.setattr(ae, "_server_ready", lambda *a, **k: False)
    monkeypatch.setattr(ae, "_find_ollama_exe", lambda: None)
    # Ningun dialogo modal del protocolo antifallo dentro de tests
    error_guard.set_dialogs_enabled(False)
    yield
