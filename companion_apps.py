"""
Companion applications: standalone tools that run alongside the simulator
but are NOT launched via exe.xml (Little Navmap, Navigraph Charts, ACARS
clients, and similar).

Unlike exe.xml entries, these:
  - Are launched directly by this app via subprocess.Popen, so they are
    never a child process of the simulator itself (MSFS never launches
    them - this app does).
  - Can optionally auto-start when the simulator starts and/or auto-stop
    when it stops, independently of each other (an ACARS client might
    want to keep running across multiple flights; Little Navmap might
    not need to).
  - Can always be started/stopped manually regardless of those two
    toggles - "Enabled" only governs eligibility for the automatic
    behavior, not manual control.

This module has no Qt dependency; controllers/companion_apps_controller.py
wraps it for GUI use and process-monitoring integration.
"""

import os
import json
import shlex
import subprocess
import tempfile
import hashlib

import settings
from logging_config import get_logger

logger = get_logger(__name__)


def companion_apps_file() -> str:
    return os.path.join(settings.APP_DIR, "companion_apps.json")


class CompanionAppEntry:
    def __init__(self, data: dict):
        self.name = data.get("name", "")
        self.path = data.get("path", "")
        self.args = data.get("args", "")
        self.enabled = data.get("enabled", True)
        self.start_with_sim = data.get("start_with_sim", False)
        self.stop_with_sim = data.get("stop_with_sim", False)
        # Seconds to wait after the simulator starts before auto-launching
        # this app. Only meaningful when start_with_sim is True. 0 = launch
        # immediately (the previous, only, behavior).
        self.start_delay_seconds = int(data.get("start_delay_seconds", 0) or 0)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "args": self.args,
            "enabled": self.enabled,
            "start_with_sim": self.start_with_sim,
            "stop_with_sim": self.stop_with_sim,
            "start_delay_seconds": self.start_delay_seconds,
        }

    def identity_key(self) -> str:
        """Stable identity for UI selection-preservation, matching the pattern AppEntry already uses."""
        return hashlib.md5(f"{self.name}|{self.path}".encode()).hexdigest()

    def monitor_key(self) -> str:
        """
        Namespaced, guaranteed-unique key for ProcessMonitor's flat
        addon_name -> path dict.

        Includes a short hash of the path, not just the name - two
        entries can never collide even if they share a name, INCLUDING
        the case where the name is blank. Using name alone previously
        meant every companion app with an empty name collapsed onto the
        exact same key ("companion:"), so starting any one of them made
        all the others falsely show as "Running" too, since they were
        all sharing one tracked process entry under the hood.
        """
        path_hash = hashlib.md5(self.path.encode()).hexdigest()[:8]
        label = self.name if self.name else "(unnamed)"
        return f"companion:{label}:{path_hash}"


class CompanionAppManager:
    def __init__(self):
        self.entries = []
        self.filepath = companion_apps_file()
        self.load()

    def load(self):
        self.entries = []
        if not os.path.exists(self.filepath):
            return
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            for entry_data in data.get("entries", []):
                self.entries.append(CompanionAppEntry(entry_data))
            logger.info(f"Loaded {len(self.entries)} companion app entries")
        except Exception as e:
            logger.error(f"Failed to load companion apps: {e}")
            self.entries = []

    def save(self):
        """Atomic write (temp file + os.replace), same pattern used for exe.xml and presets."""
        data = {"entries": [e.to_dict() for e in self.entries]}
        dir_name = os.path.dirname(self.filepath) or "."
        os.makedirs(dir_name, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(dir=dir_name, prefix=".tmp_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.filepath)
        except Exception as e:
            logger.error(f"Failed to save companion apps: {e}")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise

    def add_entry(self, name, path, args="", enabled=True, start_with_sim=False, stop_with_sim=False, start_delay_seconds=0) -> CompanionAppEntry:
        entry = CompanionAppEntry({
            "name": name, "path": path, "args": args, "enabled": enabled,
            "start_with_sim": start_with_sim, "stop_with_sim": stop_with_sim,
            "start_delay_seconds": start_delay_seconds,
        })
        self.entries.append(entry)
        self.save()
        return entry

    def modify_entry(self, index, name, path, args="", enabled=True, start_with_sim=False, stop_with_sim=False, start_delay_seconds=0):
        if index < 0 or index >= len(self.entries):
            return
        entry = self.entries[index]
        entry.name = name
        entry.path = path
        entry.args = args
        entry.enabled = enabled
        entry.start_with_sim = start_with_sim
        entry.stop_with_sim = stop_with_sim
        entry.start_delay_seconds = int(start_delay_seconds or 0)
        self.save()

    def remove_entry(self, index):
        if index < 0 or index >= len(self.entries):
            return
        del self.entries[index]
        self.save()

    def launch_entry(self, index):
        """
        Launch entries[index] directly via subprocess.Popen. This is a
        plain child process of this app (or the OS default for detached
        processes) - never routed through exe.xml, so the simulator is
        never involved in spawning it.
        """
        if index < 0 or index >= len(self.entries):
            return None
        entry = self.entries[index]
        if not os.path.exists(entry.path):
            raise FileNotFoundError(f"Executable not found: {entry.path}")

        args = shlex.split(entry.args, posix=False) if entry.args else []
        working_dir = os.path.dirname(entry.path) or None

        logger.info(f"Launching companion app: {entry.name} -> {entry.path} {args} (cwd={working_dir})")
        process = subprocess.Popen([entry.path] + args, cwd=working_dir)
        return process