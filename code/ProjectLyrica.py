# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import json, time, os, sys, winsound, heapq, ctypes, webbrowser, logging
import pygetwindow as gw
import customtkinter as ctk
from pathlib import Path
from threading import Event, Thread, Lock
from pynput.keyboard import Controller, Listener, Key
from tkinter import filedialog, messagebox
import xml.etree.ElementTree as ET
from update_checker import check_update
from logging_setup import setup_logging

logger = logging.getLogger("ProjectLyrica")

# -------------------------------
# Constante
# -------------------------------

SETTINGS_FILE = 'settings.json'
DEFAULT_WINDOW_SIZE = (400, 280)
EXPANDED_SIZE = (400, 375)
FULL_SIZE = (400, 470)
VERSION = "2.3.1"

# -------------------------------
# Language Manager
# -------------------------------

class LanguageManager:
    _translations = {}
    _current_lang = None
    _languages = []

    @classmethod
    def init(cls):
        config = ConfigManager.get_config()
        cls._current_lang = config.get("selected_language")
        cls._languages = cls._load_languages()

    @staticmethod
    def _load_languages():
        lang_file = Path('resources/config/lang.xml')
        try:
            tree = ET.parse(lang_file)
            return [
                (lang.get('code'), lang.text, lang.get('key_layout'))
                for lang in tree.findall('language')
                if lang.get('code') and lang.text
            ]
        except Exception as e:
            logger.error(f"Language load error: {e}")
            messagebox.showerror("Error", f"Language error: {e}")
            return []

    @classmethod
    def _get_translations(cls, lang_code):
        if lang_code in cls._translations:
            return cls._translations[lang_code]
        
        lang_file = Path(f'resources/lang/{lang_code}.xml')
        try:
            tree = ET.parse(lang_file)
            translations = {t.get('key'): t.text for t in tree.findall('translation')}
            cls._translations[lang_code] = translations
            return translations
        except FileNotFoundError:
            return cls._get_translations('en_US') if lang_code != 'en_US' else {}
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return {}

    @classmethod
    def get(cls, key):
        lang = cls._current_lang or 'en_US'
        trans = cls._get_translations(lang).get(key)
        return trans or cls._get_translations('en_US').get(key) or f"[{key}]"

    @classmethod
    def set_language(cls, lang_code):
        config = ConfigManager.get_config()
        try:
            layout = next((lyt for code, _, lyt in cls._languages if code == lang_code), "QWERTY")
        except StopIteration:
            layout = "QWERTY"
            logger.warning(f"Layout not found for language: {lang_code}, using default")
        
        try:
            key_map = KeyboardLayoutManager.load(layout)
        except Exception as e:
            logger.error(f"Layout error: {e}")
            key_map = config.get("key_mapping", KeyboardLayoutManager.load("QWERTY"))
        
        ConfigManager.save({
            "selected_language": lang_code,
            "keyboard_layout": layout,
            "key_mapping": key_map
        })
        cls._current_lang = lang_code

    @classmethod
    def get_languages(cls):
        return cls._languages

# -------------------------------
# Config Manager
# -------------------------------

class ConfigManager:
    DEFAULT = {
        "key_press_durations": [0.2, 0.248, 0.3, 0.5, 1.0],
        "speed_presets": [600, 800, 1000, 1200],
        "selected_language": None,
        "keyboard_layout": None,
        "key_mapping": {},
        "timing_config": {
            "initial_delay": 1.4,
            "pause_resume_delay": 1.2,
            "ramp_steps": 20
        },
        "pause_key": "#",
        "theme": "dark"
    }

    _config = None

    @classmethod
    def get_config(cls):
        if cls._config:
            return cls._config
            
        try:
            with open(SETTINGS_FILE, 'r', encoding="utf-8") as f:
                user_config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            user_config = {}
        
        cls._config = cls.DEFAULT.copy()
        for key, value in user_config.items():
            if key in ["timing_config", "key_mapping"] and isinstance(value, dict):
                cls._config[key].update(value)
            else:
                cls._config[key] = value
        return cls._config

    @classmethod
    def save(cls, updates):
        config = cls.get_config()
        for key, value in updates.items():
            if key in ["timing_config", "key_mapping"] and isinstance(value, dict):
                config[key].update(value)
            else:
                config[key] = value
        
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=3, ensure_ascii=False)

    @classmethod
    def get_value(cls, key, default=None):
        keys = key.split('.')
        value = cls.get_config()
        for k in keys:
            value = value.get(k, {})
        return value or default or cls.DEFAULT.get(key)

# -------------------------------
# Keyboard Layout Manager
# -------------------------------

class KeyboardLayoutManager:
    @staticmethod
    def load(name):
        file_path = Path(f'resources/layouts/{name.lower()}.xml')
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            layout = {}
            for key in root.findall('key'):
                key_id = key.get('id')
                if key_id:
                    key_text = key.text.strip() if key.text else ""
                    layout[key_id] = key_text
            return layout
        except Exception as e:
            logger.error(f"Layout load error: {e}")
            logger.error(f"Failed to load layout from: {file_path.resolve()}")
            raise RuntimeError(f"Could not load keyboard layout: {name}") from e

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
        while not self.stop_event.is_set():
            with self.lock:
                now = time.time()
                release_keys = []
                while self.queue and self.queue[0][0] <= now:
                    _, key = heapq.heappop(self.queue)
                    release_keys.append(key)
            
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

# -------------------------------
# Music Player
# -------------------------------

class MusicPlayer:
    def __init__(self):
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

        timing = config["timing_config"]
        self.initial_delay = timing["initial_delay"]
        self.pause_resume_delay = timing["pause_resume_delay"]
        self.ramp_steps = timing["ramp_steps"]
        self.is_ramping = False
        self.ramp_counter = 0
        
        self.start_time = 0
        self.note_count = 0
        self.pause_count = 0
        self.pause_start = 0
        self.total_pause_time = 0

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
        for title in ["Sky", "Sky: Children of the Light"]:
            windows = gw.getWindowsWithTitle(title)
            if windows: 
                return windows[0]
        return None

    def _focus_window(self, window):
        try:
            if window.isMinimized: 
                window.restore()
            if not window.isActive:
                for _ in range(3):
                    window.activate()
                    time.sleep(0.1)
                    if window.isActive:
                        break
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
        except Exception as e:
            logger.error(f"Parse error: {e}")
            raise

    def play(self, song_data):
        self.logger.info("Starting song playback")
        if self.playback_active:
            self.stop()
        
        self.scheduler.restart()
        
        self.playback_active = True
        self.scheduler.reset()
        self.stop_event.clear()
        self.is_ramping = True
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
        self.start_time = time.time()
        last_time = 0
        
        try:
            for i, note in enumerate(notes):
                if self.stop_event.is_set():
                    logger.info("Playback stopped by user")
                    break
                    
                if self.is_ramping:
                    ramp_factor = 0.5 + 0.5 * (self.ramp_counter / self.ramp_steps)
                    speed = max(500, self.current_speed * min(1.0, ramp_factor))
                    self.ramp_counter += 1
                    if self.ramp_counter >= self.ramp_steps:
                        self.is_ramping = False
                        logger.debug("Ramping completed")
                else:
                    speed = self.current_speed

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
                            self.is_ramping = True
                            self.ramp_counter = 0
                            
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
        self._release_all()
        self.playback_active = False

    def set_speed(self, speed):
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
        self.pause_key = config.get("pause_key", "#")

    def _setup_key_listener(self):
        self.key_listener = Listener(on_press=self._handle_keypress)
        self.key_listener.start()

    def _log_system_info(self):
        config = ConfigManager.get_config()
        lang_code = LanguageManager._current_lang
        layout = next((lyt for code, _, lyt in LanguageManager.get_languages() if code == lang_code))
        
        is_custom = False
        key_map_details = []
        default_key_map = {}
        
        try:
            default_key_map = KeyboardLayoutManager.load(layout)
            
            is_custom = config["key_mapping"] != default_key_map
        except Exception as e:
            logger.error(f"Layout load error in logging: {e}")
            is_custom = True
        
        for key, value in config["key_mapping"].items():
            if key in default_key_map:
                default_value = default_key_map[key]
                if value != default_value:
                    key_map_details.append(f"  {key}: {value} (modified from '{default_value}')")
                else:
                    key_map_details.append(f"  {key}: {value} (default)")
            else:
                key_map_details.append(f"  {key}: {value} (custom key)")
        
        missing_keys = [k for k in default_key_map if k not in config["key_mapping"]]
        for key in missing_keys:
            key_map_details.append(f"  {key}: MISSING (default: '{default_key_map[key]}')")
        
        timing = config.get("timing_config", {})
        
        info = [
            "== Player Config ==",
            f"Language: {lang_code}",
            f"Keyboard Layout: {layout} ({'Custom' if is_custom else 'Standard'})",
            f"Theme: {config.get('theme')}",
            "",
            "== Timing Config ==",
            f"Initial Delay: {timing.get('initial_delay')}s",
            f"Pause/Resume Delay: {timing.get('pause_resume_delay')}s",
            f"Ramp Steps: {timing.get('ramp_steps')}",
            "",
            "== Player Settings ==",
            f"Pause Key: '{config.get('pause_key')}'",
            f"Speed Presets: {config.get('speed_presets')}",
            f"Press Duration Presets: {config.get('key_press_durations')}",
            "",
            "== Key Mapping =="
        ]
        
        info.extend(key_map_details)
        
        try:
            log_message = "Application Config:\n\t" + "\n\t".join(info)
            logger.info(log_message)
        except UnicodeEncodeError:
            cleaned_info = []
            for line in info:
                try:
                    line.encode('utf-8')
                    cleaned_info.append(line)
                except UnicodeEncodeError:
                    cleaned_line = line.encode('ascii', 'replace').decode('ascii')
                    cleaned_info.append(cleaned_line)
            
            logger.info("Application Config:\n\t" + "\n\t".join(cleaned_info))

    def _init_gui(self):
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

    def _check_updates(self):
        try:
            return check_update(VERSION, "VanilleIce/ProjectLyrica")
        except:
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
        
        self.play_btn = self._create_button(
            LanguageManager.get("play_button_text"), 
            self._play_song, 200, 40, True
        )
        
        self.duration_frame = ctk.CTkFrame(self.root)
        self.duration_slider = ctk.CTkSlider(
            self.duration_frame, from_=0.1, to=1.0, 
            number_of_steps=90, width=200
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
            btn = ctk.CTkButton(
                self.speed_preset_frame, text=str(speed), width=50,
                command=lambda s=speed: self._set_speed(s)
            )
            btn.pack(side="left", padx=2)

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
        self.keypress_btn.pack(pady=5)
        self.speed_btn.pack(pady=5)
        self.play_btn.pack(pady=10)
        
        self._adjust_window_size()

    def _adjust_window_size(self):
        if self.player.keypress_enabled and self.player.speed_enabled:
            self.root.geometry(f"{FULL_SIZE[0]}x{FULL_SIZE[1]}")
        elif self.player.keypress_enabled or self.player.speed_enabled:
            self.root.geometry(f"{EXPANDED_SIZE[0]}x{EXPANDED_SIZE[1]}")
        else:
            self.root.geometry(f"{DEFAULT_WINDOW_SIZE[0]}x{DEFAULT_WINDOW_SIZE[1]}")

    def _toggle_theme(self):
        current = ctk.get_appearance_mode().lower()
        new_theme = "light" if current == "dark" else "dark"
        ctk.set_appearance_mode(new_theme)
        self.theme_btn.configure(text="🌞" if new_theme == "light" else "🌙")
        ConfigManager.save({"theme": new_theme})

    def _open_releases(self, event):
        try:
            if self.update_status == "update" and self.update_url:
                webbrowser.open(self.update_url)
            else:
                webbrowser.open("https://github.com/VanilleIce/ProjectLyrica")
        except Exception as e:
            messagebox.showerror("Error", f"Browser error: {e}")

    def _select_file(self):
        logger.info("Opening file selection dialog")
        songs_dir = Path("resources/Songs")
        file = filedialog.askopenfilename(
            initialdir=songs_dir if songs_dir.exists() else Path.cwd(),
            filetypes=[(LanguageManager.get("supported_formats"), "*.json *.txt *.skysheet")]
        )
        if file:
            self.selected_file = file
            name = Path(file).name
            display = name if len(name) <= 30 else f"{name[:25]}..."
            self.file_btn.configure(text=display)
            
            try:
                relative_path = Path(file).relative_to(Path.cwd())
                logger.info(f"Selected song: {relative_path}")
            except ValueError:
                logger.info(f"Selected song: {file}")

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
            
            time.sleep(0.2)
        
        if not window_focused:
            logger.error(f"Failed to focus Sky window after {focus_attempts} attempts")
            self.root.after(0, lambda: messagebox.showerror("Error", LanguageManager.get("sky_not_running")))
            return
        
        logger.debug(f"Waiting initial delay: {self.player.initial_delay}s")
        time.sleep(self.player.initial_delay)
        
        try:
            logger.info("Starting actual playback")
            self.player.play(song_data)
        except Exception as e:
            logger.error(f"Playback error: {e}", exc_info=True)
            self.root.after(0, lambda: messagebox.showerror("Error", f"Playback failed: {str(e)}"))
        finally:
            winsound.Beep(1000, 500)
            logger.info("Playback thread completed")
            self.root.after(0, lambda: self.play_btn.configure(
                text=LanguageManager.get("play_button_text"),
                state="normal"
            ))
            self.root.after(0, lambda: self.status_label.configure(
                text=LanguageManager.get("play_complete")
            ))

    def _handle_keypress(self, key):
        if hasattr(key, 'char') and key.char == self.pause_key:
            logger.debug(f"Pause key pressed: {key}")
            if self.player.pause_flag.is_set():
                self.player.pause_flag.clear()
                if window := self.player._find_sky_window():
                    self.player._focus_window(window)
            else:
                self.player.pause_flag.set()

    def _set_duration(self, event):
        duration = round(self.duration_slider.get(), 3)
        self.player.press_duration = duration
        self.duration_label.configure(text=f"{LanguageManager.get('duration')} {duration} s")

    def _apply_preset(self, duration):
        self.player.press_duration = duration
        self.duration_slider.set(duration)
        self.duration_label.configure(text=f"{LanguageManager.get('duration')} {duration} s")

    def _set_speed(self, speed):
        self.player.set_speed(speed)
        self.speed_label.configure(text=f"{LanguageManager.get('current_speed')}: {speed}")

    def _toggle_keypress(self):
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

    def _toggle_speed(self):
        self.player.speed_enabled = not self.player.speed_enabled
        status = "enabled" if self.player.speed_enabled else "disabled"
        self.speed_btn.configure(text=f"{LanguageManager.get('speed_control')}: {LanguageManager.get(status)}")
        
        if self.player.speed_enabled:
            self.speed_frame.pack(pady=5, before=self.play_btn)
            self.speed_preset_frame.pack(pady=5)
            self.speed_label.pack(pady=5)
        else:
            self.speed_frame.pack_forget()
            self.player.current_speed = 1000
            
        self._adjust_window_size()

    def _shutdown(self):
        logger.info("Application shutdown initiated")
        try:
            if self.player.playback_active:
                self.player.stop()
            if hasattr(self, 'key_listener'):
                self.key_listener.stop()
        except Exception as e:
            logger.error(f"Shutdown error: {e}")
        finally:
            if hasattr(self, '_mutex'):
                ctypes.windll.kernel32.CloseHandle(self._mutex)
            self.root.destroy()
            logger.info("Application closed")

    def run(self):
        self.root.mainloop()

# -------------------------------
# App Starter
# -------------------------------

if __name__ == "__main__":
    MusicApp().run()