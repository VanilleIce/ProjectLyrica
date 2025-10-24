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
                custom_file = Path('resources/layouts/CUSTOM.xml')
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

            self.initial_delay = max(0.1, delays.get("initial_delay", 0.8))
            self.pause_resume_delay = max(0.1, delays.get("pause_resume_delay", 1.0))

            self.ramp_begin_config = ramping.get("begin", {})
            self.ramp_end_config = ramping.get("end", {})
            self.ramp_after_pause_config = ramping.get("after_pause", {})

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

    def _initialize_playback_state(self):
        """Initialize playback state variables"""
        self.playback_active = False
        self.is_ramping_begin = False
        self.is_ramping_end = False
        self.is_ramping_after_pause = False
        self.ramp_begin_completed = False
        
        self.ramp_begin_counter = 0
        self.ramp_end_counter = 0  
        self.ramp_after_pause_counter = 0
        
        self.pause_count = 0
        self.total_pause_time = 0
        self.speed_ramping_active = False
        self.speed_ramp_start_speed = 0
        self.speed_ramp_target_speed = 0

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
            
            # START-RAMPING
            if self.enable_ramping:
                self.is_ramping_begin = True
                self.ramp_begin_counter = 0
                self.ramp_begin_completed = False
                begin_config = self.ramp_begin_config
                
                start_pct = begin_config.get('start_percentage', 50)
                start_speed = self.current_speed * (start_pct / 100.0)
                
                logger.info(f"Ramping ENABLED - begin: {begin_config.get('steps', 20)} notes")
                logger.info(f"Start ramping from {start_speed:.0f} to {self.current_speed}")
            else:
                logger.info("Ramping DISABLED")
            
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
        self.ramp_begin_completed = False

        self.ramp_begin_counter = 0
        self.ramp_end_counter = 0  
        self.ramp_after_pause_counter = 0
        
        self.pause_count = 0
        self.total_pause_time = 0
        self.speed_ramping_active = False
        self.speed_ramp_start_speed = 0
        self.speed_ramp_target_speed = 0

    def _play_notes(self, notes, timer_func):
        """Main loop for note playback"""
        last_time = 0
        last_note_time = 0
        total_notes = len(notes)
        
        try:
            for i, note in enumerate(notes):
                if not isinstance(note, dict) or 'time' not in note or 'key_lower' not in note:
                    logger.warning(f"Skipping invalid note at index {i}: {note}")
                    continue
                
                if self.stop_event.is_set():
                    logger.info("Playback stopped by user")
                    break

                # END-RAMPING
                if not self.is_ramping_end and i >= total_notes - self.ramp_end_config.get('steps', 16):
                    self.is_ramping_end = True
                    logger.info(f"🎵 End ramping started at note {i}/{total_notes} (last {total_notes - i} notes)")

                current_speed = self._calculate_current_speed(i, total_notes)
                
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
        """🔧 KORRIGIERT: Pausen-Ramping startet von der NEUEN Geschwindigkeit (800) bei 50%"""
        try:
            if self.speed_ramping_active:
                base_speed = self._get_current_actual_speed()
            else:
                base_speed = self.current_speed

            base_speed = max(100, min(1500, base_speed))
            
            ramp_factor = 1.0
            
            # 1. START-RAMPING 
            if self.is_ramping_begin and not self.ramp_begin_completed:
                begin_config = self.ramp_begin_config
                steps = max(1, begin_config.get('steps', 20))
                
                progress = min(1.0, self.ramp_begin_counter / steps)

                start_pct = max(1, begin_config.get('start_percentage', 50))
                end_pct = max(1, begin_config.get('end_percentage', 100))
                
                current_pct = start_pct + (end_pct - start_pct) * progress
                ramp_factor = max(0.01, current_pct / 100.0)
                        
                self.ramp_begin_counter += 1
                if self.ramp_begin_counter >= steps:
                    self.is_ramping_begin = False
                    self.ramp_begin_completed = True
                    logger.info(f"🎵 Start ramping completed")

            # 2. PAUSE-RAMPING
            if self.is_ramping_after_pause:
                after_pause_config = self.ramp_after_pause_config
                steps = max(1, after_pause_config.get('steps', 12))
                
                progress = min(1.0, self.ramp_after_pause_counter / steps)
                
                start_pct = max(1, after_pause_config.get('start_percentage', 50))
                end_pct = max(1, after_pause_config.get('end_percentage', 100))
                
                current_pct = start_pct + (end_pct - start_pct) * progress
                pause_factor = max(0.01, current_pct / 100.0)
                ramp_factor *= pause_factor
                
                # 🔧 DEBUG: Pausen-Ramping Fortschritt loggen
                if self.ramp_after_pause_counter % 3 == 0 or self.ramp_after_pause_counter <= 2:
                    current_effective_speed = base_speed * ramp_factor
                    logger.debug(f"Pause ramping: step {self.ramp_after_pause_counter}/{steps}, "
                            f"progress={progress:.2f}, factor={pause_factor:.2f}, "
                            f"current={current_effective_speed:.0f}")
                
                self.ramp_after_pause_counter += 1
                if self.ramp_after_pause_counter >= steps:
                    self.is_ramping_after_pause = False
                    logger.info("🎵 Pause ramping completed - reached 100% of new speed")

            # 3. END-RAMPING
            if self.is_ramping_end:
                end_config = self.ramp_end_config
                steps = max(1, end_config.get('steps', 16))
                
                notes_remaining = total_notes - note_index
                progress = max(0.0, min(1.0, (steps - notes_remaining) / steps))
                
                start_pct = max(1, end_config.get('start_percentage', 100))
                end_pct = max(1, end_config.get('end_percentage', 50))
                
                current_pct = start_pct + (end_pct - start_pct) * progress
                end_factor = max(0.01, current_pct / 100.0)
                ramp_factor *= end_factor
                
                # Debug-Log
                if notes_remaining <= 5:
                    logger.debug(f"End ramp: note {note_index}/{total_notes}, progress={progress:.2f}, factor={end_factor:.2f}")
                
                if notes_remaining <= 1:
                    self.is_ramping_end = False
                    logger.info("🎵 End ramping completed")

            final_speed = base_speed * ramp_factor
            final_speed = max(100, min(1500, final_speed))
            
            active_ramps = []
            if self.is_ramping_begin: active_ramps.append("START")
            if self.is_ramping_after_pause: active_ramps.append("PAUSE")
            if self.is_ramping_end: active_ramps.append("END")
            if self.speed_ramping_active: active_ramps.append("SPEED")
            
            should_log = (
                active_ramps and (
                    note_index % 50 == 0 or 
                    note_index < 5 or 
                    total_notes - note_index < 5 or
                    (self.is_ramping_after_pause and self.ramp_after_pause_counter <= 3)
                )
            )
            
            if should_log:
                logger.debug(f"Note {note_index}/{total_notes}: {'+'.join(active_ramps)} - "
                            f"base={base_speed:.0f}, total_factor={ramp_factor:.2f}, final={final_speed:.0f}")
            
            return final_speed
            
        except Exception as e:
            logger.error(f"Error in speed calculation: {e}, using safe fallback")
            return max(100, min(1500, self.current_speed))

    def _init_speed_ramping(self, target_speed, current_speed=None):
        """Speed-Ramping Initialisierung"""
        try:
            if current_speed is None:
                current_speed = self.current_speed
            
            target_speed = max(100, min(1500, target_speed))
            current_actual_speed = max(100, min(1500, self._get_current_actual_speed()))
            
            self.speed_ramping_active = True
            self.speed_ramp_start_speed = current_actual_speed
            self.speed_ramp_target_speed = target_speed
            self.speed_ramp_start_time = time.time()
            
            speed_diff = abs(target_speed - current_actual_speed)
            
            base_duration = 4.0  # Basiszeit für kleine Änderungen
            
            if speed_diff <= 100:      # Sehr kleine Änderung (z.B. 1000→1100)
                self.ramp_duration = base_duration * 1.2
            elif speed_diff <= 200:    # Kleine Änderung (z.B. 800→1000)
                self.ramp_duration = base_duration * 1.5
            elif speed_diff <= 400:    # Mittlere Änderung (z.B. 600→1000)
                self.ramp_duration = base_duration * 2.0
            elif speed_diff <= 600:    # Große Änderung (z.B. 600→1200)
                self.ramp_duration = base_duration * 2.8
            elif speed_diff <= 800:    # Sehr große Änderung (z.B. 400→1200)
                self.ramp_duration = base_duration * 3.5
            else:                      # Extreme Änderung (z.B. 200→1500)
                self.ramp_duration = base_duration * 4.5
            
            self.ramp_duration = max(2.0, min(60.0, self.ramp_duration))
            
        except Exception as e:
            logger.error(f"Speed ramping init error: {e}")
            self.current_speed = max(100, min(1500, target_speed))
            self.speed_ramping_active = False

    def _get_current_actual_speed(self):
        if self.speed_ramping_active:
            try:
                elapsed_time = time.time() - self.speed_ramp_start_time
                time_progress = min(1.0, elapsed_time / self.ramp_duration)
                
                eased_progress = 1 - (1 - time_progress) ** 2
                
                current_actual = self.speed_ramp_start_speed + (self.speed_ramp_target_speed - self.speed_ramp_start_speed) * eased_progress
                
                if time_progress >= 1.0:
                    self.speed_ramping_active = False
                    self.current_speed = max(100, min(1500, self.speed_ramp_target_speed))
                    logger.info(f"Speed ramping completed: {self.current_speed}")
                
                return max(100, min(1500, current_actual))
            except Exception as e:
                logger.error(f"Error in actual speed calculation: {e}")
                self.speed_ramping_active = False
                return max(100, min(1500, self.current_speed))
        else:
            return max(100, min(1500, self.current_speed))

    def _wait_with_pause_check(self, wait_time, timer_func):
        """Wait with pause support and timeout protection"""
        wait_start = timer_func()
        max_wait_time = wait_time * 2
        
        while (timer_func() - wait_start) < wait_time:
            if (timer_func() - wait_start) > max_wait_time:
                logger.warning(f"Wait timeout detected: expected {wait_time:.3f}s, actual {(timer_func() - wait_start):.3f}s")
                break
                
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
            else:
                break
                
        return True

    def _handle_pause(self, timer_func):
        ramping_state = self._get_ramping_state()
        
        # Thread-sichere Increments
        with self.status_lock:
            self.pause_count += 1
        pause_start = timer_func()
        
        self._release_all()

        pause_timeout = 3600
        pause_start_time = timer_func()
        
        speed_before_pause = self._get_current_actual_speed()
        
        while self.pause_flag.is_set() and not self.stop_event.is_set():
            if (timer_func() - pause_start_time) > pause_timeout:
                logger.error("Pause timeout exceeded, forcing resume")
                break
            time.sleep(0.05)
            
        if self.stop_event.is_set():
            return False

        pause_duration = timer_func() - pause_start
        
        # Thread Akkumulation
        with self.status_lock:
            self.total_pause_time += pause_duration

        # Pause-Resume Delay
        if self.pause_resume_delay > 0:
            delay_start = timer_func()
            while (timer_func() - delay_start) < self.pause_resume_delay:
                if self.stop_event.is_set():
                    return False
                time.sleep(0.01)

        self._restore_ramping_state(ramping_state)

        current_speed_after_pause = self._get_current_actual_speed()
        speed_changed_during_pause = abs(current_speed_after_pause - speed_before_pause) > 1
        
        if self.enable_ramping and (speed_changed_during_pause or self.is_ramping_after_pause):
            self.is_ramping_after_pause = True
            self.ramp_after_pause_counter = 0
            logger.info(f"Starting pause ramping after resume (speed changed: {speed_changed_during_pause})")
        
        return True

    def _get_ramping_state(self):
        """Get current ramping state"""
        return {
            'begin': self.is_ramping_begin,
            'end': self.is_ramping_end,
            'after_pause': self.is_ramping_after_pause,
            'begin_counter': self.ramp_begin_counter,
            'end_counter': self.ramp_end_counter,
            'after_pause_counter': self.ramp_after_pause_counter,
            'begin_completed': self.ramp_begin_completed,
            'speed_ramping': self.speed_ramping_active,
            'speed_ramp_target': self.speed_ramp_target_speed
        }

    def _restore_ramping_state(self, state):
        """Restores ramping state"""
        self.is_ramping_begin = state['begin']
        self.is_ramping_end = state['end'] 
        self.is_ramping_after_pause = state['after_pause']
        self.ramp_begin_counter = state['begin_counter']
        self.ramp_end_counter = state['end_counter']
        self.ramp_after_pause_counter = state['after_pause_counter']
        self.ramp_begin_completed = state['begin_completed']
        self.speed_ramping_active = state['speed_ramping']
        self.speed_ramp_target_speed = state['speed_ramp_target']

        if self.enable_ramping and not any([state['begin'], state['end'], state['after_pause']]):
            self.is_ramping_after_pause = True
            self.ramp_after_pause_counter = 0

    def _cleanup_playback(self):
        """Tidy up after playback"""
        self._release_all()
        self.playback_active = False
        
        self.speed_ramping_active = False
        
        logger.info(f"Playback finished - Total notes: {self.note_count}, "
                f"Pauses: {self.pause_count}, "
                f"Total pause time: {self.total_pause_time:.2f}s")

    def stop(self):
        """Stop Playback"""
        if not self.playback_active:
            return
            
        self.stop_event.set()
        self.pause_flag.clear()
        self._release_all()
        self.playback_active = False
        self.speed_ramping_active = False

    def set_speed(self, speed):
        try:
            speed = float(speed)
            if speed <= 0:
                logger.warning(f"Invalid speed {speed}, resetting to 1000")
                self.current_speed = 1000
            else:
                self.current_speed = max(100, min(1500, speed))
                
            if self.playback_active and not self.pause_flag.is_set():
                logger.info(f"Speed changed to {speed} during playback (instant)")
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid speed value: {speed}, error: {e}")
            self.current_speed = 1000

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
                            logger.warning(f"Window activation failed after 2 attempts: {e}")
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