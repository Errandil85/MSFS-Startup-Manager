"""
Simulator launching.

Handles the two very different ways MSFS can be installed and launched:

  - Steam: launched via the steam:// protocol handler (no elevation), or
    by launching steam.exe itself with "runas" + "-applaunch <appid>"
    (elevation - the game inherits admin rights from the elevated Steam
    client).
  - MS Store / Xbox app: these are UWP-packaged apps. They are launched
    via `explorer.exe shell:AppsFolder\\<PackageFamilyName>!App`, and
    Windows does NOT allow elevating a UWP app via ShellExecute's "runas"
    verb (or any other normal means) - this is a Windows platform
    restriction, not something this app can work around. Requesting
    admin for an MS Store install is silently downgraded to a normal
    launch, with a warning logged (the UI is expected to disable the
    "Run as Administrator" option for MS Store installs in the first
    place, so this is a safety net rather than the primary guard).

This module has no Qt dependency, so it's easy to test/reuse independent
of the GUI.
"""

import os
import sys
import subprocess

import settings
from logging_config import get_logger

logger = get_logger(__name__)


STEAM_APP_IDS = {
    "MSFS2020": "1250410",
    "MSFS2024": "2537590",
}

# Same package family names settings.py already uses for exe.xml
# auto-detection - kept in sync with those.
MS_STORE_PACKAGE_FAMILY = {
    "MSFS2020": "Microsoft.FlightSimulator_8wekyb3d8bbwe",
    "MSFS2024": "Microsoft.Limitless_8wekyb3d8bbwe",
}

STEAM_EXE_XML_DIR = {
    "MSFS2020": r"%APPDATA%\Microsoft Flight Simulator",
    "MSFS2024": r"%APPDATA%\Microsoft Flight Simulator 2024",
}


class SimLaunchError(Exception):
    """Raised when the simulator could not be launched for any reason."""
    pass


def detect_install_type(sim_version: str, exe_xml_path: str = None) -> str:
    """
    Determine whether sim_version is a Steam or MS Store/Xbox install.

    Prefers the currently loaded exe.xml's path (most reliable, since it's
    exactly where the file was found). Falls back to probing the
    filesystem for known install markers if no exe.xml path is available.

    Returns "steam", "ms_store", or "unknown".
    """
    if exe_xml_path:
        install_label = settings.get_installation_type(exe_xml_path)
        if "MS Store" in install_label:
            return "ms_store"
        if install_label == "Steam":
            return "steam"

    # Fallback: probe the filesystem directly.
    package_family = MS_STORE_PACKAGE_FAMILY.get(sim_version)
    if package_family:
        local_state = os.path.expandvars(
            rf"%LOCALAPPDATA%\Packages\{package_family}\LocalState"
        )
        if os.path.isdir(local_state):
            return "ms_store"

    steam_dir = STEAM_EXE_XML_DIR.get(sim_version)
    if steam_dir and os.path.isdir(os.path.expandvars(steam_dir)):
        return "steam"

    return "unknown"


def can_run_as_admin(install_type: str) -> bool:
    """MS Store/UWP apps cannot be elevated via any normal mechanism."""
    return install_type == "steam"


def launch_simulator(sim_version: str, install_type: str, run_as_admin: bool = False) -> None:
    """
    Launch the simulator. Raises SimLaunchError on failure.

    Note this only confirms the launch was *attempted* successfully -
    Steam and the MS Store handle the actual startup asynchronously, so a
    successful return here doesn't guarantee the sim window ever appears
    (the existing process monitor will pick it up once it does).
    """
    if install_type == "steam":
        _launch_via_steam(sim_version, run_as_admin)
    elif install_type == "ms_store":
        if run_as_admin:
            logger.warning(
                f"Run as Administrator was requested for {sim_version}, but MS Store/Xbox "
                f"apps cannot be elevated (Windows platform restriction) - launching normally."
            )
        _launch_via_ms_store(sim_version)
    else:
        raise SimLaunchError(
            f"Could not determine whether {sim_version} is a Steam or MS Store install. "
            f"Load or auto-detect an exe.xml file for this version first."
        )


def _find_steam_exe():
    """Look up Steam's install path from the registry, with common-path fallbacks."""
    try:
        import winreg
        for hive, subkey, value_name in [
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
        ]:
            try:
                with winreg.OpenKey(hive, subkey) as key:
                    install_path, _ = winreg.QueryValueEx(key, value_name)
                    steam_exe = os.path.join(os.path.normpath(install_path), "steam.exe")
                    if os.path.exists(steam_exe):
                        return steam_exe
            except OSError:
                continue
    except ImportError:
        pass  # not on Windows

    for candidate in (r"C:\Program Files (x86)\Steam\steam.exe", r"C:\Program Files\Steam\steam.exe"):
        if os.path.exists(candidate):
            return candidate
    return None


def _launch_via_steam(sim_version: str, run_as_admin: bool):
    app_id = STEAM_APP_IDS.get(sim_version)
    if not app_id:
        raise SimLaunchError(f"Unknown Steam App ID for {sim_version}")

    if run_as_admin:
        steam_exe = _find_steam_exe()
        if not steam_exe:
            raise SimLaunchError(
                "Could not locate steam.exe to launch as Administrator. "
                "Make sure Steam is installed, or launch without Administrator privileges."
            )
        logger.info(f"Launching {sim_version} via Steam as Administrator (AppID {app_id})")
        _shell_execute_runas(steam_exe, f"-applaunch {app_id}")
        return

    # Normal (non-elevated) launch: the steam:// protocol handler doesn't
    # require knowing Steam's install path at all.
    try:
        logger.info(f"Launching {sim_version} via Steam (AppID {app_id})")
        os.startfile(f"steam://rungameid/{app_id}")
    except Exception as e:
        raise SimLaunchError(f"Failed to launch via steam:// protocol: {e}")


def _launch_via_ms_store(sim_version: str):
    package_family = MS_STORE_PACKAGE_FAMILY.get(sim_version)
    if not package_family:
        raise SimLaunchError(f"Unknown MS Store package family for {sim_version}")

    # If the package genuinely isn't installed, "explorer.exe
    # shell:AppsFolder\..." resolves to nothing and Explorer just opens a
    # normal window instead of launching anything - which looks like a
    # bug but is actually Explorer's default behavior for an unresolved
    # shell URI. Checking first turns that silent no-op into a clear
    # error instead.
    local_state = os.path.expandvars(rf"%LOCALAPPDATA%\Packages\{package_family}\LocalState")
    if not os.path.isdir(local_state):
        raise SimLaunchError(
            f"{sim_version} does not appear to be installed via MS Store/Xbox on this PC "
            f"(expected package data at {local_state} was not found). If you actually use "
            f"the Steam version, try reloading or auto-detecting the exe.xml file for "
            f"{sim_version} so the install type is detected correctly."
        )

    try:
        logger.info(f"Launching {sim_version} via MS Store/Xbox (package {package_family})")
        # explorer.exe is the standard, supported way to launch a UWP app
        # from outside the package itself.
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{package_family}!App"])
    except Exception as e:
        raise SimLaunchError(f"Failed to launch MS Store/Xbox app: {e}")


def _shell_execute_runas(exe_path: str, params: str = ""):
    """Launch exe_path elevated (triggers a UAC prompt) via ShellExecuteW's 'runas' verb."""
    if sys.platform != "win32":
        raise SimLaunchError("Elevated launch is only supported on Windows.")
    try:
        import ctypes
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe_path, params, os.path.dirname(exe_path), 1
        )
        # ShellExecuteW returns a value > 32 on success, an error code otherwise.
        if result <= 32:
            raise SimLaunchError(f"ShellExecute failed (code {result}) launching {exe_path} as Administrator")
    except SimLaunchError:
        raise
    except Exception as e:
        raise SimLaunchError(f"Failed to launch elevated: {e}")