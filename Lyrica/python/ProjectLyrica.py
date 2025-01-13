import pygetwindow
from pynput.keyboard import Controller, Key
import time
import json
import os
import threading
import customtkinter as ctk
from tkinter import messagebox, filedialog
import winsound

fenster_liste = pygetwindow.getWindowsWithTitle("Sky")
sky_fenster = next((f for f in fenster_liste if f.title == "Sky"), None)

for fenster in fenster_liste:
    if fenster.title == "Sky":
        sky_fenster = fenster

if sky_fenster is None:
    messagebox.showerror("Fehler", "Sky wurde nicht gefunden. Bitte öffne Sky, bevor du dieses Skript ausführst.")
    exit()

def fenster_fokus():
    try:
        sky_fenster.activate()
    except Exception:
        sky_fenster.minimize()
        sky_fenster.restore()

tastatur_steuerung = Controller()

def tastenkarten_holen():
    print("Tastenkarten werden geladen.")
    basis_karten = {i: k for i, k in enumerate('zuiophjklönm,.-')}
    return {f'{prefix}{key}'.lower(): value for prefix in ['Key', '1Key', '2Key', '3Key'] for key, value in basis_karten.items()}

tastenkarten = tastenkarten_holen()

class TasteDruckThread(threading.Thread):
    def __init__(self, note_taste):
        super().__init__()
        self.note_taste = note_taste

    def run(self):
        try:
            if self.note_taste in tastenkarten:
                tastatur_steuerung.press(tastenkarten[self.note_taste]) 
                time.sleep(0.2)
                tastatur_steuerung.release(tastenkarten[self.note_taste])
            else:
                print(f"Übersprungen: Taste {self.note_taste} nicht in der Belegung gefunden.") 
        except Exception as e:
            print(f"Fehler beim Simulieren der Taste: {e}")

def musikdatei_parsen(dateipfad):
    print(f"Parsen der Musikdatei: {dateipfad}")
    try:
        if not os.path.exists(dateipfad):
            raise FileNotFoundError(f"Die Datei wurde nicht gefunden: {dateipfad}")
        with open(dateipfad, 'r', encoding="utf-8") as datei:
            if dateipfad.endswith('.json') or dateipfad.endswith('.skysheet'):
                return json.load(datei)
            elif dateipfad.endswith('.txt'):
                try:
                    return json.loads(datei.read())
                except json.JSONDecodeError:
                    raise ValueError(f"Fehler: Die Textdatei '{dateipfad}' enthält kein gültiges JSON-Format.")
            else:
                raise ValueError(f"Unbekanntes Dateiformat: {dateipfad}")
    except Exception as e:
        print(f"Fehler: {str(e)}")
        raise

def musik_abspielen(song_daten):
    song_notes = song_daten['songNotes']

    def note_abspielen(note, i):
        note_zeit = note['time']
        note_taste = note['key'].lower()
        
        taste_thread = TasteDruckThread(note_taste)
        taste_thread.start()
        
        if i < len(song_notes) - 1:
            nächste_note_zeit = song_notes[i + 1]['time']
            warte_zeit = (nächste_note_zeit - note_zeit) / 1000
            time.sleep(warte_zeit)

    for i, note in enumerate(song_notes):
        if sky_fenster.isActive:
            note_abspielen(note, i)
        else:
            pause_zeit_start = time.perf_counter()
            while not sky_fenster.isActive:
                time.sleep(1)
            pause_zeit_end = time.perf_counter()

    winsound.Beep(1000, 500)
    messagebox.showinfo("Info", f"Fertig mit dem Abspielen von {song_daten['name']}")

def gui_starten():
    root = ctk.CTk()
    root.title("Projekt Lyrica")
    root.geometry("480x300")
    root.iconbitmap("resources/icons/icon.ico")

    titel_label = ctk.CTkLabel(root, text="Projekt Lyrica", font=("Arial", 18, "bold"))
    titel_label.pack(pady=10)

    datei_label = ctk.CTkLabel(root, text="Kein Lied ausgewählt", font=("Arial", 14), fg_color="white", width=300, height=40)
    datei_label.pack(pady=10)

    dateipfad_ausgewählt = None
    songs_ordner = os.path.join(os.getcwd(), "resources/Songs")

    if not os.path.exists(songs_ordner):
        ctk.CTkLabel(root, text="Der Ordner 'Songs' wurde nicht gefunden.", font=("Arial", 12), text_color="red").pack(pady=10)
        return

    def datei_dialog_öffnen():
        nonlocal dateipfad_ausgewählt
        dateipfad = filedialog.askopenfilename(
            initialdir=songs_ordner,
            title="Wähle ein Lied",
            filetypes=[("Unterstützte Formate", "*.json *.txt *.skysheet")]
        )
        if dateipfad:
            dateipfad_ausgewählt = dateipfad
            datei_label.configure(text=os.path.basename(dateipfad))

    def ausgewähltes_lied_abspielen():
        if dateipfad_ausgewählt is None:
            ctk.CTkLabel(root, text="Warnung: Bitte wähle ein Lied aus!", font=("Arial", 16), text_color="red").pack(pady=10)
            return
        try:
            song_daten = musikdatei_parsen(dateipfad_ausgewählt)
            fenster_fokus()
            musik_abspielen(song_daten[0])
        except Exception as e:
            messagebox.showerror("Fehler", str(e))

    datei_button = ctk.CTkButton(root, text="Lied auswählen", command=datei_dialog_öffnen, width=200, height=40)
    datei_button.pack(pady=10)

    play_button = ctk.CTkButton(root, text="Lied abspielen", command=ausgewähltes_lied_abspielen, width=200, height=40)
    play_button.pack(pady=10)

    root.mainloop()

if __name__ == '__main__':
    gui_starten()