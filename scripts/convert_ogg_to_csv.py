#!/usr/bin/env python3
"""
Utilidad para convertir transcripciones de audio (.ogg/.wav) a formato tabular (.csv/.xlsx).

Este script es una herramienta opcional que facilita la conversion de datos
de audio transcritos al formato que la aplicacion Ecocardiograma Local puede
procesar. No forma parte del flujo principal de la aplicacion.

Formato de entrada esperado (texto transcrito, una linea por parametro):
    DDI: 50 mm
    DSI: 35 mm
    FEVI: 55 %
    ...

O un archivo JSON con estructura:
    {"DDI": 50, "DSI": 35, "FEVI": 55, ...}
"""
import os
import sys
import json
import re
import argparse
import pandas as pd
from typing import Dict


# Mapeo de nombres comunes en transcripciones a atributos del sistema
PARAM_MAP = {
    "ddi": "DDI",
    "ddvi": "DDI",
    "diametro diastolico": "DDI",
    "diametro diastólico": "DDI",
    "dsi": "DSI",
    "dsvi": "DSI",
    "diametro sistolico": "DSI",
    "diametro sistólico": "DSI",
    "ppvi": "PPVI",
    "pared posterior": "PPVI",
    "sivi": "SIVI",
    "septum": "SIVI",
    "tabique": "SIVI",
    "masa": "Masa VI",
    "masa vi": "Masa VI",
    "masa indexada": "Masa VI ind. (g/m2)",
    "rvdi": "RVDI",
    "volumen diastolico": "RVDI",
    "rvsi": "RVSI",
    "volumen sistolico": "RVSI",
    "fevi": "FEVI",
    "fraccion de eyeccion": "FEVI",
    "fracción de eyección": "FEVI",
    "ai": "Diametro AI",
    "auricula izquierda": "Diametro AI",
    "diametro ai": "Diametro AI",
    "volumen ai": "Volumen AI ind. (ml/m2)",
    "vd": "Diametro VD",
    "ventriculo derecho": "Diametro VD",
    "diametro vd": "Diametro VD",
    "tapse": "TAPSE",
    "fsr": "FSR",
    "gradiente medio mitral": "Grad. medio MI (mmHg)",
    "gradiente maximo mitral": "Grad. max MI (mmHg)",
    "gradiente máximo mitral": "Grad. max MI (mmHg)",
    "area mitral": "Area MI (cm2)",
    "area mi": "Area MI (cm2)",
    "gradiente medio aortico": "Grad. medio AO (mmHg)",
    "gradiente medio aórtico": "Grad. medio AO (mmHg)",
    "gradiente maximo aortico": "Grad. max AO (mmHg)",
    "gradiente máximo aórtico": "Grad. max AO (mmHg)",
    "area aortica": "Area AO (cm2)",
    "area aórtica": "Area AO (cm2)",
    "area ao": "Area AO (cm2)",
    "velocidad insuficiencia aortica": "Vel. insuf. AO (m/s)",
    "psap": "PSAP (mmHg)",
    "presion sistolica": "PSAP (mmHg)",
    "presión sistólica": "PSAP (mmHg)",
}


def parse_text_transcription(text: str) -> Dict[str, float]:
    """
    Parsea texto transcrito con formato 'Nombre: valor unidad'.
    Ejemplo: 'DDI: 50 mm' -> {'DDI': 50.0}
    """
    results = {}
    lines = text.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line or ":" not in line:
            continue

        parts = line.split(":", 1)
        if len(parts) != 2:
            continue

        raw_name = parts[0].strip().lower()
        raw_value = parts[1].strip()

        # Buscar el nombre mapeado
        matched_key = None
        for pattern, std_name in PARAM_MAP.items():
            if pattern in raw_name:
                matched_key = std_name
                break

        if matched_key is None:
            continue

        # Extraer valor numerico
        try:
            number_str = re.sub(r"[^0-9.,\-]", "", raw_value)
            number_str = number_str.replace(",", ".")
            value = float(number_str)
            results[matched_key] = value
        except (ValueError, IndexError):
            continue

    return results


def convert_file(input_path: str, output_path: str = None) -> str:
    """
    Convierte un archivo de transcripcion a CSV/XLSX.
    Soporta: .txt, .json, .ogg (solo si hay transcripcion previa)
    """
    if not os.path.exists(input_path):
        print(f"Error: Archivo no encontrado: {input_path}")
        sys.exit(1)

    ext = os.path.splitext(input_path)[1].lower()

    # Leer datos segun extension
    data = {}

    if ext == ".json":
        with open(input_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        # Mapear claves del JSON a nombres estandar
        for key, value in raw.items():
            key_lower = key.strip().lower()
            matched = False
            for pattern, std_name in PARAM_MAP.items():
                if pattern in key_lower:
                    try:
                        data[std_name] = float(value)
                        matched = True
                    except (ValueError, TypeError):
                        pass
                    break
            if not matched:
                # Usar la clave tal cual
                try:
                    data[key.strip()] = float(value)
                except (ValueError, TypeError):
                    pass

    elif ext in (".txt", ".csv"):
        with open(input_path, "r", encoding="utf-8") as f:
            text = f.read()
        data = parse_text_transcription(text)

    elif ext in (".ogg", ".wav", ".mp3"):
        print(f"Nota: Los archivos de audio ({ext}) requieren transcripcion previa.")
        print("Use una herramienta como Whisper para transcribir, luego convierta el .txt resultante.")
        sys.exit(1)

    else:
        print(f"Error: Formato no soportado: {ext}")
        print("Formatos soportados: .txt, .json, .csv")
        sys.exit(1)

    if not data:
        print("Error: No se encontraron parametros validos en el archivo.")
        sys.exit(1)

    # Generar ruta de salida
    if output_path is None:
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        output_path = f"{base_name}_convertido.csv"

    # Escribir CSV
    df = pd.DataFrame([data])
    df.to_csv(output_path, index=False)
    print(f"Convertido exitosamente: {output_path}")
    print(f"Parametros encontrados: {len(data)}")
    for k, v in data.items():
        print(f"  {k}: {v}")

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Convierte transcripciones de ecocardiograma a formato tabular (CSV/XLSX)"
    )
    parser.add_argument("input", help="Archivo de entrada (.txt, .json, .csv)")
    parser.add_argument("-o", "--output", help="Archivo de salida (.csv o .xlsx)")
    parser.add_argument("--xlsx", action="store_true", help="Generar XLSX en vez de CSV")

    args = parser.parse_args()

    output = args.output
    if args.xlsx and output is None:
        base_name = os.path.splitext(os.path.basename(args.input))[0]
        output = f"{base_name}_convertido.xlsx"

    result_path = convert_file(args.input, output)

    # Convertir a XLSX si se solicito
    if args.xlsx:
        df = pd.read_csv(result_path)
        xlsx_path = result_path.replace(".csv", ".xlsx")
        df.to_excel(xlsx_path, index=False)
        os.remove(result_path)
        print(f"Generado XLSX: {xlsx_path}")


if __name__ == "__main__":
    main()
