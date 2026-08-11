#!/bin/bash
# Script de configuracion del entorno para Ecocardiograma Local

set -e

echo "=========================================="
echo "  ECOCARDIOGRAMA LOCAL - Setup"
echo "=========================================="

# Verificar Python
echo ""
echo "Verificando Python..."
python_version=$(python3 --version 2>&1 || echo "NOT_FOUND")
if echo "$python_version" | grep -q "NOT_FOUND"; then
    echo "ERROR: Python 3 no encontrado. Instale Python 3.11+"
    exit 1
fi
echo "  $python_version"

# Crear entorno virtual
if [ ! -d "venv" ]; then
    echo ""
    echo "Creando entorno virtual..."
    python3 -m venv venv
    echo "  Entorno virtual creado en ./venv"
else
    echo ""
    echo "El entorno virtual ya existe en ./venv"
fi

# Activar
echo ""
echo "Activando entorno virtual..."
source venv/bin/activate
echo "  Activado."

# Instalar dependencias
echo ""
echo "Instalando dependencias..."
pip install --upgrade pip -q
pip install pandas openpyxl PyQt6 jinja2 weasyprint pyyaml cryptography tqdm -q
echo "  Dependencias instaladas."

# Crear directorios de datos
echo ""
echo "Creando directorios de datos..."
mkdir -p data/user_input data/output logs
echo "  Directorios creados."

# Generar datos ASE de referencia
echo ""
echo "Generando datos de referencia ASE..."
python scripts/create_ase_data.py

echo ""
echo "=========================================="
echo "  SETUP COMPLETADO"
echo "=========================================="
echo ""
echo "Para ejecutar la aplicacion:"
echo "  source venv/bin/activate"
echo "  python -m src.main"
echo ""
