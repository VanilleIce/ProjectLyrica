from pathlib import Path
from threading import Event, Thread, Timer
from pynput.keyboard import Controller, Listener
from tkinter import messagebox, filedialog
import customtkinter as ctk
import pygetwindow as gw
import json
import time
import winsound

# Globale Variablen
pause_flag = Event()
abspiel_thread = None
stop_event = Event()
tastatur_steuerung = Controller()

# Funktion, um das Sky-Fenster zu finden
def finde_sky_fenster():
    fenster_liste = gw.getWindowsWithTitle("Sky")
    if not fenster_liste:
        return None
    return fenster_liste[0]

# Funktion, um das Sky-Fenster zu fokussieren
def fenster_fokus(sky_fenster):
    if not sky_fenster:
        print("Sky-Fenster nicht gefunden.")
        messagebox.showerror("Fehler", "Sky-Fenster nicht gefunden. Bitte öffne Sky und versuche es erneut.")
        return

    try:
        sky_fenster.activate()
    except Exception:
        try:
            sky_fenster.minimize()
            sky_fenster.restore()
        except Exception as e:
            print(f"Fehler beim Fokusieren des Sky-Fensters: {e}")

# Funktion zum Laden der Tastenzuordnungen
def tastenkarten_holen():
    basis_karten = {i: k for i, k in enumerate('zuiophjklönm,.-')}
    return {f'{prefix}{key}'.lower(): value for prefix in ['Key', '1Key', '2Key', '3Key'] for key, value in basis_karten.items()}

tastenkarten = tastenkarten_holen()

# Funktion zum Parsen der Musikdatei
def musikdatei_parsen(dateipfad):
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

# Funktion, um eine einzelne Note abzuspielen
def note_abspielen(note, i, song_notes, tastendruck_dauer):
    note_taste = note['key'].lower()
    note_zeit = note['time']
    if note_taste in tastenkarten:
        # Simuliere Tastendruck
        tastatur_steuerung.press(tastenkarten[note_taste])
        Timer(tastendruck_dauer, tastatur_steuerung.release, [tastenkarten[note_taste]]).start()

    # Verzögerung zur nächsten Note
    if i < len(song_notes) - 1:
        nächste_note_zeit = song_notes[i + 1]['time']
        warte_zeit = (nächste_note_zeit - note_zeit) / 1000
        time.sleep(warte_zeit)

# Funktion, um Musik abzuspielen
def musik_abspielen(song_daten, stop_event, tastendruck_dauer):
    if isinstance(song_daten, list) and len(song_daten) > 0:
        song_daten = song_daten[0]
    if 'songNotes' not in song_daten:
        raise ValueError("Die Musikdatei enthält keinen Schlüssel 'songNotes'.")

    song_notes = song_daten['songNotes']
    for i, note in enumerate(song_notes):
        # Pausieren
        while pause_flag.is_set():
            time.sleep(0.1)
        # Abbrechen
        if stop_event.is_set():
            print("Abspielen gestoppt.")
            break
        note_abspielen(note, i, song_notes, tastendruck_dauer)

    winsound.Beep(1000, 500)
    print("Abspielen beendet.")

# Funktion, um das Abspielen zu starten
def ausgewähltes_lied_abspielen(dateipfad, sky_fenster, tastendruck_dauer):
    global abspiel_thread, stop_event
    if not dateipfad:
        messagebox.showwarning("Warnung", "Bitte wähle ein Lied aus!")
        return

    if abspiel_thread and abspiel_thread.is_alive():
        stop_event.set()
        abspiel_thread.join()

    try:
        song_daten = musikdatei_parsen(dateipfad)
        fenster_fokus(sky_fenster)
        stop_event.clear()
        abspiel_thread = Thread(target=musik_abspielen, args=(song_daten, stop_event, tastendruck_dauer))
        abspiel_thread.start()
    except Exception as e:
        print(f"Fehler beim Abspielen: {e}")
        messagebox.showerror("Fehler", f"Fehler beim Abspielen: {e}")

# Funktion für Tastendruck-Erkennung
def tastendruck_erkannt(key):
    try:
        if hasattr(key, 'char') and key.char.lower() == '#':
            if pause_flag.is_set():
                pause_flag.clear()
                print("Abspielen fortgesetzt.")
            else:
                pause_flag.set()
                print("Abspielen pausiert.")
    except Exception as e:
        print(f"Fehler bei Tastenerkennung: {e}")

# GUI-Setup
def gui_starten():
    global stop_event
    sky_fenster = finde_sky_fenster()
    dateipfad_ausgewählt = None
    tastendruck_dauer = 0.2

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

    def datei_dialog_öffnen():
        nonlocal dateipfad_ausgewählt
        dateipfad = filedialog.askopenfilename(
            title="Wähle ein Lied",
            filetypes=[("Unterstützte Formate", "*.json *.txt *.skysheet")]
        )
        if dateipfad:
            dateipfad_ausgewählt = dateipfad
            datei_label.configure(text=Path(dateipfad).name)
        else:
            messagebox.showwarning("Warnung", "Kein Lied wurde ausgewählt!")

    datei_label = ctk.CTkButton(root, text="Kein Lied ausgewählt", command=datei_dialog_öffnen,
                                font=("Arial", 14), fg_color="grey", width=300, height=40)
    datei_label.pack(pady=10)

    def toggle_tastendruck_dauer():
        nonlocal tastendruck_dauer
        tastendruck_dauer = 0.246 if tastendruck_dauer == 0.2 else 0.2

    tastendruck_dauer_checkbox = ctk.CTkCheckBox(root, text="Längere Tastendruckdauer (0.3s)", command=toggle_tastendruck_dauer)
    tastendruck_dauer_checkbox.pack(pady=10)

    play_button = ctk.CTkButton(root, text="Lied Abspielen",
                                command=lambda: ausgewähltes_lied_abspielen(dateipfad_ausgewählt, sky_fenster, tastendruck_dauer),
                                width=200, height=40)
    play_button.pack(pady=10)

    root.mainloop()

listener = Listener(on_press=tastendruck_erkannt)
listener.start()

if __name__ == '__main__':
    gui_starten()
