from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QDialogButtonBox,
    QLabel, QCheckBox, QFileDialog, QPushButton, QFrame, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
import os

from logging_config import get_logger

logger = get_logger(__name__)


class _PowerShellNameWorker(QThread):
    """
    Runs the PowerShell FileVersionInfo lookup off the GUI thread.

    This is only a fallback for executables pefile couldn't read metadata
    from. It used to run via a blocking subprocess.run(..., timeout=5) call
    directly in browse_executable(), which froze the whole dialog (and the
    app, since it's modal) for up to 5 seconds on every affected exe.
    """
    name_detected = Signal(str, str)  # file_path, detected_name

    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path

    def run(self):
        name = AddEditDialog.get_name_via_powershell(self.file_path)
        if name:
            self.name_detected.emit(self.file_path, name)


class ModernLineEdit(QLineEdit):
    def __init__(self, placeholder=""):
        super().__init__()
        self.setPlaceholderText(placeholder)
        self.setMinimumHeight(36)


class ModernCheckBox(QCheckBox):
    def __init__(self, text):
        super().__init__(text)
        self.setMinimumHeight(28)


class AddEditDialog(QDialog):
    def __init__(self, parent=None, title="Add Entry"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumSize(460, 300)  # Tighter than the old stacked-label layout
        self.setStyleSheet(self.get_light_dialog_stylesheet())

        # Tracks the last name we auto-filled, so a later async PowerShell
        # result knows whether it's safe to overwrite (user hasn't typed
        # their own name in the meantime) or should be discarded.
        self._auto_filled_name = None
        self._ps_worker = None
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Title
        title_label = QLabel(title)
        title_label.setObjectName("dialogTitle")
        layout.addWidget(title_label)
        
        # Form fields
        form_layout = self.create_form()
        layout.addLayout(form_layout)
        
        # Spacer
        spacer = QSpacerItem(20, 12, QSizePolicy.Minimum, QSizePolicy.Expanding)
        layout.addItem(spacer)
        
        # Buttons
        button_layout = self.create_buttons()
        layout.addLayout(button_layout)

    def closeEvent(self, event):
        """Make sure a still-running background name lookup doesn't outlive the dialog."""
        if self._ps_worker is not None and self._ps_worker.isRunning():
            self._ps_worker.quit()
            self._ps_worker.wait(1000)
        super().closeEvent(event)

    def create_form(self):
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # Name field
        self.name_edit = ModernLineEdit("e.g., FSUIPC7, FSRealistic")
        form.addRow("Name", self.name_edit)

        # Path field with browse button
        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self.path_edit = ModernLineEdit("C:\\Program Files\\...")
        browse_btn = QPushButton("...")
        browse_btn.setObjectName("browseButton")
        browse_btn.setFixedWidth(36)
        browse_btn.setMinimumHeight(36)
        browse_btn.clicked.connect(self.browse_executable)
        path_row.addWidget(self.path_edit)
        path_row.addWidget(browse_btn)
        form.addRow("Path", path_row)

        # Arguments field
        self.args_edit = ModernLineEdit("-auto, --silent (optional)")
        form.addRow("Arguments", self.args_edit)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setObjectName("separator")
        form.addRow(separator)

        # Enabled checkbox
        self.enabled_check = ModernCheckBox("Enable this addon on startup")
        self.enabled_check.setChecked(True)
        self.enabled_check.setObjectName("enabledCheck")
        form.addRow("", self.enabled_check)

        # Auto-close checkbox
        self.auto_close_check = ModernCheckBox("Auto-close when simulator stops")
        self.auto_close_check.setChecked(False)
        self.auto_close_check.setObjectName("autoCloseCheck")
        self.auto_close_check.setToolTip("Automatically close this addon when the simulator stops running")
        form.addRow("", self.auto_close_check)

        return form

    def create_buttons(self):
        layout = QHBoxLayout()
        layout.setSpacing(12)
        
        spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout.addItem(spacer)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelButton")
        cancel_btn.setMinimumHeight(36)
        cancel_btn.setMinimumWidth(90)
        cancel_btn.clicked.connect(self.reject)
        
        ok_btn = QPushButton("Save")
        ok_btn.setObjectName("okButton")
        ok_btn.setMinimumHeight(36)
        ok_btn.setMinimumWidth(90)
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        
        layout.addWidget(cancel_btn)
        layout.addWidget(ok_btn)
        
        return layout

    def browse_executable(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Executable",
            "",
            "Executable Files (*.exe);;All Files (*)"
        )
        if not file_path:
            return

        self.path_edit.setText(file_path)

        current_name = self.name_edit.text().strip()
        if current_name and current_name != "e.g., FSUIPC7, FSRealistic":
            # User already has a name in there (typed or from a previous
            # detection) - don't clobber it.
            return

        # Fast path: pefile metadata read, then a filename-cleanup fallback.
        # Both are local and near-instant, so this never noticeably blocks
        # the UI.
        fast_name = self.get_name_from_pefile(file_path)
        source = "pefile"
        if not fast_name:
            fast_name = self.get_name_from_filename(file_path)
            source = "filename"

        if fast_name:
            self.name_edit.setText(fast_name)
            self._auto_filled_name = fast_name

        if source == "pefile":
            return  # Already got a good name, no need for the slow fallback

        # Slow path: PowerShell's FileVersionInfo lookup is a better source
        # than the filename guess, but subprocess.run() to launch it can
        # take a few seconds. Run it in the background instead of blocking
        # this (modal) dialog and the whole app with it.
        self._start_powershell_lookup(file_path)

    def _start_powershell_lookup(self, file_path):
        if self._ps_worker is not None and self._ps_worker.isRunning():
            self._ps_worker.quit()
            self._ps_worker.wait(500)

        self._ps_worker = _PowerShellNameWorker(file_path, self)
        self._ps_worker.name_detected.connect(self._on_powershell_name_detected)
        self._ps_worker.start()

    def _on_powershell_name_detected(self, file_path, name):
        # The user may have picked a different executable, or typed their
        # own name, while the lookup was running - only apply this result
        # if neither of those happened.
        if self.path_edit.text().strip() != file_path:
            return
        current_name = self.name_edit.text().strip()
        if current_name and current_name != self._auto_filled_name:
            return  # user has since typed their own name - don't overwrite it
        self.name_edit.setText(name)
        self._auto_filled_name = name

    @staticmethod
    def get_name_from_pefile(file_path):
        """Try reading ProductName / FileDescription / InternalName via pefile. Fast, local, safe to call synchronously."""
        if not os.path.exists(file_path):
            return None
        try:
            import pefile

            pe = pefile.PE(file_path)

            if hasattr(pe, 'VS_VERSIONINFO'):
                for file_info in pe.FileInfo:
                    if hasattr(file_info, 'StringTable'):
                        for string_table in file_info.StringTable:
                            for key, value in string_table.entries.items():
                                if key.decode('utf-8', errors='ignore') == 'ProductName':
                                    product_name = value.decode('utf-8', errors='ignore').strip()
                                    if product_name:
                                        pe.close()
                                        return product_name

                            for key, value in string_table.entries.items():
                                if key.decode('utf-8', errors='ignore') == 'FileDescription':
                                    file_desc = value.decode('utf-8', errors='ignore').strip()
                                    if file_desc:
                                        pe.close()
                                        return file_desc

                            for key, value in string_table.entries.items():
                                if key.decode('utf-8', errors='ignore') == 'InternalName':
                                    internal_name = value.decode('utf-8', errors='ignore').strip()
                                    if internal_name:
                                        if internal_name.lower().endswith('.exe'):
                                            internal_name = internal_name[:-4]
                                        pe.close()
                                        return internal_name

            pe.close()
        except ImportError:
            pass
        except Exception as e:
            logger.info(f"pefile could not read metadata from {file_path}: {e}")

        return None

    @staticmethod
    def get_name_via_powershell(file_path):
        """
        Slow fallback: query FileVersionInfo via PowerShell. Only called from
        the background worker thread - never call this directly from the
        GUI thread, it can take several seconds.
        """
        try:
            import subprocess
            import json

            ps_command = f'''
            $version = [System.Diagnostics.FileVersionInfo]::GetVersionInfo("{file_path}")
            $result = @{{
                ProductName = $version.ProductName
                FileDescription = $version.FileDescription
                InternalName = $version.InternalName
            }}
            $result | ConvertTo-Json
            '''

            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout.strip())

                if data.get('ProductName') and data['ProductName'].strip():
                    return data['ProductName'].strip()

                if data.get('FileDescription') and data['FileDescription'].strip():
                    return data['FileDescription'].strip()

                if data.get('InternalName') and data['InternalName'].strip():
                    name = data['InternalName'].strip()
                    if name.lower().endswith('.exe'):
                        name = name[:-4]
                    return name

        except Exception as e:
            logger.info(f"PowerShell name lookup failed for {file_path}: {e}")

        return None

    @staticmethod
    def get_name_from_filename(file_path):
        """Instant fallback: clean up the bare filename. Always returns something."""
        try:
            base_name = os.path.splitext(os.path.basename(file_path))[0]

            import re
            cleaned_name = re.sub(r'\s*v?\d+(\.\d+)*\s*$', '', base_name, flags=re.IGNORECASE)

            suffixes_to_remove = ['_setup', '_installer', '_x64', '_x86', '_win64', '_win32']
            for suffix in suffixes_to_remove:
                if cleaned_name.lower().endswith(suffix.lower()):
                    cleaned_name = cleaned_name[:-len(suffix)]
                    break

            if cleaned_name:
                return ' '.join(word.capitalize() for word in cleaned_name.replace('_', ' ').replace('-', ' ').split())
            return base_name
        except Exception:
            return os.path.basename(file_path)

    def get_data(self):
        return (
            self.name_edit.text().strip(),
            self.path_edit.text().strip(),
            self.args_edit.text().strip(),
            self.enabled_check.isChecked(),
            self.auto_close_check.isChecked()

        )

    def get_light_dialog_stylesheet(self):
        """Light theme for dialogs, matching main.py's get_light_stylesheet()"""
        return """
        QDialog {
            background-color: #ffffff;
            color: #202124;
            font-family: 'Segoe UI', Consolas, 'Courier New', monospace;
        }
        
        QLabel#dialogTitle {
            font-size: 18px;
            font-weight: bold;
            color: #14202e;
            margin-bottom: 4px;
        }

        QLabel {
            font-size: 13px;
            color: #202124;
        }
        
        QLineEdit {
            background-color: #ffffff;
            color: #202124;
            border: 1px solid #c7cbd1;
            border-radius: 4px;
            padding: 8px 10px;
            font-size: 14px;
            selection-background-color: #1e88e5;
            selection-color: #ffffff;
        }
        
        QLineEdit:focus {
            border-color: #1e88e5;
        }
        
        QLineEdit:hover {
            border-color: #9aa0a6;
        }
        
        QLineEdit::placeholder {
            color: #9aa0a6;
        }
        
        QPushButton#browseButton {
            background-color: #ffffff;
            color: #202124;
            border: 1px solid #c7cbd1;
            border-radius: 4px;
            font-size: 14px;
        }
        
        QPushButton#browseButton:hover {
            background-color: #eef0f3;
            border-color: #9aa0a6;
        }
        
        QPushButton#browseButton:pressed {
            background-color: #dde5f0;
        }
        
        QCheckBox#enabledCheck, QCheckBox#autoCloseCheck {
            font-size: 13px;
            color: #202124;
            spacing: 8px;
        }
        
        QCheckBox#enabledCheck::indicator, QCheckBox#autoCloseCheck::indicator {
            width: 16px;
            height: 16px;
        }
        
        QCheckBox#enabledCheck::indicator:unchecked, QCheckBox#autoCloseCheck::indicator:unchecked {
            background-color: #ffffff;
            border: 1px solid #9aa0a6;
            border-radius: 3px;
        }
        
        QCheckBox#enabledCheck::indicator:unchecked:hover, QCheckBox#autoCloseCheck::indicator:unchecked:hover {
            border-color: #1e88e5;
        }
        
        QCheckBox#enabledCheck::indicator:checked, QCheckBox#autoCloseCheck::indicator:checked {
            background-color: #1e88e5;
            border: 1px solid #1a76c9;
            border-radius: 3px;
            image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xMC41IDFMNCAxLjVMMSAzLjUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+Cjwvc3ZnPgo=);
        }
        
        QCheckBox#enabledCheck::indicator:checked:hover, QCheckBox#autoCloseCheck::indicator:checked:hover {
            background-color: #2c94ee;
            border-color: #2c94ee;
        }
        
        QPushButton#okButton {
            background-color: #1e88e5;
            color: #ffffff;
            border: 1px solid #1a76c9;
            border-radius: 4px;
            padding: 8px 20px;
            font-size: 14px;
            font-weight: 500;
        }
        
        QPushButton#okButton:hover {
            background-color: #2c94ee;
        }
        
        QPushButton#okButton:pressed {
            background-color: #1670bd;
        }
        
        QPushButton#cancelButton {
            background-color: transparent;
            color: #202124;
            border: 1px solid #c7cbd1;
            border-radius: 4px;
            padding: 8px 20px;
            font-size: 14px;
        }
        
        QPushButton#cancelButton:hover {
            background-color: #eef0f3;
            border-color: #9aa0a6;
        }
        
        QPushButton#cancelButton:pressed {
            background-color: #dde5f0;
        }
        
        QFrame#separator {
            background-color: #d5d8dc;
            max-height: 1px;
            margin: 4px 0px;
        }
        
        QFileDialog {
            background-color: #ffffff;
            color: #202124;
        }
        """
