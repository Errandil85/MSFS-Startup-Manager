import os
import json
import subprocess
import xml.etree.ElementTree as ET
from xml.dom import minidom


class AppEntry:
    def __init__(self, name, path, args="", enabled=True):
        self.name = name
        self.path = path
        self.args = args
        self.enabled = enabled

    def to_dict(self):
        return {
            "name": self.name,
            "path": self.path,
            "args": self.args,
            "enabled": self.enabled,
        }

    @staticmethod
    def from_dict(data):
        return AppEntry(
            data.get("name", ""),
            data.get("path", ""),
            data.get("args", ""),
            data.get("enabled", True),
        )


class ExeXmlManager:
    def __init__(self, version="MSFS2020"):
        self.tree = None
        self.root = None
        self.path = None
        self.entries = []
        self.version = version  # either "MSFS2020" or "MSFS2024"

        # Resolve preset base directory in %APPDATA%
        self.appdata_dir = os.path.join(os.getenv("APPDATA"), "MSFSExeXmlManager")
        self.presets_dir = os.path.join(self.appdata_dir, "presets", self.version)
        os.makedirs(self.presets_dir, exist_ok=True)

    # ---------------------------
    # Load / Save exe.xml
    # ---------------------------
    def load(self, path):
        self.path = path
        self.tree = ET.parse(path)
        self.root = self.tree.getroot()
        self._parse_entries()

    def save(self):
        if not self.tree or not self.path:
            return

        # Remove old Launch.Addon entries
        for addon in list(self.root.findall("Launch.Addon")):
            self.root.remove(addon)

        # Write current entries back
        for entry in self.entries:
            addon = ET.SubElement(self.root, "Launch.Addon")
            ET.SubElement(addon, "Name").text = entry.name
            ET.SubElement(addon, "Path").text = entry.path
            ET.SubElement(addon, "CommandLine").text = entry.args
            ET.SubElement(addon, "Disabled").text = "False" if entry.enabled else "True"

        # Pretty-print XML with minidom
        xml_str = ET.tostring(self.root, encoding="utf-8")
        parsed = minidom.parseString(xml_str)
        pretty_xml = parsed.toprettyxml(indent="  ")

        with open(self.path, "w", encoding="utf-8") as f:
            f.write(pretty_xml)

    def _parse_entries(self):
        self.entries = []
        for addon in self.root.findall("Launch.Addon"):
            name = addon.findtext("Name", "")
            path = addon.findtext("Path", "")
            args = addon.findtext("CommandLine", "")
            enabled = addon.findtext("Disabled", "False") == "False"
            self.entries.append(AppEntry(name, path, args, enabled))

    # ---------------------------
    # Entry Management
    # ---------------------------
    def add_entry(self, name, path, args="", enabled=True):
        self.entries.append(AppEntry(name, path, args, enabled))

    def remove_entry(self, index):
        if 0 <= index < len(self.entries):
            self.entries.pop(index)

    def modify_entry(self, index, name, path, args, enabled):
        if 0 <= index < len(self.entries):
            self.entries[index] = AppEntry(name, path, args, enabled)

    def set_enabled(self, index, enabled):
        if 0 <= index < len(self.entries):
            self.entries[index].enabled = enabled

    def execute_entry(self, index):
        if 0 <= index < len(self.entries):
            entry = self.entries[index]
            exe_path = os.path.expandvars(entry.path)
            if not os.path.exists(exe_path):
                raise FileNotFoundError(f"Executable not found: {exe_path}")
            subprocess.Popen([exe_path] + (entry.args.split() if entry.args else []))

    # ---------------------------
    # Presets
    # ---------------------------
    def get_presets(self):
        """Return list of available preset filenames for current version"""
        if not os.path.exists(self.presets_dir):
            return []
        return [f for f in os.listdir(self.presets_dir) if f.endswith(".json")]

    def save_preset(self, name):
        if not name.endswith(".json"):
            name += ".json"
        path = os.path.join(self.presets_dir, name)
        data = [e.to_dict() for e in self.entries]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return path

    def load_preset(self, name):
            if not name.endswith(".json"):
                name += ".json"
            path = os.path.join(self.presets_dir, name)
            if not os.path.exists(path):
                raise FileNotFoundError(f"Preset not found: {path}")
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # If preset was saved as a single dict instead of a list, wrap it
            if isinstance(data, dict):
                data = [data]

            # If preset is list of strings (bad save), try to parse each as JSON
            if all(isinstance(d, str) for d in data):
                new_data = []
                for d in data:
                    try:
                        new_data.append(json.loads(d))
                    except Exception:
                        continue
                data = new_data

            self.entries = [AppEntry.from_dict(d) for d in data if isinstance(d, dict)]
            return path

    def set_version(self, version):
        """Switch version between MSFS2020 and MSFS2024"""
        self.version = version
        self.presets_dir = os.path.join(self.appdata_dir, "presets", self.version)
        os.makedirs(self.presets_dir, exist_ok=True)
