import json
import time
import winsound
import pygetwindow as gw
import customtkinter as ctk
from pathlib import Path
from threading import Event, Thread, Timer
from pynput.keyboard import Controller, Listener
from tkinter import filedialog, messagebox
from translation_utils import load_selected_language, load_translations, start_language_selection

def get_translations(key, translations=None):
    if translations is None:
        selected_language = load_selected_language()
        if selected_language is None:
            start_language_selection()
            selected_language = load_selected_language()
        translations = load_translations(selected_language)
    return translations.get(key, key)

class MusikPlayer:
    def __init__(self):
        self.pause_flag = Event()
        self.stop_event = Event()
        self.abspiel_thread = None
        self.tastatur_steuerung = Controller()
        self.tastenkarten = self.tastenkarten_holen()
        self.tastendruck_aktiviert = False

    def tastenkarten_holen(self):
        basis_karten = {i: k for i, k in enumerate('zuiophjklönm,.-')}
        return {f'{prefix}{key}'.lower(): value for prefix in ['Key', '1Key', '2Key', '3Key'] for key, value in basis_karten.items()}

    def finde_sky_fenster(self):
        fenster_liste = gw.getWindowsWithTitle("Sky")
        return fenster_liste[0] if fenster_liste else None

    def fenster_fokus(self, sky_fenster):
        if not sky_fenster:
            messagebox.showwarning(get_translations("warning_title"), get_translations("sky_window_not_found"))
            return
        try:
            sky_fenster.activate()
        except Exception:
            try:
                sky_fenster.minimize()
                sky_fenster.restore()
            except Exception as e:
                messagebox.showerror(get_translations("error_title"), f"{get_translations('window_focus_error')}: {e}")

    def musikdatei_parsen(self, dateipfad):
        dateipfad = Path(dateipfad)
        if not dateipfad.exists():
            raise FileNotFoundError(f"{get_translations('file_not_found')}: {dateipfad}")
        with dateipfad.open('r', encoding="utf-8") as datei:
            if dateipfad.suffix in {'.json', '.skysheet'}:
                return json.load(datei)
            elif dateipfad.suffix == '.txt':
                return json.loads(datei.read())
            else:
                raise ValueError(f"{get_translations('unknown_file_format')}: {dateipfad}")

    def note_abspielen(self, note, i, song_notes, tastendruck_dauer):
        note_taste = note['key'].lower()
        note_zeit = note['time']
        if note_taste in self.tastenkarten:
            self.tastatur_steuerung.press(self.tastenkarten[note_taste])
            Timer(tastendruck_dauer, self.tastatur_steuerung.release, [self.tastenkarten[note_taste]]).start()

        if i < len(song_notes) - 1:
            nächste_note_zeit = song_notes[i + 1]['time']
            warte_zeit = (nächste_note_zeit - note_zeit) / 1000
            time.sleep(warte_zeit)

    def musik_abspielen(self, song_daten, stop_event, tastendruck_dauer):
        if isinstance(song_daten, list) and len(song_daten) > 0:
            song_daten = song_daten[0]
        if 'songNotes' not in song_daten:
            raise ValueError(get_translations('missing_key_songNotes'))

        song_notes = song_daten['songNotes']
        for i, note in enumerate(song_notes):
            self.warten_auf_pause()
            if stop_event.is_set():
                break
            self.note_abspielen(note, i, song_notes, tastendruck_dauer)

        winsound.Beep(1000, 500)

    def warten_auf_pause(self):
        """Wartet darauf, dass die Pause beendet wird."""
        while self.pause_flag.is_set():
            time.sleep(0.1)

    def stoppe_abspiel_thread(self):
        if self.abspiel_thread and self.abspiel_thread.is_alive():
            self.stop_event.set()
            self.abspiel_thread.join()
            self.stop_event.clear()


class MusikApp:
    def __init__(self):
        self.player = MusikPlayer()
        self.dateipfad_ausgewählt = None
        self.tastendruck_dauer = 0.1
        self.presets = [0.2, 0.248, 0.3, 0.5, 1.0]
        self.root = None

        self.listener = Listener(on_press=self.tastendruck_erkannt)
        self.listener.start()

    def beenden(self):
        if not self.player.finde_sky_fenster():
            self.player.stoppe_abspiel_thread()
            self.listener.stop()
            self.root.quit()
            self.root.destroy()
            sys.exit()

    def datei_dialog_öffnen(self):
        songs_ordner = Path.cwd() / "resources/Songs"
        dateipfad = filedialog.askopenfilename(
            initialdir=songs_ordner if songs_ordner.exists() else Path.cwd(),
            title=get_translations("file_select_title"),
            filetypes=[(get_translations("supported_formats"), "*.json *.txt *.skysheet")]
        )
        if dateipfad:
            self.dateipfad_ausgewählt = dateipfad
            self.datei_label.configure(text=Path(dateipfad).name)

    def ausgewähltes_lied_abspielen(self):
        if not self.dateipfad_ausgewählt:
            messagebox.showwarning(get_translations("warning_title"), get_translations("choose_song_warning"))
            return

        self.player.stoppe_abspiel_thread()

        try:
            song_daten = self.player.musikdatei_parsen(self.dateipfad_ausgewählt)
            sky_fenster = self.player.finde_sky_fenster()
            self.player.fenster_fokus(sky_fenster)
            time.sleep(2)

            if not self.player.abspiel_thread or not self.player.abspiel_thread.is_alive():
                self.player.abspiel_thread = Thread(target=self.player.musik_abspielen, args=(song_daten, self.player.stop_event, self.tastendruck_dauer), daemon=True)
                self.player.abspiel_thread.start()
        except Exception as e:
            messagebox.showerror(get_translations("error_title"), f"{get_translations('play_error_message')}: {e}")

    def tastendruck_dauer_setzen(self, wert):
        self.tastendruck_dauer = round(float(wert), 3)
        self.dauer_anzeige.configure(text=f"{self.tastendruck_dauer} s")

    def toggle_tastendruck(self):
        self.player.tastendruck_aktiviert = not self.player.tastendruck_aktiviert
        status = get_translations("enabled" if self.player.tastendruck_aktiviert else "disabled")
        self.tastendruck_button.configure(text=f"{get_translations('key_press')}: {status}")

        if self.player.tastendruck_aktiviert:
            self.root.geometry("650x420")
            self.dauer_slider.pack(pady=10, before=self.play_button)
            self.dauer_anzeige.pack(pady=5, before=self.play_button)
            self.presets_button_frame.pack(pady=10, before=self.play_button)
        else:
            self.root.geometry("500x250")
            self.dauer_slider.pack_forget()
            self.dauer_anzeige.pack_forget()
            self.presets_button_frame.pack_forget()

    def tastendruck_erkannt(self, key):
        try:
            if hasattr(key, 'char') and key.char == '#':
                if self.player.pause_flag.is_set():
                    self.player.pause_flag.clear()
                else:
                    self.player.pause_flag.set()
        except Exception as e:
            messagebox.showerror(get_translations("error_title"), f"{get_translations('key_recognition_error')}: {e}")

    def preset_button_click(self, dauer):
        self.tastendruck_dauer = dauer
        self.dauer_slider.set(self.tastendruck_dauer)
        self.dauer_anzeige.configure(text=f"{self.tastendruck_dauer} s")

    def gui_starten(self):
        ctk.set_appearance_mode("dark")
        self.root = ctk.CTk()
        self.root.title(get_translations("project_title"))
        self.root.geometry("500x250")
        self.root.iconbitmap("resources/icons/icon.ico")

        self.root.protocol('WM_DELETE_WINDOW', self.beenden)

        titel_label = ctk.CTkLabel(self.root, text=get_translations("project_title"), font=("Arial", 18, "bold"))
        titel_label.pack(pady=10)

        self.datei_label = ctk.CTkButton(self.root, text=get_translations("no_song_selected"), command=self.datei_dialog_öffnen,
                                         font=("Arial", 14), fg_color="grey", width=300, height=40)
        self.datei_label.pack(pady=10)

        status = get_translations("enabled" if self.player.tastendruck_aktiviert else "disabled")
        self.tastendruck_button = ctk.CTkButton(self.root, text=f"{get_translations('key_press')}: {status}", command=self.toggle_tastendruck,
                                                width=200, height=30)
        self.tastendruck_button.pack(pady=10)

        self.dauer_slider = ctk.CTkSlider(self.root, from_=0.1, to=1.0, number_of_steps=100,
                                          command=self.tastendruck_dauer_setzen)
        self.dauer_slider.set(self.tastendruck_dauer)

        self.dauer_anzeige = ctk.CTkLabel(self.root, text=f"{self.tastendruck_dauer} s", font=("Arial", 12))

        self.play_button = ctk.CTkButton(self.root, text=get_translations("play_button_text"), command=self.ausgewähltes_lied_abspielen,
                                         width=200, height=40)
        self.play_button.pack(pady=20)

        self.presets_button_frame = ctk.CTkFrame(self.root)

        for preset in self.presets:
            button = ctk.CTkButton(self.presets_button_frame, text=f"{preset}s", 
                                   command=lambda p=preset: self.preset_button_click(p), 
                                   width=100, height=30)
            button.grid(row=0, column=self.presets.index(preset), padx=15, pady=10)

        self.root.mainloop()


if __name__ == '__main__':
    selected_language = load_selected_language() 
    translations = load_translations(selected_language)

    app = MusikApp()
    app.gui_starten()