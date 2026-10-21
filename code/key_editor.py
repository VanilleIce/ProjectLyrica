# Copyright (C) 2025-2026 VanilleIce
# All rights reserved.
#
# Project Lyrica is proprietary software.
# Commercial use, redistribution, and modification are prohibited.
# See LICENSE.md for details.

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from tkinter import messagebox
from typing import Dict

import customtkinter as ctk

from config_manager import ConfigManager
from language_manager import LanguageManager
from resource_loader import resource_path, writable_resource_path

logger = logging.getLogger("ProjectLyrica.KeyEditor")

CUSTOM_LAYOUT_FILE = "resources/layouts/CUSTOM.xml"


class KeyEditorWindow:
    _open_windows: list = []

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

        icon_path = resource_path("resources/icons/icon.ico")
        if Path(icon_path).exists():
            try:
                self.window.iconbitmap(icon_path)
            except Exception as e:
                logger.warning(f"Could not set icon: {e}")

        self.window.transient(parent)
        try:
            self.window.grab_set()
        except Exception:
            pass

        KeyEditorWindow._open_windows.append(self)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        # Layout-Basis ermitteln und Mappings laden
        self.base_layout = self._detect_base_layout()
        self.default_mapping = self._load_default_mapping(self.base_layout)
        self.current_mapping = self._load_current_mapping()
        self.original_mapping = self.current_mapping.copy()

        self.has_changes = False
        self.currently_editing = None
        self.close_btn = None

        self._create_ui()
        self._update_change_count()

    # ==================== Layout Detection & Loading ====================

    def _get_custom_layout_path(self) -> Path:
        """Gibt den beschreibbaren Pfad zu CUSTOM.xml zurück."""
        return Path(writable_resource_path(CUSTOM_LAYOUT_FILE))

    def _detect_base_layout(self) -> str:
        """Ermittelt das Basis-Layout (aus CUSTOM.xml oder Config)."""
        custom_file = self._get_custom_layout_path()
        if custom_file.exists():
            try:
                tree = ET.parse(custom_file)
                return tree.getroot().get('base_layout', 'QWERTY')
            except Exception as e:
                logger.error(f"Could not read base_layout from CUSTOM.xml: {e}")

        config = ConfigManager.get_config()
        layout = config.get("ui_settings", {}).get("keyboard_layout", "QWERTY")

        if layout == "Custom":
            lang_code = config.get("ui_settings", {}).get("selected_language", "en_US")
            return LanguageManager.get_fallback_layout_for_lang(lang_code)

        return layout

    def _load_default_mapping(self, layout_name: str) -> Dict[str, str]:
        """Lädt das Standard-Mapping für das angegebene Layout."""
        from language_manager import KeyboardLayoutManager
        return KeyboardLayoutManager.load_layout_silently(layout_name)

    def _load_current_mapping(self) -> Dict[str, str]:
        """Lädt Custom-Mapping falls vorhanden, sonst Default."""
        custom_file = self._get_custom_layout_path()
        if custom_file.exists():
            try:
                tree = ET.parse(custom_file)
                mapping = {}
                for key in tree.findall('key'):
                    key_id = key.get('id')
                    key_text = key.text.strip() if key.text else ""
                    if key_id:
                        mapping[key_id] = key_text
                logger.info(f"Loaded custom mapping with {len(mapping)} keys")
                return mapping
            except Exception as e:
                logger.error(f"Could not parse CUSTOM.xml: {e}")

        return self.default_mapping.copy()

    def _is_key_custom(self, key_id: str) -> bool:
        return self.current_mapping.get(key_id, "") != self.default_mapping.get(key_id, "")

    def _has_unsaved_changes(self) -> bool:
        """Prüft ob ungespeicherte Änderungen vorliegen."""
        return any(
            self.current_mapping[key_id] != self.original_mapping.get(key_id, "")
            for key_id in self.current_mapping
        )

    # ==================== UI Erstellung ====================

    def _create_ui(self):
        main_frame = ctk.CTkFrame(self.window)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

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

        ctk.CTkLabel(
            main_frame,
            text=LanguageManager.get('key_editor_instructions'),
            font=("Arial", 11),
            text_color="gray70",
            wraplength=580
        ).pack(fill="x", pady=(0, 15))

        self._create_current_key_display(main_frame)
        self._create_keyboard_layout(main_frame)
        self._create_buttons(main_frame)
        self._setup_key_bindings()

    def _create_current_key_display(self, parent):
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
        keyboard_frame = ctk.CTkFrame(parent)
        keyboard_frame.pack(fill="both", expand=True, pady=(0, 15))

        self.key_rows = [
            ['Key0', 'Key1', 'Key2', 'Key3', 'Key4'],
            ['Key5', 'Key6', 'Key7', 'Key8', 'Key9'],
            ['Key10', 'Key11', 'Key12', 'Key13', 'Key14']
        ]

        self.key_buttons: Dict[str, ctk.CTkButton] = {}

        for row_keys in self.key_rows:
            row_frame = ctk.CTkFrame(keyboard_frame, fg_color="transparent")
            row_frame.pack(pady=8)

            for key_id in row_keys:
                self._create_key_button(row_frame, key_id)

    def _create_key_button(self, parent, key_id: str):
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

        self.key_buttons[key_id] = btn

    # ==================== Key Editing ====================

    def _start_key_edit(self, key_id: str):
        self.currently_editing = key_id
        current_value = self.current_mapping.get(key_id, "")

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

        self._refresh_all_button_colors()

    def _refresh_all_button_colors(self):
        for key_id in self.key_buttons:
            self._update_key_button(key_id)

    def _process_key_input(self, key_value: str):
        if not self.currently_editing:
            return

        key_id = self.currently_editing
        self.current_mapping[key_id] = key_value
        self._update_key_button(key_id)

        display_text = f"'{key_value}'" if key_value else LanguageManager.get('key_editor_empty')
        text_color = "#2E86AB" if key_value else "red"
        self.current_key_value.configure(text=display_text, text_color=text_color)

        self._update_change_count()

    def _setup_key_bindings(self):
        self.window.bind('<KeyPress>', self._on_any_key_press)
        self.window.focus_set()
        self.window.after(
            50,
            lambda: self.window.focus_force() if self.window.winfo_exists() else None
        )

    def _on_any_key_press(self, event):
        if not self.currently_editing:
            return

        if event.keysym == 'Escape':
            self._cancel_edit()
            return
        if event.keysym == 'BackSpace':
            self._process_key_input("")
            return

        modifier_keys = {
            'Shift_L', 'Shift_R', 'Control_L', 'Control_R',
            'Alt_L', 'Alt_R', 'Caps_Lock', 'Num_Lock', 'Scroll_Lock',
            'Super_L', 'Super_R', 'Meta_L', 'Meta_R', 'Windows_L', 'Windows_R'
        }
        if event.keysym in modifier_keys:
            return

        special_keys = {
            'space': " ",
            'Return': "\n",
            'Tab': "\t"
        }

        if event.keysym in special_keys:
            self._process_key_input(special_keys[event.keysym])
            return

        char = event.char
        if char and char.isprintable():
            self._process_key_input(char)
        elif len(event.keysym) == 1:
            self._process_key_input(event.keysym)

    def _cancel_edit(self):
        self.currently_editing = None
        self.current_key_label.configure(text=LanguageManager.get('key_editor_no_selection'))
        self.current_key_value.configure(text="")
        self._refresh_all_button_colors()

    def _update_key_button(self, key_id: str):
        btn = self.key_buttons.get(key_id)
        if not btn:
            return

        current_value = self.current_mapping.get(key_id, "")
        is_custom = self._is_key_custom(key_id)
        is_selected = (key_id == self.currently_editing)

        display_text = current_value if current_value else "?"

        if is_selected:
            fg_color, hover_color = "#F24236", "#D32F2F"
        else:
            fg_color = "#2E86AB" if is_custom else "#3A3A3A"
            hover_color = "#1B5E7B" if is_custom else "#4A4A4A"

        btn.configure(
            text=display_text,
            fg_color=fg_color,
            hover_color=hover_color
        )

    def _update_change_count(self):
        changed_keys = sum(1 for key_id in self.current_mapping if self._is_key_custom(key_id))
        total_keys = len(self.current_mapping)

        self.change_label.configure(
            text=LanguageManager.get('key_editor_changes').format(
                changed=changed_keys, total=total_keys
            )
        )

        # Close-Button dynamisch aktualisieren
        self._update_close_button()

    def _update_close_button(self):
        """Aktualisiert den Close-Button je nach Änderungs-Status."""
        if not self.close_btn:
            return

        if self._has_unsaved_changes():
            self.close_btn.configure(
                text=LanguageManager.get('key_editor_save_and_close'),
                fg_color="#2b6cb0",
                hover_color="#1f538d"
            )
        else:
            self.close_btn.configure(
                text=LanguageManager.get('key_editor_cancel'),
                fg_color="#666666",
                hover_color="#555555"
            )

    # ==================== Action Buttons ====================

    def _create_buttons(self, parent):
        button_frame = ctk.CTkFrame(parent, fg_color="transparent")
        button_frame.pack(fill="x", pady=10)

        ctk.CTkButton(
            button_frame,
            text=LanguageManager.get('key_editor_reset_all'),
            command=self._reset_all_to_default,
            width=140, height=35,
            fg_color="#FF6B6B", hover_color="#FF5252"
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            button_frame,
            text=LanguageManager.get('key_editor_delete'),
            command=self._delete_custom_layout,
            width=140, height=35,
            fg_color="#DC2626", hover_color="#B91C1C"
        ).pack(side="left", padx=5)

        # Dynamischer Close/Save-Button
        self.close_btn = ctk.CTkButton(
            button_frame,
            text=LanguageManager.get('key_editor_cancel'),
            command=self._on_close,
            width=160, height=35,
            fg_color="#666666", hover_color="#555555"
        )
        self.close_btn.pack(side="right", padx=5)

    # ==================== Save / Delete / Reset ====================

    def _delete_custom_layout(self):
        if not messagebox.askyesno(
            LanguageManager.get('warning_title'),
            LanguageManager.get('key_editor_delete_custom_layout_confirm')
        ):
            return

        custom_file = self._get_custom_layout_path()
        if custom_file.exists():
            try:
                custom_file.unlink()
            except Exception as e:
                logger.error(f"Could not delete CUSTOM.xml: {e}")
                messagebox.showerror(
                    LanguageManager.get('error_title'),
                    f"Could not delete custom layout: {e}"
                )
                return

        config = ConfigManager.get_config()
        lang_code = config.get("ui_settings", {}).get("selected_language", "en_US")
        fallback_layout = LanguageManager.get_fallback_layout_for_lang(lang_code)

        ConfigManager.save({"ui_settings": {"keyboard_layout": fallback_layout}})

        info_text = LanguageManager.get('key_editor_custom_deleted')
        if info_text == '[key_editor_custom_deleted]':
            info_text = f"Custom layout deleted. Switched to {fallback_layout}."
        else:
            try:
                info_text = info_text.format(layout=fallback_layout)
            except (KeyError, IndexError):
                pass

        messagebox.showinfo(LanguageManager.get('info_title'), info_text)

        self.original_mapping = self.current_mapping.copy()
        self.has_changes = False

        if self.callback:
            self.callback()

        self._do_close()

    def _save_mapping(self, close_after: bool = False) -> bool:
        """Speichert das Custom-Mapping.

        Returns:
            True bei Erfolg, False bei Fehler.
        """
        if not self._has_unsaved_changes():
            messagebox.showinfo(
                LanguageManager.get('info_title'),
                LanguageManager.get('key_editor_no_changes')
            )
            return False

        custom_file = self._get_custom_layout_path()
        custom_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            root = ET.Element('layout')
            root.set('base_layout', self.base_layout)

            for key_id in sorted(self.current_mapping.keys()):
                key_elem = ET.SubElement(root, 'key', id=key_id)
                key_elem.text = self.current_mapping[key_id]

            from xml.dom import minidom
            rough_string = ET.tostring(root, 'utf-8')
            parsed = minidom.parseString(rough_string)
            pretty_string = parsed.toprettyxml(indent="  ")

            lines = pretty_string.split('\n')
            if '<?xml version="1.0" ?>' in lines[0]:
                lines = lines[1:]

            final_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + '\n'.join(lines)

            with open(custom_file, 'w', encoding='utf-8') as f:
                f.write(final_xml)

        except Exception as e:
            logger.error(f"Could not write CUSTOM.xml: {e}")
            messagebox.showerror(
                LanguageManager.get('error_title'),
                f"Could not save custom layout: {e}"
            )
            return False

        ConfigManager.save({"ui_settings": {"keyboard_layout": "Custom"}})

        logger.info(f"Saved custom mapping to {custom_file}")

        self.original_mapping = self.current_mapping.copy()
        self.has_changes = False

        messagebox.showinfo(
            LanguageManager.get('info_title'),
            LanguageManager.get('key_editor_custom_layout_saved_activated')
        )

        if self.callback:
            self.callback()

        if close_after:
            self._do_close()

        return True

    def _reset_all_to_default(self):
        if not messagebox.askyesno(
            LanguageManager.get('warning_title'),
            LanguageManager.get('key_editor_reset_confirm')
        ):
            return

        custom_file = self._get_custom_layout_path()
        base_layout = self.base_layout

        if custom_file.exists():
            try:
                tree = ET.parse(custom_file)
                base_layout = tree.getroot().get('base_layout', base_layout)
            except Exception:
                pass

        base_default_mapping = self._load_default_mapping(base_layout)

        self.current_mapping = base_default_mapping.copy()

        for key_id in self.key_buttons:
            self._update_key_button(key_id)

        self._update_change_count()
        self._cancel_edit()

    # ==================== Close ====================

    def _on_close(self):
        """Schließt den Key Editor. Speichert automatisch bei Änderungen."""
        if self._has_unsaved_changes():
            if not self._save_mapping(close_after=False):
                return
            self._do_close()
        else:
            self._do_close()

    def _do_close(self):
        """Interne Close-Methode (ohne Fragen)."""
        self.has_changes = False

        if self in KeyEditorWindow._open_windows:
            KeyEditorWindow._open_windows.remove(self)

        try:
            self.window.grab_release()
        except Exception:
            pass

        try:
            self.window.destroy()
        except Exception:
            pass

    @classmethod
    def is_open(cls) -> bool:
        return len(cls._open_windows) > 0