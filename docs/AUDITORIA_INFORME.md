# AUDITORÍA TÉCNICA END-TO-END — Ecocardiograma Local v1.0.4

**Fecha:** 23/08/2026 · **Alcance:** arquitectura, estabilidad, integridad clínica, IA integrada (Ollama), seguridad y testing E2E.
**Metodología:** auditoría línea a línea + análisis **ToT (Tree of Thoughts)** en 4 ramas de riesgo, con poda de ramas no verificables y verificación empírica de la rama superviviente.

---

## 1. Veredicto ejecutivo

| Dimensión | Antes | Después |
|---|---|---|
| Tests totales | 142 passed / 3 skip | **175 passed** / 3 skip (+33) |
| Cobertura (`--cov=src`) | ~78% (sin medir en local) | **81.7%** (umbral 75% ✔) |
| Ruff | Limpio | Limpio |
| Bugs críticos abiertos | **3** (B1, D1, D3) | 0 |
| Protocolos antifallo explícitos | implícitos dispersos | **P1–P10 documentados y testeado cada uno** |

El proyecto tenía una base sólida (separación gui/core/models/utils, fuente única de verdad, cascadas de fallback, borrado seguro). La auditoría encontró **un bug de seguridad clínica crítica**, dos defectos de concurrencia reales, un hueco de hermeticidad en la suite capaz de descargar 2 GB sin aviso, y varias carencias de robustez en el puente con la IA local. Todo fue corregido y cubierto por tests.

---

## 2. Metodología ToT — ramas analizadas

```
RAÍZ: "¿Dónde puede fallar el sistema end-to-end?"
├── RAMA A · Estabilidad y concurrencia (hilos Qt, cierre, excepciones)
│   ├── A1 carrera GC del hilo de actualizaciones      → CONFIRMADA → corregida
│   ├── A2 closeEvent frágil (fallo abortaba limpieza) → CONFIRMADA → corregida
│   ├── A3 sin excepthook global (PyQt aborta proceso) → CONFIRMADA → corregida
│   └── A4 check_ollama síncrono congela UI            → CONFIRMADA → corregida
├── RAMA B · Integridad clínica de datos
│   ├── B1 _normalize_patient NUNCA llamada (CRÍTICO)  → CONFIRMADA → corregida
│   ├── B2 confianza 0.0 → 0.7 por falsy-or            → CONFIRMADA → corregida
│   ├── B3 switch ai.enabled muerto                    → CONFIRMADA → conectada
│   ├── B4 límite de archivo duplicado e inconsistente → CONFIRMADA → unificado
│   └── B5 solo UTF-8 (Latin-1 garabatea acentos)      → CONFIRMADA → corregida
├── RAMA C · IA integrada orgánica en el sistema
│   ├── C1 sin truncado de contexto (modelo <7B)       → CONFIRMADA → corregida
│   ├── C2 sin reintento ante fallo transitorio        → CONFIRMADA → corregida
│   ├── C3 timeout único mata generaciones largas      → CONFIRMADA → corregida
│   ├── C4 pull de modelo sin chequear disco           → CONFIRMADA → corregida
│   ├── C5 aislamiento de carpetas                     → VERIFICADO OK (§5)
│   ├── C6 escrituras confinadas                       → VERIFICADO OK (§5)
│   └── C7 afirmación "100% offline"                   → VERIFICADO OK (§5)
└── RAMA D · Testing
    ├── D1 suite NO hermética con Ollama real (grave)  → CONFIRMADA+INCIDENTE → candado
    ├── D2 sin tests E2E                               → CONFIRMADA → 8 E2E ToT
    └── D3 inconsistencia regex vs IA en derrame       → DESCUBIERTA POR E2E → corregida
```

Ramas podadas por no ser deterministas en CI (documentadas en los propios tests): auto-arranque real de Ollama, render PDF QPrinter headless (crash conocido fuera de Windows), red externa real.

---

## 3. Hallazgos detallados

### 🔴 F-B1 — Datos del paciente de la IA sin validar *(crítico, seguridad clínica)*
`_normalize_patient()` existía en `ai_extractor.py` pero **nunca era invocada**: la salida `patientData` del modelo se fusionaba cruda. Si la IA devolvía `"sexo": "masculino"` (en vez del canónico `"M"`), `MainWindow._on_apply_extraction` evaluaba `pd["sexo"] == "M" → False` y asignaba **Femenino silenciosamente**; edades imposibles o fechas malformadas entraban al informe.
**Corrección:** fusión vía `_merge_patient(_normalize_patient(ai), regex)` — la normalización es obligatoria antes de tocar al paciente. Test de regresión incluido (`test_hardening.py::TestP1`).

### 🔴 F-D1 — Suite no hermética en máquinas con Ollama real *(grave)*
Los tests que llaman `extract_from_text(use_ai=True)` sin mock funcionaban en CI (sin Ollama) pero en un equipo de desarrollo con Ollama instalado **disparaban arranque automático y descarga real del modelo (~2 GB)**. Durante esta auditoría ocurrió de verdad: `qwen2.5:3b` (1.9 GB) quedó descargado en `~/.ollama`. **Se restauró el estado del sistema** (`ollama rm`, `models: []`) y se añadió `tests/conftest.py`: fixture autouse que neutraliza `_server_ready` y `_find_ollama_exe` para toda la suite (ningún test toca red ni procesos reales; los tests que mockean lo hacen después y ganan).

### 🟠 F-A1 — Carrera del hilo de actualizaciones
`_start_update_check` sobreescribía `self._update_worker` sin comprobar si el anterior corría: doble consulta posible y **GC del QThread vivo** → abort `QThread: Destroyed while thread is still running`. Corregido: guard de solapamiento + patrón `finished → limpiar referencia → deleteLater` (orden garantizado por conexión).

### 🟠 F-A2 — Cierre frágil
En `closeEvent`, cualquier excepción en `shutdown()` dejaba **sin ejecutar el borrado seguro** (PHI temporal en disco tras un crash). Corregido: tres etapas independientes con try propio; el borrado seguro es siempre el último intento.

### 🟠 F-A3 — Sin red global antifallo
PyQt6 aborta el proceso ante excepción no controlada en un slot → muerte sin limpieza. Nuevo `src/utils/error_guard.py`: excepthook que registra traceback completo en log, muestra diálogo acotado (máx. 3, solo hilo UI, desactivable para tests) y **no deja la app en estado indeterminado**. Instalado en `src/main.py`.

### 🟠 F-D3 — Inconsistencia regex vs IA en derrame pericárdico *(descubierta por el E2E)*
`extract_visual_regex` mapeaba `DERRAME PERICARDICO: Minimo → "Leve"` porque usaba la escala genérica de insuficiencias; el remapeo específico `{Leve→Minimo,...}` solo existía en la ruta IA. Dos rutas, dos valores distintos para el mismo hallazgo. Corregido: ambas rutas comparten el mismo mapa canónico.

### 🟡 Menores corregidos
- **B2:** `to_number(conf) or 0.7` convertía confianza explícita 0 en default → ahora solo aplica default si falta.
- **B3:** `config.ai.enabled` se cargaba y jamás se consultaba → gobierna el checkbox inicial de IA.
- **B4:** GUI limitaba con `config.max_file_mb` pero el core con constante fija 20 MB → límite inyectable y unificado.
- **B5:** TXT en Latin-1/Windows-1252 (común en equipos clínicos) garabateaba acentos → fallback de decodificación.
- **P7:** recargar un PDF distinto con el mismo nombre sobrescribía la copia previa en `user_input` → sufijo incremental si el contenido difiere; recargar el mismo archivo es idempotente.
- **Config silenciosa:** YAML roto caía a defaults sin rastro → registra ERROR con el detalle; clamps de sanidad (altitud 0–6000 msnm, `max_file_mb` ≥1, timeout IA 5s–30min).

---

## 4. Protocolos antifallo implementados

| ID | Protocolo | Ubicación | Test |
|---|---|---|---|
| P1 | Normalización obligatoria de datos de paciente de IA | `ai_extractor.extract_from_text` | `TestP1` (3) |
| P2 | Confianza 0.0 preservada; fusión toma máx. con regex | `_numeric_from_ai` / `_merge_numeric` | `TestP2` (2) |
| P3 | Truncado cabeza(2/3)+cola(1/3) a 9k chars p/ modelo <7B | `_truncate_for_model` | `TestP3` (2) |
| P4 | Reintento ×2 ante fallo transitorio; cancelación sin reintento; timeout `(conexión=10s, lectura=N)` | `_post_chat_with_retry` | `TestP4` (3) |
| P5 | Chequeo de espacio (≥3 GB libres) antes de `ollama pull`; fail-open si no se puede medir | `_disk_space_ok`/`_pull_model` | `TestP5` (3) |
| P6 | Clamps de config + error visible de YAML roto | `utils/config.load_config` | `TestP6` (5) |
| P7 | Copias a `user_input` sin colisión silenciosa (idempotente) | `helpers.copy_to_user_input` | `TestP7` (2) |
| P8 | Decodificación Latin-1 heredada para texto plano | `extract_text_from_file` | `TestP8` (2) |
| P9 | Límite de tamaño único configurable core↔GUI | `extract_text_from_file(max_bytes)` | `TestP9` (2) |
| P10 | Excepthook global no fatal, diálogos acotados y seguros | `utils/error_guard.py` + `main.py` | `TestP10` (1) |
| P11 | Hermeticidad total de la suite frente a Ollama real | `tests/conftest.py` (autouse) | transversal |
| P12 | Ciclo de vida seguro de QThreads (ref→None→deleteLater; guards anti-solapamiento) | `main_window` / `ai_tab` | E2E-2/E2E-4 |
| P13 | Cierre resiliente por etapas independientes (borrado seguro siempre intentado) | `MainWindow.closeEvent` | E2E-2 |

---

## 5. Auditoría de la IA integrada — funcionamiento orgánico en el sistema

**Mapa de I/O del motor IA (`ai_extractor.py`):**

| Recurso | Ruta | Lectura/Escritura | Veredicto |
|---|---|---|---|
| Binario Ollama | `PATH`, `%LOCALAPPDATA%\Programs\Ollama`, `Program Files` | lectura/ejecución | ✔ rutas estándar, sin side-effects |
| Modelos descargados | `~/.ollama/models` (gestionado por Ollama, NO por la app) | gestión delegada | ✔ aislamiento correcto: la app nunca escribe ahí |
| Servidor | `http://localhost:11434` (`/api/tags`, `/api/chat`) | red local | ✔ solo loopback; `serve` lanzado detached sobrevive al cierre (por diseño) |
| Documentos usuario | `<data>/user_input` (copia de sesión) | lectura + borrado seguro | ✔ nunca modifica el original (ahora sin colisiones) |
| Informes | `<data>/output` (HTML/PDF temporales) | escritura + borrado seguro | ✔ exportados del usuario intactos (verificado en E2E-2) |
| Logs | `<data>/logs/app.log`, rotación diaria 7 días | escritura + borrado seguro de rotados | ✔ sin PHI sensible identificado |
| Red externa | única excepción: GitHub Releases (updater, GET, timeout 8s) | lectura | ✔ afirmación "100% offline" sostiene el flujo clínico; updater es metadatos, no datos clínicos |

**Defensas anti-alucinación existentes (mantenidas):** regex determinista como columna vertebral, validación contra límites plausibles por parámetro, fusión donde regex gana conflictos, advertencia cuando la IA reporta claves ausentes del texto, JSON forzado (`format:"json"`).
**Añadidas en esta auditoría:** truncado inteligente de entrada (P3), reintento con cancelación cooperativa (P4), timeout dual conexión/lectura (C3), guarda de disco antes de descargar (P5), normalización obligatoria de salida de paciente (P1).

---

## 6. Suite E2E (ToT) — `tests/test_e2e_flow.py`

| Escenario | Ramas enumeradas | Podadas | Verificación de punta a punta |
|---|---|---|---|
| **E2E-1 Ruta clínica offline** | {IA ok \| solo regex \| vacío} | IA (no determinista en CI) | TXT→lectura→extracción→Patient→validación SCC/LATAM (FEVI/DDI/PSAP anómalos detectados)→recomendaciones→informe HTML con trazabilidad→borrado seguro |
| **E2E-2 Ruta GUI completa** | {carga archivo, extrae async, aplica, valida, genera, exporta, cierra} | PDF real headless | Hilos reales (`FileLoadWorker`, `ExtractWorker`), aplicación al informe, salto de pestañas, resumen VALIDACION, exportado sobrevive a la limpieza, cierre ordenado |
| **E2E-3 Resiliencia hostil** | {IA caída, auto-start sin binario, archivo fantasma, YAML roto, texto vacío} | espera de gracia 90s (lenta) | Degradación controlada a regex + advertencias; errores controlados sin crash |
| **E2E-4 Ciclo de sesión** | {huérfanos al arrancar, temporales al cerrar, exportados} | — | Limpieza de crash anterior, limpieza de sesión actual, preservación de exportaciones |

Resultado: **8/8 E2E pasan**; el propio diseño destapó F-D3 y el patrón deleteLater defectuoso antes de llegar a producción.

---

## 7. Verificación final

```text
$ QT_QPA_PLATFORM=offscreen python -m pytest -q --cov=src
175 passed, 3 skipped in ~19s   (cobertura TOTAL 81.70%, umbral 75% ✔)

$ ruff check .
All checks passed!

$ curl localhost:11434/api/tags   → {"models":[]}   # sistema restaurado, sin residuos
```

Cambios: 6 archivos modificados (`ai_extractor.py`, `main_window.py`, `ai_tab.py`, `main.py`, `config.py`, `helpers.py`) + 4 nuevos (`error_guard.py`, `tests/conftest.py`, `tests/test_hardening.py`, `tests/test_e2e_flow.py`). Sin commits (pendiente de tu aprobación).

---

## 8. Riesgos residuales y backlog recomendado

1. **Media:** mover `generate_report` a un worker (hoy bloquea UI durante el render PDF).
2. **Media:** usar `stream:true` en Ollama para progreso real y conexiones vivas en generaciones largas.
3. **Media:** firma/hash del instalador publicado en el propio Release y verificado por el updater (hoy solo SHA manual en README).
4. **Baja:** `_pull_model` sin deadline máximo (solo cancelación cooperativa) — aceptable con P5 y cancelación.
5. **Baja:** `param_registry.get_field` lineal (62% cobertura) — trivialmente cacheable.
6. **Baja:** stylesheet de statusBar persistente entre mensajes (cosmético).

### 8.1 Carencias UI/UX (estado tras P2)

Registradas al revisar la integración de componentes tras el bloque P2 (commit `e26eabc`). Dos coinciden con puntos de este backlog (se enlazan, no se repiten); tres son nuevas.

1. **Media:** `_on_generate_report` corre sincrónico en el hilo de UI (`src/gui/main_window.py:829`) — sin cursor de espera ni botón deshabilitado durante el render: posible "cuelgue" percibido. *Coincide con el punto 1.*
2. **Media:** sin progreso gráfico (`QProgressBar`): la extracción de la pestaña IA solo cambia texto ("Extrayendo datos...") en `lbl_resultado`.
3. **Baja:** los grises `#888`/`#777` de `ai_tab` (`lbl_ollama`, `lbl_pista`) están inline y no responden al modo oscuro (contraste bajo sobre `#2b2b2b`).
4. **Baja:** los colores del statusbar persisten entre mensajes (cosmético). *Coincide con el punto 6.*
5. **Baja:** accesibilidad parcial: solo 6 `setAccessibleName` (header, sexo, validar) frente a decenas de controles interactivos; sin `setStatusTip` en ninguna parte.
