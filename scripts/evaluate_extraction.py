# Runner de exactitud de la extraccion IA vs golden set.
#
# Uso:
#   venv\Scripts\python.exe scripts\evaluate_extraction.py [--dir data/golden_extraction]
#       [--use-ai] [--json salida.json]
#
# Por defecto usa el extractor por reglas (regex), deterministico y sin red.
# Con --use-ai se activa Ollama (extraccion IA + relleno por regex).
#
# El resultado imprime, por caso y por campo, exactitud, cobertura y MAE.
# Con --json se vuelca el reporte completo a un archivo para publicarlo.
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.extraction_eval import (  # noqa: E402
    cargar_casos,
    evaluar_casos,
    DEFAULT_BASE_URL,
)


def _print_reporte(reporte: dict):
    print("=" * 72)
    print(f"EVALUACION DE EXTRACCION ({reporte['total_casos']} casos, "
          f"fuente: {'IA+regex' if reporte['use_ai'] else 'regex'})")
    print("=" * 72)
    for caso in reporte["por_caso"]:
        estado = "OK" if caso["exactitud"] == 1.0 else "FALLOS"
        print(f"[{estado}] {caso['id']} - {caso['nombre']}: "
              f"{caso['params_ok']}/{caso['total_esperados']} "
              f"({caso['exactitud']:.1%})")
        for f in caso["faltantes"]:
            print(f"      faltante: {f}")
        for e in caso["errores"]:
            print(f"      error: {e}")
        if caso["falsos_positivos"]:
            print(f"      falsos positivos: {', '.join(caso['falsos_positivos'])}")

    print("-" * 72)
    print(f"Exactitud global : {reporte['exactitud_global']:.1%} "
          f"({reporte['total_parametros']} parametros)")
    print(f"Cobertura global : {reporte['cobertura_global']:.1%}")
    print("-" * 72)
    print(f"{'Parametro':<26} {'Esperados':>9} {'Exactitud':>10} {'MAE':>8}")
    for clave, info in sorted(reporte["por_campo"].items()):
        mae = f"{info['mae']:.2f}" if info["mae"] is not None else "-"
        print(f"{clave:<26} {info['esperados']:>9} "
              f"{info['exactitud']:>9.0%} {mae:>8}")
    print("=" * 72)


def main():
    parser = argparse.ArgumentParser(description="Mide exactitud de la extraccion IA")
    parser.add_argument("--dir", default="data/golden_extraction",
                        help="Directorio con los casos golden (*.json)")
    parser.add_argument("--use-ai", action="store_true",
                        help="Activa Ollama (por defecto solo regex)")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--json", default=None,
                        help="Vuelca el reporte completo a este archivo")
    args = parser.parse_args()

    casos = cargar_casos(args.dir)
    if not casos:
        print(f"No hay casos en {args.dir}", file=sys.stderr)
        sys.exit(2)

    reporte = evaluar_casos(casos, use_ai=args.use_ai, base_url=args.base_url)
    _print_reporte(reporte)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(reporte, f, ensure_ascii=False, indent=2)
        print(f"Reporte guardado en: {args.json}")


if __name__ == "__main__":
    main()
