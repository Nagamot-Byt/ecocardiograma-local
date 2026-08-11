# Golden set de validación

Proyecto: **Ecocardiograma Local** (v1.0.2)
Los casos de referencia viven en `data/golden_set/cases.json` y se ejecutan con
`tests/test_golden_set.py`. Su propósito: fijar el comportamiento esperado de la
**validación** (rangos SCC/LATAM por sexo y altitud) y de las **recomendaciones
por reglas**, de modo que un cambio no rompa silenciosamente los resultados.

## Cómo medirlo

```powershell
venv\Scripts\python.exe -m pytest tests/test_golden_set.py -q
```

El test convierte cada caso en un `Patient`, lo valida con
`load_colombian_references(altitud)` y compara **exactamente** contra lo
esperado: parámetros anormales y lista de recomendaciones.

## Cobertura de la extracción por IA

El golden set fija el resultado de validación + recomendaciones. La **extracción
IA** (texto del informe → campos) se valida aparte con el flujo de
`tests/test_ai_extractor.py`. Para medir el desempeño de la extracción sobre
informes reales aún se requiere un set de informes anonimizados con la medición
esperada (pendiente; ver "Siguientes pasos").

## Casos incluidos

| ID | Caso | Sexo | Anomalías esperadas | Recomendaciones |
|----|------|------|---------------------|-----------------|
| G001 | Varón adulto sano | M | ninguna | ninguna |
| G002 | FEVI reducida + VI dilatado | M | DDI, DSI, RVDI, RVSI, FEVI | 5 (disfunción sistólica + dilatación) |
| G003 | HVI concéntrica | F | PPVI, SIVI, Masa VI, Masa VI ind. | 4 (hipertrofia) |
| G004 | Estenosis mitral severa + AI dilatada | F | Grad. medio/máx MI, Área MI, Diám. AI, Vol. AI, PSAP | 6 (estenosis mitral + dilatación AI + PSAP) |
| G005 | Estenosis aórtica severa | M | Grad. medio/máx AO, Área AO, Vel. insuf. AO | 4 (estenosis aórtica) |
| G006 | AI y VD dilatados | F | Diám. AI, Vol. AI, Diám. VD | 3 (dilatación AI + VD) |
| G007 | Disfunción del VD | M | TAPSE, FSR | 2 (función VD) |
| G008 | PSAP 36 mmHg a nivel del mar | M | PSAP | 1 (hipertensión pulmonar) |
| G009 | Mismo PSAP a 2640 msnm | M | ninguna | ninguna (ajuste por altitud) |

El par G008/G009 demuestra el **ajuste por altitud** del PSAP
(`límite = 30 + msnm/330`): un mismo valor cambia su clasificación según la
ciudad.

## Hallazgos y correcciones de esta iteración

1. **Cobertura de la regla de velocidad de insuficiencia aórtica:** el golden set
   (G005) confirma por primera vez con un caso completo que la regla
   "Velocidad de insuficiencia aórtica elevada" se dispara. El emparejamiento
   depende del sinónimo `"vel": "velocidad"` en `src/core/recommendations.py`; el
   test `test_regla_velocidad_insuficiencia_aortica_se_dispara` lo fija como
   regresión.
2. **Pendiente de pulido:** los textos de recomendaciones se muestran **sin
   tildes** en el PDF (p. ej. "disfuncion" en lugar de "disfunción"), porque el
   módulo se escribió normalizando sin acentos. Conviene corregir los mensajes
   con acentos correctos y conservar solo la normalización interna para el
   emparejamiento. Candidato para v1.0.3.
3. **Rangos avalables:** ver `docs/validacion_clinica.md` para la revisión por
   cardiólogo de los límites y textos.

## Siguientes pasos sugeridos

- Informes reales anonimizados (N≥10) con la medición esperada para medir
  exactitud de extracción IA (exactitud campo a campo, MAE por parámetro).
- Publicar el resultado de esa medición en el README como métrica objetiva.
