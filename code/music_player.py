# Copyright (C) 2025-2026 VanilleIce
# All rights reserved.
#
# Project Lyrica is proprietary software.
# Commercial use, redistribution, and modification are prohibited.
# See LICENSE.md for details.

import ctypes
import json
import logging
import time
import xml.etree.ElementTree as ET
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock
from time import perf_counter as precision_timer
from typing import Any, Callable, Dict, List, Optional

import psutil
import pygetwindow as gw
from pynput.keyboard import Controller

from config_manager import ConfigManager
from language_manager import LanguageManager, KeyboardLayoutManager
from note_scheduler import NoteScheduler
from resource_loader import resource_path, writable_resource_path

logger = logging.getLogger("ProjectLyrica.MusicPlayer")


# ==================== Konstanten ====================

MIN_SPEED = 100
MAX_SPEED = 1500
DEFAULT_SPEED = 1000

SPEED_UP_MULTIPLIER = 1.4
SPEED_DOWN_MULTIPLIER = 1.0

MIN_RAMP_DURATION = 1.5
MAX_RAMP_DURATION = 25.0
SKIP_RAMP_THRESHOLD = 20

DEFAULT_PRESS_DURATION = 0.1
PAUSE_CHECK_INTERVAL = 0.05
SLEEP_PRECISION = 0.01
PAUSE_TIMEOUT = 3600

SKY_WINDOW_CACHE_TTL = 2.0
SKY_PID_CACHE_TTL = 3.0
FOCUS_ATTEMPTS = 3
FOCUS_RETRY_DELAY = 0.1

CUSTOM_LAYOUT_FILE = "resources/layouts/CUSTOM.xml"
SUPPORTED_ENCODINGS = ("utf-8", "utf-16", "latin-1")

# Key-Prefixes für Layout-Mapping
KEY_PREFIXES = ('', '1', '2', '3')


# ==================== Dataclasses ====================

@dataclass
class RampingState:
    is_begin: bool = False
    is_end: bool = False
    is_after_pause: bool = False
    begin_counter: int = 0
    end_counter: int = 0
    after_pause_counter: int = 0
    begin_completed: bool = False
    speed_ramping_active: bool = False
    speed_ramp_target: float = DEFAULT_SPEED
    paused_speed: float = 0.0


@dataclass
class PlaybackState:
    active: bool = False
    note_count: int = 0
    pause_count: int = 0
    total_pause_time: float = 0.0
    start_time: float = 0.0


@dataclass
class SpeedRampingState:
    active: bool = False
    start_speed: float = DEFAULT_SPEED
    target_speed: float = DEFAULT_SPEED
    start_time: float = 0.0
    duration: float = 0.0
    direction: Optional[str] = None


# ==================== Sky Window Manager ====================

class SkyWindowManager:
    """Verwaltet das Sky-Fenster (Finden via PID, Fokussieren, Caching)."""

    def __init__(self):
        self._window_cache: Optional[Any] = None
        self._window_cache_time: float = 0.0
        self._pid_cache: Optional[int] = None
        self._pid_cache_time: float = 0.0

    def _get_sky_pid(self) -> Optional[int]:
        """Findet die PID der Sky.exe anhand des konfigurierten Pfades."""
        current_time = time.time()

        # PID-Cache prüfen
        if (self._pid_cache is not None
                and current_time - self._pid_cache_time < SKY_PID_CACHE_TTL):
            try:
                if psutil.pid_exists(self._pid_cache):
                    return self._pid_cache
            except Exception:
                pass
            self._pid_cache = None

        exe_path = ConfigManager.get_value("game_settings.sky_exe_path", "")
        if not exe_path:
            return None

        target_exe = Path(exe_path).name.lower()

        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    info = proc.info
                    proc_name = (info.get('name') or '').lower()
                    proc_exe = Path(info['exe']).name.lower() if info.get('exe') else ''

                    if proc_name == target_exe or proc_exe == target_exe:
                        self._pid_cache = info['pid']
                        self._pid_cache_time = current_time
                        return info['pid']
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as e:
            logger.debug(f"Process iteration error: {e}")

        return None

    def find_window(self) -> Optional[Any]:
        """Findet das Sky-Fenster anhand der Prozess-PID."""
        current_time = time.time()

        # Window-Cache prüfen
        if (self._window_cache
                and current_time - self._window_cache_time < SKY_WINDOW_CACHE_TTL):
            return self._window_cache

        sky_pid = self._get_sky_pid()
        if not sky_pid:
            self._window_cache = None
            return None

        # Alle Fenster durchsuchen und das mit passender PID finden
        try:
            user32 = ctypes.windll.user32
            for window in gw.getAllWindows():
                hwnd = getattr(window, '_hWnd', None)
                if not hwnd:
                    continue
                try:
                    window_pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
                    if window_pid.value == sky_pid and window.title:
                        self._window_cache = window
                        self._window_cache_time = current_time
                        return window
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Window enumeration failed: {e}")

        # Fallback: Titel-Suche
        try:
            for window in gw.getWindowsWithTitle("Sky"):
                if window.title:
                    self._window_cache = window
                    self._window_cache_time = current_time
                    logger.debug("Using fallback title search for Sky window")
                    return window
        except Exception:
            pass

        return None

    def focus_window(self, window: Optional[Any] = None) -> bool:
        """Fokussiert das Sky-Fenster."""
        if window is None:
            window = self.find_window()

        if not window:
            return False

        for attempt in range(FOCUS_ATTEMPTS):
            try:
                if window.isMinimized:
                    window.restore()
                    time.sleep(0.05)

                if window.isActive:
                    return True

                window.activate()
                time.sleep(FOCUS_RETRY_DELAY)

                if window.isActive:
                    return True
            except Exception as e:
                logger.debug(f"Focus attempt {attempt + 1} failed: {e}")
                time.sleep(FOCUS_RETRY_DELAY)

        return False

    def is_running(self) -> bool:
        return self._get_sky_pid() is not None

    def clear_cache(self):
        self._window_cache = None
        self._window_cache_time = 0.0
        self._pid_cache = None
        self._pid_cache_time = 0.0


# ==================== Music Player ====================

class MusicPlayer:
    def __init__(self, config=None):
        self.logger = logging.getLogger("ProjectLyrica.MusicPlayer")
        self.config = config if config else ConfigManager.get_config()

        self.keyboard = Controller()
        self.pause_flag = Event()
        self.stop_event = Event()
        self.song_cache: Dict[str, Dict] = {}
        self.status_lock = Lock()

        self.scheduler: Optional[NoteScheduler] = None
        self.window_manager = SkyWindowManager()

        self._initialize_key_mapping(self.config)
        self._initialize_timing(self.config)
        self._initialize_state()

    # ==================== Initialisierung ====================

    def _initialize_key_mapping(self, config):
        """Lädt Key-Mapping basierend auf Layout-Konfiguration."""
        self.key_map: Dict[str, str] = {}

        ui_settings = config.get("ui_settings", {})
        current_layout = ui_settings.get("keyboard_layout", "QWERTY")

        if current_layout == "Custom":
            if self._load_custom_mapping():
                return

        if self._load_standard_mapping(current_layout):
            return

        self._load_fallback_mapping(config)

    def _load_custom_mapping(self) -> bool:
        """Lädt Custom-Layout. Gibt True bei Erfolg zurück."""
        # CUSTOM.xml liegt neben der EXE (beschreibbar), nicht im _MEIPASS
        custom_file = Path(writable_resource_path(CUSTOM_LAYOUT_FILE))
        if not custom_file.exists():
            # Fallback: im _MEIPASS (falls doch mitgeliefert)
            custom_file = Path(resource_path(CUSTOM_LAYOUT_FILE))
            if not custom_file.exists():
                logger.warning(f"Custom layout selected but {custom_file} not found")
                return False

        try:
            tree = ET.parse(custom_file)
            for key in tree.findall('key'):
                key_id = key.get('id')
                key_text = key.text.strip() if key.text else ""
                if key_id:
                    for prefix in KEY_PREFIXES:
                        self.key_map[f"{prefix}{key_id}".lower()] = key_text
            logger.info(f"Loaded custom layout with {len(self.key_map)} key bindings")
            return True
        except Exception as e:
            logger.error(f"Failed to parse CUSTOM.xml: {e}")
            return False

    def _load_standard_mapping(self, layout_name: str) -> bool:
        """Lädt Standard-Layout. Gibt True bei Erfolg zurück."""
        try:
            standard_map = KeyboardLayoutManager.load_layout_silently(layout_name)
            if not standard_map:
                return False

            for key_id, key_value in standard_map.items():
                for prefix in KEY_PREFIXES:
                    self.key_map[f"{prefix}{key_id}".lower()] = key_value

            logger.info(f"Loaded layout '{layout_name}' with {len(standard_map)} keys")
            return True
        except Exception as e:
            logger.error(f"Failed to load layout '{layout_name}': {e}")
            return False

    def _load_fallback_mapping(self, config):
        """Letzter Fallback: key_mapping aus Config."""
        key_mapping = config.get("key_mapping", {})
        if not key_mapping:
            logger.warning("No key mapping could be loaded!")
            return

        for key, value in key_mapping.items():
            if isinstance(value, str) and '\\u' in value:
                try:
                    value = bytes(value, 'latin1').decode('unicode_escape')
                except Exception:
                    pass

            for prefix in KEY_PREFIXES:
                self.key_map[f"{prefix}{key}".lower()] = value

        logger.info(f"Loaded fallback mapping with {len(key_mapping)} keys")

    def _initialize_timing(self, config):
        timing = config.get("timing_settings", {})
        delays = timing.get("delays", {})
        ramping = timing.get("ramping", {})

        self.initial_delay = max(0.1, delays.get("initial_delay", 0.8))
        self.pause_resume_delay = max(0.1, delays.get("pause_resume_delay", 1.0))
        self.ramp_begin_config = ramping.get("begin", {})
        self.ramp_end_config = ramping.get("end", {})
        self.ramp_after_pause_config = ramping.get("after_pause", {})
        self.speed_change_config = ramping.get("speed_change", {})
        self.speed_transition_time = self.speed_change_config.get('transition_time', 6.0)

        playback = config.get("playback_settings", {})
        self.enable_ramping = playback.get("enable_ramping", False)

        self.current_speed = DEFAULT_SPEED
        self.press_duration = DEFAULT_PRESS_DURATION

    def _initialize_state(self):
        self.playback = PlaybackState()
        self.ramping = RampingState()
        self.speed_ramping = SpeedRampingState()

    def _reset_playback_state(self):
        self.ramping = RampingState()
        self.playback.note_count = 0
        self.playback.pause_count = 0
        self.playback.total_pause_time = 0.0
        self.playback.start_time = 0.0
        self.speed_ramping = SpeedRampingState()

    # ==================== Song Parsing ====================

    def parse_song(self, path: str) -> Dict:
        """Parst Song-Datei und cached Ergebnis."""
        if path in self.song_cache:
            return self.song_cache[path]

        try:
            content = self._read_song_file(Path(path))
            data = json.loads(content)
            song_data = data[0] if isinstance(data, list) and data else data

            if not isinstance(song_data, dict):
                raise ValueError("Song file has invalid structure")

            song_data['bpm'] = self._extract_bpm(song_data)

            notes_field = next(
                (f for f in ('songNotes', 'notes', 'Notes') if f in song_data),
                None
            )
            if not notes_field:
                raise ValueError(LanguageManager.get('missing_song_notes'))

            notes = song_data[notes_field]
            if not isinstance(notes, list):
                raise ValueError("Notes field is not a list")

            normalized_notes = []
            for note in notes:
                if isinstance(note, dict) and 'time' in note and 'key' in note:
                    note['key_lower'] = str(note['key']).lower()
                    normalized_notes.append(note)

            song_data["songNotes"] = normalized_notes
            song_data["songTitle"] = song_data.get(
                "name", song_data.get("title", "Unknown")
            )

            self.song_cache[path] = song_data
            return song_data

        except Exception as e:
            self.logger.error(f"Song parse error [{Path(path).name}]: {e}")
            raise ValueError(f"{LanguageManager.get('invalid_song_format')}: {e}")

    def _read_song_file(self, file: Path) -> str:
        """Liest Song-Datei mit automatischer Encoding-Erkennung."""
        last_error = None

        for encoding in SUPPORTED_ENCODINGS:
            try:
                content = file.read_text(encoding=encoding)
                if content.startswith('\ufeff'):
                    content = content[1:]
                return content
            except (UnicodeDecodeError, UnicodeError) as e:
                last_error = e
                continue
            except Exception as e:
                last_error = e
                continue

        raise ValueError(f"Could not decode file: {last_error}")

    def _extract_bpm(self, song_data: Dict) -> Optional[float]:
        bpm = song_data.get('bpm')
        if bpm is None:
            return None
        try:
            return float(bpm)
        except (ValueError, TypeError):
            return None

    def clear_cache(self):
        self.song_cache.clear()

    # ==================== Playback Steuerung ====================

    def _ensure_scheduler(self):
        if self.scheduler is None:
            self.scheduler = NoteScheduler(self._release_key)
        elif not self.scheduler.active:
            self.scheduler.restart()

    def play(self, song_data: Dict):
        """Startet Song-Wiedergabe (blockiert bis fertig)."""
        try:
            if self.playback.active:
                self.stop()

            self._ensure_scheduler()
            self.scheduler.reset()
            self.stop_event.clear()

            notes = song_data.get("songNotes", [])
            if not notes:
                logger.error("No notes found in song data")
                return

            self._reset_playback_state()
            self.playback.active = True
            self.playback.note_count = len(notes)
            self._init_begin_ramping()

            if not self._wait_with_pause_check(self.initial_delay, precision_timer):
                return

            self.playback.start_time = precision_timer()
            self._play_notes(notes)

        except Exception as e:
            logger.critical(f"Playback failed: {e}", exc_info=True)
            self._release_all()
            self.playback.active = False
            raise

    def _init_begin_ramping(self):
        if self.enable_ramping:
            self.ramping.is_begin = True
            self.ramping.begin_counter = 0
            self.ramping.begin_completed = False

    def _play_notes(self, notes: List[Dict]):
        """Spielt alle Notes ab."""
        timer_func = precision_timer
        last_note_time: Optional[float] = None
        last_time = 0.0
        total_notes = len(notes)

        try:
            for i, note in enumerate(notes):
                if self.stop_event.is_set():
                    break

                self._check_end_ramping(i, total_notes)
                current_speed = self._calculate_current_speed(i, total_notes)

                if last_note_time is not None:
                    if not self._wait_for_next_note(
                        note, last_time, last_note_time, current_speed, timer_func
                    ):
                        break

                if self.stop_event.is_set():
                    break

                self._press_note(note)
                last_time = note['time']
                last_note_time = timer_func()

            # Letzten Key kurz halten (nur wenn kein Stop)
            if not self.stop_event.is_set():
                time.sleep(self.press_duration)

        finally:
            self._cleanup_playback()

    def _check_end_ramping(self, note_index: int, total_notes: int):
        if not self.ramping.is_end:
            steps = self.ramp_end_config.get('steps', 16)
            if note_index >= total_notes - steps:
                self.ramping.is_end = True

    def _wait_for_next_note(self, note: Dict, last_time: float,
                            last_note_time: float, current_speed: float,
                            timer_func: Callable) -> bool:
        """Wartet bis zum nächsten Note."""
        current_time = timer_func()
        elapsed = current_time - last_note_time
        required = (note['time'] - last_time) / 1000 * (1000 / current_speed)
        remaining = max(0, required - elapsed)
        return self._wait_with_pause_check(remaining, timer_func)

    def _press_note(self, note: Dict):
        """Drückt eine Taste."""
        key = note.get('key_lower', '')
        mapped_key = self.key_map.get(key)
        if not mapped_key:
            return

        try:
            self.keyboard.press(mapped_key)
            self.scheduler.add(mapped_key, self.press_duration)
        except Exception as e:
            logger.debug(f"Could not press key '{mapped_key}': {e}")

    def _cleanup_playback(self):
        self._release_all()
        self.playback.active = False
        self.speed_ramping.active = False

    def stop(self):
        """Stoppt die Wiedergabe."""
        if not self.playback.active:
            return

        self.stop_event.set()
        self.pause_flag.clear()
        self._release_all()
        self.playback.active = False
        self.speed_ramping.active = False

    # ==================== Geschwindigkeits-Berechnung ====================

    def _calculate_current_speed(self, note_index: int, total_notes: int) -> float:
        try:
            if self.speed_ramping.active:
                base_speed = self._get_current_actual_speed()
            else:
                base_speed = max(MIN_SPEED, min(MAX_SPEED, self.current_speed))

            ramp_factor = 1.0
            ramp_factor = self._apply_begin_ramping(ramp_factor)
            ramp_factor = self._apply_pause_ramping(ramp_factor)
            ramp_factor = self._apply_end_ramping(note_index, total_notes, ramp_factor)

            return max(MIN_SPEED, min(MAX_SPEED, base_speed * ramp_factor))
        except Exception:
            return max(MIN_SPEED, min(MAX_SPEED, self.current_speed))

    def _apply_begin_ramping(self, ramp_factor: float) -> float:
        if not (self.ramping.is_begin and not self.ramping.begin_completed):
            return ramp_factor

        config = self.ramp_begin_config
        steps = max(1, config.get('steps', 20))
        progress = min(1.0, self.ramping.begin_counter / steps)
        start_pct = 50
        end_pct = 100

        ramp_factor *= max(0.01, (start_pct + (end_pct - start_pct) * progress) / 100.0)
        self.ramping.begin_counter += 1

        if self.ramping.begin_counter >= steps:
            self.ramping.is_begin = False
            self.ramping.begin_completed = True
            logger.debug("Start ramping completed")

        return ramp_factor

    def _apply_pause_ramping(self, ramp_factor: float) -> float:
        if not self.ramping.is_after_pause:
            return ramp_factor

        config = self.ramp_after_pause_config
        steps = max(1, config.get('steps', 12))
        progress = min(1.0, self.ramping.after_pause_counter / steps)

        paused_speed = self.ramping.paused_speed
        current_speed = self.current_speed

        # Startwert: 50% des Werts VOR der Pause
        if paused_speed > 0 and current_speed > 0:
            start_speed = paused_speed * 0.5
            start_speed = max(50.0, min(start_speed, current_speed))
            start_pct = (start_speed / current_speed) * 100.0
        else:
            start_pct = 50.0

        end_pct = 100.0

        ramp_factor *= max(0.01, (start_pct + (end_pct - start_pct) * progress) / 100.0)
        self.ramping.after_pause_counter += 1

        if self.ramping.after_pause_counter >= steps:
            self.ramping.is_after_pause = False
            logger.debug("Pause ramping completed")

        return ramp_factor

    def _apply_end_ramping(self, note_index: int, total_notes: int,
                           ramp_factor: float) -> float:
        if not self.ramping.is_end:
            return ramp_factor

        config = self.ramp_end_config
        steps = max(1, config.get('steps', 16))
        notes_remaining = total_notes - note_index
        progress = max(0.0, min(1.0, (steps - notes_remaining) / steps))
        start_pct = 100
        end_pct = 50

        ramp_factor *= max(0.01, (start_pct + (end_pct - start_pct) * progress) / 100.0)

        if notes_remaining <= 1:
            self.ramping.is_end = False
            logger.debug("End ramping completed")

        return ramp_factor

    # ==================== Speed-Ramping ====================

    def _init_speed_ramping(self, target_speed: float):
        """Initialisiert Speed-Ramping zum Ziel-Wert."""
        current_actual = self._get_current_actual_speed()
        target_speed = max(MIN_SPEED, min(MAX_SPEED, target_speed))

        if abs(target_speed - current_actual) < SKIP_RAMP_THRESHOLD:
            self.current_speed = target_speed
            self.speed_ramping.active = False
            return

        if target_speed > current_actual:
            self.speed_ramping.direction = 'up'
            mult = SPEED_UP_MULTIPLIER
        else:
            self.speed_ramping.direction = 'down'
            mult = SPEED_DOWN_MULTIPLIER

        rel_change = (
            abs(target_speed - current_actual) / current_actual
            if current_actual > 0 else 1.0
        )
        ramp_duration = max(
            MIN_RAMP_DURATION,
            min(MAX_RAMP_DURATION, self.speed_transition_time * rel_change * mult)
        )

        self.speed_ramping.active = True
        self.speed_ramping.start_speed = current_actual
        self.speed_ramping.target_speed = target_speed
        self.speed_ramping.start_time = time.time()
        self.speed_ramping.duration = ramp_duration
        self.current_speed = target_speed

    def _get_current_actual_speed(self) -> float:
        """Gibt aktuelle (ggf. gerampte) Geschwindigkeit zurück."""
        if not self.speed_ramping.active:
            return max(MIN_SPEED, min(MAX_SPEED, self.current_speed))

        try:
            elapsed = time.time() - self.speed_ramping.start_time
            progress = min(1.0, elapsed / self.speed_ramping.duration)

            if progress < 0.5:
                eased = 2 * progress * progress
            else:
                eased = 1 - (-2 * progress + 2) ** 2 / 2

            current = (
                self.speed_ramping.start_speed
                + (self.speed_ramping.target_speed - self.speed_ramping.start_speed) * eased
            )

            if progress >= 1.0:
                self.speed_ramping.active = False
                self.current_speed = max(
                    MIN_SPEED, min(MAX_SPEED, self.speed_ramping.target_speed)
                )

            return max(MIN_SPEED, min(MAX_SPEED, current))
        except Exception:
            self.speed_ramping.active = False
            return max(MIN_SPEED, min(MAX_SPEED, self.current_speed))

    # ==================== Pausen-Behandlung ====================

    def _wait_with_pause_check(self, wait_time: float, timer_func: Callable) -> bool:
        """Wartet wait_time, prüft auf Pause/Stop. Gibt False bei Stop zurück."""
        if wait_time <= 0:
            return not self.stop_event.is_set()

        wait_start = timer_func()

        while (timer_func() - wait_start) < wait_time:
            if self.stop_event.is_set():
                return False

            if self.pause_flag.is_set():
                if not self._handle_pause(timer_func):
                    return False
                wait_start = timer_func()
                continue

            time_left = wait_time - (timer_func() - wait_start)
            if time_left > SLEEP_PRECISION:
                time.sleep(min(time_left * 0.3, SLEEP_PRECISION))
            else:
                break

        return True

    def _handle_pause(self, timer_func: Callable) -> bool:
        """Behandelt Pause. Gibt False zurück wenn abgebrochen."""
        ramping_state = self._get_ramping_state()

        # Speed vor der Pause merken (für die Pause-Rampe)
        ramping_state.paused_speed = self._get_current_actual_speed()

        with self.status_lock:
            self.playback.pause_count += 1
        pause_start = timer_func()

        self._release_all()

        pause_start_time = timer_func()
        while self.pause_flag.is_set() and not self.stop_event.is_set():
            if (timer_func() - pause_start_time) > PAUSE_TIMEOUT:
                logger.warning("Pause timeout reached")
                break
            time.sleep(PAUSE_CHECK_INTERVAL)

        if self.stop_event.is_set():
            return False

        with self.status_lock:
            self.playback.total_pause_time += timer_func() - pause_start

        self._wait_resume_delay(timer_func)
        self._restore_ramping_state(ramping_state)

        if self.enable_ramping:
            self.ramping.is_after_pause = True
            self.ramping.after_pause_counter = 0

        return True

    def _wait_resume_delay(self, timer_func: Callable):
        """Wartet Pause-Resume-Delay."""
        if self.pause_resume_delay <= 0:
            return

        delay_start = timer_func()
        while (timer_func() - delay_start) < self.pause_resume_delay:
            if self.stop_event.is_set():
                return
            time.sleep(SLEEP_PRECISION)

    def _get_ramping_state(self) -> RampingState:
        """Kopiert aktuellen Ramping-State."""
        return RampingState(
            is_begin=self.ramping.is_begin,
            is_end=self.ramping.is_end,
            is_after_pause=self.ramping.is_after_pause,
            begin_counter=self.ramping.begin_counter,
            end_counter=self.ramping.end_counter,
            after_pause_counter=self.ramping.after_pause_counter,
            begin_completed=self.ramping.begin_completed,
            speed_ramping_active=self.speed_ramping.active,
            speed_ramp_target=self.speed_ramping.target_speed,
            paused_speed=self.ramping.paused_speed,
        )

    def _restore_ramping_state(self, state: RampingState):
        """Stellt Ramping-State wieder her."""
        self.ramping.is_begin = state.is_begin
        self.ramping.is_end = state.is_end
        self.ramping.is_after_pause = state.is_after_pause
        self.ramping.begin_counter = state.begin_counter
        self.ramping.end_counter = state.end_counter
        self.ramping.after_pause_counter = state.after_pause_counter
        self.ramping.begin_completed = state.begin_completed
        self.ramping.paused_speed = state.paused_speed
        self.speed_ramping.active = state.speed_ramping_active
        self.speed_ramping.target_speed = state.speed_ramp_target

        if (self.enable_ramping
                and not (state.is_begin or state.is_end or state.is_after_pause)):
            self.ramping.is_after_pause = True
            self.ramping.after_pause_counter = 0

    # ==================== Key-Release ====================

    def _release_all(self):
        """Releast alle aktuell gedrückten Keys."""
        if self.scheduler:
            self.scheduler.reset()

        # Nur die tatsächlich gemappten Keys releasen (unique values)
        for key in set(self.key_map.values()):
            try:
                self.keyboard.release(key)
            except Exception:
                pass

    def _release_key(self, key: str):
        """Callback für Scheduler - released einzelnen Key."""
        try:
            self.keyboard.release(key)
        except Exception:
            pass

    # ==================== Öffentliche Methoden ====================

    def set_speed(self, speed: float):
        try:
            speed = float(speed)
            self.current_speed = (
                max(MIN_SPEED, min(MAX_SPEED, speed)) if speed > 0 else DEFAULT_SPEED
            )
        except (ValueError, TypeError):
            self.current_speed = DEFAULT_SPEED

    def get_current_speed(self) -> float:
        return self.current_speed

    def find_sky_window(self) -> Optional[Any]:
        return self.window_manager.find_window()

    def focus_sky_window(self) -> bool:
        return self.window_manager.focus_window()

    def is_sky_running(self) -> bool:
        return self.window_manager.is_running()

    # Aliase für Rückwärtskompatibilität
    _find_sky_window = find_sky_window
    _focus_window = focus_sky_window