import psutil
import threading
import time
import subprocess
import os
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

class ProcessState(Enum):
    NOT_RUNNING = "not_running"
    STARTING = "starting"
    RUNNING = "running"
    TERMINATED = "terminated"
    ERROR = "error"

@dataclass
class ManagedProcess:
    pid: Optional[int]
    name: str
    path: str
    args: str
    state: ProcessState
    started_time: Optional[float]
    auto_terminate: bool
    msfs_dependent: bool = True  # Whether this process should be terminated when MSFS closes

class PerEntryProcessManager:
    """
    Manage individual processes with per-entry control
    """
    
    def __init__(self):
        self.managed_processes: Dict[str, ManagedProcess] = {}  # key = entry_name
        self.msfs_processes = ["FlightSimulator.exe", "Microsoft.FlightSimulator.exe"]
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_monitoring = threading.Event()
        self.callbacks: Dict[str, List[Callable]] = {
            'process_started': [],
            'process_stopped': [],
            'process_terminated': [],
            'msfs_status_changed': []
        }
        self._msfs_was_running = False
        self._monitoring_active = False
    
    def add_callback(self, event_type: str, callback: Callable):
        """Add callback for events"""
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
    
    def _emit_event(self, event_type: str, *args, **kwargs):
        """Emit event to all registered callbacks"""
        for callback in self.callbacks.get(event_type, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                print(f"Callback error in {event_type}: {e}")
    
    def is_msfs_running(self) -> bool:
        """Check if any MSFS process is currently running"""
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] in self.msfs_processes:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False
    
    def launch_process(self, entry_name: str, executable_path: str, args: str = "", 
                      auto_terminate: bool = True, msfs_dependent: bool = True) -> bool:
        """
        Launch a process and optionally manage it
        
        Args:
            entry_name: Unique identifier for this entry
            executable_path: Path to executable
            args: Command line arguments
            auto_terminate: Whether to terminate when MSFS closes
            msfs_dependent: Whether this process depends on MSFS
        
        Returns:
            True if launched successfully
        """
        try:
            # Parse arguments
            cmd_args = args.split() if args else []
            full_command = [executable_path] + cmd_args
            
            # Create managed process entry
            managed_proc = ManagedProcess(
                pid=None,
                name=os.path.basename(executable_path),
                path=executable_path,
                args=args,
                state=ProcessState.STARTING,
                started_time=None,
                auto_terminate=auto_terminate,
                msfs_dependent=msfs_dependent
            )
            
            self.managed_processes[entry_name] = managed_proc
            
            # Launch process
            proc = subprocess.Popen(full_command)
            
            # Update managed process
            managed_proc.pid = proc.pid
            managed_proc.state = ProcessState.RUNNING
            managed_proc.started_time = time.time()
            
            self._emit_event('process_started', entry_name, managed_proc)
            print(f"Launched: {managed_proc.name} (PID: {proc.pid})")
            
            # Start monitoring if not already active and auto_terminate is enabled
            if auto_terminate and not self._monitoring_active:
                self.start_monitoring()
            
            return True
            
        except Exception as e:
            print(f"Failed to launch {executable_path}: {e}")
            if entry_name in self.managed_processes:
                self.managed_processes[entry_name].state = ProcessState.ERROR
            return False
    
    def terminate_process(self, entry_name: str, force: bool = False) -> bool:
        """
        Terminate a specific managed process
        
        Args:
            entry_name: Entry to terminate
            force: Use force kill instead of graceful termination
        
        Returns:
            True if terminated successfully
        """
        if entry_name not in self.managed_processes:
            return False
        
        managed_proc = self.managed_processes[entry_name]
        
        if not managed_proc.pid or managed_proc.state != ProcessState.RUNNING:
            return False
        
        try:
            proc = psutil.Process(managed_proc.pid)
            
            if not proc.is_running():
                managed_proc.state = ProcessState.NOT_RUNNING
                return True
            
            print(f"Terminating {managed_proc.name} (PID: {managed_proc.pid})")
            
            if force:
                proc.kill()
            else:
                proc.terminate()
                
                # Wait for graceful shutdown
                try:
                    proc.wait(timeout=5)
                except psutil.TimeoutExpired:
                    print(f"Force killing {managed_proc.name}")
                    proc.kill()
            
            managed_proc.state = ProcessState.TERMINATED
            self._emit_event('process_terminated', entry_name, managed_proc)
            
            return True
            
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"Process {managed_proc.name} already terminated or access denied: {e}")
            managed_proc.state = ProcessState.NOT_RUNNING
            return True
        except Exception as e:
            print(f"Error terminating process {entry_name}: {e}")
            managed_proc.state = ProcessState.ERROR
            return False
    
    def terminate_msfs_dependent_processes(self):
        """Terminate all processes that depend on MSFS"""
        terminated = []
        
        for entry_name, managed_proc in self.managed_processes.items():
            if (managed_proc.msfs_dependent and 
                managed_proc.auto_terminate and 
                managed_proc.state == ProcessState.RUNNING):
                
                if self.terminate_process(entry_name):
                    terminated.append(entry_name)
        
        if terminated:
            print(f"Terminated MSFS-dependent processes: {', '.join(terminated)}")
        
        return terminated
    
    def is_process_running(self, entry_name: str) -> bool:
        """Check if a specific managed process is running"""
        if entry_name not in self.managed_processes:
            return False
        
        managed_proc = self.managed_processes[entry_name]
        
        if not managed_proc.pid or managed_proc.state != ProcessState.RUNNING:
            return False
        
        try:
            proc = psutil.Process(managed_proc.pid)
            is_running = proc.is_running()
            
            if not is_running:
                managed_proc.state = ProcessState.NOT_RUNNING
                self._emit_event('process_stopped', entry_name, managed_proc)
            
            return is_running
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            managed_proc.state = ProcessState.NOT_RUNNING
            return False
    
    def get_process_info(self, entry_name: str) -> Optional[Dict]:
        """Get information about a managed process"""
        if entry_name not in self.managed_processes:
            return None
        
        managed_proc = self.managed_processes[entry_name]
        
        info = {
            'name': managed_proc.name,
            'path': managed_proc.path,
            'args': managed_proc.args,
            'state': managed_proc.state.value,
            'auto_terminate': managed_proc.auto_terminate,
            'msfs_dependent': managed_proc.msfs_dependent,
            'pid': managed_proc.pid,
            'uptime': None
        }
        
        if managed_proc.started_time and managed_proc.state == ProcessState.RUNNING:
            info['uptime'] = time.time() - managed_proc.started_time
        
        return info
    
    def get_all_processes_info(self) -> Dict[str, Dict]:
        """Get information about all managed processes"""
        info = {}
        for entry_name in self.managed_processes:
            info[entry_name] = self.get_process_info(entry_name)
        return info
    
    def cleanup_process(self, entry_name: str):
        """Remove a process from management"""
        if entry_name in self.managed_processes:
            managed_proc = self.managed_processes[entry_name]
            if managed_proc.state == ProcessState.RUNNING:
                self.terminate_process(entry_name)
            del self.managed_processes[entry_name]
    
    def _monitor_loop(self):
        """Monitor MSFS and managed processes"""
        while not self.stop_monitoring.is_set():
            try:
                # Check MSFS status
                msfs_currently_running = self.is_msfs_running()
                
                # MSFS status changed
                if msfs_currently_running != self._msfs_was_running:
                    self._emit_event('msfs_status_changed', msfs_currently_running)
                    
                    # MSFS stopped - terminate dependent processes
                    if not msfs_currently_running and self._msfs_was_running:
                        print("MSFS stopped - terminating dependent processes")
                        self.terminate_msfs_dependent_processes()
                
                self._msfs_was_running = msfs_currently_running
                
                # Check status of all managed processes
                for entry_name in list(self.managed_processes.keys()):
                    self.is_process_running(entry_name)
                
                # Sleep before next check
                time.sleep(3)  # Check every 3 seconds
                
            except Exception as e:
                print(f"Error in monitor loop: {e}")
                time.sleep(5)
    
    def start_monitoring(self):
        """Start the monitoring thread"""
        if self._monitoring_active:
            return
        
        self._msfs_was_running = self.is_msfs_running()
        self.stop_monitoring.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        self._monitoring_active = True
        print("Process monitoring started")
    
    def stop_monitoring(self):
        """Stop monitoring and optionally terminate all managed processes"""
        if not self._monitoring_active:
            return
        
        print("Stopping process monitoring...")
        self.stop_monitoring.set()
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        self._monitoring_active = False
        print("Process monitoring stopped")
    
    def terminate_all_managed_processes(self):
        """Terminate all managed processes"""
        for entry_name in list(self.managed_processes.keys()):
            self.terminate_process(entry_name)
    
    def cleanup_all(self):
        """Stop monitoring and clean up all processes"""
        self.stop_monitoring()
        self.terminate_all_managed_processes()
        self.managed_processes.clear()

# Usage example:
if __name__ == "__main__":
    manager = PerEntryProcessManager()
    
    # Add event callbacks
    manager.add_callback('process_started', lambda name, proc: print(f"🟢 Started: {name}"))
    manager.add_callback('process_stopped', lambda name, proc: print(f"🔴 Stopped: {name}"))
    manager.add_callback('process_terminated', lambda name, proc: print(f"🛑 Terminated: {name}"))
    manager.add_callback('msfs_status_changed', lambda running: print(f"✈️ MSFS: {'Running' if running else 'Stopped'}"))
    
    try:
        # Example: Launch a process with auto-termination
        # manager.launch_process("FSUIPC", "C:\\FSUIPC7\\FSUIPC7.exe", auto_terminate=True)
        
        # Keep running
        while True:
            time.sleep(10)
            
            # Show status
            info = manager.get_all_processes_info()
            print(f"\nManaged processes: {len(info)}")
            for name, proc_info in info.items():
                if proc_info:
                    print(f"  {name}: {proc_info['state']} (PID: {proc_info['pid']})")
            
    except KeyboardInterrupt:
        print("\nShutting down...")
        manager.cleanup_all()