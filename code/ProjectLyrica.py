# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.
# Source code: https://github.com/VanilleIce/ProjectLyrica

import json
import time
import os
import sys
import winsound
import psutil
import ctypes
import pygetwindow as gw
import customtkinter as ctk
from pathlib import Path
from threading import Event, Thread, Timer, Lock
from pynput.keyboard import Controller, Listener
from tkinter import filedialog, messagebox
import xml.etree.ElementTree as ET
import webbrowser
from update_checker import check_update

SETTINGS_FILE = 'settings.json'
DEFAULT_WINDOW_SIZE = (400, 280)
EXPANDED_SIZE = (400, 380)
FULL_SIZE = (400, 480)
version = "2.1.0"

# -------------------------------
# Language Manager Class
# -------------------------------

class LM:
    _translations_cache = {}
    _selected_language = None
    _available_languages = []

    @classmethod
    def initialize(cls):
        cls._selected_language = ConfigManager.load_config().get("selected_language")
        cls._available_languages = cls.load_available_languages()

    @staticmethod
    def load_available_languages():
        lang_file = os.path.join('resources', 'config', 'lang.xml')
        try:
            tree = ET.parse(lang_file)
            languages = []
            for lang in tree.findall('language'):
                code = lang.get('code')
                text = lang.text
                key_layout = lang.get('key_layout', 'QWERTY')
                if code and text:
                    languages.append((code, text, key_layout))
            return languages
        except Exception as e:
            messagebox.showerror("Error", f"Error loading languages: {e}")
            return []

    @classmethod
    def load_translations(cls, language_code):
        if language_code in cls._translations_cache:
            return cls._translations_cache[language_code]

        lang_file = os.path.join('resources', 'lang', f"{language_code}.xml")
        try:
            tree = ET.parse(lang_file)
            translations = {t.get('key'): t.text for t in tree.findall('translation') 
                          if t.get('key') and t.text}
            cls._translations_cache[language_code] = translations
            return translations
        except FileNotFoundError:
            if language_code != 'en_US':
                return cls.load_translations('en_US')
            return {}
        except Exception as e:
            messagebox.showerror("Error", f"Error loading translations: {e}")
            return {}

    @classmethod
    def get_translation(cls, key):
        translations = cls.load_translations(cls._selected_language or 'en_US')
        return translations.get(key, f"[{key}]")

    @classmethod
    def save_language(cls, language_code):
        cls._selected_language = language_code
        config = ConfigManager.load_config()
        
        layout_name = "QWERTY"
        for code, name, key_layout in cls._available_languages:
            if code == language_code:
                layout_name = key_layout
                break
        
        try:
            layout_mapping = KeyboardLayoutManager.load_layout(layout_name)
        except Exception as e:
            messagebox.showerror("Error", f"Error loading layout: {e}")
            layout_mapping = config.get("key_mapping", {})

        ConfigManager.save_config({
            "selected_language": language_code,
            "keyboard_layout": layout_name,
            "key_mapping": layout_mapping
        })

# -------------------------------
# Config Manager
# -------------------------------

class ConfigManager:
    DEFAULT_CONFIG = {
        "key_press_durations": [0.2, 0.248, 0.3, 0.5, 1.0],
        "speed_presets": [600, 800, 1000, 1200],
        "selected_language": None,
        "keyboard_layout": "QWERTZ",
        "key_mapping": {
            "Key0": "z", "Key1": "u", "Key2": "i", "Key3": "o",
            "Key4": "p", "Key5": "h", "Key6": "j", "Key7": "k",
            "Key8": "l", "Key9": "ö", "Key10": "n", "Key11": "m",
            "Key12": ",", "Key13": ".", "Key14": "-"
        },
        "timing_config": {
            "initial_delay": 1.2,
            "pause_resume_delay": 0.6,
            "ramp_steps": 20
        },
        "pause_key": "#"
    }

    @classmethod
    def load_config(cls):
        try:
            with open(SETTINGS_FILE, 'r', encoding="utf-8") as file:
                user_config = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            user_config = {}
        
        config = cls.DEFAULT_CONFIG.copy()
        
        for key, value in user_config.items():
            if key == "timing_config" and isinstance(value, dict):
                config[key] = {**config[key], **value}
            elif key == "key_mapping" and isinstance(value, dict):
                config[key] = {**config[key], **value}
            else:
                config[key] = value
        
        return config

    @classmethod
    def save_config(cls, config_data):
        current_config = cls.load_config()
        
        for key, value in config_data.items():
            if key in ["timing_config", "key_mapping"] and isinstance(value, dict):
                current_config[key] = {**current_config.get(key, {}), **value}
            else:
                current_config[key] = value
                
        with open(SETTINGS_FILE, 'w', encoding="utf-8") as file:
            json.dump(current_config, file, indent=3, ensure_ascii=False)

# -------------------------------
# GUI: Language Selection
# -------------------------------

class LanguageWindow:
    _open = False

    @classmethod
    def show(cls):
        if cls._open:
            return
            
        cls._open = True
        root = ctk.CTk()
        root.title(LM.get_translation('language_window_title'))
        root.geometry("400x200")
        root.iconbitmap("resources/icons/icon.ico")
        
        languages = LM._available_languages
        language_dict = {name: code for code, name, _ in languages}
        default_name = next((name for code, name, _ in languages if code == LM._selected_language), 
                            languages[0][1] if languages else "English (Amerika)")
        
        label = ctk.CTkLabel(root, text=LM.get_translation('select_language'), font=("Arial", 14))
        label.pack(pady=10)
        
        combo = ctk.CTkComboBox(root, values=list(language_dict.keys()), state="readonly")
        combo.set(default_name)
        combo.pack(pady=10)
        
        def save():
            selected_code = language_dict.get(combo.get())
            if selected_code:
                LM.save_language(selected_code)
                messagebox.showinfo("Info", LM.get_translation('language_saved'))
            root.destroy()
            
        button = ctk.CTkButton(root, text=LM.get_translation('save_button_text'), command=save)
        button.pack(pady=20)
        
        root.protocol("WM_DELETE_WINDOW", lambda: [root.destroy(), setattr(cls, '_open', False)])
        root.mainloop()
        cls._open = False

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
            mapping = {}
            
            for key in tree.getroot().findall('key'):
                key_id = key.get('id')
                key_value = key.text.strip() if key.text else ""
                if key_id and key_value:
                    mapping[key_id] = key_value
                
            return mapping
        except Exception as e:
            raise Exception(f"Error loading layout '{layout_name}': {str(e)}")

# -------------------------------
# Music Player
# -------------------------------

class MusicPlayer:
    def __init__(self):
        self.pause_flag = Event()
        self.stop_event = Event()
        self.play_thread = None
        self.keyboard = Controller()
        
        config = ConfigManager.load_config()
        self.key_map = self._create_key_map(config["key_mapping"])
        self.press_duration = 0.1
        self.speed = 1000
        self.keypress_enabled = False
        self.speed_enabled = False
        
        timing_config = config.get("timing_config", {})
        self.initial_delay = timing_config.get("initial_delay", 1.2)
        self.pause_resume_delay = timing_config.get("pause_resume_delay", 0.6)
        self.ramp_steps = timing_config.get("ramp_steps", 20)
        
        self.speed_lock = Lock()
        self.current_speed = 1000
        self.ramp_counter = 0
        self.is_ramping = False

    def _create_key_map(self, mapping):
        key_map = {}
        for prefix in ['', '1', '2', '3']:
            for key, value in mapping.items():
                key_map[f"{prefix}{key}".lower()] = value
        return key_map

    def find_sky_window(self):
        return next((w for w in gw.getWindowsWithTitle("Sky") if "Sky" in w.title), None)

    def focus_window(self, window):
        if window is None:
            return False
            
        try:
            if window.isMinimized:
                window.restore()
                
            window.activate()
            return True
        except Exception:
            try:
                user32 = ctypes.windll.user32
                hwnd = window._hWnd
                user32.ShowWindow(hwnd, 9)
                user32.SetForegroundWindow(hwnd)
                return True
            except Exception:
                return False

    def parse_song(self, path):
        path = Path(path)
        if not path.resolve().as_posix().startswith(Path.cwd().as_posix()):
            raise ValueError(LM.get_translation('security_error_path'))

        if path.suffix.lower() not in ['.json', '.txt', '.skysheet']:
            raise ValueError(LM.get_translation('invalid_file_format'))
        
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
            return data[0] if isinstance(data, list) else data

    def play_note(self, note, index, notes, current_speed):
        key = self.key_map.get(note['key'].lower())
        if key:
            self.keyboard.press(key)
            Timer(self.press_duration, self.keyboard.release, [key]).start()
        
        if index < len(notes) - 1:
            next_time = notes[index + 1]['time']
            wait_time = (next_time - note['time']) / 1000 * (1000 / current_speed)
            time.sleep(wait_time)

    def play_song(self, song_data):
        notes = song_data.get("songNotes", [])

        if not notes:
            messagebox.showerror(LM.get_translation("error_title"), LM.get_translation("missing_song_notes"))
            return

        def is_sky_running():
            return any(p.name() == "Sky.exe" for p in psutil.process_iter())

        if not is_sky_running():
            messagebox.showerror(LM.get_translation("error_title"), LM.get_translation("sky_not_running"))
            return
        
        self.is_ramping = True
        self.ramp_counter = 0
        
        for i, note in enumerate(notes):
            if self.stop_event.is_set():
                break
                
            if self.pause_flag.is_set():
                self.is_ramping = True
                self.ramp_counter = 0
                while self.pause_flag.is_set():
                    time.sleep(0.1)
                    if self.stop_event.is_set():
                        break
                
                if not self.stop_event.is_set():
                    time.sleep(self.pause_resume_delay)
            
            with self.speed_lock:
                target_speed = self.current_speed
                
            if self.is_ramping and self.ramp_counter < self.ramp_steps:
                speed_factor = 0.5 + 0.5 * (self.ramp_counter / self.ramp_steps)
                current_speed = max(500, target_speed * speed_factor)
                self.ramp_counter += 1
                if self.ramp_counter >= self.ramp_steps:
                    self.is_ramping = False
            else:
                current_speed = target_speed
                
            self.play_note(note, i, notes, current_speed)
            
        winsound.Beep(1000, 500)

    def stop_playback(self):
        self.stop_event.set()
        self.pause_flag.clear()
        if self.play_thread and self.play_thread.is_alive():
            self.play_thread.join(timeout=1.0)
        self.stop_event.clear()
        self.is_ramping = False

    def set_speed(self, speed):
        with self.speed_lock:
            self.current_speed = speed

# -------------------------------
# Main Application
# -------------------------------

class MusicApp:
    def __init__(self):
        LM.initialize()
        if not LM._selected_language:
            LanguageWindow.show()

        if self.is_already_running():
            messagebox.showerror("Error", "Application is already running!")
            sys.exit(1)
        
        self.key_listener = Listener(on_press=self.handle_keypress)
        self.key_listener.start()
        
        config = ConfigManager.load_config()
        self.duration_presets = config["key_press_durations"]
        self.speed_presets = config["speed_presets"]

        self.version = version
        self.update_status = "checking"
        self.latest_version = ""
        self.update_url = ""

        self.player = MusicPlayer()
        self.selected_file = None
        self.root = None

        try:
            result = check_update(self.version, "VanilleIce/ProjectLyrica")
            self.update_status = result[0]
            self.latest_version = result[1]
            self.update_url = result[2]
        except Exception:
            self.update_status = "error"
            self.latest_version = ""
            self.update_url = ""

        self._create_gui_components()
        self._setup_gui_layout()

    @staticmethod
    def is_already_running():
        current_pid = os.getpid()
        for proc in psutil.process_iter(['pid', 'name']):
            if "ProjectLyrica" in proc.info['name'] and proc.info['pid'] != current_pid:
                return True
        return False

    def _create_button(self, text, command, width=200, height=30, font=("Arial", 12), is_main=False, color=None):
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
        self.root.title(LM.get_translation("project_title"))
        self.root.iconbitmap("resources/icons/icon.ico")
        self.root.protocol('WM_DELETE_WINDOW', self.shutdown)

        self.status_frame = ctk.CTkFrame(self.root, fg_color="transparent", height=1)
        self.status_frame.pack(side="bottom", fill="x", padx=10, pady=3)
        
        self.title_label = ctk.CTkLabel(self.root, text=LM.get_translation("project_title"), font=("Arial", 18, "bold"))
        
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
            font=("Arial", 11)
        )
        
        self.preset_frame = ctk.CTkFrame(self.duration_frame)

        self.preset_buttons = []
        for preset in self.duration_presets:
            btn = ctk.CTkButton(
                self.preset_frame, 
                text=f"{preset} s", 
                command=lambda p=preset: [self.apply_preset(p), self.root.focus()],
                width=50,
                font=("Arial", 10)
            )
            btn.pack(side="left", padx=2)
            self.preset_buttons.append(btn)
        
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
                font=("Arial", 10)
            )
            btn.pack(side="left", padx=2)
            self.speed_buttons.append(btn)
        
        self.speed_label = ctk.CTkLabel(
            self.speed_frame, 
            text=f"{LM.get_translation('current_speed')}: {self.player.speed}",
            font=("Arial", 11)
        )
        
        self.play_button = self._create_button(
            LM.get_translation("play_button_text"), 
            self.play_selected,
            width=200,
            is_main=True
        )

        if self.update_status == "update":
            version_text = LM.get_translation('update_available_text').format(self.latest_version)
            text_color = "#FFA500"
        elif self.update_status == "no_connection":
            version_text = LM.get_translation('no_connection_text')
            text_color = "#FF0000"
        elif self.update_status == "error":
            version_text = LM.get_translation('update_error_text')
            text_color = "#FF0000"
        else:
            version_text = LM.get_translation('current_version_text').format(self.version)
            text_color = "#1E90FF"
        
        self.version_link = ctk.CTkLabel(
            self.status_frame,
            text=version_text,
            font=("Arial", 11),
            text_color=text_color,
            cursor="hand2"
        )
        
        self.version_link.pack(side="right")
        self.version_link.bind("<Button-1>", self.open_github_releases)

    def open_github_releases(self, event):
        try:
            if (self.update_status == "update" and 
                self.update_url and 
                self.update_url.startswith("https://github.com/") and 
                "VanilleIce/ProjectLyrica" in self.update_url):
                
                webbrowser.open(self.update_url)
            else:
                webbrowser.open("https://github.com/VanilleIce/ProjectLyrica")
        except Exception as e:
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

    def select_file(self):
        songs_dir = Path.cwd() / "resources/Songs"
        file_path = filedialog.askopenfilename(
            initialdir=songs_dir if songs_dir.exists() else Path.cwd(),
            filetypes=[(LM.get_translation("supported_formats"), "*.json *.txt *.skysheet")]
        )
        if file_path:
            self.selected_file = file_path
            self.file_button.configure(text=Path(file_path).name)
            self.root.focus()

    def play_selected(self):
        if not self.selected_file:
            messagebox.showwarning(LM.get_translation("warning_title"), LM.get_translation("choose_song_warning"))
            return
            
        self.player.stop_playback()
        try:
            song_data = self.player.parse_song(self.selected_file)
            sky_window = self.player.find_sky_window()
            
            self.player.focus_window(sky_window)
            
            time.sleep(self.player.initial_delay)
            
            self.player.play_thread = Thread(target=self.player.play_song, args=(song_data,), daemon=True)
            self.player.play_thread.start()
        except Exception as e:
            messagebox.showerror(LM.get_translation("error_title"), f"{LM.get_translation('play_error_message')}: {e}")

    def set_press_duration(self, value):
        self.player.press_duration = round(float(value), 3)
        self.duration_label.configure(text=f"{LM.get_translation('duration')} {self.player.press_duration} s")

    def handle_keypress(self, key):
        if getattr(key, 'char', None) == ConfigManager.load_config().get("pause_key", "#"):
            if self.player.pause_flag.is_set():
                self.player.pause_flag.clear()
                if sky_window := self.player.find_sky_window():
                    self.player.focus_window(sky_window)
            else:
                self.player.pause_flag.set()

    def set_speed(self, speed):
        self.player.set_speed(speed)
        self.speed_label.configure(text=f"{LM.get_translation('current_speed')}: {speed}")

    def apply_preset(self, duration):
        self.player.press_duration = duration
        self.duration_slider.set(duration)
        self.duration_label.configure(text=f"{LM.get_translation('duration')} {duration} s")

    def toggle_keypress(self):
        self.player.keypress_enabled = not self.player.keypress_enabled
        status = LM.get_translation("enabled" if self.player.keypress_enabled else "disabled")
        self.keypress_toggle.configure(text=f"{LM.get_translation('key_press')}: {status}")
        
        if self.player.keypress_enabled:
            self._pack_duration_controls()
        else:
            self.duration_frame.pack_forget()
            self.player.press_duration = 0.1
            
        self.adjust_window_size()

    def toggle_speed(self):
        self.player.speed_enabled = not self.player.speed_enabled
        status = LM.get_translation("enabled" if self.player.speed_enabled else "disabled")
        self.speed_toggle.configure(text=f"{LM.get_translation('speed_control')}: {status}")
        
        if self.player.speed_enabled:
            self._pack_speed_controls()
        else:
            self.speed_frame.pack_forget()
            self.player.speed = 1000
            
        self.adjust_window_size()

    def shutdown(self):
        self.player.stop_playback()
        if self.key_listener.is_alive():
            self.key_listener.stop()
        self.root.quit()
        self.root.destroy()

    def run(self):
        self.root.mainloop()

# -------------------------------
# Application Start
# -------------------------------

if __name__ == "__main__":
    app = MusicApp()
    app.run()