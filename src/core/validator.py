"""
Validador de datos numericos.
Compara los valores del paciente con los rangos normales ASE segun sexo.
"""
from typing import Dict, List
from src.models.patient import Patient
from src.models.reference_range import ReferenceRanges
from src.utils.logger import setup_logger

logger = setup_logger()


class Validator:
    """Valida los valores numericos del ecocardiograma contra los rangos ASE."""

    def __init__(self, reference_ranges: ReferenceRanges):
        self.reference_ranges = reference_ranges

    def validate_patient(self, patient: Patient) -> Dict[str, dict]:
        """
        Valida todos los campos numericos del paciente.
        Retorna un diccionario: {nombre_parametro: {normal, mensaje}}
        """
        resultados = {}
        campos = patient.get_numeric_fields()

        for nombre, valor in campos.items():
            resultado = self.reference_ranges.validate_value(
                patient.sexo, nombre, valor
            )
            resultados[nombre] = resultado

        anormales = sum(1 for r in resultados.values() if r["normal"] is False)
        normales = sum(1 for r in resultados.values() if r["normal"] is True)
        sin_ref = sum(1 for r in resultados.values() if r["normal"] is None)

        logger.info(
            f"Validacion completada: {normales} normales, "
            f"{anormales} anormales, {sin_ref} sin referencia"
        )

        return resultados

    def get_summary(self, patient: Patient) -> List[str]:
        """
        Retorna un resumen legible de los valores fuera de rango.
        """
        resultados = self.validate_patient(patient)
        alertas = []

        for nombre, resultado in resultados.items():
            if resultado["normal"] is False:
                alertas.append(f"  - {nombre}: {resultado['mensaje']}")

        if not alertas:
            alertas.append("  Todos los valores dentro de los rangos normales.")

        return alertas

    def get_validation_table(self, patient: Patient) -> List[dict]:
        """
        Retorna una lista de diccionarios para mostrar en tabla:
        [{parametro, valor, unidad, limite_inf, limite_sup, normal, mensaje}]
        """
        campos = patient.get_numeric_fields()
        filas = []

        for nombre, valor in campos.items():
            rango = self.reference_ranges.get_range(patient.sexo, nombre)
            resultado = self.reference_ranges.validate_value(
                patient.sexo, nombre, valor
            )

            fila = {
                "parametro": nombre,
                "valor": valor,
                "unidad": rango.unidad if rango else "-",
                "limite_inf": rango.limite_inferior if rango else None,
                "limite_sup": rango.limite_superior if rango else None,
                "normal": resultado["normal"],
                "mensaje": resultado["mensaje"],
            }
            filas.append(fila)

        return filas
