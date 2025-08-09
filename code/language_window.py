# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import logging
import customtkinter as ctk
from tkinter import messagebox
from language_manager import LanguageManager

logger = logging.getLogger("ProjectLyrica.LanguageWindow")

class LanguageWindow:
    _open = False

    @classmethod
    def show(cls):
        if cls._open: 
            logger.debug("Language window already open, skipping")
            return
            
        logger.info("Opening language selection window")
        cls._open = True
        try:
            root = ctk.CTk()
            root.title(LanguageManager.get('language_window_title'))
            root.geometry("400x200")
            root.iconbitmap("resources/icons/icon.ico")
            
            languages = LanguageManager.get_languages()
            if not languages:
                logger.error("No languages available from LanguageManager")
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
                logger.debug(f"Language selected: {selected_name}")
                if code := lang_dict.get(selected_name):
                    logger.info(f"Setting language to: {code}")
                    LanguageManager.set_language(code)
                    messagebox.showinfo("Info", LanguageManager.get('language_saved'))
                else:
                    logger.warning(f"Unknown language selected: {selected_name}")
                root.destroy()
                
            ctk.CTkButton(root, 
                         text=LanguageManager.get('save_button_text'), 
                         command=save).pack(pady=20)
            
            try:
                root.mainloop()
            except Exception as e:
                logger.critical(f"Language window crashed: {e}", exc_info=True)
                raise
            finally:
                cls._open = False
                
        except Exception as e:
            logger.error(f"Failed to initialize language window: {e}", exc_info=True)
            cls._open = False
            raise