import pygetwindow
from pynput.keyboard import Controller, Key
import time
import json
import os
import threading
import tkinter as tk
from tkinter import messagebox, filedialog
import winsound

# Initialisiere globale Variablen für das Sky-Fenster
fenster_liste = pygetwindow.getWindowsWithTitle("Sky")  # Holt alle Fenster mit dem Titel "Sky"
sky_fenster = None  # Initialisiert die Variable sky_fenster als None

# Durchläuft alle Fenster, um das Sky-Fenster zu finden
for fenster in fenster_liste:
    if fenster.title == "Sky":
        sky_fenster = fenster  # Wenn das Fenster mit dem Titel "Sky" gefunden wird, wird es der Variable zugewiesen

# Falls Sky nicht gefunden wurde, zeige eine Fehlermeldung und beende das Skript
if sky_fenster is None:
    messagebox.showerror("Fehler", "Sky wurde nicht gefunden. Bitte öffne Sky, bevor du dieses Skript ausführst.")
    quit()  # Beendet das Skript, wenn das "Sky"-Fenster nicht gefunden wird

# Funktion, um das Sky-Fenster in den Vordergrund zu bringen
def fenster_fokus():
    try:
        sky_fenster.activate()  # Versucht, das "Sky"-Fenster zu aktivieren (in den Vordergrund zu holen)
    except Exception as e:
        sky_fenster.minimize()  # Minimiert das Fenster, falls ein Fehler auftritt
        sky_fenster.restore()  # Stellt das Fenster wieder her, um es zu aktivieren

# Funktion, um das Icon für das Fenster zu setzen (falls vorhanden)
def icon_setzen(fenster, icon_pfad="resources/icons/icon.ico"):
    if os.path.exists(icon_pfad):  # Überprüft, ob die angegebene Icon-Datei existiert
        fenster.iconbitmap(icon_pfad)  # Setzt das Icon des Fensters, wenn es existiert

# Initialisiere den Tastaturcontroller
tastatur_steuerung = Controller()  # Erstellt einen Controller für das Simulieren von Tastatureingaben

# Definiere die Tastenzuordnungen für das Sky-Instrument
def tastenkarten_holen():
    # Basiszuordnung von Noten zu Tasten
    basis_karten = {
        0: 'z', 1: 'u', 2: 'i', 3: 'o', 4: 'p',
        5: 'h', 6: 'j', 7: 'k', 8: 'l', 9: 'ö',
        10: 'n', 11: 'm', 12: ',', 13: '.', 14: '-'
    }
    tastenkarten = {}  # Initialisiert ein leeres Dictionary für die Tastenkarten
    prefixe = ['Key', '1Key', '2Key', '3Key']  # Liste der Präfixe für die Tastenkarten
    # Durchläuft jedes Präfix und jede Note, um die Tastenkarten zu erstellen
    for prefix in prefixe:
        for key, value in basis_karten.items():
            tastenkarten[f'{prefix}{key}'.lower()] = value  # Fügt die Zuordnungen zu den Tastenkarten hinzu

    return tastenkarten  # Gibt die erstellten Tastenkarten zurück

# Hole die Tastenkarten
tastenkarten = tastenkarten_holen()  # Ruft die Funktion auf, um die Tastenkarten zu erhalten

# Thread, der das Drücken einer Taste simuliert
class TasteDruckThread(threading.Thread):
    def __init__(self, note_taste):
        super().__init__()  # Initialisiert den Thread
        self.note_taste = note_taste  # Speichert die Note, die gespielt werden soll

    def run(self):
        try:
            # Wenn die Note in der Zuordnung vorhanden ist, simuliere das Drücken der Taste
            if self.note_taste in tastenkarten:
                tastatur_steuerung.press(tastenkarten[self.note_taste])  # Simuliert das Drücken der Taste
                time.sleep(0.2)  # Wartet 0,2 Sekunden, um die Taste zu halten
                tastatur_steuerung.release(tastenkarten[self.note_taste])  # Lässt die Taste wieder los
            else:
                print(f"Übersprungen: Taste {self.note_taste} nicht in der Belegung gefunden.")  # Wenn die Taste nicht gefunden wird
        except Exception as e:
            print(f"Fehler beim Simulieren der Taste: {e}")  # Gibt einen Fehler aus, wenn das Simulieren der Taste fehlschlägt

# Funktion zum Parsen der Musikdatei (JSON oder Text)
def musikdatei_parsen(dateipfad):
    try:
        print(f"Versuche, Datei zu öffnen: {dateipfad}")  # Gibt den Pfad der Datei aus
        # Überprüfen, ob die Datei existiert
        if not os.path.exists(dateipfad):
            raise FileNotFoundError(f"Die Datei wurde nicht gefunden: {dateipfad}")  # Wirft einen Fehler, wenn die Datei nicht existiert

        with open(dateipfad, 'r', encoding="utf-8") as datei:
            # Wenn die Datei eine JSON- oder Skysheet-Datei ist, lade sie als JSON
            if dateipfad.endswith('.json') or dateipfad.endswith('.skysheet'):
                print(f"Dateiformat erkannt: {dateipfad}")  # Gibt aus, welches Dateiformat erkannt wurde
                return json.load(datei)  # Lädt die Datei als JSON
            # Wenn die Datei eine Textdatei ist, versuche sie als JSON zu laden
            elif dateipfad.endswith('.txt'):
                return json.loads(datei.read())  # Lädt den Text als JSON
            else:
                raise ValueError(f"Unterstütztes Dateiformat nicht gefunden: {dateipfad}")  # Wirft einen Fehler, wenn das Format nicht unterstützt wird
    except Exception as e:
        raise ValueError(f"Fehler beim Parsen der Datei: {e}")  # Wirft den Fehler erneut

# Funktion zum Abspielen der Musik
def musik_abspielen(song_daten):
    song_notes = song_daten['songNotes']  # Extrahiert die Noten aus den Song-Daten
    start_zeit = time.perf_counter()  # Startzeit für das Abspielen
    pause_zeit = 0  # Pausezeit, falls das Fenster nicht aktiv ist

    def note_abspielen(note, i):
        note_zeit = note['time']  # Holt die Zeit der aktuellen Note
        note_taste = note['key'].lower()  # Holt die Taste für die Note (in Kleinbuchstaben)
        
        # Starte den Thread für die Taste, die die Note repräsentiert
        taste_thread = TasteDruckThread(note_taste)
        taste_thread.start()  # Startet den Thread für das Drücken der Taste
        
        if i < len(song_notes) - 1:  # Wenn nicht die letzte Note
            nächste_note_zeit = song_notes[i + 1]['time']  # Holt die Zeit der nächsten Note
            warte_zeit = (nächste_note_zeit - note_zeit) / 1000  # Berechnet die Wartezeit in Sekunden
            time.sleep(warte_zeit)  # Wartet die berechnete Zeit

    for i, note in enumerate(song_notes):
        if sky_fenster.isActive:  # Wenn das Sky-Fenster aktiv ist, spiele die Note ab
            note_abspielen(note, i)
        else:
            # Wenn das Sky-Fenster nicht aktiv ist, warte, bis es wieder aktiv wird
            pause_zeit_start = time.perf_counter()  # Startzeit für die Pause
            while not sky_fenster.isActive:  # Solange das Fenster nicht aktiv ist, warte
                time.sleep(1)  # Warten für 1 Sekunde
            pause_zeit_end = time.perf_counter()  # Endzeit für die Pause
            pause_zeit += pause_zeit_end - pause_zeit_start  # Berechne die gesamte Pausezeit

    # Ein akustisches Signal, wenn das Lied zu Ende ist
    winsound.Beep(1000, 500)  # Frequenz: 1000 Hz, Dauer: 500 ms
    messagebox.showinfo("Info", f"Fertig mit dem Abspielen von {song_daten['name']}")  # Zeigt eine Nachricht an, dass das Lied zu Ende ist

# GUI Setup
def gui_starten():
    root = tk.Tk()  # Erstelle das Hauptfenster
    root.title("Projekt Lyrica")  # Setzt den Fenstertitel
    root.geometry("400x180")  # Setzt die Fenstergröße
    icon_setzen(root)  # Setzt das Fenster-Icon

    # Label zur Anzeige der ausgewählten Musikdatei
    datei_label = tk.Label(root, text="Kein Lied ausgewählt", font=("Arial", 12), fg="black", relief="solid", width=25)
    datei_label.pack(pady=20)  # Packt das Label mit etwas Abstand

    # Variable zum Speichern des ausgewählten Dateipfads
    dateipfad_ausgewählt = None

    # Überprüfe, ob der Ordner "Songs" existiert, zeige eine Fehlermeldung, falls nicht
    songs_ordner = os.path.join(os.getcwd(), "resources/Songs")
    if not os.path.exists(songs_ordner):
        messagebox.showerror("Fehler", "Der Ordner 'Songs' wurde nicht gefunden. Bitte erstellen oder sicherstellen, dass er existiert.")
    else:
        # Aktion, um den Datei-Explorer zu öffnen, wenn man auf das Label klickt
        def datei_dialog_öffnen():
            # Verwende askopenfilename, um eine Datei aus dem "Songs"-Ordner auszuwählen
            dateipfad = filedialog.askopenfilename(
                initialdir=songs_ordner,
                title="Wähle ein Lied", 
                filetypes=[("Unterstützte Formate", "*.json *.txt *.skysheet")]
            )
            if dateipfad:
                # Aktualisiere das Label mit dem ausgewählten Dateinamen
                datei_label.config(text=os.path.basename(dateipfad))
                # Speichere den Dateipfad für die spätere Verwendung, wenn der Benutzer auf "Play" klickt
                nonlocal dateipfad_ausgewählt
                dateipfad_ausgewählt = dateipfad

        # Binde das Klicken auf das Label, um den Datei-Explorer zu öffnen
        datei_label.bind("<Button-1>", lambda event: datei_dialog_öffnen())

        # Spiele das ausgewählte Lied nur nach dem Klick auf den "Play Song"-Button
        def ausgewähltes_lied_abspielen():
            if dateipfad_ausgewählt is None:  # Wenn keine Datei ausgewählt wurde
                messagebox.showwarning("Warnung", "Bitte wähle ein Lied aus!")  # Zeigt eine Warnung an
                return

            try:
                song_daten = musikdatei_parsen(dateipfad_ausgewählt)  # Versucht, die Song-Daten zu laden

                fenster_fokus()  # Bringt das Sky-Fenster in den Vordergrund
                musik_abspielen(song_daten[0])  # Spielt das Lied ab
            except Exception as e:
                messagebox.showerror("Fehler", str(e))  # Zeigt eine Fehlermeldung an, wenn ein Fehler auftritt

        # "Play"-Button (spielt das Lied nur nach dem Klick)
        play_button = tk.Button(root, text="Lied abspielen", command=ausgewähltes_lied_abspielen, font=("Arial", 14), width=12, height=1)
        play_button.pack(pady=15)  # Fügt den Button hinzu

    root.mainloop()  # Startet die GUI-Schleife

# Wenn das Skript direkt ausgeführt wird, starte die GUI
if __name__ == '__main__':
    gui_starten()