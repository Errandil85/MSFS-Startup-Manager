import psutil
import time
import threading
from PySide6.QtCore import QObject, Signal
import os
import json
from typing import Dict, List, Optional


class ProcessInfo:
    def __init__(self, pid: int, name: str, exe_path: str):
        self.pid = pid
        self.name = name
        self.exe_path = exe_path
        self.start_time = time.time()


class ProcessMonitor(QObject):
    """Monitor simulator and addon processes"""
    
    # Signals
    sim_started = Signal(str)  # sim_name
    sim_stopped = Signal(str)  # sim_name
    addon_started = Signal(str, int)  # addon_name, pid
    addon_stopped = Signal(str, int)  # addon_name, pid
    
    def __init__(self):
        super().__init__()
        self.monitoring = False
        self.monitor_thread = None
        
        # Process tracking
        self.sim_processes: Dict[str, ProcessInfo] = {}
        self.addon_processes: Dict[str, List[ProcessInfo]] = {}  # addon_name -> list of processes
        
        # Configuration
        self.sim_executables = {
            "MSFS2020": ["FlightSimulator.exe", "Microsoft.FlightSimulator.exe"],
            "MSFS2024": ["FlightSimulator.exe", "Microsoft.FlightDashboard.exe", "Microsoft.Limitless.exe"]
        }
        
        # Polling interval in seconds
        self.poll_interval = 2.0
        
    def start_monitoring(self, sim_version: str = "MSFS2020"):
        """Start monitoring processes"""
        if self.monitoring:
            return
            
        self.monitoring = True
        self.current_sim_version = sim_version
        
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
    def stop_monitoring(self):
        """Stop monitoring processes"""
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1.0)
            
    def add_addon_to_monitor(self, addon_name: str, exe_path: str):
        """Add an addon to monitor (when launched)"""
        if addon_name not in self.addon_processes:
            self.addon_processes[addon_name] = []
            
    def remove_addon_from_monitor(self, addon_name: str):
        """Remove an addon from monitoring"""
        if addon_name in self.addon_processes:
            del self.addon_processes[addon_name]
            
    def terminate_addon_processes(self, addon_name: str):
        """Terminate all processes for a specific addon"""
        if addon_name not in self.addon_processes:
            return
            
        terminated_count = 0
        processes_to_remove = []
        
        for process_info in self.addon_processes[addon_name]:
            try:
                process = psutil.Process(process_info.pid)
                if process.is_running():
                    # Try graceful termination first
                    process.terminate()
                    
                    # Wait a bit for graceful shutdown
                    try:
                        process.wait(timeout=3.0)
                    except psutil.TimeoutExpired:
                        # Force kill if still running
                        if process.is_running():
                            process.kill()
                            
                    terminated_count += 1
                    
                processes_to_remove.append(process_info)
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                processes_to_remove.append(process_info)
                
        # Remove terminated processes from tracking
        for process_info in processes_to_remove:
            if process_info in self.addon_processes[addon_name]:
                self.addon_processes[addon_name].remove(process_info)
                
        return terminated_count
        
    def is_simulator_running(self) -> bool:
        """Check if any simulator process is currently running"""
        return len(self.sim_processes) > 0
        
    def get_running_addons(self) -> List[str]:
        """Get list of addon names that have running processes"""
        running = []
        for addon_name, processes in self.addon_processes.items():
            if any(self._is_process_running(p.pid) for p in processes):
                running.append(addon_name)
        return running
        
    def _monitor_loop(self):
        """Main monitoring loop (runs in separate thread)"""
        while self.monitoring:
            try:
                self._check_simulator_processes()
                self._check_addon_processes()
                time.sleep(self.poll_interval)
            except Exception as e:
                print(f"Process monitor error: {e}")
                time.sleep(self.poll_interval)
                
    def _check_simulator_processes(self):
        """Check for simulator process changes"""
        current_sim_pids = set()
        sim_executables = self.sim_executables.get(self.current_sim_version, [])
        
        # Find all running simulator processes
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                proc_info = proc.info
                if proc_info['name'] in sim_executables:
                    current_sim_pids.add(proc_info['pid'])
                    
                    # Check if this is a new simulator process
                    if proc_info['pid'] not in self.sim_processes:
                        process_info = ProcessInfo(
                            proc_info['pid'], 
                            proc_info['name'], 
                            proc_info.get('exe', '')
                        )
                        self.sim_processes[proc_info['name']] = process_info
                        self.sim_started.emit(proc_info['name'])
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        # Check for stopped simulator processes
        stopped_sims = []
        for sim_name, process_info in self.sim_processes.items():
            if not self._is_process_running(process_info.pid):
                stopped_sims.append(sim_name)
                self.sim_stopped.emit(sim_name)
                
        # Remove stopped processes
        for sim_name in stopped_sims:
            del self.sim_processes[sim_name]
            
    def _check_addon_processes(self):
        """Check for addon process changes"""
        for addon_name in list(self.addon_processes.keys()):
            processes = self.addon_processes[addon_name]
            stopped_processes = []
            
            for process_info in processes:
                if not self._is_process_running(process_info.pid):
                    stopped_processes.append(process_info)
                    self.addon_stopped.emit(addon_name, process_info.pid)
                    
            # Remove stopped processes
            for process_info in stopped_processes:
                processes.remove(process_info)
                
    def _is_process_running(self, pid: int) -> bool:
        """Check if a process with given PID is still running"""
        try:
            process = psutil.Process(pid)
            return process.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
            
    def _find_process_by_exe(self, exe_path: str) -> Optional[ProcessInfo]:
        """Find a running process by executable path"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    proc_info = proc.info
                    if proc_info.get('exe') and os.path.normpath(proc_info['exe']).lower() == os.path.normpath(exe_path).lower():
                        return ProcessInfo(
                            proc_info['pid'],
                            proc_info['name'],
                            proc_info['exe']
                        )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        return None