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
            print("Sky-Fenster nicht gefunden.")
            return
        try:
            sky_fenster.activate()
        except Exception:
            try:
                sky_fenster.minimize()
                sky_fenster.restore()
            except Exception as e:
                print(f"Fehler beim Fokusieren des Sky-Fensters: {e}")

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
                print("Abspielen gestoppt.")
                break
            self.note_abspielen(note, i, song_notes, tastendruck_dauer)

        winsound.Beep(1000, 500)
        print("Abspielen beendet.")

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
            print("Abspiel-Thread gestoppt.")


class MusikApp:
    def __init__(self):
        self.player = MusikPlayer()
        self.dateipfad_ausgewählt = None
        self.tastendruck_dauer = 0.2

    def datei_dialog_öffnen(self):
        songs_ordner = Path.cwd() / "resources/Songs"
        dateipfad = filedialog.askopenfilename(
            initialdir=songs_ordner if songs_ordner.exists() else Path.cwd(),
            title="Wähle ein Lied",
            filetypes=[("Unterstützte Formate", "*.json *.txt *.skysheet")]
        )
        if dateipfad:
            print(f"Ausgewähltes Lied: {Path(dateipfad).name}")
            self.dateipfad_ausgewählt = dateipfad
            self.datei_label.configure(text=Path(dateipfad).name)
            return dateipfad
        else:
            print("Kein Lied ausgewählt.")
            messagebox.showwarning("Warnung", "Kein Lied wurde ausgewählt!")
            return None

    def toggle_tastendruck_dauer(self):
        self.tastendruck_dauer = 0.246 if self.tastendruck_dauer == 0.2 else 0.2

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
            print(f"Fehler beim Abspielen: {e}")
            messagebox.showerror("Fehler", f"Fehler beim Abspielen: {e}")

    def tastendruck_erkannt(self, key):
        try:
            if hasattr(key, 'char') and key.char.lower() == '#':
                if self.player.pause_flag.is_set():
                    self.player.pause_flag.clear()
                    print("Abspielen fortgesetzt.")
                else:
                    self.player.pause_flag.set()
                    print("Abspielen pausiert.")
        except Exception as e:
            print(f"Fehler bei Tastenerkennung: {e}")

    def gui_starten(self):
        ctk.set_appearance_mode("dark")
        root = ctk.CTk()
        root.title("Projekt Lyrica")
        root.geometry("500x350")
        root.iconbitmap("resources/icons/icon.ico")

        titel_label = ctk.CTkLabel(root, text="Projekt Lyrica", font=("Arial", 18, "bold"))
        titel_label.pack(pady=10)

        hinweis_label = ctk.CTkLabel(root, text="Tipp: Drücke '#' um Abspielen zu pausieren/fortzusetzen.",
                                     font=("Arial", 12), text_color="gray")
        hinweis_label.pack(pady=5)

        self.datei_label = ctk.CTkButton(root, text="Kein Lied ausgewählt", command=self.datei_dialog_öffnen,
                                         font=("Arial", 14), fg_color="grey", width=300, height=40)
        self.datei_label.pack(pady=10)

        tastendruck_dauer_checkbox = ctk.CTkCheckBox(root, text="Längere Tastendruckdauer (0.3s)", command=self.toggle_tastendruck_dauer)
        tastendruck_dauer_checkbox.pack(pady=10)

        play_button = ctk.CTkButton(root, text="Lied Abspielen", command=self.ausgewähltes_lied_abspielen,
                                    width=200, height=40)
        play_button.pack(pady=10)

        listener = Listener(on_press=self.tastendruck_erkannt)
        listener.start()

        root.mainloop()


# Anwendung starten
if __name__ == '__main__':
    app = MusikApp()
    app.gui_starten()
