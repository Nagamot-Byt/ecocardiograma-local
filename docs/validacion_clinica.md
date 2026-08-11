# Validación clínica de rangos y recomendaciones

Proyecto: **Ecocardiograma Local** (v1.0.2)
Propósito: documento de trabajo para que un cardiólogo avale o ajuste (a) los
rangos de referencia usados por el validador y (b) los textos de las
recomendaciones por reglas que se incluyen en el PDF.

**ADVERTENCIA:** las recomendaciones automáticas NO constituyen un diagnóstico.
Son orientaciones objetivas que acompañan al informe para el médico tratante.
El informe final siempre debe ser revisado y firmado por un profesional.

---

## 1. Rangos de referencia activos

Guía: **Guias Colombianas SCC/LATAM** (`src/models/colombian_reference.py`),
con ajuste por altitud para PSAP (Bogotá por defecto, 2640 msnm).

| # | Parámetro | Unidad | Hombres | Mujeres | Fuente |
|---|-----------|--------|---------|---------|--------|
| 1 | DDI (diámetro diastólico VI) | mm | 42 – 56 | 38 – 50 | ASE/SCC |
| 2 | DSI (diámetro sistólico VI) | mm | 23 – 37 | 21 – 33 | ASE/SCC |
| 3 | PPVI (pared posterior VI) | mm | 8 – 10.5 | 7 – 9.5 | ASE/SCC |
| 4 | SIVI (septum interventricular) | mm | 8 – 11.5 | 7 – 10.5 | ASE/SCC |
| 5 | Masa VI | g | ≤ 220 | ≤ 155 | ASE/SCC |
| 6 | Masa VI indexada | g/m² | ≤ 110 | ≤ 88 | ASE/SCC |
| 7 | RVDI (volumen diastólico) | ml | 62 – 145 | 46 – 115 | ASE/SCC |
| 8 | RVSI (volumen sistólico) | ml | 22 – 58 | 15 – 48 | ASE/SCC |
| 9 | FEVI | % | 54 – 72 | 55 – 74 | ASE/SCC |
| 10 | Diámetro AI | mm | ≤ 39 | ≤ 37 | ASE/SCC |
| 11 | Volumen AI indexado | ml/m² | ≤ 32 | ≤ 32 | ASE/SCC |
| 12 | Diámetro VD | mm | ≤ 41 | ≤ 39 | ASE/SCC |
| 13 | TAPSE | mm | ≥ 17 | ≥ 16 | ASE/SCC |
| 14 | FSR (fracción de acortamiento VD) | % | ≥ 33 | ≥ 33 | ASE/SCC |
| 15 | Gradiente medio MI | mmHg | ≤ 5 | ≤ 5 | ASE/SCC |
| 16 | Gradiente máximo MI | mmHg | ≤ 10 | ≤ 10 | ASE/SCC |
| 17 | Área MI | cm² | ≥ 4 | ≥ 4 | ASE/SCC |
| 18 | Gradiente medio AO | mmHg | ≤ 12 | ≤ 12 | ASE/SCC |
| 19 | Gradiente máximo AO | mmHg | ≤ 20 | ≤ 20 | ASE/SCC |
| 20 | Área AO | cm² | ≥ 3 | ≥ 2.5 | ASE/SCC |
| 21 | Vel. insuficiencia AO | m/s | ≤ 2.5 | ≤ 2.4 | ASE/SCC |
| 22 | PSAP | mmHg | ≤ 30* | ≤ 30* | SCC (altitud) |

\* PSAP ajustado por altitud: `límite = 30 + altitud_msnm / 330` mmHg
(~1 mmHg por cada 330 msnm; a 2640 msnm ≈ 38.0 mmHg). Base: guía colombiana.

Nota: los archivos `data/ase_references/hombres.xlsx` y `mujeres.xlsx` contienen
una variante ASE con límites ligeramente distintos (p. ej. FEVI 52–72 H / 54–74 M,
masa 230/162 g). El validador en la aplicación usa los rangos SCC/LATAM de la
tabla anterior; los xlsx se mantienen como respaldo documental.

---

## 2. Recomendaciones por reglas (22)

Generadas por `src/core/recommendations.py` cuando el valor está fuera de rango.
Se agregan al PDF en la sección "Sugerencias de Seguimiento", independientes de
la impresión clínica de la IA.

| # | Parámetro que dispara la regla | Valor anormal | Texto mostrado en el PDF |
|---|-------------------------------|---------------|--------------------------|
| 1 | FEVI | Bajo | FEVI reducida: valorar disfunción sistólica del ventrículo izquierdo y seguimiento ecocardiográfico. |
| 2 | FEVI | Elevado | FEVI preservada. |
| 3 | DDI | Elevado | Diámetro diastólico elevado: valorar dilatación del ventrículo izquierdo. |
| 4 | DSI | Elevado | Diámetro sistólico elevado: valorar dilatación o disfunción del ventrículo izquierdo. |
| 5 | PPVI | Elevado | Grosor de pared posterior elevado: valorar hipertrofia ventricular izquierda. |
| 6 | SIVI | Elevado | Septum interventricular engrosado: valorar hipertrofia ventricular izquierda. |
| 7 | Masa VI indexada | Elevado | Índice de masa ventricular elevado: valorar hipertrofia ventricular izquierda. |
| 8 | Masa VI | Elevado | Masa ventricular elevada: valorar hipertrofia ventricular izquierda. |
| 9 | RVDI | Elevado | Volumen diastólico elevado: valorar dilatación del ventrículo izquierdo. |
| 10 | RVSI | Elevado | Volumen sistólico elevado: valorar dilatación o disfunción del ventrículo izquierdo. |
| 11 | Diámetro AI | Elevado | Aurícula izquierda dilatada: valorar presiones de llenado y fibrilación auricular. |
| 12 | Volumen AI indexado | Elevado | Volumen auricular elevado: valorar dilatación de la aurícula izquierda. |
| 13 | Diámetro VD | Elevado | Ventrículo derecho dilatado: valorar patología del ventrículo derecho. |
| 14 | TAPSE | Bajo | TAPSE reducido: valorar función del ventrículo derecho. |
| 15 | FSR | Bajo | FSR reducido: valorar función sistólica del ventrículo derecho. |
| 16 | Gradiente medio MI | Elevado | Gradiente medio mitral elevado: valorar estenosis mitral. |
| 17 | Gradiente máximo MI | Elevado | Gradiente máximo mitral elevado: valorar estenosis mitral. |
| 18 | Área MI | Bajo | Área mitral reducida: valorar estenosis mitral. |
| 19 | Gradiente medio AO | Elevado | Gradiente medio aórtico elevado: valorar estenosis aórtica. |
| 20 | Gradiente máximo AO | Elevado | Gradiente máximo aórtico elevado: valorar estenosis aórtica. |
| 21 | Área AO | Bajo | Área aórtica reducida: valorar estenosis aórtica. |
| 22 | Vel. insuficiencia AO | Elevado | Velocidad de insuficiencia aórtica elevada: valorar el grado de regurgitación. |
| 23 | PSAP | Bajo | PSAP bajo: correlacionar clínicamente (puede reflejar baja presión de llenado). |
| 24 | PSAP | Elevado | PSAP elevado: valorar hipertensión pulmonar (ajustado por altitud). |

---

## 3. Registro de revisión (para el cardiólogo)

Estado: **pendiente de aval**. Por favor marque cada fila y anote ajustes.

| # | Aprobado (Sí/No) | Ajuste propuesto | Firma |
|---|------------------|------------------|-------|
| 1 | ☐ | | |
| 2 | ☐ | | |
| 3 | ☐ | | |
| 4 | ☐ | | |
| 5 | ☐ | | |
| 6 | ☐ | | |
| 7 | ☐ | | |
| 8 | ☐ | | |
| 9 | ☐ | | |
| 10 | ☐ | | |
| 11 | ☐ | | |
| 12 | ☐ | | |
| 13 | ☐ | | |
| 14 | ☐ | | |
| 15 | ☐ | | |
| 16 | ☐ | | |
| 17 | ☐ | | |
| 18 | ☐ | | |
| 19 | ☐ | | |
| 20 | ☐ | | |
| 21 | ☐ | | |
| 22 | ☐ | | |
| 23 | ☐ | | |
| 24 | ☐ | | |

Revisado por: ______________________  Fecha: ____/____/____  Especialidad: ________

---

## 4. Cómo cambiar un rango o texto (implementación)

- Rangos SCC/LATAM: `src/models/colombian_reference.py` → dict `COLOMBIAN_RANGES`.
- Ajuste de PSAP por altitud: `psap_upper_limit()` (mismo archivo).
- Textos de recomendaciones: `src/core/recommendations.py` → lista `_RULES`.
- Validación de cobertura: `tests/test_recommendations.py` y `tests/test_validator.py`.
