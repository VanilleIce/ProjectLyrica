# Copyright (C) 2025-2026 VanilleIce
# All rights reserved.
#
# Project Lyrica is proprietary software.
# Commercial use, redistribution, and modification are prohibited.
# See LICENSE.md for details.

import json
import logging
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from resource_loader import writable_resource_path

logger = logging.getLogger("ProjectLyrica.ConfigManager")

_SETTINGS_FILE_CACHE: Optional[Path] = None


def _get_settings_file() -> Path:
    """Absoluter Pfad zu settings.json (neben EXE bzw. Script,
    oder in einem übergeordneten Ordner falls dort bereits vorhanden)."""
    return Path(writable_resource_path("settings.json"))


def _get_settings_file_cached() -> Path:
    """Lazy-Wrapper: berechnet den Pfad erst beim ersten Zugriff."""
    global _SETTINGS_FILE_CACHE
    if _SETTINGS_FILE_CACHE is None:
        _SETTINGS_FILE_CACHE = _get_settings_file()
    return _SETTINGS_FILE_CACHE


class ConfigManager:
    """Handles application configuration with safe loading and saving."""

    DEFAULT_CONFIG = {
        "game_settings": {
            "sky_exe_path": None
        },

        "playback_settings": {
            "key_press_durations": [0.2, 0.248, 0.3, 0.5, 1.0],
            "speed_presets": [600, 800, 1000, 1200],
            "enable_ramping": False
        },

        "timing_settings": {
            "delays": {
                "initial_delay": 0.8,
                "pause_resume_delay": 1.0
            },
            "ramping": {
                "begin": {
                    "steps": 20
                },
                "end": {
                    "steps": 16
                },
                "after_pause": {
                    "steps": 12
                },
                "speed_change": {
                    "transition_time": 6.0
                }
            }
        },

        "ui_settings": {
            "selected_language": None,
            "keyboard_layout": None,
            "pause_key": "#",
            "reset_speed_key": "+",
            "theme": "dark"
        },

        "key_mapping": {},

        "speed_change_settings": {
            "preset_mappings": [
                {"key": "9", "speed": 600},
                {"key": "0", "speed": 800},
                {"key": "ß", "speed": 1000},
                {"key": "´", "speed": 1200}
            ]
        }
    }

    _config: Optional[Dict[str, Any]] = None
    _config_mtime: float = 0.0
    _lock = threading.RLock()

    # ==================== Pfad-Helper ====================

    @classmethod
    def _settings_file(cls) -> Path:
        """Gibt den (lazy berechneten) absoluten Pfad zu settings.json zurück."""
        return _get_settings_file_cached()

    # ==================== Public API ====================

    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """Get current configuration with file change detection."""
        with cls._lock:
            settings_file = cls._settings_file()
            logger.debug(
                f"get_config: SETTINGS_FILE={settings_file} "
                f"exists={settings_file.exists()}"
            )

            if settings_file.exists():
                try:
                    current_mtime = settings_file.stat().st_mtime
                except OSError:
                    current_mtime = 0.0

                if cls._config is not None and current_mtime == cls._config_mtime:
                    return cls._config

                # Neu laden
                try:
                    if settings_file.stat().st_size > 0:
                        with open(settings_file, 'r', encoding="utf-8") as f:
                            content = f.read().strip()

                        if content:
                            user_config = json.loads(content)
                            if isinstance(user_config, dict):
                                upgraded_config, was_upgraded = cls._upgrade_config(user_config)
                                cls._config = upgraded_config
                                cls._config_mtime = settings_file.stat().st_mtime

                                # Wenn Upgrade was geändert hat → sofort auf Disk speichern
                                if was_upgraded:
                                    logger.info("Config upgraded - persisting changes to disk")
                                    cls._save_config(upgraded_config)

                                return cls._config
                            else:
                                logger.error("Config root is not a dict, recreating defaults")
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    cls._backup_corrupt_file()
                except Exception as e:
                    logger.error(f"Config load error: {e}")

            # Fallback: Defaults
            return cls._create_default_config()

    @classmethod
    def get_value(cls, key: str, default: Any = None) -> Any:
        """Get a config value using dot notation for nested keys."""
        config = cls.get_config()

        value = config
        for k in key.split('.'):
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    @classmethod
    def save(cls, updates: Dict[str, Any]) -> bool:
        """Update and save configuration values while preserving existing ones."""
        with cls._lock:
            try:
                config = cls.get_config().copy()

                def deep_update(original: dict, update: dict) -> dict:
                    for key, value in update.items():
                        if (isinstance(value, dict)
                                and key in original
                                and isinstance(original[key], dict)):
                            original[key] = deep_update(original[key].copy(), value)
                        else:
                            original[key] = value
                    return original

                config = deep_update(config, updates)
                return cls._save_config(config)

            except Exception as e:
                logger.error(f"Failed to update config: {e}")
                return False

    @classmethod
    def reset_to_defaults(cls) -> bool:
        """Reset configuration to default values."""
        with cls._lock:
            try:
                config = json.loads(json.dumps(cls.DEFAULT_CONFIG))
                return cls._save_config(config)
            except Exception as e:
                logger.error(f"Failed to reset config: {e}")
                return False

    @classmethod
    def check_and_handle_missing_custom(cls) -> Tuple[bool, Optional[str]]:
        """Checks whether custom layout has been deleted and resets to default.

        Returns:
            (was_reset, fallback_layout) - was_reset True wenn zurückgesetzt wurde.
        """
        custom_file = Path(writable_resource_path('resources/layouts/CUSTOM.xml'))
        # Fallback: prüfe auch _MEIPASS
        if not custom_file.exists():
            from resource_loader import resource_path
            custom_file = Path(resource_path('resources/layouts/CUSTOM.xml'))

        config = cls.get_config()
        current_layout = config.get("ui_settings", {}).get("keyboard_layout", "")

        if current_layout != "Custom" or custom_file.exists():
            return False, None

        logger.warning("Custom layout is active but CUSTOM.xml is missing!")

        # Lazy import um Circular Import zu vermeiden
        try:
            from language_manager import LanguageManager
            lang_code = config.get("ui_settings", {}).get("selected_language", "en_US")
            fallback_layout = LanguageManager.get_fallback_layout_for_lang(lang_code)
        except Exception as e:
            logger.error(f"Could not determine fallback layout: {e}")
            fallback_layout = "QWERTY"

        cls.save({"ui_settings": {"keyboard_layout": fallback_layout}})
        logger.info(f"Layout reset to {fallback_layout} after custom deletion")

        return True, fallback_layout

    @classmethod
    def log_system_info(cls, version: str):
        """Log detailed system and configuration information."""
        config = cls.get_config()

        ui_settings = config.get("ui_settings", {})
        playback_settings = config.get("playback_settings", {})
        timing_settings = config.get("timing_settings", {})
        speed_change_settings = config.get("speed_change_settings", {})

        timing_ramping = timing_settings.get("ramping", {})
        speed_change_config = timing_ramping.get("speed_change", {})

        lang_code = ui_settings.get("selected_language", "en_US")
        current_layout = ui_settings.get("keyboard_layout", "QWERTY")

        if current_layout == "Custom":
            current_key_map = cls._load_custom_key_mapping()
            layout_display = "Custom"
            default_key_map = {}
        else:
            from language_manager import KeyboardLayoutManager
            default_key_map = KeyboardLayoutManager.load_layout_silently(current_layout)
            current_key_map = config.get("key_mapping", {})
            layout_display = current_layout

        key_map_details = cls._build_key_map_details(
            current_key_map, current_layout, default_key_map
        )

        timing_delays = timing_settings.get("delays", {})

        preset_mappings = speed_change_settings.get("preset_mappings", [])
        preset_info = [
            f"    {m.get('key', '?')} → {m.get('speed', '?')}"
            for m in preset_mappings
        ]

        info = [
            "== Player Config ==",
            f"Language: {lang_code}",
            f"Keyboard Layout: {layout_display}",
            f"Theme: {ui_settings.get('theme')}",
            f"Pause Key: '{ui_settings.get('pause_key')}'",
            f"Reset Speed Key: '{ui_settings.get('reset_speed_key', '+')}'",
            "",
            "== Timing Config ==",
            f"Initial Delay: {timing_delays.get('initial_delay')}s",
            f"Pause/Resume Delay: {timing_delays.get('pause_resume_delay')}s",
            f"Ramp Steps Begin: {timing_ramping.get('begin', {}).get('steps')}",
            f"Ramp Steps End: {timing_ramping.get('end', {}).get('steps')}",
            f"Ramp Steps Pause: {timing_ramping.get('after_pause', {}).get('steps')}",
            "",
            "== Player Settings ==",
            f"Speed Presets: {playback_settings.get('speed_presets')}",
            f"Press Duration Presets: {playback_settings.get('key_press_durations')}",
            f"Enable Ramping: {playback_settings.get('enable_ramping')}",
            "",
            "== Speed Change Settings ==",
            "Preset Mappings:",
            *preset_info,
            "",
            "== Speed Ramping Config (Time-Based) ==",
            f"Transition Time: {speed_change_config.get('transition_time', 6.0)}s",
            "",
            "== Key Mapping ==",
            *key_map_details,
            ""
        ]

        logger.info("Application Config:\n\t" + "\n\t".join(info))
        logger.info("Full configuration logged")

    # ==================== Private Helpers ====================

    @classmethod
    def _backup_corrupt_file(cls):
        """Backup a corrupt config file before recreating."""
        try:
            settings_file = cls._settings_file()
            backup = settings_file.with_suffix('.json.bak')
            if backup.exists():
                backup.unlink()
            settings_file.rename(backup)
            logger.info(f"Backed up corrupt config to {backup.name}")
        except Exception as e:
            logger.error(f"Could not backup corrupt config: {e}")

    @classmethod
    def _create_default_config(cls) -> Dict[str, Any]:
        """Create and save a new config file with defaults safely."""
        with cls._lock:
            config = json.loads(json.dumps(cls.DEFAULT_CONFIG))

            if cls._save_config(config):
                logger.info("Created new config file with defaults")
            else:
                logger.error("Failed to save default config")

            return config

    @classmethod
    def _save_config(cls, config: Dict[str, Any]) -> bool:
        """Internal method to save config to file (must be called with lock held)."""
        try:
            settings_file = cls._settings_file()
            settings_file.parent.mkdir(parents=True, exist_ok=True)

            # Atomisches Schreiben: erst temp, dann rename
            tmp_file = settings_file.with_suffix('.json.tmp')
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            tmp_file.replace(settings_file)

            cls._config = config

            try:
                cls._config_mtime = settings_file.stat().st_mtime
            except OSError:
                cls._config_mtime = time.time()

            return True

        except Exception as e:
            logger.error(f"Save failed: {e}")
            return False

    @classmethod
    def _load_custom_key_mapping(cls) -> Dict[str, str]:
        """Lädt Key-Mapping aus CUSTOM.xml."""
        # Erst neben EXE suchen (beschreibbar)
        custom_file = Path(writable_resource_path('resources/layouts/CUSTOM.xml'))
        if not custom_file.exists():
            # Fallback: im _MEIPASS
            from resource_loader import resource_path
            custom_file = Path(resource_path('resources/layouts/CUSTOM.xml'))
        if not custom_file.exists():
            return {}

        try:
            tree = ET.parse(custom_file)
            mapping = {}
            for key in tree.findall('key'):
                key_id = key.get('id')
                key_text = key.text.strip() if key.text else ""
                if key_id:
                    mapping[key_id] = key_text
            return mapping
        except Exception as e:
            logger.error(f"Could not parse CUSTOM.xml: {e}")
            return {}

    @classmethod
    def _build_key_map_details(cls, current_key_map: Dict[str, str],
                               current_layout: str,
                               default_key_map: Dict[str, str]) -> list:
        """Erstellt formatierte Key-Mapping-Details für Logging."""
        details = []
        for key in sorted(current_key_map.keys()):
            current_val = current_key_map[key]
            if current_layout == "Custom":
                details.append(f"  {key}: {current_val}")
            else:
                default_val = default_key_map.get(key, "")
                if current_val == default_val:
                    details.append(f"  {key}: {current_val} (default)")
                else:
                    details.append(f"  {key}: {current_val} (modified from '{default_val}')")
        return details

    @classmethod
    def _upgrade_config(cls, config: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        """Upgrade existing config to latest version and migrate old values.

        Returns:
            Tuple: (upgraded_config, was_upgraded)
        """
        upgraded = False

        # --- Migration: alte Top-Level Keys → neue Sektionen ---

        migrations = [
            ("sky_exe_path", "game_settings", "sky_exe_path"),
            ("pause_key", "ui_settings", "pause_key"),
            ("selected_language", "ui_settings", "selected_language"),
            ("keyboard_layout", "ui_settings", "keyboard_layout"),
            ("theme", "ui_settings", "theme"),
            ("key_press_durations", "playback_settings", "key_press_durations"),
            ("speed_presets", "playback_settings", "speed_presets"),
            ("enable_ramping", "playback_settings", "enable_ramping"),
        ]

        for old_key, section, new_key in migrations:
            if old_key in config:
                if section not in config:
                    config[section] = {}
                if config[section].get(new_key) is None or not config[section].get(new_key):
                    config[section][new_key] = config[old_key]
                    upgraded = True

        # Alte timing_config → timing_settings
        if "timing_config" in config and "timing_settings" not in config:
            old_timing = config["timing_config"]
            config["timing_settings"] = {
                "delays": {
                    "initial_delay": old_timing.get("initial_delay", 0.8),
                    "pause_resume_delay": old_timing.get("pause_resume_delay", 1.0)
                },
                "ramping": {
                    "begin": {
                        "steps": old_timing.get("ramp_steps_begin", 20)
                    },
                    "end": {
                        "steps": old_timing.get("ramp_steps_end", 16)
                    },
                    "after_pause": {
                        "steps": old_timing.get("ramp_steps_after_pause", 12)
                    },
                    "speed_change": {
                        "transition_time": 6.0
                    }
                }
            }
            del config["timing_config"]
            upgraded = True

        # speed_change_settings Migration
        if "speed_change_settings" not in config:
            config["speed_change_settings"] = json.loads(
                json.dumps(cls.DEFAULT_CONFIG["speed_change_settings"])
            )
            upgraded = True
        else:
            scs = config["speed_change_settings"]

            if "preset_keys" in scs and "preset_mappings" not in scs:
                preset_keys = scs.get("preset_keys", ["1", "2", "3", "4"])
                speed_presets = config.get("playback_settings", {}).get(
                    "speed_presets", [600, 800, 1000, 1200]
                )
                scs["preset_mappings"] = [
                    {"key": key, "speed": speed_presets[i]}
                    for i, key in enumerate(preset_keys)
                    if i < len(speed_presets)
                ]
                del scs["preset_keys"]
                upgraded = True

            for key in ["ramping", "step_size", "enabled", "mode", "increment_keys"]:
                if key in scs:
                    del scs[key]
                    upgraded = True

            if "preset_mappings" not in scs:
                scs["preset_mappings"] = json.loads(
                    json.dumps(cls.DEFAULT_CONFIG["speed_change_settings"]["preset_mappings"])
                )
                upgraded = True

        # --- Struktur sicherstellen: alle Sektionen und Keys vorhanden ---
        # Deep-Merge: fügt fehlende Keys rekursiv hinzu (auch verschachtelte!)
        def deep_merge_defaults(target: dict, defaults: dict) -> bool:
            """Fügt fehlende Keys aus `defaults` in `target` rekursiv ein.

            Returns:
                True wenn etwas hinzugefügt wurde.
            """
            changed = False
            for key, default_value in defaults.items():
                if key not in target:
                    # Komplett fehlend → hinzufügen
                    target[key] = (
                        json.loads(json.dumps(default_value))
                        if isinstance(default_value, (dict, list))
                        else default_value
                    )
                    changed = True
                elif isinstance(default_value, dict) and isinstance(target[key], dict):
                    # Beide Dicts → rekursiv weiter
                    if deep_merge_defaults(target[key], default_value):
                        changed = True
            return changed

        if deep_merge_defaults(config, cls.DEFAULT_CONFIG):
            upgraded = True

        # --- Alte Top-Level Keys entfernen ---
        old_keys = [
            "sky_exe_path", "pause_key",
            "key_press_durations", "speed_presets", "enable_ramping",
            "selected_language", "keyboard_layout", "theme", "ramping_info_display_count",
        ]
        for key in old_keys:
            if key in config:
                del config[key]
                upgraded = True

        # --- Cleanup: start_percentage/end_percentage aus Ramping entfernen ---
        # Diese Werte waren zeitweise in der Config, gehören aber nicht mehr rein
        # (sind hardcoded in music_player.py)
        if "timing_settings" in config:
            ramping = config["timing_settings"].get("ramping", {})
            if isinstance(ramping, dict):
                for phase in ("begin", "end", "after_pause"):
                    phase_config = ramping.get(phase)
                    if isinstance(phase_config, dict):
                        if "start_percentage" in phase_config:
                            del phase_config["start_percentage"]
                            upgraded = True
                        if "end_percentage" in phase_config:
                            del phase_config["end_percentage"]
                            upgraded = True

        if upgraded:
            logger.info("Upgraded config to new structure")

        return config, upgraded