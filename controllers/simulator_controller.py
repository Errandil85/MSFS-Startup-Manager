from PySide6.QtCore import QObject, Signal

import settings
import sim_launcher
from logging_config import get_logger

logger = get_logger(__name__)


class SimulatorController(QObject):
    """
    Owns simulator-launch behavior: detecting Steam vs MS Store/Xbox,
    launching (optionally elevated), and persisting the "run as
    administrator" preference per simulator version.

    Kept separate from MainWindow so simulator-launch logic doesn't keep
    growing the already large MainWindow class - a first step toward
    splitting MainWindow's responsibilities into focused controllers
    (backups, presets, and process monitoring are natural next
    candidates for the same treatment).
    """

    launch_started = Signal(str)         # sim_version
    launch_succeeded = Signal(str, str)  # sim_version, install_type ("steam" | "ms_store")
    launch_failed = Signal(str, str)     # sim_version, error_message

    def __init__(self, parent=None):
        super().__init__(parent)

    # -------------------------
    # Run-as-admin preference (persisted per sim version, in the same
    # settings.json the rest of the app already uses)
    # -------------------------
    def get_run_as_admin(self, sim_version: str) -> bool:
        s = settings.load_settings()
        prefs = s.get("run_sim_as_admin", {})
        return bool(prefs.get(sim_version, False))

    def set_run_as_admin(self, sim_version: str, value: bool):
        s = settings.load_settings()
        prefs = s.get("run_sim_as_admin", {})
        prefs[sim_version] = bool(value)
        s["run_sim_as_admin"] = prefs
        settings.save_settings(s)
        logger.info(f"Run as Administrator for {sim_version} set to {bool(value)}")

    # -------------------------
    # Install type / admin support
    # -------------------------
    def detect_install_type(self, sim_version: str, exe_xml_path: str = None) -> str:
        return sim_launcher.detect_install_type(sim_version, exe_xml_path)

    def is_admin_supported(self, install_type: str) -> bool:
        return sim_launcher.can_run_as_admin(install_type)

    # -------------------------
    # Launch
    # -------------------------
    def launch(self, sim_version: str, exe_xml_path: str = None):
        """
        Launch sim_version. Emits launch_started immediately, then either
        launch_succeeded or launch_failed once the attempt resolves.

        The "run as admin" preference is only honored if the detected
        install type actually supports it (Steam) - for MS Store/Xbox
        installs it's silently ignored here as a safety net, since the UI
        is expected to disable the option for those installs in the
        first place.
        """
        install_type = self.detect_install_type(sim_version, exe_xml_path)
        admin_requested = self.get_run_as_admin(sim_version)
        run_as_admin = admin_requested and self.is_admin_supported(install_type)

        self.launch_started.emit(sim_version)
        logger.info(
            f"Launching {sim_version} (install_type={install_type}, "
            f"admin_requested={admin_requested}, run_as_admin={run_as_admin})"
        )

        try:
            sim_launcher.launch_simulator(sim_version, install_type, run_as_admin=run_as_admin)
            self.launch_succeeded.emit(sim_version, install_type)
        except sim_launcher.SimLaunchError as e:
            logger.error(f"Failed to launch {sim_version}: {e}")
            self.launch_failed.emit(sim_version, str(e))
        except Exception as e:
            logger.error(f"Unexpected error launching {sim_version}: {e}")
            self.launch_failed.emit(sim_version, f"Unexpected error: {e}")
