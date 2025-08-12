# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import json
import time
import logging
from pathlib import Path
from threading import Event, Lock
from pynput.keyboard import Controller
import pygetwindow as gw
import psutil
from tkinter import messagebox

from language_manager import LanguageManager
from config_manager import ConfigManager
from note_scheduler import NoteScheduler

logger = logging.getLogger("ProjectLyrica.MusicPlayer")

class MusicPlayer:
    def __init__(self):
        try:
            self.logger = logging.getLogger("ProjectLyrica.MusicPlayer")
            config = ConfigManager.get_config()

            self.keyboard = Controller()
            self.pause_flag = Event()
            self.stop_event = Event()
            self.song_cache = {}
            self.status_lock = Lock()

            self.scheduler = NoteScheduler(self._release_key)
            
            self._initialize_key_mapping(config)
            self._initialize_timing(config)
            self._initialize_playback_state()
            
        except Exception as e:
            logger.critical(f"Initialization failed: {e}", exc_info=True)
            raise

    def _initialize_key_mapping(self, config):
        """Initialize keyboard mapping from config"""
        self.key_map = {}
        for prefix in ['', '1', '2', '3']:
            for key, value in config["key_mapping"].items():
                try:
                    if isinstance(value, str) and '\\u' in value:
                        value = bytes(value, 'latin1').decode('unicode_escape')
                    self.key_map[f"{prefix}{key}".lower()] = value
                except Exception as e:
                    logger.error(f"Key mapping error for {key}: {value} - {e}")
                    self.key_map[f"{prefix}{key}".lower()] = value

    def _initialize_timing(self, config):
        """Initialize timing parameters from config"""
        timing = config["timing_config"]
        self.press_duration = 0.1
        self.current_speed = 1000
        self.initial_delay = timing["initial_delay"]
        self.pause_resume_delay = timing["pause_resume_delay"]
        self.ramp_steps_begin = timing["ramp_steps_begin"]
        self.ramp_steps_end = timing["ramp_steps_end"]
        self.ramp_steps_after_pause = timing["ramp_steps_after_pause"]
        self.enable_ramping = config.get("enable_ramping", False)

    def _initialize_playback_state(self):
        """Initialize playback state variables"""
        self.playback_active = False
        self.is_ramping_begin = False
        self.is_ramping_end = False
        self.is_ramping_after_pause = False
        self.ramp_counter = 0
        self.start_time = 0
        self.note_count = 0
        self.pause_count = 0
        self.pause_start = 0
        self.total_pause_time = 0

    def parse_song(self, path):
        self.logger.debug(f"Parsing song: {path}")
        if path in self.song_cache:
            return self.song_cache[path]
        
        file = Path(path)
        try:
            try:
                content = file.read_text(encoding='utf-16')
            except UnicodeDecodeError:
                content = file.read_text(encoding='utf-8')
            
            if content.startswith('\ufeff'):
                content = content[1:]
            
            # Parse JSON content
            data = json.loads(content)
            
            # Handle single-item array format
            song_data = data[0] if isinstance(data, list) and data else data
            
            # Extract notes
            if "songNotes" in song_data:
                pass
            elif "notes" in song_data:
                song_data["songNotes"] = song_data["notes"]
            elif "Notes" in song_data:
                song_data["songNotes"] = song_data["Notes"]
            else:
                raise ValueError(LanguageManager.get('missing_song_notes'))
            
            # Get title
            song_data["songTitle"] = song_data.get("name", song_data.get("title", "Unknown"))
            
            # Prepare notes
            for note in song_data["songNotes"]:
                note['key_lower'] = note.get('key', '').lower()
            
            # Cache and return
            self.song_cache[path] = song_data
            return song_data
            
        except Exception as e:
            self.logger.error(f"Song parse error [{path}]: {e}", exc_info=True)
            error_msg = LanguageManager.get('invalid_song_format')
            raise ValueError(f"{error_msg}: {str(e)}")

    def play(self, song_data):
        try:
            self.logger.info("Starting song playback")
            if self.playback_active:
                self.stop()
        
            self.scheduler.restart()
            self.playback_active = True
            self.pause_enabled = True
            self.scheduler.reset()
            self.stop_event.clear()

            notes = song_data.get("songNotes", [])
            if not notes:
                logger.error("No notes found in song data")
                messagebox.showerror(LanguageManager.get("error_title"), LanguageManager.get("missing_song_notes"))
                return

            self.is_ramping_begin = False
            self.is_ramping_end = False
            self.is_ramping_after_pause = False
            self.ramp_counter = 0

            if self.enable_ramping:
                self.is_ramping_begin = True
                self.ramp_counter = 0
            
            self.pause_count = 0
            self.total_pause_time = 0
            self.note_count = len(notes)
            
            song_title = song_data.get("songTitle", "Unknown")
            logger.info(f"Playing song: '{song_title}' with {self.note_count} notes at speed {self.current_speed}")

            from time import perf_counter as precision_timer

            time.sleep(self.initial_delay)
            
            self.start_time = precision_timer()
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

                    current_speed = self.current_speed
                    if self.enable_ramping:
                        if self.is_ramping_after_pause:
                            ramp_factor = 0.5 + 0.5 * (self.ramp_counter / self.ramp_steps_after_pause)
                            current_speed = max(500, self.current_speed * min(1.0, ramp_factor))
                            self.ramp_counter += 1

                            if self.ramp_counter >= self.ramp_steps_after_pause:
                                self.is_ramping_after_pause = False
                                logger.debug(f"Post-pause ramping completed after {self.ramp_steps_after_pause} notes")
                                
                        elif self.is_ramping_begin:
                            ramp_factor = 0.5 + 0.5 * (self.ramp_counter / self.ramp_steps_begin)
                            current_speed = max(500, self.current_speed * min(1.0, ramp_factor))
                            self.ramp_counter += 1
                            
                            if self.ramp_counter >= self.ramp_steps_begin:
                                self.is_ramping_begin = False
                                logger.debug(f"Beginning ramping completed after {self.ramp_steps_begin} notes")
                                
                        elif i >= len(notes) - self.ramp_steps_end:
                            progress = (len(notes) - i) / self.ramp_steps_end
                            ramp_factor = max(0.5, progress)
                            current_speed = max(500, self.current_speed * ramp_factor)
                            
                            if not self.is_ramping_end:
                                self.is_ramping_end = True
                                logger.debug(f"End ramping started for {self.ramp_steps_end} notes")

                    if current_speed <= 0:
                        logger.warning(f"Invalid speed {current_speed}, resetting to 1000")
                        current_speed = 1000

                    current_time = precision_timer()
                    if last_note_time > 0:
                        elapsed_since_last = current_time - last_note_time
                        required_interval = (note['time'] - last_time) / 1000 * (1000 / current_speed)
                        remaining_wait = max(0, required_interval - elapsed_since_last)

                        wait_start = precision_timer()
                        while (precision_timer() - wait_start) < remaining_wait:
                            if self.stop_event.is_set():
                                break

                            if self.pause_flag.is_set():
                                ramping_state = {
                                    'begin': self.is_ramping_begin,
                                    'end': self.is_ramping_end,
                                    'after_pause': self.is_ramping_after_pause,
                                    'counter': self.ramp_counter
                                }
                                
                                with self.status_lock:
                                    self.pause_count += 1
                                self.pause_start = precision_timer()
                                self._release_all()

                                while self.pause_flag.is_set() and not self.stop_event.is_set():
                                    time.sleep(0.05)
                                
                                if self.stop_event.is_set():
                                    break

                                pause_duration = precision_timer() - self.pause_start
                                self.total_pause_time += pause_duration

                                if self.pause_resume_delay > 0:
                                    logger.debug(f"Applying pause-resume delay: {self.pause_resume_delay}s")
                                    delay_start = precision_timer()
                                    while (precision_timer() - delay_start) < self.pause_resume_delay:
                                        if self.stop_event.is_set():
                                            break
                                        time.sleep(0.01)
                                    
                                    if self.stop_event.is_set():
                                        break

                                self.is_ramping_begin = ramping_state['begin']
                                self.is_ramping_end = ramping_state['end']
                                self.is_ramping_after_pause = ramping_state['after_pause']
                                self.ramp_counter = ramping_state['counter']

                                if self.enable_ramping:
                                    any_ramp_active = (
                                        ramping_state['begin'] or 
                                        ramping_state['end'] or 
                                        ramping_state['after_pause']
                                    )
                                    
                                    if not any_ramp_active:
                                        self.is_ramping_after_pause = True
                                        self.ramp_counter = 0
                                        logger.debug(f"Starting post-pause ramping for {self.ramp_steps_after_pause} notes")
                                    else:
                                        logger.debug("Resuming existing ramping after pause")

                                current_time = precision_timer()
                                last_note_time = current_time
                                last_time = note['time']
                                break

                            time_left = remaining_wait - (precision_timer() - wait_start)
                            if time_left > 0.005:
                                time.sleep(min(time_left * 0.5, 0.01))
                    
                    if self.stop_event.is_set():
                        break

                    key = note.get('key_lower', '')
                    if key:
                        mapped_key = self.key_map.get(key.lower())
                        if mapped_key:
                            try:
                                self.keyboard.press(mapped_key)
                                self.scheduler.add(mapped_key, self.press_duration)
                                logger.debug(f"Pressed key: {mapped_key} for note {i+1}/{self.note_count}")
                            except Exception as e:
                                logger.error(f"Key press error: {e}")

                    last_time = note['time']
                    last_note_time = precision_timer()

                    if i == len(notes) - 1:
                        time.sleep(self.press_duration)
                        
            except Exception as e:
                logger.error(f"Unexpected playback error: {e}", exc_info=True)
            finally:
                self._release_all()
                self.playback_active = False
                self.pause_enabled = False
        except Exception as e:
            logger.critical(f"Playback initialization failed: {e}", exc_info=True)
            self._release_all()
            raise

    def stop(self):
        if not self.playback_active:
            return
            
        self.stop_event.set()
        self.pause_flag.clear()
        self.pause_enabled = False
        self._release_all()
        self.playback_active = False

    def set_speed(self, speed):
        if speed <= 0:
            logger.warning(f"Invalid speed {speed}, resetting to 1000")
            self.current_speed = 1000
        else:
            self.current_speed = speed

    def _release_all(self):
        if hasattr(self, 'scheduler'):
            self.scheduler.reset()
        for key in set(self.key_map.values()):
            try: 
                self.keyboard.release(key)
            except Exception as e: 
                logger.error(f"Key release error: {e}")

    def _find_sky_window(self):
        try:
            exe_path = ConfigManager.get_value("sky_exe_path", "")
            if not exe_path:
                logger.error("No Sky.exe path in settings.json!")
                return None

            target_exe_name = Path(exe_path).name.lower()

            for proc in psutil.process_iter(['name', 'exe']):
                try:
                    if proc.info['name'].lower() == target_exe_name or \
                       (proc.info['exe'] and Path(proc.info['exe']).name.lower() == target_exe_name):
                        windows = gw.getWindowsWithTitle("Sky")
                        if windows:
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
        try:
            if not isinstance(window, gw.Window):
                logger.error("Invalid window object provided")
                return False
                
            if window.isMinimized: 
                window.restore()
            if not window.isActive:
                for _ in range(3):
                    try:
                        window.activate()
                        time.sleep(0.1)
                        if window.isActive:
                            break
                    except Exception as e:
                        logger.warning(f"Window activation attempt failed: {e}")
                        continue
            return window.isActive
        except Exception as e:
            logger.error(f"Window focus error: {e}")
            return False

    def _release_key(self, key):
        try:
            self.keyboard.release(key)
        except Exception as e:
            logger.error(f"Key release error in scheduler: {e}")