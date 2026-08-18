from PySide6.QtCore import QObject, Signal, QTimer

from companion_apps import CompanionAppManager
from logging_config import get_logger

logger = get_logger(__name__)


class CompanionAppsController(QObject):
    """
    Owns companion-app lifecycle: manual start/stop, and automatic
    start-with-sim / stop-with-sim behavior (including an optional
    per-entry start delay).

    Deliberately reuses the existing ProcessMonitor rather than building
    a second process-tracking system - ProcessMonitor's addon tracking
    (add_addon_to_monitor / terminate_addon_processes / etc.) was already
    generic name-to-path tracking with no actual dependency on exe.xml,
    it just happened to only be used for exe.xml auto-close entries so
    far. Companion apps use the same mechanism with a namespaced key
    (see CompanionAppEntry.monitor_key) so they can't collide with an
    exe.xml addon that happens to share a display name.

    This is the second piece of splitting MainWindow's responsibilities
    into focused controllers, following the same pattern as
    SimulatorController.
    """

    entries_changed = Signal()            # table should repopulate
    app_launch_failed = Signal(str, str)  # name, error_message
    status_message = Signal(str)          # forwarded to MainWindow.update_status

    def __init__(self, process_monitor, parent=None):
        super().__init__(parent)
        self.process_monitor = process_monitor
        self.manager = CompanionAppManager()

        # monitor_key -> QTimer, for entries whose auto-start is
        # currently counting down a start_delay_seconds delay. Tracked so
        # a pending launch can be cancelled if the sim stops (or the
        # entry is removed/modified) before the delay elapses.
        self._pending_start_timers = {}

        # Register every loaded entry for monitoring immediately, so
        # "already running" status (including apps started manually,
        # outside this app entirely, before this session even began) is
        # correct from the moment the app opens rather than only after
        # the next poll cycle happens to notice.
        self.register_all_for_monitoring()

    # -------------------------
    # ProcessMonitor integration
    # -------------------------
    def register_all_for_monitoring(self):
        for entry in self.manager.entries:
            if entry.path:
                self.process_monitor.add_addon_to_monitor(entry.monitor_key(), entry.path)

    def refresh_monitoring_for_entry(self, entry):
        self.process_monitor.remove_addon_from_monitor(entry.monitor_key())
        if entry.path:
            self.process_monitor.add_addon_to_monitor(entry.monitor_key(), entry.path)

    def is_running(self, entry) -> bool:
        return self.process_monitor.get_addon_process_count(entry.monitor_key()) > 0

    # -------------------------
    # CRUD (delegates to CompanionAppManager, keeps monitoring in sync)
    # -------------------------
    def add_entry(self, name, path, args, enabled, start_with_sim, stop_with_sim, start_delay_seconds=0):
        entry = self.manager.add_entry(name, path, args, enabled, start_with_sim, stop_with_sim, start_delay_seconds)
        self.refresh_monitoring_for_entry(entry)
        self.entries_changed.emit()

    def modify_entry(self, index, name, path, args, enabled, start_with_sim, stop_with_sim, start_delay_seconds=0):
        if 0 <= index < len(self.manager.entries):
            old_entry = self.manager.entries[index]
            self._cancel_pending_start(old_entry.monitor_key())
            self.process_monitor.remove_addon_from_monitor(old_entry.monitor_key())
        self.manager.modify_entry(index, name, path, args, enabled, start_with_sim, stop_with_sim, start_delay_seconds)
        if 0 <= index < len(self.manager.entries):
            self.refresh_monitoring_for_entry(self.manager.entries[index])
        self.entries_changed.emit()

    def remove_entry(self, index):
        if 0 <= index < len(self.manager.entries):
            entry = self.manager.entries[index]
            self._cancel_pending_start(entry.monitor_key())
            self.process_monitor.remove_addon_from_monitor(entry.monitor_key())
        self.manager.remove_entry(index)
        self.entries_changed.emit()

    # -------------------------
    # Manual start/stop - always available regardless of the Enabled
    # flag, which only governs automatic start/stop-with-sim eligibility.
    # Manual Start always launches immediately - start_delay_seconds only
    # applies to the automatic start-with-sim path below.
    # -------------------------
    def start_entry(self, index):
        try:
            entry = self.manager.entries[index]
        except IndexError:
            return
        if self.is_running(entry):
            self.status_message.emit(f"{entry.name} is already running")
            return
        try:
            process = self.manager.launch_entry(index)
            if process is not None:
                # Register the PID we already have immediately, instead
                # of waiting for the next poll cycle (up to ~2s) to
                # discover it via a name/path scan. This is what makes
                # the Status column update right away, and what makes an
                # immediate Stop click actually have something to
                # terminate rather than finding nothing tracked yet.
                self.process_monitor.track_known_process(entry.monitor_key(), process.pid, entry.path)
            self.status_message.emit(f"Launched {entry.name}")
        except Exception as e:
            logger.error(f"Failed to launch companion app {entry.name}: {e}")
            self.app_launch_failed.emit(entry.name, str(e))

    def stop_entry(self, index):
        try:
            entry = self.manager.entries[index]
        except IndexError:
            return

        # A manual Stop should also cancel any delayed auto-start still
        # counting down for this entry - otherwise it could stop it now
        # and then have it launch again moments later on its own.
        self._cancel_pending_start(entry.monitor_key())

        terminated = self.process_monitor.terminate_addon_processes(entry.monitor_key())

        if terminated == 0:
            # Fall back to a direct fresh scan-and-terminate by path,
            # rather than giving up just because nothing was tracked yet -
            # covers Stop clicked right after Start (before the next poll
            # cycle), or an app that was started outside this app
            # entirely and hasn't been picked up by a scan yet.
            terminated = self.process_monitor.terminate_by_exe_path(entry.path)

        # Re-sync tracking either way, so the table reflects reality
        # immediately instead of waiting for the next poll cycle.
        self.refresh_monitoring_for_entry(entry)
        self.entries_changed.emit()

        if terminated > 0:
            self.status_message.emit(f"Stopped {entry.name}")
        else:
            self.status_message.emit(f"{entry.name} was not running")

    # -------------------------
    # Automatic start-with-sim / stop-with-sim, driven by the same
    # ProcessMonitor.sim_started / sim_stopped signals the exe.xml
    # auto-close logic already uses.
    # -------------------------
    def on_sim_started(self, sim_name):
        for index, entry in enumerate(self.manager.entries):
            if entry.enabled and entry.start_with_sim and not self.is_running(entry):
                delay = max(0, int(entry.start_delay_seconds or 0))
                if delay > 0:
                    logger.info(f"Scheduling delayed auto-start for {entry.name} in {delay}s")
                    self._schedule_delayed_start(entry, delay)
                else:
                    logger.info(f"Auto-starting companion app with simulator: {entry.name}")
                    self.start_entry(index)

    def on_sim_stopped(self, sim_name):
        # Cancel any delayed auto-starts still counting down - the sim
        # already stopped, so launching "with the sim" now would be
        # launching into an already-closed sim, which defeats the point.
        for key in list(self._pending_start_timers.keys()):
            logger.info(f"Cancelling pending delayed auto-start (simulator stopped): {key}")
            self._cancel_pending_start(key)

        for index, entry in enumerate(self.manager.entries):
            if entry.enabled and entry.stop_with_sim and self.is_running(entry):
                logger.info(f"Auto-stopping companion app with simulator: {entry.name}")
                self.stop_entry(index)

    # -------------------------
    # Delayed auto-start scheduling
    # -------------------------
    def _schedule_delayed_start(self, entry, delay_seconds):
        key = entry.monitor_key()
        self._cancel_pending_start(key)  # replace any existing pending timer for this entry

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._execute_delayed_start(key))
        timer.start(delay_seconds * 1000)
        self._pending_start_timers[key] = timer

    def _execute_delayed_start(self, key):
        self._pending_start_timers.pop(key, None)
        # Re-look-up the entry by its stable key rather than trusting a
        # captured index, since entries can be added/removed/reordered
        # while the delay was counting down.
        for index, entry in enumerate(self.manager.entries):
            if entry.monitor_key() == key:
                if entry.enabled and entry.start_with_sim and not self.is_running(entry):
                    logger.info(f"Executing delayed auto-start for {entry.name}")
                    self.start_entry(index)
                return

    def _cancel_pending_start(self, key):
        timer = self._pending_start_timers.pop(key, None)
        if timer is not None:
            timer.stop()