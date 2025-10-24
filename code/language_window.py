# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import logging
import customtkinter as ctk
from tkinter import messagebox
from language_manager import LanguageManager
from resource_loader import resource_path

logger = logging.getLogger("ProjectLyrica.LanguageWindow")

class LanguageWindow:
    _open = False

    @classmethod
    def show(cls):
        if cls._open: 
            logger.debug("Language window already open, skipping")
            return
            
        cls._open = True
        
        root = ctk.CTk()
        root.title(LanguageManager.get('language_window_title'))
        root.geometry("400x200")
        root.iconbitmap(resource_path("resources/icons/icon.ico"))
        
        languages = LanguageManager.get_languages()
        if not languages:
            messagebox.showerror("Error", "No languages configured")
            cls._open = False
            return

        lang_dict = {name: code for code, name, _ in languages}
        default_name = next(
            (n for c, n, _ in languages if c == LanguageManager._current_lang),
            languages[0][1]
        )
        
        ctk.CTkLabel(root, 
                     text=LanguageManager.get('select_language'), 
                     font=("Arial", 14)).pack(pady=10)
        
        combo = ctk.CTkComboBox(root, 
                              values=list(lang_dict.keys()), 
                              state="readonly")
        combo.set(default_name)
        combo.pack(pady=10)
        
        def save():
            selected_name = combo.get()
            if code := lang_dict.get(selected_name):
                LanguageManager.set_language(code)
                messagebox.showinfo("Info", LanguageManager.get('language_saved'))
            root.destroy()
            
        ctk.CTkButton(root, 
                     text=LanguageManager.get('save_button_text'), 
                     command=save).pack(pady=20)
        
        root.mainloop()
        cls._open = False