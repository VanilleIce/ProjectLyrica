# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.
# Source code: https://github.com/VanilleIce/ProjectLyrica

import json, time, os, sys, winsound, heapq, ctypes, webbrowser, logging
import pygetwindow as gw
import customtkinter as ctk
from pathlib import Path
from threading import Event, Thread, Lock
from pynput.keyboard import Controller, Listener
from tkinter import filedialog, messagebox
import xml.etree.ElementTree as ET
from update_checker import check_update
from logging_setup import setup_logging

logger = logging.getLogger(__name__)

SETTINGS_FILE = 'settings.json'
DEFAULT_WINDOW_SIZE = (400, 280)
EXPANDED_SIZE = (400, 375)
FULL_SIZE = (400, 470)
version = "2.3.0"

# -------------------------------
# Language Manager Class
# -------------------------------

class LM:
    _translations_cache = {}
    _selected_language = None
    _available_languages = []

    @classmethod
    def initialize(cls):
        logger.info("Initializing language system")
        cls._selected_language = ConfigManager.load_config().get("selected_language")
        cls._available_languages = cls.load_available_languages()

    @staticmethod
    def load_available_languages():
        logger.debug("Scanning available languages")
        lang_file = os.path.join('resources', 'config', 'lang.xml')
        try:
            tree = ET.parse(lang_file)
            languages = [
                (lang.get('code'), lang.text, lang.get('key_layout'))
                for lang in tree.findall('language')
                if lang.get('code') and lang.text
            ]
            logger.info(f"Found {len(languages)} available languages")
            return languages
        except Exception as e:
            logger.error(f"Error loading languages: {e}")
            messagebox.showerror("Error", f"Error loading languages: {e}")
            return []

    @classmethod
    def load_translations(cls, language_code):
        logger.debug(f"Loading translations for: {language_code}")
        if language_code in cls._translations_cache:
            return cls._translations_cache[language_code]
        
        lang_file = os.path.join('resources', 'lang', f"{language_code}.xml")
        try:
            tree = ET.parse(lang_file)
            translations = {
                t.get('key'): t.text
                for t in tree.findall('translation')
                if t.get('key') and t.text
            }
            cls._translations_cache[language_code] = translations
            logger.info(f"Loaded {len(translations)} translations for {language_code}")
            return translations
        except FileNotFoundError:
            logger.warning(f"Translation file not found for {language_code}, falling back to en_US")
            return cls.load_translations('en_US') if language_code != 'en_US' else {}
        except Exception as e:
            logger.error(f"Error loading translations: {e}")
            messagebox.showerror("Error", f"Error loading translations: {e}")
            return {}

    @classmethod
    def get_translation(cls, key):
        lang = cls._selected_language or 'en_US'
        trans = cls.load_translations(lang).get(key)
        if not trans and lang != 'en_US':
            trans = cls.load_translations('en_US').get(key)
        return trans or f"[{key}]"

    @classmethod
    def save_language(cls, language_code):
        logger.info(f"Updating language: {language_code}")
        cls._selected_language = language_code
        config = ConfigManager.load_config()
        
        layout_name = next(
            (key_layout for code, _, key_layout in cls._available_languages 
            if code == language_code),
            "QWERTY"
        )
        logger.debug(f"Selected keyboard layout: {layout_name}")
        
        try:
            layout_mapping = KeyboardLayoutManager.load_layout(layout_name)
        except Exception as e:
            logger.error(f"Error loading layout: {e}")
            messagebox.showerror("Error", f"Error loading layout: {e}")
            layout_mapping = config.get("key_mapping", {})
        
        ConfigManager.save_config({
            "selected_language": language_code,
            "keyboard_layout": layout_name,
            "key_mapping": layout_mapping
        })
        logger.info(f"Language updated | Code: {language_code} | Layout: {layout_name}")

    @classmethod
    def get_available_languages(cls):
        if not cls._available_languages:
            cls._available_languages = cls.load_available_languages()
        return cls._available_languages

# -------------------------------
# Config Manager
# -------------------------------

class ConfigManager:
    DEFAULT_CONFIG = {
        "key_press_durations": [0.2, 0.248, 0.3, 0.5, 1.0],
        "speed_presets": [600, 800, 1000, 1200],
        "selected_language": None,
        "keyboard_layout": None,
        "key_mapping": {},
        "timing_config": {
            "initial_delay": 1.4,
            "pause_resume_delay": 0.8,
            "ramp_steps": 20
        },
        "pause_key": "#",
        "theme": "dark"
    }

    _config_cache = None

    @classmethod
    def load_config(cls):
        logger.debug("Loading configuration")
        if cls._config_cache is not None:
            return cls._config_cache
            
        try:
            with open(SETTINGS_FILE, 'r', encoding="utf-8") as file:
                user_config = json.load(file)
            logger.info("Configuration loaded from file")
        except FileNotFoundError:
            logger.warning("Settings file not found, using defaults")
            user_config = {}
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding settings file: {e}")
            user_config = {}
        
        config = cls.DEFAULT_CONFIG.copy()
        
        for key, value in user_config.items():
            if key == "timing_config" and isinstance(value, dict):
                config[key] = {**config[key], **value}
            elif key == "key_mapping" and isinstance(value, dict):
                config[key] = {**config[key], **value}
            else:
                config[key] = value
        
        cls._config_cache = config
        logger.info("Configuration loaded successfully")
        logger.debug(f"Config details: {json.dumps(config, indent=2)}")
        return config

    @classmethod
    def save_config(cls, config_data):
        logger.info("Saving configuration updates")
        current_config = cls.load_config()
        
        for key, value in config_data.items():
            if key in ["timing_config", "key_mapping"] and isinstance(value, dict):
                current_config[key] = {**current_config.get(key, {}), **value}
            else:
                current_config[key] = value
        
        cls._config_cache = current_config
                
        try:
            with open(SETTINGS_FILE, 'w', encoding="utf-8") as file:
                json.dump(current_config, file, indent=3, ensure_ascii=False)
            logger.info(f"Config updated | Keys: {', '.join(config_data.keys())}")
            logger.debug(f"Config details: {json.dumps(config_data, indent=2)}")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")

    @classmethod
    def get_value(cls, key, default=None):
        config = cls.load_config()
        keys = key.split('.')
        value = config
        try:
            for k in keys:
                value = value[k]
            return value
        except KeyError:
            return default if default is not None else cls.DEFAULT_CONFIG.get(key)

# -------------------------------
# GUI: Language Selection
# -------------------------------

class LanguageWindow:
    _open = False

    @classmethod
    def show(cls):
        if cls._open:
            return
            
        logger.info("Showing language selection window")
        cls._open = True
        root = ctk.CTk()
        root.title(LM.get_translation('language_window_title'))
        root.geometry("400x200")
        root.iconbitmap("resources/icons/icon.ico")
        
        languages = LM._available_languages
        language_dict = {name: code for code, name, _ in languages}
        default_name = next((name for code, name, _ in languages if code == LM._selected_language), 
                            languages[0][1] if languages else "English")
        
        label = ctk.CTkLabel(root, text=LM.get_translation('select_language'), font=("Arial", 14))
        label.pack(pady=10)
        
        combo = ctk.CTkComboBox(root, values=list(language_dict.keys()), state="readonly")
        combo.set(default_name)
        combo.pack(pady=10)
        
        def save():
            selected_name = combo.get()
            selected_code = language_dict.get(selected_name)
            if selected_code:
                logger.info(f"User selected language: {selected_name} ({selected_code})")
                LM.save_language(selected_code)
                messagebox.showinfo("Info", LM.get_translation('language_saved'))
            root.destroy()
            
        button = ctk.CTkButton(root, text=LM.get_translation('save_button_text'), command=save)
        button.pack(pady=20)
        
        root.protocol("WM_DELETE_WINDOW", lambda: [root.destroy(), setattr(cls, '_open', False)])
        root.mainloop()
        cls._open = False
        logger.info("Language window closed")

# -------------------------------
# KeyboardLayoutManager
# ------------------------------- 

class KeyboardLayoutManager:
    @classmethod
    def load_layout(cls, layout_name):
        try:
            file_path = os.path.join('resources', 'layouts', f"{layout_name.lower()}.xml")
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Layout file not found: {file_path}")
                
            tree = ET.parse(file_path)
            layout = {
                key.get('id'): (key.text or "").strip()
                for key in tree.getroot().findall('key')
                if key.get('id')
            }
            return layout
        except Exception as e:
            logger.error(f"Error loading layout: {str(e)}")
            raise

# -------------------------------
# NoteScheduler
# ------------------------------- 

class NoteScheduler:
    def __init__(self, release_callback):
        logger.info("Initializing scheduler subsystem")
        self.queue = []
        self.callback = release_callback
        self.lock = Lock()
        self.stop_event = Event()
        self.thread = Thread(target=self.run, daemon=True)
        self.thread.start()
        logger.info("Scheduler started with precision timing")
    
    def add(self, key, delay):
        with self.lock:
            heapq.heappush(self.queue, (time.time() + delay, key))
        logger.debug(f"Scheduled key release: {key} in {delay:.3f}s")
    
    def stop(self):
        logger.info("Stopping note scheduler")
        self.stop_event.set()
        self.thread.join(timeout=1.0)
    
    def reset(self):
        with self.lock:
            self.queue = []
        logger.debug("Note scheduler queue reset")
    
    def is_running(self):
        return self.thread.is_alive() and not self.stop_event.is_set()
    
    def run(self):
        logger.debug("Starting scheduler processing loop")
        while not self.stop_event.is_set():
            with self.lock:
                now = time.time()
                to_release = []
                while self.queue and self.queue[0][0] <= now:
                    _, key = heapq.heappop(self.queue)
                    to_release.append(key)
                next_time = self.queue[0][0] if self.queue else None
            
            for key in to_release:
                try:
                    self.callback(key)
                    logger.debug(f"Released key: {key}")
                except Exception as e:
                    logger.error(f"Key release failed: {str(e)}")
                    
            if next_time:
                sleep_time = max(0.001, next_time - time.time())
                time.sleep(sleep_time)
            else:
                time.sleep(0.01)
        logger.info("Scheduler processing loop ended")

# -------------------------------
# Music Player
# -------------------------------

class MusicPlayer:
    def __init__(self):
        logger.info("Initializing player core")
        self.pause_flag = Event()
        self.stop_event = Event()
        self.play_thread = None
        self.keyboard = Controller()

        self.keypress_enabled = False
        self.speed_enabled = False
        
        config = ConfigManager.load_config()

        self.song_cache = {}
        
        self.key_map = self._create_key_map(config["key_mapping"])
        self.press_duration = 0.1
        
        timing_config = config.get("timing_config", {})
        self.initial_delay = timing_config.get("initial_delay")
        self.pause_resume_delay = timing_config.get("pause_resume_delay")
        self.ramp_steps = timing_config.get("ramp_steps")
        
        self.speed_lock = Lock()
        self.current_speed = 1000
        self.ramp_counter = 0
        self.is_ramping = False

        self.playback_active = False
        
        self.window_cache = None
        self.cache_time = 0
        self.CACHE_EXPIRY = 10
        self.window_lock = Lock()
        self.scheduler = NoteScheduler(self.keyboard.release)

        logger.info(f"Key mapping loaded: {len(self.key_map)} keys")
        if config["key_mapping"]:
            logger.debug(f"Key mapping details: {json.dumps(config['key_mapping'], indent=2)}")

    def _create_key_map(self, mapping):
        return {f"{prefix}{key}".lower(): value 
                for prefix in ['', '1', '2', '3'] 
                for key, value in mapping.items()}

    def find_sky_window(self, force_search=False):
        now = time.time()
        
        with self.window_lock:
            if not force_search and self.window_cache and (now - self.cache_time) < self.CACHE_EXPIRY:
                return self.window_cache
                
            titles = ["Sky", "Sky: Children of the Light"]
            found_window = None
            
            for title in titles:
                try:
                    windows = gw.getWindowsWithTitle(title)
                    if windows:
                        found_window = windows[0]
                        break
                except Exception as e:
                    logger.error(f"Error searching for window '{title}': {e}")
            
            if found_window:
                logger.debug(f"Found Sky window: {found_window.title}")
            else:
                if not self.window_cache or force_search:
                    logger.warning("Sky window not found - searched titles: %s", titles)
                    try:
                        all_windows = gw.getAllWindows()
                        all_titles = [w.title for w in all_windows if w.title.strip()]
                        logger.debug("Top 10 available window titles: %s", all_titles[:10])
                    except Exception as e:
                        logger.error("Error listing windows: %s", str(e))
            
            self.window_cache = found_window
            self.cache_time = now
            return found_window

    def focus_window(self, window=None):
        target = window or self.window_cache
        if not target:
            logger.warning("No window to focus")
            return False
            
        try:
            logger.debug(f"Focusing window: {target.title}")
            logger.debug(f"Initial state: minimized={target.isMinimized}, active={target.isActive}")
            
            if target.isMinimized:
                target.restore()
            if not target.isActive:
                target.activate()
                
            logger.debug("Window focused successfully")
            return True
        except Exception as e:
            logger.error(f"Window focus failed: {str(e)}")
            try:
                logger.debug(f"Current state: minimized={target.isMinimized}, active={target.isActive}")
            except:
                logger.debug("Could not retrieve current window state")
            return False

    def parse_song(self, path):
        logger.info(f"Parsing song file: {Path(path).name}")
        if path in self.song_cache:
            logger.debug(f"Using cached song: {Path(path).name}")
            return self.song_cache[path]
        
        path_obj = Path(path)
        try:
            with path_obj.open('r', encoding='utf-8') as f:
                content = f.read().strip()
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            raise ValueError(f"Error reading file: {e}")

        if path_obj.suffix.lower() in ('.json', '.skysheet', '.txt'):
            try:
                data = json.loads(content)
                
                if isinstance(data, list) and len(data) == 1:
                    song_data = data[0]
                else:
                    song_data = data
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON format: {e}")
                raise ValueError(f"Invalid JSON format: {e}")
        else:
            logger.error(f"Unsupported file format: {path_obj.suffix}")
            raise ValueError("Unsupported file format")

        if "songNotes" not in song_data:
            logger.error("Missing songNotes in file")
            raise ValueError(LM.get_translation('missing_song_notes'))
        
        for note in song_data["songNotes"]:
            note['key_lower'] = note.get('key', '').lower()

        self.song_cache[path] = song_data
        logger.info(f"Song parsed | Notes: {len(song_data['songNotes'])}")
        return song_data

    def play_song(self, song_data):
        logger.info("Starting playback session")
        if self.playback_active:
            self.stop_playback()
            
        self.playback_active = True
        
        self.scheduler.reset()
        if not hasattr(self, 'scheduler') or not self.scheduler.is_running():
            logger.info("Restarting scheduler thread")
            self.scheduler = NoteScheduler(self.keyboard.release)
        
        notes = song_data.get("songNotes", [])
        logger.info(f"Playback initialized | Notes: {len(notes)} | Target speed: {self.current_speed}")

        if not notes:
            logger.error("Missing song notes - aborting playback")
            messagebox.showerror(LM.get_translation("error_title"), LM.get_translation("missing_song_notes"))
            return

        sky_window = self.find_sky_window(force_search=True)
        if not sky_window:
            logger.error("Sky not running - playback aborted")
            messagebox.showerror(LM.get_translation("error_title"), LM.get_translation("sky_not_running"))
            self.playback_active = False
            return
        
        self.is_ramping = True
        self.ramp_counter = 0
        self.stop_event.clear()
        self.was_paused = False
        
        try:
            last_note_time = 0
            logger.debug(f"Starting playback loop with {len(notes)} notes")
            for i, note in enumerate(notes):        
                with self.speed_lock:
                    target_speed = self.current_speed
                    
                if self.is_ramping:
                    ramp_factor = min(1.0, 0.5 + 0.5 * (self.ramp_counter / self.ramp_steps))
                    current_speed = max(500, target_speed * ramp_factor)
                    self.ramp_counter += 1
                    if self.ramp_counter >= self.ramp_steps:
                        self.is_ramping = False
                else:
                    current_speed = target_speed

                if last_note_time > 0:
                    note_interval = (note['time'] - last_note_time) / 1000
                    adjusted_interval = note_interval * (1000 / current_speed)
                    start_wait = time.perf_counter()

                    while (time.perf_counter() - start_wait) < adjusted_interval:
                        if self.stop_event.is_set():
                            break
                        if self.pause_flag.is_set():
                            self.was_paused = True
                            self._release_all_keys()
                            logger.info("Playback paused")
                            while self.pause_flag.is_set() and not self.stop_event.is_set():
                                time.sleep(0.1)
                            if self.stop_event.is_set():
                                break
                            self.is_ramping = True
                            self.ramp_counter = 0
                            time.sleep(self.pause_resume_delay)
                            logger.info("Playback resumed")
                            start_wait = time.perf_counter()
                        time.sleep(0.001)
                
                if self.stop_event.is_set():
                    break
                    
                key = self.key_map.get(note['key_lower'])
                if key:
                    self.keyboard.press(key)
                    self.scheduler.add(key, self.press_duration)
                    logger.debug(f"Pressed key: {key} (mapped from {note['key_lower']})")
                
                last_note_time = note['time']
                
            if not self.stop_event.is_set():
                logger.info("Playback completed successfully")
                
        except Exception as e:
            logger.error(f"Playback error: {str(e)}", exc_info=True)
        finally:
            self._release_all_keys()
            logger.debug("Released all keys after playback")

    def _release_all_keys(self):
        logger.debug("Releasing all keys")
        self.scheduler.reset()
        for key in self.key_map.values():
            try:
                self.keyboard.release(key)
            except Exception as e:
                logger.error(f"Key release error: {str(e)}")

    def stop_playback(self):
        if not self.playback_active:
            return
            
        logger.info("Terminating playback")
        try:
            self.stop_event.set()
            self.pause_flag.clear()
            self.scheduler.stop()
            self._release_all_keys()

            if self.play_thread and self.play_thread.is_alive():
                logger.debug("Waiting for play thread to finish")
                self.play_thread.join(timeout=0.5)
                if self.play_thread.is_alive():
                    logger.warning("Play thread did not terminate properly")
        except Exception as e:
            logger.error(f"Error during stop: {e}", exc_info=True)
        finally:
            self.playback_active = False
            logger.info("Playback fully stopped")

    def set_speed(self, speed):
        with self.speed_lock:
            logger.info(f"Setting playback speed: {speed}")
            self.current_speed = speed

# -------------------------------
# Main Application
# -------------------------------

class MusicApp:
    def __init__(self):
        setup_logging(version)

        self._mutex_handle = None
        LM.initialize()
        if not LM._selected_language:
            logger.info("No language selected, showing language window")
            LanguageWindow.show()

        if self.is_already_running():
            logger.error("Application is already running!")
            messagebox.showerror("Error", "Application is already running!")
            sys.exit(1)

        self.key_listener = Listener(on_press=self.handle_keypress)
        self.key_listener.start()
        logger.info("Key listener started")
        
        config = ConfigManager.load_config()
        self.duration_presets = config["key_press_durations"]
        self.speed_presets = config["speed_presets"]
        self.pause_key = config.get("pause_key", "#")
        logger.info("Configuration loaded")

        self.version = version
        self.update_status = "checking"
        self.latest_version = ""
        self.update_url = ""

        self.player = MusicPlayer()
        self.selected_file = None
        self.root = None
        self.is_playing = False

        self._log_system_info()

        try:
            logger.info("Checking for updates")
            result = check_update(self.version, "VanilleIce/ProjectLyrica")
            self.update_status = result[0]
            self.latest_version = result[1]
            self.update_url = result[2]
            logger.info(f"Update check result: {self.update_status}")
        except Exception as e:
            logger.error(f"Update check failed: {str(e)}")
            self.update_status = "error"
            self.latest_version = ""
            self.update_url = ""

        self._create_gui_components()
        self._setup_gui_layout()
        logger.info("GUI initialized")

    def _log_system_info(self):
        """Loggt detaillierte Systeminformationen"""
        config = ConfigManager.load_config()
        timing = config.get("timing_config", {})
        key_mapping = config.get("key_mapping", {})
        
        # 1. Ermittle das Standard-Layout für die aktuelle Sprache
        lang_code = LM._selected_language or 'en_US'
        standard_layout_name = "QWERTY"  # Default-Fallback
        layout_file_path = ""
        layout_keys = 0
        
        # Durchsuche die verfügbaren Sprachen für das Layout
        for code, _, layout in LM.get_available_languages():
            if code == lang_code:
                standard_layout_name = layout
                break
        
        # Bestimme den Pfad der Layout-Datei
        layout_file_path = os.path.join('resources', 'layouts', f"{standard_layout_name.lower()}.xml")
        
        # 2. Bestimme den Mapping-Typ und lade ggf. das Standard-Layout
        mapping_type = "STANDARD"
        diff_info = ""
        
        try:
            # Lade das Standard-Layout für diese Sprache
            standard_layout = KeyboardLayoutManager.load_layout(standard_layout_name)
            layout_keys = len(standard_layout)
            
            # Vergleiche mit dem konfigurierten Mapping
            if key_mapping != standard_layout:
                mapping_type = "CUSTOM"
                
                # Berechne Unterschiede für Debug-Info
                diff = {}
                for key in set(key_mapping.keys()) | set(standard_layout.keys()):
                    custom_val = key_mapping.get(key)
                    std_val = standard_layout.get(key)
                    if custom_val != std_val:
                        diff[key] = {"custom": custom_val, "standard": std_val}
                
                diff_info = f"\nMapping differences:\n{json.dumps(diff, indent=2)}"
        except Exception as e:
            logger.error(f"Could not verify mapping type: {e}")
            mapping_type = f"UNKNOWN ({e})"
        
        # 3. Erstelle die Systeminformationen
        info = [
            f"Version: {self.version}",
            f"Language: {lang_code}",
            f"Keyboard Layout: {config.get('keyboard_layout')}",
            f"Layout File: {layout_file_path}",
            f"Keys: {layout_keys}",
            f"Pause Key: {config.get('pause_key')}",
            f"Theme: {config.get('theme')}",
            "",
            "== Timing Config ==",
            f"Initial Delay: {timing.get('initial_delay')}s",
            f"Pause/Resume Delay: {timing.get('pause_resume_delay')}s",
            f"Ramp Steps: {timing.get('ramp_steps')}",
            "",
            "== Player Settings ==",
            f"Press Duration: {self.player.press_duration}s",
            f"Current Speed: {self.player.current_speed}",
            f"Speed Presets: {config.get('speed_presets')}",
            f"Press Duration Presets: {config.get('key_press_durations')}",
            "",
            "== Key Mapping ==",
            f"Type: {mapping_type}",
            f"Entries: {len(key_mapping)}"
        ]
        
        # 4. Logge die Informationen mit Debug-Details
        logger.info("System Configuration:\n\t" + "\n\t".join(info))
        
        if diff_info:
            logger.debug(diff_info)

    def is_already_running(self):
        self._mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, False, "ProjectLyricaMutex")
        error = ctypes.windll.kernel32.GetLastError()
        if error == 183:  # ERROR_ALREADY_EXISTS
            logger.warning("Application already running (mutex exists)")
            return True
        return False

    def _create_button(self, text, command, width=200, height=30, 
                    font=("Arial", 13), is_main=False, color=None):
        button = ctk.CTkButton(
            self.root, 
            text=text, 
            command=command,
            font=font,
            width=width,
            height=height
        )
        
        if color:
            button.configure(fg_color=color)
        
        if is_main:
            button.configure(font=("Arial", 14), height=40)
        
        return button

    def _create_gui_components(self):
        self.root = ctk.CTk()
        
        saved_theme = ConfigManager.load_config().get("theme", "light")
        ctk.set_appearance_mode(saved_theme)
        logger.info(f"Set theme: {saved_theme}")
        
        self.root.title(LM.get_translation("project_title"))
        self.root.iconbitmap("resources/icons/icon.ico")
        self.root.protocol('WM_DELETE_WINDOW', self.shutdown)

        self.status_frame = ctk.CTkFrame(self.root, fg_color="transparent", height=1)
        self.status_frame.pack(side="bottom", fill="x", padx=10, pady=3)
        
        self.title_label = ctk.CTkLabel(self.root, text=LM.get_translation("project_title"), font=("Arial", 18, "bold"))
        
        if self.update_status == "update":
            version_text = LM.get_translation('update_available_text').format(self.latest_version)
            text_color = "#FFA500"
            logger.warning(f"Update available: {self.latest_version}")
        elif self.update_status == "no_connection":
            version_text = LM.get_translation('no_connection_text')
            text_color = "#FF0000"
            logger.warning("No internet connection for update check")
        elif self.update_status == "error":
            version_text = LM.get_translation('update_error_text')
            text_color = "#FF0000"
            logger.error("Update check failed")
        else:
            version_text = LM.get_translation('current_version_text').format(self.version)
            text_color = "#1E90FF"
            logger.info("Application is up to date")
        
        self.version_link = ctk.CTkLabel(
            self.status_frame,
            text=version_text,
            font=("Arial", 11),
            text_color=text_color,
            cursor="hand2"
        )
        self.version_link.pack(side="right")
        self.version_link.bind("<Button-1>", self.open_github_releases)

        theme_icon = "🌞" if saved_theme == "light" else "🌙"
        self.theme_btn = ctk.CTkButton(
            self.status_frame,
            text=theme_icon,
            command=self.toggle_theme,
            width=30,
            height=30,
            font=("Arial", 16)
        )
        self.theme_btn.pack(side="right", padx=(0, 5))
        
        self.file_button = self._create_button(
            LM.get_translation("file_select_title"), 
            self.select_file, 
            width=300,
            height=40,
            font=("Arial", 14),
            color="grey"
        )
        
        keypress_text = f"{LM.get_translation('key_press')}: " + \
                       (LM.get_translation("enabled") if self.player.keypress_enabled else LM.get_translation("disabled"))
        self.keypress_toggle = self._create_button(keypress_text, self.toggle_keypress)
        
        self.duration_frame = ctk.CTkFrame(self.root)
        
        self.duration_slider = ctk.CTkSlider(
            self.duration_frame, 
            from_=0.1, 
            to=1.0, 
            number_of_steps=90, 
            command=self.set_press_duration, 
            width=200
        )
        self.duration_slider.set(0.1)
        
        self.duration_label = ctk.CTkLabel(
            self.duration_frame, 
            text=f"{LM.get_translation('duration')} {self.player.press_duration} s",
            font=("Arial", 12)
        )
        self.preset_frame = ctk.CTkFrame(self.duration_frame)

        self.preset_buttons = [
            ctk.CTkButton(
                self.preset_frame, 
                text=f"{preset} s", 
                command=lambda p=preset: [self.apply_preset(p), self.root.focus()],
                width=50,
                font=("Arial", 12)
            ) for preset in self.duration_presets
        ]
        for btn in self.preset_buttons:
            btn.pack(side="left", padx=2)
        
        speed_text = f"{LM.get_translation('speed_control')}: " + \
                   (LM.get_translation("enabled") if self.player.speed_enabled else LM.get_translation("disabled"))
        self.speed_toggle = self._create_button(speed_text, self.toggle_speed)
        
        self.speed_frame = ctk.CTkFrame(self.root)
        self.speed_preset_frame = ctk.CTkFrame(self.speed_frame)
        
        self.speed_buttons = []
        for speed in self.speed_presets:
            btn = ctk.CTkButton(
                self.speed_preset_frame, 
                text=str(speed), 
                command=lambda s=speed: [self.set_speed(s), self.root.focus()],
                width=50,
                font=("Arial", 12)
            )
            btn.pack(side="left", padx=2)
            self.speed_buttons.append(btn)
        
        self.speed_label = ctk.CTkLabel(
            self.speed_frame,
            text=f"{LM.get_translation('current_speed')}: {self.player.current_speed}",
            font=("Arial", 12)
        )
        
        self.play_button = self._create_button(
            LM.get_translation("play_button_text"), 
            self.play_selected,
            width=200,
            is_main=True
        )

    def toggle_theme(self):
        current = ctk.get_appearance_mode().lower()
        new_theme = "dark" if current == "light" else "light"
        logger.info(f"Toggling theme to: {new_theme}")
        ctk.set_appearance_mode(new_theme)
        self.theme_btn.configure(text="🌞" if new_theme == "light" else "🌙")
        ConfigManager.save_config({"theme": new_theme})

    def open_github_releases(self, event):
        try:
            logger.info("Opening GitHub releases")
            if (self.update_status == "update" and 
                self.update_url and 
                self.update_url.startswith("https://github.com/") and 
                "VanilleIce/ProjectLyrica" in self.update_url):
                
                webbrowser.open(self.update_url)
            else:
                webbrowser.open("https://github.com/VanilleIce/ProjectLyrica")
        except Exception as e:
            logger.error(f"Browser open failed: {str(e)}")
            error_message = f"{LM.get_translation('browser_open_error')}: {str(e)}"
            messagebox.showerror(LM.get_translation('error_title'), error_message)

    def _setup_gui_layout(self):
        self.title_label.pack(pady=10)
        self.file_button.pack(pady=10)
        self.keypress_toggle.pack(pady=5)
        self.speed_toggle.pack(pady=5)
        self.play_button.pack(pady=10)
        
        if self.player.keypress_enabled:
            self._pack_duration_controls()
        if self.player.speed_enabled:
            self._pack_speed_controls()
        
        self.adjust_window_size()
        logger.info("GUI layout setup complete")

    def _pack_duration_controls(self):
        self.duration_frame.pack(pady=5, before=self.speed_toggle)
        self.duration_slider.pack(pady=5)
        self.duration_label.pack()
        self.preset_frame.pack(pady=5)

    def _pack_speed_controls(self):
        self.speed_frame.pack(pady=5, before=self.play_button)
        self.speed_preset_frame.pack(pady=5)
        self.speed_label.pack(pady=5)

    def adjust_window_size(self):
        if self.player.keypress_enabled and self.player.speed_enabled:
            self.root.geometry(f"{FULL_SIZE[0]}x{FULL_SIZE[1]}")
        elif self.player.keypress_enabled or self.player.speed_enabled:
            self.root.geometry(f"{EXPANDED_SIZE[0]}x{EXPANDED_SIZE[1]}")
        else:
            self.root.geometry(f"{DEFAULT_WINDOW_SIZE[0]}x{DEFAULT_WINDOW_SIZE[1]}")
        logger.debug(f"Window size adjusted: {self.root.geometry()}")

    def select_file(self):
        logger.info("Opening file selection dialog")
        songs_dir = Path.cwd() / "resources/Songs"
        file_path = filedialog.askopenfilename(
            initialdir=songs_dir if songs_dir.exists() else Path.cwd(),
            filetypes=[(LM.get_translation("supported_formats"), "*.json *.txt *.skysheet")]
        )
        if file_path:
            self.selected_file = file_path
            filename = Path(file_path).name
            logger.info(f"Selected file: {filename}")

            if len(filename) > 30:
                shortened = filename[:25]
                if len(filename) > 25:
                    shortened += "..." 
                if " - " in shortened:
                    shortened = shortened.split(" - ")[0] + "..."
                elif "(" in shortened and ")" in shortened:
                    shortened = shortened.split("(")[0] + "..." 
                display_name = shortened
            else:
                display_name = filename
                
            self.file_button.configure(text=display_name)
            self.root.focus()

    def _play_song_thread(self, song_data):
        try:
            logger.info("Playback thread started")
            sky_window = self.player.window_cache
            if sky_window:
                logger.debug("Focusing Sky window")
                self.player.focus_window(sky_window)
            
            logger.debug(f"Waiting initial delay: {self.player.initial_delay}s")
            time.sleep(self.player.initial_delay)
            
            self.player.play_song(song_data)
            
            winsound.Beep(1000, 500)
            logger.info("Playback thread completed")
                
        except Exception as e:
            logger.error(f"Playback thread error: {e}", exc_info=True)
        finally:
            self.is_playing = False
            self.player.playback_active = False

    def play_selected(self):
        logger.info("Playback requested")
        
        if not self.selected_file:
            logger.warning("No song file selected - aborting playback")
            messagebox.showwarning(LM.get_translation("warning_title"), LM.get_translation("choose_song_warning"))
            return
            
        if self.player.playback_active:
            logger.info("Stopping existing playback")
            self.player.stop_playback()
        
        self.is_playing = True
        filename = Path(self.selected_file).name
        
        try:
            logger.info(f"Loading song: {filename}")
            song_data = self.player.parse_song(self.selected_file)
            
            logger.info(f"Starting playback thread for: {filename}")
            self.player.play_thread = Thread(
                target=self._play_song_thread, 
                args=(song_data,), 
                daemon=True
            )
            self.player.play_thread.start()
            logger.info(f"Playback started successfully for: {filename}")
            
        except Exception as e:
            self.player.playback_active = False
            self.is_playing = False
            logger.error(f"Playback failed: {e}", exc_info=True)
            messagebox.showerror(LM.get_translation("error_title"), f"{LM.get_translation('play_error_message')}: {e}")

    def set_press_duration(self, value):
        self.player.press_duration = round(float(value), 3)
        logger.info(f"Set press duration: {self.player.press_duration}s")
        self.duration_label.configure(text=f"{LM.get_translation('duration')} {self.player.press_duration} s")

    def handle_keypress(self, key):
        if hasattr(key, 'char') and key.char == self.pause_key:
            if self.player.pause_flag.is_set():
                logger.info("Resume triggered by pause key")
                self.player.pause_flag.clear()
                if sky_window := self.player.find_sky_window():
                    try:
                        self.player.focus_window(sky_window)
                    except Exception as e:
                        logger.error(f"Window focus failed: {e}")
            else:
                logger.info("Pause triggered by pause key")
                self.player.pause_flag.set()

    def set_speed(self, speed):
        self.player.set_speed(speed)
        logger.info(f"Set playback speed: {speed}")
        self.speed_label.configure(text=f"{LM.get_translation('current_speed')}: {speed}")

    def apply_preset(self, duration):
        self.player.press_duration = duration
        logger.info(f"Applied duration preset: {duration}s")
        self.duration_slider.set(duration)
        self.duration_label.configure(text=f"{LM.get_translation('duration')}: {duration}s")

    def toggle_keypress(self):
        new_state = not self.player.keypress_enabled
        status = "enabled" if new_state else "disabled"
        logger.info(f"Toggling keypress adjustment: {status}")
        self.player.keypress_enabled = new_state
        status_text = LM.get_translation(status)
        self.keypress_toggle.configure(text=f"{LM.get_translation('key_press')}: {status_text}")
        
        if new_state:
            self._pack_duration_controls()
        else:
            self.duration_frame.pack_forget()
            self.player.press_duration = 0.1
            
        self.adjust_window_size()

    def toggle_speed(self):
        new_state = not self.player.speed_enabled
        status = "enabled" if new_state else "disabled"
        logger.info(f"Toggling speed control: {status}")
        self.player.speed_enabled = new_state
        status_text = LM.get_translation(status)
        self.speed_toggle.configure(text=f"{LM.get_translation('speed_control')}: {status_text}")
        
        if new_state:
            self._pack_speed_controls()
        else:
            self.speed_frame.pack_forget()
            self.player.current_speed = 1000
            self.speed_label.configure(text=f"{LM.get_translation('current_speed')}: {self.player.current_speed}")
            
        self.adjust_window_size()

    def shutdown(self):
        logger.info("=" * 70)
        logger.info("Shutdown sequence initiated")
        logger.info("=" * 70)
        try:
            if hasattr(self, 'player') and self.player:
                if self.player.playback_active:
                    logger.info("Stopping active playback")
                    self.player.stop_playback()

                if hasattr(self.player, 'play_thread') and self.player.play_thread:
                    logger.debug("Waiting for play thread to finish")
                    self.player.play_thread.join(timeout=0.5)
        except Exception as e:
            logger.error(f"Shutdown error: {e}")
        
        if hasattr(self, 'key_listener') and self.key_listener.is_alive():
            logger.info("Stopping key listener")
            self.key_listener.stop()
        
        if hasattr(self, '_mutex_handle'):
            logger.debug("Releasing mutex handle")
            ctypes.windll.kernel32.CloseHandle(self._mutex_handle)
        
        if hasattr(self, 'root'):
            logger.info("Closing application window")
            self.root.quit()
            self.root.destroy()
        
        logger.info("Application fully terminated")

    def run(self):
        logger.info("Starting main application loop")
        self.root.mainloop()
        logger.info("Main application loop ended")

# -------------------------------
# Application Start
# -------------------------------

if __name__ == "__main__":
    app = MusicApp()
    app.run()