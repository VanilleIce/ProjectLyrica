# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import json, logging, traceback
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("ProjectLyrica.ConfigManager")

class ConfigManager:
    """Handles application configuration with safe loading and saving."""
    
    SETTINGS_FILE = Path('settings.json')

    DEFAULT_CONFIG = {

        "_comment": "Game execution settings",
        "game_settings": {
            "sky_exe_path": None
        },
        
        "_comment": "Playback behavior settings", 
        "playback_settings": {
            "key_press_durations": [0.2, 0.248, 0.3, 0.5, 1.0],
            "speed_presets": [600, 800, 1000, 1200],
            "enable_ramping": False
        },
        
        "timing_settings": {
            "_comment": "Timing and ramping configuration",
            "delays": {
                "_comment": "Delay timings in seconds",
                "initial_delay": 0.8,
                "pause_resume_delay": 1.0
            },
            "ramping": {
                "_comment": "Smooth speed transition settings. start_percentage: beginning speed in %",
                "begin": {
                    "_comment": "Ramping at playback start",
                    "steps": 20,
                    "start_percentage": 50,
                    "end_percentage": 100
                },

                "end": {
                    "_comment": "Ramping at playback end", 
                    "steps": 16,
                    "start_percentage": 100,
                    "end_percentage": 50
                },

                "after_pause": {
                    "_comment": "Ramping after pause/resume",
                    "steps": 12,
                    "start_percentage": 50,
                    "end_percentage": 100
                }
            }
        },

        "ui_settings": {
            "_comment": "User interface settings",
            "selected_language": None,
            "keyboard_layout": None,
            "pause_key": "#",
            "theme": "dark"
        },
        
        "key_mapping": {},
        
        "ramping_info_display_count": {
            "_comment": "Internal counter for info display",
            "value": 0
        }
    }

    _config = None

    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """Get the current configuration with fallback to defaults."""
        if cls._config is not None:
            return cls._config
            
        try:
            if cls.SETTINGS_FILE.exists() and cls.SETTINGS_FILE.stat().st_size > 0:
                try:
                    with open(cls.SETTINGS_FILE, 'r', encoding="utf-8") as f:
                        content = f.read().strip()
                        
                    if not content:
                        logger.warning("Config file is empty, recreating with defaults")
                        return cls._create_default_config()
                        
                    user_config = json.loads(content)
                    config_path = str(cls.SETTINGS_FILE.absolute()).replace(str(Path.home()), "~")
                    logger.info(f"Loaded config from {config_path}")
                        
                    if isinstance(user_config, dict):
                        cls._config = cls._upgrade_config(user_config)
                        return cls._config
                    else:
                        logger.error("Config file is not a dictionary, recreating with defaults")
                        return cls._create_default_config()
                        
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error in config file: {e}")
                    backup_file = cls.SETTINGS_FILE.with_suffix('.json.bak')
                    try:
                        cls.SETTINGS_FILE.rename(backup_file)
                        backup_path = str(backup_file.absolute()).replace(str(Path.home()), "~")
                        logger.info(f"Backed up corrupt config to {backup_path}")
                    except Exception as backup_error:
                        logger.error(f"Could not backup corrupt config: {backup_error}")
                    
                    return cls._create_default_config()
                except Exception as e:
                    logger.error(f"Error loading config: {e}")
                    return cls._create_default_config()

            return cls._create_default_config()
            
        except Exception as e:
            logger.critical(f"Critical config error: {e}\n{traceback.format_exc()}")
            return cls.DEFAULT_CONFIG.copy()

    @classmethod
    def _create_default_config(cls) -> Dict[str, Any]:
        """Create and save a new config file with defaults safely"""
        config = cls.DEFAULT_CONFIG.copy()
        try:
            cls.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)

            if cls._save_config(config):
                logger.info("Created new config file with defaults")
            else:
                logger.error("Failed to save default config")
                
            return config
        except Exception as e:
            logger.error(f"Failed to create config file: {e}")
            return config

    @classmethod
    def _upgrade_config(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """Upgrade existing config to latest version and migrate old values"""
        upgraded = False

        if "sky_exe_path" in config:
            if "game_settings" not in config:
                config["game_settings"] = {}
            if config["game_settings"].get("sky_exe_path") is None:
                config["game_settings"]["sky_exe_path"] = config["sky_exe_path"]
                upgraded = True
        
        if "pause_key" in config:
            if "ui_settings" not in config:
                config["ui_settings"] = {}
            if config["ui_settings"].get("pause_key") is None:
                config["ui_settings"]["pause_key"] = config["pause_key"]
                upgraded = True

        if "key_press_durations" in config:
            if "playback_settings" not in config:
                config["playback_settings"] = {}
            if not config["playback_settings"].get("key_press_durations"):
                config["playback_settings"]["key_press_durations"] = config["key_press_durations"]
                upgraded = True
        
        if "speed_presets" in config:
            if "playback_settings" not in config:
                config["playback_settings"] = {}
            if not config["playback_settings"].get("speed_presets"):
                config["playback_settings"]["speed_presets"] = config["speed_presets"]
                upgraded = True
        
        if "enable_ramping" in config:
            if "playback_settings" not in config:
                config["playback_settings"] = {}
            if config["playback_settings"].get("enable_ramping") is None:
                config["playback_settings"]["enable_ramping"] = config["enable_ramping"]
                upgraded = True

        if "selected_language" in config:
            if "ui_settings" not in config:
                config["ui_settings"] = {}
            if config["ui_settings"].get("selected_language") is None:
                config["ui_settings"]["selected_language"] = config["selected_language"]
                upgraded = True
        
        if "keyboard_layout" in config:
            if "ui_settings" not in config:
                config["ui_settings"] = {}
            if config["ui_settings"].get("keyboard_layout") is None:
                config["ui_settings"]["keyboard_layout"] = config["keyboard_layout"]
                upgraded = True
        
        if "theme" in config:
            if "ui_settings" not in config:
                config["ui_settings"] = {}
            if config["ui_settings"].get("theme") is None:
                config["ui_settings"]["theme"] = config["theme"]
                upgraded = True

        if "ramping_info_display_count" in config and isinstance(config["ramping_info_display_count"], int):
            old_value = config["ramping_info_display_count"]
            config["ramping_info_display_count"] = {"value": old_value}
            logger.info(f"Migrated ramping_info_display_count from {old_value} to new structure")
            upgraded = True

        if "timing_config" in config and "timing_settings" not in config:
            old_timing = config["timing_config"]
            config["timing_settings"] = {
                "delays": {
                    "initial_delay": old_timing.get("initial_delay", 0.8),
                    "pause_resume_delay": old_timing.get("pause_resume_delay", 1.0)
                },
                "ramping": {
                    "begin": {
                        "steps": old_timing.get("ramp_steps_begin", 20),
                        "start_percentage": 50,
                        "end_percentage": 100
                    },
                    "end": {
                        "steps": old_timing.get("ramp_steps_end", 16),
                        "start_percentage": 100,
                        "end_percentage": 50
                    },
                    "after_pause": {
                        "steps": old_timing.get("ramp_steps_after_pause", 12),
                        "start_percentage": 50,
                        "end_percentage": 100
                    }
                }
            }
            del config["timing_config"]
            upgraded = True

        new_structure = {
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
                    "begin": {"steps": 20, "start_percentage": 50, "end_percentage": 100},
                    "end": {"steps": 16, "start_percentage": 100, "end_percentage": 50},
                    "after_pause": {"steps": 12, "start_percentage": 50, "end_percentage": 100}
                }
            },
            "ui_settings": {
                "selected_language": None,
                "keyboard_layout": None,
                "pause_key": "#",
                "theme": "dark"
            },
            "key_mapping": {},
            "ramping_info_display_count": {"value": 0}
        }

        for section, default_values in new_structure.items():
            if section not in config:
                config[section] = default_values.copy() if isinstance(default_values, dict) else default_values
                upgraded = True
            elif isinstance(default_values, dict) and isinstance(config[section], dict):
                for key, default_value in default_values.items():
                    if key not in config[section]:
                        config[section][key] = default_value.copy() if isinstance(default_value, dict) else default_value
                        upgraded = True

        old_keys_to_remove = [
            "sky_exe_path", "pause_key", 
            "key_press_durations", "speed_presets", "enable_ramping",
            "selected_language", "keyboard_layout", "theme"
        ]
        
        for key in old_keys_to_remove:
            if key in config:
                del config[key]
                upgraded = True

        if upgraded:
            try:
                with open(cls.SETTINGS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                logger.info("Upgraded config file to new structure and migrated old values")
            except Exception as e:
                logger.error(f"Failed to save upgraded config: {e}")

        return config

    @classmethod
    def save(cls, updates: Dict[str, Any]) -> bool:
        """Update and save configuration values while preserving existing ones."""
        try:
            config = cls.get_config().copy()

            for key, value in updates.items():
                if isinstance(value, dict) and key in config and isinstance(config[key], dict):
                    config[key].update(value)
                else:
                    config[key] = value

            return cls._save_config(config)
            
        except Exception as e:
            logger.error(f"Failed to update config: {e}\n{traceback.format_exc()}")
            return False

    @classmethod
    def _save_config(cls, config: Dict[str, Any]) -> bool:
        """Internal method to save config to file"""
        try:
            logger.debug("Saving configuration")
            cls.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            
            with open(cls.SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
                
            cls._config = config
            return True
        except Exception as e:
            logger.error(f"Save failed: {e}\n{traceback.format_exc()}")
            return False

    @classmethod
    def get_value(cls, key: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation for nested keys."""
        try:
            config = cls.get_config()

            keys = key.split('.')
            value = config
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
                    
            return value
        except Exception as e:
            logger.error(f"Error getting config value {key}: {e}")
            return default

    @classmethod
    def reset_to_defaults(cls) -> bool:
        """Reset configuration to default values."""
        try:
            cls._config = cls.DEFAULT_CONFIG.copy()
            return cls._save_config(cls._config)
        except Exception as e:
            logger.error(f"Failed to reset config: {e}")
            return False

    @classmethod
    def log_system_info(cls, version: str):
        """Log detailed system and configuration information."""
        config = cls.get_config()

        ui_settings = config.get("ui_settings", {})
        game_settings = config.get("game_settings", {})
        playback_settings = config.get("playback_settings", {})
        timing_settings = config.get("timing_settings", {})
        
        lang_code = ui_settings.get("selected_language", "en_US")
        
        try:
            from language_manager import LanguageManager, KeyboardLayoutManager
            
            languages = LanguageManager.get_languages()
            layout = next((lyt for code, _, lyt in languages if code == lang_code), "QWERTY")

            default_key_map = KeyboardLayoutManager.load_layout_silently(layout)
            current_key_map = config.get("key_mapping", {})
            
            is_custom = current_key_map != default_key_map

            key_map_details = []
            relevant_keys = set(default_key_map.keys()).intersection(set(current_key_map.keys()))
            
            for key in sorted(relevant_keys):
                current_val = current_key_map[key]
                default_val = default_key_map[key]
                
                if current_val == default_val:
                    key_map_details.append(f"  {key}: {current_val} (default)")
                else:
                    key_map_details.append(f"  {key}: {current_val} (modified from '{default_val}')")

            if is_custom:
                layout_display = f"Custom ({layout})"
            else:
                layout_display = layout
                
        except Exception as e:
            logger.error(f"Key mapping analysis error: {e}")
            key_map_details = ["  [Error: Could not analyze key mapping]"]
            layout_display = "Error"

        timing_delays = timing_settings.get("delays", {})
        timing_ramping = timing_settings.get("ramping", {})
        
        info = [
            "== Player Config ==",
            f"Language: {lang_code}",
            f"Keyboard Layout: {layout_display}",
            f"Theme: {ui_settings.get('theme')}",
            "",
            "== Timing Config ==",
            f"Initial Delay: {timing_delays.get('initial_delay')}s",
            f"Pause/Resume Delay: {timing_delays.get('pause_resume_delay')}s",
            f"Ramp Steps Begin: {timing_ramping.get('begin', {}).get('steps')}",
            f"Ramp Steps End: {timing_ramping.get('end', {}).get('steps')}",
            f"Ramp Steps Pause: {timing_ramping.get('after_pause', {}).get('steps')}",
            "",
            "== Player Settings ==",
            f"Pause Key: '{ui_settings.get('pause_key')}'",
            f"Speed Presets: {playback_settings.get('speed_presets')}",
            f"Press Duration Presets: {playback_settings.get('key_press_durations')}",
            f"Enable Ramping: {playback_settings.get('enable_ramping')}",
            f"Ramping Info Display Count: {config.get('ramping_info_display_count', {}).get('value')}",
            "",
            "== Key Mapping ==",
            *key_map_details
        ]

        try:
            logger.info("Application Config:\n\t" + "\n\t".join(info))
        except UnicodeEncodeError:
            cleaned_info = [line.encode('ascii', 'replace').decode('ascii') for line in info]
            logger.info("Application Config (ASCII-safe):\n\t" + "\n\t".join(cleaned_info))
        
        logger.info("Full configuration logged")