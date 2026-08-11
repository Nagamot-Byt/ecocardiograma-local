"""
Cargador de datos.
Lee las tablas ASE de referencia y los archivos de entrada del usuario (.xlsx/.csv).
"""
import os
from typing import Dict
from src.models.reference_range import ReferenceRanges
from src.models.patient import Patient, Sexo
from src.utils.logger import setup_logger

logger = setup_logger()


class DataLoader:
    """Carga y administra los datos de referencia ASE y los datos del usuario."""

    def __init__(self, hombres_path: str, mujeres_path: str):
        self.hombres_path = hombres_path
        self.mujeres_path = mujeres_path
        self.reference_ranges = ReferenceRanges()
        self._loaded = False
        self.last_row_count: int = 0  # Filas del ultimo archivo cargado
        self.last_loaded_row: int = 0  # Indice de la fila usada (0 = primera)

    def load_references(self) -> bool:
        """Carga las tablas de referencia ASE desde los archivos Excel."""
        if self._loaded:
            return True

        try:
            if os.path.exists(self.hombres_path) and os.path.exists(self.mujeres_path):
                self.reference_ranges.load_from_excel(
                    self.hombres_path, self.mujeres_path
                )
                n_m = len(self.reference_ranges.get_all_ranges(Sexo.MASCULINO))
                n_f = len(self.reference_ranges.get_all_ranges(Sexo.FEMENINO))
                logger.info(
                    f"Referencias ASE cargadas: {n_m} parametros (hombres), "
                    f"{n_f} parametros (mujeres)"
                )
                self._loaded = True
                return True
            else:
                logger.warning(
                    "Archivos de referencia no encontrados: "
                    f"{os.path.basename(self.hombres_path)} / "
                    f"{os.path.basename(self.mujeres_path)}"
                )
                return False
        except Exception as e:
            logger.error(f"Error cargando referencias ASE: {e}")
            return False

    def load_patient_from_file(
        self, filepath: str, patient: Patient, row: int = 0
    ) -> bool:
        """
        Carga datos numericos desde un archivo Excel o CSV del usuario.
        El archivo debe tener columnas con los nombres de los parametros.
        ``row`` selecciona la fila a usar cuando el archivo tiene varias.
        Retorna True si la carga fue exitosa.
        """
        if not os.path.exists(filepath):
            logger.error(f"Archivo no encontrado: {os.path.basename(filepath)}")
            return False

        try:
            import pandas as pd  # import perezoso: pandas es pesado de cargar

            if filepath.endswith(".xlsx"):
                df = pd.read_excel(filepath)
            elif filepath.endswith(".csv"):
                df = pd.read_csv(filepath)
            else:
                logger.error(f"Formato no soportado: {os.path.basename(filepath)}")
                return False

            # Normalizar nombres de columna
            df.columns = [str(c).strip() for c in df.columns]

            self.last_row_count = len(df)
            if not 0 <= row < self.last_row_count:
                logger.warning(
                    f"Fila {row} inexistente (el archivo tiene "
                    f"{self.last_row_count} filas). Se usara la primera."
                )
                row = 0
            self.last_loaded_row = row

            if self.last_row_count > 1:
                logger.warning(
                    f"El archivo {os.path.basename(filepath)} tiene "
                    f"{self.last_row_count} filas; se usa la fila {row + 1}. "
                    "Las demas filas se ignoran."
                )

            # Mapeo de columnas del archivo a atributos del Patient
            mapeo = self._build_column_mapping()
            filled = 0

            for col_name, attr_name in mapeo.items():
                if col_name in df.columns:
                    try:
                        value = df[col_name].iloc[row] if len(df) > 0 else None
                        if pd.notna(value):
                            if isinstance(value, str):
                                value = value.replace(",", ".")
                            setattr(patient, attr_name, float(value))
                            filled += 1
                    except (ValueError, TypeError, IndexError):
                        pass

            logger.info(
                f"Datos cargados de {os.path.basename(filepath)}: {filled} campos llenados"
            )
            return filled > 0

        except Exception as e:
            logger.error(
                f"Error cargando datos de {os.path.basename(filepath)}: {e}"
            )
            return False

    def get_available_parameters(self, sexo: Sexo) -> Dict[str, str]:
        """
        Retorna los parametros disponibles para un sexo dado.
        Diccionario {nombre_parametro: unidad}
        """
        rangos = self.reference_ranges.get_all_ranges(sexo)
        return {
            r.parametro: r.unidad
            for r in rangos.values()
        }

    @staticmethod
    def template_columns() -> Dict[str, float]:
        """
        Columnas canonicas para generar una plantilla .xlsx de ejemplo.
        Retorna {nombre_columna: valor_de_ejemplo}.
        """
        return {
            "DDI": 48.0, "DSI": 30.0, "PPVI": 9.0, "SIVI": 10.0,
            "Masa VI": 150.0, "Masa VI Ind": 82.0,
            "RVDI": 110.0, "RVSI": 40.0, "FEVI": 60.0,
            "Diametro AI": 38.0, "Volumen AI": 28.0, "Diametro VD": 34.0,
            "TAPSE": 22.0, "FSR": 45.0,
            "Gradiente Media MI": 2.0, "Gradiente Max MI": 6.0, "Area MI": 4.0,
            "Gradiente Media AO": 6.0, "Gradiente Max AO": 18.0, "Area AO": 3.0,
            "Velocidad Insuf AO": 2.2, "PSAP": 28.0,
        }

    @staticmethod
    def _build_column_mapping() -> Dict[str, str]:
        """Mapeo flexible de nombres de columna a atributos del Patient."""
        return {
            "DDI": "ddi",
            "ddi": "ddi",
            "Diametro Diastolico VI": "ddi",
            "DDVI": "ddi",
            "DSI": "dsi",
            "dsi": "dsi",
            "Diametro Sistolico VI": "dsi",
            "DSVI": "dsi",
            "PPVI": "ppvi",
            "ppvi": "ppvi",
            "Pared Posterior VI": "ppvi",
            "SIVI": "sivi",
            "sivi": "sivi",
            "Septum Interventricular": "sivi",
            "Masa VI": "masa_vi",
            "masa_vi": "masa_vi",
            "Masa VI Ind": "masa_vi_ind",
            "masa_vi_ind": "masa_vi_ind",
            "RVDI": "rvdi",
            "rvdi": "rvdi",
            "RVSI": "rvsi",
            "rvsi": "rvsi",
            "FEVI": "fevi",
            "fevi": "fevi",
            "Fraccion de Eyeccion": "fevi",
            "Diametro AI": "diametro_ai",
            "diametro_ai": "diametro_ai",
            "Volumen AI": "volumen_ai",
            "volumen_ai": "volumen_ai",
            "Diametro VD": "diametro_vd",
            "diametro_vd": "diametro_vd",
            "TAPSE": "tad",
            "tad": "tad",
            "FSR": "fsr",
            "fsr": "fsr",
            "Gradiente Media MI": "gradiente_media_mi",
            "Gradiente Max MI": "gradiente_max_mi",
            "Area MI": "area_mi",
            "Gradiente Media AO": "gradiente_media_ao",
            "Gradiente Max AO": "gradiente_max_ao",
            "Area AO": "area_ao",
            "Velocidad Insuf AO": "velocidad_insuf_ao",
            "PSAP": "psap",
            "psap": "psap",
        }
