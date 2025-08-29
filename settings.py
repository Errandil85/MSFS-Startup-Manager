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


def get_backup_dir(sim_version: str):
    """
    Return the backup directory for a given simulator version.
    Example: %APPDATA%/MSFSExeXmlManager/MSFS2020/backups
    """
    path = os.path.join(APP_DIR, sim_version, "backups")
    os.makedirs(path, exist_ok=True)
    return path


def create_backup(exe_xml_path: str, sim_version: str):
    """
    Create a backup of the exe.xml file.
    
    Args:
        exe_xml_path: Path to the original exe.xml file
        sim_version: Simulator version (MSFS2020 or MSFS2024)
    
    Returns:
        str: Path to the backup file, or None if backup failed
    """
    if not os.path.exists(exe_xml_path):
        return None
    
    backup_dir = get_backup_dir(sim_version)
    
    # Generate backup filename with timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    install_type = get_installation_type(exe_xml_path).replace(" ", "_").replace("(", "").replace(")", "")
    backup_filename = f"exe_xml_backup_{install_type}_{timestamp}.xml"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    try:
        import shutil
        shutil.copy2(exe_xml_path, backup_path)
        return backup_path
    except Exception as e:
        print(f"Failed to create backup: {e}")
        return None


def get_existing_backups(sim_version: str):
    """
    Get a list of existing backup files for a simulator version.
    
    Args:
        sim_version: Simulator version (MSFS2020 or MSFS2024)
    
    Returns:
        list: List of tuples (filename, full_path, creation_time)
    """
    backup_dir = get_backup_dir(sim_version)
    backups = []
    
    try:
        for filename in os.listdir(backup_dir):
            if filename.startswith("exe_xml_backup_") and filename.endswith(".xml"):
                full_path = os.path.join(backup_dir, filename)
                creation_time = os.path.getctime(full_path)
                backups.append((filename, full_path, creation_time))
        
        # Sort by creation time, newest first
        backups.sort(key=lambda x: x[2], reverse=True)
        
    except Exception as e:
        print(f"Failed to list backups: {e}")
    
    return backups


def is_first_time_using_file(exe_xml_path: str, sim_version: str):
    """
    Check if this is the first time using this specific exe.xml file.
    
    Args:
        exe_xml_path: Path to the exe.xml file
        sim_version: Simulator version
    
    Returns:
        bool: True if this is the first time using this file
    """
    s = load_settings()
    backed_up_files = s.get("backed_up_files", {})
    sim_backed_up = backed_up_files.get(sim_version, [])
    
    # Normalize the path for comparison
    normalized_path = os.path.normpath(exe_xml_path).lower()
    
    return normalized_path not in [os.path.normpath(p).lower() for p in sim_backed_up]


def mark_file_as_backed_up(exe_xml_path: str, sim_version: str):
    """
    Mark a file as having been backed up.
    
    Args:
        exe_xml_path: Path to the exe.xml file
        sim_version: Simulator version
    """
    s = load_settings()
    if "backed_up_files" not in s:
        s["backed_up_files"] = {}
    
    if sim_version not in s["backed_up_files"]:
        s["backed_up_files"][sim_version] = []
    
    # Normalize the path for storage
    normalized_path = os.path.normpath(exe_xml_path)
    
    if normalized_path not in s["backed_up_files"][sim_version]:
        s["backed_up_files"][sim_version].append(normalized_path)
        save_settings(s)


def auto_backup_if_needed(exe_xml_path: str, sim_version: str):
    """
    Automatically create a backup if this is the first time using this file.
    
    Args:
        exe_xml_path: Path to the exe.xml file
        sim_version: Simulator version
    
    Returns:
        tuple: (backup_created, backup_path, error_message)
    """
    if not is_first_time_using_file(exe_xml_path, sim_version):
        return False, None, "File already backed up previously"
    
    backup_path = create_backup(exe_xml_path, sim_version)
    
    if backup_path:
        mark_file_as_backed_up(exe_xml_path, sim_version)
        return True, backup_path, None
    else:
        return False, None, "Failed to create backup"