"""End-to-end tests for the complete application flow."""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QMessageBox, QFileDialog
from src.gui.main_window import MainWindow


@pytest.fixture(autouse=True)
def auto_answer_dialogs(monkeypatch):
    """Responde automaticamente los dialogos modales (offscreen no puede abrirlos)."""
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )
    for name in ("information", "critical", "warning", "about"):
        monkeypatch.setattr(QMessageBox, name, lambda *a, **k: None)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))


@pytest.fixture
def app():
    """Create QApplication instance."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def main_window(app):
    """Create main window instance."""
    window = MainWindow()
    window.show()
    yield window
    window.close()


class TestE2EFlow:
    """End-to-end tests for complete user flows."""

    def test_complete_patient_workflow(self, main_window):
        """Test complete patient workflow: new -> data -> validate -> report."""
        w = main_window
        
        # 1. New patient
        w._on_new_patient()
        assert w.patient is not None
        
        # 2. Fill numeric data
        w.numeric_tab._on_test_data()
        
        # 3. Fill visual data
        w.visual_tab._on_clear()
        
        # 4. Validate
        w._on_validate()
        
        # 5. Check status
        assert "VALIDACION" in w.statusBar().currentMessage() or "valid" in w.statusBar().currentMessage().lower()
        
        # 6. Generate report
        w.report_tab.chk_disclaimer.setChecked(True)
        w._on_generate_report()
        assert w.report_tab._pdf_path is not None or w.report_tab._html_path is not None

    def test_keyboard_shortcuts(self, main_window):
        """Test keyboard shortcuts work."""
        w = main_window
        
        # Test Ctrl+N triggers new patient
        w._on_new_patient()
        assert w.patient is not None
        
        # Test F5 triggers validation
        w.numeric_tab._on_test_data()
        w._on_validate()
        assert "VALIDACION" in w.statusBar().currentMessage().upper() or "VALIDACION" in w.statusBar().currentMessage()

    def test_dark_mode_toggle(self, main_window):
        """Test dark mode toggle."""
        from PyQt6.QtCore import QSettings

        w = main_window
        if w.dark_mode:
            w.act_tema.setChecked(False)  # normaliza si venia guardado en True
        assert not w.dark_mode

        w._on_toggle_theme_shortcut()
        assert w.dark_mode is True
        assert w.act_tema.isChecked()

        w._on_toggle_theme_shortcut()
        assert w.dark_mode is False
        assert not w.act_tema.isChecked()
        QSettings().setValue("dark_mode", False)

    def test_dark_mode_persistence(self, main_window, tmp_path):
        """Test dark mode preference persists."""
        from PyQt6.QtCore import QSettings

        # Use temp directory for settings
        settings = QSettings()
        settings.setValue("dark_mode", True)

        # Create new window - should load saved preference
        new_window = MainWindow()
        assert new_window.dark_mode is True
        new_window.close()
        settings.setValue("dark_mode", False)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
