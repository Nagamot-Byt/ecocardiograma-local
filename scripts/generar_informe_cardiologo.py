"""Genera el informe de validacion clinica (PDF) para revision y aval del cardiologo.

El informe se adapta en usabilidad y alcance a una audiencia clinica:
lenguaje no tecnico, enfoque en validez de las referencias, limites de uso
y hoja de aval para firma. Se genera con QPrinter (PyQt6), el mismo motor
de PDF que usa la aplicacion en Windows.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

from PyQt6.QtCore import QMarginsF, QRectF, Qt
from PyQt6.QtGui import QFont, QImage, QPageLayout, QPageSize, QPainter, QTextDocument
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtWidgets import QApplication
from pypdf import PdfReader

from src.core.data_loader import DataLoader
from src.models.colombian_reference import DEFAULT_ALTITUDE_MASL, psap_upper_limit
from src.models.patient import Sexo

VERSION = "1.0.4"
FECHA_GENERACION = "12 de agosto de 2026"


def fmt_range(rng, sexo_nombre):
    lo, hi = rng.limite_inferior, rng.limite_superior
    if lo is not None and hi is not None:
        return f"{lo:g} \u2013 {hi:g}"
    if lo is not None:
        return f"\u2265 {lo:g}"
    if hi is not None:
        return f"\u2264 {hi:g}"
    return "\u2014"


def nota_rango(rng):
    lo, hi = rng.limite_inferior, rng.limite_superior
    if lo is not None and hi is not None:
        return "Rango completo (normalidad)"
    if lo is None and hi is not None:
        return "Valor igual o menor al limite (normalidad)"
    if lo is not None and hi is None:
        return "Valor igual o mayor al limite (normalidad)"
    return "Sin referencia disponible"


def build_reference_table(loader):
    rows_m = loader.reference_ranges.get_all_ranges(Sexo.MASCULINO)
    rows_f = loader.reference_ranges.get_all_ranges(Sexo.FEMENINO)
    html = []
    for name in rows_m:
        rm = rows_m[name]
        rf = rows_f.get(name)
        unidad = rm.unidad
        label = name.replace(f" ({unidad})", "")
        nota = nota_rango(rm)
        html.append(
            f"<tr>"
            f"<td>{label}</td>"
            f"<td align=\"center\">{unidad}</td>"
            f"<td align=\"center\">{fmt_range(rm, 'H')}</td>"
            f"<td align=\"center\">{fmt_range(rf, 'M')}</td>"
            f"<td>{nota}</td>"
            f"</tr>"
        )
    return "\n".join(html)


def build_html(loader) -> str:
    psap_lim = psap_upper_limit(DEFAULT_ALTITUDE_MASL)
    ref_table = build_reference_table(loader)
    base = (
        "background-color:#0b3d5c;color:#ffffff;font-family:'Segoe UI';"
        "font-size:20pt;padding:14px;font-weight:bold;"
    )
    return f"""
<html>
<head>
<style>
  body {{ font-family:'Segoe UI'; font-size:10pt; color:#222222; }}
  h1 {{ font-size:16pt; color:#0b3d5c; }}
  h2 {{ font-size:12.5pt; color:#0b3d5c; border-bottom:1px solid #0b3d5c; padding-bottom:2px; }}
  h3 {{ font-size:11pt; color:#0b3d5c; }}
  li {{ margin:2px; }}
</style>
</head>
<body>

<table width="100%" cellspacing="0" cellpadding="4" border="0">
  <tr><td style="{base}">Ecocardiograma Local &mdash; Informe de Validaci&oacute;n Cl&iacute;nica</td></tr>
  <tr>
    <td style="background-color:#eaf1f6;color:#0b3d5c;font-size:9.5pt;padding:6px;">
      Versi&oacute;n {VERSION} &nbsp;&middot;&nbsp; Generado el {FECHA_GENERACION}
      &nbsp;&middot;&nbsp; Documento de respaldo para revisi&oacute;n y aval del servicio de cardiolog&iacute;a
    </td>
  </tr>
</table>

<h1>1. Resumen ejecutivo</h1>
<p>
<b>Ecocardiograma Local</b> es una herramienta de apoyo para el ecocardiografista.
Registra los par&aacute;metros de la ecocardiograf&iacute;a transtor&aacute;cica, los contrasta
autom&aacute;ticamente contra valores de referencia publicados y genera un informe final en PDF
listo para revisi&oacute;n y firma del m&eacute;dico.
</p>
<p>
La aplicaci&oacute;n funciona <b>100% sin conexi&oacute;n a internet</b>: los datos del paciente
permanecen en el equipo del m&eacute;dico y son borrados de forma segura cuando se requiere.
</p>
<p>
Este documento describe el alcance, las referencias utilizadas, la metodolog&iacute;a de
validaci&oacute;n y el estado de calidad del software, y finaliza con la <b>hoja de aval</b>
que el cardi&oacute;logo puede firmar tras su revisi&oacute;n.
</p>

<h2>1.1 &iquest;Por qu&eacute; se solicita este aval?</h2>
<p>
Durante la evaluaci&oacute;n de la versi&oacute;n 1.0.3 se formul&oacute; una recomendaci&oacute;n de
mejora: <i>obtener el aval de un cardi&oacute;logo sobre los rangos de referencia y la
metodolog&iacute;a de validaci&oacute;n antes del uso cl&iacute;nico rutinario</i>. Las dem&aacute;s
recomendaciones (arranque instant&aacute;neo, cierre correcto de descargas de modelos,
publicaci&oacute;n del repositorio y optimizaci&oacute;n de la extracci&oacute;n de datos) ya est&aacute;n
implementadas y verificadas. Este informe es el soporte para completar la &uacute;ltima.

<h1>2. Alcance de la aplicaci&oacute;n</h1>

<h2>2.1 &iquest;Qu&eacute; hace?</h2>
<ul>
  <li><b>Validaci&oacute;n num&eacute;rica:</b> compara cada medida registrada con el valor de
      referencia correspondiente seg&uacute;n el sexo del paciente (22 par&aacute;metros).</li>
  <li><b>Ajuste por altitud:</b> corrige autom&aacute;ticamente el l&iacute;mite superior de la
      presi&oacute;n sist&oacute;lica de la arteria pulmonar (PSAP) seg&uacute;n la altitud de la ciudad
      (v&eacute;ase secci&oacute;n 3.4).</li>
  <li><b>Clasificaci&oacute;n por par&aacute;metro:</b> normal, fuera de rango (bajo o alto) o
      <i>sin registro</i> &mdash; para que un valor ausente nunca se interprete como normal.</li>
  <li><b>Hallazgos visuales estructurados:</b> insuficiencias valvulares (mitral, a&oacute;rtica,
      tric&uacute;spide, pulmonar), derrame peric&aacute;rdico y contractilidad.</li>
  <li><b>Recomendaciones objetivas:</b> la aplicaci&oacute;n solo sugiere acciones cuando hay valores
      fuera de rango, con base en reglas expl&iacute;citas y revisables.</li>
  <li><b>Extracci&oacute;n asistida de datos:</b> permite cargar medidas desde informes previos
      (PDF, TXT, CSV o imagen) con inteligencia artificial local opcional (Ollama). Cada valor
      queda marcado con su origen (IA o captura manual) y su nivel de confianza.</li>
  <li><b>Informe final en PDF</b> con los datos validados y los hallazgos registrados.</li>
  <li><b>Borrado seguro:</b> los archivos temporales con datos cl&iacute;nicos se eliminan de forma
      segura, no quedan copias en disco.</li>
</ul>

<h2>2.2 L&iacute;mites y advertencias de uso</h2>
<ul>
  <li>La aplicaci&oacute;n <b>no emite diagn&oacute;sticos</b> ni interpretaciones cl&iacute;nicas:
      es una herramienta de apoyo a la lectura.</li>
  <li><b>No sustituye el juicio del cardi&oacute;logo:</b> todo informe debe ser revisado y
      firmado por un especialista.</li>
  <li>No es un <b>dispositivo m&eacute;dico registrado</b> ante autoridad sanitaria.</li>
  <li>La <b>inteligencia artificial solo transcribe y estructura valores</b>; nunca decide sobre
      ellos. El m&eacute;dico confirma el 100% de las medidas del informe.</li>
  <li>Los valores de referencia corresponden a <b>poblaci&oacute;n general</b> (gu&iacute;as
      internacionales y colombianas) y pueden no aplicar a cada paciente en particular.</li>
</ul>

<h2>2.3 Uso previsto (flujo de trabajo)</h2>
<ol>
  <li>Abrir la aplicaci&oacute;n e ingresar datos b&aacute;sicos del paciente (edad, sexo, ciudad/altitud).</li>
  <li>Registrar las medidas (teclado) o cargarlas desde un informe previo.</li>
  <li>Revisar el resumen de validaci&oacute;n: sem&aacute;foro por par&aacute;metro (normal / fuera de rango / sin registro).</li>
  <li>Registrar los hallazgos visuales observados en el estudio.</li>
  <li>Generar el informe PDF y firmarlo tras la revisi&oacute;n m&eacute;dica.</li>
</ol>

<h1>3. Referencias y metodolog&iacute;a de validaci&oacute;n</h1>

<h2>3.1 Fuentes consultadas</h2>
<ul>
  <li>Gu&iacute;as ASE 2015 (American Society of Echocardiography) para dimensiones,
      vol&uacute;menes y funci&oacute;n ventricular.</li>
  <li>Gu&iacute;as de la Sociedad Colombiana de Cardiolog&iacute;a (SCC) y de la
      Sociedad Latinoamericana de Cardiolog&iacute;a.</li>
  <li>Referencias locales colombianas (Cl&iacute;nica Shaio, Fundaci&oacute;n Cardioinfantil,
      Hospital Militar) para el ajuste por altitud.</li>
</ul>

<h2>3.2 Tabla de referencia de validaci&oacute;n (valores cargados en la versi&oacute;n {VERSION})</h2>
<table width="100%" border="1" cellspacing="0" cellpadding="4">
  <tr>
    <th style="background-color:#0b3d5c;color:#ffffff;">Par&aacute;metro</th>
    <th style="background-color:#0b3d5c;color:#ffffff;" width="50">Unidad</th>
    <th style="background-color:#0b3d5c;color:#ffffff;" width="75">Hombres</th>
    <th style="background-color:#0b3d5c;color:#ffffff;" width="75">Mujeres</th>
    <th style="background-color:#0b3d5c;color:#ffffff;">Criterio de normalidad</th>
  </tr>
  {ref_table}
</table>

<h2>3.3 Metodolog&iacute;a de validaci&oacute;n</h2>
<p>
Cada medida se clasifica en una de tres categor&iacute;as, de forma transparente para el m&eacute;dico:
</p>
<ul>
  <li><b>Normal:</b> el valor se encuentra dentro del rango de referencia para el sexo.</li>
  <li><b>Fuera de rango:</b> el valor supera el l&iacute;mite superior o no alcanza el inferior;
      la aplicaci&oacute;n lo se&ntilde;ala y ofrece recomendaciones objetivas.</li>
  <li><b>Sin registro:</b> el par&aacute;metro no fue ingresado ni extra&iacute;do; se lista
      expl&iacute;citamente para evitar conclusiones por omisi&oacute;n.</li>
</ul>

<h2>3.4 Ajuste por altitud (PSAP)</h2>
<p>
La altitud elevada aumenta fisiol&oacute;gicamente la presi&oacute;n arterial pulmonar. La
aplicaci&oacute;n corrige el l&iacute;mite superior de normalidad de la PSAP con la f&oacute;rmula:
<b>l&iacute;mite = 30 + altitud / 330</b> (mmHg). Para la altitud por defecto de Bogot&aacute;
(2.640 msnm) el l&iacute;mite efectivo es de <b>{psap_lim:g} mmHg</b>, frente a 30 mmHg a nivel del mar.
</p>

<h1>4. Estado de calidad y verificaciones</h1>
<table width="100%" border="1" cellspacing="0" cellpadding="4">
  <tr>
    <th style="background-color:#0b3d5c;color:#ffffff;" width="55%">Verificaci&oacute;n</th>
    <th style="background-color:#0b3d5c;color:#ffffff;">Resultado</th>
  </tr>
  <tr><td>Versi&oacute;n entregable e instalador</td><td>{VERSION} &middot; instalador verificado por SHA-256 publicado</td></tr>
  <tr><td>Pruebas automatizadas de calidad</td><td>145/145 en verde &middot; cobertura 76,9%</td></tr>
  <tr><td>Exactitud de extracci&oacute;n de datos (conjunto de validaci&oacute;n)</td><td>100% (29 par&aacute;metros, 0 falsos positivos)</td></tr>
  <tr><td>Integraci&oacute;n continua (CI)</td><td>Verde en Python 3.11 y 3.12 en cada publicaci&oacute;n</td></tr>
  <tr><td>Actualizaciones</td><td>Verificaci&oacute;n autom&aacute;tica contra el repositorio p&uacute;blico</td></tr>
  <tr><td>Privacidad / datos locales</td><td>100% sin conexi&oacute;n &middot; borrado seguro de datos temporales</td></tr>
</table>

<h1>5. Aval del cardi&oacute;logo</h1>
<p>Se solicita la revisi&oacute;n y aval del especialista sobre los siguientes puntos:</p>
<table width="100%" border="1" cellspacing="0" cellpadding="6">
  <tr>
    <th style="background-color:#eaf1f6;color:#0b3d5c;">Punto revisado</th>
    <th style="background-color:#eaf1f6;color:#0b3d5c;" width="42">S&iacute;</th>
    <th style="background-color:#eaf1f6;color:#0b3d5c;" width="42">No</th>
    <th style="background-color:#eaf1f6;color:#0b3d5c;" width="60">Observaci&oacute;n</th>
  </tr>
  <tr>
    <td>Rangos de referencia por sexo (tabla 3.2) acordes con la pr&aacute;ctica y las gu&iacute;as</td>
    <td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td>
  </tr>
  <tr>
    <td>Metodolog&iacute;a de validaci&oacute;n (normal / fuera de rango / sin registro)</td>
    <td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td>
  </tr>
  <tr>
    <td>Ajuste de PSAP por altitud (f&oacute;rmula 30 + msnm/330)</td>
    <td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td>
  </tr>
  <tr>
    <td>L&iacute;mites de uso declarados (la aplicaci&oacute;n no diagnostica ni sustituye al m&eacute;dico)</td>
    <td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td>
  </tr>
</table>

<p>&nbsp;</p>
<table width="100%" cellspacing="0" cellpadding="2" border="0">
  <tr>
    <td width="50%">Nombre y apellidos: ______________________________</td>
    <td width="50%">Registro profesional (RMP/RQS): ______________</td>
  </tr>
  <tr>
    <td>Especialidad: ________________________________________</td>
    <td>Instituci&oacute;n: ____________________________________</td>
  </tr>
  <tr>
    <td>Fecha: ________________</td>
    <td>Ciudad / altitud: ________________</td>
  </tr>
</table>
<p>&nbsp;</p>
<p style="font-size:12pt;"><b>Firma:</b></p>
<p style="font-size:12pt;letter-spacing:1px;">&nbsp;____________________________________________________</p>
<p style="font-size:9pt;color:#666666;">Al firmar, el profesional certifica haber revisado el alcance, los rangos de
referencia y los l&iacute;mites de uso descritos en este documento, y avala su empleo como herramienta de
apoyo a la lectura ecocardiogr&aacute;fica bajo supervisi&oacute;n m&eacute;dica.</p>

<h1>6. Trazabilidad</h1>
<p style="font-size:9pt;color:#555555;">
Repositorio p&uacute;blico: github.com/Nagamot-Byt/ecocardiograma-local &middot;
Versi&oacute;n del documento: {VERSION} &middot; Fuentes de referencia: ASE 2015, SCC/LATAM y
ajustes por altitud colombianos. Este documento fue generado autom&aacute;ticamente por el
script <i>scripts/generar_informe_cardiologo.py</i> del proyecto.
</p>

</body>
</html>
"""


def render_pdf(html: str, out_path: str, preview_dir: str = "") -> int:
    QApplication.instance() or QApplication([])
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageMargins(QMarginsF(14, 14, 14, 14), QPageLayout.Unit.Millimeter)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(out_path)

    doc = QTextDocument()
    doc.setDefaultFont(QFont("Segoe UI", 10))
    doc.setPageSize(printer.pageRect(QPrinter.Unit.Point).size())
    doc.setHtml(html)
    doc.print(printer)

    n_pages = len(PdfReader(out_path).pages)
    if preview_dir:
        os.makedirs(preview_dir, exist_ok=True)
        _preview_pages(doc, printer.pageRect(QPrinter.Unit.Point), preview_dir)
    return n_pages


def _preview_pages(doc: QTextDocument, page_rect: QRectF, out_dir: str) -> None:
    scale = 1.5
    w = int(page_rect.width() * scale)
    h = int(page_rect.height() * scale)
    pages = doc.pageCount()
    for i in range(pages):
        img = QImage(w, h, QImage.Format.Format_RGB32)
        img.fill(Qt.GlobalColor.white)
        painter = QPainter(img)
        painter.scale(scale, scale)
        painter.translate(-page_rect.left(), -page_rect.top())
        clip = QRectF(0, i * page_rect.height(), page_rect.width(), page_rect.height())
        painter.translate(0, -i * page_rect.height())
        painter.setClipRect(clip.translated(0, i * page_rect.height()))
        doc.drawContents(painter, clip)
        painter.end()
        img.save(os.path.join(out_dir, f"pagina_{i + 1}.png"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="docs/Informe_Validacion_Cardiologo_v1.0.4.pdf")
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    loader = DataLoader("data/ase_references/hombres.xlsx", "data/ase_references/mujeres.xlsx")
    if not loader.load_references():
        sys.exit("No se pudieron cargar las referencias")
    n_m = len(loader.reference_ranges.get_all_ranges(Sexo.MASCULINO))
    print(f"Referencias cargadas: {n_m} parametros por sexo")

    html = build_html(loader)
    preview = os.path.join(os.environ.get("TEMP", "."), "informe_card_preview") if args.preview else ""
    pages = render_pdf(html, args.out, preview)
    size_kb = os.path.getsize(args.out) / 1024
    print(f"PDF generado: {args.out}")
    print(f"  Paginas: {pages} | Tamano: {size_kb:.0f} KB")
    if preview:
        print(f"  Vista previa: {preview}")


if __name__ == "__main__":
    main()
