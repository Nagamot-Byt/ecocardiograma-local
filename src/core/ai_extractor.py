"""
Motor de extraccion inteligente de datos de ecocardiograma.

Usa una IA local (Ollama, modelo < 7B) para leer el texto de un informe
ecocardiografico y extraer:
  - Parametros numericos (DDI, DSI, FEVI, PSAP, etc.)
  - Hallazgos visuales (insuficiencias, derrame, contractilidad)
  - Datos del paciente (sexo, edad, medico, fecha, notas)

Estrategia de estabilidad (en cascada):
  1. Si Ollama esta disponible y configurado -> extraccion con IA (JSON estructurado).
  2. Se "mezclan" los resultados de la IA con la extraccion por reglas (regex):
     la IA llena lo que entiende y el regex rellena los vacios. Asi la salida
     nunca queda incompleta si el modelo omite un parametro.
  3. Si Ollama no responde -> extraccion puramente por reglas (la app siempre funciona).
"""
import json
import os
import re
import subprocess
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import requests

from src.models.param_registry import build_param_specs
from src.utils.logger import setup_logger

logger = setup_logger()

# ---------------------------------------------------------------------------
# Definicion de parametros: clave interna = atributo de Patient
# Fuente unica de verdad: src.models.param_registry
# ---------------------------------------------------------------------------

PARAM_SPECS: Dict[str, Dict[str, Any]] = build_param_specs()

# Opciones canonicas para hallazgos visuales
OPCIONES_INSUFICIENCIA = ["No", "Leve", "Moderada", "Severa", "Grave"]
OPCIONES_DERRAME = ["No", "Minimo", "Moderado", "Severo", "Grave"]
OPCIONES_CONTRACTILIDAD = [
    "Normal", "Hipocinetica generalizada", "Hipocinetica segmentaria",
    "Acinetica", "Discinetica",
]

VISUAL_FIELDS = [
    "insuficiencia_mitral", "insuficiencia_aortica",
    "insuficiencia_tricuspidea", "insuficiencia_pulmonar",
    "derrame_pericardico", "contractilidad",
    "segmentos_afectados", "observaciones_visuales",
]

# ---------------------------------------------------------------------------
# Utilidades de normalizacion
# ---------------------------------------------------------------------------


def strip_accents(text: str) -> str:
    """Elimina acentos y normaliza a minusculas, sin caracteres especiales."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.lower()


def to_number(value: Any) -> Optional[float]:
    """Convierte un valor a float, manejando coma decimal y None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def in_bounds(key: str, value: float) -> bool:
    """Verifica que el valor este dentro de los limites plausibles del parametro."""
    spec = PARAM_SPECS.get(key)
    if not spec:
        return False
    return spec["min"] <= value <= spec["max"]


# ---------------------------------------------------------------------------
# Extraccion por reglas (regex) - fallback deterministico
# ---------------------------------------------------------------------------

def _alias_pattern(alias: str) -> str:
    """Convierte un alias en patron regex flexible (espacios/puntos y mayusculas)."""
    norm = strip_accents(alias)
    escaped = re.escape(norm)
    return escaped.replace(r"\ ", r"[\s.]*")


def _param_value_pattern(alias: str) -> str:
    """Patron que captura el valor (y unidad, si la hay) despues de un alias."""
    pat = _alias_pattern(alias)
    return (
        r"\b" + pat +
        r"[.\s]*(?:\([^)]*\))?\)?\s*[:.]?\s*(\d+(?:[.,]\d+)?)"
        r"\s*(cm|mm)?"
    )


def _convert_to_spec_unit(value: float, detected: Optional[str], spec: Dict[str, Any]) -> float:
    """Convierte un valor capturado a la unidad canonica del parametro.

    Ejemplos: "DDI: 5,4 cm" -> 54 mm; "Area MI: 480 mm2" -> 4.8 cm2.
    """
    if not detected or not spec:
        return value
    unit = strip_accents(str(spec.get("unit", ""))).replace("²", "2").replace("³", "3")
    detected = detected.lower()

    if detected == "cm":
        if unit == "mm":
            return value * 10
        if unit == "cm2":
            return value  # ya en cm2
        if unit == "mm2":
            return value * 100
    elif detected == "mm":
        if unit == "cm":
            return value / 10
        if unit == "cm2":
            return value / 100  # 480 mm2 = 4.8 cm2
    return value


# Patrones de alias precompilados, ordenados por longitud de alias (descendente).
# Precompilar evita reconstruir/reescuchar la cadena en cada busqueda, lo que
# acelera notablemente documentos largos (OCR con cientos de lineas).
_PARAM_PATTERNS: Optional[List[Tuple[str, str, "re.Pattern"]]] = None


def _param_patterns() -> List[Tuple[str, str, "re.Pattern"]]:
    """Retorna (key, alias, patron_compilado) ordenados por largo de alias desc."""
    global _PARAM_PATTERNS
    if _PARAM_PATTERNS is None:
        items = [
            (key, alias, re.compile(_param_value_pattern(alias), re.IGNORECASE))
            for key, spec in PARAM_SPECS.items()
            for alias in spec["aliases"]
        ]
        items.sort(key=lambda t: len(t[1]), reverse=True)
        _PARAM_PATTERNS = items
    return _PARAM_PATTERNS


def _match_compiled(
    compiled: "re.Pattern", search_text: str, spec: Optional[Dict[str, Any]] = None
) -> Optional[float]:
    """Busca el valor numerico de un alias precompilado (en la unidad del parametro)."""
    m = compiled.search(search_text)
    if not m:
        return None
    value = to_number(m.group(1))
    if value is None:
        return None
    return _convert_to_spec_unit(value, m.group(2), spec)


# Fase C: patron por parametro precompilado (formato "Estado (valor > ref)").
_FASE_C_PATTERNS: Dict[str, "re.Pattern"] = {}


def _fase_c_pattern(key: str) -> "re.Pattern":
    if key not in _FASE_C_PATTERNS:
        spec = PARAM_SPECS[key]
        alts = [a for a in spec["aliases"] if len(a) > 3]
        _FASE_C_PATTERNS[key] = re.compile(
            r"\b(" + "|".join(re.escape(a) for a in alts)
            + r")\s*\([^)]*\)\s*:\s*(?:Elevado|Bajo|Normal|Alto)\s*\((\d+(?:[.,]\d+))",
            re.IGNORECASE,
        )
    return _FASE_C_PATTERNS[key]


def extract_numeric_params_regex(text: str) -> Dict[str, Tuple[float, float]]:
    """
    Extrae parametros numericos por regex.
    Retorna {key: (valor, confianza)}.

    Estrategia:
      A. Por linea: cada linea asigna UN parametro (el de alias mas largo),
         evitando colisiones como "volumen diastolico vi" vs "diastolico vi".
      B. Texto completo: rellena parametros faltantes (documentos de una linea).
      C. Formato "Estado (valor > ref)" del reporte validado.
    """
    full_text = text.replace("\r", "").replace("\n", " ")
    lines = text.replace("\r", "").split("\n")

    # Se normaliza el texto (sin acentos, minusculas) para que los alias con
    # acentos ("Área") matcheen documentos que los escriben sin acento y viceversa.
    # Los valores capturados son numericos, asi que la normalizacion no los altera.
    full_text = strip_accents(full_text)
    lines = [strip_accents(ln) for ln in lines]

    results: Dict[str, float] = {}
    conf: Dict[str, float] = {}

    def best_match_for(search_text: str) -> Optional[Tuple[str, float]]:
        """Retorna el (key, valor) con el alias mas largo que aparezca en el texto."""
        for key, _alias, compiled in _param_patterns():
            if key in results:
                continue
            value = _match_compiled(compiled, search_text, PARAM_SPECS[key])
            if value is not None and in_bounds(key, value):
                return key, value
        return None

    # Fase A: por linea
    for line in lines:
        line = line.strip()
        if not line or len(line) < 4:
            continue
        hit = best_match_for(line)
        if hit:
            key, value = hit
            results[key] = value
            conf[key] = 0.85

    # Fase B: texto completo (rellena faltantes)
    for key, _alias, compiled in _param_patterns():
        if key in results:
            continue
        value = _match_compiled(compiled, full_text, PARAM_SPECS[key])
        if value is not None and in_bounds(key, value):
            results[key] = value
            conf[key] = 0.75

    # Fase C: formato "Parametro (unit): Estado (valor unit > ref)"
    for key in PARAM_SPECS:
        if key in results:
            continue
        m = _fase_c_pattern(key).search(full_text)
        if m:
            value = to_number(m.group(2))
            if value is not None and in_bounds(key, value):
                results[key] = value
                conf[key] = 0.9

    return {k: (v, conf.get(k, 0.7)) for k, v in results.items()}


def _normalize_severity(raw: str) -> str:
    """Mapea un texto de severidad a la opcion canonica."""
    t = strip_accents(raw)
    mapa = [
        (["no", "negativo", "ausente", "sin"], "No"),
        (["trivial", "minimo", "mínimo", "discreta", "ligera"], "Leve"),
        (["leve"], "Leve"),
        (["moderada", "moderado"], "Moderada"),
        (["severa", "severo", "grave", "importante"], "Severa"),
        (["importante"], "Severa"),
    ]
    for keys, value in mapa:
        if any(k in t for k in keys):
            return value
    return "No"


def extract_visual_regex(text: str) -> Dict[str, str]:
    """Extrae hallazgos visuales por regex (trabaja sobre texto sin acentos)."""
    visual: Dict[str, str] = {
        "insuficiencia_mitral": "No",
        "insuficiencia_aortica": "No",
        "insuficiencia_tricuspidea": "No",
        "insuficiencia_pulmonar": "No",
        "derrame_pericardico": "No",
        "contractilidad": "Normal",
        "segmentos_afectados": "",
        "observaciones_visuales": "",
    }

    # El texto se normaliza (sin acentos) para robustez, ya que los valores
    # canonicos de salida tampoco llevan acentos.
    norm = strip_accents(text)

    insuf_patterns = {
        "insuficiencia_mitral": r"(?:insuf(?:iciencia)?|regurgitacion)\s*(?:mitral|mi)\s*:\s*(?:grado\s*)?\s*(no|trivial|minimo|leve|discreta|ligera|moderada|severa|grave|importante|\d\s*/?\s*4)",
        "insuficiencia_aortica": r"(?:insuf(?:iciencia)?|regurgitacion)\s*(?:aortica|ao)\s*:\s*(?:grado\s*)?\s*(no|trivial|minimo|leve|discreta|ligera|moderada|severa|grave|importante|\d\s*/?\s*4)",
        "insuficiencia_tricuspidea": r"(?:insuf(?:iciencia)?|regurgitacion)\s*(?:tricuspidea|tricuspide|ti|tc)\s*:\s*(?:grado\s*)?\s*(no|trivial|minimo|leve|discreta|ligera|moderada|severa|grave|importante|\d\s*/?\s*4)",
        "insuficiencia_pulmonar": r"(?:insuf(?:iciencia)?|regurgitacion)\s*(?:pulmonar|valvula pulmonar|vp)\s*:\s*(?:grado\s*)?\s*(no|trivial|minimo|leve|discreta|ligera|moderada|severa|grave|importante|\d\s*/?\s*4)",
    }
    for key, pattern in insuf_patterns.items():
        m = re.search(pattern, norm, re.IGNORECASE)
        if m:
            visual[key] = _normalize_severity(m.group(1))

    derrame = re.search(
        r"(?:derrame|efusion)\s*(?:pericardica|pericardico)\s*:\s*(?:grado\s*)?\s*"
        r"(no|minimo|leve|discreto|moderado|severo|grave|importante)",
        norm, re.IGNORECASE,
    )
    if derrame:
        visual["derrame_pericardico"] = _normalize_severity(derrame.group(1))

    # Contractilidad y segmentos se buscan por linea: la primera que contenga
    # la etiqueta define el valor, y la captura se limita al final de la linea
    # (los valores pueden ir seguidos de otras secciones separadas por un salto).
    for line in norm.split("\n"):
        line = line.strip()
        if not line:
            continue

        m = re.match(r"(?:contractilidad|funcion sistolica)\s*:\s*(.*)", line)
        if m:
            t = m.group(1).strip()
            if "hipocinetic" in t and "segmentaria" in t:
                visual["contractilidad"] = "Hipocinetica segmentaria"
            elif "hipocinetic" in t:
                visual["contractilidad"] = "Hipocinetica generalizada"
            elif "acinetic" in t:
                visual["contractilidad"] = "Acinetica"
            elif "discinetic" in t:
                visual["contractilidad"] = "Discinetica"
            elif "hiper" in t:
                visual["contractilidad"] = "Normal"
            elif "normal" in t:
                visual["contractilidad"] = "Normal"
            else:
                visual["contractilidad"] = t[:50]
            continue

        m = re.match(r"(?:segmentos?\s*afectados?)\s*:\s*(.*)", line)
        if m:
            visual["segmentos_afectados"] = m.group(1).strip()[:200]
            continue

    obs = re.search(
        r"(?:observaciones?\s*(?:visuales)?)\s*:\s*([\s\S]+?)(?:\s{2,}Resumen|\s{2,}Informe|$)",
        norm, re.IGNORECASE,
    )
    if obs:
        visual["observaciones_visuales"] = obs.group(1).strip()[:300]

    return visual


def extract_patient_regex(text: str) -> Dict[str, Any]:
    """Extrae datos del paciente por regex."""
    patient: Dict[str, Any] = {
        "sexo": None, "edad": None, "nombre_medico": None,
        "fecha_estudio": None, "notas": None,
    }

    # Sexo
    m = re.search(r"(?:paciente|sexo|sex)\s*[:\s]*\s*(masculino|masc|hombre|var[oó]n|femenino|fem|mujer)", text, re.IGNORECASE)
    if m:
        patient["sexo"] = "M" if re.search(r"masculino|masc|hombre|var[oó]n", m.group(1), re.IGNORECASE) else "F"
    if not patient["sexo"]:
        if re.search(r"\bmasculino\b", text, re.IGNORECASE):
            patient["sexo"] = "M"
        elif re.search(r"\bfemenino\b", text, re.IGNORECASE):
            patient["sexo"] = "F"
    if not patient["sexo"]:
        sm = re.search(r"(\d+)\s*(?:anos|años|anios)\s*[,.\-]?\s*(masculino|mujer|femenino|hombre|var[oó]n)", text, re.IGNORECASE)
        if sm:
            patient["sexo"] = "F" if re.search(r"femenino|mujer", sm.group(2), re.IGNORECASE) else "M"

    # Edad (acepta grafias "anos", "años" y el error comun "anios")
    for p in [
        r"(?:edad|paciente)\s*[:\s]*\s*(\d{1,3})\s*(?:anos|años|anios)",
        r"(\d{1,3})\s*(?:anos|años|anios)\s*(?:[,.\s]|de\s*edad)",
        r"(\d{1,3})\s*(?:anos|años|anios)",
    ]:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            age = int(m.group(1))
            if 10 < age < 110:
                patient["edad"] = str(age)
                break

    # Medico (acepta mayusculas o minusculas; se normaliza a formato Titulo).
    # Un nombre no debe engullir palabras-clave del informe ("Fecha:", "Sexo:"...).
    _medico_keywords = (
        r"(?:fecha|sexo|edad|paciente|documento|cc|cedula|telefono|tel|"
        r"notas?|observaciones?|conclusion|resumen|n°|num)"
    )
    for p in [
        r"(?:Dr\.?|Dra\.?|Doctor|Doctora)\s+"
        r"([A-Za-zÁÉÍÓÚÑáéíóúñ]+(?:\s+(?!" + _medico_keywords + r"\s*[:.\d]?)[A-Za-zÁÉÍÓÚÑáéíóúñ]+){1,4})",
        r"(?:m[eé]d[ií]c[oó]\s*[:\s]*)\s*(?:Dr\.?|Dra\.?|Doctora?)?\s*"
        r"([A-Za-zÁÉÍÓÚÑáéíóúñ]+(?:\s+(?!" + _medico_keywords + r"\s*[:.\d]?)[A-Za-zÁÉÍÓÚÑáéíóúñ]+){1,4})",
    ]:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            patient["nombre_medico"] = m.group(1).strip().title()
            break

    # Fecha de estudio
    m = re.search(
        r"(?:fecha\s*(?:de\s*)?(?:estudio|ecocardiograma|eco|procedimiento)|fecha[:\s]*)\s*"
        r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})",
        text, re.IGNORECASE,
    )
    if not m:
        m = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", text)
    if m:
        raw = m.group(1) if m.lastindex == 1 else m.group(0)
        parts = re.split(r"[/\-.]", raw)
        if len(parts) == 3:
            day, month, year = parts
            year = year if len(year) == 4 else "20" + year
            patient["fecha_estudio"] = f"{day.zfill(2)}/{month.zfill(2)}/{year}"
        else:
            patient["fecha_estudio"] = raw

    # Notas
    m = re.search(
        r"(?:notas?|observaciones?|comentarios?|conclusion|resumen)\s*[:.\-]?\s*([\s\S]{10,300}?)(?:\n\n|\n[A-ZÁÉÍÓÚÑ]|$)",
        text, re.IGNORECASE,
    )
    if m:
        patient["notas"] = m.group(1).strip()[:300]

    return patient


# ---------------------------------------------------------------------------
# IA local (Ollama)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """Eres un asistente medico experto en ecocardiografia en Colombia.
Analiza el texto de un informe ecocardiografico y extrae TODA la informacion.

PARAMETROS NUMERICOS (usar estas claves): {params}
HALLAZGOS VISUALES (usar estas claves y SOLO estos valores):
  - insuficiencia_mitral/aortica/tricuspidea/pulmonar: "No" | "Leve" | "Moderada" | "Severa" | "Grave"
  - derrame_pericardico: "No" | "Minimo" | "Moderado" | "Severo" | "Grave"
  - contractilidad: "Normal" | "Hipocinetica generalizada" | "Hipocinetica segmentaria" | "Acinetica" | "Discinetica"
  - segmentos_afectados: texto libre o ""
  - observaciones_visuales: texto libre o ""
DATOS DEL PACIENTE:
  - sexo: "M" o "F" o null
  - edad: numero en string o null
  - nombre_medico: string o null
  - fecha_estudio: "DD/MM/AAAA" o null
  - notas: string o null
IMPRESION CLINICA:
  - summary: resumen breve
  - clinicalImpression: impresion clinica (analiza valores vs guia: {guide})
  - recommendations: lista de recomendaciones
  - warnings: lista de alertas

Responde SOLO JSON valido, sin texto adicional. Ejemplo:
{{
  "numericParams": [{{"key": "fevi", "value": 55, "confidence": 0.9}}],
  "visualData": {{"insuficiencia_mitral": "No", "insuficiencia_aortica": "Leve",
    "insuficiencia_tricuspidea": "No", "insuficiencia_pulmonar": "No",
    "derrame_pericardico": "No", "contractilidad": "Normal",
    "segmentos_afectados": "", "observaciones_visuales": ""}},
  "patientData": {{"sexo": "M", "edad": "62", "nombre_medico": "Dr. Juan Perez",
    "fecha_estudio": "06/08/2026", "notas": ""}},
  "summary": "...", "clinicalImpression": "...",
  "recommendations": ["..."], "warnings": ["..."]
}}"""


def check_ollama(base_url: str = "http://localhost:11434", timeout: float = 3.0) -> Tuple[bool, List[str]]:
    """Verifica si Ollama responde y retorna los modelos disponibles."""
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout)
        if resp.status_code != 200:
            return False, []
        models = [m.get("name", "") for m in resp.json().get("models", [])]
        return True, models
    except requests.RequestException:
        return False, []


# ---------------------------------------------------------------------------
# Arranque automatico de Ollama
# ---------------------------------------------------------------------------


def _find_ollama_exe() -> Optional[str]:
    """Localiza el binario de Ollama (PATH o rutas comunes de Windows)."""
    import shutil

    cmd = shutil.which("ollama")
    if cmd:
        return cmd
    for candidate in (
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
        r"C:\Program Files\Ollama\ollama.exe",
        r"C:\Program Files (x86)\Ollama\ollama.exe",
    ):
        if os.path.exists(candidate):
            return candidate
    return None


def _server_ready(base_url: str, timeout: float = 3.0) -> bool:
    """Retorna True si el servidor de Ollama responde en base_url."""
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def _model_available(base_url: str, model: str) -> bool:
    """Retorna True si el modelo (o una variante suya) ya esta descargado."""
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=5.0)
        if resp.status_code != 200:
            return False
        names = {m.get("name", "") for m in resp.json().get("models", [])}
    except (requests.RequestException, ValueError):
        return False
    return any(name == model or name.startswith(model + ":") for name in names)


def _pull_model(base_url: str, model: str, cancel_cb=None) -> str:
    """Descarga el modelo con `ollama pull`. Retorna "ok" | "pull_failed".

    Espera en pasos cortos y revisa ``cancel_cb()`` para poder abandonar la
    espera (p. ej. cuando el usuario cierra la app durante una descarga).
    """
    exe = _find_ollama_exe()
    if not exe:
        return "pull_failed"
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        proc = subprocess.Popen(
            [exe, "pull", model],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        while proc.poll() is None:
            if cancel_cb is not None and cancel_cb():
                logger.info("Descarga del modelo cancelada (cierre de la app).")
                return "pull_failed"
            time.sleep(0.5)
        return "ok" if proc.returncode == 0 else "pull_failed"
    except (OSError, subprocess.TimeoutExpired):
        return "pull_failed"


def ensure_ollama_running(
    base_url: str = "http://localhost:11434",
    model: str = "qwen2.5:3b",
    wait: float = 60.0,
    pull_model: bool = True,
    exe_path: Optional[str] = None,
    progress_cb=None,
    cancel_cb=None,
) -> str:
    """Garantiza Ollama corriendo y (si aplica) el modelo descargado.

    Retorna un codigo de estado:
      "ok"            - servidor listo y modelo disponible (o no requerido)
      "started"       - servidor iniciado ahora (modelo disponible o no requerido)
      "model_pulled"  - modelo descargado ahora
      "not_found"     - Ollama no esta instalado
      "timeout"       - el servidor no respondio a tiempo
      "pull_failed"   - el modelo no pudo descargarse (o la espera fue cancelada)
    """
    if exe_path is None:
        exe_path = _find_ollama_exe()

    if _server_ready(base_url):
        if pull_model and not _model_available(base_url, model):
            if progress_cb:
                progress_cb(f"Descargando modelo {model} (primera vez, puede tardar)...")
            return _pull_model(base_url, model, cancel_cb)
        return "ok"

    if not exe_path:
        return "not_found"

    if progress_cb:
        progress_cb("Iniciando Ollama...")
    flags = 0
    if os.name == "nt":
        flags = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    try:
        subprocess.Popen(
            [exe_path, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )
    except OSError:
        return "not_found"

    deadline = time.time() + wait
    while time.time() < deadline:
        if cancel_cb is not None and cancel_cb():
            return "timeout"
        if _server_ready(base_url):
            if pull_model and not _model_available(base_url, model):
                if progress_cb:
                    progress_cb(f"Descargando modelo {model} (primera vez, puede tardar)...")
                return _pull_model(base_url, model, cancel_cb)
            return "started"
        time.sleep(1.0)
    return "timeout"


def _extract_json_block(text: str) -> Optional[dict]:
    """Extrae el primer objeto JSON valido de una respuesta del modelo."""
    text = text.strip()
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def ollama_extract(
    text: str,
    model: str,
    base_url: str = "http://localhost:11434",
    guide: str = "colombian",
    timeout: float = 300.0,
    auto_start_ollama: bool = True,
    pull_model: bool = True,
    progress_cb=None,
    cancel_cb=None,
) -> Tuple[Optional[dict], str]:
    """Llama a Ollama y retorna (datos_parseados, modo).

    Si ``auto_start_ollama`` es True y el servidor no responde, se intenta
    iniciarlo automaticamente (y descargar el modelo la primera vez).
    """
    if auto_start_ollama:
        status = ensure_ollama_running(
            base_url, model, wait=min(max(timeout, 5.0), 90.0),
            pull_model=pull_model, progress_cb=progress_cb, cancel_cb=cancel_cb,
        )
        if status == "not_found":
            raise RuntimeError(
                "Ollama no esta instalado en este equipo. Instale Ollama desde "
                "https://ollama.com o desactive la IA para usar solo reglas."
            )
        if status == "timeout":
            raise RuntimeError(
                "Ollama no respondio al iniciarlo automaticamente. "
                "Active Ollama manualmente o use solo extraccion por reglas."
            )
        if status == "pull_failed":
            if cancel_cb is not None and cancel_cb():
                # La app se esta cerrando: no continuar a la llamada de IA
                raise RuntimeError("Descarga del modelo cancelada (la aplicacion se esta cerrando).")
            logger.warning("No se pudo descargar el modelo %s; se intentara igual.", model)

    guide_name = "Guias Colombianas SCC/LATAM" if guide == "colombian" else "ASE 2023"
    params_list = ", ".join(sorted(PARAM_SPECS.keys()))
    system = _SYSTEM_PROMPT.format(params=params_list, guide=guide_name)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Texto del documento:\n\n{text}"},
        ],
        "stream": False,
        "format": "json",
    }
    url = f"{base_url.rstrip('/')}/api/chat"
    resp = requests.post(url, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Ollama respondio {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    content = data.get("message", {}).get("content", "")
    parsed = _extract_json_block(content)
    if parsed is None:
        # Ultimo intento: la respuesta puede traer texto antes del JSON
        parsed = _extract_json_block(data.get("response", ""))
    return parsed, "ollama"


# ---------------------------------------------------------------------------
# Fusion y normalizacion
# ---------------------------------------------------------------------------

def _normalize_visual(raw: Dict[str, Any]) -> Dict[str, str]:
    """Normaliza los hallazgos visuales a las opciones canonicas."""
    visual: Dict[str, str] = {
        "insuficiencia_mitral": "No",
        "insuficiencia_aortica": "No",
        "insuficiencia_tricuspidea": "No",
        "insuficiencia_pulmonar": "No",
        "derrame_pericardico": "No",
        "contractilidad": "Normal",
        "segmentos_afectados": "",
        "observaciones_visuales": "",
    }
    if not raw:
        return visual

    for key in ["insuficiencia_mitral", "insuficiencia_aortica",
                "insuficiencia_tricuspidea", "insuficiencia_pulmonar"]:
        val = str(raw.get(key, "")).strip()
        if not val or val.lower() in ("null", "none", "n/a"):
            val = "No"
        norm = _normalize_severity(val)
        visual[key] = norm if norm in OPCIONES_INSUFICIENCIA else "No"

    val = str(raw.get("derrame_pericardico", "")).strip()
    if not val or val.lower() in ("null", "none"):
        val = "No"
    d = _normalize_severity(val)
    mapa_derrame = {"Leve": "Minimo", "Moderada": "Moderado", "Severa": "Severo", "Grave": "Grave", "No": "No"}
    visual["derrame_pericardico"] = mapa_derrame.get(d, "No")

    val = str(raw.get("contractilidad", "")).strip()
    if not val or val.lower() in ("null", "none"):
        val = "Normal"
    t = strip_accents(val)
    if "hipocinetic" in t and "segmentaria" in t:
        visual["contractilidad"] = "Hipocinetica segmentaria"
    elif "hipocinetic" in t:
        visual["contractilidad"] = "Hipocinetica generalizada"
    elif "acinetic" in t:
        visual["contractilidad"] = "Acinetica"
    elif "discinetic" in t:
        visual["contractilidad"] = "Discinetica"
    elif "normal" in t or "conservada" in t:
        visual["contractilidad"] = "Normal"

    seg = str(raw.get("segmentos_afectados", "")).strip()
    if seg and seg.lower() not in ("null", "none"):
        visual["segmentos_afectados"] = seg[:200]

    obs = str(raw.get("observaciones_visuales", "")).strip()
    if obs and obs.lower() not in ("null", "none"):
        visual["observaciones_visuales"] = obs[:300]

    return visual


def _normalize_patient(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza los datos del paciente."""
    patient: Dict[str, Any] = {
        "sexo": None, "edad": None, "nombre_medico": None,
        "fecha_estudio": None, "notas": None,
    }
    if not raw:
        return patient

    sexo = str(raw.get("sexo", "")).strip().upper() if raw.get("sexo") is not None else ""
    if sexo in ("M", "MASCULINO", "HOMBRE"):
        patient["sexo"] = "M"
    elif sexo in ("F", "FEMENINO", "MUJER"):
        patient["sexo"] = "F"

    edad = to_number(raw.get("edad"))
    if edad is not None and 10 < edad < 110:
        patient["edad"] = str(int(edad))

    med = str(raw.get("nombre_medico", "")).strip()
    if med and med.lower() not in ("null", "none"):
        patient["nombre_medico"] = med[:80]

    fecha = str(raw.get("fecha_estudio", "")).strip()
    m = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", fecha)
    if m:
        y = m.group(3) if len(m.group(3)) == 4 else "20" + m.group(3)
        patient["fecha_estudio"] = f"{m.group(1).zfill(2)}/{m.group(2).zfill(2)}/{y}"

    notas = str(raw.get("notas", "")).strip()
    if notas and notas.lower() not in ("null", "none"):
        patient["notas"] = notas[:300]

    return patient


def _numeric_from_ai(ai: dict) -> Dict[str, Tuple[float, float]]:
    """Convierte numericParams de la IA a {key: (valor, confianza)}."""
    result: Dict[str, Tuple[float, float]] = {}
    for p in ai.get("numericParams", []) or []:
        key = str(p.get("key", "")).strip()
        value = to_number(p.get("value"))
        conf = to_number(p.get("confidence")) or 0.7
        if key in PARAM_SPECS and value is not None and in_bounds(key, value):
            result[key] = (value, min(max(conf, 0.0), 1.0))
    return result


# ---------------------------------------------------------------------------
# Resultado y orquestacion principal
# ---------------------------------------------------------------------------

@dataclass
class ExtractionResult:
    """Resultado estructurado de la extraccion."""
    source: str = "desconocido"
    numeric_params: Dict[str, float] = field(default_factory=dict)
    numeric_confidence: Dict[str, float] = field(default_factory=dict)
    visual_data: Dict[str, str] = field(default_factory=dict)
    patient_data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    warnings: List[str] = field(default_factory=list)
    summary: str = ""
    clinical_impression: str = ""
    recommendations: List[str] = field(default_factory=list)
    raw_text: str = ""
    model: str = ""
    processing_time: float = 0.0


def _values_close(a: float, b: float, rel: float = 0.05, abs_tol: float = 0.5) -> bool:
    """Considera dos valores cercanos (iguales dentro de tolerancia relativa/absoluta)."""
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b)))


# Alias que son solo unidades de medida: su presencia en el texto no respalda
# que la medicion correspondiente este explicitamente mencionada (p. ej. "ml/m2"
# aparece como unidad de cualquier medicion indexada). Se excluyen del chequeo.
_UNIT_ONLY_ALIASES = frozenset({
    "ml/m2", "g/m2", "cm2", "mm2", "m/s", "mmhg", "cm", "mm", "ml", "g", "%",
})


def _mentioned_keys(text: str) -> set:
    """Retorna las claves cuyos alias (>= 4 caracteres) aparecen en el texto normalizado.

    Los alias que son solo unidades de medida se ignoran: no cuentan como
    mencion explicita de un parametro.
    """
    norm = strip_accents(text)
    mentioned = set()
    for key, spec in PARAM_SPECS.items():
        if any(
            len(a) >= 4 and a not in _UNIT_ONLY_ALIASES and a in norm
            for a in spec["aliases"]
        ):
            mentioned.add(key)
    return mentioned


def _merge_numeric(
    ai: Dict[str, Tuple[float, float]],
    regex: Dict[str, Tuple[float, float]],
    mentioned: Optional[set] = None,
) -> Tuple[Dict[str, float], Dict[str, float], List[str]]:
    """
    Mezcla resultados de IA y regex:
      - Ambos: si coinciden (tolerancia) se usa la IA con la mayor confianza;
        si difieren, gana el regex (etiquetado y deterministico) y se advierte.
      - Solo IA: se conserva siempre (evita perder datos legitimos que el regex
        no detecta, p. ej. etiquetas abreviadas); si la clave no aparece en el
        texto se agrega una advertencia para revision manual.
      - Solo regex: se usa directamente.
    """
    merged: Dict[str, float] = {}
    conf: Dict[str, float] = {}
    warnings: List[str] = []

    for key in PARAM_SPECS:
        in_ai = key in ai
        in_rx = key in regex
        if in_ai and in_rx:
            a_val, a_c = ai[key]
            r_val, r_c = regex[key]
            if _values_close(a_val, r_val):
                merged[key], conf[key] = a_val, max(a_c, r_c)
            else:
                merged[key], conf[key] = r_val, r_c
                warnings.append(
                    f"Conflicto IA vs reglas en '{key}' "
                    f"(IA={a_val}, reglas={r_val}). Se usa el valor de reglas."
                )
        elif in_ai:
            merged[key], conf[key] = ai[key]
            if mentioned is not None and key not in mentioned:
                warnings.append(
                    f"Valor de IA para '{key}' no aparece explicitamente en el "
                    "texto; puede requerir revision manual."
                )
        elif in_rx:
            merged[key], conf[key] = regex[key]

    return merged, conf, warnings


def _merge_patient(
    ai: Optional[Dict[str, Any]], regex: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Mezcla datos del paciente: el regex gana por campo, la IA rellena huecos."""
    merged = dict(regex or {})
    for key, value in (ai or {}).items():
        if value not in (None, "") and not merged.get(key):
            merged[key] = value
    return merged


def extract_from_text(
    text: str,
    use_ai: bool = True,
    model: str = "qwen2.5:3b",
    base_url: str = "http://localhost:11434",
    guide: str = "colombian",
    ai_timeout: float = 300.0,
    auto_start_ollama: bool = True,
    pull_model: bool = True,
    progress_cb=None,
    cancel_cb=None,
) -> ExtractionResult:
    """
    Extrae datos de un texto de ecocardiograma.
    Estrategia en cascada: IA (si disponible) + relleno por regex.
    """
    start = time.time()
    text = (text or "").strip()
    result = ExtractionResult(raw_text=text, processing_time=0.0)

    if not text:
        result.source = "vacio"
        result.warnings.append("No hay texto para procesar.")
        return result

    regex_numeric = extract_numeric_params_regex(text)
    regex_visual = extract_visual_regex(text)
    regex_patient = extract_patient_regex(text)

    ai_numeric: Dict[str, Tuple[float, float]] = {}
    ai_visual: Dict[str, Any] = {}
    ai_patient: Dict[str, Any] = {}
    ai_clinical = {}
    model_used = "reglas (regex)"
    source = "regex"

    if use_ai:
        try:
            parsed, _mode = ollama_extract(
                text, model, base_url, guide, ai_timeout,
                auto_start_ollama=auto_start_ollama,
                pull_model=pull_model,
                progress_cb=progress_cb,
                cancel_cb=cancel_cb,
            )
            if parsed:
                ai_numeric = _numeric_from_ai(parsed)
                ai_visual = parsed.get("visualData", {})
                ai_patient = parsed.get("patientData", {})
                ai_clinical = parsed
                model_used = model
                source = "ollama+regex"
            else:
                result.warnings.append(
                    "La IA no devolvio JSON valido. Se uso la extraccion por reglas."
                )
        except requests.RequestException as e:
            result.warnings.append(
                f"Ollama no disponible ({type(e).__name__}). Se uso la extraccion por reglas."
            )
            logger.warning(f"Ollama no disponible: {e}")
        except Exception as e:  # noqa: BLE001 - estabilidad ante cualquier fallo del modelo
            result.warnings.append(
                f"Error de la IA ({e}). Se uso la extraccion por reglas."
            )
            logger.error(f"Error en IA: {e}")

    if ai_numeric:
        source = "ollama+regex"

    merged, conf, merge_warnings = _merge_numeric(
        ai_numeric, regex_numeric, _mentioned_keys(text)
    )
    result.warnings.extend(merge_warnings)

    visual = _normalize_visual(ai_visual) if ai_visual else regex_visual
    # Si la IA no detecto nada visual pero el regex si, preferir el regex
    if ai_visual and not any(ai_visual.values()):
        visual = regex_visual

    # Datos del paciente: el regex (determinista) tiene prioridad por campo y
    # la IA solo rellena los huecos. Asi un valor alucinado por la IA nunca
    # pisa un valor que el regex extrajo correctamente (p. ej. la edad).
    patient = _merge_patient(ai_patient, regex_patient)

    # Impresion clinica de la IA (si existe)
    if ai_clinical:
        result.summary = str(ai_clinical.get("summary", "")).strip()
        result.clinical_impression = str(ai_clinical.get("clinicalImpression", "")).strip()
        recs = ai_clinical.get("recommendations", []) or []
        result.recommendations = [str(r).strip() for r in recs if str(r).strip()][:8]

    result.source = source
    result.numeric_params = merged
    result.numeric_confidence = conf
    result.visual_data = visual
    result.patient_data = patient
    result.model = model_used
    result.processing_time = round(time.time() - start, 2)

    if merged:
        result.confidence = round(sum(conf.values()) / len(conf), 2)
    else:
        result.confidence = 0.0
        result.warnings.append("No se logro extraer parametros numericos del texto.")

    return result


def extract_text_from_pdf(path: str) -> str:
    """Extrae el texto de un PDF usando pypdf."""
    from pypdf import PdfReader

    reader = PdfReader(path)
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 - pagina ilegible no debe romper todo
            continue
    return "\n".join(parts).strip()


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp")

# Limite de tamano de archivos de entrada (evita leer/OcR documentos enormes)
MAX_EXTRACT_FILE_BYTES = 20 * 1024 * 1024  # 20 MB


def _get_tesseract_cmd() -> Optional[str]:
    """Localiza el binario de Tesseract (PATH o rutas comunes de Windows)."""
    import shutil

    cmd = shutil.which("tesseract")
    if cmd:
        return cmd
    for candidate in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    ):
        if os.path.exists(candidate):
            return candidate
    return None


def extract_text_from_image(path: str, lang: str = "spa+eng") -> str:
    """Extrae el texto de una imagen con OCR (Tesseract)."""
    try:
        from PIL import Image
        import pytesseract
    except ImportError as e:
        raise RuntimeError(
            "Se requiere 'pytesseract' y 'pillow' para leer imagenes."
        ) from e

    cmd = _get_tesseract_cmd()
    if cmd is None:
        raise RuntimeError(
            "Tesseract OCR no esta instalado. Instale Tesseract o use PDF/texto."
        )
    pytesseract.pytesseract.tesseract_cmd = cmd

    with Image.open(path) as src:
        img = src.convert("RGB")

    text = pytesseract.image_to_string(img, lang=lang)
    return text.strip()


def extract_text_from_file(path: str) -> str:
    """Extrae texto de un archivo soportado (PDF, imagen con OCR, TXT, CSV)."""
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    if size > MAX_EXTRACT_FILE_BYTES:
        raise ValueError(
            f"El archivo supera el limite de {MAX_EXTRACT_FILE_BYTES // (1024 * 1024)} MB."
        )
    lower = path.lower()
    if lower.endswith(".pdf"):
        return extract_text_from_pdf(path)
    if lower.endswith(IMAGE_EXTENSIONS):
        return extract_text_from_image(path)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read().strip()


def extract_from_file(
    path: str,
    use_ai: bool = True,
    model: str = "qwen2.5:3b",
    base_url: str = "http://localhost:11434",
    guide: str = "colombian",
    ai_timeout: float = 300.0,
    auto_start_ollama: bool = True,
    pull_model: bool = True,
    progress_cb=None,
    cancel_cb=None,
) -> ExtractionResult:
    """Extrae datos desde un archivo (PDF/TXT/CSV) completo."""
    try:
        text = extract_text_from_file(path)
    except Exception as e:  # noqa: BLE001
        logger.error(f"No se pudo leer el archivo {os.path.basename(path)}: {e}")
        result = ExtractionResult(source="error", warnings=[f"No se pudo leer el archivo: {e}"])
        return result

    result = extract_from_text(
        text, use_ai=use_ai, model=model,
        base_url=base_url, guide=guide, ai_timeout=ai_timeout,
        auto_start_ollama=auto_start_ollama,
        pull_model=pull_model,
        progress_cb=progress_cb,
        cancel_cb=cancel_cb,
    )
    return result
