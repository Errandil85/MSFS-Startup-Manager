import psutil
import time
import threading
from PySide6.QtCore import QObject, Signal
import os
import json
from typing import Dict, List, Optional
from logging_config import get_logger

logger = get_logger(__name__)


class ProcessInfo:
    def __init__(self, pid: int, name: str, exe_path: str):
        self.pid = pid
        self.name = name
        self.exe_path = exe_path
        self.start_time = time.time()


class ProcessMonitor(QObject):
    """Monitor simulator and addon processes"""

    sim_started = Signal(str)
    sim_stopped = Signal(str)
    addon_started = Signal(str, int)
    addon_stopped = Signal(str, int)

    def __init__(self):
        super().__init__()
        self.monitoring = False
        self.monitor_thread = None

        # Guards sim_processes / addon_processes / tracked_addon_paths,
        # which are read and written from both the monitor thread and
        # the Qt GUI thread.
        self._lock = threading.Lock()

        self.sim_processes: Dict[str, ProcessInfo] = {}
        self.addon_processes: Dict[str, List[ProcessInfo]] = {}
        self.tracked_addon_paths: Dict[str, str] = {}

        self.sim_executables = {
            "MSFS2020": ["FlightSimulator.exe", "Microsoft.FlightSimulator.exe"],
            "MSFS2024": ["FlightSimulator.exe", "Microsoft.FlightDashboard.exe", "Microsoft.Limitless.exe", "FlightSimulator2024.exe"]
        }

        self.poll_interval = 2.0

    def start_monitoring(self, sim_version: str = "MSFS2020"):
        if self.monitoring:
            self.stop_monitoring()

        self.monitoring = True
        self.current_sim_version = sim_version

        with self._lock:
            self.sim_processes.clear()

        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info(f"Started process monitoring for {sim_version}")

        self._initial_scan()

    def stop_monitoring(self):
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1.0)
        logger.info("Stopped process monitoring")

    def add_addon_to_monitor(self, addon_name: str, exe_path: str):
        with self._lock:
            self.tracked_addon_paths[addon_name] = exe_path
            if addon_name not in self.addon_processes:
                self.addon_processes[addon_name] = []
        logger.info(f"Added addon to monitor: {addon_name} -> {exe_path}")
        self._scan_for_addon_processes(addon_name, exe_path)

    def remove_addon_from_monitor(self, addon_name: str):
        with self._lock:
            if addon_name in self.addon_processes:
                del self.addon_processes[addon_name]
            if addon_name in self.tracked_addon_paths:
                del self.tracked_addon_paths[addon_name]
        logger.info(f"Removed addon from monitor: {addon_name}")

    def track_known_process(self, addon_name: str, pid: int, exe_path: str = ""):
        """
        Immediately register a process we already know about (e.g. one
        this app just launched itself via Popen and already has the PID
        for), instead of waiting for the next poll cycle to discover it
        through a name/path scan. Closes a race where clicking Stop
        immediately after Start would find nothing tracked yet to
        terminate, and where the Running/Stopped status would lag by up
        to one poll interval after a manual launch.
        """
        exe_name = os.path.basename(exe_path) if exe_path else ""
        newly_tracked = False
        with self._lock:
            if addon_name not in self.addon_processes:
                self.addon_processes[addon_name] = []
            if not any(p.pid == pid for p in self.addon_processes[addon_name]):
                self.addon_processes[addon_name].append(ProcessInfo(pid, exe_name, exe_path))
                newly_tracked = True

        if newly_tracked:
            logger.info(f"Immediately tracking known process: {addon_name} (PID: {pid})")
            self.addon_started.emit(addon_name, pid)

    def terminate_by_exe_path(self, exe_path: str) -> int:
        """
        Immediately scan for and terminate any process matching exe_path,
        regardless of whether it's currently in the tracked
        addon_processes dict. Used as a robust fallback for manual Stop,
        so it isn't dependent on a prior scan (via polling or
        add_addon_to_monitor) having already succeeded in finding and
        tracking the process - e.g. if it was started outside this app
        entirely, or the poll cycle simply hasn't run yet.
        """
        if not exe_path or not os.path.exists(exe_path):
            return 0

        exe_name = os.path.basename(exe_path)
        exe_path_normalized = os.path.normpath(exe_path).lower()
        terminated_count = 0

        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                proc_info = proc.info
                if proc_info['name'] != exe_name:
                    continue
                proc_exe = proc_info.get('exe')
                if proc_exe and os.path.normpath(proc_exe).lower() != exe_path_normalized:
                    continue

                process = psutil.Process(proc_info['pid'])
                if process.is_running():
                    logger.info(f"Force-terminating process by path match: {exe_path} (PID: {proc_info['pid']})")
                    process.terminate()
                    try:
                        process.wait(timeout=5.0)
                    except psutil.TimeoutExpired:
                        if process.is_running():
                            process.kill()
                            try:
                                process.wait(timeout=2.0)
                            except psutil.TimeoutExpired:
                                logger.error(f"Failed to kill process {proc_info['pid']}")
                                continue
                    terminated_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        return terminated_count

    def _initial_scan(self):
        try:
            logger.info("Performing initial process scan...")
            self._check_simulator_processes()
            self._check_addon_processes()
            logger.info(f"Initial scan complete")
        except Exception as e:
            logger.error(f"Error during initial scan: {e}")

    def terminate_addon_processes(self, addon_name: str) -> int:
        logger.info(f"Attempting to terminate processes for addon: {addon_name}")

        with self._lock:
            processes = list(self.addon_processes.get(addon_name, []))

        if not processes:
            logger.info(f"No processes found for {addon_name}")
            return 0

        terminated_count = 0
        processes_to_remove = []

        for process_info in processes:
            try:
                process = psutil.Process(process_info.pid)
                if process.is_running():
                    logger.info(f"Terminating addon process: {addon_name} (PID: {process_info.pid}, Name: {process.name()})")
                    process.terminate()
                    try:
                        process.wait(timeout=5.0)
                        logger.info(f"Process {process_info.pid} terminated gracefully")
                    except psutil.TimeoutExpired:
                        if process.is_running():
                            logger.info(f"Process {process_info.pid} didn't respond to terminate, force killing...")
                            process.kill()
                            try:
                                process.wait(timeout=2.0)
                                logger.info(f"Process {process_info.pid} force killed")
                            except psutil.TimeoutExpired:
                                logger.error(f"Failed to kill process {process_info.pid}")
                                continue
                    terminated_count += 1
                else:
                    logger.info(f"Process {process_info.pid} was already terminated")
                processes_to_remove.append(process_info)
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.error(f"Process {process_info.pid} already gone or access denied: {e}")
                processes_to_remove.append(process_info)

        with self._lock:
            if addon_name in self.addon_processes:
                for process_info in processes_to_remove:
                    if process_info in self.addon_processes[addon_name]:
                        self.addon_processes[addon_name].remove(process_info)

        logger.info(f"Terminated {terminated_count} processes for {addon_name}")
        return terminated_count

    def terminate_all_addon_processes(self, exclude_prefixes: tuple = ()) -> int:
        """
        Terminate every currently tracked addon process, optionally
        excluding any whose tracking key starts with one of
        exclude_prefixes.

        This exists as a catch-all safety net when the simulator stops,
        to clean up any exe.xml auto-close addon not caught by the more
        targeted per-entry pass in MainWindow.on_simulator_stopped. It
        must NOT sweep up companion apps, which have their own separate
        Stop w/ Sim opt-in per entry - they only share this same tracker
        for live Running/Stopped status, not for auto-close eligibility.
        Callers that need that protection should pass
        exclude_prefixes=("companion:",).
        """
        with self._lock:
            addon_names = [
                name for name in self.addon_processes.keys()
                if not any(name.startswith(prefix) for prefix in exclude_prefixes)
            ]

        total_terminated = 0
        for addon_name in addon_names:
            total_terminated += self.terminate_addon_processes(addon_name)
        return total_terminated

    def terminate_simulator_processes(self) -> int:
        """
        Force-terminate any currently tracked simulator process(es) - used
        for the Stop button, to recover from a hung simulator without
        needing Task Manager. Reuses the same terminate -> wait ->
        force-kill escalation as terminate_addon_processes.

        Emits sim_stopped for each process actually stopped, same as a
        normal simulator exit, so the existing auto-close cascade (and
        any UI state tied to that signal) runs exactly as it would if the
        simulator had closed on its own.
        """
        with self._lock:
            processes = list(self.sim_processes.items())  # [(exe_name, ProcessInfo), ...]

        if not processes:
            logger.info("terminate_simulator_processes called but no simulator process is tracked")
            return 0

        terminated_count = 0
        stopped_names = []

        for exe_name, process_info in processes:
            try:
                process = psutil.Process(process_info.pid)
                if process.is_running():
                    logger.info(f"Force-terminating simulator process: {exe_name} (PID: {process_info.pid})")
                    process.terminate()
                    try:
                        process.wait(timeout=5.0)
                        logger.info(f"Simulator process {process_info.pid} terminated gracefully")
                    except psutil.TimeoutExpired:
                        if process.is_running():
                            logger.info(f"Simulator process {process_info.pid} didn't respond to terminate, force killing...")
                            process.kill()
                            try:
                                process.wait(timeout=2.0)
                                logger.info(f"Simulator process {process_info.pid} force killed")
                            except psutil.TimeoutExpired:
                                logger.error(f"Failed to kill simulator process {process_info.pid} - it may be unkillable (e.g. stuck in an uninterruptible I/O wait)")
                                continue
                    terminated_count += 1
                stopped_names.append(exe_name)
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.info(f"Simulator process {process_info.pid} already gone or access denied: {e}")
                stopped_names.append(exe_name)

        with self._lock:
            for exe_name in stopped_names:
                if exe_name in self.sim_processes:
                    del self.sim_processes[exe_name]

        for exe_name in stopped_names:
            self.sim_stopped.emit(exe_name)

        return terminated_count

    def is_simulator_running(self) -> bool:
        with self._lock:
            return len(self.sim_processes) > 0

    def get_running_addons(self) -> List[str]:
        with self._lock:
            items = list(self.addon_processes.items())
        return [name for name, procs in items if any(self._is_process_running(p.pid) for p in procs)]

    def get_addon_process_count(self, addon_name: str) -> int:
        with self._lock:
            procs = list(self.addon_processes.get(addon_name, []))
        return len([p for p in procs if self._is_process_running(p.pid)])

    def _monitor_loop(self):
        logger.info("Process monitor loop started")
        while self.monitoring:
            try:
                self._check_simulator_processes()
                self._check_addon_processes()
                time.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Process monitor error: {e}")
                time.sleep(self.poll_interval)
        logger.info("Process monitor loop ended")

    def _check_simulator_processes(self):
        current_sim_processes = {}
        sim_executables = self.sim_executables.get(self.current_sim_version, [])

        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                proc_info = proc.info
                if proc_info['name'] in sim_executables:
                    current_sim_processes[proc_info['name']] = ProcessInfo(
                        proc_info['pid'], proc_info['name'], proc_info.get('exe', '')
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        newly_started = []
        stopped_sims = []
        with self._lock:
            for name, info in current_sim_processes.items():
                if name not in self.sim_processes:
                    self.sim_processes[name] = info
                    newly_started.append((name, info))
            for sim_name in list(self.sim_processes.keys()):
                if sim_name not in current_sim_processes:
                    stopped_sims.append((sim_name, self.sim_processes[sim_name]))
            for sim_name, _ in stopped_sims:
                del self.sim_processes[sim_name]

        for name, info in newly_started:
            logger.info(f"Simulator started: {name} (PID: {info.pid})")
            self.sim_started.emit(name)
        for sim_name, info in stopped_sims:
            logger.info(f"Simulator stopped: {sim_name} (PID: {info.pid})")
            self.sim_stopped.emit(sim_name)

    def _check_addon_processes(self):
        with self._lock:
            tracked = dict(self.tracked_addon_paths)
        for addon_name, exe_path in tracked.items():
            self._scan_for_addon_processes(addon_name, exe_path)

        with self._lock:
            addon_names = list(self.addon_processes.keys())

        for addon_name in addon_names:
            with self._lock:
                processes = list(self.addon_processes.get(addon_name, []))
            stopped_processes = [p for p in processes if not self._is_process_running(p.pid)]
            if stopped_processes:
                with self._lock:
                    for p in stopped_processes:
                        if p in self.addon_processes.get(addon_name, []):
                            self.addon_processes[addon_name].remove(p)
                for p in stopped_processes:
                    logger.info(f"Addon process stopped: {addon_name} (PID: {p.pid})")
                    self.addon_stopped.emit(addon_name, p.pid)

    def _scan_for_addon_processes(self, addon_name: str, exe_path: str):
        if not os.path.exists(exe_path):
            return

        exe_name = os.path.basename(exe_path)
        exe_path_normalized = os.path.normpath(exe_path).lower()

        with self._lock:
            current_pids = {p.pid for p in self.addon_processes.get(addon_name, [])}

        found = []
        skipped_unverified = 0
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                proc_info = proc.info
                if proc_info['pid'] in current_pids:
                    continue
                if proc_info['name'] != exe_name:
                    continue
                proc_exe = proc_info.get('exe')
                if proc_exe:
                    proc_exe_normalized = os.path.normpath(proc_exe).lower()
                    if proc_exe_normalized != exe_path_normalized:
                        continue
                else:
                    # Can't verify the actual path (psutil often can't
                    # read it for processes owned by another user/session,
                    # protected processes, etc.) - a name match alone is
                    # not reliable enough to trust: plenty of unrelated
                    # programs can share a generic exe filename with a
                    # tracked entry. Skip rather than risk a false
                    # "running" status.
                    skipped_unverified += 1
                    continue
                found.append(ProcessInfo(proc_info['pid'], proc_info['name'], proc_exe or exe_path))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        if skipped_unverified:
            logger.info(
                f"Skipped {skipped_unverified} process(es) named '{exe_name}' while scanning for "
                f"{addon_name}: could not verify their actual path, so not counted as a match."
            )

        if found:
            with self._lock:
                if addon_name not in self.addon_processes:
                    self.addon_processes[addon_name] = []
                self.addon_processes[addon_name].extend(found)
            for p in found:
                logger.info(f"New addon process detected: {addon_name} (PID: {p.pid}, Path: {p.exe_path})")
                self.addon_started.emit(addon_name, p.pid)

    def _is_process_running(self, pid: int) -> bool:
        try:
            process = psutil.Process(pid)
            return process.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False

    def debug_status(self):
        with self._lock:
            sim_count = len(self.sim_processes)
            sim_items = list(self.sim_processes.items())
            tracked_items = list(self.tracked_addon_paths.items())
            addon_items = list(self.addon_processes.items())

        logger.info(f"\n=== Process Monitor Debug Status ===")
        logger.info(f"Monitoring: {self.monitoring}")
        logger.info(f"Current sim version: {getattr(self, 'current_sim_version', 'Not set')}")
        logger.info(f"Simulator processes: {sim_count}")
        for name, proc in sim_items:
            logger.info(f"  - {name}: PID {proc.pid}")

        logger.info(f"Tracked addon paths: {len(tracked_items)}")
        for name, path in tracked_items:
            logger.info(f"  - {name}: {path}")

        logger.info(f"Addon processes: {len(addon_items)}")
        for name, processes in addon_items:
            running_count = sum(1 for p in processes if self._is_process_running(p.pid))
            logger.info(f"  - {name}: {len(processes)} total, {running_count} running")
            for proc in processes:
                status = "running" if self._is_process_running(proc.pid) else "stopped"
                logger.info(f"    * PID {proc.pid}: {status}")
        logger.info("=" * 35)