import os, json

APP_DIR = os.path.join(os.getenv("APPDATA"), "MSFSExeXmlManager")
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")


def get_preset_dir(sim_version: str):
    """
    Return the preset directory for a given simulator version.
    Example: %APPDATA%/MSFSExeXmlManager/MSFS2020/presets
    """
    path = os.path.join(APP_DIR, sim_version, "presets")
    os.makedirs(path, exist_ok=True)
    return path


def load_settings():
    """Load settings.json as dict."""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_settings(data: dict):
    """Save settings dict to settings.json."""
    os.makedirs(APP_DIR, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
