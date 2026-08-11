# Ecocardiograma Local

Aplicacion de escritorio offline para la generacion de informes ecocardiograficos
basados en las guias de la **Sociedad Colombiana de Cardiologia (SCC/LATAM)** y la
**American Society of Echocardiography (ASE)**.

## Caracteristicas principales

- **100% offline**: Sin llamadas a APIs externas. La extraccion con IA se hace con
  un modelo local (Ollama, < 7B) que se inicia y descarga automaticamente.
- **Validacion automatica**: Compara valores numericos contra rangos de referencia
  colombianos SCC/LATAM (ajustables por sexo y por altitud de la ciudad para PSAP)
  o ASE por sexo.
- **Extraccion automatica con IA local**: Lee PDF, TXT, CSV o imagenes (OCR con
  Tesseract) y extrae parametros, hallazgos visuales e impresion clinica.
- **Ingreso manual de hallazgos visuales**: Insuficiencias valvulares, contractilidad,
  derrame pericardico, etc.
- **Generacion de informes PDF**: Renderizado via Jinja2 + WeasyPrint (Linux/Mac)
  o QPrinter de PyQt6 (Windows, sin dependencias externas).
- **Borrado seguro**: Al cerrar sesion, los archivos temporales (HTML/PDF internos)
  se sobreescriben y eliminan. Los informes exportados por el usuario se conservan.
- **Trazabilidad**: Registro de operaciones en archivo log local con rotacion diaria.

## Requisitos

- Python 3.11+
- Las dependencias se instalan con `pip install -r requirements.txt`:
  PyQt6, pandas, openpyxl, Jinja2, PyYAML, requests, pypdf, pillow, pytesseract.
- **Ollama** (opcional): motor de IA local. El instalador puede descargarlo, o
  instalarlo manualmente desde https://ollama.com. Sin Ollama la app funciona igual
  usando extraccion por reglas (regex).
- **Tesseract OCR** (opcional): solo necesario para leer imagenes.

## Instalacion

```bash
# Clonar o copiar el proyecto
cd ecocardiograma_local

# Crear entorno virtual (opcional pero recomendado)
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate   # Linux/Mac

# Instalar dependencias
pip install -r requirements.txt
```

### Instalador para Windows

El proyecto se distribuye como instalador generado con Inno Setup
(`installer\ecocardiograma.iss`). El instalador puede, de forma opcional,
descargar e instalar Ollama silenciosamente para habilitar la IA local.

**Ultima version: v1.0.3** — `dist\installer\EcocardiogramaLocal-Setup-1.0.3.exe`

- **Verificacion SHA-256:**
  `A4FB85E08C584E340F303EFC4969DF7523D8B39B566D1CA7BC8249292DD82015`
- Verificar en PowerShell:
  ```powershell
  Get-FileHash dist\installer\EcocardiogramaLocal-Setup-1.0.3.exe -Algorithm SHA256
  ```

> **Datos en runtime:** la aplicacion instalada es de solo lectura en su carpeta
> de instalacion. Los datos de la sesion (logs, archivos de entrada y PDF/HTML
> temporales) se guardan en `%LOCALAPPDATA%\EcocardiogramaLocal`.

## Uso

```bash
# Ejecutar la aplicacion
python -m src.main
```

### Flujo de trabajo

1. **Seleccione el sexo** del paciente en el encabezado.
2. **Extraiga los datos con IA** (pestana "IA - Lectura"): cargue un PDF, TXT, CSV
   o imagen, o pegue el texto, y pulse "Extraer Datos con IA". Alternativamente
   ingrese los datos a mano en la pestana "Datos Numericos" (o cargue un .xlsx/.csv).
3. **Revise los hallazgos visuales** en la pestana "Hallazgos Visuales".
4. **Valide los datos**: El boton "Validar Datos" compara contra los rangos y
   colorea los campos (verde = normal, rojo = fuera de rango).
5. **Genere el informe**: En la pestana "Informe", haga clic en "Generar Informe"
   para crear el PDF y previsualizarlo.
6. **Exporte el PDF**: Use "Exportar PDF" para guardar el informe donde desee.
7. **Cierre la aplicacion**: Al cerrar, los archivos temporales se eliminan de
   forma segura.

## Estructura del proyecto

```
ecocardiograma_local/
  src/            - Codigo fuente
    gui/          - Interfaz grafica PyQt6
    core/         - Logica de negocio
    models/       - Modelos de datos
    utils/        - Utilidades
  data/           - Datos y plantillas
    ase_references/ - Tablas ASE por sexo
    templates/    - Plantilla Jinja2
    user_input/   - Archivos del usuario (temporal)
    output/       - Informes generados (temporal)
  configs/        - Configuracion
  tests/          - Tests unitarios
  scripts/        - Scripts auxiliares
```

## Licencia

MIT License - Ver archivo LICENSE para mas detalles.
