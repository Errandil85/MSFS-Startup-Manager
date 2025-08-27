from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QDialogButtonBox, QLabel, QCheckBox

class AddEditDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add/Edit Entry")

        self.name_edit = QLineEdit()
        self.path_edit = QLineEdit()
        self.args_edit = QLineEdit()
        self.enabled_check = QCheckBox("Enabled")
        self.enabled_check.setChecked(True)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Name:"))
        layout.addWidget(self.name_edit)
        layout.addWidget(QLabel("Path:"))
        layout.addWidget(self.path_edit)
        layout.addWidget(QLabel("Args:"))
        layout.addWidget(self.args_edit)
        layout.addWidget(self.enabled_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_data(self):
        return (
            self.name_edit.text(),
            self.path_edit.text(),
            self.args_edit.text(),
            self.enabled_check.isChecked()
        )
