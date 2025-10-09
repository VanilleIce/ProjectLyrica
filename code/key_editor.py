# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import customtkinter as ctk
from tkinter import messagebox
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple, Callable

from language_manager import LanguageManager
from resource_loader import resource_path

logger = logging.getLogger("ProjectLyrica.KeyEditor")

class KeyEditorWindow:
    _open_windows = []

    def __init__(self, parent, callback):
        if KeyEditorWindow._open_windows:
            KeyEditorWindow._open_windows[0].window.focus()
            return
            
        self.parent = parent
        self.callback = callback
        self.window = ctk.CTkToplevel(parent)
        self.window.title(LanguageManager.get('key_editor_title'))
        self.window.geometry("620x620")
        self.window.resizable(False, False)
        self.window.iconbitmap(resource_path("resources/icons/icon.ico"))
        
        self.window.transient(parent)
        self.window.grab_set()
        
        KeyEditorWindow._open_windows.append(self)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Load mappings
        self.default_mapping = self._load_default_mapping()
        self.current_mapping = self._load_current_mapping()
        self.original_mapping = self.current_mapping.copy()

        self.has_changes = False
        self._calculate_initial_changes()
        
        self.currently_editing = None
        self._create_ui()
        self._update_change_count()

    def _calculate_initial_changes(self):
        """Calculates initial changes during loading’"""
        for key_id in self.current_mapping:
            if self.current_mapping[key_id] != self.original_mapping.get(key_id, ""):
                self.has_changes = True
                break

    def _load_default_mapping(self) -> Dict[str, str]:
        """Load the default key mapping based on the current layout setting"""
        try:
            from config_manager import ConfigManager
            config = ConfigManager.get_config()
            layout = config.get("ui_settings", {}).get("keyboard_layout", "QWERTY")
            
            from language_manager import KeyboardLayoutManager
            return KeyboardLayoutManager.load_layout_silently(layout)
        except Exception as e:
            logger.error(f"Error loading default mapping: {e}")
            return {}

    def _load_current_mapping(self) -> Dict[str, str]:
        """Load custom mapping or fallback to default basic layout"""
        try:
            custom_file = Path(resource_path('resources/layouts/CUSTOM.xml'))
            if custom_file.exists():
                tree = ET.parse(custom_file)
                mapping = {}
                
                root = tree.getroot()
                base_layout = root.get('base_layout', 'QWERTY')
                self.base_layout = base_layout
                
                for key in tree.findall('key'):
                    key_id = key.get('id')
                    key_text = key.text.strip() if key.text else ""
                    if key_id:
                        mapping[key_id] = key_text
                        
                logger.info(f"Loaded custom mapping with {len(mapping)} keys (base: {base_layout})")
                return mapping
        except Exception as e:
            logger.error(f"Error loading custom mapping: {e}")
        
        # Fallback to default
        self.base_layout = "QWERTY"
        return self._load_default_mapping()

    def _create_ui(self):
        """Create the user interface"""
        main_frame = ctk.CTkFrame(self.window)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Title and Info
        title_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(
            title_frame,
            text=LanguageManager.get('key_editor_title'),
            font=("Arial", 18, "bold")
        ).pack(side="left")
        
        self.change_label = ctk.CTkLabel(
            title_frame,
            text="",
            font=("Arial", 11),
            text_color="gray60"
        )
        self.change_label.pack(side="right")
        
        # Instructions
        ctk.CTkLabel(
            main_frame,
            text=LanguageManager.get('key_editor_instructions'),
            font=("Arial", 11),
            text_color="gray70",
            wraplength=580
        ).pack(fill="x", pady=(0, 15))
        
        # Current Key Display
        self._create_current_key_display(main_frame)
        
        # Keyboard Layout
        self._create_keyboard_layout(main_frame)
        
        # Buttons
        self._create_buttons(main_frame)
        
        # Setup key bindings
        self._setup_key_bindings()

    def _create_current_key_display(self, parent):
        """Create display for currently edited key"""
        self.current_key_frame = ctk.CTkFrame(parent, height=60)
        self.current_key_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(
            self.current_key_frame,
            text=LanguageManager.get('key_editor_current_key'),
            font=("Arial", 12, "bold")
        ).pack(pady=(8, 0))
        
        self.current_key_label = ctk.CTkLabel(
            self.current_key_frame,
            text=LanguageManager.get('key_editor_no_selection'),
            font=("Arial", 14),
            text_color="gray60"
        )
        self.current_key_label.pack(pady=5)
        
        self.current_key_value = ctk.CTkLabel(
            self.current_key_frame,
            text="",
            font=("Arial", 16, "bold"),
            text_color="#2E86AB"
        )
        self.current_key_value.pack(pady=5)

    def _create_keyboard_layout(self, parent):
        """Create the visual keyboard layout"""
        keyboard_frame = ctk.CTkFrame(parent)
        keyboard_frame.pack(fill="both", expand=True, pady=(0, 15))

        self.key_rows = [
            ['Key0', 'Key1', 'Key2', 'Key3', 'Key4'],
            ['Key5', 'Key6', 'Key7', 'Key8', 'Key9'], 
            ['Key10', 'Key11', 'Key12', 'Key13', 'Key14']
        ]
        
        self.key_buttons = {}
        
        for row_index, row_keys in enumerate(self.key_rows):
            row_frame = ctk.CTkFrame(keyboard_frame, fg_color="transparent")
            row_frame.pack(pady=8)
            
            for key_id in row_keys:
                self._create_key_button(row_frame, key_id)

    def _create_key_button(self, parent, key_id: str):
        """Create a key button"""
        default_value = self.default_mapping.get(key_id, "")
        current_value = self.current_mapping.get(key_id, default_value)
        is_custom = current_value != default_value
        
        btn = ctk.CTkButton(
            parent,
            text=current_value if current_value else "?",
            width=80,
            height=80,
            font=("Arial", 16, "bold"),
            fg_color="#2E86AB" if is_custom else "#3A3A3A",
            hover_color="#1B5E7B" if is_custom else "#4A4A4A",
            command=lambda k=key_id: self._start_key_edit(k)
        )
        btn.pack(side="left", padx=6)
        
        self.key_buttons[key_id] = {'button': btn}

    def _start_key_edit(self, key_id: str):
        """Start editing a button"""
        self.currently_editing = key_id
        default_value = self.default_mapping.get(key_id, "")
        current_value = self.current_mapping.get(key_id, default_value)
        
        self.current_key_label.configure(text=f"{key_id}:")
        
        if current_value:
            self.current_key_value.configure(
                text=f"'{current_value}'",
                text_color="#2E86AB"
            )
        else:
            self.current_key_value.configure(
                text=LanguageManager.get('key_editor_press_key'),
                text_color="orange"
            )
        
        # Highlight selected button
        for k, btn_data in self.key_buttons.items():
            is_selected = (k == key_id)
            is_custom = self.current_mapping.get(k, "") != self.default_mapping.get(k, "")
            
            if is_selected:
                btn_data['button'].configure(
                    fg_color="#F24236",
                    hover_color="#D32F2F"
                )
            else:
                btn_data['button'].configure(
                    fg_color="#2E86AB" if is_custom else "#3A3A3A",
                    hover_color="#1B5E7B" if is_custom else "#4A4A4A"
                )

    def _process_key_input(self, key_value: str):
        """Process the key input change detection"""
        if not self.currently_editing:
            return
            
        key_id = self.currently_editing
        
        original_value = self.original_mapping.get(key_id, "")
        if key_value != original_value:
            self.has_changes = True
        
        self.current_mapping[key_id] = key_value
        self._update_key_button(key_id)
        
        display_text = f"'{key_value}'" if key_value else LanguageManager.get('key_editor_empty')
        text_color = "#2E86AB" if key_value else "red"
        self.current_key_value.configure(text=display_text, text_color=text_color)
        
        self._update_change_count()

    def _setup_key_bindings(self):
        """Set up keyboard bindings for key input"""
        self.window.bind('<KeyPress>', self._on_any_key_press)
        self.window.bind('<Escape>', lambda e: self._cancel_edit())
        self.window.bind('<BackSpace>', lambda e: self._process_key_input(""))
        self.window.focus_set()

    def _on_any_key_press(self, event):
        """Intercepts all key presses"""
        if not self.currently_editing:
            return
            
        modifier_keys = ['Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R', 'Caps_Lock', 'Num_Lock', 'Scroll_Lock']
        if event.keysym in modifier_keys:
            return
        
        if event.keysym in ['Escape', 'BackSpace']:
            return
        
        special_keys = {
            'space': " ",
            'Return': "\n",
            'Tab': "\t"
        }
        
        if event.keysym in special_keys:
            self._process_key_input(special_keys[event.keysym])
            return
        
        if event.char and event.char != '':
            self._process_key_input(event.char)
        elif len(event.keysym) == 1:
            self._process_key_input(event.keysym)

    def _cancel_edit(self):
        """Cancel editing"""
        self.currently_editing = None
        self.current_key_label.configure(text=LanguageManager.get('key_editor_no_selection'))
        self.current_key_value.configure(text="")
        
        # Reset button colors
        for key_id, btn_data in self.key_buttons.items():
            is_custom = self.current_mapping.get(key_id, "") != self.default_mapping.get(key_id, "")
            btn_data['button'].configure(
                fg_color="#2E86AB" if is_custom else "#3A3A3A",
                hover_color="#1B5E7B" if is_custom else "#4A4A4A"
            )

    def _update_key_button(self, key_id: str):
        """Update a key button"""
        current_value = self.current_mapping.get(key_id, "")
        default_value = self.default_mapping.get(key_id, "")
        is_custom = current_value != default_value
        is_selected = (key_id == self.currently_editing)
        
        btn_data = self.key_buttons[key_id]
        display_text = current_value if current_value else "?"
        
        if is_selected:
            fg_color = "#F24236"
            hover_color = "#D32F2F"
        else:
            fg_color = "#2E86AB" if is_custom else "#3A3A3A"
            hover_color = "#1B5E7B" if is_custom else "#4A4A4A"
        
        btn_data['button'].configure(
            text=display_text,
            fg_color=fg_color,
            hover_color=hover_color
        )

    def _update_change_count(self):
        """Update the change count"""
        changed_keys = sum(
            1 for key_id in self.current_mapping 
            if self.current_mapping[key_id] != self.default_mapping.get(key_id, "")
        )
        
        total_keys = len(self.current_mapping)
        self.change_label.configure(
            text=LanguageManager.get('key_editor_changes').format(
                changed=changed_keys, total=total_keys
            )
        )

    def _create_buttons(self, parent):
        """Create the action buttons"""
        button_frame = ctk.CTkFrame(parent, fg_color="transparent")
        button_frame.pack(fill="x", pady=10)
        
        ctk.CTkButton(
            button_frame,
            text=LanguageManager.get('key_editor_save'),
            command=self._save_mapping,
            width=120,
            height=35
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            button_frame,
            text=LanguageManager.get('key_editor_reset_all'),
            command=self._reset_all_to_default,
            width=120,
            height=35,
            fg_color="#FF6B6B",
            hover_color="#FF5252"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            button_frame,
            text=LanguageManager.get('key_editor_delete'),
            command=self._delete_custom_layout,
            width=120,
            height=35,
            fg_color="#DC2626",
            hover_color="#B91C1C"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            button_frame,
            text=LanguageManager.get('key_editor_cancel'),
            command=self._on_close,
            width=120,
            height=35,
            fg_color="#666666",
            hover_color="#555555"
        ).pack(side="right", padx=5)

    def _delete_custom_layout(self):
        """Delete the custom layout and reset to default"""
        if messagebox.askyesno(
            LanguageManager.get('warning_title'),
            LanguageManager.get('key_editor_delete_custom_layout_confirm')
        ):
            try:
                custom_file = Path(resource_path('resources/layouts/CUSTOM.xml'))
                if custom_file.exists():
                    custom_file.unlink()
                    logger.info("Custom layout file deleted")
                
                from config_manager import ConfigManager
                config = ConfigManager.get_config()
                lang_code = config.get("ui_settings", {}).get("selected_language", "en_US")
                
                lang_to_layout = {
                    "ar": "Arabic", "da": "QWERTY", "de": "QWERTZ", "en": "QWERTY",
                    "en_US": "QWERTY", "es": "QWERTY", "fr": "AZERTY", "id": "QWERTY",
                    "it": "QWERTY", "ja": "JIS", "ko_KR": "QWERTY", "mg_MG": "QWERTY",
                    "nl": "QWERTY", "pl": "QWERTY", "pt": "QWERTY", "ru": "йцукен",
                    "zh": "QWERTY",
                }
                fallback_layout = lang_to_layout.get(lang_code, "QWERTY")
                
                updates = {"ui_settings": {"keyboard_layout": fallback_layout}}
                ConfigManager.save(updates)
                logger.info(f"Layout reset to {fallback_layout} after custom deletion")
                
                messagebox.showinfo(
                    LanguageManager.get('info_title'),
                    f"Custom layout deleted. Switched to {fallback_layout}."
                )
                
                if self.callback:
                    self.callback()
                    
                self._on_close()
                
            except Exception as e:
                logger.error(f"Error deleting custom layout: {e}")
                messagebox.showerror(
                    LanguageManager.get('error_title'),
                    LanguageManager.get('key_editor_error_deleting_custom_layout')
                )

    def _save_mapping(self):
        """Save the custom mapping - ONLY if there are actual changes"""
        has_actual_changes = any(
            self.current_mapping[key_id] != self.original_mapping.get(key_id, "")
            for key_id in self.current_mapping
        )
        
        if not has_actual_changes:
            messagebox.showinfo(
                LanguageManager.get('info_title'),
                LanguageManager.get('key_editor_no_changes')
            )
            self._on_close()
            return
        
        try:
            custom_file = Path(resource_path('resources/layouts/CUSTOM.xml'))
            custom_file.parent.mkdir(parents=True, exist_ok=True)
            
            root = ET.Element('layout')
            
            try:
                from config_manager import ConfigManager
                config = ConfigManager.get_config()
                current_layout = config.get("ui_settings", {}).get("keyboard_layout", "QWERTY")
                
                root.set('base_layout', current_layout)
                logger.info(f"Custom mapping saved with base layout: {current_layout}")
                
                config_updates = {"ui_settings": {"keyboard_layout": "Custom"}}
                ConfigManager.save(config_updates)
                logger.info("Automatically set keyboard layout to 'Custom'")
                
            except Exception as e:
                logger.error(f"Error setting base layout: {e}")
                root.set('base_layout', 'QWERTY')
            
            for key_id in sorted(self.current_mapping.keys()):
                key_elem = ET.SubElement(root, 'key', id=key_id)
                key_elem.text = self.current_mapping[key_id]
            
            # Pretty XML
            from xml.dom import minidom
            rough_string = ET.tostring(root, 'utf-8')
            parsed = minidom.parseString(rough_string)
            pretty_string = parsed.toprettyxml(indent="  ")
            
            # XML Declaration
            lines = pretty_string.split('\n')
            if '<?xml version="1.0" ?>' in lines[0]:
                lines = lines[1:]
            
            final_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + '\n'.join(lines)
            
            with open(custom_file, 'w', encoding='utf-8') as f:
                f.write(final_xml)
            
            logger.info(f"Saved custom mapping with {len(self.current_mapping)} keys")
            self.has_changes = False
            
            messagebox.showinfo(
                LanguageManager.get('info_title'),
                LanguageManager.get('key_editor_custom_layout_saved_activated')
            )

            if self.callback:
                self.callback()

            self._on_close()
            
        except Exception as e:
            logger.error(f"Error saving custom mapping: {e}")
            messagebox.showerror(
                LanguageManager.get('error_title'),
                LanguageManager.get('key_editor_save_error')
            )

    def _reset_all_to_default(self):
        """Reset all keys to default values"""
        if messagebox.askyesno(
            LanguageManager.get('warning_title'),
            LanguageManager.get('key_editor_reset_confirm')
        ):
            try:
                custom_file = Path(resource_path('resources/layouts/CUSTOM.xml'))
                base_layout = "QWERTY"
                
                if custom_file.exists():
                    tree = ET.parse(custom_file)
                    root = tree.getroot()
                    base_layout = root.get('base_layout', 'QWERTY')
                    logger.info(f"Resetting to base layout: {base_layout}")
                
                from language_manager import KeyboardLayoutManager
                base_default_mapping = KeyboardLayoutManager.load_layout_silently(base_layout)
                
                has_actual_changes = any(
                    self.current_mapping[key_id] != base_default_mapping.get(key_id, "")
                    for key_id in self.current_mapping
                )
                
                if has_actual_changes:
                    self.has_changes = True
                
                self.current_mapping = base_default_mapping.copy()
                
                # Update UI
                for key_id in self.key_buttons:
                    self._update_key_button(key_id)
                
                self._update_change_count()
                self._cancel_edit()
                
                logger.info(f"Reset all keys to base layout: {base_layout}")
                
            except Exception as e:
                logger.error(f"Error resetting to base layout: {e}")
                # Fallback
                has_actual_changes = any(
                    self.current_mapping[key_id] != self.default_mapping.get(key_id, "")
                    for key_id in self.current_mapping
                )
                
                if has_actual_changes:
                    self.has_changes = True
                    
                self.current_mapping = self.default_mapping.copy()
                for key_id in self.key_buttons:
                    self._update_key_button(key_id)
                self._update_change_count()
                self._cancel_edit()

    def _on_close(self):
        """Close the window with confirmation if there are unsaved changes"""
        if self.has_changes:
            response = messagebox.askyesnocancel(
                LanguageManager.get('warning_title'),
                LanguageManager.get('key_editor_unconfirm_changes')
            )
            
            if response is None:  # Cancel
                return
            elif response:  # Yes - Save
                self._save_mapping()
                return
            # No - Continue closing
        
        self.has_changes = False
        
        if self in KeyEditorWindow._open_windows:
            KeyEditorWindow._open_windows.remove(self)
        self.window.destroy()

    @classmethod
    def is_open(cls):
        """Check whether a Key Editor window is open"""
        return len(cls._open_windows) > 0