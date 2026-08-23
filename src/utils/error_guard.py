"""
Red de seguridad global contra fallos no controlados.

PyQt6, ante una excepcion no capturada dentro de un slot invocado por Qt,
llama a sys.excepthook y por defecto aborta el proceso (comportamiento
heredado de PyQt5.5+). Este modulo instala un excepthook propio que:

  1. Registra el traceback completo en el log (con rotacion segura).
  2. Muestra un dialogo NO fatal al usuario (acotado a 3 dialogos para evitar
     tormentas modales ante fallos en cascada).
  3. Permite que la aplicacion continue en un estado consistente en lugar de
     morir sin limpiar la sesion (que dejaria PHI temporal en disco).

Es la capa final del protocolo antifallo: los componentes ya capturan sus
errores esperables; esto cubre lo imprevisto.
"""
import sys
import logging
import traceback

logger = logging.getLogger("ecocardiograma")

# Acumulador de dialogos mostrados (evitar bucles de errores -> dialogo -> error)
_MAX_ERROR_DIALOGS = 3
_state = {"dialogs": 0, "dialogs_enabled": True}


def reset_error_guard() -> None:
    """Reinicia el contador de dialogos (util en tests)."""
    _state["dialogs"] = 0


def set_dialogs_enabled(enabled: bool) -> None:
    """Activa/desactiva los dialogos de error del excepthook.

    La suite de tests la desactiva (conftest): un exec() modal dentro de un
    test sin bucle de eventos activo bloquearia la ejecucion para siempre.
    """
    _state["dialogs_enabled"] = bool(enabled)


def _show_error_dialog(title: str, message: str) -> None:
    """Muestra un QMessageBox critico SOLO si es seguro hacerlo.

    Condiciones de seguridad (protocolo antifallo):
      - dialogos habilitados (tests los apagan).
      - existe una QApplication.
      - estamos en el hilo propietario de la app (UI). Desde otro hilo, o sin
        bucle de eventos, un exec() podria bloquear indefinidamente: entonces
        el error queda solo en el log.
    """
    try:
        if not _state["dialogs_enabled"]:
            return
        from PyQt6.QtCore import QThread
        from PyQt6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance()
        if app is None or QThread.currentThread() is not app.thread():
            return
        if _state["dialogs"] >= _MAX_ERROR_DIALOGS:
            logger.warning(
                "Se alcanzo el limite de dialogos de error (%d); "
                "el resto solo se registra en el log.",
                _MAX_ERROR_DIALOGS,
            )
            return
        _state["dialogs"] += 1
        box = QMessageBox(QMessageBox.Icon.Critical, title, message)
        box.exec()
    except Exception:  # noqa: BLE001 - mostrar el dialogo nunca debe fallar
        pass


def install_excepthook(allow_abort: bool = False) -> None:
    """Instala el excepthook antifallo de la aplicacion.

    Con ``allow_abort=False`` (por defecto) las excepciones no controladas se
    registran y se informan, pero no abortan el proceso: el cierre ordenado
    (borrado seguro de temporales) sigue garantizado.
    """
    def hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.error("Excepcion no controlada:\n%s", tb_text)
        _show_error_dialog(
            "Error inesperado",
            "Ocurrio un error inesperado y fue registrado en el log.\n"
            "La aplicacion continuara funcionando; si el problema persiste,\n"
            "use Archivo > Limpiar Sesion o reinicie la aplicacion.\n\n"
            f"{exc_type.__name__}: {exc_value}",
        )
        if allow_abort:
            sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = hook
