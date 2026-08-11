"""Tests unitarios para ReportEngine."""
import os
import pytest
from src.core.report_engine import ReportEngine
from src.core.validator import Validator
from src.core.visual_input import VisualInputHandler
from src.models.reference_range import ReferenceRanges, ReferenceRange
from src.models.patient import Patient, Sexo


@pytest.fixture
def report_engine(tmp_path):
    """Crea un ReportEngine con template de prueba."""
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template_path = template_dir / "test_template.html"

    template_path.write_text(
        "<html><body>"
        "<h1>Informe: {{ paciente_id }}</h1>"
        "<p>Sexo: {{ paciente_sexo }}</p>"
        "{% for row in tabla_validacion %}"
        "<p>{{ row.parametro }}: {{ row.valor }} ({{ row.unidad }})</p>"
        "{% endfor %}"
        "</body></html>"
    )

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    return ReportEngine(str(template_path), str(output_dir))


@pytest.fixture
def validator_with_ranges():
    ranges = ReferenceRanges()
    ranges._rangos[Sexo.MASCULINO]["DDI (mm)"] = ReferenceRange(
        parametro="DDI (mm)", limite_inferior=42, limite_superior=58, unidad="mm"
    )
    ranges._rangos[Sexo.MASCULINO]["FEVI (%)"] = ReferenceRange(
        parametro="FEVI (%)", limite_inferior=52, limite_superior=72, unidad="%"
    )
    return Validator(ranges)


class TestReportEngine:
    def test_generate_html_report(self, report_engine, validator_with_ranges, tmp_path):
        patient = Patient(
            id="TEST-001", sexo=Sexo.MASCULINO,
            ddi=50.0, fevi=60.0
        )
        visual_handler = VisualInputHandler()

        result = report_engine.generate_report(
            patient, validator_with_ranges, visual_handler,
            output_filename="test_informe.pdf"
        )

        assert os.path.exists(result)
        assert result.endswith(".html") or result.endswith(".pdf")

        # Verificar contenido HTML
        html_path = result.replace(".pdf", ".html")
        if os.path.exists(html_path):
            content = open(html_path).read()
            assert "TEST-001" in content
            assert "DDI (mm)" in content
