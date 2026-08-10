import sys
import os
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QObject, Signal

from resource_utils import get_resource_path
from logging_config import get_logger

logger = get_logger(__name__)


class SystemTrayManager(QObject):
    """Manages system tray icon and menu"""
    
    # Signals
    show_window_requested = Signal()
    exit_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tray_icon = None
        self.tray_menu = None
        
    def setup_tray(self, icon=None):
        """
        Setup system tray icon and menu.

        Args:
            icon: Optional pre-resolved QIcon (e.g. MainWindow.windowIcon()).
                  Preferred over re-resolving icon.ico independently here,
                  since two separate lookups of the same file is exactly
                  how the window icon and tray icon can end up mismatched.
                  Falls back to resolving icon.ico directly if not given,
                  or if the given icon turns out to be null/empty.
        """
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("System tray is not available")
            return False
        
        # Parent the tray icon to this manager instead of leaving it
        # parentless, so its lifetime is tied to ours rather than relying
        # on Qt's top-level object cleanup.
        self.tray_icon = QSystemTrayIcon(self)
        
        try:
            if icon is not None and not icon.isNull():
                resolved_icon = icon
            else:
                # Fallback: resolve icon.ico ourselves using the same
                # PyInstaller-aware path helper main.py uses, instead of a
                # bare relative "icon.ico" (which only resolves correctly
                # if the process's working directory happens to be the
                # app's install folder - not guaranteed when launched via
                # a shortcut or from exe.xml).
                icon_path = get_resource_path("icon.ico")
                resolved_icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
                if resolved_icon.isNull() and not os.path.exists(icon_path):
                    logger.warning(f"icon.ico not found at expected path: {icon_path} - using fallback tray icon")

            if resolved_icon.isNull():
                style = QApplication.style()
                resolved_icon = style.standardIcon(style.StandardPixmap.SP_DesktopIcon)

            self.tray_icon.setIcon(resolved_icon)
        except Exception as e:
            logger.warning(f"Icon loading failed: {e}")
            # Ultimate fallback
            try:
                style = QApplication.style()
                fallback_icon = style.standardIcon(style.StandardPixmap.SP_DesktopIcon)
                self.tray_icon.setIcon(fallback_icon)
            except Exception as e2:
                logger.error(f"Fallback icon loading failed: {e2}")
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