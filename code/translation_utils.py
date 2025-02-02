import os
import json
import sys
import customtkinter as ctk
from tkinter import messagebox, ttk
import xml.etree.ElementTree as ET

SETTINGS_FILE = 'settings.json'

# -------------------------------
# Funktion: Ausgewählte Sprache laden
# -------------------------------
def load_selected_language():
    """Lädt die ausgewählte Sprache aus der settings.json."""
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as file:
            settings = json.load(file)
            return settings.get('selected_language', 'en_US')
    except FileNotFoundError:
        return None
    except Exception as e:
        return None

# -------------------------------
# Funktion: Sprache speichern
# -------------------------------
def save_selected_language(language_code):
    """Speichert die ausgewählte Sprache in der settings.json."""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as file:
            json.dump({'selected_language': language_code}, file, indent=4)
    except Exception as e:
        pass

# -------------------------------
# Funktion: Verfügbare Sprachen laden
# -------------------------------
def load_available_languages():
    """Lädt die verfügbaren Sprachen aus der config/lang.xml."""
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
        messagebox.showerror("Fehler", get_translation('lang_config_not_found'))
        return []
    except Exception as e:
        messagebox.showerror("Fehler", get_translation('error_loading_languages').format(e))
        return []

# -------------------------------
# Funktion: Übersetzungen laden
# -------------------------------
def load_translations(language_code):
    """Lädt Übersetzungen basierend auf dem Sprachcode."""
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
        return translations
    except FileNotFoundError:
        if language_code != 'en_US':
            return load_translations('en_US')
        else:
            messagebox.showerror(
                get_translation('error_title'), 
                get_translation('missing_translations_file').format(language_code)
            )
            return {}
    except Exception as e:
        messagebox.showerror(
            get_translation('error_title'), 
            get_translation('error_loading_translations').format(e)
        )
        return {}

# -------------------------------
# Funktion: Übersetzung für Fehlernachrichten
# -------------------------------
def get_translation(key):
    """Holt die Übersetzung basierend auf dem Key aus der geladenen Sprache."""
    selected_language = load_selected_language()
    translations = load_translations(selected_language or 'en_US')
    return translations.get(key, f"[{key}]")

# -------------------------------
# GUI: Sprachwahlfenster
# -------------------------------

language_window_open = False

def language_selection_window():
    global language_window_open
    """Zeigt ein Fenster zur Sprachauswahl an."""
    if language_window_open:
        return

    language_window_open = True

    selected_language = load_selected_language()

    if selected_language:
        language_window_open = False
        return

    translations = load_translations(selected_language or 'en_US')

    root = ctk.CTk()
    root.title(translations.get('language_window_title'))
    root.geometry("400x200")
    root.iconbitmap("resources/icons/icon.ico")

    languages = load_available_languages()
    language_dict = {name: code for code, name in languages}
    language_names = list(language_dict.keys())

    default_language_name = next((name for name, code in language_dict.items() if code == selected_language), "English")

    ctk.CTkLabel(root, text=translations.get('select_language'), font=("Arial", 14)).pack(pady=10)
    
    language_combobox = ctk.CTkComboBox(root, values=language_names, state="readonly", font=("Arial", 12))
    language_combobox.set(default_language_name)
    language_combobox.pack(pady=10)

    def on_save():
        """Speichert die ausgewählte Sprache und beendet das Fenster."""
        selected_name = language_combobox.get()
        selected_code = language_dict.get(selected_name)

        if not selected_code:
            messagebox.showerror(
                translations.get('error_title'), 
                get_translation('language_not_found')
            )
            return

        save_selected_language(selected_code)
        messagebox.showinfo(
            translations.get('info_title'), 
            get_translation('language_saved')
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
        sys.exit()

    root.protocol("WM_DELETE_WINDOW", close_language_window)

    root.mainloop()

# -------------------------------
# Funktion: Hauptprogramm starten
# -------------------------------
def start_main_program():
    """Startet das Hauptprogramm nach der Sprachauswahl."""
    from ProjectLyrica import MusikApp
    app = MusikApp()
    app.gui_starten()

# -------------------------------
# Start: Sprachauswahl aufrufen
# -------------------------------
def start_language_selection():
    """Ruft die GUI für die Sprachwahl auf, aber nur wenn noch keine Sprache ausgewählt wurde."""
    selected_language = load_selected_language()

    if selected_language is not None:
        start_main_program()
        return  

    language_selection_window() 

# -------------------------------
# Hauptlauf
# -------------------------------
if __name__ == "__main__":
    start_main_program()