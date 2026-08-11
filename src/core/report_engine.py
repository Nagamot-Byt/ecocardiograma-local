"""
Motor de generacion de informes.
Combina datos numericos + visuales, renderiza HTML con Jinja2 y convierte a PDF.

Conversion a PDF en cascada para que funcione en Windows y en Linux/Mac:
  1. WeasyPrint (necesita GTK, disponible en Linux/Mac).
  2. QPrinter + QTextDocument de PyQt6 (fallback universal, no requiere GTK).
"""
import os
import re
from datetime import datetime
from typing import Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
from src.models.patient import Patient
from src.core.validator import Validator
from src.core.visual_input import VisualInputHandler
from src.models.colombian_reference import psap_upper_limit
from src.utils.logger import setup_logger
from src.utils.helpers import format_number, safe_filename

logger = setup_logger()


class ReportEngine:
    """Genera informes PDF de ecocardiograma a partir de datos del paciente."""

    def __init__(
        self,
        template_path: str,
        output_dir: str,
        guide_name: str = "Guias Colombianas SCC/LATAM",
        altitude_masl: Optional[float] = None,
    ):
        self.template_path = template_path
        self.output_dir = output_dir
        self.guide_name = guide_name
        self.altitude_masl = altitude_masl

        # Configurar Jinja2
        template_dir = os.path.dirname(template_path)
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html"]),
        )

    def generate_report(
        self,
        patient: Patient,
        validator: Validator,
        visual_handler: VisualInputHandler,
        output_filename: str = None,
    ) -> str:
        """
        Genera el informe PDF y retorna la ruta del archivo generado.
        """
        # Construir contexto de datos
        context = self._build_context(patient, validator, visual_handler)

        # Renderizar HTML
        template_name = os.path.basename(self.template_path)
        template = self.env.get_template(template_name)
        html_content = template.render(**context)

        # Guardar HTML temporal
        os.makedirs(self.output_dir, exist_ok=True)
        if output_filename is None:
            output_filename = safe_filename("informe_eco", ".pdf")

        html_path = output_filename.replace(".pdf", ".html")
        html_full_path = os.path.join(self.output_dir, html_path)
        pdf_full_path = os.path.join(self.output_dir, output_filename)

        with open(html_full_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # Convertir HTML a PDF (WeasyPrint -> QPrinter/PyQt6)
        pdf_ok = self._render_html_to_pdf(html_content, pdf_full_path)
        if pdf_ok:
            logger.info(f"Informe PDF generado: {os.path.basename(pdf_full_path)}")
            return pdf_full_path

        logger.warning(
            "No se pudo generar PDF. Se retorna solo HTML: "
            + os.path.basename(html_full_path)
        )
        return html_full_path

    @staticmethod
    def _weasyprint_available() -> bool:
        """Verifica si las librerias GTK de WeasyPrint estan instaladas.

        En Windows casi nunca lo estan; importar weasyprint sin ellas imprime
        un bloque ruidoso a stderr, asi que se evita el import en ese caso.
        """
        try:
            import ctypes.util

            for name in ("gobject-2.0-0", "gobject-2.0", "libgobject-2.0-0"):
                if ctypes.util.find_library(name):
                    return True
        except Exception:  # noqa: BLE001
            pass
        return False

    def _render_html_to_pdf(self, html_content: str, pdf_path: str) -> bool:
        """
        Convierte HTML a PDF. Prueba WeasyPrint y cae a QPrinter (PyQt6).
        Retorna True si el PDF se genero correctamente.
        """
        # 1) WeasyPrint (Linux/Mac; requiere GTK)
        if self._weasyprint_available():
            try:
                from weasyprint import HTML

                HTML(string=html_content).write_pdf(pdf_path)
                return True
            except Exception as e:  # noqa: BLE001 - cualquier fallo activa el fallback
                logger.warning(f"WeasyPrint fallo: {e}")
        else:
            logger.info("WeasyPrint no disponible (sin GTK). Se usara QPrinter (PyQt6).")

        # 2) QPrinter + QTextDocument (PyQt6, funciona en Windows sin GTK)
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtGui import QPageSize, QTextDocument
            from PyQt6.QtPrintSupport import QPrinter

            # Mantener referencia al QApplication (se crea si no existe)
            app = QApplication.instance() or QApplication([])  # noqa: F841

            # QTextDocument ignora <head>/<style>, asi que se extraen por separado
            css = ""
            css_match = re.search(r"<style[^>]*>(.*?)</style>", html_content, re.S)
            if css_match:
                css = css_match.group(1)

            body_match = re.search(r"<body[^>]*>(.*)</body>", html_content, re.S)
            body = body_match.group(1) if body_match else html_content

            doc = QTextDocument()
            if css:
                doc.setDefaultStyleSheet(css)
            doc.setHtml(body)

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(pdf_path)
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            doc.print(printer)
            return True
        except Exception as e:  # noqa: BLE001 - sin PDF, se retorna HTML
            logger.error(f"QPrinter/PyQt6 tampoco disponible: {e}")
            return False

    def _build_context(
        self,
        patient: Patient,
        validator: Validator,
        visual_handler: VisualInputHandler,
    ) -> dict:
        """Construye el contexto de datos para la plantilla Jinja2."""
        # Tabla de validacion
        validation_rows = validator.get_validation_table(patient)

        # Datos numericos formateados
        numeric_data = patient.get_numeric_fields()
        numeric_formatted = {
            k: format_number(v) for k, v in numeric_data.items()
        }

        # Hallazgos visuales
        visual_data = patient.get_visual_fields()
        visual_summary = visual_handler.get_summary(patient)

        # Nota metodologica por altitud (solo si el informe lleva PSAP)
        nota_altitud = ""
        if self.altitude_masl and "PSAP (mmHg)" in numeric_data:
            lim = psap_upper_limit(self.altitude_masl)
            alt_text = f"{int(self.altitude_masl):,}".replace(",", ".")
            nota_altitud = (
                f"PSAP: limite superior de normalidad ajustado por altitud "
                f"({lim} mmHg a {alt_text} msnm; referencia 30 mmHg a nivel del mar)."
            )

        # Alertas de valores fuera de rango
        validation_summary = validator.get_summary(patient)

        # Trazabilidad de la IA (modelo y confianza media)
        ia_confidence = patient.ia_confidence
        ia_confidence_pct = ""
        if patient.ia_model and isinstance(ia_confidence, (int, float)) and 0 <= ia_confidence <= 1:
            ia_confidence_pct = f"{round(ia_confidence * 100)}%"

        now = datetime.now()

        context = {
            # Datos del paciente
            "paciente_id": patient.id,
            "paciente_sexo": patient.sexo.value,
            "paciente_edad": patient.edad or "No registrada",
            "nombre_medico": patient.nombre_medico or "",
            "fecha_estudio": patient.fecha_estudio or now.strftime("%d/%m/%Y"),
            "fecha_generacion": now.strftime("%d/%m/%Y %H:%M"),
            # Datos numericos
            "datos_numericos": numeric_data,
            "datos_formateados": numeric_formatted,
            "tabla_validacion": validation_rows,
            # Hallazgos visuales
            "datos_visuales": visual_data,
            "resumen_visual": visual_summary,
            # Resumen
            "resumen_validacion": validation_summary,
            "notas": patient.notas or "",
            "nota_altitud": nota_altitud,
            # IA
            "impresion_clinica": patient.impresion_clinica or "",
            "recomendaciones": list(patient.recomendaciones or []),
            "guia_nombre": self.guide_name,
            "ia_model": patient.ia_model or "",
            "ia_source": patient.ia_source or "",
            "ia_confidence": ia_confidence_pct,
            # Funciones helper
            "format_number": format_number,
        }

        return context
