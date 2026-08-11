import os
import subprocess
import shlex
import tempfile
import xml.etree.ElementTree as ET
from xml.dom import minidom
import json
import hashlib

from logging_config import get_logger

logger = get_logger(__name__)


class AppEntry:
    def __init__(self, elem, auto_close_settings=None):
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
        
        # Auto-close functionality (stored separately, NOT in XML)
        entry_id = self._generate_entry_id()
        if auto_close_settings and entry_id in auto_close_settings:
            self.auto_close = auto_close_settings[entry_id]
        else:
            self.auto_close = False
    
    def _generate_entry_id(self):
        """Generate a unique ID for this entry based on name and path"""
        unique_string = f"{self.name}|{self.path}"
        return hashlib.md5(unique_string.encode()).hexdigest()


class ExeXmlManager:
    def __init__(self):
        self.tree = None
        self.root = None
        self.entries = []
        self.filepath = None
        self.auto_close_settings = {}  # Store auto-close settings separately
        self.auto_close_file = None

    def load(self, filepath):
        self.filepath = filepath

        # Comments in exe.xml (e.g. left behind by an addon installer, or
        # hand-added by the user) were previously dropped silently on the
        # very first save, since ET.parse()'s default parser discards
        # them. This comment-preserving parser (stdlib, Python 3.8+)
        # keeps them as Comment nodes in the tree instead, so they
        # round-trip through load -> save intact.
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        self.tree = ET.parse(filepath, parser=parser)
        self.root = self.tree.getroot()
        
        # Load auto-close settings from separate file
        self._load_auto_close_settings()
        
        self.parse_entries()
        # Prune auto-close settings for entries that no longer exist,
        # so the sidecar file doesn't grow forever over months of edits.
        self._prune_auto_close_settings()

    def _load_auto_close_settings(self):
        """Load auto-close settings from a separate JSON file"""
        if not self.filepath:
            return
            
        # Create auto-close settings file path based on exe.xml location
        base_name = os.path.splitext(os.path.basename(self.filepath))[0]
        dir_name = os.path.dirname(self.filepath)
        self.auto_close_file = os.path.join(dir_name, f"{base_name}_autoclose.json")
        
        try:
            if os.path.exists(self.auto_close_file):
                with open(self.auto_close_file, 'r', encoding='utf-8') as f:
                    self.auto_close_settings = json.load(f)
            else:
                self.auto_close_settings = {}
        except Exception as e:
            logger.error(f"Error loading auto-close settings: {e}")
            self.auto_close_settings = {}

    def _save_auto_close_settings(self):
        """Save auto-close settings to separate JSON file (atomic)"""
        if not self.auto_close_file:
            return
        self._atomic_write_text(
            self.auto_close_file,
            json.dumps(self.auto_close_settings, indent=2),
        )

    def _prune_auto_close_settings(self):
        """Remove auto-close entries whose (name|path) no longer matches any entry."""
        if not self.auto_close_settings:
            return
        live_ids = {e._generate_entry_id() for e in self.entries}
        stale_ids = [eid for eid in self.auto_close_settings if eid not in live_ids]
        if stale_ids:
            for eid in stale_ids:
                del self.auto_close_settings[eid]
            logger.info(f"Pruned {len(stale_ids)} stale auto-close setting(s)")
            self._save_auto_close_settings()

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
                    entry_data.get("enabled", True),
                    entry_data.get("auto_close", False)
                )
            
            logger.info(f"Loaded preset with {len(preset_data.get('entries', []))} entries")
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid preset file format: {e}")

    def save_preset(self, preset_path):
        """Save current entries as a preset file (atomic)"""
        preset_data = {
            "name": os.path.basename(preset_path).replace(".json", ""),
            "entries": []
        }
        
        for entry in self.entries:
            preset_data["entries"].append({
                "name": entry.name,
                "path": entry.path,
                "args": entry.args,
                "enabled": entry.enabled,
                "auto_close": entry.auto_close
            })
        
        self._atomic_write_text(preset_path, json.dumps(preset_data, indent=2))

    def parse_entries(self):
        self.entries = []
        
        possible_tags = [
            "Launch.Addon",           # Direct children
            ".//Launch.Addon",        # Anywhere in document
            ".//Addon",               # Alternative naming
            "./Launch.Addon",         # Direct children only
        ]
        
        for tag_pattern in possible_tags:
            elements = self.root.findall(tag_pattern)
            if elements:
                for elem in elements:
                    self.entries.append(AppEntry(elem, self.auto_close_settings))
                break  # Use the first pattern that finds elements

        logger.info(f"Total entries loaded: {len(self.entries)}")

    # -------------------------
    # Atomic file writing helpers
    # -------------------------
    def _atomic_write_bytes(self, path, write_func):
        """
        Write to a temp file in the same directory, fsync, then atomically
        replace the target file. write_func(file_obj) does the actual writing.
        This avoids ever leaving a truncated/corrupt file behind if the
        process dies mid-write (crash, AV lock, power loss, etc).
        """
        dir_name = os.path.dirname(os.path.abspath(path)) or "."
        os.makedirs(dir_name, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(dir=dir_name, prefix=".tmp_", suffix=".xml")
        try:
            with os.fdopen(fd, "wb") as f:
                write_func(f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)  # atomic on Windows and POSIX
        except Exception as e:
            logger.error(f"Atomic write to {path} failed: {e}")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise

    def _atomic_write_text(self, path, text, encoding="utf-8"):
        def _write(f):
            f.write(text.encode(encoding))
        self._atomic_write_bytes(path, _write)

    def _pretty_print_xml(self, root):
        """
        Reformat the tree in place so it's human-readable, not a single line.
        Prefers the standard library's ET.indent (Python 3.9+, well tested);
        falls back to a manual indenter on older Pythons.
        """
        if hasattr(ET, "indent"):
            ET.indent(root, space="  ")
        else:
            self._manual_indent_xml(root)

    def _manual_indent_xml(self, elem, level=0):
        """Fallback pretty-printer for Python < 3.9."""
        indent = "\n" + level * "  "
        children = list(elem)
        if children:
            if not elem.text or not elem.text.strip():
                elem.text = indent + "  "
            for child in children:
                self._manual_indent_xml(child, level + 1)
            last = children[-1]
            if not last.tail or not last.tail.strip():
                last.tail = indent
            for child in children[:-1]:
                if not child.tail or not child.tail.strip():
                    child.tail = indent + "  "
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent

    def save(self):
        if self.tree is not None and self.filepath:
            # Format the XML with proper indentation (never single-line)
            self._pretty_print_xml(self.root)

            def _write(f):
                f.write(b"<?xml version='1.0' encoding='utf-8'?>\n")
                self.tree.write(f, encoding="utf-8", xml_declaration=False)

            self._atomic_write_bytes(self.filepath, _write)

            # Save auto-close settings separately (also atomic)
            self._save_auto_close_settings()

    def add_entry(self, name, path, args, enabled=True, auto_close=False):
        launch_parent = self.root.find(".//SimBase.Document")
        if launch_parent is None:
            launch_parent = self.root
            
        addon = ET.Element("Launch.Addon")
        ET.SubElement(addon, "Name").text = name
        ET.SubElement(addon, "Path").text = path
        ET.SubElement(addon, "CommandLine").text = args
        ET.SubElement(addon, "Disabled").text = "False" if enabled else "True"
        launch_parent.append(addon)
        
        entry_id = hashlib.md5(f"{name}|{path}".encode()).hexdigest()
        self.auto_close_settings[entry_id] = auto_close
        
        self.parse_entries()

    def remove_entry(self, index):
        entry = self.entries[index]
        
        entry_id = entry._generate_entry_id()
        if entry_id in self.auto_close_settings:
            del self.auto_close_settings[entry_id]
        
        self.root.remove(entry.elem)
        del self.entries[index]
        self.save()

    def execute_entry(self, index):
        if index < 0 or index >= len(self.entries):
            return None
        entry = self.entries[index]
        if not os.path.exists(entry.path):
            raise FileNotFoundError(f"Executable not found: {entry.path}")
        
        # shlex.split respects quoted arguments (e.g. paths with spaces),
        # unlike a naive whitespace .split().
        args = shlex.split(entry.args, posix=False) if entry.args else []
        working_dir = os.path.dirname(entry.path) or None
        
        logger.info(f"Launching entry: {entry.name} -> {entry.path} {args} (cwd={working_dir})")
        process = subprocess.Popen([entry.path] + args, cwd=working_dir)
        return process

    def set_enabled(self, index, enabled: bool):
        if index < 0 or index >= len(self.entries):
            return
        entry = self.entries[index]
        disabled_elem = entry.elem.find("Disabled")
        if disabled_elem is None:
            disabled_elem = ET.SubElement(entry.elem, "Disabled")
        disabled_elem.text = "False" if enabled else "True"
        self.parse_entries()
    
    def set_auto_close(self, index, auto_close: bool):
        if index < 0 or index >= len(self.entries):
            return
        
        entry = self.entries[index]
        entry_id = entry._generate_entry_id()
        self.auto_close_settings[entry_id] = auto_close
        entry.auto_close = auto_close
    
    def modify_entry(self, index, name, path, args, enabled=True, auto_close=False):
        if index < 0 or index >= len(self.entries):
            return
        
        entry = self.entries[index]
        old_entry_id = entry._generate_entry_id()
        
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
        
        new_entry_id = hashlib.md5(f"{name}|{path}".encode()).hexdigest()
        
        if old_entry_id != new_entry_id and old_entry_id in self.auto_close_settings:
            del self.auto_close_settings[old_entry_id]
        
        self.auto_close_settings[new_entry_id] = auto_close
        
        self.parse_entries()