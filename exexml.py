import os
import subprocess
import xml.etree.ElementTree as ET

class AppEntry:
    def __init__(self, elem):
        self.elem = elem
        self.name = elem.findtext("Name", "").strip()
        self.path = elem.findtext("Path", "").strip()
        self.args = elem.findtext("CommandLine", elem.findtext("Args", "")).strip()
        disabled = elem.findtext("Disabled", "False")
        self.enabled = disabled.lower() not in ["true", "1", "yes"]

class ExeXmlManager:
    def __init__(self):
        self.tree = None
        self.root = None
        self.entries = []
        self.filepath = None

    def load(self, filepath):
        self.filepath = filepath
        self.tree = ET.parse(filepath)
        self.root = self.tree.getroot()
        self.parse_entries()

    def parse_entries(self):
        self.entries = []
        for elem in self.root.findall(".//Launch.Addon"):
            self.entries.append(AppEntry(elem))

    def save(self):
        if self.tree is not None and self.filepath:
            self.tree.write(self.filepath, encoding="utf-8", xml_declaration=True)

    def add_entry(self, name, path, args, enabled=True):
        addon = ET.Element("Launch.Addon")
        ET.SubElement(addon, "Name").text = name
        ET.SubElement(addon, "Path").text = path
        ET.SubElement(addon, "CommandLine").text = args
        ET.SubElement(addon, "Disabled").text = "False" if enabled else "True"
        self.root.append(addon)
        self.parse_entries()

    def remove_entry(self, index):
        if index < 0 or index >= len(self.entries):
            return
        self.root.remove(self.entries[index].elem)
        self.parse_entries()

    def execute_entry(self, index):
        if index < 0 or index >= len(self.entries):
            return
        entry = self.entries[index]
        if not os.path.exists(entry.path):
            raise FileNotFoundError(f"Executable not found: {entry.path}")
        subprocess.Popen([entry.path] + entry.args.split())

    def set_enabled(self, index, enabled: bool):
        if index < 0 or index >= len(self.entries):
            return
        entry = self.entries[index]
        disabled_elem = entry.elem.find("Disabled")
        if disabled_elem is None:
            disabled_elem = ET.SubElement(entry.elem, "Disabled")
        disabled_elem.text = "False" if enabled else "True"
        self.parse_entries()
    
    def modify_entry(self, index, name, path, args, enabled=True):
        if index < 0 or index >= len(self.entries):
            return
        entry = self.entries[index]
        entry.elem.find("Name").text = name
        entry.elem.find("Path").text = path
        cmd_elem = entry.elem.find("CommandLine")
        if cmd_elem is None:
            cmd_elem = entry.elem.find("Args")
        if cmd_elem is None:
            cmd_elem = ET.SubElement(entry.elem, "CommandLine")
        cmd_elem.text = args
        disabled_elem = entry.elem.find("Disabled")
        if disabled_elem is None:
            disabled_elem = ET.SubElement(entry.elem, "Disabled")
        disabled_elem.text = "False" if enabled else "True"
        self.parse_entries()
