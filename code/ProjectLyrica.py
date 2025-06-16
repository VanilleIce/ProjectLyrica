# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.
# Source code: https://github.com/VanilleIce/ProjectLyrica

import json
import time
import os
import winsound
import pygetwindow as gw
import customtkinter as ctk
from pathlib import Path
from threading import Event, Thread, Timer, Lock
from pynput.keyboard import Controller, Listener
from tkinter import filedialog, messagebox
import xml.etree.ElementTree as ET

SETTINGS_FILE = 'settings.json'
DEFAULT_WINDOW_SIZE = (500, 250)
EXPANDED_SIZE = (500, 350)
FULL_SIZE = (500, 450)

# Centralized timing configuration
TIMING_CONFIG = {
    "initial_delay": 1.2,
    "pause_resume_delay": 0.6,
    "ramp_steps": 20
}

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
            return [(lang.get('code'), lang.text) for lang in tree.findall('language') 
                    if lang.get('code') and lang.text]
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
        ConfigManager.save_config({"selected_language": language_code})

# -------------------------------
# Config Manager
# -------------------------------

class ConfigManager:
    DEFAULT_CONFIG = {
        "key_press_durations": [0.2, 0.248, 0.3, 0.5, 1.0],
        "speed_presets": [600, 800, 1000, 1200],
        "selected_language": None,
        "key_mapping": {
            "Key0": "z", "Key1": "u", "Key2": "i", "Key3": "o",
            "Key4": "p", "Key5": "h", "Key6": "j", "Key7": "k",
            "Key8": "l", "Key9": "ö", "Key10": "n", "Key11": "m",
            "Key12": ",", "Key13": ".", "Key14": "-"
        },
        "pause_key": "#"
    }

    @classmethod
    def load_config(cls):
        try:
            with open(SETTINGS_FILE, 'r', encoding="utf-8") as file:
                return {**cls.DEFAULT_CONFIG, **json.load(file)}
        except (FileNotFoundError, json.JSONDecodeError):
            return cls.DEFAULT_CONFIG

    @classmethod
    def save_config(cls, config_data):
        with open(SETTINGS_FILE, 'w', encoding="utf-8") as file:
            json.dump({**cls.load_config(), **config_data}, 
                     file, indent=3, ensure_ascii=False)

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
        language_dict = {name: code for code, name in languages}
        default_name = next((name for code, name in languages if code == LM._selected_language), languages[0][1] if languages else "English")
        
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
        
        self.initial_delay = TIMING_CONFIG["initial_delay"]
        self.pause_resume_delay = TIMING_CONFIG["pause_resume_delay"]
        self.ramp_steps = TIMING_CONFIG["ramp_steps"]
        
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
        if window:
            try:
                if window.isMinimized:
                    window.restore()
                window.activate()
                return True
            except Exception:
                pass
        return False

    def parse_song(self, path):
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(LM.get_translation('file_not_found'))
        
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
                
            # Calculate current speed (ramp up at start and after pause)
            if self.is_ramping and self.ramp_counter < self.ramp_steps:
                # Smooth ramp: start at 50% and increase to 100%
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
        
        self.player = MusicPlayer()
        self.selected_file = None
        self.root = None
        self.key_listener = Listener(on_press=self.handle_keypress)
        self.key_listener.start()
        
        config = ConfigManager.load_config()
        self.duration_presets = config["key_press_durations"]
        self.speed_presets = config["speed_presets"]
        
        self._create_gui_components()
        self._setup_gui_layout()

    def _create_gui_components(self):
        self.root = ctk.CTk()
        self.root.title(LM.get_translation("project_title"))
        self.root.geometry(f"{DEFAULT_WINDOW_SIZE[0]}x{DEFAULT_WINDOW_SIZE[1]}")
        self.root.iconbitmap("resources/icons/icon.ico")
        self.root.protocol('WM_DELETE_WINDOW', self.shutdown)
        
        self.title_label = ctk.CTkLabel(self.root, text=LM.get_translation("project_title"), 
                                      font=("Arial", 18, "bold"))
        
        self.file_button = ctk.CTkButton( self.root, text=LM.get_translation("file_select_title"), command=self.select_file, font=("Arial", 14), fg_color="grey", width=300, height=40 )
        
        keypress_text = f"{LM.get_translation('key_press')}: " + \
                       (LM.get_translation("enabled") if self.player.keypress_enabled else LM.get_translation("disabled"))
        self.keypress_toggle = ctk.CTkButton(self.root, text=keypress_text, command=self.toggle_keypress, width=200, height=30)
        
        self.duration_frame = ctk.CTkFrame(self.root)
        
        self.duration_slider = ctk.CTkSlider( self.duration_frame, from_=0.1, to=1.0, number_of_steps=90, command=self.set_press_duration, width=100)
        self.duration_slider.set(0.1)
        
        self.duration_label = ctk.CTkLabel(self.duration_frame, text=f"{LM.get_translation('duration')} {self.player.press_duration} s")
        
        self.preset_frame = ctk.CTkFrame(self.duration_frame)

        self.preset_buttons = []
        for preset in self.duration_presets:
            btn = ctk.CTkButton(
                self.preset_frame, 
                text=f"{preset} s", 
                command=lambda p=preset: [self.apply_preset(p), self.root.focus()],
                width=50
            )
            btn.pack(side="left", padx=2)
            self.preset_buttons.append(btn)
        
        speed_text = f"{LM.get_translation('speed_control')}: " + \
                   (LM.get_translation("enabled") if self.player.speed_enabled else LM.get_translation("disabled"))
        self.speed_toggle = ctk.CTkButton(self.root, text=speed_text, command=self.toggle_speed, width=200, height=30)
        
        self.speed_frame = ctk.CTkFrame(self.root)
        self.speed_preset_frame = ctk.CTkFrame(self.speed_frame)
        
        self.speed_buttons = []
        for speed in self.speed_presets:
            btn = ctk.CTkButton(
                self.speed_preset_frame, 
                text=str(speed), 
                command=lambda s=speed: [self.set_speed(s), self.root.focus()],
                width=50
            )
            btn.pack(side="left", padx=2)
            self.speed_buttons.append(btn)
        
        self.speed_label = ctk.CTkLabel(self.speed_frame, text=f"{LM.get_translation('current_speed')}: {self.player.speed}")
        
        self.play_button = ctk.CTkButton(self.root, text=LM.get_translation("play_button_text"), command=self.play_selected, font=("Arial", 14), width=200, height=40)

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

    def play_selected(self):
        if not self.selected_file:
            messagebox.showwarning(LM.get_translation("warning_title"), 
                                LM.get_translation("choose_song_warning"))
            return
            
        self.player.stop_playback()
        try:
            song_data = self.player.parse_song(self.selected_file)
            sky_window = self.player.find_sky_window()
            self.player.focus_window(sky_window)
            time.sleep(self.player.initial_delay)
            
            self.player.play_thread = Thread(target=self.player.play_song, 
                                          args=(song_data,), daemon=True)
            self.player.play_thread.start()
        except Exception as e:
            messagebox.showerror(LM.get_translation("error_title"), 
                              f"{LM.get_translation('play_error_message')}: {e}")

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