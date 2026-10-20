# Copyright (C) 2025-2026 VanilleIce
# All rights reserved.
#
# Project Lyrica is proprietary software.
# Commercial use, redistribution, and modification are prohibited.
# See LICENSE.md for details.

import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Dict, List, Optional, Tuple
import customtkinter as ctk

from config_manager import ConfigManager
from language_manager import LanguageManager
from resource_loader import resource_path, writable_resource_path

logger = logging.getLogger("ProjectLyrica.SettingsWindow")

CUSTOM_LAYOUT_FILE = "resources/layouts/CUSTOM.xml"


class SettingsWindow:
    _open_windows: List["SettingsWindow"] = []

    def __init__(self, parent=None, **callbacks):
        if not self._ensure_single_window():
            return

        self.parent = parent
        self.callbacks = callbacks
        self.input_vars: Dict[str, ctk.StringVar] = {}
        self.preset_key_vars: List[ctk.StringVar] = []
        self.preset_speed_vars: List[ctk.StringVar] = []
        self.close_btn = None
        self._last_change_state = False
        self._is_closing = False

        self.window = self._create_window()
        self._open_windows.append(self)

        logger.info("Settings window opened")

        try:
            self._check_missing_custom_layout()
            self._load_current_config()
            self._create_ui()
            self._setup_bindings()
            self._position_window()

            self.window.deiconify()
            self.window.focus()
        except Exception as e:
            logger.critical(f"Failed to build settings window: {e}", exc_info=True)
            self._on_close()
            raise

    # ==================== Fenster-Management ====================

    @classmethod
    def _ensure_single_window(cls) -> bool:
        """Stellt sicher, dass nur ein Einstellungsfenster geöffnet ist."""
        for window in cls._open_windows[:]:
            try:
                if window.window.winfo_exists():
                    window.window.focus()
                    window.window.lift()
                    return False
            except Exception:
                pass
            cls._open_windows.remove(window)
        return True

    def _create_window(self) -> ctk.CTkToplevel:
        """Erstellt das Einstellungsfenster (noch unsichtbar)."""
        window = ctk.CTkToplevel(self.parent)
        window.title(LanguageManager.get('settings_window_title'))
        window.geometry("700x700")
        window.resizable(False, False)
        window.withdraw()

        try:
            window.iconbitmap(resource_path("resources/icons/icon.ico"))
        except Exception:
            pass

        window.protocol("WM_DELETE_WINDOW", self._on_close)
        if self.parent is not None:
            window.transient(self.parent)
        try:
            window.grab_set()
        except Exception:
            pass

        return window

    def _position_window(self):
        """Positioniert das Fenster neben dem Hauptfenster."""
        default_geometry = "720x780+100+100"

        if not (self.parent and self.parent.winfo_exists()):
            self.window.geometry(default_geometry)
            return

        try:
            self.parent.update_idletasks()

            main_x = self.parent.winfo_x()
            main_y = self.parent.winfo_y()
            main_width = self.parent.winfo_width()

            settings_x = main_x + main_width + 10
            settings_y = main_y

            screen_width = self.window.winfo_screenwidth()
            if settings_x + 720 > screen_width:
                settings_x = max(0, screen_width - 720 - 10)

            self.window.geometry(f"720x780+{settings_x}+{settings_y}")
        except Exception:
            self.window.geometry(default_geometry)

    # ==================== Konfiguration laden ====================

    def _check_missing_custom_layout(self):
        """Prüft ob das Custom-Layout gelöscht wurde."""
        custom_was_missing, fallback_layout = ConfigManager.check_and_handle_missing_custom()
        if custom_was_missing:
            messagebox.showinfo(
                LanguageManager.get('info_title'),
                LanguageManager.get('custom_layout_not_found').format(
                    fallback_layout=fallback_layout
                )
            )

    def _load_current_config(self):
        """Lädt die aktuelle Konfiguration in self.current_* Dicts."""
        self.config = ConfigManager.get_config()

        timing = self.config.get("timing_settings", {})
        delays = timing.get("delays", {})
        ramping = timing.get("ramping", {})

        self.current_delays = {
            "initial_delay": delays.get("initial_delay", 0.8),
            "pause_resume_delay": delays.get("pause_resume_delay", 1.0),
        }

        self.current_ramping = {
            "begin_steps": ramping.get("begin", {}).get("steps", 20),
            "end_steps": ramping.get("end", {}).get("steps", 16),
            "after_pause_steps": ramping.get("after_pause", {}).get("steps", 12),
        }
        
        self.current_speed_ramping = {
            "transition_time": ramping.get("speed_change", {}).get("transition_time", 6.0),
        }

        ui_settings = self.config.get("ui_settings", {})
        self.current_ui = {
            "language": ui_settings.get("selected_language", "en_US"),
            "theme": ui_settings.get("theme", "dark"),
            "keyboard_layout": ui_settings.get("keyboard_layout", "QWERTY"),
            "pause_key": ui_settings.get("pause_key", "#"),
            "reset_speed_key": ui_settings.get("reset_speed_key", "+"),
        }

        self.current_game = {
            "sky_exe_path": self.config.get("game_settings", {}).get("sky_exe_path", ""),
        }

        playback_settings = self.config.get("playback_settings", {})
        self.current_playback = {
            "key_durations": playback_settings.get(
                "key_press_durations", [0.2, 0.248, 0.3, 0.5, 1.0]
            ),
            "speed_presets": playback_settings.get(
                "speed_presets", [600, 800, 1000, 1200]
            ),
        }

        self.current_speed_change = {
            "preset_mappings": self.config.get("speed_change_settings", {}).get(
                "preset_mappings",
                [
                    {"key": "9", "speed": 600},
                    {"key": "0", "speed": 800},
                    {"key": "ß", "speed": 1000},
                    {"key": "´", "speed": 1200},
                ],
            ),
        }

    # ==================== UI Erstellung ====================

    def _create_ui(self):
        """Erstellt die komplette UI."""
        main_frame = ctk.CTkFrame(self.window)
        main_frame.pack(fill="both", expand=True, padx=0, pady=0)

        self.scrollable_frame = ctk.CTkScrollableFrame(
            main_frame, width=580, height=580
        )
        self.scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self._create_title()
        self._create_game_section()
        self._create_playback_section()
        self._create_speed_change_section()
        self._create_delays_section()
        self._create_ramping_section()
        self._create_interface_section()
        self._create_buttons_section(main_frame)

    def _create_title(self):
        ctk.CTkLabel(
            self.scrollable_frame,
            text=LanguageManager.get('settings_window_title'),
            font=("Arial", 20, "bold"),
        ).pack(pady=(0, 20))

    def _create_labeled_frame(self, parent, title_key: str) -> ctk.CTkFrame:
        """Erstellt einen beschrifteten Frame."""
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            frame,
            text=LanguageManager.get(title_key),
            font=("Arial", 16, "bold"),
        ).pack(anchor="w", pady=(8, 10), padx=10)

        return frame

    def _create_setting_row(self, parent, label_key: str = "",
                            label_width: int = 150) -> ctk.CTkFrame:
        """Erstellt eine einheitliche Einstellungszeile."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=4)

        if label_key:
            ctk.CTkLabel(
                frame,
                text=LanguageManager.get(label_key),
                width=label_width,
            ).pack(side="left")

        return frame

    # ==================== Game Sektion ====================

    def _create_game_section(self):
        section = self._create_labeled_frame(self.scrollable_frame, 'settings_game_title')
        row = self._create_setting_row(section, 'settings_sky_path')

        self.sky_path_var = ctk.StringVar(value=self.current_game.get('sky_exe_path', ''))
        ctk.CTkEntry(
            row, textvariable=self.sky_path_var, width=250
        ).pack(side="left", padx=5, fill="x", expand=True)
        ctk.CTkButton(
            row, text="...", width=30, command=self._browse_sky_exe
        ).pack(side="left", padx=5)

    def _browse_sky_exe(self):
        steam_paths = [
            Path("C:/Program Files (x86)/Steam/steamapps/common/Sky Children of the Light"),
            Path("C:/Program Files/Steam/steamapps/common/Sky Children of the Light"),
            Path.home() / "Steam/steamapps/common/Sky Children of the Light",
        ]

        initial_dir: Optional[str] = None
        for p in steam_paths:
            if p.exists():
                initial_dir = str(p)
                break

        if initial_dir is None and self.sky_path_var.get():
            current = Path(self.sky_path_var.get())
            if current.parent.exists():
                initial_dir = str(current.parent)

        file = filedialog.askopenfilename(
            title=LanguageManager.get('select_sky_exe'),
            initialdir=initial_dir,
            filetypes=[("Sky Executable", "Sky.exe")],
        )
        if file:
            self.sky_path_var.set(file)

    # ==================== Playback Sektion ====================

    def _create_playback_section(self):
        section = self._create_labeled_frame(self.scrollable_frame, 'settings_playback_title')

        self._create_array_setting(
            section, 'settings_key_durations', 'key_durations',
            [0.2, 0.248, 0.3, 0.5, 1.0], 'settings_key_durations_hint',
        )
        self._create_array_setting(
            section, 'settings_speed_presets', 'speed_presets',
            [600, 800, 1000, 1200], 'settings_speed_presets_hint',
        )
        self._create_custom_keys_row(section)

    def _create_array_setting(self, parent, label_key: str, config_key: str,
                              default_values: List, hint_key: str):
        row = self._create_setting_row(parent, label_key)

        current_value = self.current_playback.get(config_key, default_values)
        array_str = ", ".join(map(str, current_value))

        var = ctk.StringVar(value=array_str)
        ctk.CTkEntry(
            row, textvariable=var, width=200,
            placeholder_text=", ".join(map(str, default_values)),
        ).pack(side="left", padx=5)

        self.input_vars[config_key] = var

        ctk.CTkLabel(
            row,
            text=LanguageManager.get(hint_key),
            font=("Arial", 10),
            text_color="gray60",
        ).pack(side="left", padx=10)

    def _create_custom_keys_row(self, parent):
        row = self._create_setting_row(parent, 'settings_custom_keys')

        ctk.CTkButton(
            row, text=LanguageManager.get('settings_edit_keys'),
            command=self._open_key_editor, width=120,
        ).pack(side="left", padx=5)

        self.custom_keys_status = ctk.CTkLabel(
            row, text=self._get_custom_keys_status(),
            font=("Arial", 10), text_color="gray60",
        )
        self.custom_keys_status.pack(side="left", padx=10)

    def _open_key_editor(self):
        from key_editor import KeyEditorWindow
        KeyEditorWindow(self.window, self._update_ui_after_custom_save)

    def _update_ui_after_custom_save(self):
        """Aktualisiert UI nach Änderungen im Key-Editor."""
        self._load_current_config()
        self.custom_keys_status.configure(text=self._get_custom_keys_status())

        # Live-Reload: Player-Key-Mapping neu laden
        callback = self.callbacks.get('custom_layout_callback')
        if callback:
            try:
                callback()
                logger.info("Player key mapping reloaded (live)")
            except Exception as e:
                logger.error(f"Custom layout callback failed: {e}")

        # Preset-Zuordnungen neu aufbauen (falls Speed-Presets geändert wurden)
        self._create_preset_keys_ui()

        # Layout-Dropdown aktualisieren
        available_layouts = self._get_available_layouts()
        current_value = self.current_ui['keyboard_layout']

        # CUSTOM.xml: prüfen ob vorhanden (neben EXE oder im _MEIPASS)
        custom_file = Path(writable_resource_path(CUSTOM_LAYOUT_FILE))
        if not custom_file.exists():
            custom_file = Path(resource_path(CUSTOM_LAYOUT_FILE))

        if current_value == "Custom" and not custom_file.exists():
            current_value = LanguageManager.get_fallback_layout_for_lang(
                self.current_ui.get('language', 'en_US')
            )

        matched = None
        if current_value:
            for available in available_layouts:
                if available.lower() == current_value.lower():
                    matched = available
                    break

        if matched:
            current_value = matched
        else:
            # Sprache-basierter Fallback
            lang_code = self.current_ui.get('language', 'en_US')
            fallback = LanguageManager.get_fallback_layout_for_lang(lang_code)

            for available in available_layouts:
                if available.lower() == fallback.lower():
                    current_value = available
                    logger.warning(
                        f"Layout '{self.current_ui['keyboard_layout']}' not available, "
                        f"using language fallback: '{current_value}'"
                    )
                    break
            else:
                if "QWERTY" in available_layouts:
                    current_value = "QWERTY"
                else:
                    current_value = available_layouts[0] if available_layouts else "QWERTY"
                logger.warning(f"Using last-resort layout: '{current_value}'")

        self.keyboard_layout_dropdown.configure(values=available_layouts)
        self.keyboard_layout_var.set(current_value)

        # Close-Button zurücksetzen
        self._last_change_state = False
        self._update_close_button(False)

    # ==================== Speed Change Sektion ====================

    def _create_speed_change_section(self):
        section = self._create_labeled_frame(
            self.scrollable_frame, 'settings_speed_change_title'
        )

        info_row = self._create_setting_row(section, '', label_width=0)
        ctk.CTkLabel(
            info_row,
            text=LanguageManager.get('settings_speed_change_enable_hint'),
            font=("Arial", 11, "italic"),
            text_color="gray60",
            wraplength=600,
        ).pack(side="left")

        self.preset_keys_frame = ctk.CTkFrame(section, fg_color="transparent")
        self._create_preset_keys_ui()

    def _create_preset_keys_ui(self):
        """Erstellt die UI für Preset-Key-Zuordnungen (idempotent)."""
        for widget in self.preset_keys_frame.winfo_children():
            widget.destroy()

        self.preset_keys_frame.pack(fill="x", padx=10, pady=5)

        row = self._create_setting_row(
            self.preset_keys_frame, 'settings_speed_change_preset_keys'
        )
        grid_frame = ctk.CTkFrame(row, fg_color="transparent")
        grid_frame.pack(side="left", padx=5, fill="x", expand=True)

        available_speeds = self.current_playback.get('speed_presets', [600, 800, 1000, 1200])
        speed_display_values = [f"{speed}" for speed in available_speeds]
        current_mappings = self.current_speed_change.get('preset_mappings', [])

        # Vars neu initialisieren
        self.preset_key_vars = []
        self.preset_speed_vars = []

        max_presets = min(len(current_mappings), 4)
        for i in range(0, max_presets, 2):
            row_frame = ctk.CTkFrame(grid_frame, fg_color="transparent")
            row_frame.pack(fill="x", pady=2)

            for col in range(2):
                preset_index = i + col
                if preset_index >= max_presets:
                    break
                self._create_preset_mapping_row(
                    row_frame, preset_index, current_mappings[preset_index],
                    available_speeds, speed_display_values,
                )

    def _create_preset_mapping_row(self, parent, index: int, mapping: dict,
                                   available_speeds: List, display_values: List):
        preset_frame = ctk.CTkFrame(parent, fg_color="transparent")
        preset_frame.pack(side="left", padx=15)

        ctk.CTkLabel(preset_frame, text=f"Preset {index + 1}:").pack(side="left")

        key_var = ctk.StringVar(value=mapping.get('key', f'{index + 1}'))
        ctk.CTkEntry(preset_frame, textvariable=key_var, width=60).pack(side="left", padx=2)

        ctk.CTkLabel(preset_frame, text="→").pack(side="left", padx=5)

        current_speed = mapping.get(
            'speed',
            available_speeds[index] if index < len(available_speeds) else 600,
        )
        speed_var = ctk.StringVar(value=f"{current_speed}")

        ctk.CTkComboBox(
            preset_frame, values=display_values, variable=speed_var,
            state="readonly", width=80,
        ).pack(side="left", padx=2)

        self.preset_key_vars.append(key_var)
        self.preset_speed_vars.append(speed_var)

    # ==================== Delays Sektion ====================

    def _create_delays_section(self):
        section = self._create_labeled_frame(self.scrollable_frame, 'settings_delays_title')
        self._create_delay_entry(section, 'settings_initial_delay', 'initial_delay')
        self._create_delay_entry(section, 'settings_pause_delay', 'pause_resume_delay')

    def _create_delay_entry(self, parent, label_key: str, config_key: str):
        row = self._create_setting_row(parent, label_key)
        current_value = self.current_delays[config_key]
        var = ctk.StringVar(value=f"{current_value}")

        ctk.CTkEntry(row, textvariable=var, width=80).pack(side="left", padx=5)
        ctk.CTkLabel(row, text="s").pack(side="left")

        self.input_vars[config_key] = var

    # ==================== Ramping Sektion ====================

    def _create_ramping_section(self):
        section = self._create_labeled_frame(self.scrollable_frame, 'settings_ramping_title')

        self._create_ramping_entry(
            section, 'settings_ramping_start', 'begin_steps', 'settings_ramping_start_hint'
        )
        self._create_ramping_entry(
            section, 'settings_ramping_end', 'end_steps', 'settings_ramping_end_hint'
        )
        self._create_ramping_entry(
            section, 'settings_ramping_after_pause', 'after_pause_steps',
            'settings_ramping_pause_hint'
        )

        ctk.CTkFrame(section, height=2, fg_color="gray30").pack(
            fill="x", padx=20, pady=10
        )

        ctk.CTkLabel(
            section,
            text=LanguageManager.get('settings_speed_ramping_title'),
            font=("Arial", 14, "bold"),
        ).pack(anchor="w", pady=(5, 10), padx=10)

        self._create_speed_ramping_entry(section)

    def _create_ramping_entry(self, parent, label_key: str, config_key: str, hint_key: str):
        row = self._create_setting_row(parent, label_key)
        current_value = self.current_ramping[config_key]
        var = ctk.StringVar(value=str(current_value))

        ctk.CTkEntry(
            row, textvariable=var, width=80, placeholder_text="20"
        ).pack(side="left", padx=5)
        self.input_vars[config_key] = var

        ctk.CTkLabel(
            row, text=LanguageManager.get(hint_key),
            font=("Arial", 10), text_color="gray60",
        ).pack(side="left", padx=10)

    def _create_speed_ramping_entry(self, parent):
        row = self._create_setting_row(parent, 'settings_speed_transition')
        current_value = self.current_speed_ramping['transition_time']
        var = ctk.StringVar(value=str(current_value))

        ctk.CTkEntry(
            row, textvariable=var, width=80, placeholder_text="6.0"
        ).pack(side="left", padx=5)
        ctk.CTkLabel(row, text="s").pack(side="left", padx=2)

        self.input_vars['transition_time'] = var

        ctk.CTkLabel(
            row,
            text=LanguageManager.get('settings_speed_transition_hint'),
            font=("Arial", 10), text_color="gray60",
        ).pack(side="left", padx=10)

    # ==================== Interface Sektion ====================

    def _create_interface_section(self):
        section = self._create_labeled_frame(self.scrollable_frame, 'settings_interface_title')

        self._create_language_dropdown(section)
        self._create_theme_selector(section)
        self._create_layout_dropdown(section)
        self._create_key_input_row(section, 'settings_pause_key', 'pause_key')
        self._create_key_input_row(
            section, 'settings_reset_speed_key', 'reset_speed_key', default='+'
        )

    def _create_language_dropdown(self, parent):
        languages = [name for _, name, _ in LanguageManager.get_languages()]
        self._create_dropdown(
            parent, 'settings_language', 'language', languages, self.current_ui['language']
        )

    def _create_layout_dropdown(self, parent):
        """Erstellt Layout-Dropdown mit case-insensitive Matching."""
        available_layouts = self._get_available_layouts()
        current_layout = self.current_ui['keyboard_layout']

        # Case-insensitive Match: "qwertz" == "QWERTZ"
        matched = None
        if current_layout:
            for available in available_layouts:
                if available.lower() == current_layout.lower():
                    matched = available
                    break

        if matched:
            current_layout = matched
        else:
            # Sprache-basierter Fallback
            lang_code = self.current_ui.get('language', 'en_US')
            fallback = LanguageManager.get_fallback_layout_for_lang(lang_code)

            for available in available_layouts:
                if available.lower() == fallback.lower():
                    current_layout = available
                    logger.warning(
                        f"Layout '{self.current_ui['keyboard_layout']}' not available, "
                        f"using language fallback: '{current_layout}'"
                    )
                    break
            else:
                if "QWERTY" in available_layouts:
                    current_layout = "QWERTY"
                else:
                    current_layout = available_layouts[0] if available_layouts else "QWERTY"
                logger.warning(f"Using last-resort layout: '{current_layout}'")

        self._create_dropdown(
            parent, 'settings_keyboard_layout', 'keyboard_layout',
            available_layouts, current_layout
        )

    def _create_dropdown(self, parent, label_key: str, config_key: str,
                        values: List, current_value: str):
        row = self._create_setting_row(parent, label_key)

        display_value = current_value
        if config_key == 'language':
            for code, name, _ in LanguageManager.get_languages():
                if code == current_value:
                    display_value = name
                    break

        var = ctk.StringVar(value=display_value)
        dropdown = ctk.CTkComboBox(
            row, values=values, variable=var, state="readonly", width=150
        )
        dropdown.pack(side="left")

        if config_key == 'keyboard_layout':
            self.keyboard_layout_dropdown = dropdown
            self.keyboard_layout_var = var

        self.input_vars[config_key] = var

    def _create_key_input_row(self, parent, label_key: str, config_key: str,
                              default: str = '#'):
        row = self._create_setting_row(parent, label_key)
        current_value = self.current_ui.get(config_key, default)
        var = ctk.StringVar(value=current_value)
        ctk.CTkEntry(row, textvariable=var, width=50).pack(side="left")
        self.input_vars[config_key] = var

    def _create_theme_selector(self, parent):
        row = self._create_setting_row(parent, 'settings_theme')

        theme_var = ctk.StringVar(value=self.current_ui['theme'])
        self.input_vars['theme'] = theme_var

        theme_frame = ctk.CTkFrame(row, fg_color="transparent")
        theme_frame.pack(side="left")

        for theme in ("dark", "light"):
            ctk.CTkRadioButton(
                theme_frame,
                text=LanguageManager.get(f'theme_{theme}'),
                variable=theme_var,
                value=theme,
            ).pack(side="left", padx=10)

    # ==================== Layout-Hilfsmethoden ====================

    def _get_available_layouts(self) -> List[str]:
        """Liste aller verfügbaren Layouts (inkl. Custom falls vorhanden).

        Behält Original-Groß-/Kleinschreibung der Dateinamen bei
        (z.B. "QWERTZ" wenn Datei "QWERTZ.xml" heißt).
        """
        available_layouts: List[str] = []
        layouts_dir = Path(resource_path("resources/layouts"))

        if layouts_dir.exists():
            for xml_file in layouts_dir.glob("*.xml"):
                layout_name = xml_file.stem
                if layout_name.upper() == "CUSTOM":
                    continue
                if layout_name not in available_layouts:
                    available_layouts.append(layout_name)

        available_layouts.sort()

        # Custom prüfen: neben EXE ODER im _MEIPASS
        custom_file = Path(writable_resource_path(CUSTOM_LAYOUT_FILE))
        if not custom_file.exists():
            custom_file = Path(resource_path(CUSTOM_LAYOUT_FILE))

        if custom_file.exists():
            available_layouts.append("Custom")

        return available_layouts

    def _get_custom_keys_status(self) -> str:
        # CUSTOM.xml neben EXE ODER im _MEIPASS
        custom_file = Path(writable_resource_path(CUSTOM_LAYOUT_FILE))
        if not custom_file.exists():
            custom_file = Path(resource_path(CUSTOM_LAYOUT_FILE))

        if not custom_file.exists():
            return LanguageManager.get('settings_using_default_layout')

        if self.current_ui.get('keyboard_layout', '') == "Custom":
            return LanguageManager.get('settings_custom_active')
        return LanguageManager.get('settings_custom_available')

    # ==================== Buttons ====================

    def _create_buttons_section(self, parent):
        button_frame = ctk.CTkFrame(parent, fg_color="transparent")
        button_frame.pack(fill="x", pady=10, padx=10, side="bottom")

        ctk.CTkButton(
            button_frame, text=LanguageManager.get('settings_reset'),
            command=self._reset_defaults, width=120, height=35,
            fg_color="#FF6B6B", hover_color="#FF5252",
        ).pack(side="left", padx=5)

        # Dynamischer Close/Save-Button
        self.close_btn = ctk.CTkButton(
            button_frame, text=LanguageManager.get('settings_cancel'),
            command=self._on_close, width=160, height=35,
            fg_color="#666666", hover_color="#555555",
        )
        self.close_btn.pack(side="right", padx=5)

    def _setup_bindings(self):
        self.window.bind('<Return>', lambda e: self._on_close())
        self.window.bind('<Escape>', lambda e: self._on_close())

        # Initial: keine Änderungen → Close-Button zeigt "Schließen"
        self._last_change_state = False
        self._update_close_button(False)

        # Change-Tracking: Close-Button-Text dynamisch aktualisieren
        self._check_changes_periodic()

    def _check_changes_periodic(self):
        """Prüft periodisch ob Änderungen vorliegen → Close-Button-Text anpassen."""
        try:
            if not self.window.winfo_exists():
                return

            has_changes = False
            try:
                updates = self._collect_updates()
                has_changes = bool(updates)
            except Exception:
                has_changes = False

            # Nur updaten wenn sich was geändert hat (Performance)
            if has_changes != self._last_change_state:
                self._last_change_state = has_changes
                self._update_close_button(has_changes)
        except Exception:
            pass

        # Alle 500ms prüfen
        try:
            self.window.after(500, self._check_changes_periodic)
        except Exception:
            pass

    def _update_close_button(self, has_changes: Optional[bool] = None):
        """Aktualisiert den Close-Button-Text."""
        if not self.close_btn:
            return

        try:
            if not self.window.winfo_exists():
                return
            # Prüfen ob Button noch gültig ist
            self.close_btn.winfo_exists()
        except Exception:
            return

        if has_changes is None:
            try:
                has_changes = bool(self._collect_updates())
            except Exception:
                has_changes = False

        try:
            if has_changes:
                self.close_btn.configure(
                    text=LanguageManager.get('settings_save_and_close'),
                    fg_color="#2b6cb0",
                    hover_color="#1f538d",
                )
            else:
                self.close_btn.configure(
                    text=LanguageManager.get('settings_cancel'),
                    fg_color="#666666",
                    hover_color="#555555",
                )
        except Exception as e:
            logger.debug(f"Could not update close button: {e}")

    # ==================== Validierung ====================

    def _validate_inputs(self) -> Tuple[bool, Optional[str]]:
        try:
            # Delays
            for key in ('initial_delay', 'pause_resume_delay'):
                if key in self.input_vars:
                    val = float(self.input_vars[key].get().strip())
                    if val <= 0:
                        return False, LanguageManager.get('settings_error_positive')

            # Ramping Steps
            for key in ('begin_steps', 'end_steps', 'after_pause_steps'):
                if key in self.input_vars:
                    val = int(self.input_vars[key].get().strip())
                    if val <= 0:
                        return False, LanguageManager.get('settings_error_positive')

            # Transition Time
            if 'transition_time' in self.input_vars:
                val = float(self.input_vars['transition_time'].get().strip())
                if val <= 0:
                    return False, LanguageManager.get('settings_error_positive')

            # Keys
            for key in ('pause_key', 'reset_speed_key'):
                if key in self.input_vars:
                    val = self.input_vars[key].get().strip()
                    if len(val) != 1:
                        return False, LanguageManager.get(f'settings_error_{key}')

            return True, None

        except ValueError:
            return False, LanguageManager.get('settings_error_numbers')
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return False, LanguageManager.get('settings_error_general')

    # ==================== Speichern ====================

    def _save_settings(self, close_after: bool = False) -> bool:
        valid, error_msg = self._validate_inputs()
        if not valid:
            messagebox.showerror(LanguageManager.get('error_title'), error_msg)
            return False

        try:
            updates = self._collect_updates()

            if not updates:
                messagebox.showinfo(
                    LanguageManager.get('info_title'),
                    LanguageManager.get('settings_no_changes'),
                )
                return False

            # ← NEU: Original-Werte VOR dem Speichern merken
            original_lang = self.current_ui['language']
            original_layout = self.current_ui['keyboard_layout']
            new_lang = (
                self._get_selected_lang_code()
                if 'language' in self.input_vars else original_lang
            )
            new_layout = (
                self.input_vars['keyboard_layout'].get()
                if 'keyboard_layout' in self.input_vars else original_layout
            )

            if not ConfigManager.save(updates):
                messagebox.showerror(
                    LanguageManager.get('error_title'),
                    LanguageManager.get('settings_save_error'),
                )
                return False

            self._trigger_callbacks(updates)
            self._load_current_config()

            restart_needed = self._handle_post_save(
                original_lang, original_layout, new_lang, new_layout
            )

            if restart_needed:
                return True

            if close_after:
                self._do_close()

            return True

        except Exception as e:
            logger.error(f"Error saving settings: {e}", exc_info=True)
            messagebox.showerror(
                LanguageManager.get('error_title'),
                LanguageManager.get('settings_save_error'),
            )
            return False

    def _collect_updates(self) -> Dict[str, Any]:
        """Sammelt alle Änderungen."""
        updates: Dict[str, Any] = {}

        timing_updates = self._collect_timing_updates()
        if timing_updates:
            updates["timing_settings"] = timing_updates

        ui_updates = self._collect_ui_updates()
        if ui_updates:
            updates["ui_settings"] = ui_updates

        new_sky_path = self.sky_path_var.get()
        if new_sky_path != self.current_game['sky_exe_path']:
            updates["game_settings"] = {"sky_exe_path": new_sky_path}

        playback_updates = self._collect_playback_updates()
        if playback_updates:
            updates["playback_settings"] = playback_updates

        speed_change_updates = self._collect_speed_change_updates()
        if speed_change_updates:
            updates["speed_change_settings"] = speed_change_updates

        lang_layout_updates = self._collect_lang_layout_updates()
        if lang_layout_updates:
            updates.setdefault("ui_settings", {}).update(lang_layout_updates)

        return updates

    def _collect_timing_updates(self) -> Optional[Dict]:
        timing_updates: Dict[str, Any] = {"delays": {}, "ramping": {}}
        timing_changed = False

        for key, var_key in (
            ('initial_delay', 'initial_delay'),
            ('pause_resume_delay', 'pause_resume_delay'),
        ):
            if var_key in self.input_vars:
                new_val = float(self.input_vars[var_key].get().strip())
                if new_val != self.current_delays[key]:
                    timing_updates["delays"][key] = new_val
                    timing_changed = True

        ramping_keys = {
            'begin_steps': 'begin',
            'end_steps': 'end',
            'after_pause_steps': 'after_pause',
        }
        for var_key, config_key in ramping_keys.items():
            if var_key in self.input_vars:
                new_val = int(self.input_vars[var_key].get().strip())
                if new_val != self.current_ramping[var_key]:
                    timing_updates["ramping"].setdefault(config_key, {})
                    timing_updates["ramping"][config_key]["steps"] = new_val
                    timing_changed = True

        if 'transition_time' in self.input_vars:
            new_val = float(self.input_vars['transition_time'].get().strip())
            if new_val != self.current_speed_ramping["transition_time"]:
                timing_updates["ramping"].setdefault("speed_change", {})
                timing_updates["ramping"]["speed_change"]["transition_time"] = new_val
                timing_changed = True

        if not timing_updates["delays"]:
            del timing_updates["delays"]
        if not timing_updates["ramping"]:
            del timing_updates["ramping"]

        return timing_updates if timing_changed else None

    def _collect_ui_updates(self) -> Optional[Dict]:
        updates: Dict[str, Any] = {}

        for key in ('pause_key', 'reset_speed_key'):
            if key in self.input_vars:
                new_val = self.input_vars[key].get()
                if new_val != self.current_ui.get(key):
                    updates[key] = new_val

        if 'theme' in self.input_vars:
            new_val = self.input_vars['theme'].get()
            if new_val != self.current_ui['theme']:
                updates['theme'] = new_val

        return updates if updates else None

    def _collect_playback_updates(self) -> Optional[Dict]:
        updates: Dict[str, Any] = {}

        if 'key_durations' in self.input_vars:
            new_val = self._parse_array_setting(
                self.input_vars['key_durations'].get(), float
            )
            if new_val != self.current_playback['key_durations']:
                updates['key_press_durations'] = new_val

        if 'speed_presets' in self.input_vars:
            new_val = self._parse_array_setting(
                self.input_vars['speed_presets'].get(), int
            )
            if new_val != self.current_playback['speed_presets']:
                updates['speed_presets'] = new_val

        return updates if updates else None

    def _collect_speed_change_updates(self) -> Optional[Dict]:
        new_mappings = []
        available_speeds = self.current_playback.get(
            'speed_presets', [600, 800, 1000, 1200]
        )

        for i, (key_var, speed_var) in enumerate(
            zip(self.preset_key_vars, self.preset_speed_vars)
        ):
            key = key_var.get().strip()
            try:
                speed = int(speed_var.get().strip())
                if speed not in available_speeds and available_speeds:
                    speed = available_speeds[0]
            except (ValueError, TypeError):
                speed = available_speeds[i] if i < len(available_speeds) else 600

            new_mappings.append({"key": key, "speed": speed})

        if new_mappings != self.current_speed_change.get('preset_mappings', []):
            return {"preset_mappings": new_mappings}
        return None

    def _collect_lang_layout_updates(self) -> Optional[Dict]:
        updates: Dict[str, Any] = {}

        if 'language' in self.input_vars:
            new_lang = self._get_selected_lang_code()
            if new_lang != self.current_ui['language']:
                updates['selected_language'] = new_lang

        if 'keyboard_layout' in self.input_vars:
            new_layout = self.input_vars['keyboard_layout'].get()
            if new_layout != self.current_ui['keyboard_layout']:
                updates['keyboard_layout'] = new_layout

        return updates if updates else None

    # ==================== Callbacks ====================

    def _trigger_callbacks(self, updates: Dict):
        """Löst die entsprechenden Callbacks aus."""
        callback_map = {
            'timing_settings': self.callbacks.get('timing_callback'),
            'playback_settings': self.callbacks.get('playback_callback'),
            'speed_change_settings': self.callbacks.get('speed_change_callback'),
        }

        for key, callback in callback_map.items():
            if key in updates and callback:
                try:
                    callback(updates[key])
                except Exception as e:
                    logger.error(f"Callback for '{key}' failed: {e}")

        if 'ui_settings' in updates:
            ui = updates['ui_settings']
            if 'pause_key' in ui and self.callbacks.get('pause_key_callback'):
                self.callbacks['pause_key_callback'](ui['pause_key'])
            if 'reset_speed_key' in ui and self.callbacks.get('reset_speed_key_callback'):
                self.callbacks['reset_speed_key_callback'](ui['reset_speed_key'])
            if 'theme' in ui and self.callbacks.get('theme_callback'):
                self.callbacks['theme_callback'](ui['theme'])
                ctk.set_appearance_mode(ui['theme'])

    def _handle_post_save(self, original_lang: str, original_layout: str,
                        new_lang: str, new_layout: str) -> bool:
        """Behandelt Aktionen nach dem Speichern.

        Returns:
            True wenn Neustart durchgeführt wird (App beendet sich), sonst False.
        """
        # Custom-Layout-Änderung → Live-Reload, KEIN Neustart!
        if original_layout == "Custom" and new_layout == "Custom":
            messagebox.showinfo(
                LanguageManager.get('info_title'),
                LanguageManager.get('settings_saved'),
            )
            return False

        needs_restart = (original_layout != new_layout) or (original_lang != new_lang)

        if not needs_restart:
            messagebox.showinfo(
                LanguageManager.get('info_title'),
                LanguageManager.get('settings_saved'),
            )
            return False

        if messagebox.askyesno(
            LanguageManager.get('info_title'),
            LanguageManager.get('settings_restart_required') + "\n\n" +
            LanguageManager.get('settings_restart_now'),
        ):
            self._restart_main_application()
            return True
        else:
            messagebox.showinfo(
                LanguageManager.get('info_title'),
                LanguageManager.get('settings_restart_later'),
            )
            return False

    # ==================== Hilfsmethoden ====================

    def _parse_array_setting(self, value_str: str, converter: type) -> List:
        if not value_str.strip():
            return []
        try:
            return [converter(x.strip()) for x in value_str.split(",") if x.strip()]
        except ValueError as e:
            raise ValueError(f"Invalid array format: {value_str}") from e

    def _get_selected_lang_code(self) -> str:
        if 'language' not in self.input_vars:
            return self.current_ui['language']
        lang_name = self.input_vars['language'].get()
        for code, name, _ in LanguageManager.get_languages():
            if name == lang_name:
                return code
        return "en_US"

    def _restart_main_application(self):
        """Startet die App neu (PyInstaller-safe, .bat-safe, Store-Python-safe)."""
        try:
            # 1. Mutex freigeben (BEVOR Popen, damit neue Instanz starten kann)
            if self.parent is not None and hasattr(self.parent, '_mutex') and self.parent._mutex:
                try:
                    import ctypes
                    ctypes.windll.kernel32.CloseHandle(self.parent._mutex)
                    self.parent._mutex = None
                    logger.info("Mutex released before restart")
                except Exception as e:
                    logger.warning(f"Could not release mutex: {e}")

            # 2. Kommandozeile + Arbeitsverzeichnis bestimmen
            if getattr(sys, 'frozen', False):
                # === PyInstaller-EXE (onefile oder onedir) ===
                exe_path = Path(sys.executable).resolve()
                args = [str(exe_path)]
                work_dir = exe_path.parent
                logger.info(f"Restarting EXE: {exe_path} (cwd={work_dir})")
            else:
                # === Entwicklungsmodus (.py oder .bat) ===
                try:
                    import __main__
                    main_file = getattr(__main__, '__file__', None)
                    if main_file:
                        script_path = Path(main_file).resolve()
                    else:
                        script_path = Path(sys.argv[0]).resolve()
                except Exception:
                    script_path = Path(sys.argv[0]).resolve()

                if script_path.suffix.lower() in ('.bat', '.cmd'):
                    candidate = script_path.parent / "ProjectLyrica.py"
                    if candidate.exists():
                        script_path = candidate.resolve()

                args = [sys.executable, str(script_path)]
                work_dir = script_path.parent
                logger.info(
                    f"Restarting script: python={sys.executable} "
                    f"script={script_path} (cwd={work_dir})"
                )

            # 3. Settings schließen
            self._do_close()

            # 4. Kurz warten
            time.sleep(1.0)

            # 5. Umgebung für neue Instanz vorbereiten
            env = os.environ.copy()
            env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
            env.pop("_PYI_APPLICATION_HOME_DIR", None)
            env.pop("_PYI_PARENT_PROCESS_LEVEL", None)

            # 6. Neue Instanz starten
            try:
                subprocess.Popen(
                    args,
                    cwd=str(work_dir),
                    close_fds=True,
                    env=env,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                    if sys.platform == "win32" else 0,
                )
                logger.info(f"New instance started: args={args} cwd={work_dir}")
            except Exception as e:
                logger.error(f"Failed to start new instance: {e}", exc_info=True)
                messagebox.showerror(
                    LanguageManager.get('error_title'),
                    LanguageManager.get('settings_restart_failed'),
                )
                return

            # 7. Aktuelle App beenden
            if self.parent is not None:
                try:
                    self.parent.quit()
                    self.parent.destroy()
                except Exception as e:
                    logger.warning(f"Could not destroy parent: {e}")

            # 8. Hart aussteigen
            os._exit(0)

        except Exception as e:
            logger.error(f"Failed to restart main application: {e}", exc_info=True)
            messagebox.showerror(
                LanguageManager.get('error_title'),
                LanguageManager.get('settings_restart_failed'),
            )

    def _reset_defaults(self):
        if not messagebox.askyesno(
            LanguageManager.get('warning_title'),
            LanguageManager.get('settings_reset_confirm'),
        ):
            return

        if not ConfigManager.reset_to_defaults():
            messagebox.showerror(
                LanguageManager.get('error_title'),
                LanguageManager.get('settings_reset_error'),
            )
            return

        logger.info("Settings reset to defaults")
        messagebox.showinfo(
            LanguageManager.get('info_title'),
            LanguageManager.get('settings_reset_success'),
        )
        self._do_close()

    # ==================== Close ====================

    def _on_close(self):
        if self._is_closing:
            return

        self._is_closing = True

        try:
            updates = self._collect_updates()
            has_changes = bool(updates)
        except Exception:
            has_changes = False

        if has_changes:
            try:
                if not self._save_settings(close_after=False):
                    self._is_closing = False
                    return
            except Exception as e:
                logger.error(f"Error during save on close: {e}")
                self._is_closing = False
                return

            # Wenn Neustart durchgeführt wurde: App beendet sich bereits
            try:
                if not self.window.winfo_exists():
                    return
            except Exception:
                return

        self._do_close()

    def _do_close(self):
        """Interne Close-Methode (ohne Fragen)."""
        logger.info("Settings window closed")

        try:
            self.window.grab_release()
        except Exception:
            pass

        if self in SettingsWindow._open_windows:
            SettingsWindow._open_windows.remove(self)

        try:
            if self.window.winfo_exists():
                self.window.destroy()
        except Exception:
            pass

    @classmethod
    def is_open(cls) -> bool:
        return len(cls._open_windows) > 0