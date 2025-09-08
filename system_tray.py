import sys
import os
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QObject, Signal


class SystemTrayManager(QObject):
    """Manages system tray icon and menu"""
    
    # Signals
    show_window_requested = Signal()
    exit_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tray_icon = None
        self.tray_menu = None
        
    def setup_tray(self):
        """Setup system tray icon and menu"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("System tray is not available")
            return False
        
        # Create tray icon
        self.tray_icon = QSystemTrayIcon()
        
        # Set icon (try to use the same icon as the main window)
        try:
            icon = QIcon("icon.ico")
            if icon.isNull():
                # Fallback to a default icon if icon.ico doesn't exist
                style = QApplication.style()
                icon = style.standardIcon(style.StandardPixmap.SP_DesktopIcon)
            self.tray_icon.setIcon(icon)
        except Exception as e:
            print(f"Icon loading failed: {e}")
            # Ultimate fallback
            try:
                style = QApplication.style()
                icon = style.standardIcon(style.StandardPixmap.SP_DesktopIcon)
                self.tray_icon.setIcon(icon)
            except Exception as e2:
                print(f"Fallback icon loading failed: {e2}")
                # Create a minimal icon if all else fails
                from PySide6.QtGui import QPixmap, QPainter, QBrush
                from PySide6.QtCore import Qt
                pixmap = QPixmap(16, 16)
                pixmap.fill(Qt.transparent)
                painter = QPainter(pixmap)
                painter.setBrush(QBrush(Qt.blue))
                painter.drawEllipse(2, 2, 12, 12)
                painter.end()
                self.tray_icon.setIcon(QIcon(pixmap))
        
        self.tray_icon.setToolTip("MSFS Startup Manager")
        
        # Create tray menu
        self.create_tray_menu()
        
        # Connect signals
        self.tray_icon.activated.connect(self._on_tray_activated)
        
        # Show tray icon
        self.tray_icon.show()
        
        return True
    
    def create_tray_menu(self):
        """Create the system tray context menu"""
        self.tray_menu = QMenu()
        
        # Show/Hide action
        show_action = QAction("Show Manager", self)
        show_action.triggered.connect(self.show_window_requested.emit)
        self.tray_menu.addAction(show_action)
        
        self.tray_menu.addSeparator()
        
        # Exit action
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.exit_requested.emit)
        self.tray_menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(self.tray_menu)
    
    def _on_tray_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_window_requested.emit()
    
    def show_message(self, title, message, icon=QSystemTrayIcon.Information, timeout=3000):
        """Show system tray notification"""
        if self.tray_icon and self.tray_icon.isVisible():
            self.tray_icon.showMessage(title, message, icon, timeout)
    
    def hide(self):
        """Hide the system tray icon"""
        if self.tray_icon:
            self.tray_icon.hide()
    
    def is_visible(self):
        """Check if tray icon is visible"""
        return self.tray_icon and self.tray_icon.isVisible()