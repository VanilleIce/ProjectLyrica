# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import json, time, os, sys, winsound, heapq, ctypes, webbrowser, logging, psutil
import pygetwindow as gw
import customtkinter as ctk
from pathlib import Path
from threading import Event, Thread, Lock
from pynput.keyboard import Controller, Listener, Key
from tkinter import filedialog, messagebox
import xml.etree.ElementTree as ET

from update_checker import check_update
from logging_setup import setup_logging
from config_manager import ConfigManager
from language_manager import LanguageManager, KeyboardLayoutManager
from sky_checker import SkyChecker

logger = logging.getLogger("ProjectLyrica.ProjectLyrica")

# -------------------------------
# Constants
# -------------------------------

DEFAULT_WINDOW_SIZE = (400, 355)
EXPANDED_SIZE = (400, 455)
FULL_SIZE = (400, 535)
RAMPING_INFO_HEIGHT = 55
MAX_RAMPING_INFO_DISPLAY = 6
VERSION = "2.4.0"

# -------------------------------
# Note Scheduler
# -------------------------------

class NoteScheduler:
    def __init__(self, release_callback):
        self.queue = []
        self.callback = release_callback
        self.lock = Lock()
        self.stop_event = Event()
        self.thread = Thread(target=self._run, daemon=True)
        self.thread.start()
        self.active = True

    def add(self, key, delay):
        with self.lock:
            heapq.heappush(self.queue, (time.time() + delay, key))

    def reset(self):
        with self.lock:
            self.queue = []

    def stop(self):
        if self.active:
            self.stop_event.set()
            self.thread.join(timeout=0.5)
            if self.thread.is_alive():
                logger.warning("Scheduler thread did not terminate gracefully")
            self.active = False

    def restart(self):
        if not self.active:
            self.stop_event.clear()
            self.thread = Thread(target=self._run, daemon=True)
            self.thread.start()
            self.active = True

    def _run(self):
        try:
            while not self.stop_event.is_set():
                try:
                    with self.lock:
                        now = time.time()
                        release_keys = []
                        while self.queue and self.queue[0][0] <= now:
                            try:
                                _, key = heapq.heappop(self.queue)
                                release_keys.append(key)
                            except Exception as e:
                                logger.error(f"Queue pop failed: {e}")
                                break
                    
                    for key in release_keys:
                        try:
                            self.callback(key)
                        except Exception as e:
                            logger.error(f"Key release failed: {e}")

                    with self.lock:
                        if self.queue:
                            next_time = self.queue[0][0]
                            sleep_time = max(0, min(0.05, next_time - time.time()))
                        else:
                            sleep_time = 0.05
                            
                    time.sleep(sleep_time)
                except Exception as e:
                    logger.error(f"Scheduler iteration failed: {e}")
                    time.sleep(0.1)
        except Exception as e:
            logger.critical(f"Scheduler thread crashed: {e}", exc_info=True)

# -------------------------------
# Music Player
# -------------------------------

class MusicPlayer:
    def __init__(self):
        try:
            self.logger = logging.getLogger("ProjectLyrica.MusicPlayer")
            config = ConfigManager.get_config()

            self.keyboard = Controller()
            self.pause_flag = Event()
            self.stop_event = Event()
            self.song_cache = {}
            self.status_lock = Lock()
            
            self.key_map = self._create_key_map(config["key_mapping"])
            self.press_duration = 0.1
            self.current_speed = 1000
            self.playback_active = False
            self.scheduler = NoteScheduler(self.keyboard.release)
            
            self.keypress_enabled = False
            self.speed_enabled = False
            self.pause_enabled = False
            
            timing = config["timing_config"]
            self.initial_delay = timing["initial_delay"]
            self.pause_resume_delay = timing["pause_resume_delay"]
            self.ramp_steps_begin = timing["ramp_steps_begin"]
            self.ramp_steps_end = timing["ramp_steps_end"]
            
            self.enable_ramping = config.get("enable_ramping", False)
            self.is_ramping_begin = False
            self.is_ramping_end = False
            self.ramp_counter = 0
            
            self.start_time = 0
            self.note_count = 0
            self.pause_count = 0
            self.pause_start = 0
            self.total_pause_time = 0
        except Exception as e:
            logger.critical(f"MusicPlayer initialization failed: {e}", exc_info=True)
            raise

    def _create_key_map(self, mapping):
        key_map = {}
        for prefix in ['', '1', '2', '3']:
            for key, value in mapping.items():
                try:
                    if isinstance(value, str) and '\\u' in value:
                        value = bytes(value, 'latin1').decode('unicode_escape')
                    key_map[f"{prefix}{key}".lower()] = value
                except Exception as e:
                    logger.error(f"Key mapping error for {key}: {value} - {e}")
                    key_map[f"{prefix}{key}".lower()] = value
        return key_map

    def _find_sky_window(self):
        try:
            exe_path = ConfigManager.get_value("sky_exe_path", "")
            if not exe_path:
                logger.error("No Sky.exe path in settings.json!")
                return None

            target_exe_name = Path(exe_path).name.lower()

            for proc in psutil.process_iter(['name', 'exe']):
                try:
                    if proc.info['name'].lower() == target_exe_name or \
                       (proc.info['exe'] and Path(proc.info['exe']).name.lower() == target_exe_name):
                        windows = gw.getWindowsWithTitle("Sky")
                        if windows:
                            return windows[0]
                        else:
                            logger.warning("Sky.exe is running but no window found!")
                            return None
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            logger.warning(f"{target_exe_name} not found in process list!")
            return None

        except Exception as e:
            logger.error(f"Process search failed: {e}")
            return None

    def _focus_window(self, window):
        try:
            if not isinstance(window, gw.Window):
                logger.error("Invalid window object provided")
                return False
                
            if window.isMinimized: 
                window.restore()
            if not window.isActive:
                for _ in range(3):
                    try:
                        window.activate()
                        time.sleep(0.1)
                        if window.isActive:
                            break
                    except Exception as e:
                        logger.warning(f"Window activation attempt failed: {e}")
                        continue
            return window.isActive
        except Exception as e:
            logger.error(f"Window focus error: {e}")
            return False

    def parse_song(self, path):
        self.logger.debug(f"Parsing song: {path}")
        if path in self.song_cache:
            return self.song_cache[path]
        
        file = Path(path)
        try:
            data = json.loads(file.read_text(encoding='utf-8'))
            song_data = data[0] if isinstance(data, list) and len(data) == 1 else data
            
            if "songNotes" not in song_data:
                if "notes" in song_data:
                    song_data["songNotes"] = song_data["notes"]
                elif "Notes" in song_data:
                    song_data["songNotes"] = song_data["Notes"]
                else:
                    raise ValueError(LanguageManager.get('missing_song_notes'))
                    
            title_keys = ["songName", "name", "title", "song_title", "songName"]
            song_title = "Unknown"
            for key in title_keys:
                if key in song_data:
                    song_title = song_data[key]
                    break
            song_data["songTitle"] = song_title
            
            for note in song_data["songNotes"]:
                note['key_lower'] = note.get('key', '').lower()
                
            self.song_cache[path] = song_data
            return song_data
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format in {path}: {e}")
            raise ValueError(LanguageManager.get('invalid_song_format'))
        except Exception as e:
            logger.error(f"Song parse error [{path}]: {e}", exc_info=True)
            raise

    def play(self, song_data):
        try:
            self.logger.info("Starting song playback")
            if self.playback_active:
                self.stop()
        
            self.scheduler.restart()
            self.playback_active = True
            self.pause_enabled = True
            self.scheduler.reset()
            self.stop_event.clear()

            notes = song_data.get("songNotes", [])
            if not notes:
                logger.error("No notes found in song data")
                messagebox.showerror(LanguageManager.get("error_title"), LanguageManager.get("missing_song_notes"))
                return
        
            self.is_ramping_begin = False
            self.is_ramping_end = False
            self.ramp_counter = 0
            
            if self.enable_ramping:
                self.is_ramping_begin = True
                self.ramp_counter = 0
            
            self.pause_count = 0
            self.total_pause_time = 0
            
            notes = song_data.get("songNotes", [])
            self.note_count = len(notes)
            
            if not notes:
                logger.error("No notes found in song data")
                messagebox.showerror(LanguageManager.get("error_title"), LanguageManager.get("missing_song_notes"))
                return

            song_title = song_data.get("songTitle", "Unknown")
            logger.info(f"Playing song: '{song_title}' with {self.note_count} notes at speed {self.current_speed}")
            
            time.sleep(self.initial_delay)
            
            self.start_time = time.time()
            last_time = 0
            
            try:
                for i, note in enumerate(notes):
                    if self.stop_event.is_set():
                        logger.info("Playback stopped by user")
                        break

                    if self.enable_ramping:
                        if self.is_ramping_begin:
                            ramp_factor = 0.5 + 0.5 * (self.ramp_counter / self.ramp_steps_begin)
                            speed = max(500, self.current_speed * min(1.0, ramp_factor))
                            self.ramp_counter += 1
                            if self.ramp_counter >= self.ramp_steps_begin:
                                self.is_ramping_begin = False
                                logger.debug("Beginning ramping completed")

                        elif i >= len(notes) - self.ramp_steps_end:
                            progress = (len(notes) - i) / self.ramp_steps_end
                            ramp_factor = max(0.5, progress)
                            speed = max(500, self.current_speed * ramp_factor)
                            if not self.is_ramping_end:
                                self.is_ramping_end = True
                                logger.debug("End ramping started")

                        else:
                            speed = self.current_speed
                    else:
                        speed = self.current_speed

                    if speed <= 0:
                        logger.warning(f"Invalid speed {speed}, resetting to 1000")
                        speed = 1000

                    if last_time > 0:
                        interval = (note['time'] - last_time) / 1000 * (1000 / speed)
                        start = time.perf_counter()
                        
                        while (time.perf_counter() - start) < interval:
                            if self.stop_event.is_set():
                                break
                            if self.pause_flag.is_set():
                                with self.status_lock:
                                    self.pause_count += 1
                                self.pause_start = time.time()
                                self._release_all()
                                logger.info("Playback paused")
                                
                                while self.pause_flag.is_set() and not self.stop_event.is_set():
                                    time.sleep(0.1)
                                
                                if self.stop_event.is_set():
                                    break
                                
                                pause_duration = time.time() - self.pause_start
                                self.total_pause_time += pause_duration
                                
                                logger.info(f"Playback resumed after {pause_duration:.2f}s pause")

                                if self.enable_ramping:
                                    self.is_ramping_begin = True
                                    self.ramp_counter = 0
                                    self.is_ramping_end = False
                                
                                time.sleep(self.pause_resume_delay)
                                start = time.perf_counter()
                            time.sleep(0.001)
                    
                    if self.stop_event.is_set():
                        break

                    key = self.key_map.get(note['key_lower'])
                    if key:
                        try:
                            self.keyboard.press(key)
                            self.scheduler.add(key, self.press_duration)
                            logger.debug(f"Pressed key: {key} for note {i+1}/{self.note_count}")
                        except Exception as e:
                            logger.error(f"Key press error: {e}")
                    
                    last_time = note['time']

                    if i == len(notes) - 1:
                        time.sleep(self.press_duration)      
            except Exception as e:
                logger.error(f"Unexpected playback error: {e}", exc_info=True)
            finally:
                self._release_all()
                self.playback_active = False
                self.pause_enabled = False
        except Exception as e:
            logger.critical(f"Playback initialization failed: {e}", exc_info=True)
            self._release_all()
            raise

    def _release_all(self):
        self.scheduler.reset()
        for key in set(self.key_map.values()):
            try: 
                self.keyboard.release(key)
            except Exception as e: 
                logger.error(f"Key release error: {e}")

    def stop(self):
        if not self.playback_active:
            return
            
        self.stop_event.set()
        self.pause_flag.clear()
        self.pause_enabled = False
        self._release_all()
        self.playback_active = False

    def set_speed(self, speed):
        if speed <= 0:
            logger.warning(f"Invalid speed {speed}, resetting to 1000")
            self.current_speed = 1000
        else:
            self.current_speed = speed

# -------------------------------
# Language Window
# -------------------------------

class LanguageWindow:
    _open = False

    @classmethod
    def show(cls):
        if cls._open: 
            return
            
        cls._open = True
        root = ctk.CTk()
        root.title(LanguageManager.get('language_window_title'))
        root.geometry("400x200")
        root.iconbitmap("resources/icons/icon.ico")
        
        languages = LanguageManager.get_languages()
        lang_dict = {name: code for code, name, _ in languages}
        default_name = next((n for c, n, _ in languages if c == LanguageManager._current_lang), 
                            languages[0][1] if languages else "English")
        
        ctk.CTkLabel(root, text=LanguageManager.get('select_language'), font=("Arial", 14)).pack(pady=10)
        
        combo = ctk.CTkComboBox(root, values=list(lang_dict.keys()), state="readonly")
        combo.set(default_name)
        combo.pack(pady=10)
        
        def save():
            selected_name = combo.get()
            if code := lang_dict.get(selected_name):
                LanguageManager.set_language(code)
                messagebox.showinfo("Info", LanguageManager.get('language_saved'))
            root.destroy()
            
        ctk.CTkButton(root, text=LanguageManager.get('save_button_text'), command=save).pack(pady=20)
        root.mainloop()
        cls._open = False

# -------------------------------
# Music App
# -------------------------------

class MusicApp:
    def __init__(self):
        setup_logging(VERSION)
        self._init_language()
        self._check_running()

        if ConfigManager.get_value("sky_exe_path") is None:
            SkyChecker.show_initial_settings()

        self._init_player()
        self._init_gui()
        self._setup_key_listener()
        self._log_system_info()

    def _init_language(self):
        LanguageManager.init()
        if not LanguageManager._current_lang:
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
        self.duration_presets = config["key_press_durations"]
        self.speed_presets = config["speed_presets"]
        self.pause_key = config.get("pause_key")
        
        self.player.keypress_enabled = False
        self.player.speed_enabled = False
        self.player.pause_enabled = False
        
        self.smooth_ramping_enabled = config.get("enable_ramping", False)
        self.ramping_info_display_count = min(config.get("ramping_info_display_count", 0), MAX_RAMPING_INFO_DISPLAY)
        self.show_ramping_info = self.ramping_info_display_count < MAX_RAMPING_INFO_DISPLAY

    def _setup_key_listener(self):
        try:
            self.key_listener = Listener(on_press=self._handle_keypress)
            self.key_listener.start()
        except Exception as e:
            logger.error(f"Failed to start key listener: {e}")
            messagebox.showerror("Error", "Failed to initialize keyboard listener")

    def _log_system_info(self):
        config = ConfigManager.get_config()
        lang_code = LanguageManager._current_lang
        layout = next((lyt for code, _, lyt in LanguageManager.get_languages() if code == lang_code), "QWERTY")
        
        is_custom = False
        key_map_details = []
        
        try:
            default_key_map = KeyboardLayoutManager.load_defaults_from_xml(layout)
            current_key_map = config.get("key_mapping", {})
            
            is_custom = current_key_map != default_key_map
            
            all_keys = set(default_key_map.keys()).union(set(current_key_map.keys()))
            for key in sorted(all_keys):
                current_val = current_key_map.get(key, "MISSING")
                default_val = default_key_map.get(key, "N/A")
                
                if current_val == "MISSING":
                    key_map_details.append(f"  {key}: MISSING (default: '{default_val}')")
                elif key not in default_key_map:
                    key_map_details.append(f"  {key}: {current_val} (custom key)")
                elif current_val == default_val:
                    key_map_details.append(f"  {key}: {current_val} (default)")
                else:
                    key_map_details.append(f"  {key}: {current_val} (modified from '{default_val}')")
                    
        except Exception as e:
            logger.error(f"Error when analyzing the button assignment: {e}")
            is_custom = True
            key_map_details.append("  [Error: Could not load key mapping]")

        layout_display = "Custom" if is_custom else layout

        timing = config.get("timing_config", {})
        info = [
            "== Player Config ==",
            f"Language: {lang_code}",
            f"Keyboard Layout: {layout_display}",
            f"Theme: {config.get('theme')}",
            "",
            "== Timing Config ==",
            f"Initial Delay: {timing.get('initial_delay')}s",
            f"Pause/Resume Delay: {timing.get('pause_resume_delay')}s",
            f"Ramp Steps Begin: {timing.get('ramp_steps_begin')}",
            f"Ramp Steps End: {timing.get('ramp_steps_end')}",
            "",
            "== Player Settings ==",
            f"Pause Key: '{config.get('pause_key')}'",
            f"Speed Presets: {config.get('speed_presets')}",
            f"Press Duration Presets: {config.get('key_press_durations')}",
            f"Enable Ramping: {config.get('enable_ramping')}",
            f"Ramping Info Display Count: {config.get('ramping_info_display_count')}",
            "",
            "== Key Mapping ==",
            *key_map_details
        ]

        try:
            logger.info("Application Config:\n\t" + "\n\t".join(info))
        except UnicodeEncodeError:
            cleaned_info = [line.encode('ascii', 'replace').decode('ascii') for line in info]
            logger.info("Application Config (ASCII-safe):\n\t" + "\n\t".join(cleaned_info))
        
        logger.info("Full configuration logged")

    def _init_gui(self):
        try:
            self.root = ctk.CTk()
            self.root.title(LanguageManager.get("project_title"))
            self.root.iconbitmap("resources/icons/icon.ico")
            self.root.protocol('WM_DELETE_WINDOW', self._shutdown)
            
            theme = ConfigManager.get_value("theme", "dark")
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
            self._play_song, 200, 40, True
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
                ConfigManager.save({
                    "enable_ramping": self.smooth_ramping_enabled,
                    "ramping_info_display_count": self.ramping_info_display_count
                })
        else:
            if self.show_ramping_info:
                self.ramping_frame.pack(pady=5, before=self.play_btn)

        self._adjust_window_size()
        logger.info(f"Smooth ramping {'enabled' if self.smooth_ramping_enabled else 'disabled'}")

    def _toggle_theme(self):
        try:
            current = ctk.get_appearance_mode().lower()
            new_theme = "light" if current == "dark" else "dark"
            ctk.set_appearance_mode(new_theme)
            self.theme_btn.configure(text="🌞" if new_theme == "light" else "🌙")
            ConfigManager.save({"theme": new_theme})
        except Exception as e:
            logger.error(f"Theme toggle failed: {e}")

    def _open_releases(self, event):
        try:
            if self.update_status == "update" and self.update_url:
                webbrowser.open(self.update_url)
            else:
                webbrowser.open("https://github.com/VanilleIce/ProjectLyrica")
        except Exception as e:
            messagebox.showerror("Error", f"Browser error: {e}")

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

                try:
                    relative_path = Path(file).relative_to(Path.cwd())
                    logger.info(f"Selected song: {relative_path}")
                except ValueError:
                    logger.info(f"Selected song: {file}")
        except Exception as e:
            logger.error(f"File selection failed: {e}")
            messagebox.showerror("Error", LanguageManager.get("file_selection_error"))

    def _play_song(self):
        if not self.selected_file:
            messagebox.showwarning("Warning", LanguageManager.get("choose_song_warning"))
            return
            
        if self.player.playback_active:
            self.player.stop()
            
        try:
            song = self.player.parse_song(self.selected_file)
            Thread(target=self._play_thread, args=(song,), daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", f"{LanguageManager.get('play_error_message')}: {e}")

    def _play_thread(self, song_data):
        logger.info("Starting playback thread")
        
        try:
            relative_path = Path(self.selected_file).relative_to(Path.cwd())
            logger.info(f"Playing song from: {relative_path}")
        except ValueError:
            logger.info(f"Playing song from: {self.selected_file}")
        
        logger.info("Attempting to focus Sky window")
        window_focused = False
        focus_attempts = 3
        
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
        except Exception as e:
            logger.critical(f"Playback thread crashed: {e}", exc_info=True)
            self.root.after(0, lambda: messagebox.showerror("Critical Error", f"Playback failed: {str(e)}"))
        finally:
            try:
                winsound.Beep(1000, 500)
            except Exception as e:
                logger.warning(f"Could not play completion beep: {e}")
            logger.info("Playback thread completed")
            self.root.after(0, lambda: self.play_btn.configure(
                text=LanguageManager.get("play_button_text"),
                state="normal"
            ))

    def _handle_keypress(self, key):
        try:
            if hasattr(key, 'char') and key.char == self.pause_key and self.player.pause_enabled:
                logger.debug(f"Pause key pressed: {key}")
                if self.player.pause_flag.is_set():
                    self.player.pause_flag.clear()
                    if window := self.player._find_sky_window():
                        self.player._focus_window(window)
                else:
                    self.player.pause_flag.set()
        except Exception as e:
            logger.error(f"Keypress handling failed: {e}")

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
            if speed <= 0:
                messagebox.showerror("Error", LanguageManager.get("invalid_speed"))
                return
                
            self.player.set_speed(speed)
            self.speed_label.configure(text=f"{LanguageManager.get('current_speed')}: {speed}")
        except Exception as e:
            logger.error(f"Speed setting failed: {e}")

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