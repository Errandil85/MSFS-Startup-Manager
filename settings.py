import os
import json

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


def auto_detect_exe_xml(sim_version: str):
    """
    Auto-detect exe.xml location for different MSFS versions and installation types.
    
    Args:
        sim_version: "MSFS2020" or "MSFS2024"
    
    Returns:
        str or None: Path to exe.xml if found, None otherwise
    """
    possible_paths = []
    
    if sim_version == "MSFS2020":
        # Steam version paths
        possible_paths.extend([
            os.path.expandvars(r"%APPDATA%\Microsoft Flight Simulator\exe.xml"),
            os.path.expandvars(r"%LOCALAPPDATA%\Packages\Microsoft.FlightSimulator_8wekyb3d8bbwe\LocalState\exe.xml"),
        ])
        
        # MS Store version paths
        possible_paths.extend([
            os.path.expandvars(r"%LOCALAPPDATA%\Packages\Microsoft.FlightSimulator_8wekyb3d8bbwe\LocalState\exe.xml"),
            os.path.expandvars(r"%APPDATA%\Microsoft Flight Simulator\exe.xml"),
        ])
        
        # Additional common locations for MSFS2020
        possible_paths.extend([
            os.path.expandvars(r"%USERPROFILE%\Documents\Microsoft Flight Simulator\exe.xml"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Flight Simulator\exe.xml"),
        ])
        
    elif sim_version == "MSFS2024":
        # MSFS2024 MS Store version paths
        possible_paths.extend([
            os.path.expandvars(r"%LOCALAPPDATA%\Packages\Microsoft.Limitless_8wekyb3d8bbwe\LocalState\exe.xml"),
            os.path.expandvars(r"%APPDATA%\Microsoft Flight Simulator 2024\exe.xml"),
        ])
        
        # MSFS2024 Steam version paths (when available)
        possible_paths.extend([
            os.path.expandvars(r"%APPDATA%\Microsoft Flight Simulator 2024\exe.xml"),
            os.path.expandvars(r"%USERPROFILE%\Documents\Microsoft Flight Simulator 2024\exe.xml"),
        ])
        
        # Additional potential paths for MSFS2024
        possible_paths.extend([
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Flight Simulator 2024\exe.xml"),
            os.path.expandvars(r"%APPDATA%\Microsoft Flight Simulator\exe.xml"),  # Fallback to 2020 location
        ])
    
    # Check each path and return the first one that exists
    for path in possible_paths:
        if os.path.exists(path) and os.path.isfile(path):
            return path
    
    return None


def get_all_detected_paths(sim_version: str):
    """
    Get all detected exe.xml paths for a simulator version.
    
    Args:
        sim_version: "MSFS2020" or "MSFS2024"
    
    Returns:
        list: List of tuples (description, path) for all found exe.xml files
    """
    detected_paths = []
    
    if sim_version == "MSFS2020":
        paths_to_check = [
            ("Steam Version", os.path.expandvars(r"%APPDATA%\Microsoft Flight Simulator\exe.xml")),
            ("MS Store Version", os.path.expandvars(r"%LOCALAPPDATA%\Packages\Microsoft.FlightSimulator_8wekyb3d8bbwe\LocalState\exe.xml")),
            ("Documents Folder", os.path.expandvars(r"%USERPROFILE%\Documents\Microsoft Flight Simulator\exe.xml")),
            ("Local AppData", os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Flight Simulator\exe.xml")),
        ]
    elif sim_version == "MSFS2024":
        paths_to_check = [
            ("MS Store Version", os.path.expandvars(r"%LOCALAPPDATA%\Packages\Microsoft.Limitless_8wekyb3d8bbwe\LocalState\exe.xml")),
            ("Steam Version", os.path.expandvars(r"%APPDATA%\Microsoft Flight Simulator 2024\exe.xml")),
            ("Documents Folder", os.path.expandvars(r"%USERPROFILE%\Documents\Microsoft Flight Simulator 2024\exe.xml")),
            ("Local AppData", os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Flight Simulator 2024\exe.xml")),
            ("Fallback (2020 Location)", os.path.expandvars(r"%APPDATA%\Microsoft Flight Simulator\exe.xml")),
        ]
    else:
        return []
    
    for description, path in paths_to_check:
        if os.path.exists(path) and os.path.isfile(path):
            detected_paths.append((description, path))
    
    return detected_paths


def get_installation_type(path: str):
    """
    Determine the installation type based on the exe.xml path.
    
    Args:
        path: Path to exe.xml file
    
    Returns:
        str: "Steam", "MS Store", or "Unknown"
    """
    path_lower = path.lower()
    
    if "packages" in path_lower and "microsoft.flightsimulator_8wekyb3d8bbwe" in path_lower:
        return "MS Store (MSFS2020)"
    elif "packages" in path_lower and "microsoft.limitless_8wekyb3d8bbwe" in path_lower:
        return "MS Store (MSFS2024)"
    elif "appdata\\roaming" in path_lower and "microsoft flight simulator" in path_lower:
        return "Steam"
    elif "documents" in path_lower:
        return "Documents"
    else:
        return "Unknown"