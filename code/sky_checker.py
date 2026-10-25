# Copyright (C) 2025-2026 VanilleIce
# All rights reserved.
#
# Project Lyrica is proprietary software.
# Commercial use, redistribution, and modification are prohibited.
# See LICENSE.md for details.

import logging
import sys
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox

from config_manager import ConfigManager
from language_manager import LanguageManager
from resource_loader import resource_path

logger = logging.getLogger("ProjectLyrica.SkyChecker")

EXAMPLE_PATH = (
    r"C:\Program Files (x86)\Steam\steamapps\common"
    r"\Sky Children of the Light\Sky.exe"
)

# Mögliche Steam-Installationsordner
STEAM_SEARCH_PATHS = (
    Path("C:/Program Files (x86)/Steam/steamapps/common"),
    Path("C:/Program Files/Steam/steamapps/common"),
    Path.home() / "Steam/steamapps/common",
)


class SkyChecker:
    """Zeigt den initialen Sky.exe-Auswahl-Dialog."""

    @staticmethod
    def show_initial_settings():
        """Zeigt Auswahl-Dialog falls noch kein gültiger Sky.exe-Pfad vorhanden ist."""
        # Prüfen ob bereits gültiger Pfad konfiguriert
        current_path = ConfigManager.get_value("game_settings.sky_exe_path", "")
        if SkyChecker._is_valid_sky_path(current_path):
            logger.debug(f"Sky.exe path already set: {current_path}")
            return

        logger.info("Sky.exe path missing - showing initial setup dialog")

        # Root-Fenster erstellen
        root = ctk.CTk()
        root.title(LanguageManager.get('window_settings_title'))
        root.geometry("600x180")
        root.resizable(False, False)

        # Icon setzen (mit Fallback)
        icon_path = resource_path("resources/icons/icon.ico")
        if Path(icon_path).exists():
            try:
                root.iconbitmap(icon_path)
            except Exception as e:
                logger.warning(f"Could not set icon: {e}")

        # Zentrieren
        root.update_idletasks()
        x = (root.winfo_screenwidth() - 600) // 2
        y = (root.winfo_screenheight() - 180) // 2
        root.geometry(f"600x180+{x}+{y}")

        state = {"saved": False, "cancelled": False}

        path_var = ctk.StringVar(value=current_path if current_path else EXAMPLE_PATH)

        # UI-Elemente
        ctk.CTkLabel(
            root,
            text=LanguageManager.get('select_sky_exe_instruction'),
            font=("Arial", 14),
        ).pack(pady=10)

        frame = ctk.CTkFrame(root)
        frame.pack(pady=10, padx=20, fill="x")

        entry = ctk.CTkEntry(
            frame,
            textvariable=path_var,
            state='readonly',
            width=1,
        )
        entry.pack(side="left", fill="x", expand=True, padx=(5, 0))

        ctk.CTkButton(
            frame, text="...", width=30,
            command=lambda: SkyChecker._browse_file(path_var),
        ).pack(side="left", padx=(5, 5))

        # Buttons
        btn_frame = ctk.CTkFrame(root, fg_color="transparent")
        btn_frame.pack(pady=10)

        ctk.CTkButton(
            btn_frame,
            text=LanguageManager.get('save_button_text'),
            command=lambda: SkyChecker._save_and_close(root, path_var, state),
        ).pack(side="left", padx=10)

        # Schließen-Handler
        def on_close():
            state["cancelled"] = True
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_close)
        root.bind('<Return>', lambda e: SkyChecker._save_and_close(root, path_var, state))
        root.bind('<Escape>', lambda e: on_close())

        try:
            root.grab_set()
        except Exception:
            pass

        root.mainloop()

        # Nach Schließen: Prüfen ob gültig gespeichert
        if not state["saved"]:
            logger.critical("User closed Sky.exe dialog without saving valid path")
            messagebox.showerror(
                LanguageManager.get('error_title'),
                LanguageManager.get('exe_path_required_exit'),
            )
            sys.exit(1)

    # ==================== Hilfsmethoden ====================

    @staticmethod
    def _is_valid_sky_path(path: str) -> bool:
        """Prüft ob der Pfad gültig ist (existiert und ist Sky.exe)."""
        if not path:
            return False
        try:
            p = Path(path)
            return (
                p.exists()
                and p.is_file()
                and p.name.lower() == "sky.exe"
            )
        except (OSError, ValueError):
            return False

    @staticmethod
    def _browse_file(path_var: ctk.StringVar):
        """Öffnet Datei-Dialog zur Auswahl der Sky.exe."""
        # Steam-Pfad suchen
        initial_dir = None
        for candidate in STEAM_SEARCH_PATHS:
            if candidate.exists():
                initial_dir = str(candidate)
                break

        # Fallback: Aktueller Pfad-Wert
        if initial_dir is None:
            current = path_var.get().strip()
            if current and current != EXAMPLE_PATH:
                parent = Path(current).parent
                if parent.exists():
                    initial_dir = str(parent)

        try:
            file = filedialog.askopenfilename(
                title=LanguageManager.get('select_sky_exe'),
                initialdir=initial_dir,
                filetypes=[
                    ("Sky Executable", "Sky.exe"),
                    ("All files", "*.*"),
                ],
            )
        except Exception as e:
            logger.error(f"File dialog failed: {e}")
            return

        if file:
            path_var.set(file)

    @staticmethod
    def _save_and_close(root: ctk.CTk, path_var: ctk.StringVar, state: dict):
        """Validiert und speichert den Pfad."""
        exe_path = path_var.get().strip()

        # Validierung 1: Nicht leer / nicht Beispiel
        if not exe_path or exe_path == EXAMPLE_PATH:
            messagebox.showwarning(
                LanguageManager.get('warning_title'),
                LanguageManager.get('exe_path_required'),
            )
            return

        # Validierung 2: Endet mit Sky.exe
        if not exe_path.lower().endswith("sky.exe"):
            messagebox.showwarning(
                LanguageManager.get('warning_title'),
                LanguageManager.get('must_select_sky'),
            )
            return

        # Validierung 3: Existiert und ist Datei
        try:
            p = Path(exe_path)
            if not (p.exists() and p.is_file()):
                messagebox.showwarning(
                    LanguageManager.get('warning_title'),
                    LanguageManager.get('exe_path_invalid'),
                )
                return
        except (OSError, ValueError) as e:
            logger.error(f"Path validation failed for '{exe_path}': {e}")
            messagebox.showwarning(
                LanguageManager.get('warning_title'),
                LanguageManager.get('exe_path_invalid'),
            )
            return

        # Speichern
        success = ConfigManager.save({
            "game_settings": {"sky_exe_path": exe_path}
        })

        if not success:
            logger.error(f"Failed to save Sky.exe path: {exe_path}")
            messagebox.showerror(
                LanguageManager.get('error_title'),
                LanguageManager.get('settings_save_error'),
            )
            return

        logger.info(f"Sky.exe path saved: {exe_path}")
        state["saved"] = True
        root.destroy()