import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, 
    QTableWidget, QTableWidgetItem, QPushButton, QComboBox, QLabel,
    QFileDialog, QMessageBox, QAbstractItemView, QInputDialog, QFrame,
    QHeaderView, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QIcon, QPalette, QColor
from exexml import ExeXmlManager
from views.add_edit_dialog import AddEditDialog
import settings
from PySide6.QtGui import QIcon


class ModernButton(QPushButton):
    def __init__(self, text, icon_text="", primary=False):
        super().__init__()
        self.setText(f"{icon_text} {text}".strip())
        self.setMinimumHeight(36)
        self.setMinimumWidth(100)
        
        if primary:
            self.setObjectName("primaryButton")
        else:
            self.setObjectName("secondaryButton")


class ModernComboBox(QComboBox):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(36)
        self.setMinimumWidth(120)


class ModernLabel(QLabel):
    def __init__(self, text, subtitle=False):
        super().__init__(text)
        if subtitle:
            self.setObjectName("subtitle")
        else:
            self.setObjectName("title")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MSFS exe.xml Manager")
        self.setMinimumSize(1000, 700)
        self.setWindowIcon(QIcon("icon.ico"))
        
        # Apply modern stylesheet
        self.setStyleSheet(self.get_modern_stylesheet())
        
        # Manager backend
        self.manager = ExeXmlManager()
        s = settings.load_settings()
        self.current_version = s.get("version", "MSFS2020")

        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # Main layout
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Header section
        header_layout = self.create_header()
        layout.addLayout(header_layout)
        
        # Controls section
        controls_layout = self.create_controls()
        layout.addLayout(controls_layout)
        
        # Table section
        self.create_table()
        layout.addWidget(self.table)
        
        # Status section
        status_layout = self.create_status()
        layout.addLayout(status_layout)
        
        # Initialize
        self.refresh_presets()
        
        # Auto load if settings has path
        paths = s.get("paths", {})
        if self.current_version in paths and os.path.exists(paths[self.current_version]):
            self.load_exe(paths[self.current_version])

    def create_header(self):
        layout = QVBoxLayout()
        
        # Title
        title = ModernLabel("MSFS exe.xml Manager")
        title.setObjectName("mainTitle")
        layout.addWidget(title)
        
        # Subtitle with version selector
        subtitle_layout = QHBoxLayout()
        
        subtitle = ModernLabel("Manage your Flight Simulator addons", subtitle=True)
        subtitle_layout.addWidget(subtitle)
        
        subtitle_layout.addStretch()
        
        # Version selector
        version_label = QLabel("Simulator:")
        version_label.setObjectName("fieldLabel")
        subtitle_layout.addWidget(version_label)
        
        self.sim_combo = ModernComboBox()
        self.sim_combo.addItems(["MSFS2020", "MSFS2024"])
        self.sim_combo.setCurrentText(self.current_version)
        self.sim_combo.currentTextChanged.connect(self.change_version)
        subtitle_layout.addWidget(self.sim_combo)
        
        layout.addLayout(subtitle_layout)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setObjectName("separator")
        layout.addWidget(separator)
        
        return layout

    def create_controls(self):
        layout = QVBoxLayout()
        layout.setSpacing(16)
        
        # File operations
        file_layout = QHBoxLayout()
        file_layout.setSpacing(12)
        
        file_label = ModernLabel("File Operations")
        file_label.setObjectName("sectionTitle")
        
        load_btn = ModernButton("Load exe.xml", "📁", primary=True)
        load_btn.clicked.connect(self.load_exe)
        
        save_btn = ModernButton("Save", "💾")
        save_btn.clicked.connect(self.save_exe)
        
        file_layout.addWidget(file_label)
        file_layout.addStretch()
        file_layout.addWidget(load_btn)
        file_layout.addWidget(save_btn)
        
        layout.addLayout(file_layout)
        
        # Entry operations
        entry_layout = QHBoxLayout()
        entry_layout.setSpacing(12)
        
        entry_label = ModernLabel("Entry Operations")
        entry_label.setObjectName("sectionTitle")
        
        add_btn = ModernButton("Add", "➕")
        add_btn.clicked.connect(self.add_entry)
        
        modify_btn = ModernButton("Modify", "✏️")
        modify_btn.clicked.connect(self.modify_entry)
        
        remove_btn = ModernButton("Remove", "🗑️")
        remove_btn.clicked.connect(self.remove_entry)
        
        run_btn = ModernButton("Run", "▶️")
        run_btn.clicked.connect(self.run_entry)
        
        entry_layout.addWidget(entry_label)
        entry_layout.addStretch()
        entry_layout.addWidget(add_btn)
        entry_layout.addWidget(modify_btn)
        entry_layout.addWidget(remove_btn)
        entry_layout.addWidget(run_btn)
        
        layout.addLayout(entry_layout)
        
        # Preset operations
        preset_layout = QHBoxLayout()
        preset_layout.setSpacing(12)
        
        preset_label = ModernLabel("Presets")
        preset_label.setObjectName("sectionTitle")
        
        self.preset_combo = ModernComboBox()
        self.preset_combo.setMinimumWidth(200)
        
        load_preset_btn = ModernButton("Load", "📋")
        load_preset_btn.clicked.connect(self.load_preset_from_combo)
        
        save_preset_btn = ModernButton("Save", "💾")
        save_preset_btn.clicked.connect(self.save_preset)
        
        preset_layout.addWidget(preset_label)
        preset_layout.addWidget(self.preset_combo)
        preset_layout.addStretch()
        preset_layout.addWidget(load_preset_btn)
        preset_layout.addWidget(save_preset_btn)
        
        layout.addLayout(preset_layout)
        
        return layout

    def create_table(self):
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Enabled", "Name", "Path", "Arguments"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.itemChanged.connect(self.on_item_changed)
        
        # Modern table styling
        self.table.setObjectName("modernTable")
        
        # Header styling
        header = self.table.horizontalHeader()
        header.setDefaultSectionSize(200)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        
        # Set column widths
        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(1, 200)
        self.table.setColumnWidth(3, 150)
        
        # Row height
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.verticalHeader().hide()

    def create_status(self):
        layout = QHBoxLayout()
        
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        
        self.entries_count_label = QLabel("0 entries")
        self.entries_count_label.setObjectName("statusLabel")
        
        layout.addWidget(self.status_label)
        layout.addStretch()
        layout.addWidget(self.entries_count_label)
        
        return layout

    def update_status(self, message="Ready"):
        self.status_label.setText(message)
        count = len(self.manager.entries)
        self.entries_count_label.setText(f"{count} {'entry' if count == 1 else 'entries'}")

    # -------------------------
    # Sim Version Handling
    # -------------------------
    def change_version(self, version):
        self.current_version = version
        s = settings.load_settings()
        s["version"] = version
        settings.save_settings(s)
        self.refresh_presets()
        self.update_status(f"Switched to {version}")
        # Auto-load path if available
        paths = s.get("paths", {})
        if version in paths and os.path.exists(paths[version]):
            self.load_exe(paths[version])

    # -------------------------
    # exe.xml Handling
    # -------------------------
    def load_exe(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self, "Select exe.xml", "", "XML Files (*.xml)"
            )
            if not path:
                return
        try:
            self.manager.load(path)
            self.populate_table()
            # Save path in settings
            s = settings.load_settings()
            paths = s.get("paths", {})
            paths[self.current_version] = path
            s["paths"] = paths
            settings.save_settings(s)
            self.update_status(f"Loaded {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            self.update_status("Error loading file")

    def save_exe(self):
        try:
            self.manager.save()
            QMessageBox.information(self, "Success", "exe.xml saved successfully.")
            self.update_status("File saved successfully")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            self.update_status("Error saving file")

    # -------------------------
    # Table Handling
    # -------------------------
    def populate_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.manager.entries))
        
        for row, entry in enumerate(self.manager.entries):
            # Enabled checkbox
            enabled_item = QTableWidgetItem()
            enabled_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            enabled_item.setCheckState(Qt.Checked if entry.enabled else Qt.Unchecked)
            enabled_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, enabled_item)
            
            # Name
            name_item = QTableWidgetItem(entry.name)
            name_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.table.setItem(row, 1, name_item)
            
            # Path
            path_item = QTableWidgetItem(entry.path)
            path_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            path_item.setToolTip(entry.path)
            self.table.setItem(row, 2, path_item)
            
            # Args
            args_item = QTableWidgetItem(entry.args)
            args_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.table.setItem(row, 3, args_item)
        
        self.table.blockSignals(False)
        self.update_status()

    def on_item_changed(self, item):
        if item.column() == 0:  # Enabled checkbox changed
            row = item.row()
            enabled = item.checkState() == Qt.Checked
            self.manager.set_enabled(row, enabled)
            try:
                self.manager.save()
                self.update_status("Auto-saved changes")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    # -------------------------
    # Entry Handling
    # -------------------------
    def add_entry(self):
        dlg = AddEditDialog(self)
        if dlg.exec():
            name, path, args, enabled = dlg.get_data()
            self.manager.add_entry(name, path, args, enabled)
            self.populate_table()
            self.update_status("Entry added")

    def remove_entry(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "No Selection", "Please select an entry to remove.")
            return
        
        index = rows[0].row()
        entry_name = self.manager.entries[index].name
        
        reply = QMessageBox.question(
            self, "Confirm Removal", 
            f"Are you sure you want to remove '{entry_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.manager.remove_entry(index)
            self.populate_table()
            self.update_status("Entry removed")

    def run_entry(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "No Selection", "Please select an entry to run.")
            return
        
        index = rows[0].row()
        try:
            entry_name = self.manager.entries[index].name
            self.manager.execute_entry(index)
            self.update_status(f"Launched {entry_name}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def modify_entry(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "No Selection", "Please select an entry to modify.")
            return
        
        index = rows[0].row()
        entry = self.manager.entries[index]

        dlg = AddEditDialog(self, "Modify Entry")
        dlg.name_edit.setText(entry.name)
        dlg.path_edit.setText(entry.path)
        dlg.args_edit.setText(entry.args)
        dlg.enabled_check.setChecked(entry.enabled)

        if dlg.exec():
            name, path, args, enabled = dlg.get_data()
            self.manager.modify_entry(index, name, path, args, enabled)
            self.populate_table()
            self.update_status("Entry modified")

    # -------------------------
    # Preset Handling
    # -------------------------
    def refresh_presets(self):
        preset_dir = settings.get_preset_dir(self.current_version)
        self.preset_combo.clear()
        
        presets = [f[:-5] for f in os.listdir(preset_dir) if f.endswith(".json")]
        if presets:
            self.preset_combo.addItems(presets)
        else:
            self.preset_combo.addItem("No presets available")

        s = settings.load_settings()
        last = s.get(f"last_preset_{self.current_version}")
        if last and last in presets:
            self.preset_combo.setCurrentText(last)

    def load_preset_from_combo(self):
        name = self.preset_combo.currentText()
        if not name or name == "No presets available":
            return
        
        preset_dir = settings.get_preset_dir(self.current_version)
        path = os.path.join(preset_dir, name + ".json")
        
        try:
            self.manager.load_preset(path)
            self.populate_table()
            s = settings.load_settings()
            s[f"last_preset_{self.current_version}"] = name
            settings.save_settings(s)
            self.update_status(f"Loaded preset: {name}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load preset: {str(e)}")

    def save_preset(self):
        name, ok = QInputDialog.getText(
            self, "Save Preset", 
            f"Enter preset name for {self.current_version}:"
        )
        if not ok or not name.strip():
            return
        
        preset_dir = settings.get_preset_dir(self.current_version)
        path = os.path.join(preset_dir, name.strip() + ".json")
        
        try:
            self.manager.save_preset(path)
            s = settings.load_settings()
            s[f"last_preset_{self.current_version}"] = name.strip()
            settings.save_settings(s)
            self.refresh_presets()
            self.update_status(f"Saved preset: {name.strip()}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save preset: {str(e)}")

    
    def resource_path(relative_path):
        """ Get absolute path to resource, works for dev and PyInstaller """
        if hasattr(sys, "_MEIPASS"):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)

    def get_modern_stylesheet(self):
        return """
        QMainWindow {
            background-color: #1e1e1e;
            color: #ffffff;
            font-family: 'Segoe UI', sans-serif;
        }
        
        QWidget {
            background-color: transparent;
            color: #ffffff;
        }
        
        QLabel#mainTitle {
            font-size: 28px;
            font-weight: bold;
            color: #ffffff;
            margin-bottom: 8px;
        }
        
        QLabel#subtitle {
            font-size: 14px;
            color: #b0b0b0;
            margin-bottom: 16px;
        }
        
        QLabel#sectionTitle {
            font-size: 16px;
            font-weight: 600;
            color: #ffffff;
            margin-right: 20px;
        }
        
        QLabel#fieldLabel {
            font-size: 14px;
            color: #b0b0b0;
            margin-right: 8px;
        }
        
        QLabel#statusLabel {
            font-size: 12px;
            color: #8a8a8a;
            padding: 8px 0px;
        }
        
        QPushButton#primaryButton {
            background-color: #0078d4;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 14px;
            font-weight: 500;
        }
        
        QPushButton#primaryButton:hover {
            background-color: #106ebe;
        }
        
        QPushButton#primaryButton:pressed {
            background-color: #005a9e;
        }
        
        QPushButton#secondaryButton {
            background-color: #2d2d2d;
            color: white;
            border: 1px solid #404040;
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 14px;
        }
        
        QPushButton#secondaryButton:hover {
            background-color: #3d3d3d;
            border-color: #505050;
        }
        
        QPushButton#secondaryButton:pressed {
            background-color: #1d1d1d;
        }
        
        QComboBox {
            background-color: #2d2d2d;
            color: white;
            border: 1px solid #404040;
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 14px;
        }
        
        QComboBox:hover {
            border-color: #505050;
        }
        
        QComboBox::drop-down {
            border: none;
            width: 30px;
        }
        
        QComboBox::down-arrow {
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid #8a8a8a;
        }
        
        QComboBox QAbstractItemView {
            background-color: #2d2d2d;
            color: white;
            border: 1px solid #404040;
            selection-background-color: #0078d4;
            outline: none;
        }
        
        QTableWidget#modernTable {
            background-color: #252525;
            gridline-color: #404040;
            border: 1px solid #404040;
            border-radius: 8px;
        }
        
        QTableWidget#modernTable::item {
            padding: 8px;
            border: none;
        }
        
        QTableWidget#modernTable::item:selected {
            background-color: #0078d4;
            color: white;
        }
        
        QTableWidget#modernTable::item:alternate {
            background-color: #2a2a2a;
        }
        
        QHeaderView::section {
            background-color: #2d2d2d;
            color: white;
            border: none;
            border-right: 1px solid #404040;
            border-bottom: 1px solid #404040;
            padding: 12px 8px;
            font-weight: 600;
            font-size: 13px;
        }
        
        QFrame#separator {
            background-color: #404040;
            max-height: 1px;
            margin: 16px 0px;
        }
        
        QScrollBar:vertical {
            background-color: #2d2d2d;
            width: 12px;
            border-radius: 6px;
        }
        
        QScrollBar::handle:vertical {
            background-color: #505050;
            border-radius: 6px;
            min-height: 20px;
        }
        
        QScrollBar::handle:vertical:hover {
            background-color: #606060;
        }
        
        QMessageBox {
            background-color: #1e1e1e;
            color: white;
        }
        
        QMessageBox QPushButton {
            background-color: #0078d4;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            margin: 4px;
        }
        
        QMessageBox QPushButton:hover {
            background-color: #106ebe;
        }
        """


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("MSFS exe.xml Manager")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("Flight Sim Tools")
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())