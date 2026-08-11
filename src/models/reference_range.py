"""
Rangos de referencia ASE (American Society of Echocardiography).
Contiene los valores normales indexados por sexo, cargados desde archivos Excel.
"""
from dataclasses import dataclass
from typing import Optional, Dict
from src.models.patient import Sexo


@dataclass
class ReferenceRange:
    """Rango de referencia para un parametro ecocardiografico."""
    parametro: str
    limite_inferior: Optional[float] = None
    limite_superior: Optional[float] = None
    unidad: str = ""


class ReferenceRanges:
    """Contenedor de todos los rangos de referencia ASE, indexado por sexo."""

    def __init__(self):
        self._rangos: Dict[Sexo, Dict[str, ReferenceRange]] = {
            Sexo.MASCULINO: {},
            Sexo.FEMENINO: {},
        }

    def load_from_excel(self, filepath_hombres: str, filepath_mujeres: str) -> None:
        """Carga los rangos desde archivos Excel separados por sexo."""
        self._cargar_sexo(filepath_hombres, Sexo.MASCULINO)
        self._cargar_sexo(filepath_mujeres, Sexo.FEMENINO)

    def _cargar_sexo(self, filepath: str, sexo: Sexo) -> None:
        """Lee un archivo Excel y pobla los rangos para un sexo dado."""
        import pandas as pd  # import perezoso: pandas es pesado de cargar

        try:
            df = pd.read_excel(filepath)
        except Exception as e:
            raise ValueError(f"Error leyendo {filepath}: {e}")

        # Mapeo de nombres de columna en el Excel a parametros internos
        mapeo_columnas = {
            "Parametro": "parametro",
            "Limite_Inferior": "limite_inferior",
            "Limite_Superior": "limite_superior",
            "Unidad": "unidad",
        }

        # Normalizar nombres de columna (minuscculas, sin espacios)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        # Renombrar segun mapeo
        rename_map = {}
        for original_key, internal_key in mapeo_columnas.items():
            normalized = original_key.lower().replace(" ", "_")
            rename_map[normalized] = internal_key

        df = df.rename(columns=rename_map)

        for _, row in df.iterrows():
            param = str(row.get("parametro", "")).strip()
            if not param:
                continue

            li = row.get("limite_inferior")
            ls = row.get("limite_superior")

            # Convertir a float si es posible
            try:
                li = float(li) if pd.notna(li) else None
            except (ValueError, TypeError):
                li = None
            try:
                ls = float(ls) if pd.notna(ls) else None
            except (ValueError, TypeError):
                ls = None

            unidad = str(row.get("unidad", "")).strip()

            rango = ReferenceRange(
                parametro=param,
                limite_inferior=li,
                limite_superior=ls,
                unidad=unidad,
            )
            self._rangos[sexo][param] = rango

    def get_range(self, sexo: Sexo, parametro: str) -> Optional[ReferenceRange]:
        """Retorna el rango de referencia para un parametro y sexo dados."""
        return self._rangos.get(sexo, {}).get(parametro)

    def get_all_ranges(self, sexo: Sexo) -> Dict[str, ReferenceRange]:
        """Retorna todos los rangos para un sexo dado."""
        return self._rangos.get(sexo, {})

    def validate_value(self, sexo: Sexo, parametro: str, valor: float) -> dict:
        """
        Valida un valor contra el rango de referencia.
        Retorna un diccionario con: {normal: bool, mensaje: str}
        """
        rango = self.get_range(sexo, parametro)
        if rango is None:
            return {
                "normal": None,
                "mensaje": f"Sin rango de referencia para '{parametro}'",
            }

        if rango.limite_inferior is not None and valor < rango.limite_inferior:
            return {
                "normal": False,
                "mensaje": f"Bajo ({valor} {rango.unidad} < {rango.limite_inferior})",
            }

        if rango.limite_superior is not None and valor > rango.limite_superior:
            return {
                "normal": False,
                "mensaje": f"Elevado ({valor} {rango.unidad} > {rango.limite_superior})",
            }

        return {
            "normal": True,
            "mensaje": f"Normal ({valor} {rango.unidad})",
        }
