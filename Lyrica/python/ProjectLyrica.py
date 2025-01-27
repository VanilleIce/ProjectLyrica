import json
import time
import winsound
import pygetwindow as gw
import customtkinter as ctk
from pathlib import Path
from threading import Event, Thread, Timer
from pynput.keyboard import Controller, Listener
from tkinter import filedialog, messagebox


class MusikPlayer:
    def __init__(self):
        self.pause_flag = Event()
        self.stop_event = Event()
        self.abspiel_thread = None
        self.tastatur_steuerung = Controller()
        self.tastenkarten = self.tastenkarten_holen()

    def tastenkarten_holen(self):
        basis_karten = {i: k for i, k in enumerate('zuiophjklönm,.-')}
        return {f'{prefix}{key}'.lower(): value for prefix in ['Key', '1Key', '2Key', '3Key'] for key, value in basis_karten.items()}

    def finde_sky_fenster(self):
        fenster_liste = gw.getWindowsWithTitle("Sky")
        if not fenster_liste:
            return None
        return fenster_liste[0]

    def fenster_fokus(self, sky_fenster):
        if not sky_fenster:
            messagebox.showwarning("Warnung", "Sky-Fenster nicht gefunden.")
            return
        try:
            sky_fenster.activate()
        except Exception:
            try:
                sky_fenster.minimize()
                sky_fenster.restore()
            except Exception as e:
                messagebox.showerror("Fehler", f"Fehler beim Fokussieren des Sky-Fensters: {e}")

    def musikdatei_parsen(self, dateipfad):
        dateipfad = Path(dateipfad)
        if not dateipfad.exists():
            raise FileNotFoundError(f"Die Datei wurde nicht gefunden: {dateipfad}")
        with dateipfad.open('r', encoding="utf-8") as datei:
            if dateipfad.suffix in {'.json', '.skysheet'}:
                return json.load(datei)
            elif dateipfad.suffix == '.txt':
                return json.loads(datei.read())
            else:
                raise ValueError(f"Unbekanntes Dateiformat: {dateipfad}")

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
            raise ValueError("Die Musikdatei enthält keinen Schlüssel 'songNotes'.")

        song_notes = song_daten['songNotes']
        for i, note in enumerate(song_notes):
            # Pausieren
            self.warten_auf_pause()
            # Abbrechen
            if stop_event.is_set():
                break
            self.note_abspielen(note, i, song_notes, tastendruck_dauer)

        winsound.Beep(1000, 500)

    def warten_auf_pause(self):
        """Wartet darauf, dass die Pause beendet wird."""
        while self.pause_flag.is_set():
            time.sleep(0.1)

    def stoppe_abspiel_thread(self):
        """Stoppt den aktuellen Abspiel-Thread, wenn er läuft."""
        if self.abspiel_thread and self.abspiel_thread.is_alive():
            self.stop_event.set()
            self.abspiel_thread.join()
            self.stop_event.clear()


class MusikApp:
    def __init__(self):
        self.player = MusikPlayer()
        self.dateipfad_ausgewählt = None
        self.tastendruck_dauer = 0.2  # Standard-Tastendruckdauer
        self.presets = [0.2, 0.3, 0.5, 1.0]  # Presets für die Tastendruckdauer

    def datei_dialog_öffnen(self):
        songs_ordner = Path.cwd() / "resources/Songs"
        dateipfad = filedialog.askopenfilename(
            initialdir=songs_ordner if songs_ordner.exists() else Path.cwd(),
            title="Wähle ein Lied",
            filetypes=[("Unterstützte Formate", "*.json *.txt *.skysheet")]
        )
        if dateipfad:
            self.dateipfad_ausgewählt = dateipfad
            self.datei_label.configure(text=Path(dateipfad).name)
            return dateipfad
        else:
            messagebox.showwarning("Warnung", "Kein Lied wurde ausgewählt!")
            return None

    def tastendruck_dauer_setzen(self, wert):
        self.tastendruck_dauer = round(float(wert), 3)  # Rundung auf 3 Nachkommastellen
        self.dauer_anzeige.configure(text=f"{self.tastendruck_dauer} s")

    def preset_auswählen(self, wert):
        self.tastendruck_dauer_setzen(wert)
        self.dauer_slider.set(wert)

    def ausgewähltes_lied_abspielen(self):
        if not self.dateipfad_ausgewählt:
            messagebox.showwarning("Warnung", "Bitte wähle ein Lied aus!")
            return

        self.player.stoppe_abspiel_thread()

        try:
            song_daten = self.player.musikdatei_parsen(self.dateipfad_ausgewählt)
            sky_fenster = self.player.finde_sky_fenster()
            self.player.fenster_fokus(sky_fenster)
            time.sleep(2)
            self.player.abspiel_thread = Thread(target=self.player.musik_abspielen, args=(song_daten, self.player.stop_event, self.tastendruck_dauer))
            self.player.abspiel_thread.start()
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Abspielen: {e}")

    def tastendruck_erkannt(self, key):
        try:
            if hasattr(key, 'char') and key.char.lower() == '#':
                if self.player.pause_flag.is_set():
                    self.player.pause_flag.clear()
                else:
                    self.player.pause_flag.set()
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler bei Tastenerkennung: {e}")

    def gui_starten(self):
        ctk.set_appearance_mode("dark")
        root = ctk.CTk()
        root.title("Projekt Lyrica")
        root.geometry("500x400")
        root.iconbitmap("resources/icons/icon.ico")

        titel_label = ctk.CTkLabel(root, text="Projekt Lyrica", font=("Arial", 18, "bold"))
        titel_label.pack(pady=10)

        hinweis_label = ctk.CTkLabel(root, text="Tipp: Drücke '#' um Abspielen zu pausieren/fortzusetzen.",
                                     font=("Arial", 12), text_color="gray")
        hinweis_label.pack(pady=5)

        self.datei_label = ctk.CTkButton(root, text="Kein Lied ausgewählt", command=self.datei_dialog_öffnen,
                                         font=("Arial", 14), fg_color="grey", width=300, height=40)
        self.datei_label.pack(pady=10)

        slider_label = ctk.CTkLabel(root, text="Tastendruckdauer (Sekunden):", font=("Arial", 12))
        slider_label.pack(pady=5)

        self.dauer_slider = ctk.CTkSlider(root, from_=0.1, to=1.0, number_of_steps=100,
                                          command=self.tastendruck_dauer_setzen)
        self.dauer_slider.set(self.tastendruck_dauer)
        self.dauer_slider.pack(pady=10)

        self.dauer_anzeige = ctk.CTkLabel(root, text=f"{self.tastendruck_dauer} s", font=("Arial", 12))
        self.dauer_anzeige.pack(pady=5)

        preset_frame = ctk.CTkFrame(root)
        preset_frame.pack(pady=10)

        for preset in self.presets:
            preset_button = ctk.CTkButton(preset_frame, text=f"{preset}s", command=lambda p=preset: self.preset_auswählen(p),
                                          width=50, height=30, font=("Arial", 10))
            preset_button.pack(side="left", padx=5)

        play_button = ctk.CTkButton(root, text="Lied Abspielen", command=self.ausgewähltes_lied_abspielen,
                                    width=200, height=40)
        play_button.pack(pady=20)

        listener = Listener(on_press=self.tastendruck_erkannt)
        listener.start()

        root.mainloop()


# Anwendung starten
if __name__ == '__main__':
    app = MusikApp()
    app.gui_starten()
