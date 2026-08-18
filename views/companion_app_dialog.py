from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QLabel, QCheckBox, QFileDialog, QPushButton, QFrame, QSpacerItem, QSizePolicy,
    QMessageBox, QSpinBox
)
from PySide6.QtCore import Qt

from logging_config import get_logger
# Reuse the exe-name-detection logic (pefile / background PowerShell
# fallback / filename cleanup) and the light dialog stylesheet from
# AddEditDialog instead of duplicating ~150 lines of near-identical code.
from views.add_edit_dialog import AddEditDialog, _PowerShellNameWorker

logger = get_logger(__name__)


class ModernLineEdit(QLineEdit):
    def __init__(self, placeholder=""):
        super().__init__()
        self.setPlaceholderText(placeholder)
        self.setMinimumHeight(36)


class ModernCheckBox(QCheckBox):
    def __init__(self, text):
        super().__init__(text)
        self.setMinimumHeight(28)


class CompanionAppDialog(QDialog):
    """
    Add/Edit dialog for a standalone companion app (Little Navmap,
    Navigraph Charts, ACARS clients, etc.) - launched directly by this
    app via subprocess, independent of exe.xml, never a child process of
    the simulator.
    """

    NAME_PLACEHOLDER = "e.g., Little Navmap, Navigraph Charts"

    def __init__(self, parent=None, title="Add Companion App"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumSize(460, 360)
        # get_light_dialog_stylesheet doesn't touch self internally - it's
        # a pure constant - so calling it unbound avoids instantiating a
        # whole AddEditDialog just to borrow its stylesheet string.
        self.setStyleSheet(AddEditDialog.get_light_dialog_stylesheet(None))

        self._auto_filled_name = None
        self._ps_worker = None

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title_label = QLabel(title)
        title_label.setObjectName("dialogTitle")
        layout.addWidget(title_label)

        layout.addLayout(self.create_form())

        spacer = QSpacerItem(20, 12, QSizePolicy.Minimum, QSizePolicy.Expanding)
        layout.addItem(spacer)

        layout.addLayout(self.create_buttons())

    def closeEvent(self, event):
        if self._ps_worker is not None and self._ps_worker.isRunning():
            self._ps_worker.quit()
            self._ps_worker.wait(1000)
        super().closeEvent(event)

    def create_form(self):
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.name_edit = ModernLineEdit(self.NAME_PLACEHOLDER)
        form.addRow("Name", self.name_edit)

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

        self.args_edit = ModernLineEdit("(optional)")
        form.addRow("Arguments", self.args_edit)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setObjectName("separator")
        form.addRow(separator)

        self.enabled_check = ModernCheckBox("Enabled")
        self.enabled_check.setChecked(True)
        self.enabled_check.setObjectName("enabledCheck")
        self.enabled_check.setToolTip(
            "Whether this app is eligible for automatic start/stop with the "
            "simulator. Manual Start/Stop always work regardless of this."
        )
        form.addRow("", self.enabled_check)

        self.start_with_sim_check = ModernCheckBox("Start automatically when the simulator starts")
        self.start_with_sim_check.setObjectName("autoCloseCheck")
        form.addRow("", self.start_with_sim_check)

        delay_row = QHBoxLayout()
        delay_row.setSpacing(8)
        self.start_delay_spin = QSpinBox()
        self.start_delay_spin.setRange(0, 3600)
        self.start_delay_spin.setSuffix(" sec")
        self.start_delay_spin.setMinimumHeight(32)
        self.start_delay_spin.setToolTip(
            "Wait this many seconds after the simulator starts before launching this "
            "app. Useful for tools that need the sim further along before connecting "
            "(e.g. waiting for a flight to load). 0 = launch immediately."
        )
        self.start_delay_spin.setEnabled(False)  # only meaningful when Start w/ Sim is checked
        self.start_with_sim_check.toggled.connect(self.start_delay_spin.setEnabled)
        delay_row.addWidget(self.start_delay_spin)
        delay_row.addStretch()
        form.addRow("Start delay", delay_row)

        self.stop_with_sim_check = ModernCheckBox("Stop automatically when the simulator stops")
        self.stop_with_sim_check.setObjectName("autoCloseCheck")
        form.addRow("", self.stop_with_sim_check)

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
        ok_btn.clicked.connect(self.validate_and_accept)

        layout.addWidget(cancel_btn)
        layout.addWidget(ok_btn)
        return layout

    def browse_executable(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Executable", "", "Executable Files (*.exe);;All Files (*)"
        )
        if not file_path:
            return
        self.path_edit.setText(file_path)

        current_name = self.name_edit.text().strip()
        if current_name and current_name != self.NAME_PLACEHOLDER:
            return  # user already has a name typed in - don't clobber it

        # Fast synchronous path (pefile, then filename cleanup) - both
        # local and near-instant.
        fast_name = AddEditDialog.get_name_from_pefile(file_path)
        source = "pefile"
        if not fast_name:
            fast_name = AddEditDialog.get_name_from_filename(file_path)
            source = "filename"

        if fast_name:
            self.name_edit.setText(fast_name)
            self._auto_filled_name = fast_name

        if source == "pefile":
            return

        # Slow fallback (PowerShell FileVersionInfo) - runs in the
        # background so it never blocks this dialog.
        self._start_powershell_lookup(file_path)

    def _start_powershell_lookup(self, file_path):
        if self._ps_worker is not None and self._ps_worker.isRunning():
            self._ps_worker.quit()
            self._ps_worker.wait(500)
        self._ps_worker = _PowerShellNameWorker(file_path, self)
        self._ps_worker.name_detected.connect(self._on_powershell_name_detected)
        self._ps_worker.start()

    def _on_powershell_name_detected(self, file_path, name):
        if self.path_edit.text().strip() != file_path:
            return
        current_name = self.name_edit.text().strip()
        if current_name and current_name != self._auto_filled_name:
            return
        self.name_edit.setText(name)
        self._auto_filled_name = name

    def validate_and_accept(self):
        """
        Require a non-blank Name and Path before accepting. A blank name
        previously slipped through silently (e.g. if auto-detection from
        the exe failed and the user didn't notice/fill it in manually),
        which caused every blank-named entry to collide onto the same
        process-tracking key and falsely share "Running" status with
        each other.
        """
        name = self.name_edit.text().strip()
        path = self.path_edit.text().strip()

        if not name:
            QMessageBox.warning(
                self, "Name Required",
                "Please enter a name for this app (or use Browse to auto-detect one)."
            )
            self.name_edit.setFocus()
            return

        if not path:
            QMessageBox.warning(self, "Path Required", "Please select the executable for this app.")
            self.path_edit.setFocus()
            return

        self.accept()

    def get_data(self):
        return (
            self.name_edit.text().strip(),
            self.path_edit.text().strip(),
            self.args_edit.text().strip(),
            self.enabled_check.isChecked(),
            self.start_with_sim_check.isChecked(),
            self.stop_with_sim_check.isChecked(),
            self.start_delay_spin.value(),
        )