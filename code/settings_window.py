# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import customtkinter as ctk
from tkinter import messagebox
import logging
from pathlib import Path
import xml.etree.ElementTree as ET

from config_manager import ConfigManager
from language_manager import LanguageManager
from resource_loader import resource_path

logger = logging.getLogger("ProjectLyrica.SettingsWindow")

class SettingsWindow:
    _open_windows = []
    
    def __init__(self, parent=None, theme_callback=None, timing_callback=None, playback_callback=None, pause_key_callback=None, speed_change_callback=None):
        for window in SettingsWindow._open_windows[:]:
            try:
                if hasattr(window, 'window') and window.window.winfo_exists():
                    window.window.focus()
                    window.window.lift()
                    return
                else:
                    SettingsWindow._open_windows.remove(window)
            except Exception as e:
                SettingsWindow._open_windows.remove(window)

        self.parent = parent
        self.window = ctk.CTkToplevel(parent)
        self.window.title(LanguageManager.get('settings_window_title'))
        self.window.geometry("720x750")
        self.window.resizable(False, False)

        self.window.withdraw()

        try:
            self.window.iconbitmap(resource_path("resources/icons/icon.ico"))
        except Exception:
            pass
        
        SettingsWindow._open_windows.append(self)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self.window.transient(parent)
        self.window.grab_set()
        
        self._check_missing_custom_layout()
        self._original_custom_hash = self._get_custom_file_hash()
        self._load_current_config()
        self._create_ui()
        self._setup_bindings()
        
        self.theme_callback = theme_callback
        self.timing_callback = timing_callback
        self.playback_callback = playback_callback
        self.pause_key_callback = pause_key_callback
        self.speed_change_callback = speed_change_callback
        
        self._position_window()

        self.window.deiconify()
        self.window.focus()

    def _check_missing_custom_layout(self):
        """Checks whether custom layout has been deleted"""
        try:
            custom_was_missing, fallback_layout = ConfigManager.check_and_handle_missing_custom()
            if custom_was_missing:
                logger.info(f"Settings: Custom was missing, switched to {fallback_layout}")
                messagebox.showinfo(
                    LanguageManager.get('info_title'),
                    LanguageManager.get('custom_layout_not_found').format(fallback_layout=fallback_layout)
                )
        except Exception as e:
            logger.error(f"Error checking missing custom in settings: {e}")

    def _position_window(self):
        """Position window next to main window"""
        if self.parent and hasattr(self.parent, 'winfo_x') and self.parent.winfo_exists():
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
                
                self.window.geometry(f"720x750+{settings_x}+{settings_y}")
                
            except Exception:
                self.window.geometry("720x750+100+100")
        else:
            self.window.geometry("720x750+100+100")

    def _load_current_config(self):
        """Load current configuration"""
        self.config = ConfigManager.get_config()
        
        timing = self.config.get("timing_settings", {})
        delays = timing.get("delays", {})
        ramping = timing.get("ramping", {})
        
        self.current_delays = {
            "initial_delay": delays.get("initial_delay", 0.8),
            "pause_resume_delay": delays.get("pause_resume_delay", 1.0)
        }
        
        self.current_ramping = {
            "begin_steps": ramping.get("begin", {}).get("steps", 20),
            "end_steps": ramping.get("end", {}).get("steps", 16), 
            "after_pause_steps": ramping.get("after_pause", {}).get("steps", 12),
            "speed_change_steps": ramping.get("speed_change", {}).get("steps", 8)
        }
        
        ui_settings = self.config.get("ui_settings", {})
        self.current_ui = {
            "language": ui_settings.get("selected_language", "en_US"),
            "theme": ui_settings.get("theme", "dark"),
            "keyboard_layout": ui_settings.get("keyboard_layout", "QWERTY"),
            "pause_key": ui_settings.get("pause_key", "#")
        }

        game_settings = self.config.get("game_settings", {})
        self.current_game = {
            "sky_exe_path": game_settings.get("sky_exe_path", "")
        }

        playback_settings = self.config.get("playback_settings", {})
        self.current_playback = {
            "key_durations": playback_settings.get("key_press_durations", [0.2, 0.248, 0.3, 0.5, 1.0]),
            "speed_presets": playback_settings.get("speed_presets", [600, 800, 1000, 1200])
        }

        speed_change_settings = self.config.get("speed_change_settings", {})
        self.current_speed_change = {
            "enabled": speed_change_settings.get("enabled", False),
            "mode": speed_change_settings.get("mode", "preset"),
            "preset_mappings": speed_change_settings.get("preset_mappings", [
                {"key": "1", "speed": 600},
                {"key": "2", "speed": 800},
                {"key": "3", "speed": 1000},
                {"key": "4", "speed": 1200}
            ])
        }

    def _create_ui(self):
        """Create the user interface with scrollbar"""
        main_frame = ctk.CTkFrame(self.window)
        main_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        self.scrollable_frame = ctk.CTkScrollableFrame(
            main_frame, 
            width=580,
            height=550
        )
        self.scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        title_label = ctk.CTkLabel(
            self.scrollable_frame, 
            text=LanguageManager.get('settings_window_title'),
            font=("Arial", 20, "bold")
        )
        title_label.pack(pady=(0, 20))
        
        self._create_game_section(self.scrollable_frame)
        self._create_playback_section(self.scrollable_frame)
        self._create_speed_change_section(self.scrollable_frame)
        self._create_delays_section(self.scrollable_frame)
        self._create_ramping_section(self.scrollable_frame)
        self._create_interface_section(self.scrollable_frame)
        
        self._create_buttons_section(main_frame)

    def _create_game_section(self, parent):
        section_frame = ctk.CTkFrame(parent)
        section_frame.pack(fill="x", pady=(0, 15))
        
        title_label = ctk.CTkLabel(
            section_frame, 
            text=LanguageManager.get('settings_game_title'),
            font=("Arial", 16, "bold")
        )
        title_label.pack(anchor="w", pady=(10, 15), padx=10)
        
        path_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        path_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(path_frame, text=LanguageManager.get('settings_sky_path'), width=150).pack(side="left")
        
        self.sky_path_var = ctk.StringVar(value=self.current_game.get('sky_exe_path', ''))
        path_entry = ctk.CTkEntry(path_frame, textvariable=self.sky_path_var, width=250)
        path_entry.pack(side="left", padx=5, fill="x", expand=True)
        
        browse_btn = ctk.CTkButton(path_frame, text="...", width=30, command=self._browse_sky_exe)
        browse_btn.pack(side="left", padx=5)

    def _create_playback_section(self, parent):
        section_frame = ctk.CTkFrame(parent)
        section_frame.pack(fill="x", pady=(0, 15))
        
        title_label = ctk.CTkLabel(
            section_frame, 
            text=LanguageManager.get('settings_playback_title'),
            font=("Arial", 16, "bold")
        )
        title_label.pack(anchor="w", pady=(10, 15), padx=10)
        
        self._create_array_setting(
            section_frame, 'settings_key_durations', 'key_durations',
            [0.2, 0.248, 0.3, 0.5, 1.0], 'settings_key_durations_hint'
        )
        
        self._create_array_setting(
            section_frame, 'settings_speed_presets', 'speed_presets',
            [600, 800, 1000, 1200], 'settings_speed_presets_hint'
        )
        
        custom_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        custom_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(custom_frame, text=LanguageManager.get('settings_custom_keys'), width=150).pack(side="left")
        ctk.CTkButton(custom_frame, text=LanguageManager.get('settings_edit_keys'), command=self._open_key_editor, width=120).pack(side="left", padx=5)
        
        self.custom_keys_status = ctk.CTkLabel(
            custom_frame, text=self._get_custom_keys_status(),
            font=("Arial", 10), text_color="gray60"
        )
        self.custom_keys_status.pack(side="left", padx=10)

    def _create_speed_change_section(self, parent):
        """Create speed change during playback section - nur Preset Mode"""
        section_frame = ctk.CTkFrame(parent)
        section_frame.pack(fill="x", pady=(0, 15))
        
        title_label = ctk.CTkLabel(
            section_frame, 
            text=LanguageManager.get('settings_speed_change_title'),
            font=("Arial", 16, "bold")
        )
        title_label.pack(anchor="w", pady=(10, 15), padx=10)
        
        info_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        info_frame.pack(fill="x", padx=10, pady=5)
        
        info_text = LanguageManager.get('settings_speed_change_enable')
        ctk.CTkLabel(
            info_frame, 
            text=info_text,
            font=("Arial", 11),
            text_color="gray70",
            wraplength=600
        ).pack(side="left")

        self.preset_keys_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        self._create_preset_keys_ui()

    def _create_preset_keys_ui(self):
        """Create UI for flexible preset key-speed mappings in 2x2 grid"""
        for widget in self.preset_keys_frame.winfo_children():
            widget.destroy()
            
        self.preset_keys_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(self.preset_keys_frame, text=LanguageManager.get('settings_speed_change_preset_keys'), width=150).pack(side="left")
        
        grid_frame = ctk.CTkFrame(self.preset_keys_frame, fg_color="transparent")
        grid_frame.pack(side="left", padx=5, fill="x", expand=True)
        
        available_speeds = self.current_playback.get('speed_presets', [600, 800, 1000, 1200])
        speed_display_values = [f"{speed}" for speed in available_speeds]
        
        current_mappings = self.current_speed_change.get('preset_mappings', [
            {"key": "1", "speed": 600},
            {"key": "2", "speed": 800},
            {"key": "3", "speed": 1000},
            {"key": "4", "speed": 1200}
        ])
        
        self.preset_key_vars = []
        self.preset_speed_vars = []
        
        for row in range(2):
            row_frame = ctk.CTkFrame(grid_frame, fg_color="transparent")
            row_frame.pack(fill="x", pady=2)
            
            for col in range(2):
                preset_index = row * 2 + col
                if preset_index >= len(current_mappings):
                    break
                    
                preset_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
                preset_frame.pack(side="left", padx=15)
                
                ctk.CTkLabel(preset_frame, text=f"Preset {preset_index + 1}:").pack(side="left")
                
                key_var = ctk.StringVar(value=current_mappings[preset_index].get('key', f'{preset_index + 1}'))
                key_entry = ctk.CTkEntry(preset_frame, textvariable=key_var, width=60)
                key_entry.pack(side="left", padx=2)
                
                ctk.CTkLabel(preset_frame, text="→").pack(side="left", padx=5)
                
                current_speed = current_mappings[preset_index].get('speed', available_speeds[preset_index] if preset_index < len(available_speeds) else 600)
                speed_var = ctk.StringVar(value=f"{current_speed}")
                
                speed_dropdown = ctk.CTkComboBox(
                    preset_frame, 
                    values=speed_display_values,
                    variable=speed_var,
                    state="readonly",
                    width=80
                )
                speed_dropdown.pack(side="left", padx=2)
                
                self.preset_key_vars.append(key_var)
                self.preset_speed_vars.append(speed_var)

    def _on_speed_change_mode_changed(self, mode):
        """Handle speed change mode change"""
        if mode == "preset":
            self.preset_keys_frame.pack(fill="x", padx=10, pady=5)
            self.incremental_frame.pack_forget()
        else:
            self.preset_keys_frame.pack_forget()
            self.incremental_frame.pack(fill="x", padx=10, pady=5)

    def _create_array_setting(self, parent, label_key, config_key, default_values, hint_key):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(frame, text=LanguageManager.get(label_key), width=150).pack(side="left")
        
        current_value = self.current_playback.get(config_key, default_values)
        array_str = ", ".join(map(str, current_value))
        
        var = ctk.StringVar(value=array_str)
        entry = ctk.CTkEntry(frame, textvariable=var, width=200, placeholder_text=", ".join(map(str, default_values)))
        entry.pack(side="left", padx=5)
        
        setattr(self, f"{config_key}_var", var)
        
        ctk.CTkLabel(frame, text=LanguageManager.get(hint_key), font=("Arial", 10), text_color="gray60").pack(side="left", padx=10)

    def _browse_sky_exe(self):
        from tkinter import filedialog
        import os
        
        steam_paths = [
            "C:/Program Files (x86)/Steam/steamapps/common/Sky Children of the Light",
            "C:/Program Files/Steam/steamapps/common/Sky Children of the Light",
            os.path.expanduser("~/Steam/steamapps/common/Sky Children of the Light")
        ]
        
        initial_dir = None
        for path in steam_paths:
            if os.path.exists(path):
                initial_dir = path
                break
        
        if not initial_dir and self.sky_path_var.get():
            current_path = self.sky_path_var.get()
            if os.path.exists(os.path.dirname(current_path)):
                initial_dir = os.path.dirname(current_path)
        
        file = filedialog.askopenfilename(
            title=LanguageManager.get('select_sky_exe'),
            initialdir=initial_dir,
            filetypes=[("Sky Executable", "Sky.exe")]
        )
        if file:
            self.sky_path_var.set(file)

    def _open_key_editor(self):
        from key_editor import KeyEditorWindow
        
        def refresh_settings():
            self._load_current_config()
            self._update_ui_after_custom_save()
        
        KeyEditorWindow(self.window, refresh_settings)

    def _update_ui_after_custom_save(self):
        self._load_current_config()
        
        custom_file = Path("resources/layouts/CUSTOM.xml")
        custom_exists = custom_file.exists()
        
        self.custom_keys_status.configure(text=self._get_custom_keys_status())
        
        available_layouts = self._get_available_layouts()
        
        current_value = self.keyboard_layout_var.get()
        
        if current_value == "Custom" and not custom_exists:
            current_value = self._get_fallback_layout()
            logger.info(f"Auto-switched from deleted Custom to {current_value}")
        
        if current_value not in available_layouts:
            current_value = available_layouts[0] if available_layouts else "QWERTY"
        
        self.keyboard_layout_dropdown.configure(values=available_layouts)
        self.keyboard_layout_var.set(current_value)

    def _get_available_layouts(self):
        available_layouts = []
        layouts_dir = Path("resources/layouts")
        
        if layouts_dir.exists():
            for xml_file in layouts_dir.glob("*.xml"):
                layout_name = xml_file.stem
                if layout_name.upper() == "CUSTOM":
                    continue
                formatted_name = layout_name[0].upper() + layout_name[1:].lower()
                available_layouts.append(formatted_name)
        
        available_layouts.sort()
        
        custom_file = Path("resources/layouts/CUSTOM.xml")
        if custom_file.exists() and "Custom" not in available_layouts:
            available_layouts.append("Custom")
        
        return available_layouts

    def _get_fallback_layout(self):
        lang_code = self.config.get("ui_settings", {}).get("selected_language", "en_US")
        lang_to_layout = {
            "ar": "Arabic", "da": "QWERTY", "de": "QWERTZ", "en": "QWERTY",
            "en_US": "QWERTY", "es": "QWERTY", "fr": "AZERTY", "id": "QWERTY",
            "it": "QWERTY", "ja": "JIS", "ko_KR": "QWERTY", "mg_MG": "QWERTY",
            "nl": "QWERTY", "pl": "QWERTY", "pt": "QWERTY", "ru": "йцукен",
            "zh": "QWERTY",
        }
        return lang_to_layout.get(lang_code, "QWERTY")

    def _get_custom_keys_status(self):
        custom_file = Path("resources/layouts/CUSTOM.xml")
        
        if not custom_file.exists():
            return LanguageManager.get('settings_using_default_layout')
        
        current_layout = self.current_ui.get('keyboard_layout', '')
        if current_layout == "Custom":
            return LanguageManager.get('settings_custom_active')
        else:
            return LanguageManager.get('settings_custom_available')

    def _create_delays_section(self, parent):
        section_frame = ctk.CTkFrame(parent)
        section_frame.pack(fill="x", pady=(0, 15))
        
        title_label = ctk.CTkLabel(section_frame, text=LanguageManager.get('settings_delays_title'), font=("Arial", 16, "bold"))
        title_label.pack(anchor="w", pady=(10, 15), padx=10)
        
        self._create_delay_entry(section_frame, 'settings_initial_delay', 'initial_delay')
        self._create_delay_entry(section_frame, 'settings_pause_delay', 'pause_resume_delay')

    def _create_delay_entry(self, parent, label_key, config_key):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(frame, text=LanguageManager.get(label_key), width=150).pack(side="left")
        
        current_value = self.current_delays[config_key]
        var = ctk.StringVar(value=f"{current_value}")
        
        entry = ctk.CTkEntry(frame, textvariable=var, width=80)
        entry.pack(side="left", padx=5)
        ctk.CTkLabel(frame, text="s").pack(side="left")
        
        if config_key == 'initial_delay':
            self.initial_delay_var = var
        elif config_key == 'pause_resume_delay':
            self.pause_resume_delay_var = var
        
        logger.debug(f"Created delay entry: {config_key} = {current_value}")

    def _create_ramping_section(self, parent):
        """Create ramping section with speed change ramping"""
        section_frame = ctk.CTkFrame(parent)
        section_frame.pack(fill="x", pady=(0, 15))
        
        title_label = ctk.CTkLabel(section_frame, text=LanguageManager.get('settings_ramping_title'), font=("Arial", 16, "bold"))
        title_label.pack(anchor="w", pady=(10, 15), padx=10)
        
        self._create_ramping_entry(section_frame, 'settings_ramping_start', 'begin_steps', 'settings_ramping_start_hint')
        self._create_ramping_entry(section_frame, 'settings_ramping_end', 'end_steps', 'settings_ramping_end_hint')
        self._create_ramping_entry(section_frame, 'settings_ramping_after_pause', 'after_pause_steps', 'settings_ramping_pause_hint')
        
        ramp_steps_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        ramp_steps_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(ramp_steps_frame, text=LanguageManager.get('settings_speed_change_ramp_steps'), width=150).pack(side="left")
        
        step_options = ["2", "4", "6", "8", "12", "16", "20"]
        current_steps = str(self.current_ramping.get('speed_change_steps', 8))
        
        self.speed_change_ramp_steps_var = ctk.StringVar(value=current_steps)
        steps_dropdown = ctk.CTkComboBox(
            ramp_steps_frame, 
            values=step_options,
            variable=self.speed_change_ramp_steps_var,
            state="readonly",
            width=80
        )
        steps_dropdown.pack(side="left", padx=5)

    def _create_ramping_entry(self, parent, label_key, config_key, hint_key):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(frame, text=LanguageManager.get(label_key), width=150).pack(side="left")
        
        current_value = self.current_ramping[config_key]
        var = ctk.StringVar(value=str(current_value))
        
        entry = ctk.CTkEntry(frame, textvariable=var, width=80, placeholder_text="20")
        entry.pack(side="left", padx=5)

        if config_key == 'begin_steps':
            self.begin_steps_var = var
        elif config_key == 'end_steps':
            self.end_steps_var = var
        elif config_key == 'after_pause_steps':
            self.after_pause_steps_var = var
        
        ctk.CTkLabel(frame, text=LanguageManager.get(hint_key), font=("Arial", 10), text_color="gray60").pack(side="left", padx=10)

    def _create_interface_section(self, parent):
        section_frame = ctk.CTkFrame(parent)
        section_frame.pack(fill="x", pady=(0, 15))
        
        title_label = ctk.CTkLabel(section_frame, text=LanguageManager.get('settings_interface_title'), font=("Arial", 16, "bold"))
        title_label.pack(anchor="w", pady=(10, 15), padx=10)
        
        self._create_dropdown(section_frame, 'settings_language', 'language', 
                             [name for _, name, _ in LanguageManager.get_languages()], 
                             self.current_ui['language'])
        
        self._create_theme_selector(section_frame)
        
        available_layouts = self._get_available_layouts()
        current_layout = self.current_ui['keyboard_layout']
        if current_layout not in available_layouts:
            current_layout = available_layouts[0] if available_layouts else "QWERTY"
        
        self._create_dropdown(section_frame, 'settings_keyboard_layout', 'keyboard_layout',
                             available_layouts, current_layout)
        
        pause_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        pause_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(pause_frame, text=LanguageManager.get('settings_pause_key'), width=150).pack(side="left")
        self.pause_key_var = ctk.StringVar(value=self.current_ui['pause_key'])
        ctk.CTkEntry(pause_frame, textvariable=self.pause_key_var, width=50).pack(side="left")

    def _create_dropdown(self, parent, label_key, config_key, values, current_value):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(frame, text=LanguageManager.get(label_key), width=150).pack(side="left")
        
        display_value = current_value
        if config_key == 'language':
            for code, name, _ in LanguageManager.get_languages():
                if code == current_value:
                    display_value = name
                    break
        
        var = ctk.StringVar(value=display_value)
        dropdown = ctk.CTkComboBox(frame, values=values, variable=var, state="readonly", width=150)
        dropdown.pack(side="left")
        
        if config_key == 'keyboard_layout':
            self.keyboard_layout_dropdown = dropdown
            self.keyboard_layout_var = var
        
        setattr(self, f"{config_key}_var", var)
        return dropdown

    def _create_theme_selector(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(frame, text=LanguageManager.get('settings_theme'), width=150).pack(side="left")
        
        self.theme_var = ctk.StringVar(value=self.current_ui['theme'])
        
        theme_frame = ctk.CTkFrame(frame, fg_color="transparent")
        theme_frame.pack(side="left")
        
        for theme in ["dark", "light"]:
            radio = ctk.CTkRadioButton(
                theme_frame, text=LanguageManager.get(f'theme_{theme}'),
                variable=self.theme_var, value=theme
            )
            radio.pack(side="left", padx=10)

    def _create_buttons_section(self, parent):
        button_frame = ctk.CTkFrame(parent, fg_color="transparent")
        button_frame.pack(fill="x", pady=10, padx=10, side="bottom")
        
        ctk.CTkButton(button_frame, text=LanguageManager.get('settings_save'), command=self._save_settings, width=120, height=35).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text=LanguageManager.get('settings_reset'), command=self._reset_defaults, width=120, height=35, fg_color="#FF6B6B", hover_color="#FF5252").pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text=LanguageManager.get('settings_cancel'), command=self._on_close, width=120, height=35, fg_color="#666666", hover_color="#555555").pack(side="right", padx=5)

    def _setup_bindings(self):
        self.window.bind('<Return>', lambda e: self._save_settings())
        self.window.bind('<Escape>', lambda e: self._on_close())

    def _validate_inputs(self):
        try:            
            initial_delay = float(self.initial_delay_var.get().strip())
            pause_resume_delay = float(self.pause_resume_delay_var.get().strip())
            
            if initial_delay <= 0 or pause_resume_delay <= 0:
                return False, LanguageManager.get('settings_error_positive')
            
            begin_steps = int(self.begin_steps_var.get().strip())
            end_steps = int(self.end_steps_var.get().strip())
            after_pause_steps = int(self.after_pause_steps_var.get().strip())
            
            if begin_steps <= 0 or end_steps <= 0 or after_pause_steps <= 0:
                return False, LanguageManager.get('settings_error_positive')
            
            try:
                speed_change_steps = int(self.speed_change_ramp_steps_var.get().strip())
                if speed_change_steps <= 0:
                    return False, LanguageManager.get('settings_error_positive')
            except ValueError:
                return False, LanguageManager.get('settings_error_numbers')
            
            pause_key = self.pause_key_var.get().strip()
            if len(pause_key) != 1:
                return False, LanguageManager.get('settings_error_pause_key')
                
            return True, None
            
        except ValueError:
            return False, LanguageManager.get('settings_error_numbers')
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return False, LanguageManager.get('settings_error_general')

    def _save_settings(self):
        valid, error_msg = self._validate_inputs()
        if not valid:
            messagebox.showerror(LanguageManager.get('error_title'), error_msg)
            return
        
        try:
            original_lang = self.current_ui['language']
            original_layout = self.current_ui['keyboard_layout']
            original_theme = self.current_ui['theme']
            original_pause_key = self.current_ui['pause_key']
            
            updates = {}
            
            new_initial_delay = float(self.initial_delay_var.get())
            new_pause_delay = float(self.pause_resume_delay_var.get())
            new_begin_steps = int(self.begin_steps_var.get())
            new_end_steps = int(self.end_steps_var.get())
            new_after_pause_steps = int(self.after_pause_steps_var.get())
            new_speed_change_steps = int(self.speed_change_ramp_steps_var.get())
            
            timing_changed = (
                new_initial_delay != self.current_delays["initial_delay"] or
                new_pause_delay != self.current_delays["pause_resume_delay"] or
                new_begin_steps != self.current_ramping["begin_steps"] or
                new_end_steps != self.current_ramping["end_steps"] or
                new_after_pause_steps != self.current_ramping["after_pause_steps"] or
                new_speed_change_steps != self.current_ramping["speed_change_steps"]
            )
            
            if timing_changed:
                updates["timing_settings"] = {
                    "delays": {
                        "initial_delay": new_initial_delay,
                        "pause_resume_delay": new_pause_delay
                    },
                    "ramping": {
                        "begin": {"steps": new_begin_steps},
                        "end": {"steps": new_end_steps},
                        "after_pause": {"steps": new_after_pause_steps},
                        "speed_change": {"steps": new_speed_change_steps}
                    }
                }
            
            new_pause_key = self.pause_key_var.get()
            new_theme = self.theme_var.get()
            
            if new_pause_key != original_pause_key:
                if "ui_settings" not in updates:
                    updates["ui_settings"] = {}
                updates["ui_settings"]["pause_key"] = new_pause_key
            
            if new_theme != original_theme:
                if "ui_settings" not in updates:
                    updates["ui_settings"] = {}
                updates["ui_settings"]["theme"] = new_theme
            
            new_sky_path = self.sky_path_var.get()
            if new_sky_path != self.current_game['sky_exe_path']:
                updates["game_settings"] = {
                    "sky_exe_path": new_sky_path
                }

            new_key_durations = self._parse_array_setting(self.key_durations_var.get(), float)
            new_speed_presets = self._parse_array_setting(self.speed_presets_var.get(), int)
            
            playback_changed = (
                new_key_durations != self.current_playback['key_durations'] or
                new_speed_presets != self.current_playback['speed_presets']
            )
            
            if playback_changed:
                updates["playback_settings"] = {
                    "key_press_durations": new_key_durations,
                    "speed_presets": new_speed_presets
                }

            new_preset_mappings = []
            available_speeds = self.current_playback.get('speed_presets', [600, 800, 1000, 1200])

            for i, (key_var, speed_var) in enumerate(zip(self.preset_key_vars, self.preset_speed_vars)):
                if i >= 4:
                    break
                
                key = key_var.get().strip()
                speed_str = speed_var.get().strip()
                
                try:
                    speed = int(speed_str)
                    if speed not in available_speeds and available_speeds:
                        speed = available_speeds[0]
                except (ValueError, TypeError):
                    speed = available_speeds[i] if i < len(available_speeds) else 600
                    
                new_preset_mappings.append({
                    "key": key,
                    "speed": speed
                })

            current_mappings = self.current_speed_change.get('preset_mappings', [])
            speed_change_changed = new_preset_mappings != current_mappings

            speed_change_updates = {}
            if speed_change_changed:
                speed_change_updates["preset_mappings"] = new_preset_mappings
                if "speed_change_settings" not in updates:
                    updates["speed_change_settings"] = {}
                updates["speed_change_settings"]["preset_mappings"] = new_preset_mappings

            new_lang_code = self._get_selected_lang_code()
            layout_name = self.keyboard_layout_var.get()
            
            if new_lang_code != original_lang or layout_name != original_layout:
                if "ui_settings" not in updates:
                    updates["ui_settings"] = {}
                updates["ui_settings"]["selected_language"] = new_lang_code
                updates["ui_settings"]["keyboard_layout"] = layout_name

            if updates:
                if ConfigManager.save(updates):
                    if "timing_settings" in updates:
                        timing_updates = updates["timing_settings"]
                        if "delays" in timing_updates:
                            self.current_delays["initial_delay"] = timing_updates["delays"]["initial_delay"]
                            self.current_delays["pause_resume_delay"] = timing_updates["delays"]["pause_resume_delay"]
                        if "ramping" in timing_updates:
                            ramping = timing_updates["ramping"]
                            self.current_ramping["begin_steps"] = ramping["begin"]["steps"]
                            self.current_ramping["end_steps"] = ramping["end"]["steps"]
                            self.current_ramping["after_pause_steps"] = ramping["after_pause"]["steps"]
                            self.current_ramping["speed_change_steps"] = ramping["speed_change"]["steps"]

                    if "playback_settings" in updates:
                        playback = updates["playback_settings"]
                        self.current_playback["key_durations"] = playback["key_press_durations"]
                        self.current_playback["speed_presets"] = playback["speed_presets"]

                    if "speed_change_settings" in updates:
                        speed_change = updates["speed_change_settings"]
                        if "preset_mappings" in speed_change:
                            self.current_speed_change["preset_mappings"] = speed_change["preset_mappings"]
                    
                    logger.debug("Current config updated after successful save")

                    if new_pause_key != original_pause_key and hasattr(self, 'pause_key_callback'):
                        self.pause_key_callback(new_pause_key)
                    
                    if new_theme != original_theme and self.theme_callback:
                        self.theme_callback(new_theme)
                        ctk.set_appearance_mode(new_theme)

                    if "timing_settings" in updates and self.timing_callback:
                        timing_updates = updates["timing_settings"]
                        if "delays" not in timing_updates:
                            timing_updates["delays"] = {
                                "initial_delay": self.current_delays["initial_delay"],
                                "pause_resume_delay": self.current_delays["pause_resume_delay"]
                            }
                        self.timing_callback(timing_updates)
                    
                    if "playback_settings" in updates and self.playback_callback:
                        self.playback_callback(updates["playback_settings"])
                    
                    if speed_change_changed and hasattr(self, 'speed_change_callback'):
                        self.speed_change_callback(speed_change_updates)
                    
                    needs_restart = (original_layout != layout_name) or (original_lang != new_lang_code)
                    
                    if needs_restart:
                        if messagebox.askyesno(
                            LanguageManager.get('info_title'),
                            LanguageManager.get('settings_restart_required') + "\n\n" + LanguageManager.get('settings_restart_now')
                        ):
                            self._restart_main_application()
                            return
                        else:
                            messagebox.showinfo(LanguageManager.get('info_title'), LanguageManager.get('settings_restart_later'))
                    else:
                        messagebox.showinfo(LanguageManager.get('info_title'), LanguageManager.get('settings_saved'))
                else:
                    messagebox.showerror(LanguageManager.get('error_title'), LanguageManager.get('settings_save_error'))
            else:
                messagebox.showinfo(LanguageManager.get('info_title'), LanguageManager.get('settings_no_changes'))
                    
        except Exception as e:
            logger.error(f"Error saving settings: {e}", exc_info=True)
            messagebox.showerror(LanguageManager.get('error_title'), LanguageManager.get('settings_save_error'))

    def _get_custom_file_hash(self):
        try:
            custom_file = Path("resources/layouts/CUSTOM.xml")
            if custom_file.exists():
                content = custom_file.read_text(encoding='utf-8')
                return hash(content)
            return None
        except Exception as e:
            logger.error(f"Error getting custom file hash: {e}")
            return None

    def _restart_main_application(self):
        try:
            import subprocess
            import sys
            import os
            import time
            
            python = sys.executable
            script = os.path.abspath(sys.argv[0])
            
            self._on_close()
            time.sleep(0.5)
            
            subprocess.Popen([python, script])

            if self.parent:
                self.parent.destroy()
            
        except Exception as e:
            logger.error(f"Failed to restart main application: {e}")
            messagebox.showerror(LanguageManager.get('error_title'), LanguageManager.get('settings_restart_failed'))

    def _parse_array_setting(self, value_str, converter):
        try:
            if not value_str.strip():
                return []
            values = [converter(x.strip()) for x in value_str.split(",") if x.strip()]
            return values
        except ValueError:
            raise ValueError(f"Invalid array format: {value_str}")

    def _get_selected_lang_code(self):
        lang_name = self.language_var.get()
        for code, name, _ in LanguageManager.get_languages():
            if name == lang_name:
                return code
        return "en_US"

    def _reset_defaults(self):
        if messagebox.askyesno(LanguageManager.get('warning_title'), LanguageManager.get('settings_reset_confirm')):
            if ConfigManager.reset_to_defaults():
                messagebox.showinfo(LanguageManager.get('info_title'), LanguageManager.get('settings_reset_success'))
                self._on_close()
            else:
                messagebox.showerror(LanguageManager.get('error_title'), LanguageManager.get('settings_reset_error'))

    def _on_close(self):
        try:
            try:
                self.window.grab_release()
            except:
                pass

            if self in SettingsWindow._open_windows:
                SettingsWindow._open_windows.remove(self)

            if hasattr(self, 'window') and self.window.winfo_exists():
                self.window.destroy()
                
        except Exception as e:
            SettingsWindow._open_windows.clear()

    @classmethod
    def is_open(cls):
        return len(cls._open_windows) > 0