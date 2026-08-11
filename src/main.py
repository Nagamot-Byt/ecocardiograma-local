"""
Punto de entrada principal de la aplicacion Ecocardiograma Local.
Lanza la interfaz grafica y orquesta el flujo completo.
"""
import sys
import os


def main():
    """Funcion principal: inicializa y lanza la aplicacion."""
    # Asegurar que el directorio del proyecto esta en el path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Intentar importar PyQt6
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QFont
    except ImportError:
        print("=" * 60)
        print("ERROR: PyQt6 no esta instalado.")
        print("Instale las dependencias con:")
        print("  pip install -r requirements.txt")
        print("=" * 60)
        sys.exit(1)

    # Crear aplicacion Qt
    app = QApplication(sys.argv)
    app.setApplicationName("Ecocardiograma Local")
    app.setOrganizationName("EcoLocal")

    # Configurar fuente por defecto
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Importar y lanzar ventana principal
    from src.gui.main_window import MainWindow

    try:
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error fatal iniciando la aplicacion: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
