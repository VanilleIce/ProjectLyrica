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
from threading import Event, Thread, Timer
from pynput.keyboard import Controller, Listener
from tkinter import filedialog, messagebox
import xml.etree.ElementTree as ET

SETTINGS_FILE = 'settings.json'

# -------------------------------
# Language Manager Class
# -------------------------------

class LM:
    _translations_cache = {}

    @staticmethod
    def load_selected_language():
        config = ConfigManager.load_config()
        return config.get("selected_language")

    @staticmethod
    def save_selected_language(language_code):
        ConfigManager.save_config({"selected_language": language_code})

    @staticmethod
    def load_available_languages():
        lang_file = os.path.join('resources', 'config', 'lang.xml')
        try:
            tree = ET.parse(lang_file)
            root = tree.getroot()

            languages = []
            for language in root.findall('language'):
                code = language.get('code')
                name = language.text
                if code and name:
                    languages.append((code, name))
            return languages
        except FileNotFoundError:
            messagebox.showerror(LM.get_translation('error_title'), LM.get_translation('lang_config_not_found'))
            return []
        except Exception as e:
            messagebox.showerror(LM.get_translation('error_title'), LM.get_translation('error_loading_languages').format(e))
            return []

    @staticmethod
    def load_translations(language_code):
        if language_code in LM._translations_cache:
            return LM._translations_cache[language_code]

        lang_file = os.path.join('resources', 'lang', f"{language_code}.xml")
        try:
            tree = ET.parse(lang_file)
            root = tree.getroot()

            translations = {}
            for translation in root.findall('translation'):
                key = translation.get('key')
                value = translation.text
                if key and value:
                    translations[key] = value

        except FileNotFoundError:
            if language_code != 'en_US':

                return LM.load_translations('en_US')
            else:
                messagebox.showerror(
                    LM.get_translation('error_title'), 
                    LM.get_translation('missing_translations_file').format(language_code)
                )
                return {}
        except Exception as e:
            messagebox.showerror(
                LM.get_translation('error_title'), 
                LM.get_translation('error_loading_translations').format(e)
            )
            return {}

        LM._translations_cache[language_code] = translations
        return translations

    @staticmethod
    def get_translation(key):
        selected_language = LM.load_selected_language()
        translations = LM.load_translations(selected_language)
        return translations.get(key, f"[{key}]")

class ConfigManager:
    DEFAULT_CONFIG = {
        "key_press_durations": [0.2, 0.248, 0.3, 0.5, 1.0],
        "speed_presets": [600, 800, 1000, 1200],
        "selected_language": None
    }

    @staticmethod
    def load_config():
        try:
            with open(SETTINGS_FILE, 'r', encoding="utf-8") as file:
                config = json.load(file)
                return {**ConfigManager.DEFAULT_CONFIG, **config}
        except (FileNotFoundError, json.JSONDecodeError):
            return ConfigManager.DEFAULT_CONFIG

    @staticmethod
    def save_config(config_data):
        current_config = ConfigManager.load_config()
        updated_config = {**current_config, **config_data}
        with open(SETTINGS_FILE, 'w', encoding="utf-8") as file:
            json.dump(updated_config, file, indent=3, separators=(', ', ': '), ensure_ascii=False)

# -------------------------------
# GUI: Language Selection Window
# -------------------------------

language_window_open = False


def language_selection_window():
    global language_window_open
    if language_window_open:
        return

    language_window_open = True

    selected_language = LM.load_selected_language()
    translations = LM.load_translations(selected_language)

    root = ctk.CTk()
    root.title(translations.get('language_window_title'))
    root.geometry("400x200")
    root.iconbitmap("resources/icons/icon.ico")

    languages = LM.load_available_languages()
    language_dict = {name: code for code, name in languages}
    language_names = list(language_dict.keys())

    default_language_name = next((name for name, code in language_dict.items() if code == selected_language), next(iter(language_dict.keys()), "English"))

    ctk.CTkLabel(root, text=translations.get('select_language'), font=("Arial", 14)).pack(pady=10)
    
    language_combobox = ctk.CTkComboBox(root, values=language_names, state="readonly", font=("Arial", 12))
    language_combobox.set(default_language_name)
    language_combobox.pack(pady=10)

    def on_save():
        global language_window_open

        selected_name = language_combobox.get()
        selected_code = language_dict.get(selected_name)

        if not selected_code:
            messagebox.showerror(
                translations.get('error_title'), 
                LM.get_translation('language_not_found')
            )
            return

        LM.save_selected_language(selected_code)
        messagebox.showinfo(
            translations.get('info_title'), 
            LM.get_translation('language_saved')
        )
        root.quit()
        root.destroy()
        language_window_open = False

    ctk.CTkButton(root, text=translations.get('save_button_text'), command=on_save).pack(pady=20)

    def close_language_window():
        global language_window_open
        
        language_window_open = False
        root.quit()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close_language_window)

    root.mainloop()

# -------------------------------
# Music Player Functions
# -------------------------------

class MusikPlayer:
    def __init__(self):
        self.pause_flag = Event()
        self.stop_event = Event()
        self.abspiel_thread = None
        self.tastatur_steuerung = Controller()
        self.tastenkarten = {f'{prefix}{key}'.lower(): value for prefix in ['Key', '1Key', '2Key', '3Key']
                   for key, value in enumerate('zuiophjklönm,.-')}

        self.tastendruck_aktiviert = False
        self.tastendruck_dauer = 0.1

        self.geschwindigkeit_aktiviert = False
        self.aktuelle_geschwindigkeit = 1000

    def finde_sky_fenster(self):
        fenster_liste = gw.getWindowsWithTitle("Sky")
        return fenster_liste[0] if fenster_liste else None

    def fenster_fokus(self, sky_fenster):
        if not sky_fenster:
            messagebox.showwarning(LM.get_translation("warning_title"), LM.get_translation("sky_window_not_found"))
            return
        if not self.player.fenster_fokus(sky_fenster):
            return
        try:    
            if sky_fenster.isMinimized:
                sky_fenster.restore()
            sky_fenster.activate()
            return True
        except Exception as e:
            messagebox.showerror(LM.get_translation("error_title"), f"{LM.get_translation('window_focus_error')}: {e}")
            return False

    def musikdatei_parsen(self, dateipfad):
        dateipfad = Path(dateipfad)
        if not dateipfad.exists():
            raise FileNotFoundError(f"{LM.get_translation('file_not_found')}: {dateipfad}")

        try:
            with dateipfad.open('r') as datei:
                inhalt = datei.read()
                if not inhalt.strip():
                    raise ValueError(f"{LM.get_translation('file_empty_error')}: {dateipfad}")

                daten = json.loads(inhalt)

                if isinstance(daten, list) and daten:
                    daten = daten[0]

                if "songNotes" in daten:
                    return {"songNotes": daten["songNotes"]}
                else:
                    raise ValueError(f"{LM.get_translation('missing_key_songNotes')}: {dateipfad}")

        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"{LM.get_translation('file_encoding_error')}: {dateipfad}, {e}")

    def note_abspielen(self, note, i, song_notes, tastendruck_dauer):
        note_taste = note['key'].lower()
        note_zeit = note['time']

        if note_taste in self.tastenkarten:
            self.tastatur_steuerung.press(self.tastenkarten[note_taste])
            Timer(self.tastendruck_dauer, self.tastatur_steuerung.release, [self.tastenkarten[note_taste]]).start()

        if i < len(song_notes) - 1:
            nächste_note_zeit = song_notes[i + 1]['time']
            geschwindigkeits_faktor = 1000 / self.aktuelle_geschwindigkeit
            warte_zeit = (nächste_note_zeit - note_zeit) / 1000 * geschwindigkeits_faktor
            time.sleep(warte_zeit)

    def musik_abspielen(self, song_daten, stop_event, tastendruck_dauer):
        if isinstance(song_daten, list) and song_daten:
            song_daten = song_daten[0]

        if "songNotes" not in song_daten:
            raise ValueError(LM.get_translation("missing_key_songNotes"))

        for i, note in enumerate(song_daten["songNotes"]):
            self.warten_pause()
            if stop_event.is_set():
                break

            self.note_abspielen(note, i, song_daten["songNotes"], tastendruck_dauer)

        winsound.Beep(1000, 500)

    def warten_pause(self):
        while self.pause_flag.is_set():
            time.sleep(0.1)

    def stoppe_abspiel_thread(self):
        self.stop_event.set()
        self.pause_flag.clear()
        if self.abspiel_thread and self.abspiel_thread.is_alive():
            self.abspiel_thread.join(timeout=1.0)
        self.stop_event.clear()

# -------------------------------
# Main Application (GUI)
# -------------------------------

class MusikApp:
    def __init__(self):
        self.player = MusikPlayer()
        self.dateipfad_ausgewählt = None
        self.root = None
        self.listener = Listener(on_press=self.tastendruck_erkannt)
        self.listener.start()

        if LM.load_selected_language() is None:
            language_selection_window()

        config = ConfigManager.load_config()
        self.presets = config["key_press_durations"]
        self.geschwindigkeits_presets = config["speed_presets"]

    def beenden(self):
        self.player.stoppe_abspiel_thread()
        if self.listener.is_alive():
            self.listener.stop()
        if hasattr(self, 'player'):
            del self.player
        if hasattr(self, 'listener'):
            del self.listener
        self.root.quit()
        self.root.destroy()

    def datei_dialog_öffnen(self):
        songs_ordner = Path.cwd() / "resources/Songs"
        dateipfad = filedialog.askopenfilename(
            initialdir=songs_ordner if songs_ordner.exists() else Path.cwd(),
            title=LM.get_translation("file_select_title"),
            filetypes=[(LM.get_translation("supported_formats"), "*.json *.txt *.skysheet")]
        )
        if dateipfad:
            self.dateipfad_ausgewählt = dateipfad
            self.datei_label.configure(text=Path(dateipfad).name)

    def ausgewähltes_lied_abspielen(self):
        if not self.dateipfad_ausgewählt:
            messagebox.showwarning(LM.get_translation("warning_title"), LM.get_translation("choose_song_warning"))
            return

        self.player.stoppe_abspiel_thread()

        if not self.player.tastendruck_aktiviert:
            self.dauer_slider.set(0.1)

        try:
            if not Path(self.dateipfad_ausgewählt).exists():
                raise FileNotFoundError(LM.get_translation("file_not_found"))
                
            song_daten = self.player.musikdatei_parsen(self.dateipfad_ausgewählt)

            sky_fenster = self.player.finde_sky_fenster()
            if not sky_fenster or not self.player.fenster_fokus(sky_fenster):
                return
            
            time.sleep(2) # Wartezeit vor dem Abspielen

            if not self.player.abspiel_thread or not self.player.abspiel_thread.is_alive():
                self.player.abspiel_thread = Thread(target=self.player.musik_abspielen, 
                                                args=(song_daten, self.player.stop_event, self.player.tastendruck_dauer), 
                                                daemon=True)
                self.player.abspiel_thread.start()
        except Exception as e:
            messagebox.showerror(LM.get_translation("error_title"), f"{LM.get_translation('play_error_message')}: {e}")

    def tastendruck_dauer_setzen(self, wert):
        self.player.tastendruck_dauer = round(float(wert), 3)
        self.dauer_anzeige.configure(text=f"{LM.get_translation('duration')} {self.player.tastendruck_dauer} s")
        
    def tastendruck_erkannt(self, key):
        if getattr(key, 'char', None) == '#':
            if self.player.pause_flag.is_set():
                self.player.pause_flag.clear()
                sky_fenster = self.player.finde_sky_fenster()
                if not sky_fenster:
                    messagebox.showwarning(LM.get_translation("warning_title"),
                                        LM.get_translation("sky_window_not_found"))
                    return
                if sky_fenster and self.player.fenster_fokus(sky_fenster):
                    time.sleep(2)

    def setze_geschwindigkeit(self, geschwindigkeit):
        self.player.aktuelle_geschwindigkeit = geschwindigkeit
        self.geschwindigkeit_label.configure(text=f"{LM.get_translation('current_speed')}: {geschwindigkeit}")
        
        if self.player.abspiel_thread and self.player.abspiel_thread.is_alive() and not self.player.pause_flag.is_set():
            self.player.stoppe_abspiel_thread()
            self.ausgewähltes_lied_abspielen()

    def toggle_tastendruck(self):
        self.player.tastendruck_aktiviert = not self.player.tastendruck_aktiviert
        status = LM.get_translation("enabled" if self.player.tastendruck_aktiviert else "disabled")
        self.tastendruck_button.configure(text=f"{LM.get_translation('key_press')}: {status}")
        
        if not self.player.tastendruck_aktiviert:
            self.player.tastendruck_dauer = 0.1
            self.dauer_slider.set(0.1)
            self.dauer_anzeige.configure(text=f"{LM.get_translation('duration')} 0.1 s")
        
        self.tastendruck_controls_frame.pack(pady=5, before=self.geschwindigkeit_button) \
            if self.player.tastendruck_aktiviert else self.tastendruck_controls_frame.pack_forget()
        
        self.anpassen_fenstergroesse()

    def preset_button_click(self, dauer):
        self.player.tastendruck_dauer = dauer
        self.dauer_slider.set(dauer)
        self.dauer_anzeige.configure(text=f"{LM.get_translation('duration')} {dauer} s")

    def toggle_geschwindigkeit(self):
        self.player.geschwindigkeit_aktiviert = not self.player.geschwindigkeit_aktiviert
        
        if not self.player.geschwindigkeit_aktiviert:
            self.player.aktuelle_geschwindigkeit = 1000
            self.geschwindigkeit_label.configure(text=f"{LM.get_translation('current_speed')}: 1000")
        
        status = LM.get_translation("enabled" if self.player.geschwindigkeit_aktiviert else "disabled")
        self.geschwindigkeit_button.configure(text=f"{LM.get_translation('speed_control')}: {status}")
        
        if self.player.geschwindigkeit_aktiviert:
            self.geschwindigkeit_controls_frame.pack(pady=5, before=self.play_button)
        else:
            self.geschwindigkeit_controls_frame.pack_forget()
        
        self.anpassen_fenstergroesse()

    def anpassen_fenstergroesse(self):
        if self.player.tastendruck_aktiviert and self.player.geschwindigkeit_aktiviert:
            self.root.geometry("500x450")
        elif self.player.tastendruck_aktiviert:
            self.root.geometry("500x350")
        elif self.player.geschwindigkeit_aktiviert:
            self.root.geometry("500x350")
        else:
            self.root.geometry("500x250")

# -------------------------------
# Frontend GUI
# -------------------------------

    def gui_starten(self):
        ctk.set_appearance_mode("dark")
        self.root = ctk.CTk()
        self.root.title(LM.get_translation("project_title"))
        self.root.geometry("500x250")
        self.root.iconbitmap("resources/icons/icon.ico")

        titel_label = ctk.CTkLabel(self.root, text=LM.get_translation("project_title"), 
                                font=("Arial", 18, "bold"))
        titel_label.pack(pady=10)

        self.datei_label = ctk.CTkButton(
            self.root, 
            text=LM.get_translation("file_select_title"),
            command=self.datei_dialog_öffnen,
            font=("Arial", 14),
            fg_color="grey",
            width=300,
            height=40
        )
        self.datei_label.pack(pady=10)

        tastendruck_status = LM.get_translation("enabled" if self.player.tastendruck_aktiviert else "disabled")
        self.tastendruck_button = ctk.CTkButton(
            self.root,
            text=f"{LM.get_translation('key_press')}: {tastendruck_status}",
            command=self.toggle_tastendruck,
            width=200,
            height=30
        )
        self.tastendruck_button.pack(pady=5)

        self.tastendruck_controls_frame = ctk.CTkFrame(self.root)
        
        self.dauer_slider = ctk.CTkSlider(
            self.tastendruck_controls_frame,
            from_=0.1,
            to=1.0,
            number_of_steps=100,
            command=self.tastendruck_dauer_setzen,
            width=200
        )
        self.dauer_slider.pack(pady=5)
        
        self.dauer_anzeige = ctk.CTkLabel(
            self.tastendruck_controls_frame,
            text=LM.get_translation("duration") + f" {self.player.tastendruck_dauer} s"
        )
        self.dauer_anzeige.pack()
        
        self.presets_button_frame = ctk.CTkFrame(self.tastendruck_controls_frame)
        for wert in self.presets:
            ctk.CTkButton(
                self.presets_button_frame,
                text=f"{wert} s",
                command=lambda v=wert: self.preset_button_click(v),
                width=50
            ).pack(side="left", padx=2)
        self.presets_button_frame.pack(pady=5)

        geschwindigkeit_status = LM.get_translation("enabled" if self.player.geschwindigkeit_aktiviert else "disabled")
        self.geschwindigkeit_button = ctk.CTkButton(
            self.root,
            text=f"{LM.get_translation('speed_control')}: {geschwindigkeit_status}",
            command=self.toggle_geschwindigkeit,
            width=200,
            height=30
        )
        self.geschwindigkeit_button.pack(pady=5)

        self.geschwindigkeit_controls_frame = ctk.CTkFrame(self.root)
        
        self.geschwindigkeit_presets_frame = ctk.CTkFrame(self.geschwindigkeit_controls_frame)
        for geschwindigkeit in self.geschwindigkeits_presets:
            ctk.CTkButton(
                self.geschwindigkeit_presets_frame,
                text=str(geschwindigkeit),
                command=lambda g=geschwindigkeit: self.setze_geschwindigkeit(g),
                fg_color="green" if geschwindigkeit == 1000 else None,
                width=50
            ).pack(side="left", padx=2)
        self.geschwindigkeit_presets_frame.pack(pady=5)
        
        self.geschwindigkeit_label = ctk.CTkLabel(
            self.geschwindigkeit_controls_frame,
            text=f"{LM.get_translation('current_speed')}: {self.player.aktuelle_geschwindigkeit}"
        )
        self.geschwindigkeit_label.pack(pady=5)

        self.play_button = ctk.CTkButton(
            self.root,
            text=LM.get_translation("play_button_text"),
            command=self.ausgewähltes_lied_abspielen,
            font=("Arial", 14),
            width=200,
            height=40
        )
        self.play_button.pack(pady=10)

        if self.player.tastendruck_aktiviert:
            self.tastendruck_controls_frame.pack(pady=5, before=self.geschwindigkeit_button)
        else:
            self.tastendruck_controls_frame.pack_forget()
        
        if self.player.geschwindigkeit_aktiviert:
            self.geschwindigkeit_controls_frame.pack(pady=5, before=self.play_button)
        else:
            self.geschwindigkeit_controls_frame.pack_forget()

        self.root.protocol('WM_DELETE_WINDOW', self.beenden)
        self.root.mainloop()

# -------------------------------
# Start Application
# -------------------------------

if __name__ == "__main__":
    ConfigManager.load_config()
    app = MusikApp()
    app.gui_starten()