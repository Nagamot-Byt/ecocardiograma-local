# Ecocardiograma Local — Guía de Uso

**Versión 1.0.5 · YAMID**
Aplicación de escritorio para la generación de informes ecocardiográficos basados en las guías **SCC/LATAM (Sociedad Colombiana de Cardiología)** y **ASE**, funcionando **100% sin conexión** a internet.

---

## 1. Requisitos del sistema

| Requisito | Detalle |
|---|---|
| Sistema operativo | Windows 10 o superior (64 bits) |
| Memoria RAM | 8 GB recomendados (4 GB mínimos sin IA local) |
| Espacio en disco | ~500 MB la aplicación · ~2 GB adicionales si instala la IA local (Ollama + modelo) |
| Internet | **No necesario para usar la aplicación.** Solo para la instalación inicial y, opcionalmente, para descargar el motor de IA |
| Permisos | Instala en tu carpeta de usuario; **no requiere ser administrador** |

---

## 2. Instalación

### Paso a paso

1. Ejecute **`EcocardiogramaLocal-Setup-1.0.5.exe`**.
2. Si Windows muestra un aviso azul *"Windows protegió su PC"* (SmartScreen), pulse
   **"Más información" → "Ejecutar de todas formas"**. Es normal en programas que
   aún no tienen firma digital comercial.
3. Siga el asistente:
   - ✔ Marque **"Crear acceso directo en el escritorio"** si lo desea.
   - ✔ Marque **"Instalar Ollama (motor de IA local)"** solo si desea la
     *extracción inteligente* de informes (ver sección 5). Esta casilla descarga
     ~700 MB desde ollama.com durante la instalación.
4. Pulse **Instalar** y al finalizar marque *"Ejecutar Ecocardiograma Local"*.

> **Alternativa portable:** también puede usar `EcocardiogramaLocal-portable.zip`:
> descomprímalo en cualquier carpeta y ejecute `EcocardiogramaLocal.exe` directamente,
> sin instalador.

### Dónde guarda sus datos la aplicación

La carpeta de instalación queda **de solo lectura**. Todo lo que la aplicación genera
se guarda en su perfil de usuario:

```
%LOCALAPPDATA%\EcocardiogramaLocal\
   ├── logs\        → registro técnico (rotación diaria, borrado seguro a 7 días)
   ├── user_input\  → copias temporales de los documentos que carga (se borran solas)
   └── output\      → informes HTML/PDF temporales de la sesión (se borran al cerrar)
```

Los informes que usted **exporta** a otra ubicación (Escritorio, Documentos…) **nunca se borran**.

---

## 3. Primer arranque

Al abrir la aplicación verá una ventana con:

- **Datos del paciente**: identificador generado automáticamente y selector de sexo.
- **Pestaña numérica**: los 22 parámetros del ecocardiograma (DDI, FEVI, TAPSE, PSAP…).
- **Hallazgos visuales**: insuficiencias valvulares, contractilidad, derrame pericárdico.
- **Extracción con IA**: zona para cargar un documento fuente y extraer sus datos automáticamente.
- **Informe**: vista previa, generación y exportación del PDF final.

El primer arranque crea automáticamente las carpetas anteriores y limpia restos de
una sesión anterior si la PC se apagó de forma abrupta.

---

## 4. Flujo de trabajo completo (paso a paso)

### Paso 1 — Cargar el documento fuente
En la sección de extracción, pulse **Cargar archivo** y seleccione el informe original:

- PDF de texto (el más común)
- TXT o CSV
- Imagen (JPG/PNG) — *requiere Tesseract OCR instalado aparte*

El documento se **copia** a la sesión: su archivo original nunca se modifica.
Si carga otro archivo distinto con el mismo nombre, la app conserva ambos sin
sobrescribir nada.

### Paso 2 — Extracción automática
Pulse **Extraer**. La aplicación lee el documento mediante dos estrategias combinadas:

1. **IA local** (si instaló Ollama): entiende el texto y extrae parámetros, hallazgos
   e incluso una propuesta de impresión clínica.
2. **Reglas deterministas** (regex): columna vertebral infalible que funciona incluso
   sin IA, sin internet ni modelo.

Ambas se **fusionan con prioridad por las reglas**: si la IA discrepa de un valor
etiquetado, gana el valor etiquetado y la app le avisa. Cada dato lleva su nivel de
confianza. Los campos que no aparecen en el documento quedan vacíos y se le indican
para revisión — **jamás se inventan valores**.

> ⏱️ La **primera** extracción con IA descarga el modelo (~2 GB) y tarda varios minutos.
> A partir de la segunda, es cuestión de segundos/minuto y medio según su PC.

### Paso 3 — Aplicar y revisar
Pulse **Aplicar al formulario**. Revise en la pestaña numérica y en hallazgos visuales;
todo valor es editable a mano. El sexo detectado en el documento ajusta automáticamente
los rangos de referencia.

### Paso 4 — Validar
Pulse **Validar**. La tabla muestra cada parámetro con su valor, unidad, límites
normales y estado:

- ✅ Normal
- ⚠ Fuera de rango (con detalle de por qué)

Las referencias son **SCC/LATAM colombianas** con **PSAP ajustado por altitud**
(Bogotá 2.640 msnm por defecto; configurable en `configs/config.yaml`).

### Paso 5 — Generar el informe
Pulse **Generar informe**. Se produce un PDF con:

- Datos del paciente y fecha
- Tabla de parámetros validados
- Hallazgos visuales
- Impresión clínica (propuesta de IA editable) y recomendaciones de seguimiento
- Nota metodológica de altitud cuando aplica
- **Trazabilidad**: modelo de IA usado y confianza media de la extracción

### Paso 6 — Exportar
Guarde el PDF donde quiera conservarlo (Escritorio, Documentos, red de la clínica).
Lo exportado **queda fuera** del ciclo de limpieza automática.

### Paso 7 — Cerrar la sesión
Al cerrar la aplicación (o con **Archivo → Limpiar sesión**) se **sobrescriben y
borran de forma segura** todos los temporales (copias de documentos, HTML, PDF internos),
impidiendo la recuperación de datos clínicos de pacientes por terceros.

---

## 5. La IA local explicada de forma sencilla

- La "inteligencia" vive **dentro de su computadora** (programa gratuito Ollama +
  modelo pequeño qwen2.5 de 3B parámetros).
- **Ningún dato del paciente sale a internet. Nunca.** No hay servidores externos,
  no hay nube, no hay APIs de terceros.
- Si Ollama no está instalado o falla, la aplicación **sigue funcionando** con las
  reglas deterministas y le informa qué ocurrió.
- Puede comprobar el estado del motor en la pestaña de extracción (verde = listo).

---

## 6. Privacidad y seguridad

| Mecanismo | Qué hace |
|---|---|
| Funcionamiento offline | Cero envío de información clínica fuera del equipo |
| Copia de trabajo | El original que usted carga jamás se modifica |
| Borrado seguro | Temporales sobrescritos varias veces antes de eliminarse (no recuperables) |
| Exportados protegidos | Lo que usted exporta nunca se borra automáticamente |
| Logs rotativos | Registro técnico local, 7 días, con borrado seguro |

Única excepción de red: la verificación **manual** de actualizaciones consulta
GitHub Releases (metadatos de versión, ningún dato clínico).

---

## 7. Actualizaciones

1. Menú de ayuda/acciones → **Buscar actualizaciones**.
2. Si existe una versión nueva, se le indica cuál y de dónde descargarla
   (GitHub Releases del proyecto).
3. Descargue el nuevo Setup e instale encima: conserva configuración y datos.

---

## 8. Solución de problemas

| Problema | Solución |
|---|---|
| *"Windows protegió su PC"* al instalar | Más información → Ejecutar de todas formas (aviso normal sin firma comercial) |
| La primera extracción demora mucho | Es la descarga única del modelo de IA (~2 GB). Solo ocurre una vez |
| La IA aparece "no disponible" | La app sigue operando con reglas. Reinicie la PC (Ollama arranca con Windows) o reinstale marcando la casilla de Ollama |
| No puedo cargar una imagen escaneada | Instale Tesseract OCR (https://github.com/UB-Mannheim/tesseract/wiki) y reinicie la app |
| El PDF no se genera | Verifique que haya valores cargados y que la carpeta destino no esté bloqueada por otro programa |
| La app se cerró por un corte de luz | Al reabrir, limpia sola los temporales de la sesión anterior. Sus exportados están a salvo |
| Un valor extraído está mal | Corríjalo a mano en la pestaña numérica antes de validar/generar; la app siempre le muestra qué detectó y con qué confianza |

---

## 9. Preguntas frecuentes

**¿Necesito internet para trabajar?**
No. Solo para la instalación inicial, la descarga opcional de Ollama/modelo y la búsqueda manual de actualizaciones.

**¿Mis informes de pacientes viajan a algún servidor?**
No. Toda la IA corre localmente; la app no tiene backend ni nube.

**¿Puedo usarla en varias PCs?**
Sí, instale el Setup en cada equipo. Las licencias/usos no tienen restricción técnica.

**¿Qué pasa si desinstalo?**
El desinstalador elimina la carpeta de programa. Los datos en `%LOCALAPPDATA%\EcocardiogramaLocal`
(exportados y logs) se conservan por seguridad; bórrelos manualmente si lo desea.

**¿Los rangos normales son confiables?**
Proceden de las guías SCC/LATAM colombianas y ASE, con ajuste de PSAP por altitud
documentado dentro del propio informe.

---

*Ecocardiograma Local v1.0.5 · YAMID — Documento de acompañamiento para el cliente.*
