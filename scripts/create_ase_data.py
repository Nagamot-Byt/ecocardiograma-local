"""
Script para crear los archivos Excel de referencia ASE (hombres y mujeres).
Basado en las guias de la American Society of Echocardiography (2023).
"""
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "ase_references")


def create_ase_references():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ---- HOMBRES ----
    data_hombres = [
        # Geometria VI
        {"Parametro": "DDI (mm)", "Limite_Inferior": 42, "Limite_Superior": 58, "Unidad": "mm"},
        {"Parametro": "DSI (mm)", "Limite_Inferior": 22, "Limite_Superior": 38, "Unidad": "mm"},
        {"Parametro": "PPVI (mm)", "Limite_Inferior": 8, "Limite_Superior": 11, "Unidad": "mm"},
        {"Parametro": "SIVI (mm)", "Limite_Inferior": 8, "Limite_Superior": 12, "Unidad": "mm"},
        {"Parametro": "Masa VI (g)", "Limite_Inferior": None, "Limite_Superior": 230, "Unidad": "g"},
        {"Parametro": "Masa VI ind. (g/m2)", "Limite_Inferior": None, "Limite_Superior": 115, "Unidad": "g/m2"},
        # Volumenes VI
        {"Parametro": "RVDI (ml)", "Limite_Inferior": 62, "Limite_Superior": 150, "Unidad": "ml"},
        {"Parametro": "RVSI (ml)", "Limite_Inferior": 21, "Limite_Superior": 61, "Unidad": "ml"},
        {"Parametro": "FEVI (%)", "Limite_Inferior": 52, "Limite_Superior": 72, "Unidad": "%"},
        # Auricula izquierda
        {"Parametro": "Diametro AI (mm)", "Limite_Inferior": None, "Limite_Superior": 40, "Unidad": "mm"},
        {"Parametro": "Volumen AI ind. (ml/m2)", "Limite_Inferior": None, "Limite_Superior": 34, "Unidad": "ml/m2"},
        # Ventriculo derecho
        {"Parametro": "Diametro VD (mm)", "Limite_Inferior": None, "Limite_Superior": 42, "Unidad": "mm"},
        {"Parametro": "TAPSE (mm)", "Limite_Inferior": 17, "Limite_Superior": None, "Unidad": "mm"},
        {"Parametro": "FSR (%)", "Limite_Inferior": 32, "Limite_Superior": None, "Unidad": "%"},
        # Valvulas mitral
        {"Parametro": "Grad. medio MI (mmHg)", "Limite_Inferior": None, "Limite_Superior": 5, "Unidad": "mmHg"},
        {"Parametro": "Grad. max MI (mmHg)", "Limite_Inferior": None, "Limite_Superior": 10, "Unidad": "mmHg"},
        {"Parametro": "Area MI (cm2)", "Limite_Inferior": 4.0, "Limite_Superior": None, "Unidad": "cm2"},
        # Valvulas aortica
        {"Parametro": "Grad. medio AO (mmHg)", "Limite_Inferior": None, "Limite_Superior": 12, "Unidad": "mmHg"},
        {"Parametro": "Grad. max AO (mmHg)", "Limite_Inferior": None, "Limite_Superior": 20, "Unidad": "mmHg"},
        {"Parametro": "Area AO (cm2)", "Limite_Inferior": 3.0, "Limite_Superior": None, "Unidad": "cm2"},
        {"Parametro": "Vel. insuf. AO (m/s)", "Limite_Inferior": None, "Limite_Superior": 2.5, "Unidad": "m/s"},
        # Presiones
        {"Parametro": "PSAP (mmHg)", "Limite_Inferior": None, "Limite_Superior": 35, "Unidad": "mmHg"},
    ]

    df_hombres = pd.DataFrame(data_hombres)
    path_h = os.path.join(OUTPUT_DIR, "hombres.xlsx")
    df_hombres.to_excel(path_h, index=False)
    print(f"Creado: {path_h}")

    # ---- MUJERES ----
    data_mujeres = [
        # Geometria VI
        {"Parametro": "DDI (mm)", "Limite_Inferior": 38, "Limite_Superior": 52, "Unidad": "mm"},
        {"Parametro": "DSI (mm)", "Limite_Inferior": 20, "Limite_Superior": 34, "Unidad": "mm"},
        {"Parametro": "PPVI (mm)", "Limite_Inferior": 7, "Limite_Superior": 10, "Unidad": "mm"},
        {"Parametro": "SIVI (mm)", "Limite_Inferior": 7, "Limite_Superior": 11, "Unidad": "mm"},
        {"Parametro": "Masa VI (g)", "Limite_Inferior": None, "Limite_Superior": 162, "Unidad": "g"},
        {"Parametro": "Masa VI ind. (g/m2)", "Limite_Inferior": None, "Limite_Superior": 95, "Unidad": "g/m2"},
        # Volumenes VI
        {"Parametro": "RVDI (ml)", "Limite_Inferior": 46, "Limite_Superior": 120, "Unidad": "ml"},
        {"Parametro": "RVSI (ml)", "Limite_Inferior": 14, "Limite_Superior": 50, "Unidad": "ml"},
        {"Parametro": "FEVI (%)", "Limite_Inferior": 54, "Limite_Superior": 74, "Unidad": "%"},
        # Auricula izquierda
        {"Parametro": "Diametro AI (mm)", "Limite_Inferior": None, "Limite_Superior": 38, "Unidad": "mm"},
        {"Parametro": "Volumen AI ind. (ml/m2)", "Limite_Inferior": None, "Limite_Superior": 34, "Unidad": "ml/m2"},
        # Ventriculo derecho
        {"Parametro": "Diametro VD (mm)", "Limite_Inferior": None, "Limite_Superior": 40, "Unidad": "mm"},
        {"Parametro": "TAPSE (mm)", "Limite_Inferior": 17, "Limite_Superior": None, "Unidad": "mm"},
        {"Parametro": "FSR (%)", "Limite_Inferior": 32, "Limite_Superior": None, "Unidad": "%"},
        # Valvulas mitral
        {"Parametro": "Grad. medio MI (mmHg)", "Limite_Inferior": None, "Limite_Superior": 5, "Unidad": "mmHg"},
        {"Parametro": "Grad. max MI (mmHg)", "Limite_Inferior": None, "Limite_Superior": 10, "Unidad": "mmHg"},
        {"Parametro": "Area MI (cm2)", "Limite_Inferior": 4.0, "Limite_Superior": None, "Unidad": "cm2"},
        # Valvulas aortica
        {"Parametro": "Grad. medio AO (mmHg)", "Limite_Inferior": None, "Limite_Superior": 12, "Unidad": "mmHg"},
        {"Parametro": "Grad. max AO (mmHg)", "Limite_Inferior": None, "Limite_Superior": 20, "Unidad": "mmHg"},
        {"Parametro": "Area AO (cm2)", "Limite_Inferior": 2.5, "Limite_Superior": None, "Unidad": "cm2"},
        {"Parametro": "Vel. insuf. AO (m/s)", "Limite_Inferior": None, "Limite_Superior": 2.4, "Unidad": "m/s"},
        # Presiones
        {"Parametro": "PSAP (mmHg)", "Limite_Inferior": None, "Limite_Superior": 35, "Unidad": "mmHg"},
    ]

    df_mujeres = pd.DataFrame(data_mujeres)
    path_m = os.path.join(OUTPUT_DIR, "mujeres.xlsx")
    df_mujeres.to_excel(path_m, index=False)
    print(f"Creado: {path_m}")


if __name__ == "__main__":
    create_ase_references()
    print("Archivos ASE de referencia creados exitosamente.")
