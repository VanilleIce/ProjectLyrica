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
    
    def __init__(self, parent=None, theme_callback=None, timing_callback=None, playback_callback=None):
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
        self.window.geometry("620x680")
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
                if settings_x + 620 > screen_width:
                    settings_x = max(0, screen_width - 620 - 10)
                
                self.window.geometry(f"620x680+{settings_x}+{settings_y}")
                
            except Exception:
                # Fallback Position
                self.window.geometry("620x680+100+100")
        else:
            # Fallback Position
            self.window.geometry("620x680+100+100")

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
            "after_pause_steps": ramping.get("after_pause", {}).get("steps", 12)
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

    def _create_ui(self):
        """Create the user interface with scrollbar"""
        main_frame = ctk.CTkFrame(self.window)
        main_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Scrollable frame
        self.scrollable_frame = ctk.CTkScrollableFrame(
            main_frame, 
            width=480,
            height=500
        )
        self.scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Title
        title_label = ctk.CTkLabel(
            self.scrollable_frame, 
            text=LanguageManager.get('settings_window_title'),
            font=("Arial", 20, "bold")
        )
        title_label.pack(pady=(0, 20))
        
        # Sections
        self._create_game_section(self.scrollable_frame)
        self._create_playback_section(self.scrollable_frame)
        self._create_delays_section(self.scrollable_frame)
        self._create_ramping_section(self.scrollable_frame)
        self._create_interface_section(self.scrollable_frame)
        
        # Buttons
        self._create_buttons_section(main_frame)

    def _create_game_section(self, parent):
        """Create Game Settings section"""
        section_frame = ctk.CTkFrame(parent)
        section_frame.pack(fill="x", pady=(0, 15))
        
        title_label = ctk.CTkLabel(
            section_frame, 
            text=LanguageManager.get('settings_game_title'),
            font=("Arial", 16, "bold")
        )
        title_label.pack(anchor="w", pady=(10, 15), padx=10)
        
        # Sky.exe Path
        path_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        path_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(path_frame, text=LanguageManager.get('settings_sky_path'), width=150).pack(side="left")
        
        self.sky_path_var = ctk.StringVar(value=self.current_game.get('sky_exe_path', ''))
        path_entry = ctk.CTkEntry(path_frame, textvariable=self.sky_path_var, width=250)
        path_entry.pack(side="left", padx=5, fill="x", expand=True)
        
        browse_btn = ctk.CTkButton(path_frame, text="...", width=30, command=self._browse_sky_exe)
        browse_btn.pack(side="left", padx=5)

    def _create_playback_section(self, parent):
        """Create Playback Settings section"""
        section_frame = ctk.CTkFrame(parent)
        section_frame.pack(fill="x", pady=(0, 15))
        
        title_label = ctk.CTkLabel(
            section_frame, 
            text=LanguageManager.get('settings_playback_title'),
            font=("Arial", 16, "bold")
        )
        title_label.pack(anchor="w", pady=(10, 15), padx=10)
        
        # Key Press Durations
        self._create_array_setting(
            section_frame, 'settings_key_durations', 'key_durations',
            [0.2, 0.248, 0.3, 0.5, 1.0], 'settings_key_durations_hint'
        )
        
        # Speed Presets
        self._create_array_setting(
            section_frame, 'settings_speed_presets', 'speed_presets',
            [600, 800, 1000, 1200], 'settings_speed_presets_hint'
        )
        
        # Custom Key Mapping
        custom_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        custom_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(custom_frame, text=LanguageManager.get('settings_custom_keys'), width=150).pack(side="left")
        ctk.CTkButton(custom_frame, text=LanguageManager.get('settings_edit_keys'), command=self._open_key_editor, width=120).pack(side="left", padx=5)
        
        self.custom_keys_status = ctk.CTkLabel(
            custom_frame, text=self._get_custom_keys_status(),
            font=("Arial", 10), text_color="gray60"
        )
        self.custom_keys_status.pack(side="left", padx=10)

    def _create_array_setting(self, parent, label_key, config_key, default_values, hint_key):
        """Create an array setting (durations, presets)"""
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
        """Open file dialogue for Sky.exe"""
        from tkinter import filedialog
        import os
        
        # Standard Steam Pfade
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
        """Open the Key Mapping Editor"""
        from key_editor import KeyEditorWindow
        
        def refresh_settings():
            """Update UI after key editor"""
            self._load_current_config()
            self._update_ui_after_custom_save()
        
        KeyEditorWindow(self.window, refresh_settings)

    def _update_ui_after_custom_save(self):
        """Update the UI after custom changes"""
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
        """Determine available layouts"""
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
        """Determines fallback layout based on language"""
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
        """Get status of custom key mapping"""
        custom_file = Path("resources/layouts/CUSTOM.xml")
        
        if not custom_file.exists():
            return LanguageManager.get('settings_using_default_layout')
        
        current_layout = self.current_ui.get('keyboard_layout', '')
        if current_layout == "Custom":
            return LanguageManager.get('settings_custom_active')
        else:
            return LanguageManager.get('settings_custom_available')

    def _create_delays_section(self, parent):
        """Create Delays Section"""
        section_frame = ctk.CTkFrame(parent)
        section_frame.pack(fill="x", pady=(0, 15))
        
        title_label = ctk.CTkLabel(section_frame, text=LanguageManager.get('settings_delays_title'), font=("Arial", 16, "bold"))
        title_label.pack(anchor="w", pady=(10, 15), padx=10)
        
        # Initial Delay
        self._create_delay_entry(section_frame, 'settings_initial_delay', 'initial_delay')
        
        # Pause-Resume Delay
        self._create_delay_entry(section_frame, 'settings_pause_delay', 'pause_resume_delay')

    def _create_delay_entry(self, parent, label_key, config_key):
        """Create a delay entry"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(frame, text=LanguageManager.get(label_key), width=150).pack(side="left")
        
        current_value = self.current_delays[config_key]
        var = ctk.StringVar(value=f"{current_value}")
        
        entry = ctk.CTkEntry(frame, textvariable=var, width=80)
        entry.pack(side="left", padx=5)
        ctk.CTkLabel(frame, text="s").pack(side="left")
        
        setattr(self, f"{config_key}_var", var)

    def _create_ramping_section(self, parent):
        """Create ramping section"""
        section_frame = ctk.CTkFrame(parent)
        section_frame.pack(fill="x", pady=(0, 15))
        
        title_label = ctk.CTkLabel(section_frame, text=LanguageManager.get('settings_ramping_title'), font=("Arial", 16, "bold"))
        title_label.pack(anchor="w", pady=(10, 15), padx=10)
        
        self._create_ramping_entry(section_frame, 'settings_ramping_start', 'begin_steps', 'settings_ramping_start_hint')
        self._create_ramping_entry(section_frame, 'settings_ramping_end', 'end_steps', 'settings_ramping_end_hint')
        self._create_ramping_entry(section_frame, 'settings_ramping_after_pause', 'after_pause_steps', 'settings_ramping_pause_hint')

    def _create_ramping_entry(self, parent, label_key, config_key, hint_key):
        """Create a ramping entry"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(frame, text=LanguageManager.get(label_key), width=150).pack(side="left")
        
        current_value = self.current_ramping[config_key]
        var = ctk.StringVar(value=str(current_value))
        
        entry = ctk.CTkEntry(frame, textvariable=var, width=80, placeholder_text="20")
        entry.pack(side="left", padx=5)
        
        setattr(self, f"{config_key}_var", var)
        
        ctk.CTkLabel(frame, text=LanguageManager.get(hint_key), font=("Arial", 10), text_color="gray60").pack(side="left", padx=10)

    def _create_interface_section(self, parent):
        """Create interface section"""
        section_frame = ctk.CTkFrame(parent)
        section_frame.pack(fill="x", pady=(0, 15))
        
        title_label = ctk.CTkLabel(section_frame, text=LanguageManager.get('settings_interface_title'), font=("Arial", 16, "bold"))
        title_label.pack(anchor="w", pady=(10, 15), padx=10)
        
        # Language
        self._create_dropdown(section_frame, 'settings_language', 'language', 
                             [name for _, name, _ in LanguageManager.get_languages()], 
                             self.current_ui['language'])
        
        # Theme
        self._create_theme_selector(section_frame)
        
        # Keyboard Layout
        available_layouts = self._get_available_layouts()
        current_layout = self.current_ui['keyboard_layout']
        if current_layout not in available_layouts:
            current_layout = available_layouts[0] if available_layouts else "QWERTY"
        
        self._create_dropdown(section_frame, 'settings_keyboard_layout', 'keyboard_layout',
                             available_layouts, current_layout)
        
        # Pause Key
        pause_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        pause_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(pause_frame, text=LanguageManager.get('settings_pause_key'), width=150).pack(side="left")
        self.pause_key_var = ctk.StringVar(value=self.current_ui['pause_key'])
        ctk.CTkEntry(pause_frame, textvariable=self.pause_key_var, width=50).pack(side="left")

    def _create_dropdown(self, parent, label_key, config_key, values, current_value):
        """Create a drop-down menu"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(frame, text=LanguageManager.get(label_key), width=150).pack(side="left")
        
        # Find display value
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

    def _create_theme_selector(self, parent):
        """Create theme selection"""
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
        """Create buttons section"""
        button_frame = ctk.CTkFrame(parent, fg_color="transparent")
        button_frame.pack(fill="x", pady=10, padx=10, side="bottom")
        
        ctk.CTkButton(button_frame, text=LanguageManager.get('settings_save'), command=self._save_settings, width=120, height=35).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text=LanguageManager.get('settings_reset'), command=self._reset_defaults, width=120, height=35, fg_color="#FF6B6B", hover_color="#FF5252").pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text=LanguageManager.get('settings_cancel'), command=self._on_close, width=120, height=35, fg_color="#666666", hover_color="#555555").pack(side="right", padx=5)

    def _setup_bindings(self):
        """Setup Event Bindings"""
        self.window.bind('<Return>', lambda e: self._save_settings())
        self.window.bind('<Escape>', lambda e: self._on_close())

    def _validate_inputs(self):
        """Validate all entries - numeric values only"""
        try:            
            # Delays
            initial_delay = float(self.initial_delay_var.get().strip())
            pause_resume_delay = float(self.pause_resume_delay_var.get().strip())
            
            if initial_delay <= 0 or pause_resume_delay <= 0:
                return False, LanguageManager.get('settings_error_positive')
            
            # Ramping Steps
            begin_steps = int(self.begin_steps_var.get().strip())
            end_steps = int(self.end_steps_var.get().strip())
            after_pause_steps = int(self.after_pause_steps_var.get().strip())
            
            if begin_steps <= 0 or end_steps <= 0 or after_pause_steps <= 0:
                return False, LanguageManager.get('settings_error_positive')
                
            # Pause Key
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
        """Save settings"""
        valid, error_msg = self._validate_inputs()
        if not valid:
            messagebox.showerror(LanguageManager.get('error_title'), error_msg)
            return
        
        try:
            original_lang = self.current_ui['language']
            original_layout = self.current_ui['keyboard_layout']
            original_theme = self.current_ui['theme']
            
            timing_updates = {
                "delays": {
                    "initial_delay": float(self.initial_delay_var.get()),
                    "pause_resume_delay": float(self.pause_resume_delay_var.get())
                },
                "ramping": {
                    "begin": {"steps": int(self.begin_steps_var.get())},
                    "end": {"steps": int(self.end_steps_var.get())},
                    "after_pause": {"steps": int(self.after_pause_steps_var.get())}
                }
            }
            
            playback_updates = {
                "key_press_durations": self._parse_array_setting(self.key_durations_var.get(), float),
                "speed_presets": self._parse_array_setting(self.speed_presets_var.get(), int)
            }
            
            ui_updates = {
                "pause_key": self.pause_key_var.get(),
                "theme": self.theme_var.get()
            }
            
            game_updates = {
                "sky_exe_path": self.sky_path_var.get()
            }
            
            updates = {
                "timing_settings": timing_updates,
                "ui_settings": ui_updates,
                "game_settings": game_updates,
                "playback_settings": playback_updates
            }
            
            new_lang_code = self._get_selected_lang_code()
            updates["ui_settings"]["selected_language"] = new_lang_code
            
            layout_name = self.keyboard_layout_var.get()
            updates["ui_settings"]["keyboard_layout"] = layout_name
            
            needs_restart = (original_layout != layout_name) or (original_lang != new_lang_code)
            
            if ConfigManager.save(updates):
                
                # Theme
                new_theme = self.theme_var.get()
                ctk.set_appearance_mode(new_theme)
                if self.theme_callback:
                    self.theme_callback(new_theme)
                
                # Timing-settings
                if self.timing_callback:
                    self.timing_callback(timing_updates)
                
                # Playback-settings  
                if self.playback_callback:
                    self.playback_callback(playback_updates)
                
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
                
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            messagebox.showerror(LanguageManager.get('error_title'), LanguageManager.get('settings_save_error'))

    def _get_custom_file_hash(self):
        """Creates hash of custom file contents"""
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
        """Restarts the main application"""
        
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
        """Parse array settings from string"""
        try:
            if not value_str.strip():
                return []
            values = [converter(x.strip()) for x in value_str.split(",") if x.strip()]
            return values
        except ValueError:
            raise ValueError(f"Invalid array format: {value_str}")

    def _get_selected_lang_code(self):
        """Retrieves language code from selected name"""
        lang_name = self.language_var.get()
        for code, name, _ in LanguageManager.get_languages():
            if name == lang_name:
                return code
        return "en_US"

    def _reset_defaults(self):
        """Reset default values"""
        if messagebox.askyesno(LanguageManager.get('warning_title'), LanguageManager.get('settings_reset_confirm')):
            if ConfigManager.reset_to_defaults():
                messagebox.showinfo(LanguageManager.get('info_title'), LanguageManager.get('settings_reset_success'))
                self._on_close()
            else:
                messagebox.showerror(LanguageManager.get('error_title'), LanguageManager.get('settings_reset_error'))

    def _on_close(self):
        """Close the window and release all grabs"""
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
        """Check whether a settings window is open."""
        return len(cls._open_windows) > 0