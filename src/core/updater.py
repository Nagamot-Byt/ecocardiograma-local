"""
Verificador de actualizaciones contra GitHub Releases.

Consulta la API publica de GitHub (https://api.github.com/repos/{repo}/releases/latest)
y compara la version publicada con la version instalada. Toda la logica de red
esta aislada para poder probarse sin conexion; la GUI la invoca desde un hilo.
"""
import json
import re
import urllib.request
from typing import Optional, Tuple

from src.core.version import APP_VERSION

_GITHUB_API = "https://api.github.com/repos/{repo}/releases/latest"


def parse_version(version: str) -> Tuple[int, ...]:
    """Convierte 'v1.2.3' / '1.2.3' en una tupla comparable (1, 2, 3).

    Devuelve (0,) si no puede interpretar la version.
    """
    if not version:
        return (0,)
    match = re.search(r"(\d+(?:\.\d+)+)", str(version))
    if not match:
        return (0,)
    return tuple(int(p) for p in match.group(1).split("."))


def version_es_mayor(version_a: str, version_b: str) -> bool:
    """True si ``version_a`` es estrictamente mayor que ``version_b``."""
    return parse_version(version_a) > parse_version(version_b)


def _get_json(url: str, timeout: float) -> Optional[dict]:
    # Defensa en profundidad: solo se consulta el dominio oficial de la API,
    # con esquema https explicito (auditado por bandit B310).
    if not str(url).startswith("https://api.github.com/"):
        return None
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "EcocardiogramaLocal-updater", "Accept": "application/vnd.github+json"}
        )
        with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310
            parsed = json.loads(resp.read().decode("utf-8"))
            # Contrato: siempre dict o None. Un endpoint comprometido/roto que
            # devuelva una lista u otro tipo no debe tumbar al llamador.
            return parsed if isinstance(parsed, dict) else None
    except Exception:  # noqa: BLE001 - la red falla de muchas formas; siempre devolver None
        return None


def fetch_latest_release(repo: str, timeout: float = 10.0) -> Optional[str]:
    """Retorna el tag_name de la ultima release de ``repo`` (o None si falla)."""
    data = _get_json(_GITHUB_API.format(repo=repo), timeout)
    # Doble defensa: aunque _get_json ya solo devuelve dicts, el consumidor
    # no confia en el contrato por si el origen cambia (fail-safe).
    if not isinstance(data, dict):
        return None
    return data.get("tag_name")


def check_for_updates(
    current_version: str = APP_VERSION,
    repo: str = "",
    timeout: float = 10.0,
) -> dict:
    """
    Comprueba si hay una version mas reciente publicada en GitHub.

    Retorna:
      {disponible: bool, version_remota: str, error: str|None}
    - disponible=True solo si repo esta configurado, hay red y la version
      remota es estrictamente mayor.
    - error describe por que no se pudo comprobar (sin lanzar excepciones).
    """
    if not repo:
        return {"disponible": False, "version_remota": "", "error": None}

    tag = fetch_latest_release(repo, timeout)
    if not tag:
        return {
            "disponible": False,
            "version_remota": "",
            "error": "No se pudo consultar GitHub (sin conexion o repositorio inexistente).",
        }

    version_remota = str(tag).lstrip("v")
    disponible = version_es_mayor(version_remota, current_version)
    return {
        "disponible": disponible,
        "version_remota": version_remota,
        "error": None,
    }
