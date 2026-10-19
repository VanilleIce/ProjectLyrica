# Copyright (C) 2026 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import logging
from pathlib import Path

import customtkinter as ctk
from tkinter import messagebox

from language_manager import LanguageManager
from resource_loader import resource_path

logger = logging.getLogger("ProjectLyrica.LanguageWindow")


class LanguageWindow:
    """Sprachauswahl-Dialog.

    Kann auf zwei Arten genutzt werden:
        1. Standalone (parent=None): erstellt CTk() und ruft mainloop()
        2. Als Toplevel (parent=...): CTkToplevel, mainloop kommt vom Parent
    """

    _open = False
    _window = None

    @classmethod
    def show(cls, parent=None):
        """Zeigt den Sprachauswahl-Dialog.

        Args:
            parent: Optionales Parent-Window. Wenn None, wird ein
                    eigenständiges CTk() mit mainloop() erstellt.
        """
        # Wenn schon offen → fokussieren
        if cls._open and cls._window is not None:
            try:
                if cls._window.winfo_exists():
                    cls._window.focus()
                    cls._window.lift()
                    return
            except Exception:
                pass
            # Fenster existiert nicht mehr → Reset
            cls._open = False
            cls._window = None

        cls._open = True

        try:
            cls._build_window(parent)
        except Exception as e:
            logger.critical(f"Failed to open language window: {e}", exc_info=True)
            cls._open = False
            cls._window = None
            raise

    # ==================== Private ====================

    @classmethod
    def _build_window(cls, parent=None):
        """Erstellt und zeigt das Sprachauswahl-Fenster."""
        # Sprachen prüfen
        languages = LanguageManager.get_languages()
        if not languages:
            cls._open = False

            error_text = LanguageManager.get('no_languages_configured')
            if error_text == '[no_languages_configured]':
                error_text = "No languages configured"

            messagebox.showerror(
                LanguageManager.get('error_title'),
                error_text
            )
            return

        # Fenster erstellen
        is_standalone = parent is None

        if is_standalone:
            window = ctk.CTk()
        else:
            window = ctk.CTkToplevel(parent)
            try:
                window.transient(parent)
            except Exception:
                pass

        cls._window = window

        window.title(LanguageManager.get('language_window_title'))
        window.geometry("400x200")
        window.resizable(False, False)

        # Icon setzen (mit Fallback)
        icon_path = resource_path("resources/icons/icon.ico")
        if Path(icon_path).exists():
            try:
                window.iconbitmap(icon_path)
            except Exception as e:
                logger.warning(f"Could not set window icon: {e}")

        # Modality
        try:
            window.grab_set()
        except Exception:
            pass

        # Callback beim Schließen
        window.protocol("WM_DELETE_WINDOW", cls._close_window)

        # Sprachen-Mapping
        lang_dict = {name: code for code, name, _ in languages}
        current_lang = LanguageManager.get_current_lang()
        default_name = next(
            (n for c, n, _ in languages if c == current_lang),
            languages[0][1]
        )

        # ==================== UI ====================

        ctk.CTkLabel(
            window,
            text=LanguageManager.get('select_language'),
            font=("Arial", 14)
        ).pack(pady=10)

        combo = ctk.CTkComboBox(
            window,
            values=list(lang_dict.keys()),
            state="readonly",
            width=200
        )
        combo.set(default_name)
        combo.pack(pady=10)

        def save():
            selected_name = combo.get()
            code = lang_dict.get(selected_name)
            if not code:
                return

            if LanguageManager.set_language(code):
                messagebox.showinfo(
                    LanguageManager.get('info_title'),
                    LanguageManager.get('language_saved')
                )
                cls._close_window()
            else:
                error_text = LanguageManager.get('language_save_failed')
                if error_text == '[language_save_failed]':
                    error_text = "Could not save language. Please try again."

                messagebox.showerror(
                    LanguageManager.get('error_title'),
                    error_text
                )

        ctk.CTkButton(
            window,
            text=LanguageManager.get('save_button_text'),
            command=save,
            width=120
        ).pack(pady=20)

        # Enter/Escape Bindings
        window.bind('<Return>', lambda e: save())
        window.bind('<Escape>', lambda e: cls._close_window())

        # Fokus verzögert
        window.after(50, cls._focus_window)

        # ==================== Mainloop ====================

        if is_standalone:
            # Eigenständiges Fenster → blockiert bis geschlossen
            logger.debug("LanguageWindow standalone: entering mainloop")
            window.mainloop()
            # Cleanup nach mainloop (falls nicht schon passiert)
            cls._open = False
            cls._window = None
        else:
            # Toplevel → Parent kümmert sich um mainloop
            logger.debug("LanguageWindow toplevel: parent handles mainloop")

    @classmethod
    def _focus_window(cls):
        """Fokussiert das Fenster (mit Safety-Check)."""
        if cls._window is None:
            return
        try:
            if cls._window.winfo_exists():
                cls._window.focus_force()
                cls._window.lift()
        except Exception:
            pass

    @classmethod
    def _close_window(cls):
        """Schließt das Fenster sauber."""
        try:
            if cls._window is not None and cls._window.winfo_exists():
                try:
                    cls._window.grab_release()
                except Exception:
                    pass
                cls._window.destroy()
        except Exception as e:
            logger.error(f"Error closing language window: {e}")
        finally:
            cls._window = None
            cls._open = False

    # ==================== Public Helpers ====================

    @classmethod
    def is_open(cls) -> bool:
        """Prüft ob Fenster offen ist (validiert auch _window)."""
        if not cls._open:
            return False
        if cls._window is None:
            cls._open = False
            return False
        try:
            if not cls._window.winfo_exists():
                cls._open = False
                cls._window = None
                return False
        except Exception:
            cls._open = False
            cls._window = None
            return False
        return True