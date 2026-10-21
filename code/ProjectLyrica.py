# Copyright (C) 2025-2026 VanilleIce
# All rights reserved.
#
# Project Lyrica is proprietary software.
# Commercial use, redistribution, and modification are prohibited.
# See LICENSE.md for details.

import ctypes
import logging
import os
import sys
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from threading import Thread
from tkinter import filedialog, messagebox

# =============================================================================
if __name__ == "__main__":
    try:
        if getattr(sys, 'frozen', False):
            # PyInstaller-EXE: cwd = Ordner, in dem die EXE liegt
            # (NICHT _MEIPASS / __file__, das ist der Temp-Entpackordner)
            os.chdir(Path(sys.executable).parent)
        else:
            # Entwicklungsmodus: cwd = Ordner des Scripts
            os.chdir(Path(__file__).resolve().parent)
    except Exception:
        pass
# =============================================================================

import customtkinter as ctk
import winsound
from pynput.keyboard import Listener

from config_manager import ConfigManager
from language_manager import LanguageManager
from language_window import LanguageWindow
from logging_setup import setup_logging
from music_player import MusicPlayer
from resource_loader import resource_path
from sky_checker import SkyChecker
from update_checker import (
    STATUS_CURRENT,
    STATUS_NO_CONNECTION,
    STATUS_UPDATE,
    check_update,
)

logger = logging.getLogger("ProjectLyrica.ProjectLyrica")

# ==================== Konstanten ====================

VERSION = "2.8.0"

# Fenster-Größen
DEFAULT_WINDOW_SIZE = (360, 365)
EXPANDED_SIZE = (360, 470)
FULL_SIZE = (360, 545)
WINDOW_WIDTH = 360

# Zusätzliche Höhe für Hint-Zeile
HINT_FRAME_EXTRA_HEIGHT = 25

# Button-Breite (einheitlich)
OPTION_BUTTON_WIDTH = 220

# Card-Style für Option-Buttons
CARD_STYLE = {
    "fg_color": "transparent",
    "border_width": 0,
    "border_color": ("gray75", "gray35"),
    "corner_radius": 10,
}
CARD_PADY = 3

# Speed-Grenzen
MIN_SPEED = 100
MAX_SPEED = 1500
DEFAULT_SPEED = 1000

# Sky-Check Intervalle (Millisekunden)
SKY_CHECK_START_DELAY = 15000
SKY_CHECK_INTERVAL_ACTIVE = 15000
SKY_CHECK_INTERVAL_INACTIVE = 4000

# GitHub
GITHUB_REPO = "VanilleIce/ProjectLyrica"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"

# Song-Datei Filter
SONG_FILE_TYPES = "*.json *.txt *.skysheet"

# Timings
PLAYBACK_STOP_DELAY = 0.3

# Theme-Hintergrundfarben für tk-Widgets
THEME_BG_DARK = "#242424"
THEME_BG_LIGHT = "#EBEBEB"


# ==================== Tooltip-Klasse ====================

class CTkTooltip:
    """Tooltip für Widgets. Zeigt Text bei Hover."""

    def __init__(self, widget, text, delay=300):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tooltip = None
        self._after_id = None

        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")

    def _on_enter(self, event=None):
        if self._after_id or self.tooltip:
            return
        self._after_id = self.widget.after(self.delay, self._show)

    def _on_leave(self, event=None):
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self._hide()

    def _show(self):
        if self.tooltip:
            return

        try:
            x = self.widget.winfo_rootx() - 250
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 30

            self.tooltip = ctk.CTkToplevel(self.widget)
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.wm_geometry(f"+{max(10, x)}+{y}")
            self.tooltip.attributes("-topmost", True)

            tooltip_bg = ("gray90", "gray20")
            transparent_color = "#010203"
            try:
                self.tooltip.configure(fg_color=transparent_color)
                self.tooltip.wm_attributes("-transparentcolor", transparent_color)
            except Exception:
                try:
                    self.tooltip.configure(fg_color=tooltip_bg)
                except Exception:
                    pass

            tooltip_frame = ctk.CTkFrame(
                self.tooltip,
                fg_color=tooltip_bg,
                corner_radius=8,
            )
            tooltip_frame.pack(padx=0, pady=0)

            label = ctk.CTkLabel(
                tooltip_frame,
                text=self.text,
                font=("Arial", 11),
                fg_color="transparent",
                text_color=("#000000", "#FFFFFF"),
                wraplength=280,
                justify="left",
            )
            label.pack(padx=12, pady=8)
        except Exception as e:
            logger.debug(f"Could not show tooltip: {e}")
            self.tooltip = None

    def _hide(self):
        if self.tooltip:
            try:
                self.tooltip.destroy()
            except Exception:
                pass
            self.tooltip = None


# ==================== Hauptklasse ====================

class MusicApp:
    """Hauptanwendung - verwaltet UI, Playback und Sky-Erkennung."""

    def __init__(self):
        setup_logging(VERSION)
        self._check_running()

        self.config = ConfigManager.get_config()

        custom_was_missing, _ = ConfigManager.check_and_handle_missing_custom()
        if custom_was_missing:
            self.config = ConfigManager.get_config()

        self._previous_sky_running = False
        self._playback_was_paused_before_sky_exit = False
        self._originally_paused_file: str = None
        self._paused_speed: float = None
        self._last_sky_check = 0.0
        self._sky_running_cache = False

        self._init_language()

        if not ConfigManager.get_value("game_settings.sky_exe_path"):
            SkyChecker.show_initial_settings()
            self.config = ConfigManager.get_config()

        self._init_player()

        self.config = ConfigManager.get_config()

        self._init_gui()

        self.speed_changed_by_preset = False
        self.last_speed_before_disable = DEFAULT_SPEED
        self.song_speeds: dict = {}
        self.original_bpm_button = None

        self.root.after(SKY_CHECK_START_DELAY, self._start_sky_check)
        self._setup_key_listener()

        ConfigManager.log_system_info(VERSION)

    # ==================== Properties ====================

    @property
    def current_song_name(self) -> str:
        if not self.selected_file:
            return "No song"
        return self._truncate_filename(self.selected_file, 35)

    # ==================== Initialisierung ====================

    def _check_running(self):
        try:
            self._mutex = ctypes.windll.kernel32.CreateMutexW(
                None, False, "ProjectLyricaMutex"
            )
            if ctypes.windll.kernel32.GetLastError() == 183:
                messagebox.showerror("Error", "Application is already running!")
                sys.exit(1)
        except Exception as e:
            logger.warning(f"Could not create mutex: {e}")
            self._mutex = None

    def _init_language(self):
        LanguageManager.init()
        ui_language = self.config.get("ui_settings", {}).get("selected_language")

        if not ui_language:
            LanguageWindow.show()
            self.config = ConfigManager.get_config()

    def _init_player(self):
        self.player = MusicPlayer(self.config)
        self.selected_file: str = None

        playback_settings = self.config.get("playback_settings", {})
        ui_settings = self.config.get("ui_settings", {})

        self.duration_presets = (
            playback_settings.get("key_press_durations")
            or [0.2, 0.248, 0.3, 0.5, 1.0]
        )
        self.speed_presets = (
            playback_settings.get("speed_presets")
            or [600, 800, 1000, 1200]
        )
        self.pause_key = ui_settings.get("pause_key", "#")
        self.reset_speed_key = ui_settings.get("reset_speed_key", "+")

        self.speed_change_config = self.config.get("speed_change_settings", {})

        self.keypress_enabled = False
        self.speed_enabled = False
        self.current_speed_value = DEFAULT_SPEED
        self.player.current_speed = DEFAULT_SPEED

        self.smooth_ramping_enabled = playback_settings.get("enable_ramping", False)

    def _reload_player_key_mapping(self):
        """Lädt Key-Mapping neu (nach Custom-Layout-Änderung)."""
        try:
            self.config = ConfigManager.get_config()
            self.player._initialize_key_mapping(self.config)
            logger.info(f"Reloaded key mapping ({len(self.player.key_map)} keys)")
        except Exception as e:
            logger.error(f"Could not reload key mapping: {e}")

    def _setup_key_listener(self):
        try:
            self.key_listener = Listener(on_press=self._handle_keypress)
            self.key_listener.start()
            logger.info("Key listener started")
        except Exception as e:
            logger.error(f"Could not start key listener: {e}")
            self.key_listener = None

    # ==================== GUI Initialisierung ====================

    def _init_gui(self):
        self.root = ctk.CTk()
        self.root.title(LanguageManager.get("project_title"))
        self.root.protocol('WM_DELETE_WINDOW', self._shutdown)
        self.root.resizable(False, False)

        icon_path = resource_path("resources/icons/icon.ico")
        if Path(icon_path).exists():
            try:
                self.root.iconbitmap(icon_path)
            except Exception as e:
                logger.warning(f"Could not set icon: {e}")

        theme = self.config.get("ui_settings", {}).get("theme", "dark")
        ctk.set_appearance_mode(theme)

        self.current_play_state = "disabled"

        self.update_status = "checking"
        self.latest_version = ""
        self.update_url = ""
        Thread(target=self._check_updates_async, daemon=True).start()

        self._create_gui_components()
        self._setup_gui_layout()

        self._update_play_button_state("no_sky")
        self._update_file_dependent_buttons()

    def _check_updates_async(self):
        try:
            status, version, url = check_update(VERSION, GITHUB_REPO)
        except Exception as e:
            logger.error(f"Update check failed: {e}")
            status, version, url = ("error", "", "")

        self.update_status = status
        self.latest_version = version
        self.update_url = url

        try:
            self.root.after(0, self._apply_update_status)
        except Exception:
            pass

    def _apply_update_status(self):
        if not hasattr(self, 'version_link'):
            return

        if self.update_status == STATUS_UPDATE:
            text = LanguageManager.get('update_available_text').format(self.latest_version)
            color = "#FFA500"
        elif self.update_status == STATUS_NO_CONNECTION:
            text = LanguageManager.get('no_connection_text')
            color = "#FF0000"
        else:
            text = LanguageManager.get('current_version_text').format(VERSION)
            color = "#1E90FF"

        try:
            self.version_link.configure(text=text, text_color=color)
        except Exception:
            pass

    def _create_button(self, text, command, width=200, height=30, main=False):
        return ctk.CTkButton(
            self.root,
            text=text,
            command=command,
            font=("Arial", 14 if main else 13),
            width=width,
            height=height,
        )

    def _create_gui_components(self):
        self.file_btn = self._create_button(
            LanguageManager.get("file_select_title"),
            self._select_file, 280, 40, True,
        )

        self.hint_frame = ctk.CTkFrame(
            self.root,
            fg_color=("gray92", "gray14"),
            border_width=1,
            border_color=("gray75", "gray30"),
            corner_radius=8,
        )

        self.file_hint_label = ctk.CTkLabel(
            self.hint_frame,
            text=LanguageManager.get('file_hint_no_file'),
            font=("Arial", 13, "bold"),
            text_color=("#000000", "#FFFFFF"),
        )
        self.file_hint_label.pack(pady=8, padx=15)

        # --- Card 1: Keypress ---
        self.keypress_card = ctk.CTkFrame(self.root, **CARD_STYLE)

        self.keypress_btn = ctk.CTkButton(
            self.keypress_card,
            text=f"{LanguageManager.get('key_press')}: {LanguageManager.get('disabled')}",
            command=self._toggle_keypress,
            font=("Arial", 13),
            width=OPTION_BUTTON_WIDTH,
            height=32,
        )
        self.keypress_btn.pack(pady=5, padx=10)

        # --- Card 2: Speed ---
        self.speed_card = ctk.CTkFrame(self.root, **CARD_STYLE)

        speed_text = (
            f"{LanguageManager.get('speed_control')}: "
            f"{LanguageManager.get('disabled')}"
        )
        self.speed_btn = ctk.CTkButton(
            self.speed_card,
            text=speed_text,
            command=self._toggle_speed,
            font=("Arial", 13),
            width=OPTION_BUTTON_WIDTH,
            height=32,
        )
        self.speed_btn.pack(pady=5, padx=10)

        # --- Card 3: Ramping ---
        self.ramping_card = ctk.CTkFrame(self.root, **CARD_STYLE)

        ramping_status = "enabled" if self.smooth_ramping_enabled else "disabled"
        self.ramping_btn = ctk.CTkButton(
            self.ramping_card,
            text=f"{LanguageManager.get('smooth_ramping')}: {LanguageManager.get(ramping_status)}",
            command=self._toggle_smooth_ramping,
            font=("Arial", 13),
            width=OPTION_BUTTON_WIDTH,
            height=32,
        )
        self.ramping_btn.pack(pady=5, padx=10)

        # ?-Label ÜBER dem Button (mit place() im ramping_card)
        try:
            from customtkinter import ThemeManager
            bg_color = ThemeManager.single_color(
                self.root.cget("fg_color"),
                ctk.get_appearance_mode()
            )
        except Exception:
            theme = self.config.get("ui_settings", {}).get("theme", "dark")
            bg_color = THEME_BG_DARK if theme == "dark" else THEME_BG_LIGHT

        self.info_btn = tk.Label(
            self.ramping_card,
            text="?",
            font=("Arial", 10, "bold"),
            fg="gray50",
            bg=bg_color,
            bd=0,
            highlightthickness=0,
            highlightbackground=bg_color,
            highlightcolor=bg_color,
            padx=0,
            pady=0,
            cursor="hand2",
        )
        self.info_btn.place(relx=1.0, rely=0.0, x=-2, y=7, anchor="ne")

        self._ramping_tooltip = CTkTooltip(
            self.info_btn,
            LanguageManager.get('smooth_ramping_info'),
            delay=300,
        )

        self.play_btn = self._create_button(
            LanguageManager.get("play_button_text"),
            None, 200, 40, True,
        )

        self._create_duration_controls()
        self._create_speed_controls()

    def _create_duration_controls(self):
        self.duration_frame = ctk.CTkFrame(self.keypress_card, fg_color="transparent")

        self.slider_wrapper = ctk.CTkFrame(
            self.duration_frame,
            fg_color=("gray88", "gray18"),
            corner_radius=6,
        )
        self.slider_wrapper.pack(pady=5, padx=10, fill="x")

        self.duration_slider = ctk.CTkSlider(
            self.slider_wrapper, from_=0.1, to=1.0,
            number_of_steps=90, width=100,
        )
        self.duration_slider.set(0.1)
        self.duration_slider.bind("<B1-Motion>", self._set_duration)
        self.duration_slider.bind("<ButtonRelease-1>", self._set_duration)
        self.duration_slider.pack(pady=5, padx=8, fill="x")

        self.duration_label = ctk.CTkLabel(
            self.duration_frame,
            text=f"{LanguageManager.get('duration')} 0.1 s",
            font=("Arial", 12),
        )

        self.preset_frame = ctk.CTkFrame(self.duration_frame)
        self._update_duration_preset_buttons()

    def _create_speed_controls(self):
        self.speed_frame = ctk.CTkFrame(self.speed_card, fg_color="transparent")

        self.original_bpm_frame = ctk.CTkFrame(
            self.speed_frame, fg_color="transparent"
        )
        self.original_bpm_frame.pack(pady=(5, 5))

        self.speed_preset_frame = ctk.CTkFrame(self.speed_frame)
        self._update_speed_preset_buttons()

    # ==================== UI Update Methoden ====================

    def _update_original_bpm_button(self, file_path: str = None):
        try:
            for widget in self.original_bpm_frame.winfo_children():
                widget.destroy()

            if not file_path:
                file_path = self.selected_file

            if not file_path:
                self.original_bpm_button = None
                return

            try:
                song_data = self.player.parse_song(file_path)
                bpm = song_data.get('bpm')
                bpm_value = int(float(bpm)) if bpm is not None else DEFAULT_SPEED
            except Exception:
                bpm_value = DEFAULT_SPEED

            self.original_bpm_button = ctk.CTkButton(
                self.original_bpm_frame,
                text=f"Original: {bpm_value}",
                width=100, height=28,
                font=("Arial", 12, "bold"),
                fg_color="#4CAF50",
                hover_color="#45a049",
                command=self._reset_to_original_speed,
            )
            self.original_bpm_button.pack()

        except Exception as e:
            logger.error(f"Could not update original BPM button: {e}")

    def _update_file_dependent_buttons(self):
        has_file = bool(self.selected_file)
        sky_running = self._check_sky_running()

        try:
            self.file_btn.configure(state="normal" if sky_running else "disabled")
        except Exception as e:
            logger.debug(f"Could not update file button state: {e}")

        options_ready = has_file and sky_running
        options_state = "normal" if options_ready else "disabled"

        for btn in (self.keypress_btn, self.speed_btn, self.ramping_btn):
            try:
                btn.configure(state=options_state)
            except Exception as e:
                logger.debug(f"Could not update button state: {e}")

        show_hint = sky_running and not has_file

        try:
            if show_hint:
                self.file_hint_label.configure(
                    text=LanguageManager.get('file_hint_no_file')
                )
                self.hint_frame.pack(
                    pady=(0, 7), padx=20,
                    before=self.keypress_card,
                )
            else:
                self.hint_frame.pack_forget()
        except Exception as e:
            logger.debug(f"Could not update hint: {e}")

        self._adjust_window_size()

    def _update_play_button_state(self, state: str = None):
        if state is None:
            sky_running = self._check_sky_running(use_cache=False)
            has_file = bool(self.selected_file)
            is_paused = self.player.playback.active and self.player.pause_flag.is_set()
            is_playing = (
                self.player.playback.active
                and not self.player.pause_flag.is_set()
            )

            if not sky_running:
                new_state = "no_sky"
            elif not has_file:
                new_state = "no_file"
            elif is_playing:
                new_state = "playing"
            elif is_paused:
                new_state = "paused"
            else:
                new_state = "ready"
        else:
            new_state = state

        if new_state == self.current_play_state:
            if new_state == "paused":
                config = self._get_state_config(new_state)
                if self.play_btn.cget("text") != config.get("text", ""):
                    self.play_btn.configure(**config)
            return

        self.current_play_state = new_state
        config = self._get_state_config(new_state)
        try:
            self.play_btn.configure(**config)
        except Exception as e:
            logger.error(f"Could not configure play button: {e}")

        logger.debug(f"Button state changed to: {new_state}")

    def _get_state_config(self, state: str) -> dict:
        configs = {
            "no_sky": {
                "text": LanguageManager.get("sky_only_warning"),
                "command": None,
                "fg_color": "#666666",
                "hover_color": "#666666",
                "text_color": "#aaaaaa",
                "state": "disabled",
                "height": 40,
            },
            "no_file": {
                "text": LanguageManager.get("play_button_text"),
                "command": None,
                "fg_color": "#666666",
                "hover_color": "#666666",
                "text_color": "#aaaaaa",
                "state": "disabled",
                "height": 40,
            },
            "playing": {
                "text": LanguageManager.get("playing_button_text"),
                "command": None,
                "fg_color": "#666666",
                "hover_color": "#666666",
                "text_color": "#ffffff",
                "state": "disabled",
                "height": 40,
            },
            "ready": {
                "text": LanguageManager.get("play_button_text"),
                "command": self._play_song,
                "fg_color": "#2b6cb0",
                "hover_color": "#1f538d",
                "text_color": "#ffffff",
                "state": "normal",
                "height": 40,
            },
        }

        if state == "paused":
            return self._get_paused_button_config()

        return configs.get(state, configs["no_file"])

    def _get_paused_button_config(self) -> dict:
        has_different_file = (
            self._originally_paused_file is not None
            and self.selected_file is not None
            and self._originally_paused_file != self.selected_file
        )

        pause_hint = LanguageManager.get("pause_key_hint").replace(
            "[pause_key]", self.pause_key
        )

        if has_different_file:
            return {
                "text": f"{LanguageManager.get('play_button_text')}\n{pause_hint}",
                "command": self._play_song,
                "fg_color": "#8B4B8B",
                "hover_color": "#6A3A6A",
                "text_color": "#ffffff",
                "state": "normal",
                "height": 50,
            }
        else:
            return {
                "text": f"{LanguageManager.get('restart_button_text')}\n{pause_hint}",
                "command": self._play_song,
                "fg_color": "#D2691E",
                "hover_color": "#A0522D",
                "text_color": "#ffffff",
                "state": "normal",
                "height": 50,
            }

    def _update_speed_preset_buttons(self):
        if not (
            hasattr(self, 'speed_preset_frame')
            and self.speed_preset_frame.winfo_exists()
        ):
            return

        for widget in self.speed_preset_frame.winfo_children():
            widget.destroy()

        if not self.speed_presets:
            return

        for speed in self.speed_presets:
            if speed <= 0:
                continue
            ctk.CTkButton(
                self.speed_preset_frame,
                text=str(speed),
                width=45, height=28,
                font=("Arial", 12),
                command=lambda s=speed: self._apply_speed_change(s, "preset"),
            ).pack(side="left", padx=2)

    def _update_duration_preset_buttons(self):
        if not (
            hasattr(self, 'preset_frame')
            and self.preset_frame.winfo_exists()
        ):
            return

        for widget in self.preset_frame.winfo_children():
            widget.destroy()

        if not self.duration_presets:
            return

        for preset in self.duration_presets:
            ctk.CTkButton(
                self.preset_frame,
                text=f"{preset} s",
                width=50,
                command=lambda p=preset: self._apply_preset(p),
            ).pack(side="left", padx=2)

    def _update_speed_ui_visibility(self):
        if self.speed_enabled:
            self.speed_card.configure(border_width=1)
            self.speed_frame.pack(pady=(0, 8), padx=10)
            self.speed_preset_frame.pack(pady=(5, 8))
            logger.info("Speed Control: expanded")
        else:
            self.speed_frame.pack_forget()
            self.speed_card.configure(border_width=0)
            logger.info("Speed Control: collapsed")

        self._adjust_window_size()

    def _update_speed_display(self, new_speed: float):
        self.current_speed_value = new_speed

        if not self.selected_file:
            text = (
                f"{LanguageManager.get('speed_control')}: "
                f"{LanguageManager.get('disabled')}"
            )
        else:
            text = f"{LanguageManager.get('speed_control')}: {int(new_speed)}"

        try:
            self.speed_btn.configure(text=text)
        except Exception:
            pass

    # ==================== Sky Management ====================

    def _check_sky_running(self, use_cache: bool = True) -> bool:
        current_time = time.time()

        if use_cache and current_time - self._last_sky_check < 2.0:
            return self._sky_running_cache

        if not hasattr(self, 'player') or self.player is None:
            return False

        try:
            result = self.player.is_sky_running()
        except Exception:
            result = False

        self._sky_running_cache = result
        self._last_sky_check = current_time
        return result

    def _start_sky_check(self):
        def check_sky():
            try:
                sky_running = self._check_sky_running()
                previous = self._previous_sky_running

                if previous != sky_running:
                    logger.info(f"Sky state changed: {previous} -> {sky_running}")
                    self._previous_sky_running = sky_running
                    self._update_play_button_state()
                    self._update_file_dependent_buttons()
            except Exception as e:
                logger.error(f"Sky check error: {e}")
                sky_running = self._previous_sky_running

            if sky_running:
                next_interval = SKY_CHECK_INTERVAL_ACTIVE
            else:
                next_interval = SKY_CHECK_INTERVAL_INACTIVE

            try:
                self.root.after(next_interval, check_sky)
            except Exception:
                pass

        self._previous_sky_running = self._check_sky_running()
        logger.info(f"Initial Sky state: {self._previous_sky_running}")
        self._update_play_button_state()
        self._update_file_dependent_buttons()

        next_interval = (
            SKY_CHECK_INTERVAL_ACTIVE
            if self._previous_sky_running
            else SKY_CHECK_INTERVAL_INACTIVE
        )
        try:
            self.root.after(next_interval, check_sky)
        except Exception:
            pass

    def _focus_sky_window(self, song_name: str = None) -> bool:
        if not song_name:
            song_name = self.current_song_name

        for attempt in range(2):
            try:
                window = self.player.window_manager.find_window()
                if window and self.player.window_manager.focus_window(window):
                    logger.info("Sky window focused")
                    return True
            except Exception:
                pass
            time.sleep(0.2)

        logger.error("Cannot focus Sky window")
        return False

    # ==================== Geschwindigkeit ====================

    def _validate_and_clamp_speed(self, speed, show_warnings: bool = True):
        try:
            speed = float(speed)
        except (ValueError, TypeError):
            if show_warnings:
                msg = LanguageManager.get('invalid_speed_number')
                if msg == '[invalid_speed_number]':
                    msg = "Speed must be a valid number"
                messagebox.showerror(LanguageManager.get('error_title'), msg)
            return None

        if speed <= 0:
            if show_warnings:
                messagebox.showerror(
                    LanguageManager.get('error_title'),
                    LanguageManager.get("invalid_speed"),
                )
            return None

        if speed < MIN_SPEED:
            if show_warnings:
                messagebox.showwarning(
                    LanguageManager.get('warning_title'),
                    LanguageManager.get('speed_too_slow').format(
                        min_speed=MIN_SPEED, min_speed_again=MIN_SPEED,
                    ),
                )
            speed = MIN_SPEED

        if speed > MAX_SPEED:
            if show_warnings:
                messagebox.showwarning(
                    LanguageManager.get('warning_title'),
                    LanguageManager.get('speed_too_fast').format(
                        max_speed=MAX_SPEED, max_speed_again=MAX_SPEED,
                    ),
                )
            speed = MAX_SPEED

        return speed

    def _apply_speed_change(self, target_speed, source: str = "manual") -> bool:
        target_speed = self._validate_and_clamp_speed(target_speed)
        if target_speed is None:
            return False

        old_speed = int(self.current_speed_value)
        target_speed = int(target_speed)

        if abs(old_speed - target_speed) < 1:
            return False

        self.current_speed_value = target_speed
        self.last_speed_before_disable = target_speed
        self.speed_changed_by_preset = True

        try:
            self._update_speed_display(target_speed)
        except Exception:
            pass

        if source == "original":
            logger.info(f"Speed Control: ({old_speed}) → ({target_speed}) [original]")
        else:
            logger.info(f"Speed Control: ({old_speed}) → ({target_speed})")

        if self.player.playback.active:
            if not self.player.pause_flag.is_set():
                self.player._init_speed_ramping(target_speed)
            else:
                self.player.current_speed = target_speed
                self.player.speed_ramping.active = False
                if self.selected_file:
                    self.song_speeds[self.selected_file] = target_speed
        else:
            self.player.current_speed = target_speed

        return True

    def _reset_to_original_speed(self):
        if not self.selected_file:
            return

        try:
            song_data = self.player.parse_song(self.selected_file)
            original_bpm = song_data.get('bpm') or DEFAULT_SPEED
            self._apply_speed_change(float(original_bpm), "original")
        except Exception as e:
            logger.error(f"Error resetting speed: {e}")

    # ==================== Event Handler ====================

    def _handle_keypress(self, key):
        try:
            if not hasattr(self, 'root') or not self.root.winfo_exists():
                return
        except Exception:
            return

        key_char = getattr(key, 'char', None)
        key_name = getattr(key, 'name', None)

        if key_char == self.pause_key:
            self._handle_pause_key()
            return
        elif key_char == self.reset_speed_key:
            self._reset_to_original_speed()
            return

        self._handle_preset_speed_change(key_char, key_name)

    def _handle_pause_key(self):
        logger.info("Pause key pressed")

        if not self._check_sky_running():
            self._update_play_button_state("no_sky")
            return

        if self.player.pause_flag.is_set():
            self._handle_resume()
        elif self.player.playback.active:
            self._handle_pause()

    def _handle_resume(self):
        if not self._originally_paused_file:
            self.player.pause_flag.clear()
            self._update_play_button_state("ready")
            return

        paused_file = self._originally_paused_file
        song_name = self._truncate_filename(paused_file, 35)

        if self.selected_file != paused_file:
            self.selected_file = paused_file
            self.file_btn.configure(text=self._truncate_filename(paused_file))
            self._update_original_bpm_button(paused_file)
            logger.info("Resumed previous song (new song discarded)")

        new_speed = self.current_speed_value
        self.player.current_speed = new_speed

        Thread(
            target=self._focus_sky_window,
            args=(song_name,),
            daemon=True,
        ).start()

        self.player.pause_flag.clear()

        self._update_play_button_state("playing")

        self._originally_paused_file = None
        self._paused_speed = None

        logger.info("Resumed song")

    def _handle_pause(self):
        if not (self.player.playback.active and self.selected_file):
            return

        self._paused_speed = self.player.current_speed
        self.song_speeds[self.selected_file] = self.player.current_speed
        self.player.pause_flag.set()
        self._originally_paused_file = self.selected_file
        self._update_play_button_state("paused")

        logger.info("Paused song")

    def _handle_preset_speed_change(self, key_char, key_name):
        for mapping in self.speed_change_config.get('preset_mappings', []):
            preset_key = mapping.get('key', '')
            preset_speed = mapping.get('speed', 600)

            if (key_char and key_char == preset_key) or (
                key_name and key_name == preset_key
            ):
                self._apply_speed_change(preset_speed, "preset")
                return

    # ==================== Playback ====================

    def _play_thread(self, song_data):
        song_name = self.current_song_name

        if self.player.stop_event.is_set():
            self.player.stop_event.clear()

        logger.info("Focusing Sky window")

        if not self._focus_sky_window(song_name):
            self.player.playback.active = False
            self.root.after(0, lambda: messagebox.showerror(
                LanguageManager.get("error_title"),
                LanguageManager.get("sky_window_focus_error"),
            ))
            self.root.after(0, lambda: self._update_play_button_state("ready"))
            return

        try:
            self.player.play(song_data)
        except Exception as e:
            logger.error(f"Playback failed: {e}")
            self.root.after(0, lambda err=e: messagebox.showerror(
                LanguageManager.get("error_title"),
                f"Playback failed: {err}",
            ))
        finally:
            self.player.playback.active = False

            try:
                winsound.Beep(1000, 500)
            except Exception:
                pass

            self.root.after(0, self._update_play_button_state)
            self._originally_paused_file = None

    def _play_song(self):
        if not self._check_sky_running(use_cache=False):
            self._update_play_button_state("no_sky")
            return

        if not self.selected_file:
            messagebox.showwarning(
                LanguageManager.get('warning_title'),
                LanguageManager.get("choose_song_warning"),
            )
            self._update_play_button_state("no_file")
            return

        is_resuming_same = (
            self._originally_paused_file is not None
            and self.selected_file == self._originally_paused_file
            and self.player.playback.active
            and self.player.pause_flag.is_set()
        )

        if is_resuming_same:
            current_text = self.play_btn.cget("text")
            is_restart = LanguageManager.get("restart_button_text") in current_text

            if is_restart:
                logger.info("Restarting paused song from beginning")
                self._stop_playback()
                self._originally_paused_file = None
                self._start_new_playback()
            else:
                self._handle_resume()
            return

        if self._originally_paused_file is not None:
            old = self._truncate_filename(self._originally_paused_file, 35)
            logger.info(f"Starting new song (discarding paused: {old})")

        self._stop_playback()
        self._start_new_playback()

    def _stop_playback(self):
        if not self.player.playback.active:
            return

        self.player.stop()
        time.sleep(PLAYBACK_STOP_DELAY)
        self.player._release_all()
        self.player.stop_event.clear()

    def _start_new_playback(self):
        if self.selected_file in self.song_speeds:
            playback_speed = self.song_speeds[self.selected_file]
        else:
            playback_speed = self.current_speed_value

        self.song_speeds[self.selected_file] = playback_speed
        self.player.current_speed = playback_speed
        self.player._reset_playback_state()

        try:
            song = self.player.parse_song(self.selected_file)
        except Exception as e:
            logger.error(f"Could not parse song: {e}")
            messagebox.showerror(
                LanguageManager.get('error_title'),
                f"Invalid song: {e}",
            )
            self._update_play_button_state("ready")
            return

        logger.info(f"Starting Song: {self.current_song_name}")

        self.player.playback.active = True

        self._update_play_button_state("playing")
        Thread(target=self._play_thread, args=(song,), daemon=True).start()

    # ==================== Dateiauswahl ====================

    def _get_songs_dir(self) -> Path:
        """Findet den Songs-Ordner.

        Sucht in dieser Reihenfolge:
        1. Neben der EXE (extern, für Release) — Vorrang für Nutzer-Songs
        2. Im _MEIPASS (falls eingepackt)
        3. Über resource_path (sucht im Script-Dir und bis zu 3 Ebenen darüber)
        4. Fallback: CWD
        """
        # 1. Neben der EXE
        if getattr(sys, 'frozen', False):
            exe_dir = Path(sys.executable).parent
            external_songs = exe_dir / "resources" / "Songs"
            if external_songs.exists():
                return external_songs

        # 2. Im _MEIPASS (falls Songs in die EXE eingepackt wurden)
        if hasattr(sys, '_MEIPASS'):
            internal_songs = Path(sys._MEIPASS) / "resources" / "Songs"
            if internal_songs.exists():
                return internal_songs

        # 3. resource_path — sucht im Script-Dir UND in übergeordneten Ordnern
        #    (wichtig für .bat-Start, wo Songs eine Ebene höher liegen)
        songs_dir = Path(resource_path("resources/Songs"))
        if songs_dir.exists():
            return songs_dir

        # 4. Fallback: CWD
        return Path.cwd()

    def _select_file(self):
        logger.info("File manager opened")

        songs_dir = self._get_songs_dir()
        logger.info(f"Opening file dialog at: {songs_dir}")

        file = filedialog.askopenfilename(
            initialdir=str(songs_dir),
            filetypes=[
                (LanguageManager.get("supported_formats"), SONG_FILE_TYPES),
            ],
        )

        if not file:
            logger.info("File manager closed (no selection)")
            self._update_play_button_state()
            return

        previous_file = self.selected_file
        was_paused = self.player.playback.active and self.player.pause_flag.is_set()

        try:
            song_data = self.player.parse_song(file)
            bpm = song_data.get('bpm')

            self.selected_file = file
            self.file_btn.configure(text=self._truncate_filename(file))

            logger.info(f"Selected: {self._get_short_path(file)}")

            if was_paused and previous_file and previous_file != file:
                logger.info("Switched to new song while paused")

            if was_paused and previous_file:
                self.song_speeds[previous_file] = self.current_speed_value

            if bpm is not None:
                bpm_value = float(bpm)
                self.current_speed_value = bpm_value
                self.player.current_speed = bpm_value
                self.speed_changed_by_preset = True
                logger.info(f"BPM: {bpm_value}")
            else:
                messagebox.showwarning(
                    LanguageManager.get('warning_title'),
                    LanguageManager.get('no_bpm_found'),
                )
                self.current_speed_value = DEFAULT_SPEED
                self.player.current_speed = DEFAULT_SPEED
                self.speed_changed_by_preset = True

            self._update_speed_display(self.current_speed_value)
            self._update_original_bpm_button(file)

            self._update_file_dependent_buttons()

            if was_paused:
                self._update_play_button_state("paused")
            else:
                self._update_play_button_state()

        except Exception as e:
            logger.error(f"Invalid song file: {Path(file).name} - {e}")
            messagebox.showerror(
                LanguageManager.get('error_title'),
                f"Invalid song format!\n\n{Path(file).name}\n\n{e}",
            )

            if previous_file:
                self.selected_file = previous_file
                self.file_btn.configure(text=self._truncate_filename(previous_file))
                self._update_play_button_state()
            else:
                self.selected_file = None
                self.file_btn.configure(text=LanguageManager.get("file_select_title"))
                self._update_play_button_state("no_file")

            self._update_file_dependent_buttons()

        logger.info("File manager closed")

    # ==================== UI Actions ====================

    def _set_duration(self, event=None):
        try:
            duration = round(self.duration_slider.get(), 3)
            self.player.press_duration = duration
            self.duration_label.configure(
                text=f"{LanguageManager.get('duration')} {duration} s"
            )
        except Exception:
            pass

    def _apply_preset(self, duration: float):
        try:
            self.player.press_duration = duration
            self.duration_slider.set(duration)
            self.duration_label.configure(
                text=f"{LanguageManager.get('duration')} {duration} s"
            )
            logger.info(f"Keypress preset: {duration}s")
        except Exception:
            pass

    def _toggle_keypress(self):
        if not self.selected_file:
            return

        self.keypress_enabled = not self.keypress_enabled
        status = "enabled" if self.keypress_enabled else "disabled"
        logger.info(f"Keypress: {status}")

        self.keypress_btn.configure(
            text=f"{LanguageManager.get('key_press')}: {LanguageManager.get(status)}"
        )

        if self.keypress_enabled:
            self.keypress_card.configure(border_width=1)
            self.duration_frame.pack(pady=(0, 8), padx=10)
            self.duration_slider.pack(pady=5)
            self.duration_label.pack()
            self.preset_frame.pack(pady=5)
        else:
            self.duration_frame.pack_forget()
            self.keypress_card.configure(border_width=0)
            self.player.press_duration = 0.1

        self._adjust_window_size()

    def _toggle_speed(self):
        if not self.selected_file:
            return

        self.speed_enabled = not self.speed_enabled

        if self.speed_enabled:
            self.player.current_speed = self.current_speed_value
            self._update_original_bpm_button()
        else:
            self.last_speed_before_disable = self.current_speed_value
            self.player.current_speed = DEFAULT_SPEED

        self._update_speed_ui_visibility()
        self._update_speed_display(self.current_speed_value)

    def _toggle_smooth_ramping(self):
        if not self.selected_file:
            return

        self.smooth_ramping_enabled = not self.smooth_ramping_enabled
        status = "enabled" if self.smooth_ramping_enabled else "disabled"
        logger.info(f"Smooth Ramping: {status}")

        self.ramping_btn.configure(
            text=f"{LanguageManager.get('smooth_ramping')}: {LanguageManager.get(status)}"
        )

        self.player.enable_ramping = self.smooth_ramping_enabled

        Thread(
            target=ConfigManager.save,
            args=(
                {
                    "playback_settings": {
                        "enable_ramping": self.smooth_ramping_enabled
                    },
                },
            ),
            daemon=True,
        ).start()

        self._adjust_window_size()

    # ==================== Settings & Callbacks ====================

    def _open_settings(self):
        """Öffnet Einstellungsfenster."""
        from settings_window import SettingsWindow

        SettingsWindow(
            parent=self.root,
            theme_callback=self._on_theme_changed,
            timing_callback=self._on_timing_changed,
            playback_callback=self._on_playback_changed,
            pause_key_callback=self._on_pause_key_changed,
            reset_speed_key_callback=self._on_reset_speed_key_changed,
            speed_change_callback=self._on_speed_change_changed,
            custom_layout_callback=self._reload_player_key_mapping,
        )

    def _on_reset_speed_key_changed(self, new_key: str):
        self.reset_speed_key = new_key
        logger.info(f"Reset speed key: {new_key}")

    def _on_speed_change_changed(self, speed_change_updates):
        self.config = ConfigManager.get_config()
        self.speed_change_config = self.config.get("speed_change_settings", {})

    def _on_pause_key_changed(self, new_pause_key: str):
        self.pause_key = new_pause_key
        if self.current_play_state == "paused":
            self._update_play_button_state("paused")

    def _on_theme_changed(self, new_theme: str):
        from settings_window import SettingsWindow
        if SettingsWindow.is_open():
            for window in SettingsWindow._open_windows[:]:
                try:
                    window._on_close()
                except Exception:
                    pass
            SettingsWindow._open_windows.clear()

        text_color = "#FFFFFF" if new_theme == "dark" else "#000000"
        hover_color = "#2B2B2B" if new_theme == "dark" else "#E0E0E0"

        try:
            self.settings_btn.configure(
                text_color=text_color, hover_color=hover_color
            )
        except Exception:
            pass

        # ?-Label Hintergrundfarbe aktualisieren
        try:
            from customtkinter import ThemeManager
            bg_color = ThemeManager.single_color(
                self.root.cget("fg_color"),
                ctk.get_appearance_mode()
            )
            self.info_btn.configure(
                bg=bg_color,
                highlightbackground=bg_color,
                highlightcolor=bg_color,
            )
        except Exception:
            pass

    def _on_timing_changed(self, timing_updates: dict):
        if not hasattr(self, 'player'):
            return

        if "delays" in timing_updates:
            delays = timing_updates["delays"]
            self.player.initial_delay = delays.get(
                "initial_delay", self.player.initial_delay
            )
            self.player.pause_resume_delay = delays.get(
                "pause_resume_delay", self.player.pause_resume_delay
            )

        if "ramping" in timing_updates:
            ramping = timing_updates["ramping"]
            self.player.ramp_begin_config = ramping.get(
                "begin", self.player.ramp_begin_config
            )
            self.player.ramp_end_config = ramping.get(
                "end", self.player.ramp_end_config
            )
            self.player.ramp_after_pause_config = ramping.get(
                "after_pause", self.player.ramp_after_pause_config
            )

    def _on_playback_changed(self, playback_updates: dict):
        if "speed_presets" in playback_updates:
            self.speed_presets = playback_updates["speed_presets"]
            self._update_speed_preset_buttons()

        if "key_press_durations" in playback_updates:
            self.duration_presets = playback_updates["key_press_durations"]
            self._update_duration_preset_buttons()

    # ==================== Window Layout ====================

    def _setup_gui_layout(self):
        status_frame = ctk.CTkFrame(self.root, height=1, fg_color="transparent")
        status_frame.pack(side="bottom", fill="x", padx=10, pady=2)

        self.version_link = ctk.CTkLabel(
            status_frame,
            text=LanguageManager.get('current_version_text').format(VERSION),
            font=("Arial", 11),
            text_color="#1E90FF",
            cursor="hand2",
        )
        self.version_link.pack(side="right")
        self.version_link.bind("<Button-1>", self._open_releases)

        theme = self.config.get("ui_settings", {}).get("theme", "dark")
        text_color = "#FFFFFF" if theme == "dark" else "#000000"
        hover_color = "#2B2B2B" if theme == "dark" else "#E0E0E0"

        self.settings_btn = ctk.CTkButton(
            status_frame,
            text="⚙️",
            width=8, height=20,
            font=("Arial", 16),
            command=self._open_settings,
            fg_color="transparent",
            border_width=0,
            text_color=text_color,
            hover_color=hover_color,
        )
        self.settings_btn.pack(side="right", padx=(0, 5))

        ctk.CTkLabel(
            self.root,
            text=LanguageManager.get("project_title"),
            font=("Arial", 18, "bold"),
        ).pack(pady=(15, 20))

        self.file_btn.pack(pady=(0, 20))

        self.keypress_card.pack(pady=(0, CARD_PADY))
        self.speed_card.pack(pady=(0, CARD_PADY))
        self.ramping_card.pack(pady=(0, 8))

        self.play_btn.pack(pady=(0, 0))

        self._adjust_window_size()

    def _adjust_window_size(self):
        try:
            if self.keypress_enabled and self.speed_enabled:
                base_height = FULL_SIZE[1]
            elif self.keypress_enabled or self.speed_enabled:
                base_height = EXPANDED_SIZE[1]
            else:
                base_height = DEFAULT_WINDOW_SIZE[1]

            has_file = bool(self.selected_file)
            sky_running = self._check_sky_running()

            if sky_running and not has_file:
                base_height += HINT_FRAME_EXTRA_HEIGHT + 2

            if has_file:
                if self.keypress_enabled and self.speed_enabled:
                    base_height -= 5
                elif self.speed_enabled:
                    base_height -= 15
                elif self.keypress_enabled:
                    base_height -= 20
                else:
                    base_height -= 25

            self.root.geometry(f"{WINDOW_WIDTH}x{base_height}")
        except Exception:
            self.root.geometry(
                f"{DEFAULT_WINDOW_SIZE[0]}x{DEFAULT_WINDOW_SIZE[1]}"
            )

    def _open_releases(self, event=None):
        try:
            url = (
                self.update_url
                if (self.update_status == STATUS_UPDATE and self.update_url)
                else GITHUB_RELEASES_URL
            )
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror(
                LanguageManager.get('error_title'),
                f"Browser error: {e}",
            )

    # ==================== Helpers ====================

    def _truncate_filename(self, filepath, max_len: int = 30) -> str:
        try:
            name = Path(filepath).name
            if len(name) <= max_len:
                return name
            return f"{name[:max_len - 3]}..."
        except Exception:
            return "Unknown"

    def _get_short_path(self, file_path) -> str:
        try:
            path = Path(file_path)
            path_str = str(path).replace("\\", "/")

            if "resources/Songs" in path_str:
                rel = path_str.split("resources/Songs")[-1].lstrip("/")
                return f"Songs/{rel}"
            elif "resources" in path_str:
                rel = path_str.split("resources")[-1].lstrip("/")
                return f"resources/{rel}"
            return path.name
        except Exception:
            return Path(file_path).name

    # ==================== Shutdown ====================

    def _shutdown(self):
        logger.info("App Shutdown initiated")

        try:
            if hasattr(self, 'player') and self.player.playback.active:
                self.player.stop()
                logger.info("Playback stopped")

            if hasattr(self, 'player'):
                self.player.clear_cache()
                logger.info("Cache cleared")

            if hasattr(self, 'key_listener') and self.key_listener is not None:
                if self.key_listener.is_alive():
                    self.key_listener.stop()
                    logger.info("Listener stopped")

            if hasattr(self, '_mutex') and self._mutex:
                try:
                    ctypes.windll.kernel32.CloseHandle(self._mutex)
                    logger.info("Mutex released")
                except Exception:
                    pass

        except Exception as e:
            logger.critical(f"Shutdown error: {e}", exc_info=True)
        finally:
            try:
                self.root.destroy()
            except Exception:
                pass
            logger.info("App Closed")

    def run(self):
        self.root.mainloop()


# ==================== Entry Point ====================

if __name__ == "__main__":        
    if os.name == 'nt':
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    ctk.set_widget_scaling(1.0)
    ctk.set_window_scaling(1.0)

    try:
        app = MusicApp()
        app.run()
    except Exception as e:
        try:
            print(f"Crash: {e}", exc_info=True)
        except Exception:
            pass
        try:
            messagebox.showerror(
                "Critical Error",
                f"The application encountered a critical error and will close:\n\n{e}",
            )
        except Exception:
            print(f"Critical Error: {e}", file=sys.stderr)