# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import logging, sys, os
import customtkinter as ctk
from tkinter import messagebox, filedialog
from pathlib import Path
from config_manager import ConfigManager
from language_manager import LanguageManager
from resource_loader import resource_path

logger = logging.getLogger("ProjectLyrica.skychecker")

class SkyChecker:
    @staticmethod
    def show_initial_settings():
        # Check if path already exists and is valid
        current_path = ConfigManager.get_value("game_settings.sky_exe_path", "")
        if current_path and os.path.exists(current_path) and current_path.endswith("Sky.exe"):
            return

        root = ctk.CTk()
        root.title(LanguageManager.get('window_settings_title'))
        root.geometry("600x150")
        root.iconbitmap(resource_path("resources/icons/icon.ico"))

        saved = False
        example_path = "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sky Children of the Light\\Sky.exe"
        
        def on_close():
            nonlocal saved
            current_value = path_var.get().strip()
            if not saved and current_value and current_value != example_path:
                messagebox.showerror(
                    LanguageManager.get('error_title'),
                    LanguageManager.get('exe_path_required_exit')
                )
                sys.exit(1)
            root.destroy()
        
        root.protocol("WM_DELETE_WINDOW", on_close)
        
        ctk.CTkLabel(root, 
                    text=LanguageManager.get('select_sky_exe_instruction'),
                    font=("Arial", 14)).pack(pady=10)

        path_var = ctk.StringVar(value=current_path if current_path else example_path)
        
        def browse_file():
            initial_dir = Path("C:/Program Files (x86)/Steam/steamapps/common")
            if not initial_dir.exists():
                initial_dir = None
            
            file = filedialog.askopenfilename(
                title=LanguageManager.get('select_sky_exe'),
                initialdir=initial_dir,
                filetypes=[("Sky Executable", "Sky.exe")]
            )
            if file:
                path_var.set(file)
        
        frame = ctk.CTkFrame(root)
        frame.pack(pady=10, padx=20, fill="x")
        
        entry_frame = ctk.CTkFrame(frame)
        entry_frame.pack(side="left", fill="x", expand=True)
        
        entry = ctk.CTkEntry(entry_frame, 
                           textvariable=path_var, 
                           state='readonly',
                           width=1)
        entry.pack(side="left", fill="x", expand=True, padx=5)
        
        browse_btn = ctk.CTkButton(frame, text="...", width=30, command=browse_file)
        browse_btn.pack(side="left")
        
        def save_and_continue():
            nonlocal saved
            exe_path = path_var.get().strip()
            
            if not exe_path or exe_path == example_path:
                messagebox.showwarning(
                    LanguageManager.get('warning_title'),
                    LanguageManager.get('exe_path_required')
                )
                return
            
            if not exe_path.lower().endswith("sky.exe"):
                messagebox.showwarning(
                    LanguageManager.get('warning_title'),
                    LanguageManager.get('must_select_sky')
                )
                return
            
            if not os.path.exists(exe_path):
                messagebox.showwarning(
                    LanguageManager.get('warning_title'),
                    LanguageManager.get('exe_path_invalid')
                )
                return
            
            ConfigManager.save({
                "game_settings": {
                    "sky_exe_path": exe_path
                }
            })
            
            saved = True
            root.destroy()
        
        btn_frame = ctk.CTkFrame(root, fg_color="transparent")
        btn_frame.pack(pady=10)
        
        ctk.CTkButton(btn_frame, 
                     text=LanguageManager.get('save_button_text'),
                     command=save_and_continue).pack(side="left", padx=10)
        
        root.grab_set()
        root.mainloop()
        
        # Final validation after window closes
        final_path = path_var.get().strip()
        if not saved and (not final_path or final_path == example_path):
            messagebox.showerror(
                LanguageManager.get('error_title'),
                LanguageManager.get('exe_path_required_exit')
            )
            sys.exit(1)