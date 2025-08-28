import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QToolBar, QFileDialog, QMessageBox,
    QTableWidget, QTableWidgetItem, QPushButton, QVBoxLayout, QWidget, QComboBox,
    QAbstractItemView, QInputDialog
)
from PySide6.QtCore import Qt
from exexml import ExeXmlManager
from views.add_edit_dialog import AddEditDialog
import settings


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MSFS exe.xml Manager (2020 + 2024)")

        # Manager backend
        self.manager = ExeXmlManager()
        s = settings.load_settings()
        self.current_version = s.get("version", "MSFS2020")

        # Toolbar
        toolbar = QToolBar("Main")
        self.addToolBar(toolbar)

        # Simulator selection
        self.sim_combo = QComboBox()
        self.sim_combo.addItems(["MSFS2020", "MSFS2024"])
        self.sim_combo.setCurrentText(self.current_version)
        self.sim_combo.currentTextChanged.connect(self.change_version)
        toolbar.addWidget(self.sim_combo)

        load_btn = QPushButton("Load exe.xml")
        load_btn.clicked.connect(self.load_exe)
        toolbar.addWidget(load_btn)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_exe)
        toolbar.addWidget(save_btn)

        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.add_entry)
        toolbar.addWidget(add_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self.remove_entry)
        toolbar.addWidget(remove_btn)

        run_btn = QPushButton("Run")
        run_btn.clicked.connect(self.run_entry)
        toolbar.addWidget(run_btn)

        modify_btn = QPushButton("Modify")
        modify_btn.clicked.connect(self.modify_entry)
        toolbar.addWidget(modify_btn)

        # Preset combo
        self.preset_combo = QComboBox()
        toolbar.addWidget(self.preset_combo)

        load_preset_btn = QPushButton("Load Preset")
        load_preset_btn.clicked.connect(self.load_preset_from_combo)
        toolbar.addWidget(load_preset_btn)

        save_preset_btn = QPushButton("Save Preset")
        save_preset_btn.clicked.connect(self.save_preset)
        toolbar.addWidget(save_preset_btn)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Enabled", "Name", "Path", "Args"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.itemChanged.connect(self.on_item_changed)

        layout = QVBoxLayout()
        layout.addWidget(self.table)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Refresh presets
        self.refresh_presets()

        # Auto load if settings has path
        paths = s.get("paths", {})
        if self.current_version in paths and os.path.exists(paths[self.current_version]):
            self.load_exe(paths[self.current_version])

    # -------------------------
    # Sim Version Handling
    # -------------------------
    def change_version(self, version):
        self.current_version = version
        s = settings.load_settings()
        s["version"] = version
        settings.save_settings(s)
        self.refresh_presets()
        # Auto-load path if available
        paths = s.get("paths", {})
        if version in paths and os.path.exists(paths[version]):
            self.load_exe(paths[version])

    # -------------------------
    # exe.xml Handling
    # -------------------------
    def load_exe(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Select exe.xml", "", "XML Files (*.xml)")
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
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def save_exe(self):
        try:
            self.manager.save()
            QMessageBox.information(self, "Saved", "exe.xml saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    # -------------------------
    # Table Handling
    # -------------------------
    def populate_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.manager.entries))
        for row, entry in enumerate(self.manager.entries):
            enabled_item = QTableWidgetItem()
            enabled_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            enabled_item.setCheckState(Qt.Checked if entry.enabled else Qt.Unchecked)
            self.table.setItem(row, 0, enabled_item)
            self.table.setItem(row, 1, QTableWidgetItem(entry.name))
            self.table.setItem(row, 2, QTableWidgetItem(entry.path))
            self.table.setItem(row, 3, QTableWidgetItem(entry.args))
        self.table.blockSignals(False)

    def on_item_changed(self, item):
        if item.column() == 0:  # Enabled checkbox changed
            row = item.row()
            enabled = item.checkState() == Qt.Checked
            self.manager.set_enabled(row, enabled)
            try:
                self.manager.save()
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

    def remove_entry(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        index = rows[0].row()
        self.manager.remove_entry(index)
        self.populate_table()

    def run_entry(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        index = rows[0].row()
        try:
            self.manager.execute_entry(index)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def modify_entry(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        index = rows[0].row()
        entry = self.manager.entries[index]

        dlg = AddEditDialog(self)
        dlg.name_edit.setText(entry.name)
        dlg.path_edit.setText(entry.path)
        dlg.args_edit.setText(entry.args)
        dlg.enabled_check.setChecked(entry.enabled)

        if dlg.exec():
            name, path, args, enabled = dlg.get_data()
            self.manager.modify_entry(index, name, path, args, enabled)
            self.populate_table()

    # -------------------------
    # Preset Handling
    # -------------------------
    def refresh_presets(self):
        preset_dir = settings.get_preset_dir(self.current_version)
        self.preset_combo.clear()
        for file in os.listdir(preset_dir):
            if file.endswith(".json"):
                self.preset_combo.addItem(file[:-5])

        s = settings.load_settings()
        last = s.get(f"last_preset_{self.current_version}")
        if last:
            self.preset_combo.setCurrentText(last)

    def load_preset_from_combo(self):
        name = self.preset_combo.currentText()
        if not name:
            return
        preset_dir = settings.get_preset_dir(self.current_version)
        path = os.path.join(preset_dir, name + ".json")
        self.manager.load_preset(path)
        self.populate_table()
        s = settings.load_settings()
        s[f"last_preset_{self.current_version}"] = name
        settings.save_settings(s)

    def save_preset(self):
        name, ok = QInputDialog.getText(self, "Save Preset", f"Preset name for {self.current_version}:")
        if not ok or not name.strip():
            return
        preset_dir = settings.get_preset_dir(self.current_version)
        path = os.path.join(preset_dir, name.strip() + ".json")
        self.manager.save_preset(path)
        s = settings.load_settings()
        s[f"last_preset_{self.current_version}"] = name.strip()
        settings.save_settings(s)
        self.refresh_presets()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(900, 600)
    window.show()
    sys.exit(app.exec())
