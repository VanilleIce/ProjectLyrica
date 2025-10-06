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
VERSION = "2.5.2"

# -------------------------------
# Music App
# -------------------------------

class MusicApp:
    def __init__(self):
        setup_logging(VERSION)
        self._init_language()
        self._check_running()

        if ConfigManager.get_value("game_settings.sky_exe_path") is None:
            SkyChecker.show_initial_settings()

        self._init_player()
        self._init_gui()
        self._setup_key_listener()

        ConfigManager.log_system_info(VERSION)

    def _init_language(self):
        LanguageManager.init()
        ui_language = ConfigManager.get_value("ui_settings.selected_language")
        
        if not ui_language:
            LanguageWindow.show()

    def _check_running(self):
        self._mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "ProjectLyricaMutex")
        if ctypes.windll.kernel32.GetLastError() == 183:
            messagebox.showerror("Error", "Application is already running!")
            sys.exit(1)

    def _init_player(self):
        config = ConfigManager.get_config()
        self.player = MusicPlayer()
        self.selected_file = None

        playback_settings = config.get("playback_settings", {})
        ui_settings = config.get("ui_settings", {})
        
        self.duration_presets = playback_settings.get("key_press_durations")
        self.speed_presets = playback_settings.get("speed_presets")
        self.pause_key = ui_settings.get("pause_key")
        
        self.player.keypress_enabled = False
        self.player.speed_enabled = False
        self.player.pause_enabled = False
        
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
            
            theme = ConfigManager.get_value("ui_settings.theme")
            ctk.set_appearance_mode(theme)
            self.theme_icon = "🌞" if theme == "light" else "🌙"
            
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
        
        self.speed_btn = self._create_button(
            f"{LanguageManager.get('speed_control')}: {LanguageManager.get('disabled')}", 
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
        self.speed_label = ctk.CTkLabel(
            self.speed_frame,
            text=f"{LanguageManager.get('current_speed')}: {self.player.current_speed}",
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
        """Robust play button state update for CustomTkinter"""
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
            has_different_file = (hasattr(self, '_originally_paused_file') and 
                                self._originally_paused_file is not None and 
                                self.selected_file is not None and
                                self._originally_paused_file != self.selected_file)
            
            if has_different_file:
                pause_key_hint = LanguageManager.get("pause_key_hint").replace("[pause_key]", self.pause_key)
                self.play_btn.configure(
                    text=f"{LanguageManager.get('play_button_text')}\n{pause_key_hint}",
                    command=self._play_song,
                    fg_color="#8B4B8B",
                    hover_color="#6A3A6A",
                    text_color="#ffffff",
                    state="normal",
                    height=50
                )
                logger.debug(f"Mixed state (purple) - originally paused: {self._originally_paused_file}, selected: {self.selected_file}")
            else:
                pause_key_hint = LanguageManager.get("pause_key_hint").replace("[pause_key]", self.pause_key)
                self.play_btn.configure(
                    text=f"{LanguageManager.get('restart_button_text')}\n{pause_key_hint}",
                    command=self._play_song,
                    fg_color="#D2691E",
                    hover_color="#A0522D",
                    text_color="#ffffff",
                    state="normal",
                    height=50
                )
                logger.debug(f"Restart state (orange) - originally paused: {self._originally_paused_file}, selected: {self.selected_file}")
        elif state == "ready":
            self.play_btn.configure(
                text=LanguageManager.get("play_button_text"),
                command=self._play_song,
                fg_color="#2b6cb0",
                hover_color="#1f538d",
                text_color="#ffffff",
                state="normal",
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
        """Stoppt die Wiedergabe komplett"""
        if self.player.playback_active:
            self.player.stop()
            self._update_play_button_state("ready")

    def _resume_from_pause(self):
        """Setzt die Wiedergabe fort - gleiche Funktion wie Pause-Key"""
        if self.player.pause_flag.is_set():
            self.player.pause_flag.clear()
            self._update_play_button_state("playing")
            
            if window := self.player._find_sky_window():
                self.player._focus_window(window)

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
        
        self.theme_btn = ctk.CTkButton(
            status_frame,
            text=self.theme_icon,
            width=30,
            height=30,
            font=("Arial", 16),
            command=self._toggle_theme
        )
        self.theme_btn.pack(side="right", padx=(0, 5))
        
        ctk.CTkLabel(self.root, text=LanguageManager.get("project_title"), 
                    font=("Arial", 18, "bold")).pack(pady=10)
        self.file_btn.pack(pady=10)
        self.keypress_btn.pack(pady=10)
        self.speed_btn.pack(pady=10)
        self.ramping_btn.pack(pady=10)
        
        self.play_btn.pack(pady=10)
        
        self._update_play_button_state("disabled")
        
        if not self.smooth_ramping_enabled and self.show_ramping_info:
            self.ramping_frame.pack(pady=5, before=self.play_btn)
        
        self._adjust_window_size()

    def _adjust_window_size(self):
        try:
            keypress_enabled = getattr(self.player, 'keypress_enabled', False)
            speed_enabled = getattr(self.player, 'speed_enabled', False)
            
            if keypress_enabled and speed_enabled:
                base_height = FULL_SIZE[1]
            elif keypress_enabled or speed_enabled:
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

    def _toggle_theme(self):
        try:
            current = ctk.get_appearance_mode().lower()
            new_theme = "light" if current == "dark" else "dark"
            ctk.set_appearance_mode(new_theme)
            self.theme_btn.configure(text="🌞" if new_theme == "light" else "🌙")
            ConfigManager.save({
                "ui_settings": {
                    "theme": new_theme
                }
            })
        except Exception as e:
            logger.error(f"Theme toggle failed: {e}")

    def _open_releases(self, event):
        try:
            if self.update_status == "update" and self.update_url:
                webbrowser.open(self.update_url)
            else:
                webbrowser.open("https://github.com/VanilleIce/ProjectLyrica/releases/latest")
        except Exception as e:
            messagebox.showerror("Error", f"Browser error: {e}")

    def _play_thread(self, song_data):
        self.root.after(0, lambda: self._update_play_button_state("playing"))
        
        logger.info("Starting playback thread")
        
        try:
            relative_path = Path(self.selected_file).relative_to(Path.cwd())
            logger.info(f"Playing song: {relative_path}")
        except ValueError:
            logger.info(f"Playing song: {self.selected_file}")
        
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
                        window = self.player._find_sky_window()
                else:
                    logger.warning(f"No Sky window found on attempt {attempt}/{focus_attempts}")
            except Exception as e:
                logger.error(f"Window focus error on attempt {attempt}/{focus_attempts}: {e}")
                time.sleep(0.5)
            
            time.sleep(0.2)
        
        if not window_focused:
            logger.error(f"Failed to focus Sky window after {focus_attempts} attempts")
            self.root.after(0, lambda: messagebox.showerror("Error", LanguageManager.get("sky_not_running")))
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
            logger.info("Starting actual playback")
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
        """Handle pause key events with comprehensive state logging"""
        try:
            if not hasattr(key, 'char') or key.char != self.pause_key:
                return

            state_info = {
                'playback_active': self.player.playback_active,
                'pause_enabled': self.player.pause_enabled,
                'currently_paused': self.player.pause_flag.is_set(),
                'song_loaded': bool(self.selected_file)
            }

            if not state_info['song_loaded']:
                logger.debug("Pause Ignored - no song loaded")
                return
                
            if not state_info['playback_active']:
                logger.debug("Pause Ignored - playback not active")
                return
                
            if not state_info['pause_enabled']:
                logger.debug("Pause Ignored - pause disabled")
                return

            if state_info['currently_paused']:
                self.player.pause_flag.clear()
                self.root.after(0, lambda: self._update_play_button_state("playing"))
                
                if window := self.player._find_sky_window():
                    if self.player._focus_window(window):
                        logger.debug("Successfully focused game window")
                    else:
                        logger.debug("Failed to focus game window")
            else:
                self.player.pause_flag.set()

                if not hasattr(self, '_originally_paused_file'):
                    self._originally_paused_file = self.selected_file
                    logger.debug(f"Originally paused file set to: {self._originally_paused_file}")
                
                self.root.after(0, lambda: self._update_play_button_state("paused"))
                
        except Exception as e:
            logger.error(f"Critical error in pause handler: {str(e)}", exc_info=True)

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
                self.selected_file = file
                
                try:
                    name = Path(file).name
                    display = name if len(name) <= 30 else f"{name[:25]}..."
                    self.file_btn.configure(text=display)
                except Exception as e:
                    logger.error(f"Filename processing failed: {e}")
                    self.file_btn.configure(text="Selected file")

                if self.player.playback_active and self.player.pause_flag.is_set():
                    self._update_play_button_state("paused")
                    logger.info(f"File selected while song is paused - showing appropriate pause state")
                else:
                    self._update_play_button_state("ready")
                    logger.info(f"File selected: {file} - Ready to play new song")

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
                    self._update_play_button_state("disabled")
                    logger.info("File dialog closed without selection - no previous file")
                    
        except Exception as e:
            logger.error(f"File selection failed: {e}")
            messagebox.showerror("Error", LanguageManager.get("file_selection_error"))

    def _play_song(self):
        if not self.selected_file:
            messagebox.showwarning("Warning", LanguageManager.get("choose_song_warning"))
            return

        if hasattr(self, '_originally_paused_file'):
            del self._originally_paused_file
            logger.debug("Cleared originally paused file due to new song play")
            
        if self.player.playback_active:
            self.player.stop()
            time.sleep(0.1)
        
        try:
            song = self.player.parse_song(self.selected_file)
            Thread(target=self._play_thread, args=(song,), daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", f"{LanguageManager.get('play_error_message')}: {e}")

            self.root.after(0, lambda: self._update_play_button_state("ready"))

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
                    "Warning", 
                    f"Speed too slow. Minimum speed is {MIN_SPEED}. Setting to {MIN_SPEED}."
                )
                speed = MIN_SPEED
                
            if speed > MAX_SPEED:
                messagebox.showwarning(
                    "Warning", 
                    f"Speed too fast. Maximum speed is {MAX_SPEED}. Setting to {MAX_SPEED}."
                )
                speed = MAX_SPEED
                
            self.player.set_speed(speed)
            display_speed = int(speed) if speed.is_integer() else speed
            self.speed_label.configure(text=f"{LanguageManager.get('current_speed')}: {display_speed}")
            
        except Exception as e:
            logger.error(f"Speed setting failed: {e}")
            messagebox.showerror("Error", f"Failed to set speed: {e}")

    def _toggle_keypress(self):
        try:
            self.player.keypress_enabled = not self.player.keypress_enabled
            status = "enabled" if self.player.keypress_enabled else "disabled"
            self.keypress_btn.configure(text=f"{LanguageManager.get('key_press')}: {LanguageManager.get(status)}")
            
            if self.player.keypress_enabled:
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
            self.player.speed_enabled = not self.player.speed_enabled
            status = "enabled" if self.player.speed_enabled else "disabled"
            self.speed_btn.configure(text=f"{LanguageManager.get('speed_control')}: {LanguageManager.get(status)}")
            
            if self.player.speed_enabled:
                self.speed_frame.pack(pady=5, before=self.ramping_btn)
                self.speed_preset_frame.pack(pady=(0, 8))
                self.speed_label.pack(pady=(0, 8))
            else:
                self.speed_frame.pack_forget()
                self.player.current_speed = 1000

            self._adjust_window_size()
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
                        time.sleep(0.1)
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