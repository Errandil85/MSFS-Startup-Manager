import os
import subprocess
import xml.etree.ElementTree as ET
from xml.dom import minidom
import json

class AppEntry:
    def __init__(self, elem):
        self.elem = elem
        self.name = elem.findtext("Name", "").strip()
        self.path = elem.findtext("Path", "").strip()
        
        # Handle both self-closing CommandLine tags and regular ones
        cmd_elem = elem.find("CommandLine")
        if cmd_elem is not None:
            # Check if it's a self-closing tag or has text content
            self.args = cmd_elem.text if cmd_elem.text else ""
        else:
            # Fallback to Args if CommandLine doesn't exist
            self.args = elem.findtext("Args", "")
        
        self.args = self.args.strip()
        
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
        
        # Debug: Print XML structure
        print(f"Root tag: {self.root.tag}")
        print("All child elements:")
        for child in self.root:
            print(f"  - {child.tag}")
            for grandchild in child:
                print(f"    - {grandchild.tag}")
        
        self.parse_entries()

    def load_preset(self, preset_path):
        """Load a preset file (JSON format) and apply it to current exe.xml"""
        if not os.path.exists(preset_path):
            raise FileNotFoundError(f"Preset file not found: {preset_path}")
        
        try:
            with open(preset_path, 'r', encoding='utf-8') as f:
                preset_data = json.load(f)
            
            # Clear existing entries
            if self.root is not None:
                # Remove all Launch.Addon elements
                for addon in self.root.findall(".//Launch.Addon"):
                    self.root.remove(addon)
            
            # Add entries from preset
            for entry_data in preset_data.get("entries", []):
                self.add_entry(
                    entry_data.get("name", ""),
                    entry_data.get("path", ""),
                    entry_data.get("args", ""),
                    entry_data.get("enabled", True)
                )
            
            print(f"Loaded preset with {len(preset_data.get('entries', []))} entries")
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid preset file format: {e}")

    def save_preset(self, preset_path):
        """Save current entries as a preset file"""
        preset_data = {
            "name": os.path.basename(preset_path).replace(".json", ""),
            "entries": []
        }
        
        for entry in self.entries:
            preset_data["entries"].append({
                "name": entry.name,
                "path": entry.path,
                "args": entry.args,
                "enabled": entry.enabled
            })
        
        with open(preset_path, 'w', encoding='utf-8') as f:
            json.dump(preset_data, f, indent=2)

    def parse_entries(self):
        self.entries = []
        
        # MSFS exe.xml typically has this structure:
        # <SimBase.Document ...>
        #   <Launch.Addon>
        #     <Name>...</Name>
        #     <Path>...</Path>
        #     <CommandLine>...</CommandLine>
        #     <Disabled>...</Disabled>
        #   </Launch.Addon>
        # </SimBase.Document>
        
        # Try different possible tag patterns for MSFS exe.xml
        possible_tags = [
            "Launch.Addon",           # Direct children
            ".//Launch.Addon",        # Anywhere in document
            ".//Addon",               # Alternative naming
            "./Launch.Addon",         # Direct children only
        ]
        
        for tag_pattern in possible_tags:
            elements = self.root.findall(tag_pattern)
            print(f"Found {len(elements)} elements with pattern '{tag_pattern}'")
            if elements:
                for elem in elements:
                    print(f"  Element: {elem.tag}")
                    print(f"    Name: {elem.findtext('Name', 'N/A')}")
                    print(f"    Path: {elem.findtext('Path', 'N/A')}")
                    print(f"    CommandLine: {elem.findtext('CommandLine', 'N/A')}")
                    print(f"    Args: {elem.findtext('Args', 'N/A')}")
                    self.entries.append(AppEntry(elem))
                break  # Use the first pattern that finds elements
        
        print(f"Total entries loaded: {len(self.entries)}")

    def save(self):
        if self.tree is not None and self.filepath:
            # Format the XML with proper indentation
            self._indent_xml(self.root)
            self.tree.write(self.filepath, encoding="utf-8", xml_declaration=True)
    
    def _indent_xml(self, elem, level=0):
        """Add proper indentation to XML elements"""
        indent = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
            for child in elem:
                self._indent_xml(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = indent
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent

    def add_entry(self, name, path, args, enabled=True):
        # Try to find the correct parent element or create the structure
        launch_parent = self.root.find(".//SimBase.Document")
        if launch_parent is None:
            launch_parent = self.root
            
        addon = ET.Element("Launch.Addon")
        ET.SubElement(addon, "Name").text = name
        ET.SubElement(addon, "Path").text = path
        ET.SubElement(addon, "CommandLine").text = args
        ET.SubElement(addon, "Disabled").text = "False" if enabled else "True"
        launch_parent.append(addon)
        self.parse_entries()

    def remove_entry(self, index):
        if index < 0 or index >= len(self.entries):
            return
        parent = self.entries[index].elem.getparent()
        if parent is not None:
            parent.remove(self.entries[index].elem)
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