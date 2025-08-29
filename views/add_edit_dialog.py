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
        self.setStyleSheet(self.get_vs_dark_dialog_stylesheet())
        
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