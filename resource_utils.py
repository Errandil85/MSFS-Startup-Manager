"""
Shared resource-path helper.

Both main.py and system_tray.py need to locate bundled resources (icon.ico)
in a way that works both running from source and from a frozen PyInstaller
build. This used to be duplicated - main.py had its own get_resource_path()
while system_tray.py loaded QIcon("icon.ico") with a bare relative path,
which only works if the process's current working directory happens to be
the app's install folder. That mismatch is a likely cause of the tray/
taskbar icon showing the wrong thing in some launch configurations (e.g.
launched via a shortcut with a different "Start in" folder, or the
exe.xml-triggered background instance).
"""

import os
import sys


def get_resource_path(relative_path):
    """Get absolute path to a bundled resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)
