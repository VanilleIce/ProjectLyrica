# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import json, time, os, sys, winsound, ctypes, webbrowser, logging
import customtkinter as ctk
from pathlib import Path
from threading import Event, Thread
from pynput.keyboard import Listener, Key
from tkinter import filedialog, messagebox
import xml.etree.ElementTree as ET

from update_checker import check_update
from logging_setup import setup_logging
from config_manager import ConfigManager
from language_manager import LanguageManager, KeyboardLayoutManager
from language_window import LanguageWindow
from sky_checker import SkyChecker
from music_player import MusicPlayer
from resource_loader import resource_path

logger = logging.getLogger("ProjectLyrica.ProjectLyrica")

# -------------------------------
# Constants
# -------------------------------

DEFAULT_WINDOW_SIZE = (400, 355)
EXPANDED_SIZE = (400, 455)
FULL_SIZE = (400, 535)
RAMPING_INFO_HEIGHT = 55
MAX_RAMPING_INFO_DISPLAY = 6
VERSION = "2.7.0"

# -------------------------------
# Music App
# -------------------------------

class MusicApp:
    def __init__(self):
        setup_logging(VERSION)
        self._check_running()

        self.config = ConfigManager.get_config()

        try:
            custom_was_missing, fallback_layout = ConfigManager.check_and_handle_missing_custom()
            if custom_was_missing:
                logger.info(f"Custom layout was missing, switched to {fallback_layout}")
                self.config = ConfigManager.get_config()
        except Exception as e:
            logger.error(f"Error handling missing custom layout: {e}")

        self._init_language()

        if ConfigManager.get_value("game_settings.sky_exe_path") is None:
            SkyChecker.show_initial_settings()
            self.config = ConfigManager.get_config()

        self._last_sky_check = 0
        self._sky_running_cache = False

        self._init_player()    
        self._init_gui()

        self.current_play_state = "ready"
        self._start_sky_check()

        self._setup_key_listener()

        ConfigManager.log_system_info(VERSION)

    def _start_sky_check(self):
        def check_sky():
            try:
                if self.current_play_state in ["ready", "disabled"]:
                    self._update_play_button_state("ready")
                
                self.root.after(2000, check_sky)
            except Exception as e:
                logger.error(f"Sky check timer error: {e}")
                self.root.after(5000, check_sky)
        
        check_sky()

    def _update_play_button_based_on_sky(self):
        if not hasattr(self, 'player') or self.player is None:
            self._update_play_button_state("disabled")
            return
            
        sky_running = self._check_sky_running()
        has_file = bool(self.selected_file)

        if self.player.playback_active and self.player.pause_flag.is_set():
            self._update_play_button_state("paused")
        elif not sky_running or not has_file:
            self._update_play_button_state("disabled")
        else:
            self._update_play_button_state("ready")

    def _check_sky_running(self, use_cache=True):
        try:
            current_time = time.time()
            
            if use_cache and current_time - self._last_sky_check < 1:
                return self._sky_running_cache
            
            if hasattr(self, 'player') and self.player is not None:
                window = self.player._find_sky_window()
                result = window is not None

                self._sky_running_cache = result
                self._last_sky_check = current_time
                return result
            return False
        except Exception as e:
            logger.error(f"Error checking if Sky is running: {e}")
            return False

    def _init_language(self):
        LanguageManager.init()
        ui_language = self.config.get("ui_settings", {}).get("selected_language")
        
        if not ui_language:
            LanguageWindow.show()
            self.config = ConfigManager.get_config()

    def _check_running(self):
        self._mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "ProjectLyricaMutex")
        if ctypes.windll.kernel32.GetLastError() == 183:
            messagebox.showerror("Error", "Application is already running!")
            sys.exit(1)

    def _init_player(self):
        config = self.config
        
        self.player = MusicPlayer(config)
        self.selected_file = None

        playback_settings = config.get("playback_settings", {})
        ui_settings = config.get("ui_settings", {})
        
        self.duration_presets = playback_settings.get("key_press_durations")
        self.speed_presets = playback_settings.get("speed_presets")
        self.pause_key = ui_settings.get("pause_key")
        
        speed_change_settings = config.get("speed_change_settings", {})
        self.speed_change_config = speed_change_settings
        
        self.keypress_enabled = False
        self.speed_enabled = False
        self.current_speed_value = 1000
        self.smooth_ramping_enabled = playback_settings.get("enable_ramping")
        
        ramping_count_config = config.get("ramping_info_display_count", {})
        self.ramping_info_display_count = min(ramping_count_config.get("value", 0), MAX_RAMPING_INFO_DISPLAY)
        self.show_ramping_info = self.ramping_info_display_count < MAX_RAMPING_INFO_DISPLAY

    def _setup_key_listener(self):
        try:
            self.key_listener = Listener(on_press=self._handle_keypress)
            self.key_listener.start()
        except Exception as e:
            logger.error(f"Failed to start key listener: {e}")
            messagebox.showerror("Error", "Failed to initialize keyboard listener")

    def _init_gui(self):
        try:
            self.root = ctk.CTk()
            self.root.title(LanguageManager.get("project_title"))
            self.root.iconbitmap(resource_path("resources/icons/icon.ico"))
            self.root.protocol('WM_DELETE_WINDOW', self._shutdown)
            
            theme = self.config.get("ui_settings", {}).get("theme", "dark")
            ctk.set_appearance_mode(theme)
            
            self.update_status, self.latest_version, self.update_url = self._check_updates()
            self._create_gui_components()
            self._setup_gui_layout()

        except Exception as e:
            logger.critical(f"GUI initialization failed: {e}", exc_info=True)
            if hasattr(self, 'root'):
                self.root.destroy()
            raise

    def _check_updates(self):
        try:
            return check_update(VERSION, "VanilleIce/ProjectLyrica")
        except Exception as e:
            logger.error(f"Update check failed: {e}")
            return ("error", "", "")

    def _create_gui_components(self):
        if self.update_status == "update":
            self.version_text = LanguageManager.get('update_available_text').format(self.latest_version)
            self.version_color = "#FFA500"
        elif self.update_status == "no_connection":
            self.version_text = LanguageManager.get('no_connection_text')
            self.version_color = "#FF0000"
        else:
            self.version_text = LanguageManager.get('current_version_text').format(VERSION)
            self.version_color = "#1E90FF"
        
        self.file_btn = self._create_button(
            LanguageManager.get("file_select_title"), 
            self._select_file, 300, 40, True
        )
        
        self.keypress_btn = self._create_button(
            f"{LanguageManager.get('key_press')}: {LanguageManager.get('disabled')}", 
            self._toggle_keypress
        )
        
        speed_display_text = f"{LanguageManager.get('speed_control')}: {LanguageManager.get('disabled')}"
        self.speed_btn = self._create_button(
            speed_display_text, 
            self._toggle_speed
        )

        self.ramping_btn = self._create_button(
            f"{LanguageManager.get('smooth_ramping')}: {LanguageManager.get('enabled' if self.smooth_ramping_enabled else 'disabled')}", 
            self._toggle_smooth_ramping
        )
        
        self.play_btn = self._create_button(
            LanguageManager.get("play_button_text"), 
            None, 200, 40, True
        )
        
        self.duration_frame = ctk.CTkFrame(self.root)
        self.duration_slider = ctk.CTkSlider(
            self.duration_frame, from_=0.1, to=1.0, 
            number_of_steps=90, width=100
        )
        self.duration_slider.set(0.1)
        self.duration_slider.bind("<B1-Motion>", self._set_duration)
        
        self.duration_label = ctk.CTkLabel(
            self.duration_frame, 
            text=f"{LanguageManager.get('duration')} 0.1 s",
            font=("Arial", 12)
        )
        
        self.preset_frame = ctk.CTkFrame(self.duration_frame)
        if hasattr(self, 'duration_presets') and self.duration_presets:
            for preset in self.duration_presets:
                btn = ctk.CTkButton(
                    self.preset_frame, text=f"{preset} s", width=50,
                    command=lambda p=preset: self._apply_preset(p)
                )
                btn.pack(side="left", padx=2)
        
        self.speed_frame = ctk.CTkFrame(self.root)
        
        current_speed = self.player.get_current_speed()
        self.speed_label = ctk.CTkLabel(
            self.speed_frame,
            text=f"{LanguageManager.get('current_speed')}: {current_speed}",
            font=("Arial", 12)
        )
        
        self.speed_preset_frame = ctk.CTkFrame(self.speed_frame)
        if hasattr(self, 'speed_presets') and self.speed_presets:
            for speed in self.speed_presets:
                if speed <= 0:
                    continue
                    
                btn = ctk.CTkButton(
                    self.speed_preset_frame, 
                    text=str(speed), 
                    width=40,
                    height=25,
                    font=("Arial", 12),
                    command=lambda s=speed: self._set_speed(s)
                )
                btn.pack(side="left", padx=2)
        
        self.ramping_frame = ctk.CTkFrame(self.root)
        self.ramping_label = ctk.CTkLabel(
            self.ramping_frame,
            text=LanguageManager.get('smooth_ramping_info'),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            wraplength=350,
            justify="left"
        )
        self.ramping_label.pack(pady=5, padx=5)

    def _create_button(self, text, command, width=200, height=30, main=False):
        btn = ctk.CTkButton(
            self.root, text=text, command=command,
            font=("Arial", 14 if main else 13),
            width=width, height=height
        )
        return btn

    def _update_play_button_state(self, state):
        logger.debug(f"Update play button state: {state}")
        
        self.current_play_state = state
        
        if state == "playing":
            self.play_btn.configure(
                text=LanguageManager.get("playing_button_text"),
                command=None,
                fg_color="#666666",
                hover_color="#666666",
                text_color="#ffffff",
                state="disabled"
            )
        elif state == "paused":
            has_different_file = False
            if (hasattr(self, '_originally_paused_file') and 
                self._originally_paused_file is not None and 
                self.selected_file is not None):
                
                has_different_file = (self._originally_paused_file != self.selected_file)
            
            pause_key_hint = LanguageManager.get("pause_key_hint").replace("[pause_key]", self.pause_key)
            
            if has_different_file:
                self.play_btn.configure(
                    text=f"{LanguageManager.get('play_button_text')}\n{pause_key_hint}",
                    command=self._play_song,
                    fg_color="#8B4B8B",
                    hover_color="#6A3A6A",
                    text_color="#ffffff",
                    state="normal",
                    height=50
                )
            else:
                self.play_btn.configure(
                    text=f"{LanguageManager.get('restart_button_text')}\n{pause_key_hint}",
                    command=self._play_song,
                    fg_color="#D2691E",
                    hover_color="#A0522D",
                    text_color="#ffffff",
                    state="normal",
                    height=50
                )
                
        elif state == "ready":
            sky_running = self._check_sky_running(use_cache=False)
            has_file = bool(self.selected_file)
            
            if sky_running and has_file:
                self.play_btn.configure(
                    text=LanguageManager.get("play_button_text"),
                    command=self._play_song,
                    fg_color="#2b6cb0",
                    hover_color="#1f538d",
                    text_color="#ffffff",
                    state="normal",
                    height=40
                )
            elif not sky_running:
                self.play_btn.configure(
                    text=LanguageManager.get("sky_only_warning"),
                    command=None,
                    fg_color="#666666",
                    hover_color="#666666",
                    text_color="#aaaaaa",
                    state="disabled",
                    height=40
                )
            else:
                self.play_btn.configure(
                    text=LanguageManager.get("play_button_text"),
                    command=None,
                    fg_color="#666666",
                    hover_color="#666666",
                    text_color="#aaaaaa",
                    state="disabled",
                    height=40
                )
        elif state == "disabled":
            self.play_btn.configure(
                text=LanguageManager.get("play_button_text"),
                command=None,
                fg_color="#666666",
                hover_color="#666666",
                text_color="#aaaaaa",
                state="disabled",
                height=40
            )

        self.root.update_idletasks()

    def _stop_song(self):
        """Stops playback completely"""
        if self.player.playback_active:
            self.player.stop()
            self._update_play_button_state("ready")

    def _setup_gui_layout(self):
        status_frame = ctk.CTkFrame(self.root, height=1, fg_color="transparent")
        status_frame.pack(side="bottom", fill="x", padx=10, pady=3)
        
        self.version_link = ctk.CTkLabel(
            status_frame,
            text=self.version_text,
            font=("Arial", 11),
            text_color=self.version_color,
            cursor="hand2"
        )
        self.version_link.pack(side="right")
        self.version_link.bind("<Button-1>", self._open_releases)

        current_theme = self.config.get("ui_settings", {}).get("theme", "dark")
        
        self.settings_btn = ctk.CTkButton(
            status_frame,
            text="⚙️", 
            width=8,
            height=20,
            font=("Arial", 16),
            command=self._open_settings,
            fg_color="transparent",
            border_width=0
        )
        self.settings_btn.pack(side="right", padx=(0, 5))
        
        ctk.CTkLabel(self.root, text=LanguageManager.get("project_title"), 
                    font=("Arial", 18, "bold")).pack(pady=10)
        self.file_btn.pack(pady=10)
        self.keypress_btn.pack(pady=10)
        self.speed_btn.pack(pady=10)
        self.ramping_btn.pack(pady=10)
        
        self.play_btn.pack(pady=10)
        
        if not self.smooth_ramping_enabled and self.show_ramping_info:
            self.ramping_frame.pack(pady=5, before=self.play_btn)
        
        self._adjust_window_size()

    def _open_settings(self):
        from settings_window import SettingsWindow
        
        SettingsWindow(
            parent=self.root,
            theme_callback=self._on_theme_changed,
            timing_callback=self._on_timing_changed,
            playback_callback=self._on_playback_changed,
            pause_key_callback=self._on_pause_key_changed,
            speed_change_callback=self._on_speed_change_changed
        )

    def _on_speed_change_changed(self, speed_change_updates):
        """Handle speed change settings updates"""
        logger.info(f"Speed change settings updated: {speed_change_updates}")
        
        self.config = ConfigManager.get_config()
        
        speed_change_settings = self.config.get("speed_change_settings", {})
        self.speed_change_config = speed_change_settings
        
        if "preset_mappings" in speed_change_updates:
            logger.info("Speed change preset mappings updated")

    def _on_pause_key_changed(self, new_pause_key):
        logger.info(f"Pause key changed to: '{new_pause_key}'")
        self.pause_key = new_pause_key
        
        if self.current_play_state == "paused":
            self._update_play_button_state("paused")

    def _on_theme_changed(self, new_theme):
        logger.info(f"Theme changed to: {new_theme}")

        from settings_window import SettingsWindow
        if SettingsWindow.is_open():
            for window in SettingsWindow._open_windows[:]:
                try:
                    window._on_close()
                except:
                    pass
            SettingsWindow._open_windows.clear()

        text_color = "#FFFFFF" if new_theme == "dark" else "#000000"
        hover_color = "#2B2B2B" if new_theme == "dark" else "#E0E0E0"
        
        self.settings_btn.configure(
            text_color=text_color,
            hover_color=hover_color
        )

    def _on_timing_changed(self, timing_updates):
        logger.info(f"Timing settings updated: {timing_updates}")

        if hasattr(self, 'player'):
            if "delays" in timing_updates:
                delays = timing_updates["delays"]
                self.player.initial_delay = delays.get("initial_delay", self.player.initial_delay)
                self.player.pause_resume_delay = delays.get("pause_resume_delay", self.player.pause_resume_delay)
            
            if "ramping" in timing_updates:
                ramping = timing_updates["ramping"]
                self.player.ramp_begin_config = ramping.get("begin", self.player.ramp_begin_config)
                self.player.ramp_end_config = ramping.get("end", self.player.ramp_end_config)
                self.player.ramp_after_pause_config = ramping.get("after_pause", self.player.ramp_after_pause_config)

                self.player.speed_change_ramping_config = ramping.get("speed_change", self.player.speed_change_ramping_config)
                self.player.speed_change_ramp_steps = ramping.get("speed_change", {}).get("steps", 8)
            
            logger.info("MusicPlayer timing settings updated immediately")

    def _on_playback_changed(self, playback_updates):
        logger.info(f"Playback settings updated: {playback_updates}")
        
        if hasattr(self, 'speed_presets'):
            self.speed_presets = playback_updates["speed_presets"]
            self._update_speed_preset_buttons()
        
        if hasattr(self, 'player'):
            self.player.key_press_durations = playback_updates["key_press_durations"]
            logger.info("MusicPlayer playback settings updated immediately")
            
        if hasattr(self, 'duration_presets'):
            self.duration_presets = playback_updates["key_press_durations"]
            self._update_duration_preset_buttons()

    def _update_speed_preset_buttons(self):
        if hasattr(self, 'speed_preset_frame') and self.speed_preset_frame.winfo_exists():
            for widget in self.speed_preset_frame.winfo_children():
                widget.destroy()
            
            if hasattr(self, 'speed_presets') and self.speed_presets:
                for speed in self.speed_presets:
                    if speed <= 0:
                        continue
                        
                    btn = ctk.CTkButton(
                        self.speed_preset_frame, 
                        text=str(speed), 
                        width=40,
                        height=25,
                        font=("Arial", 12),
                        command=lambda s=speed: self._set_speed(s)
                    )
                    btn.pack(side="left", padx=2)
        
    def _update_duration_preset_buttons(self):
        if hasattr(self, 'preset_frame') and self.preset_frame.winfo_exists():
            for widget in self.preset_frame.winfo_children():
                widget.destroy()
            
            if hasattr(self, 'duration_presets') and self.duration_presets:
                for preset in self.duration_presets:
                    btn = ctk.CTkButton(
                        self.preset_frame, text=f"{preset} s", width=50,
                        command=lambda p=preset: self._apply_preset(p)
                    )
                    btn.pack(side="left", padx=2)

    def _adjust_window_size(self):
        try:
            if self.keypress_enabled and self.speed_enabled:
                base_height = FULL_SIZE[1]
            elif self.keypress_enabled or self.speed_enabled:
                base_height = EXPANDED_SIZE[1]
            else:
                base_height = DEFAULT_WINDOW_SIZE[1]
            
            if not self.smooth_ramping_enabled and self.show_ramping_info:
                base_height += RAMPING_INFO_HEIGHT
            
            self.root.geometry(f"{FULL_SIZE[0]}x{base_height}")
        except Exception as e:
            logger.error(f"Window size adjustment failed: {e}")
            self.root.geometry(f"{DEFAULT_WINDOW_SIZE[0]}x{DEFAULT_WINDOW_SIZE[1]}")

    def _toggle_smooth_ramping(self):
        self.smooth_ramping_enabled = not self.smooth_ramping_enabled
                
        status = "enabled" if self.smooth_ramping_enabled else "disabled"
        self.ramping_btn.configure(
            text=f"{LanguageManager.get('smooth_ramping')}: {LanguageManager.get(status)}"
        )

        self.player.enable_ramping = self.smooth_ramping_enabled

        if self.smooth_ramping_enabled:
            self.ramping_frame.pack_forget()
            if self.show_ramping_info:
                self.ramping_info_display_count += 1
                self.show_ramping_info = self.ramping_info_display_count < MAX_RAMPING_INFO_DISPLAY
        else:
            if self.show_ramping_info:
                self.ramping_frame.pack(pady=5, before=self.play_btn)

        ConfigManager.save({
            "playback_settings": {
                "enable_ramping": self.smooth_ramping_enabled
            },
            "ramping_info_display_count": {
                "value": self.ramping_info_display_count
            }
        })

        self._adjust_window_size()
        logger.info(f"Smooth ramping {'enabled' if self.smooth_ramping_enabled else 'disabled'}")

    def _open_releases(self, event):
        try:
            if self.update_status == "update" and self.update_url:
                webbrowser.open(self.update_url)
            else:
                webbrowser.open("https://github.com/VanilleIce/ProjectLyrica/releases/latest")
        except Exception as e:
            messagebox.showerror("Error", f"Browser error: {e}")

    def _play_thread(self, song_data):
        logger.info("Starting playback thread")
        
        try:
            song_name = Path(self.selected_file).name
            logger.info(f"Playing: {song_name}")
        except Exception as e:
            logger.error(f"Could not get song name: {e}")
        
        logger.info("Attempting to focus Sky window")
        window_focused = False
        focus_attempts = 2
        
        focus_start_time = time.time()
        
        for attempt in range(1, focus_attempts + 1):
            try:
                window = self.player._find_sky_window()
                if window:
                    logger.debug(f"Found Sky window: {window.title}")
                    if self.player._focus_window(window):
                        window_focused = True
                        logger.info(f"Successfully focused Sky window on attempt {attempt}/{focus_attempts}")
                        break
                    else:
                        logger.warning(f"Failed to focus Sky window on attempt {attempt}/{focus_attempts}")
                else:
                    logger.warning(f"No Sky window found on attempt {attempt}/{focus_attempts}")
            except Exception as e:
                logger.error(f"Window focus error on attempt {attempt}/{focus_attempts}: {e}")
                time.sleep(0.5)
            
            time.sleep(0.2)
        
        if not window_focused:
            logger.error(f"Failed to focus Sky window after {focus_attempts} attempts")
            self.root.after(0, lambda: messagebox.showerror(
                LanguageManager.get("error_title"), 
                LanguageManager.get("sky_window_focus_error")
            ))
            self.root.after(0, lambda: self._update_play_button_state("ready"))
            return
        
        elapsed_time = time.time() - focus_start_time
        remaining_delay = max(0, self.player.initial_delay - elapsed_time)
        
        if remaining_delay > 0:
            logger.debug(f"Waiting initial delay: {remaining_delay:.2f}s (of {self.player.initial_delay}s)")
            time.sleep(remaining_delay)
        else:
            logger.debug(f"Focus took longer than initial delay ({elapsed_time:.2f}s), skipping wait")
        
        try:
            self.player.play(song_data)
        except Exception as play_error:
            logger.critical(f"Playback thread crashed: {play_error}", exc_info=True)
            self.root.after(0, lambda e=play_error: messagebox.showerror(
                "Critical Error", 
                f"Playback failed: {str(e)}"
            ))
        finally:
            try:
                winsound.Beep(1000, 500)
            except Exception as e:
                logger.warning(f"Could not play completion beep: {e}")
            logger.info("Playback thread completed")

            self.root.after(0, lambda: self._update_play_button_state("ready"))

    def _handle_keypress(self, key):
        """Handle all key events including pause and speed changes"""
        try:
            key_char = getattr(key, 'char', None)
            key_name = getattr(key, 'name', None)
            
            # Pause key handling
            if key_char == self.pause_key:
                self._handle_pause_key()
                return
                
            if (self.player.playback_active and
                self.smooth_ramping_enabled):
                
                self._handle_speed_change_key(key_char, key_name)
                
        except Exception as e:
            logger.error(f"Key handler error: {e}")

    def _handle_pause_key(self):
        """Handle pause key events"""
        if not self.selected_file or not self.player.playback_active:
            return

        if self.player.pause_flag.is_set():
            logger.info("Resuming playback via pause key")
            self.player.pause_flag.clear()
            self.root.after(0, lambda: self._update_play_button_state("playing"))
            
            if window := self.player._find_sky_window():
                self.player._focus_window(window)
        else:
            logger.info("Pausing playback via pause key")
            self.player.pause_flag.set()

            if not hasattr(self, '_originally_paused_file'):
                self._originally_paused_file = self.selected_file
                logger.info(f"Originally paused file set to: {self._originally_paused_file}")
            
            self.root.after(0, lambda: self._update_play_button_state("paused"))

    def _handle_speed_change_key(self, key_char, key_name):
        """Handle speed change keys during playback - nur Preset Mode"""
        if self.player.playback_active:
            self._handle_preset_speed_change(key_char, key_name)

    def _handle_preset_speed_change(self, key_char, key_name):
        """Change to user-mapped preset speed - auch während Pause"""
        preset_mappings = self.speed_change_config.get('preset_mappings', [])
        
        for mapping in preset_mappings:
            preset_key = mapping.get('key', '')
            preset_speed = mapping.get('speed', 600)
            
            # Check if pressed key matches preset key
            if (key_char and key_char == preset_key) or (key_name and key_name == preset_key):
                if self.player.playback_active and not self.player.pause_flag.is_set():
                    success = self.player.change_speed_during_playback(preset_speed)
                    if success:
                        self.current_speed_value = preset_speed
                        logger.info(f"Speed change with ramping to {preset_speed}")
                else:
                    self.current_speed_value = preset_speed
                    self.player.current_speed = preset_speed
                    logger.info(f"Speed changed directly to {preset_speed} (paused: {self.player.pause_flag.is_set()})")
                
                self.root.after(0, lambda: self._update_speed_display(preset_speed, force_ui_enable=True))
                return

    def _update_speed_ui_visibility(self):
        """Aktualisiert die Sichtbarkeit der Speed-UI"""
        if self.speed_enabled:
            current_speed = self.current_speed_value
            self.speed_btn.configure(text=f"{LanguageManager.get('speed_control')}: {current_speed}")
            self.speed_frame.pack(pady=5, before=self.ramping_btn)
            self.speed_preset_frame.pack(pady=(0, 8))
            if hasattr(self, 'speed_label'):
                self.speed_label.configure(text=f"{LanguageManager.get('current_speed')}: {current_speed}")
                self.speed_label.pack(pady=(0, 8))
        else:
            self.speed_btn.configure(text=f"{LanguageManager.get('speed_control')}: {LanguageManager.get('disabled')}")
            self.speed_frame.pack_forget()
        
        self._adjust_window_size()

    def _update_speed_display(self, new_speed, force_ui_enable=False):
        """Aktualisiert die Geschwindigkeits-Anzeige in der GUI - auch während Pause"""
        self.current_speed_value = new_speed
        self.player.current_speed = new_speed
        
        display_speed = int(new_speed)
        
        if force_ui_enable and not self.speed_enabled:
            self.speed_enabled = True
            self._update_speed_ui_visibility()
        
        if self.speed_enabled:
            self.speed_btn.configure(text=f"{LanguageManager.get('speed_control')}: {display_speed}")
            if hasattr(self, 'speed_label') and self.speed_label.winfo_exists():
                self.speed_label.configure(text=f"{LanguageManager.get('current_speed')}: {display_speed}")
            
            self.root.update_idletasks()

    def _select_file(self):
        try:
            logger.info("Opening file selection dialog")
            songs_dir = Path("resources/Songs")
            try:
                if not songs_dir.exists():
                    logger.warning("Songs directory not found, falling back to CWD")
                    songs_dir = Path.cwd()
            except Exception as e:
                logger.error(f"Directory check failed: {e}")
                songs_dir = Path.cwd()

            file = filedialog.askopenfilename(
                initialdir=songs_dir,
                filetypes=[(LanguageManager.get("supported_formats"), "*.json *.txt *.skysheet")]
            )
            
            if file:
                previous_file = getattr(self, 'selected_file', None)
                self.selected_file = file
                
                try:
                    name = Path(file).name
                    display = name if len(name) <= 30 else f"{name[:25]}..."
                    self.file_btn.configure(text=display)
                except Exception as e:
                    logger.error(f"Filename processing failed: {e}")
                    self.file_btn.configure(text="Selected file")

                if self.player.playback_active and self.player.pause_flag.is_set():
                    if not hasattr(self, '_originally_paused_file'):
                        self._originally_paused_file = previous_file
                        logger.info(f"Set originally paused file to: {previous_file}")
                    
                    has_different_file = (self._originally_paused_file != self.selected_file)
                    if has_different_file:
                        logger.info(f"Different file selected during pause - showing PURPLE button")
                    else:
                        logger.info(f"Same file selected during pause - showing ORANGE button")
                        
                    self._update_play_button_state("paused")
                else:
                    self._update_play_button_state("ready")
                
                try:
                    relative_path = Path(file).relative_to(Path.cwd())
                    logger.info(f"Selected song: {relative_path}")
                except ValueError:
                    logger.info(f"Selected song: {file}")
                    
            else:
                if hasattr(self, 'selected_file') and self.selected_file:
                    logger.info("File dialog closed without selection - keeping previous file")
                    if self.player.playback_active and self.player.pause_flag.is_set():
                        self._update_play_button_state("paused")
                    else:
                        self._update_play_button_state("ready")
                else:
                    self._update_play_button_state("ready")
                        
        except Exception as e:
            logger.error(f"File selection failed: {e}")
            messagebox.showerror("Error", LanguageManager.get("file_selection_error"))
            self._update_play_button_state("ready")

    def _play_song(self):
        if not self._check_sky_running(use_cache=False):
            messagebox.showerror(
                LanguageManager.get("error_title"),
                LanguageManager.get("sky_only_warning")
            )
            self._update_play_button_state("ready")
            return
            
        if not self.selected_file:
            messagebox.showwarning("Warning", LanguageManager.get("choose_song_warning"))
            self._update_play_button_state("ready")
            return

        try:
            if self.player.playback_active:
                self.player.stop()
                time.sleep(0.1)

            if hasattr(self, '_originally_paused_file'):
                del self._originally_paused_file
                logger.info("Cleared originally paused file for restart")

            current_speed = self.current_speed_value
            self.player.current_speed = current_speed
            logger.info(f"Starting playback with speed: {current_speed}")
            
            song = self.player.parse_song(self.selected_file)
            self._update_play_button_state("playing")
            Thread(target=self._play_thread, args=(song,), daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("Error", f"{LanguageManager.get('play_error_message')}: {e}")
            self._update_play_button_state("ready")

    def _set_duration(self, event):
        try:
            duration = round(self.duration_slider.get(), 3)
            self.player.press_duration = duration
            self.duration_label.configure(text=f"{LanguageManager.get('duration')} {duration} s")
        except Exception as e:
            logger.error(f"Duration setting failed: {e}")

    def _apply_preset(self, duration):
        try:
            self.player.press_duration = duration
            self.duration_slider.set(duration)
            self.duration_label.configure(text=f"{LanguageManager.get('duration')} {duration} s")
        except Exception as e:
            logger.error(f"Preset application failed: {e}")

    def _set_speed(self, speed):
        try:
            MIN_SPEED = 100
            MAX_SPEED = 1500
            
            try:
                speed = float(speed)
            except (ValueError, TypeError):
                messagebox.showerror("Error", "Speed must be a valid number")
                return
                
            if speed <= 0:
                messagebox.showerror("Error", LanguageManager.get("invalid_speed"))
                return
                
            if speed < MIN_SPEED:
                messagebox.showwarning(
                    LanguageManager.get('warning_title'), 
                    LanguageManager.get('speed_too_slow').format(
                        min_speed=MIN_SPEED, 
                        min_speed_again=MIN_SPEED
                    )
                )
                speed = MIN_SPEED
                
            if speed > MAX_SPEED:
                messagebox.showwarning(
                    LanguageManager.get('warning_title'), 
                    LanguageManager.get('speed_too_fast').format(
                        max_speed=MAX_SPEED,
                        max_speed_again=MAX_SPEED
                    )
                )
                speed = MAX_SPEED
                
            self.current_speed_value = speed
            self.player.set_speed(speed)
            
            self._update_speed_display(speed, force_ui_enable=False)
            
        except Exception as e:
            logger.error(f"Speed setting failed: {e}")
            messagebox.showerror(
                LanguageManager.get('error_title'), 
                LanguageManager.get('speed_setting_failed').format(error=str(e))
            )

    def _toggle_keypress(self):
        try:
            self.keypress_enabled = not self.keypress_enabled
            status = "enabled" if self.keypress_enabled else "disabled"
            self.keypress_btn.configure(text=f"{LanguageManager.get('key_press')}: {LanguageManager.get(status)}")
            
            if self.keypress_enabled:
                self.duration_frame.pack(pady=5, before=self.speed_btn)
                self.duration_slider.pack(pady=5)
                self.duration_label.pack()
                self.preset_frame.pack(pady=5)
            else:
                self.duration_frame.pack_forget()
                self.player.press_duration = 0.1
                
            self._adjust_window_size()
        except Exception as e:
            logger.error(f"Keypress toggle failed: {e}")

    def _toggle_speed(self):
        try:
            self.speed_enabled = not self.speed_enabled
            self._update_speed_ui_visibility()
        except Exception as e:
            logger.error(f"Speed toggle failed: {e}")

    def _shutdown(self):
        logger.info("Application shutdown initiated")
        try:
            if hasattr(self, 'player') and self.player.playback_active:
                try:
                    self.player.stop()
                except Exception as e:
                    logger.error(f"Player stop failed during shutdown: {e}")
            
            if hasattr(self, 'player'):
                try:
                    self.player.clear_cache()
                except Exception as e:
                    logger.error(f"Cache cleanup failed: {e}")

            if hasattr(self, 'key_listener'):
                try:
                    if self.key_listener.is_alive():
                        self.key_listener.stop()
                except Exception as e:
                    logger.error(f"Key listener stop failed: {e}")

            if hasattr(self, '_mutex'):
                try:
                    ctypes.windll.kernel32.CloseHandle(self._mutex)
                except Exception as e:
                    logger.error(f"Mutex close failed: {e}")

        except Exception as e:
            logger.critical(f"Shutdown error: {e}", exc_info=True)
        finally:
            try:
                self.root.destroy()
            except Exception as e:
                logger.error(f"Root window destruction failed: {e}")
            logger.info("Application closed")

    def run(self):
        try:
            self.root.mainloop()
        except Exception as e:
            logger.critical(f"Main loop crashed: {e}", exc_info=True)
            raise

# -------------------------------
# App Starter
# -------------------------------

if __name__ == "__main__":
    try:
        if os.name == 'nt':
            try:
                from ctypes import windll
                windll.shcore.SetProcessDpiAwareness(1)
            except Exception as e:
                logger.warning(f"DPI awareness setting failed: {e}")

        ctk.set_widget_scaling(1.0)
        ctk.set_window_scaling(1.0)

        MusicApp().run()
    except Exception as e:
        logger.critical(f"Application crashed: {e}", exc_info=True)
        messagebox.showerror("Critical Error", f"The application encountered a critical error and will close: {str(e)}")