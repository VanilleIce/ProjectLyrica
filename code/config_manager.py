# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import json
from pathlib import Path
import logging
import traceback
from typing import Any, Dict

logger = logging.getLogger("ProjectLyrica.ConfigManager")

class ConfigManager:
    """Handles application configuration with safe loading and saving."""
    
    SETTINGS_FILE = Path('settings.json')
    
    DEFAULT_CONFIG = {
        "key_press_durations": [0.2, 0.248, 0.3, 0.5, 1.0],
        "speed_presets": [600, 800, 1000, 1200],
        "selected_language": None,
        "keyboard_layout": None,
        "key_mapping": {},
        "timing_config": {
            "initial_delay": 0.8,
            "pause_resume_delay": 1.0,
            "ramp_steps_begin": 20,
            "ramp_steps_end": 16,
            "ramp_steps_after_pause": 12
        },
        "pause_key": "#",
        "theme": "dark",
        "enable_ramping": False,
        "ramping_info_display_count": 0,
        "sky_exe_path": None
    }

    _config = None

    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """Get the current configuration with fallback to defaults."""
        if cls._config is not None:
            return cls._config
            
        try:
            if cls.SETTINGS_FILE.exists():
                try:
                    with open(cls.SETTINGS_FILE, 'r', encoding="utf-8") as f:
                        user_config = json.load(f)
                        
                    if isinstance(user_config, dict):
                        cls._config = cls._upgrade_config(user_config)
                        return cls._config
                except Exception as e:
                    logger.error(f"Error loading config: {e}")

            cls._config = cls._create_default_config()
            return cls._config
            
        except Exception as e:
            logger.critical(f"Critical config error: {e}\n{traceback.format_exc()}")
            return cls.DEFAULT_CONFIG.copy()

    @classmethod
    def _create_default_config(cls) -> Dict[str, Any]:
        """Create and save a new config file with defaults"""
        config = cls.DEFAULT_CONFIG.copy()
        try:
            cls.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(cls.SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logger.info("Created new config file with defaults")
        except Exception as e:
            logger.error(f"Failed to create config file: {e}")
        return config

    @classmethod
    def _upgrade_config(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """Upgrade existing config to latest version"""
        upgraded = False

        for key, default_value in cls.DEFAULT_CONFIG.items():
            if key not in config:
                config[key] = default_value
                upgraded = True
                logger.info(f"Added missing top-level key: {key}")

        timing_config = config.get("timing_config", {})
        default_timing = cls.DEFAULT_CONFIG["timing_config"]
        
        for key, default_value in default_timing.items():
            if key not in timing_config:
                timing_config[key] = default_value
                upgraded = True
                logger.info(f"Added missing timing key: {key}")
        
        config["timing_config"] = timing_config

        if upgraded:
            try:
                with open(cls.SETTINGS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                logger.info("Upgraded config file to latest version")
            except Exception as e:
                logger.error(f"Failed to save upgraded config: {e}")
        
        return config

    @classmethod
    def save(cls, updates: Dict[str, Any]) -> bool:
        """Update and save configuration values."""
        try:
            config = cls.get_config().copy()

            for key, value in updates.items():
                if key == "timing_config":
                    if "timing_config" not in config:
                        config["timing_config"] = {}
                    config["timing_config"].update(value)
                elif key == "key_mapping":
                    config["key_mapping"] = value
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