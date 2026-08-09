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

    def terminate_all_addon_processes(self) -> int:
        with self._lock:
            addon_names = list(self.addon_processes.keys())

        total_terminated = 0
        for addon_name in addon_names:
            total_terminated += self.terminate_addon_processes(addon_name)
        return total_terminated

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
                    logger.error(f"Warning: Could not get exe path for PID {proc_info['pid']}, matching by name only")
                found.append(ProcessInfo(proc_info['pid'], proc_info['name'], proc_exe or exe_path))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

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
