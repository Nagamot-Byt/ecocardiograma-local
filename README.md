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
- **Generacion de informes PDF**: HTML con Jinja2 y PDF con QPrinter (PyQt6) en
  las tres plataformas, sin dependencias de sistema adicionales. WeasyPrint
  existe como extra opcional (`pip install .[pdf]`) para desarrollo en Linux/Mac,
  pero los binarios oficiales usan QPrinter (es el motor validado en 1.0.5).
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

## Como abrir la aplicacion

### Windows

**Doble clic en `AbrirEcocardiograma.cmd`** (raiz del proyecto): lanza la
aplicacion compilada en `dist\EcocardiogramaLocal\EcocardiogramaLocal.exe`.

> **Nota sobre carpetas:** `dist\EcocardiogramaLocal\EcocardiogramaLocal.exe`
> es el ejecutable real. La carpeta `dist\installer\` contiene los instaladores
> (use siempre el de version mas alta, p. ej. `EcocardiogramaLocal-Setup-1.0.5.exe`).
> No ejecute archivos dentro de `build\` ni otras subcarpetas: son artefactos
> internos del empaquetado y no abren la aplicacion.

### macOS

Abra `dist/EcocardiogramaLocal.app`. El `.app` **no esta notarizado** (requiere
certificado Apple Developer ID), asi que Gatekeeper lo bloquea la primera vez:

- Clic derecho sobre el icono → **Abrir** → **Abrir** en el dialogo, o
- `xattr -cr /ruta/a/EcocardiogramaLocal.app` desde Terminal.

### Linux

El portable (`EcocardiogramaLocal-linux-x64.tar.gz`) incluye `LEEME_LINUX.txt`:

```bash
tar xzf EcocardiogramaLocal-linux-x64.tar.gz
cd EcocardiogramaLocal
./lanzar.sh          # abre la aplicacion
./install.sh         # opcional: anhade el icono al menu de aplicaciones
```

Requiere fuentes TrueType y fontconfig (p. ej. `fonts-dejavu-core`); sin
fuentes el PDF sale con el texto vacio.

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

**Ultima version: v1.0.5** — `dist\installer\EcocardiogramaLocal-Setup-1.0.5.exe`

- **Verificacion SHA-256:**
  `5E98540AF6E23A781A04CB97281D199832E97338E1A8F36FCCB60767FFF00AC6`
- Verificar en PowerShell:
  ```powershell
  Get-FileHash dist\installer\EcocardiogramaLocal-Setup-1.0.5.exe -Algorithm SHA256
  ```

> **Datos en runtime:** la aplicacion instalada es de solo lectura en su carpeta
> de instalacion. Los datos de la sesion (logs, archivos de entrada y PDF/HTML
> temporales) se guardan en `%LOCALAPPDATA%\EcocardiogramaLocal`.

## Compilar desde codigo (Windows / macOS / Linux)

```bash
# 1. Dependencias de desarrollo y de empaquetado (versiones fijadas)
pip install -r requirements-dev.txt -r requirements-build.txt

# 2. Control de calidad (lo mismo que CI)
ruff check src tests scripts
python scripts/check_version.py          # version sincronizada en 7 ficheros
pytest                                   # 353 tests, cobertura >= 90%

# 3. Binario portable one-dir (misma spec en las tres plataformas)
pyinstaller ecocardiograma.spec --noconfirm --clean

# 4. Smoke test: comprueba que el binario arranca y no muere
bash scripts/smoke_test.sh dist/EcocardiogramaLocal/EcocardiogramaLocal
```

- **Windows**: `powershell -ExecutionPolicy Bypass -File scripts\build.ps1`
  encadena lint + tests + PyInstaller + Inno Setup + SHA-256.
- **macOS**: el spec genera ademas el bundle `dist/EcocardiogramaLocal.app`.
- **Linux**: el paso de release anhade `lanzar.sh`, `install.sh`,
  `ecocardiogramalocal.desktop` y `LEEME_LINUX.txt` antes de crear el `.tar.gz`.

Los releases oficiales los publica el workflow `.github/workflows/release.yml`
al etiquetar un tag `v*` (matrix Windows/macOS/Linux con lint, tests, version
y smoke test antes de empaquetar).

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
