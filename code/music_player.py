# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import json, time, logging, psutil, math
from pathlib import Path
from threading import Event, Lock
from pynput.keyboard import Controller
import pygetwindow as gw
from tkinter import messagebox

from language_manager import LanguageManager
from config_manager import ConfigManager
from note_scheduler import NoteScheduler

logger = logging.getLogger("ProjectLyrica.MusicPlayer")

class MusicPlayer:
    def __init__(self, config=None):
        try:
            self.logger = logging.getLogger("ProjectLyrica.MusicPlayer")
            
            if config is None:
                config = ConfigManager.get_config()
            self.config = config

            self.keyboard = Controller()
            self.pause_flag = Event()
            self.stop_event = Event()
            self.song_cache = {}
            self.status_lock = Lock()

            self.scheduler = None

            self._sky_window_cache = None
            self._sky_window_cache_time = 0
            self._sky_window_cache_ttl = 2.0
            
            self._initialize_key_mapping(self.config)
            self._initialize_timing(self.config)  
            self._initialize_playback_state()
            
        except Exception as e:
            logger.critical(f"Initialization failed: {e}", exc_info=True)
            raise

    def _initialize_key_mapping(self, config):
        """Initialize keyboard mapping from config with support for custom layouts"""
        self.key_map = {}
        
        try:
            from language_manager import KeyboardLayoutManager
            
            ui_settings = config.get("ui_settings", {})
            current_layout = ui_settings.get("keyboard_layout", "QWERTY")
            
            logger.info(f"Initializing key mapping with layout: {current_layout}")
            
            if current_layout == "Custom":
                custom_file = Path("resources/layouts/CUSTOM.xml")
                if custom_file.exists():
                    import xml.etree.ElementTree as ET
                    tree = ET.parse(custom_file)
                    for key in tree.findall('key'):
                        key_id = key.get('id')
                        key_text = key.text.strip() if key.text else ""
                        if key_id:
                            prefixes = ['', '1', '2', '3']
                            for prefix in prefixes:
                                self.key_map[f"{prefix}{key_id}".lower()] = key_text
                    logger.info(f"✅ Loaded CUSTOM mapping with {len(self.key_map)} keys")
                else:
                    self._load_standard_mapping("QWERTY")
                    logger.warning("❌ Custom layout selected but CUSTOM.xml not found, using QWERTY")
            else:
                self._load_standard_mapping(current_layout)
                logger.info(f"✅ Loaded {current_layout} mapping with {len(self.key_map)} keys")
                
        except Exception as e:
            logger.error(f"❌ Key mapping initialization error: {e}")
            self._load_fallback_mapping(config)

    def _load_standard_mapping(self, layout_name):
        """Load standard layout with all prefix variants"""
        from language_manager import KeyboardLayoutManager
        standard_map = KeyboardLayoutManager.load_layout_silently(layout_name)
        
        prefixes = ['', '1', '2', '3']
        for key_id, key_value in standard_map.items():
            for prefix in prefixes:
                self.key_map[f"{prefix}{key_id}".lower()] = key_value

    def _load_fallback_mapping(self, config):
        """Fallback: use key_mapping from config"""
        prefixes = ['', '1', '2', '3']
        key_mapping = config.get("key_mapping", {})
        
        for prefix in prefixes:
            for key, value in key_mapping.items():
                try:
                    if isinstance(value, str) and '\\u' in value:
                        value = bytes(value, 'latin1').decode('unicode_escape')
                    self.key_map[f"{prefix}{key}".lower()] = value
                except Exception as e:
                    logger.error(f"Key mapping error for {key}: {value} - {e}")
                    self.key_map[f"{prefix}{key}".lower()] = value

    def _initialize_timing(self, config):
        """Initialize timing parameters from config"""
        try:
            timing = config.get("timing_settings", {})
            delays = timing.get("delays", {})
            ramping = timing.get("ramping", {})

            self.initial_delay = delays.get("initial_delay", 0.8)
            self.pause_resume_delay = delays.get("pause_resume_delay", 1.0)

            self.ramp_begin_config = ramping.get("begin", {})
            self.ramp_end_config = ramping.get("end", {})
            self.ramp_after_pause_config = ramping.get("after_pause", {})
            
            self.speed_change_ramping_config = ramping.get("speed_change", {})
            self.speed_change_ramp_steps = self.speed_change_ramping_config.get("steps", 8)

            playback = config.get("playback_settings", {})
            self.enable_ramping = playback.get("enable_ramping", False)

            self.current_speed = 1000
            self.press_duration = 0.1
                    
        except Exception as e:
            logger.error(f"Error initializing timing: {e}")
            self.initial_delay = 0.8
            self.pause_resume_delay = 1.0
            self.enable_ramping = False
            self.current_speed = 1000
            self.press_duration = 0.1
            self.speed_change_ramp_steps = 8

    def _initialize_playback_state(self):
        """Initialize playback state variables"""
        self.playback_active = False
        self.is_ramping_begin = False
        self.is_ramping_end = False
        self.is_ramping_after_pause = False
        self.ramp_counter = 0
        self.ramp_begin_completed = False
        self.start_time = 0
        self.note_count = 0
        self.pause_count = 0
        self.pause_start = 0
        self.total_pause_time = 0
        self.speed_ramping_active = False
        self.speed_ramp_start_speed = 0
        self.speed_ramp_target_speed = 0
        self.speed_ramp_counter = 0

    def parse_song(self, path):
        """Parse song file with caching"""
        if path in self.song_cache:
            return self.song_cache[path]
        
        file = Path(path)
        try:
            encodings = ['utf-8', 'utf-16', 'latin-1']
            content = None
            
            for encoding in encodings:
                try:
                    content = file.read_text(encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                raise UnicodeDecodeError("Could not decode file with any encoding")
            
            if content.startswith('\ufeff'):
                content = content[1:]
            
            data = json.loads(content)
            
            song_data = data[0] if isinstance(data, list) and data else data
            
            notes_field = next(
                (field for field in ['songNotes', 'notes', 'Notes'] 
                 if field in song_data), 
                None
            )
            
            if not notes_field:
                raise ValueError(LanguageManager.get('missing_song_notes'))
            
            song_data["songNotes"] = song_data[notes_field]
            song_data["songTitle"] = song_data.get("name", song_data.get("title", "Unknown"))

            for note in song_data["songNotes"]:
                note['key_lower'] = note.get('key', '').lower()
            
            self.song_cache[path] = song_data
            return song_data
            
        except Exception as e:
            self.logger.error(f"Song parse error [{path}]: {e}", exc_info=True)
            error_msg = LanguageManager.get('invalid_song_format')
            raise ValueError(f"{error_msg}: {str(e)}")

    def clear_cache(self):
        """Clear song cache"""
        cache_size = len(self.song_cache)
        self.song_cache.clear()
        self.logger.info(f"Cleared song cache with {cache_size} entries")

    def _ensure_scheduler(self):
        """Ensures that Scheduler exists"""
        if self.scheduler is None:
            self.scheduler = NoteScheduler(self._release_key)
        elif not self.scheduler.active:
            self.scheduler.restart()

    def play(self, song_data):
        try:
            self.logger.info("Starting song playback")
            
            if self.playback_active:
                self.stop()
        
            self._ensure_scheduler()
            self.playback_active = True
            self.scheduler.reset()
            self.stop_event.clear()

            notes = song_data.get("songNotes", [])
            if not notes:
                logger.error("No notes found in song data")
                messagebox.showerror(LanguageManager.get("error_title"), LanguageManager.get("missing_song_notes"))
                return

            self._reset_playback_state()
            
            if self.enable_ramping:
                self.is_ramping_begin = True
                self.ramp_counter = 0
                self.ramp_begin_completed = False
                begin_config = self.ramp_begin_config
                self.logger.info(f"Ramping ENABLED - begin: {begin_config.get('steps', 20)} notes")
            else:
                self.logger.info("Ramping DISABLED")
            
            self.note_count = len(notes)
            song_title = song_data.get("songTitle", "Unknown")
            logger.info(f"Playing song: '{song_title}' with {self.note_count} notes at speed {self.current_speed}")

            from time import perf_counter as precision_timer

            time.sleep(self.initial_delay)
            
            self.start_time = precision_timer()
            self._play_notes(notes, precision_timer)
                        
        except Exception as e:
            logger.critical(f"Playback initialization failed: {e}", exc_info=True)
            self._release_all()
            self.playback_active = False
            raise

    def _reset_playback_state(self):
        """Reset playback state variables"""
        self.is_ramping_begin = False
        self.is_ramping_end = False
        self.is_ramping_after_pause = False
        self.ramp_counter = 0
        self.ramp_begin_completed = False
        self.pause_count = 0
        self.total_pause_time = 0
        self.speed_ramping_active = False
        self.speed_ramp_start_speed = 0
        self.speed_ramp_target_speed = 0
        self.speed_ramp_counter = 0

    def _play_notes(self, notes, timer_func):
        """Main loop for note playback"""
        last_time = 0
        last_note_time = 0
        
        try:
            for i, note in enumerate(notes):
                if not isinstance(note, dict) or 'time' not in note or 'key_lower' not in note:
                    logger.warning(f"Skipping invalid note at index {i}: {note}")
                    continue
                
                if self.stop_event.is_set():
                    logger.info("Playback stopped by user")
                    break

                current_speed = self._calculate_current_speed(i, len(notes))
                
                current_time = timer_func()
                if last_note_time > 0:
                    elapsed_since_last = current_time - last_note_time
                    required_interval = (note['time'] - last_time) / 1000 * (1000 / current_speed)
                    remaining_wait = max(0, required_interval - elapsed_since_last)

                    if not self._wait_with_pause_check(remaining_wait, timer_func):
                        break

                if self.stop_event.is_set():
                    break

                key = note.get('key_lower', '')
                if key and key in self.key_map:
                    mapped_key = self.key_map[key]
                    try:
                        self.keyboard.press(mapped_key)
                        self.scheduler.add(mapped_key, self.press_duration)
                    except Exception as e:
                        logger.error(f"Key press error: {e}")

                last_time = note['time']
                last_note_time = timer_func()

                if i == len(notes) - 1:
                    time.sleep(self.press_duration)
                    
        except Exception as e:
            logger.error(f"Unexpected playback error: {e}", exc_info=True)
        finally:
            self._cleanup_playback()

    def _calculate_current_speed(self, note_index, total_notes):
        """Calculate current speed with intelligent ramping priorities"""
        base_speed = self.current_speed

        if self.speed_ramping_active:
            base_speed = self._calculate_speed_with_ramping()

            if note_index % 5 == 0:
                elapsed = time.time() - self.speed_ramp_start_time
                progress = min(1.0, elapsed / self.speed_ramp_duration)
                logger.debug(f"Speed ramping: {base_speed:.0f} (progress: {progress:.2f})")
        
        ramp_factor = 1.0
        
        if self.is_ramping_begin and not self.ramp_begin_completed:
            begin_config = self.ramp_begin_config
            steps = begin_config.get('steps', 20)
            start_pct = begin_config.get('start_percentage', 50)
            end_pct = begin_config.get('end_percentage', 100)
            
            progress = min(1.0, self.ramp_counter / steps)
            ramp_factor = (start_pct + (end_pct - start_pct) * progress) / 100.0
            
            self.ramp_counter += 1
            if self.ramp_counter >= steps:
                self.is_ramping_begin = False
                self.ramp_begin_completed = True
                logger.info("Start ramping completed")

        elif self.is_ramping_after_pause:
            after_pause_config = self.ramp_after_pause_config
            steps = after_pause_config.get('steps', 12)
            start_pct = after_pause_config.get('start_percentage', 50)
            end_pct = after_pause_config.get('end_percentage', 100)
            
            progress = min(1.0, self.ramp_counter / steps)
            ramp_factor = (start_pct + (end_pct - start_pct) * progress) / 100.0
            
            self.ramp_counter += 1
            if self.ramp_counter >= steps:
                self.is_ramping_after_pause = False
                logger.info("Pause ramping completed")

        elif note_index >= total_notes - self.ramp_end_config.get('steps', 16):
            if not self.is_ramping_end:
                self.is_ramping_end = True
                self.ramp_counter = 0
                logger.info("End ramping started")
            
            end_config = self.ramp_end_config
            steps = end_config.get('steps', 16)
            start_pct = end_config.get('start_percentage', 100)
            end_pct = end_config.get('end_percentage', 50)
            
            notes_remaining = total_notes - note_index
            progress = max(0.0, min(1.0, (steps - notes_remaining) / steps))
            ramp_factor = (start_pct + (end_pct - start_pct) * progress) / 100.0

        final_speed = base_speed * ramp_factor
        
        return max(100, min(1500, final_speed))

    def _calculate_speed_with_ramping(self):
        """Calculate current speed with time-based ramping"""
        if not self.speed_ramping_active:
            return self.current_speed
        
        elapsed = time.time() - self.speed_ramp_start_time
        progress = min(1.0, elapsed / self.speed_ramp_duration)
        
        eased_progress = 1 - (1 - progress) ** 3  # Kubisches Easing
        
        start_speed = self.speed_ramp_start_speed
        target_speed = self.speed_ramp_target_speed
        
        if start_speed < target_speed:
            factor = target_speed / start_speed
            current_factor = 1 + (factor - 1) * eased_progress
            current_speed = start_speed * current_factor
        else:
            factor = target_speed / start_speed
            current_factor = 1 + (factor - 1) * eased_progress
            current_speed = start_speed * current_factor

        if progress >= 1.0:
            self.speed_ramping_active = False
            self.current_speed = target_speed
            logger.info(f"Time-based speed ramping completed: {self.current_speed}")
            
        return current_speed

    def change_speed_during_playback(self, new_speed):
        """Change speed during playback with ramping"""
        try:
            if not self.playback_active:
                return False
                
            logger.info(f"Changing speed to {new_speed}")

            self._init_speed_ramping(new_speed)
            
            return True
            
        except Exception as e:
            logger.error(f"Speed change error: {e}")
            return False

    # Init
    def _init_speed_ramping(self, target_speed):
        """Initialize with combined adaptive ramping"""
        # Ramping-State aktivieren und Startwerte setzen
        self.speed_ramping_active = True
        self.speed_ramp_start_speed = self.current_speed
        self.speed_ramp_target_speed = target_speed
        self.speed_ramp_start_time = time.time()
        
        # 1. Prozentuale Geschwindigkeitsänderung berechnen
        # Beispiel: 800 → 600 = (800-600)/800 = 0.25 (25% Reduktion)
        speed_change_ratio = abs(target_speed - self.current_speed) / self.current_speed
        
        # 2. Basisdauer basierend auf Änderungsstärke - größere Änderungen brauchen mehr Zeit
        if speed_change_ratio <= 0.2:    # Kleine Änderung: (z.B. 1000→800, 800→600)
            base_duration = 2.6          # Schneller Übergang (kleinere Zahl = schneller)
        elif speed_change_ratio <= 0.5:  # Mittlere Änderung: (z.B. 800→600, 1000→500)  
            base_duration = 2.4          # Standard Übergang
        else:                            # Große Änderung: (z.B. 600→1200, 800→1600)
            base_duration = 4.0          # Langer, sanfter Übergang (größere Zahl = langsamer)
        
        # 3. Richtungsanpassung - Verlangsamen braucht mehr Zeit für natürlichen Übergang
        # Psychoakustik
        if target_speed < self.current_speed:  # VERLANGSAMEN (z.B. 800→600)
            base_duration *= 1.5  # (größere Zahl = langsamer)
        else:  # BESCHLEUNIGEN (z.B. 600→800)
            base_duration *= 1.6  # (größere Zahl = langsamer)
        
        # 4. Steps-Feinabstimmung - benutzerkonfigurierbare Steps skalieren die Gesamtdauer
        # 8 Steps = 0.67x kürzer/schneller | 12 Steps = 1.0x Standard | 16 Steps = 1.33x länger/sanfter
        # KLEINERE Steps-Zahl = SCHNELLER | GRÖSSERE Steps-Zahl = LANGSAMER
        steps_multiplier = self.speed_change_ramp_steps / 12.0
        self.speed_ramp_duration = base_duration * steps_multiplier
        
        # 5. Stabilitätsgrenzen - verhindern extreme Werte für konsistente Performance
        self.speed_ramp_duration = max(1.5, min(6.0, self.speed_ramp_duration))  # Min 1.5s, Max 6.0s
        
        # Debug-Logging
        logger.info(f"Smart ramping: {self.current_speed} → {target_speed} over {self.speed_ramp_duration:.1f}s (ratio: {speed_change_ratio:.2f})")

    def _wait_with_pause_check(self, wait_time, timer_func):
        """Wait with pause support"""
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
            if time_left > 0.01:
                time.sleep(min(time_left * 0.3, 0.01))
            elif time_left > 0.001:
                time.sleep(0.001)
                
        return True

    def _handle_pause(self, timer_func):
        """Treated Break"""
        ramping_state = self._get_ramping_state()
        
        with self.status_lock:
            self.pause_count += 1
        self.pause_start = timer_func()
        self._release_all()

        while self.pause_flag.is_set() and not self.stop_event.is_set():
            time.sleep(0.05)
            
        if self.stop_event.is_set():
            return False

        pause_duration = timer_func() - self.pause_start
        self.total_pause_time += pause_duration

        # Pause-Resume Delay
        if self.pause_resume_delay > 0:
            delay_start = timer_func()
            while (timer_func() - delay_start) < self.pause_resume_delay:
                if self.stop_event.is_set():
                    return False
                time.sleep(0.01)

        # Ramping-State
        self._restore_ramping_state(ramping_state)
        
        return True

    def _get_ramping_state(self):
        """Get current ramping state"""
        return {
            'begin': self.is_ramping_begin,
            'end': self.is_ramping_end,
            'after_pause': self.is_ramping_after_pause,
            'counter': self.ramp_counter,
            'begin_completed': self.ramp_begin_completed,
            'speed_ramping': self.speed_ramping_active,
            'speed_ramp_counter': self.speed_ramp_counter,
            'speed_ramp_target': self.speed_ramp_target_speed
        }

    def _restore_ramping_state(self, state):
        """Restores ramping state"""
        self.is_ramping_begin = state['begin']
        self.is_ramping_end = state['end'] 
        self.is_ramping_after_pause = state['after_pause']
        self.ramp_counter = state['counter']
        self.ramp_begin_completed = state['begin_completed']
        self.speed_ramping_active = state['speed_ramping']
        self.speed_ramp_counter = state['speed_ramp_counter']
        self.speed_ramp_target_speed = state['speed_ramp_target']

        if self.enable_ramping and not any([state['begin'], state['end'], state['after_pause']]):
            self.is_ramping_after_pause = True
            self.ramp_counter = 0

    def _cleanup_playback(self):
        """Tidy up after playback"""
        self._release_all()
        self.playback_active = False
        
        self.speed_ramping_active = False
        
        logger.info(f"Playback finished - Total notes: {self.note_count}, "
                f"Pauses: {self.pause_count}, "
                f"Total pause time: {self.total_pause_time:.2f}s")

    def stop(self):
        """Stoppt Playback"""
        if not self.playback_active:
            return
            
        self.stop_event.set()
        self.pause_flag.clear()
        self._release_all()
        self.playback_active = False
        self.speed_ramping_active = False

    def set_speed(self, speed):
        """Sets speed"""
        if speed <= 0:
            logger.warning(f"Invalid speed {speed}, resetting to 1000")
            self.current_speed = 1000
        else:
            self.current_speed = speed
            
        if self.playback_active and not self.pause_flag.is_set():
            logger.info(f"Speed changed to {speed} during playback (instant)")

    def get_current_speed(self):
        """Get current speed value"""
        return self.current_speed

    def _release_all(self):
        """Releases all buttons"""
        if self.scheduler:
            self.scheduler.reset()
        
        released_keys = set()
        for key in self.key_map.values():
            if key not in released_keys:
                try: 
                    self.keyboard.release(key)
                    released_keys.add(key)
                except Exception as e: 
                    logger.error(f"Key release error: {e}")

    def _find_sky_window(self):
        """Find Sky windows with cache"""
        current_time = time.time()
        if (self._sky_window_cache and 
            current_time - self._sky_window_cache_time < self._sky_window_cache_ttl):
            return self._sky_window_cache

        try:
            exe_path = ConfigManager.get_value("game_settings.sky_exe_path", "")
            if not exe_path:
                logger.error("No Sky.exe path in settings.json!")
                return None

            target_exe_name = Path(exe_path).name.lower()

            for proc in psutil.process_iter(['name', 'exe']):
                try:
                    if (proc.info['name'].lower() == target_exe_name or 
                        (proc.info['exe'] and Path(proc.info['exe']).name.lower() == target_exe_name)):
                        
                        windows = gw.getWindowsWithTitle("Sky")
                        if windows:
                            self._sky_window_cache = windows[0]
                            self._sky_window_cache_time = current_time
                            return windows[0]
                        else:
                            logger.warning("Sky.exe is running but no window found!")
                            return None
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            logger.warning(f"{target_exe_name} not found in process list!")
            return None

        except Exception as e:
            logger.error(f"Process search failed: {e}")
            return None

    def _focus_window(self, window):
        """Focused window"""
        try:
            if not isinstance(window, gw.Window):
                logger.error("Invalid window object provided")
                return False
                
            if window.isMinimized: 
                window.restore()
                
            if not window.isActive:
                for attempt in range(3):
                    try:
                        window.activate()
                        time.sleep(0.1)
                        if window.isActive:
                            return True
                    except Exception as e:
                        if attempt == 2:
                            logger.warning(f"Window activation failed after 3 attempts: {e}")
            return window.isActive
            
        except Exception as e:
            logger.error(f"Window focus error: {e}")
            return False

    def _release_key(self, key):
        """Releases key (for scheduler)"""
        try:
            self.keyboard.release(key)
        except Exception as e:
            logger.error(f"Key release error in scheduler: {e}")