from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QDialogButtonBox, 
    QLabel, QCheckBox, QFileDialog, QPushButton, QFrame, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class ModernLineEdit(QLineEdit):
    def __init__(self, placeholder=""):
        super().__init__()
        self.setPlaceholderText(placeholder)
        self.setMinimumHeight(40)


class ModernCheckBox(QCheckBox):
    def __init__(self, text):
        super().__init__(text)
        self.setMinimumHeight(32)


class AddEditDialog(QDialog):
    def __init__(self, parent=None, title="Add Entry"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumSize(500, 350)
        self.setStyleSheet(self.get_dialog_stylesheet())
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setSpacing(24)
        layout.setContentsMargins(32, 32, 32, 32)
        
        # Title
        title_label = QLabel(title)
        title_label.setObjectName("dialogTitle")
        layout.addWidget(title_label)
        
        # Form fields
        form_layout = self.create_form()
        layout.addLayout(form_layout)
        
        # Spacer
        spacer = QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        layout.addItem(spacer)
        
        # Buttons
        button_layout = self.create_buttons()
        layout.addLayout(button_layout)

    def create_form(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        
        # Name field
        name_label = QLabel("Application Name")
        name_label.setObjectName("fieldLabel")
        self.name_edit = ModernLineEdit("e.g., FSUIPC7, FSRealistic")
        
        layout.addWidget(name_label)
        layout.addWidget(self.name_edit)
        
        # Path field with browse button
        path_label = QLabel("Executable Path")
        path_label.setObjectName("fieldLabel")
        
        path_layout = QHBoxLayout()
        path_layout.setSpacing(8)
        
        self.path_edit = ModernLineEdit("C:\\Program Files\\...")
        browse_btn = QPushButton("Browse...")
        browse_btn.setObjectName("browseButton")
        browse_btn.setMinimumHeight(40)
        browse_btn.setMinimumWidth(80)
        browse_btn.clicked.connect(self.browse_executable)
        
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(browse_btn)
        
        layout.addWidget(path_label)
        layout.addLayout(path_layout)
        
        # Arguments field
        args_label = QLabel("Command Line Arguments")
        args_label.setObjectName("fieldLabel")
        self.args_edit = ModernLineEdit("-auto, --silent (optional)")
        
        layout.addWidget(args_label)
        layout.addWidget(self.args_edit)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setObjectName("separator")
        layout.addWidget(separator)
        
        # Enabled checkbox
        self.enabled_check = ModernCheckBox("Enable this addon on startup")
        self.enabled_check.setChecked(True)
        self.enabled_check.setObjectName("enabledCheck")
        layout.addWidget(self.enabled_check)
        
        return layout

    def create_buttons(self):
        layout = QHBoxLayout()
        layout.setSpacing(12)
        
        # Add spacer to right-align buttons
        spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout.addItem(spacer)
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelButton")
        cancel_btn.setMinimumHeight(40)
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self.reject)
        
        # OK button
        ok_btn = QPushButton("Save")
        ok_btn.setObjectName("okButton")
        ok_btn.setMinimumHeight(40)
        ok_btn.setMinimumWidth(100)
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
        if file_path:
            self.path_edit.setText(file_path)

    def get_data(self):
        return (
            self.name_edit.text().strip(),
            self.path_edit.text().strip(),
            self.args_edit.text().strip(),
            self.enabled_check.isChecked()
        )

    def get_dialog_stylesheet(self):
        return """
        QDialog {
            background-color: #1e1e1e;
            color: #ffffff;
            font-family: 'Segoe UI', sans-serif;
        }
        
        QLabel#dialogTitle {
            font-size: 22px;
            font-weight: bold;
            color: #ffffff;
            margin-bottom: 8px;
        }
        
        QLabel#fieldLabel {
            font-size: 14px;
            font-weight: 500;
            color: #ffffff;
            margin-bottom: 4px;
        }
        
        QLineEdit {
            background-color: #2d2d2d;
            color: white;
            border: 2px solid #404040;
            border-radius: 8px;
            padding: 10px 12px;
            font-size: 14px;
        }
        
        QLineEdit:focus {
            border-color: #0078d4;
            background-color: #323232;
        }
        
        QLineEdit:hover {
            border-color: #505050;
        }
        
        QPushButton#browseButton {
            background-color: #2d2d2d;
            color: white;
            border: 1px solid #404040;
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 14px;
        }
        
        QPushButton#browseButton:hover {
            background-color: #3d3d3d;
            border-color: #505050;
        }
        
        QPushButton#browseButton:pressed {
            background-color: #1d1d1d;
        }
        
        QCheckBox#enabledCheck {
            font-size: 14px;
            color: #ffffff;
            spacing: 8px;
        }
        
        QCheckBox#enabledCheck::indicator {
            width: 18px;
            height: 18px;
        }
        
        QCheckBox#enabledCheck::indicator:unchecked {
            background-color: #2d2d2d;
            border: 2px solid #404040;
            border-radius: 4px;
        }
        
        QCheckBox#enabledCheck::indicator:unchecked:hover {
            border-color: #505050;
        }
        
        QCheckBox#enabledCheck::indicator:checked {
            background-color: #0078d4;
            border: 2px solid #0078d4;
            border-radius: 4px;
            image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xMC41IDFMNCAxLjVMMSAzLjUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+Cjwvc3ZnPgo=);
        }
        
        QCheckBox#enabledCheck::indicator:checked:hover {
            background-color: #106ebe;
            border-color: #106ebe;
        }
        
        QPushButton#okButton {
            background-color: #0078d4;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
            font-size: 14px;
            font-weight: 500;
        }
        
        QPushButton#okButton:hover {
            background-color: #106ebe;
        }
        
        QPushButton#okButton:pressed {
            background-color: #005a9e;
        }
        
        QPushButton#cancelButton {
            background-color: transparent;
            color: #b0b0b0;
            border: 1px solid #404040;
            border-radius: 6px;
            padding: 10px 20px;
            font-size: 14px;
        }
        
        QPushButton#cancelButton:hover {
            background-color: #2d2d2d;
            color: #ffffff;
            border-color: #505050;
        }
        
        QPushButton#cancelButton:pressed {
            background-color: #1d1d1d;
        }
        
        QFrame#separator {
            background-color: #404040;
            max-height: 1px;
            margin: 8px 0px;
        }
        
        QFileDialog {
            background-color: #1e1e1e;
            color: white;
        }
        """