import sys
import os
import argparse
import xml.etree.ElementTree as ET
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, 
    QTableWidget, QTableWidgetItem, QPushButton, QComboBox, QLabel,
    QFileDialog, QMessageBox, QAbstractItemView, QInputDialog, QFrame,
    QHeaderView, QSpacerItem, QSizePolicy, QMenu, QMenuBar, QCheckBox,
    QSystemTrayIcon
)
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QFont, QIcon, QPalette, QColor, QAction, QCloseEvent
from exexml import ExeXmlManager
from views.add_edit_dialog import AddEditDialog
from process_monitor import ProcessMonitor
from single_instance import SingleInstanceManager
from system_tray import SystemTrayManager
import settings
from PySide6.QtGui import QIcon


class BackupDialog(QMessageBox):
    def __init__(self, exe_xml_path, sim_version, parent=None):
        super().__init__(parent)
        self.exe_xml_path = exe_xml_path
        self.sim_version = sim_version
        
        self.setWindowTitle("First Time Setup - Backup Required")
        self.setIcon(QMessageBox.Information)
        
        install_type = settings.get_installation_type(exe_xml_path)
        
        self.setText(
            f"🛡️ <b>Safety First!</b><br><br>"
            f"This is the first time you're using this exe.xml file:<br>"
            f"<b>{install_type}</b><br>"
            f"<code>{exe_xml_path}</code><br><br>"
            f"<b>A backup will be created automatically</b> before making any changes.<br>"
            f"This ensures you can always restore your original configuration."
        )
        
        self.setDetailedText(
            f"Backup Details:\n"
            f"• Location: {settings.get_backup_dir(sim_version)}\n"
            f"• Format: exe_xml_backup_{install_type.replace(' ', '_')}_{'{timestamp}'}.xml\n"
            f"• You can view/restore backups from the File menu\n\n"
            f"The backup will be created when you first save changes or add entries."
        )
        
        # Add custom buttons
        self.addButton("Create Backup & Continue", QMessageBox.AcceptRole)
        self.addButton("View Existing Backups", QMessageBox.ActionRole)
        self.addButton("Cancel", QMessageBox.RejectRole)
        
        self.setDefaultButton(self.buttons()[0])


class BackupManagerDialog(QMessageBox):
    def __init__(self, sim_version, parent=None):
        super().__init__(parent)
        self.sim_version = sim_version
        self.setWindowTitle(f"Backup Manager - {sim_version}")
        self.setIcon(QMessageBox.Information)
        
        backups = settings.get_existing_backups(sim_version)
        
        if not backups:
            self.setText("No backups found for this simulator version.")
            self.setStandardButtons(QMessageBox.Ok)
        else:
            text = f"<b>Found {len(backups)} backup(s) for {sim_version}:</b><br><br>"
            
            from datetime import datetime
            for i, (filename, full_path, creation_time) in enumerate(backups[:10], 1):  # Show max 10
                dt = datetime.fromtimestamp(creation_time)
                # Extract install type from filename
                parts = filename.replace("exe_xml_backup_", "").replace(".xml", "").split("_")
                install_type = " ".join(parts[:-2]) if len(parts) > 2 else "Unknown"
                
                text += f"{i}. <b>{install_type}</b><br>"
                text += f"   Created: {dt.strftime('%Y-%m-%d %H:%M:%S')}<br>"
                text += f"   File: {filename}<br><br>"
            
            if len(backups) > 10:
                text += f"... and {len(backups) - 10} more backups"
            
            self.setText(text)
            
            # Add buttons for backup actions
            self.addButton("Open Backup Folder", QMessageBox.ActionRole)
            self.addButton("Close", QMessageBox.RejectRole)
            
            self.backup_folder = settings.get_backup_dir(sim_version)


class DetectedPathDialog(QMessageBox):
    def __init__(self, detected_paths, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Auto-detected exe.xml Files")
        self.setIcon(QMessageBox.Question)
        
        if len(detected_paths) == 1:
            description, path = detected_paths[0]
            installation_type = settings.get_installation_type(path)
            self.setText(f"Found exe.xml file:\n\n{description} ({installation_type})\n{path}\n\nWould you like to load this file?")
            self.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            self.setDefaultButton(QMessageBox.Yes)
        else:
            text = f"Found {len(detected_paths)} exe.xml files:\n\n"
            for i, (description, path) in enumerate(detected_paths, 1):
                installation_type = settings.get_installation_type(path)
                text += f"{i}. {description} ({installation_type})\n   {path}\n\n"
            
            text += "Which one would you like to load?"
            self.setText(text)
            
            # Add custom buttons for each detected path
            for i, (description, path) in enumerate(detected_paths):
                installation_type = settings.get_installation_type(path)
                button_text = f"{description} ({installation_type})"
                button = self.addButton(button_text, QMessageBox.AcceptRole)
                button.setProperty("path", path)
            
            self.addButton("Browse...", QMessageBox.RejectRole)
            self.addButton("Cancel", QMessageBox.RejectRole)


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
    def __init__(self, start_hidden=False):
        super().__init__()
        self.start_hidden = start_hidden
        self.setWindowTitle("MSFS exe.xml Manager")
        self.setMinimumSize(1000, 700)
        self.setWindowIcon(QIcon("icon.ico"))
        
        # Apply Visual Studio dark theme
        self.setStyleSheet(self.get_vs_dark_stylesheet())
        
        # Manager backend
        self.manager = ExeXmlManager()
        s = settings.load_settings()
        self.current_version = s.get("version", "MSFS2020")
        
        # Process monitoring
        self.process_monitor = ProcessMonitor()
        self.process_monitor.sim_stopped.connect(self.on_simulator_stopped)
        self.process_monitor.addon_started.connect(self.on_addon_started)
        self.process_monitor.addon_stopped.connect(self.on_addon_stopped)
        self.running_addons = {}  # addon_name -> process info
        
        # System tray
        self.tray_manager = SystemTrayManager(self)
        self.tray_manager.show_window_requested.connect(self.show_from_tray)
        self.tray_manager.exit_requested.connect(self.exit_application)
        
        # Track if we're really exiting (not just hiding to tray)
        self.really_exit = False
        
        # Setup UI
        self.setup_ui()
        
        # Initialize
        self.refresh_presets()
        
        # Auto load with detection
        self.auto_load_exe()
        
        # Start process monitoring
        self.process_monitor.start_monitoring(self.current_version)
        
        # Setup system tray if starting hidden or if tray is available
        if start_hidden or QSystemTrayIcon.isSystemTrayAvailable():
            self.setup_tray()
        
        # Show window if not starting hidden
        if not start_hidden:
            self.show()
        elif self.tray_manager.is_visible():
            print("Started in background mode - running in system tray")
            self.tray_manager.show_message(
                "MSFS exe.xml Manager", 
                "Application started in background mode",
                QSystemTrayIcon.Information
            )
    
    def setup_ui(self):
        """Setup the main UI components"""
        # Create menu bar
        self.create_menu_bar()

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
    
    def setup_tray(self):
        """Setup system tray functionality"""
        if self.tray_manager.setup_tray():
            print("System tray initialized")
        else:
            print("Failed to initialize system tray")
            if self.start_hidden:
                # If we can't use tray and started hidden, show the window
                self.show()
    
    def show_from_tray(self):
        """Show window from system tray"""
        self.show()
        self.raise_()
        self.activateWindow()
        print("Window shown from system tray")
    
    def exit_application(self):
        """Exit the application completely"""
        self.really_exit = True
        self.close()

    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        # Background mode toggle
        if QSystemTrayIcon.isSystemTrayAvailable():
            background_action = QAction('Run in Background', self)
            background_action.setCheckable(True)
            background_action.setChecked(self.start_hidden)
            background_action.triggered.connect(self.toggle_background_mode)
            file_menu.addAction(background_action)
            file_menu.addSeparator()
        
        # Backup submenu
        backup_menu = file_menu.addMenu('Backups')
        
        view_backups_action = QAction('View Backups...', self)
        view_backups_action.triggered.connect(self.show_backup_manager)
        backup_menu.addAction(view_backups_action)
        
        open_backup_folder_action = QAction('Open Backup Folder', self)
        open_backup_folder_action.triggered.connect(self.open_backup_folder)
        backup_menu.addAction(open_backup_folder_action)
        
        backup_menu.addSeparator()
        
        create_manual_backup_action = QAction('Create Manual Backup', self)
        create_manual_backup_action.triggered.connect(self.create_manual_backup)
        backup_menu.addAction(create_manual_backup_action)
        
        file_menu.addSeparator()
        
        # Settings
        settings_action = QAction('Settings...', self)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        # Exit
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.exit_application)
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menubar.addMenu('Help')
        
        about_action = QAction('About...', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def toggle_background_mode(self):
        """Toggle background mode"""
        # This is just a placeholder - in a real implementation you might
        # save this preference and use it on next startup
        pass

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
        
        # Auto-detect button
        auto_detect_btn = ModernButton("Auto-detect", "🔍")
        auto_detect_btn.clicked.connect(self.auto_detect_exe)
        auto_detect_btn.setToolTip("Automatically detect exe.xml files for the current simulator version")
        subtitle_layout.addWidget(auto_detect_btn)
        
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
        
        load_btn = ModernButton("Load exe.xml", "📂", primary=True)
        load_btn.clicked.connect(self.load_exe)
        
        save_btn = ModernButton("Apply", "✅")
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
        self.table.setColumnCount(5)  # Added Auto-Close column
        self.table.setHorizontalHeaderLabels(["Enabled", "Name", "Path", "Arguments", "Auto-Close"])
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
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        
        # Set column widths
        self.table.setColumnWidth(0, 80)   # Enabled
        self.table.setColumnWidth(1, 200)  # Name
        self.table.setColumnWidth(3, 150)  # Arguments
        self.table.setColumnWidth(4, 90)   # Auto-Close
        
        # Row height
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.verticalHeader().hide()

    def create_status(self):
        layout = QHBoxLayout()
        
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        
        self.entries_count_label = QLabel("0 entries")
        self.entries_count_label.setObjectName("statusLabel")
        
        # Installation type label
        self.install_type_label = QLabel("")
        self.install_type_label.setObjectName("statusLabel")
        
        layout.addWidget(self.status_label)
        layout.addStretch()
        layout.addWidget(self.install_type_label)
        layout.addWidget(self.entries_count_label)
        
        return layout

    def update_status(self, message="Ready"):
        self.status_label.setText(message)
        count = len(self.manager.entries)
        self.entries_count_label.setText(f"{count} {'entry' if count == 1 else 'entries'}")
        
        # Update installation type if file is loaded
        if self.manager.filepath:
            install_type = settings.get_installation_type(self.manager.filepath)
            # Show both the install type and the actual path for debugging
            self.install_type_label.setText(f"• {install_type} | Path: {self.manager.filepath}")
        else:
            self.install_type_label.setText("")

    # Override closeEvent to handle minimize to tray
    def closeEvent(self, event: QCloseEvent):
        if not self.really_exit and self.tray_manager.is_visible():
            # Hide to tray instead of closing
            event.ignore()
            self.hide()
            if not self.start_hidden:  # Only show message if user manually closed
                self.tray_manager.show_message(
                    "MSFS exe.xml Manager",
                    "Application minimized to tray. Double-click the tray icon to restore.",
                    QSystemTrayIcon.Information
                )
        else:
            # Really exiting
            self.process_monitor.stop_monitoring()
            self.tray_manager.hide()
            event.accept()

    def auto_load_exe(self):
        """Try to auto-load exe.xml on startup"""
        s = settings.load_settings()
        paths = s.get("paths", {})
        
        # First, try saved path
        if self.current_version in paths and os.path.exists(paths[self.current_version]):
            self.load_exe(paths[self.current_version])
            return
        
        # If no saved path, try auto-detection
        auto_path = settings.auto_detect_exe_xml(self.current_version)
        if auto_path:
            try:
                self.load_exe(auto_path)
                self.update_status(f"Auto-loaded {os.path.basename(auto_path)}")
            except Exception as e:
                self.update_status(f"Auto-detection found file but failed to load: {str(e)}")

    def auto_detect_exe(self):
        """Manual auto-detection triggered by button"""
        detected_paths = settings.get_all_detected_paths(self.current_version)
        
        if not detected_paths:
            QMessageBox.information(
                self, 
                "Auto-detection", 
                f"No exe.xml files were automatically detected for {self.current_version}.\n\n"
                "Please use 'Load exe.xml' to browse manually.\n\n"
                "Expected locations:\n"
                "• Steam: %APPDATA%\\Microsoft Flight Simulator\\exe.xml\n"
                "• MS Store: %LOCALAPPDATA%\\Packages\\Microsoft.FlightSimulator_8wekyb3d8bbwe\\LocalState\\exe.xml"
            )
            return
        
        if len(detected_paths) == 1:
            # Single path found, ask to load it
            description, path = detected_paths[0]
            installation_type = settings.get_installation_type(path)
            reply = QMessageBox.question(
                self,
                "Auto-detection",
                f"Found exe.xml file:\n\n{description} ({installation_type})\n{path}\n\nWould you like to load this file?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                try:
                    self.load_exe(path)
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to load exe.xml: {str(e)}")
        else:
            # Multiple paths found, show selection dialog
            dialog = DetectedPathDialog(detected_paths, self)
            result = dialog.exec()
            
            if result == QMessageBox.Accepted:
                # Find which button was clicked
                clicked_button = dialog.clickedButton()
                if clicked_button and hasattr(clicked_button, 'property') and clicked_button.property("path"):
                    path = clicked_button.property("path")
                    try:
                        self.load_exe(path)
                    except Exception as e:
                        QMessageBox.critical(self, "Error", f"Failed to load exe.xml: {str(e)}")
                elif clicked_button and clicked_button.text() == "Browse...":
                    self.load_exe()  # Trigger manual browse

    # -------------------------
    # Backup Management
    # -------------------------
    def check_and_create_backup(self, exe_xml_path):
        """Check if backup is needed and create it"""
        backup_created, backup_path, error = settings.auto_backup_if_needed(exe_xml_path, self.current_version)
        
        if backup_created:
            QMessageBox.information(
                self,
                "Backup Created",
                f"✅ <b>Backup created successfully!</b><br><br>"
                f"Your original exe.xml has been backed up to:<br>"
                f"<code>{backup_path}</code><br><br>"
                f"You can now safely make changes to your configuration."
            )
            return True
        elif error and "already backed up" not in error:
            reply = QMessageBox.warning(
                self,
                "Backup Failed",
                f"⚠️ <b>Warning: Backup creation failed</b><br><br>"
                f"Error: {error}<br><br>"
                f"Do you want to continue without a backup?<br>"
                f"<b>This is not recommended.</b>",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            return reply == QMessageBox.Yes
        
        return True  # No backup needed (already exists) or user chose to continue

    def show_first_time_backup_dialog(self, exe_xml_path):
        """Show the first-time backup dialog"""
        dialog = BackupDialog(exe_xml_path, self.current_version, self)
        result = dialog.exec()
        
        clicked_button = dialog.clickedButton()
        button_text = clicked_button.text() if clicked_button else ""
        
        if "Create Backup" in button_text:
            return self.check_and_create_backup(exe_xml_path)
        elif "View Existing" in button_text:
            self.show_backup_manager()
            return False  # Don't continue loading
        else:
            return False  # Cancel

    def show_backup_manager(self):
        """Show the backup manager dialog"""
        dialog = BackupManagerDialog(self.current_version, self)
        result = dialog.exec()
        
        if hasattr(dialog, 'backup_folder'):
            clicked_button = dialog.clickedButton()
            if clicked_button and "Open Backup Folder" in clicked_button.text():
                self.open_backup_folder()

    def open_backup_folder(self):
        """Open the backup folder in file explorer"""
        backup_dir = settings.get_backup_dir(self.current_version)
        
        try:
            import subprocess
            import platform
            
            if platform.system() == "Windows":
                subprocess.run(["explorer", backup_dir])
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", backup_dir])
            else:  # Linux
                subprocess.run(["xdg-open", backup_dir])
                
        except Exception as e:
            QMessageBox.information(
                self,
                "Backup Folder",
                f"Backup folder location:\n{backup_dir}\n\n"
                f"(Could not open automatically: {str(e)})"
            )

    def create_manual_backup(self):
        """Create a manual backup of the current exe.xml file"""
        if not self.manager.filepath:
            QMessageBox.information(self, "No File Loaded", "Please load an exe.xml file first.")
            return
        
        backup_path = settings.create_backup(self.manager.filepath, self.current_version)
        
        if backup_path:
            QMessageBox.information(
                self,
                "Manual Backup Created",
                f"✅ Manual backup created successfully!\n\n"
                f"Backup saved to:\n{backup_path}"
            )
        else:
            QMessageBox.critical(
                self,
                "Backup Failed",
                "Failed to create manual backup. Please check file permissions."
            )

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About MSFS exe.xml Manager",
            f"<h3>MSFS exe.xml Manager v1.0.0-rc1</h3>"
            f"<p>A modern tool for managing Microsoft Flight Simulator addons.</p>"
            f"<p><b>Features:</b></p>"
            f"<ul>"
            f"<li>Auto-detection for Steam and MS Store versions</li>"
            f"<li>Automatic backups for safety</li>"
            f"<li>Auto-close addons when simulator stops</li>"
            f"<li>Background operation with system tray</li>"
            f"<li>Preset management</li>"
            f"<li>Support for MSFS2020 and MSFS2024</li>"
            f"</ul>"
            f"<p>Your original exe.xml files are automatically backed up before any changes.</p>"
        )

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
        
        # Update process monitoring for new version
        self.process_monitor.stop_monitoring()
        self.running_addons.clear()
        
        # Clear current data
        self.manager = ExeXmlManager()
        self.populate_table()
        
        # Try auto-load for new version
        self.auto_load_exe()
        
        # Restart monitoring for new version
        self.process_monitor.start_monitoring(version)

    # -------------------------
    # exe.xml Handling
    # -------------------------
    def load_exe(self, path=None):
        if not path:
            # Get last used directory for file dialog
            s = settings.load_settings()
            paths = s.get("paths", {})
            start_dir = ""
            
            if self.current_version in paths and os.path.exists(os.path.dirname(paths[self.current_version])):
                start_dir = os.path.dirname(paths[self.current_version])
            else:
                # Use default MSFS directory based on version
                if self.current_version == "MSFS2020":
                    start_dir = os.path.expandvars(r"%APPDATA%\Microsoft Flight Simulator")
                elif self.current_version == "MSFS2024":
                    start_dir = os.path.expandvars(r"%APPDATA%\Microsoft Flight Simulator 2024")
                
                # Fallback to user's home directory if default doesn't exist
                if not os.path.exists(start_dir):
                    start_dir = os.path.expanduser("~")
            
            path, _ = QFileDialog.getOpenFileName(
                self, "Select exe.xml", start_dir, "XML Files (*.xml)"
            )
            if not path:
                return
        
        try:
            # Check if backup is needed for first-time use
            if settings.is_first_time_using_file(path, self.current_version):
                if not self.show_first_time_backup_dialog(path):
                    return  # User cancelled or backup failed
            
            self.manager.load(path)
            self.populate_table()
            
            # Save path in settings
            s = settings.load_settings()
            paths = s.get("paths", {})
            paths[self.current_version] = path
            s["paths"] = paths
            settings.save_settings(s)
            
            # Update process monitoring for auto-close entries
            self.update_process_monitoring()
            
            # Determine installation type and update status
            install_type = settings.get_installation_type(path)
            self.update_status(f"Loaded {os.path.basename(path)} ({install_type})")
            
            # Show tray notification if running in background
            if self.tray_manager.is_visible() and self.isHidden():
                self.tray_manager.show_message(
                    "File Loaded",
                    f"Loaded {os.path.basename(path)} ({install_type})",
                    QSystemTrayIcon.Information
                )
            
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            self.update_status("Error loading file")

    def save_exe(self):
        if not self.manager.filepath:
            QMessageBox.information(self, "No File Loaded", "Please load an exe.xml file first.")
            return
            
        try:
            # Create backup before saving if this is the first save
            if settings.is_first_time_using_file(self.manager.filepath, self.current_version):
                backup_created, backup_path, error = settings.auto_backup_if_needed(self.manager.filepath, self.current_version)
                if backup_created:
                    self.update_status(f"Backup created: {os.path.basename(backup_path)}")
            
            self.manager.save()
            QMessageBox.information(self, "Success", "exe.xml saved successfully.")
            self.update_status("File saved successfully")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            self.update_status("Error saving file")

    def update_process_monitoring(self):
        """Update process monitoring for all auto-close entries"""
        print("\n=== Updating Process Monitoring ===")
        
        # Clear current monitoring
        for addon_name in list(self.running_addons.keys()):
            self.process_monitor.remove_addon_from_monitor(addon_name)
        self.running_addons.clear()
        
        # Add all auto-close entries to monitoring
        for entry in self.manager.entries:
            if entry.auto_close and entry.enabled and os.path.exists(entry.path):
                self.process_monitor.add_addon_to_monitor(entry.name, entry.path)
                self.running_addons[entry.name] = {
                    'process': None,
                    'path': entry.path,
                    'auto_close': True
                }
                print(f"Added to monitoring: {entry.name} -> {entry.path}")
            elif entry.auto_close and entry.enabled:
                print(f"WARNING: Auto-close entry path does not exist: {entry.name} -> {entry.path}")
            elif entry.auto_close and not entry.enabled:
                print(f"Skipping disabled auto-close entry: {entry.name}")
        
        print("=== Process Monitoring Updated ===\n")

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
            
            # Auto-Close checkbox
            auto_close_item = QTableWidgetItem()
            auto_close_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            auto_close_item.setCheckState(Qt.Checked if entry.auto_close else Qt.Unchecked)
            auto_close_item.setTextAlignment(Qt.AlignCenter)
            auto_close_item.setToolTip("Automatically close this addon when the simulator stops")
            self.table.setItem(row, 4, auto_close_item)
        
        self.table.blockSignals(False)
        self.update_status()

    def on_item_changed(self, item):
        row = item.row()
        
        if item.column() == 0:  # Enabled checkbox changed
            enabled = item.checkState() == Qt.Checked
            
            # Create backup before first modification if needed
            if settings.is_first_time_using_file(self.manager.filepath, self.current_version):
                backup_created, backup_path, error = settings.auto_backup_if_needed(self.manager.filepath, self.current_version)
                if backup_created:
                    self.update_status(f"Backup created: {os.path.basename(backup_path)}")
            
            self.manager.set_enabled(row, enabled)
            
        elif item.column() == 4:  # Auto-Close checkbox changed
            auto_close = item.checkState() == Qt.Checked
            
            # Update auto-close setting (stored separately, not in XML)
            self.manager.set_auto_close(row, auto_close)
            
            # Update process monitoring
            entry = self.manager.entries[row]
            if auto_close and os.path.exists(entry.path):
                self.process_monitor.add_addon_to_monitor(entry.name, entry.path)
                print(f"Added {entry.name} to auto-close monitoring")
            elif not auto_close:
                self.process_monitor.remove_addon_from_monitor(entry.name)
                if entry.name in self.running_addons:
                    del self.running_addons[entry.name]
                print(f"Removed {entry.name} from auto-close monitoring")
        
        try:
            self.manager.save()
            self.update_status("Auto-saved changes")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    # -------------------------
    # Entry Handling
    # -------------------------
    def add_entry(self):
        if not self.manager.filepath:
            QMessageBox.information(self, "No File Loaded", "Please load an exe.xml file first.")
            return
            
        dlg = AddEditDialog(self)
        if dlg.exec():
            # Create backup before first modification if needed
            if settings.is_first_time_using_file(self.manager.filepath, self.current_version):
                backup_created, backup_path, error = settings.auto_backup_if_needed(self.manager.filepath, self.current_version)
                if backup_created:
                    self.update_status(f"Backup created: {os.path.basename(backup_path)}")
            
            name, path, args, enabled, auto_close = dlg.get_data()
            self.manager.add_entry(name, path, args, enabled, auto_close)
            self.populate_table()
            
            # Add to process monitoring if auto-close is enabled
            if auto_close and os.path.exists(path):
                self.process_monitor.add_addon_to_monitor(name, path)
                print(f"Added new entry {name} to auto-close monitoring")
            
            self.update_status("Entry added")

    def remove_entry(self):
        if not self.manager.filepath:
            QMessageBox.information(self, "No File Loaded", "Please load an exe.xml file first.")
            return
            
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
            # Create backup before first modification if needed
            if settings.is_first_time_using_file(self.manager.filepath, self.current_version):
                backup_created, backup_path, error = settings.auto_backup_if_needed(self.manager.filepath, self.current_version)
                if backup_created:
                    self.update_status(f"Backup created: {os.path.basename(backup_path)}")
            
            # Remove from process monitoring if it was being tracked
            entry = self.manager.entries[index]
            if entry.name in self.running_addons:
                self.process_monitor.remove_addon_from_monitor(entry.name)
                del self.running_addons[entry.name]
                print(f"Removed {entry.name} from monitoring")
            
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
            entry = self.manager.entries[index]
            print(f"\n=== Running Entry ===")
            print(f"Name: {entry.name}")
            print(f"Path: {entry.path}")
            print(f"Args: {entry.args}")
            print(f"Auto-close: {entry.auto_close}")
            
            process = self.manager.execute_entry(index)
            
            if process:
                print(f"Process started with PID: {process.pid}")
                
                if entry.auto_close:
                    # Track this process for auto-closing
                    self.process_monitor.add_addon_to_monitor(entry.name, entry.path)
                    self.running_addons[entry.name] = {
                        'process': process,
                        'path': entry.path,
                        'auto_close': True
                    }
                    print(f"Added to auto-close monitoring: {entry.name} (PID: {process.pid})")
                
                self.update_status(f"Launched {entry.name}")
                
                # Show tray notification if running in background
                if self.tray_manager.is_visible() and self.isHidden():
                    self.tray_manager.show_message(
                        "Addon Launched",
                        f"Started {entry.name}",
                        QSystemTrayIcon.Information
                    )
            else:
                print("Failed to start process")
                self.update_status(f"Failed to launch {entry.name}")
                
            print("=== End Running Entry ===\n")
            
        except Exception as e:
            print(f"Error running entry: {e}")
            QMessageBox.critical(self, "Error", str(e))

    def modify_entry(self):
        if not self.manager.filepath:
            QMessageBox.information(self, "No File Loaded", "Please load an exe.xml file first.")
            return
            
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
        dlg.auto_close_check.setChecked(entry.auto_close)

        if dlg.exec():
            # Create backup before first modification if needed
            if settings.is_first_time_using_file(self.manager.filepath, self.current_version):
                backup_created, backup_path, error = settings.auto_backup_if_needed(self.manager.filepath, self.current_version)
                if backup_created:
                    self.update_status(f"Backup created: {os.path.basename(backup_path)}")
            
            # Remove old monitoring
            old_name = entry.name
            if old_name in self.running_addons:
                self.process_monitor.remove_addon_from_monitor(old_name)
                del self.running_addons[old_name]
            
            name, path, args, enabled, auto_close = dlg.get_data()
            self.manager.modify_entry(index, name, path, args, enabled, auto_close)
            
            # Add new monitoring if auto-close is enabled
            if auto_close and os.path.exists(path):
                self.process_monitor.add_addon_to_monitor(name, path)
                print(f"Updated monitoring for {name}")
            
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
            
            # Update process monitoring after loading preset
            self.update_process_monitoring()
            
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

    # -------------------------
    # Process Monitoring Handlers
    # -------------------------
    def on_simulator_stopped(self, sim_name):
        """Called when the simulator process stops"""
        print(f"\n=== Simulator Stopped Event ===")
        print(f"Simulator: {sim_name}")
        
        # Debug current state
        self.process_monitor.debug_status()
        
        # Find all entries that should be auto-closed
        auto_close_entries = []
        for entry in self.manager.entries:
            if entry.auto_close and entry.enabled:
                auto_close_entries.append(entry)
                print(f"Auto-close entry found: {entry.name} -> {entry.path}")
        
        if not auto_close_entries:
            print("No auto-close entries found")
            self.update_status(f"Simulator stopped ({sim_name}) - No auto-close addons")
            return
        
        # Terminate all addon processes that should auto-close
        total_terminated = 0
        
        for entry in auto_close_entries:
            addon_name = entry.name
            process_count = self.process_monitor.get_addon_process_count(addon_name)
            print(f"Checking {addon_name}: {process_count} running processes")
            
            if process_count > 0:
                try:
                    terminated = self.process_monitor.terminate_addon_processes(addon_name)
                    total_terminated += terminated
                    print(f"Terminated {terminated} process(es) for {addon_name}")
                except Exception as e:
                    print(f"Error terminating {addon_name}: {e}")
        
        # Also try to terminate any other running addon processes
        additional_terminated = self.process_monitor.terminate_all_addon_processes()
        if additional_terminated > total_terminated:
            print(f"Terminated {additional_terminated - total_terminated} additional processes")
            total_terminated = additional_terminated
        
        # Update status
        if total_terminated > 0:
            status_message = f"Simulator stopped - Auto-closed {total_terminated} addon(s)"
            print(f"SUCCESS: {status_message}")
        else:
            status_message = f"Simulator stopped ({sim_name}) - No addons to close"
            print(f"NO ACTION: {status_message}")
        
        self.update_status(status_message)
        
        # Show tray notification if running in background
        if self.tray_manager.is_visible():
            if total_terminated > 0:
                self.tray_manager.show_message(
                    "Auto-Close Complete",
                    f"Closed {total_terminated} addon(s) when {sim_name} stopped",
                    QSystemTrayIcon.Information
                )
            else:
                self.tray_manager.show_message(
                    "Simulator Stopped",
                    f"{sim_name} stopped (no addons to close)",
                    QSystemTrayIcon.Information
                )
        
        print("=== End Simulator Stopped Event ===\n")
    
    def on_addon_started(self, addon_name, pid):
        """Called when an addon process starts"""
        print(f"Addon process started: {addon_name} (PID: {pid})")
        # Update our tracking
        if addon_name not in self.running_addons:
            # Find the entry to get the path
            for entry in self.manager.entries:
                if entry.name == addon_name:
                    self.running_addons[addon_name] = {
                        'process': None,  # We don't have the Process object
                        'path': entry.path,
                        'auto_close': entry.auto_close
                    }
                    break

    def on_addon_stopped(self, addon_name, pid):
        """Called when an addon process stops"""
        print(f"Addon process stopped: {addon_name} (PID: {pid})")

    def debug_auto_close_status(self):
        """Debug method to check auto-close status"""
        print("\n=== Debug Auto-Close Status ===")
        print(f"Process monitor active: {self.process_monitor.monitoring}")
        print(f"Simulator running: {self.process_monitor.is_simulator_running()}")
        
        print("Auto-close entries:")
        for i, entry in enumerate(self.manager.entries):
            if entry.auto_close:
                exists = os.path.exists(entry.path)
                process_count = self.process_monitor.get_addon_process_count(entry.name)
                print(f"  {i}: {entry.name}")
                print(f"      Path: {entry.path}")
                print(f"      Enabled: {entry.enabled}")
                print(f"      Path exists: {exists}")
                print(f"      Running processes: {process_count}")
        
        print("Tracked addons:")
        for name, info in self.running_addons.items():
            print(f"  {name}: {info}")
        
        self.process_monitor.debug_status()
        print("=== End Debug ===\n")

    def get_vs_dark_stylesheet(self):
        """Visual Studio Dark theme colors"""
        return """
        QMainWindow {
            background-color: #1e1e1e;
            color: #cccccc;
            font-family: 'Segoe UI', Consolas, 'Courier New', monospace;
        }
        
        QWidget {
            background-color: transparent;
            color: #cccccc;
        }
        
        QMenuBar {
            background-color: #2d2d30;
            color: #cccccc;
            border-bottom: 1px solid #3e3e42;
            padding: 2px;
        }
        
        QMenuBar::item {
            background-color: transparent;
            padding: 4px 8px;
        }
        
        QMenuBar::item:selected {
            background-color: #3e3e40;
        }
        
        QMenu {
            background-color: #1b1b1c;
            color: #cccccc;
            border: 1px solid #3e3e42;
        }
        
        QMenu::item {
            padding: 6px 20px;
            border-bottom: 1px solid #2d2d30;
        }
        
        QMenu::item:selected {
            background-color: #094771;
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
            color: #9cdcfe;
            margin-bottom: 16px;
        }
        
        QLabel#sectionTitle {
            font-size: 16px;
            font-weight: 600;
            color: #dcdcaa;
            margin-right: 20px;
        }
        
        QLabel#fieldLabel {
            font-size: 14px;
            color: #9cdcfe;
            margin-right: 8px;
        }
        
        QLabel#statusLabel {
            font-size: 12px;
            color: #808080;
            padding: 8px 0px;
        }
        
        QPushButton#primaryButton {
            background-color: #0e639c;
            color: #ffffff;
            border: 1px solid #1177bb;
            border-radius: 4px;
            padding: 8px 16px;
            font-size: 14px;
            font-weight: 500;
        }
        
        QPushButton#primaryButton:hover {
            background-color: #1177bb;
            border-color: #1e88cc;
        }
        
        QPushButton#primaryButton:pressed {
            background-color: #0d5a87;
        }
        
        QPushButton#secondaryButton {
            background-color: #3c3c3c;
            color: #cccccc;
            border: 1px solid #555555;
            border-radius: 4px;
            padding: 8px 16px;
            font-size: 14px;
        }
        
        QPushButton#secondaryButton:hover {
            background-color: #464647;
            border-color: #6e6e6e;
        }
        
        QPushButton#secondaryButton:pressed {
            background-color: #2a2a2a;
        }
        
        QComboBox {
            background-color: #3c3c3c;
            color: #cccccc;
            border: 1px solid #555555;
            border-radius: 4px;
            padding: 6px 12px;
            font-size: 14px;
            min-height: 20px;
        }
        
        QComboBox:hover {
            border-color: #0e639c;
        }
        
        QComboBox:focus {
            border-color: #007acc;
        }
        
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border-left: 1px solid #555555;
        }
        
        QComboBox::down-arrow {
            width: 12px;
            height: 12px;
            background-color: #cccccc;
        }
        
        QComboBox QAbstractItemView {
            background-color: #1e1e1e;
            color: #cccccc;
            border: 1px solid #555555;
            selection-background-color: #094771;
            selection-color: #ffffff;
            outline: none;
        }
        
        QComboBox QAbstractItemView::item {
            padding: 6px;
            border: none;
        }
        
        QComboBox QAbstractItemView::item:hover {
            background-color: #2a2d2e;
        }
        
        QTableWidget#modernTable {
            background-color: #252526;
            gridline-color: #3e3e42;
            border: 1px solid #3e3e42;
            alternate-background-color: #2a2a2b;
            selection-background-color: #094771;
            selection-color: #ffffff;
        }
        
        QTableWidget#modernTable::item {
            padding: 8px;
            border: none;
            color: #cccccc;
        }
        
        QTableWidget#modernTable::item:selected {
            background-color: #094771;
            color: #ffffff;
        }
        
        QTableWidget#modernTable::item:alternate {
            background-color: #2a2a2b;
        }
        
        QHeaderView::section {
            background-color: #2d2d30;
            color: #cccccc;
            border: none;
            border-right: 1px solid #3e3e42;
            border-bottom: 1px solid #3e3e42;
            padding: 10px 8px;
            font-weight: 600;
            font-size: 13px;
        }
        
        QHeaderView::section:hover {
            background-color: #3e3e40;
        }
        
        QFrame#separator {
            background-color: #3e3e42;
            max-height: 1px;
            margin: 16px 0px;
        }
        
        QScrollBar:vertical {
            background-color: #2b2b2c;
            width: 14px;
            border: none;
        }
        
        QScrollBar::handle:vertical {
            background-color: #555556;
            border: none;
            min-height: 20px;
        }
        
        QScrollBar::handle:vertical:hover {
            background-color: #686868;
        }
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        
        QScrollBar:horizontal {
            background-color: #2b2b2c;
            height: 14px;
            border: none;
        }
        
        QScrollBar::handle:horizontal {
            background-color: #555556;
            border: none;
            min-width: 20px;
        }
        
        QScrollBar::handle:horizontal:hover {
            background-color: #686868;
        }
        
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0px;
        }
        
        QMessageBox {
            background-color: #2d2d30;
            color: #cccccc;
        }
        
        QMessageBox QPushButton {
            background-color: #0e639c;
            color: #ffffff;
            border: 1px solid #1177bb;
            border-radius: 4px;
            padding: 6px 16px;
            margin: 4px;
            min-width: 75px;
        }
        
        QMessageBox QPushButton:hover {
            background-color: #1177bb;
        }
        
        QMessageBox QPushButton:pressed {
            background-color: #0d5a87;
        }
        
        QDialog {
            background-color: #2d2d30;
            color: #cccccc;
        }
        
        QLineEdit {
            background-color: #3c3c3c;
            color: #cccccc;
            border: 1px solid #555555;
            border-radius: 4px;
            padding: 6px 8px;
            font-size: 14px;
        }
        
        QLineEdit:focus {
            border-color: #007acc;
            background-color: #404040;
        }
        
        QLineEdit:hover {
            border-color: #6e6e6e;
        }
        
        QCheckBox {
            color: #cccccc;
            font-size: 14px;
        }
        
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
        }
        
        QCheckBox::indicator:unchecked {
            background-color: #3c3c3c;
            border: 1px solid #555555;
        }
        
        QCheckBox::indicator:unchecked:hover {
            border-color: #0e639c;
        }
        
        QCheckBox::indicator:checked {
            background-color: #007acc;
            border: 1px solid #007acc;
            image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xMC41IDFMNCAxLjVMMSAzLjUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+Cjwvc3ZnPgo=);
        }
        
        QCheckBox::indicator:checked:hover {
            background-color: #1177bb;
            border-color: #1177bb;
        }
        
        QToolTip {
            background-color: #2d2d30;
            color: #cccccc;
            border: 1px solid #555555;
            padding: 4px;
        }
        """


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='MSFS exe.xml Manager')
    parser.add_argument(
        '--start-background', 
        action='store_true',
        help='Start the application in background mode (system tray)'
    )
    parser.add_argument(
        '--show',
        action='store_true',
        help='Show the main window if instance is already running'
    )
    parser.add_argument(
        '--exit',
        action='store_true',
        help='Exit any running instance'
    )
    
    return parser.parse_args()


def main():
    args = parse_arguments()
    
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("MSFS exe.xml Manager")
    app.setApplicationVersion("1.0.0-rc1")
    app.setOrganizationName("Flight Sim Tools")
    
    # Handle single instance
    instance_manager = SingleInstanceManager()
    
    # Handle command line arguments for running instance
    if args.exit:
        if instance_manager.send_shutdown_signal():
            print("Sent shutdown signal to running instance")
            sys.exit(0)
        else:
            print("No running instance found")
            sys.exit(1)
    
    if args.show:
        if instance_manager.try_connect_to_existing():
            print("Showed existing instance")
            sys.exit(0)
        else:
            print("No running instance found, starting new instance...")
    
    # Check if another instance is already running
    if instance_manager.try_connect_to_existing():
        print("Another instance is already running. Showing existing window...")
        sys.exit(0)
    
    # We are the primary instance
    if not instance_manager.start_server():
        print("Failed to start single instance server")
        sys.exit(1)
    
    # Create main window
    start_hidden = args.start_background or not QSystemTrayIcon.isSystemTrayAvailable()
    window = MainWindow(start_hidden=start_hidden)
    
    # Connect single instance signals
    instance_manager.show_window_requested.connect(window.show_from_tray)
    instance_manager.shutdown_requested.connect(window.exit_application)
    
    # Cleanup on application exit
    app.aboutToQuit.connect(instance_manager.cleanup)
    
    # Show window if not starting in background
    if not start_hidden:
        window.show()
    
    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()