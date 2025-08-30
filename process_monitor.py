import psutil
import threading
import time
import subprocess
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

class MonitorState(Enum):
    STOPPED = "stopped"
    WAITING_FOR_MSFS = "waiting_for_msfs"
    MONITORING = "monitoring"
    CLEANING_UP = "cleaning_up"

@dataclass
class ProcessInfo:
    pid: int
    name: str
    path: str
    started_time: float

class MSFSProcessMonitor:
    """
    Monitor MSFS processes and manage addon processes lifecycle
    """
    
    def __init__(self):
        self.state = MonitorState.STOPPED
        self.msfs_processes = ["FlightSimulator.exe", "Microsoft.FlightSimulator.exe"]
        self.launched_processes: Dict[int, ProcessInfo] = {}
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_monitoring = threading.Event()
        self.callbacks: Dict[str, List[Callable]] = {
            'msfs_started': [],
            'msfs_stopped': [],
            'addon_terminated': [],
            'state_changed': []
        }
    
    def add_callback(self, event_type: str, callback: Callable):
        """Add callback for events: msfs_started, msfs_stopped, addon_terminated, state_changed"""
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
    
    def _emit_event(self, event_type: str, *args, **kwargs):
        """Emit event to all registered callbacks"""
        for callback in self.callbacks.get(event_type, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                print(f"Callback error in {event_type}: {e}")
    
    def _set_state(self, new_state: MonitorState):
        """Set monitor state and emit state change event"""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            self._emit_event('state_changed', old_state, new_state)
    
    def is_msfs_running(self) -> bool:
        """Check if any MSFS process is currently running"""
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] in self.msfs_processes:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False
    
    def get_msfs_pids(self) -> List[int]:
        """Get all MSFS process IDs"""
        pids = []
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] in self.msfs_processes:
                    pids.append(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return pids
    
    def launch_and_track_process(self, executable_path: str, args: str = "") -> Optional[int]:
        """
        Launch a process and add it to tracking
        Returns the PID if successful, None otherwise
        """
        try:
            # Parse arguments
            cmd_args = args.split() if args else []
            full_command = [executable_path] + cmd_args
            
            # Launch process
            proc = subprocess.Popen(full_command)
            
            # Track the process
            process_info = ProcessInfo(
                pid=proc.pid,
                name=os.path.basename(executable_path),
                path=executable_path,
                started_time=time.time()
            )
            
            self.launched_processes[proc.pid] = process_info
            print(f"Launched and tracking: {process_info.name} (PID: {proc.pid})")
            
            return proc.pid
            
        except Exception as e:
            print(f"Failed to launch {executable_path}: {e}")
            return None
    
    def terminate_tracked_processes(self):
        """Terminate all tracked addon processes"""
        if not self.launched_processes:
            return
        
        self._set_state(MonitorState.CLEANING_UP)
        terminated_count = 0
        
        for pid, process_info in list(self.launched_processes.items()):
            try:
                proc = psutil.Process(pid)
                
                # Check if process is still running
                if proc.is_running():
                    print(f"Terminating {process_info.name} (PID: {pid})")
                    
                    # Try graceful termination first
                    proc.terminate()
                    
                    # Wait a bit for graceful shutdown
                    try:
                        proc.wait(timeout=5)
                    except psutil.TimeoutExpired:
                        # Force kill if it doesn't terminate gracefully
                        print(f"Force killing {process_info.name} (PID: {pid})")
                        proc.kill()
                    
                    self._emit_event('addon_terminated', process_info)
                    terminated_count += 1
                
                # Remove from tracking
                del self.launched_processes[pid]
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Process already gone, just remove from tracking
                del self.launched_processes[pid]
            except Exception as e:
                print(f"Error terminating process {pid}: {e}")
        
        print(f"Terminated {terminated_count} addon processes")
    
    def _monitor_loop(self):
        """Main monitoring loop (runs in separate thread)"""
        msfs_was_running = False
        
        while not self.stop_monitoring.is_set():
            try:
                msfs_currently_running = self.is_msfs_running()
                
                # MSFS started
                if msfs_currently_running and not msfs_was_running:
                    print("MSFS started - beginning monitoring")
                    self._set_state(MonitorState.MONITORING)
                    self._emit_event('msfs_started')
                
                # MSFS stopped
                elif not msfs_currently_running and msfs_was_running:
                    print("MSFS stopped - terminating addon processes")
                    self._emit_event('msfs_stopped')
                    self.terminate_tracked_processes()
                    
                    if self.stop_monitoring.is_set():
                        break
                    
                    print("Waiting for MSFS to start again...")
                    self._set_state(MonitorState.WAITING_FOR_MSFS)
                
                # Update state
                elif not msfs_currently_running and self.state != MonitorState.WAITING_FOR_MSFS:
                    self._set_state(MonitorState.WAITING_FOR_MSFS)
                
                msfs_was_running = msfs_currently_running
                
                # Clean up dead processes from tracking
                self._cleanup_dead_processes()
                
                # Wait before next check
                time.sleep(2)  # Check every 2 seconds
                
            except Exception as e:
                print(f"Error in monitor loop: {e}")
                time.sleep(5)  # Wait longer on error
        
        # Final cleanup when stopping
        if self.launched_processes:
            print("Monitor stopping - final cleanup of tracked processes")
            self.terminate_tracked_processes()
        
        self._set_state(MonitorState.STOPPED)
    
    def _cleanup_dead_processes(self):
        """Remove dead processes from tracking"""
        dead_pids = []
        
        for pid in self.launched_processes:
            try:
                proc = psutil.Process(pid)
                if not proc.is_running():
                    dead_pids.append(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                dead_pids.append(pid)
        
        for pid in dead_pids:
            process_info = self.launched_processes.pop(pid, None)
            if process_info:
                print(f"Process {process_info.name} (PID: {pid}) ended naturally")
    
    def start_monitoring(self):
        """Start the monitoring service"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            print("Monitor already running")
            return
        
        print("Starting MSFS process monitor...")
        self.stop_monitoring.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        # Set initial state
        if self.is_msfs_running():
            self._set_state(MonitorState.MONITORING)
        else:
            self._set_state(MonitorState.WAITING_FOR_MSFS)
    
    def stop_monitoring(self):
        """Stop the monitoring service"""
        if not self.monitor_thread or not self.monitor_thread.is_alive():
            print("Monitor not running")
            return
        
        print("Stopping MSFS process monitor...")
        self.stop_monitoring.set()
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
        
        # Final cleanup
        if self.launched_processes:
            self.terminate_tracked_processes()
        
        self._set_state(MonitorState.STOPPED)
    
    def get_status(self) -> Dict:
        """Get current monitor status"""
        return {
            'state': self.state.value,
            'msfs_running': self.is_msfs_running(),
            'msfs_pids': self.get_msfs_pids(),
            'tracked_processes': len(self.launched_processes),
            'tracked_process_list': [
                {
                    'pid': pid,
                    'name': info.name,
                    'uptime': time.time() - info.started_time
                }
                for pid, info in self.launched_processes.items()
            ]
        }

# Usage example:
if __name__ == "__main__":
    import os
    
    monitor = MSFSProcessMonitor()
    
    # Add event callbacks
    monitor.add_callback('msfs_started', lambda: print("🟢 MSFS Started!"))
    monitor.add_callback('msfs_stopped', lambda: print("🔴 MSFS Stopped!"))
    monitor.add_callback('addon_terminated', lambda info: print(f"🛑 Terminated: {info.name}"))
    monitor.add_callback('state_changed', lambda old, new: print(f"📊 State: {old.value} -> {new.value}"))
    
    # Start monitoring
    monitor.start_monitoring()
    
    try:
        # Keep running and show status
        while True:
            status = monitor.get_status()
            print(f"\nStatus: {status['state']} | MSFS: {status['msfs_running']} | Tracked: {status['tracked_processes']}")
            
            # Example: launch a process when MSFS is detected
            if status['msfs_running'] and status['tracked_processes'] == 0:
                # This would be your addon launch
                pass
            
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\nStopping monitor...")
        monitor.stop_monitoring()