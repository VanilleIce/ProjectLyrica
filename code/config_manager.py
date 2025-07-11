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
            "pause_resume_delay": 1.2,
            "ramp_steps_begin": 20,
            "ramp_steps_end": 15
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
            if not cls.SETTINGS_FILE.exists():
                cls._config = cls.DEFAULT_CONFIG.copy()
                cls._save_config(cls._config)
                return cls._config
                
            with open(cls.SETTINGS_FILE, 'r', encoding="utf-8") as f:
                user_config = json.load(f)
                
            if not isinstance(user_config, dict):
                raise ValueError("Config file must contain a JSON object")
                
            config = cls._merge_configs(cls.DEFAULT_CONFIG.copy(), user_config)
            cls._config = config
            return config
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            return cls._reset_to_defaults()
        except Exception as e:
            logger.error(f"Failed to load config: {e}\n{traceback.format_exc()}")
            return cls._reset_to_defaults()

    @classmethod
    def _merge_configs(cls, base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge that properly handles key_mapping"""
        result = base.copy()
        
        for key, value in updates.items():
            if key == "key_mapping":
                result[key] = value.copy()
            elif isinstance(value, dict) and key in base and isinstance(base[key], dict):
                result[key] = cls._merge_configs(base[key], value)
            else:
                result[key] = value
                
        return result

    @classmethod
    def _save_config(cls, config: Dict[str, Any]) -> bool:
        try:
            logger.debug(f"Saving config: {config}")
            cls.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(cls.SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Save failed: {e}\n{traceback.format_exc()}")
            return False

    @classmethod
    def save(cls, updates: Dict[str, Any]) -> bool:
        """Update and save configuration values."""
        try:
            config = cls.get_config()
            logger.debug(f"Current config before merge: {config}")
            logger.debug(f"Updates to apply: {updates}")
            
            config = cls._merge_configs(config, updates)
            logger.debug(f"Config after merge: {config}")
            
            if cls._save_config(config):
                cls._config = config
                logger.info("Configuration saved successfully")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to update config: {e}\n{traceback.format_exc()}")
            return False

    @classmethod
    def get_value(cls, key: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation for nested keys."""
        try:
            keys = key.split('.')
            value = cls.get_config()
            
            for k in keys:
                if isinstance(value, dict):
                    value = value.get(k, {})
                else:
                    return default
                    
            return value if value is not None else default
        except Exception as e:
            logger.error(f"Error getting config value {key}: {e}")
            return default

    @classmethod
    def _reset_to_defaults(cls) -> Dict[str, Any]:
        """Reset configuration to default values."""
        try:
            cls._config = cls.DEFAULT_CONFIG.copy()
            cls._save_config(cls._config)
            return cls._config
        except Exception as e:
            logger.error(f"Failed to reset config: {e}")
            return cls.DEFAULT_CONFIG.copy()

    @classmethod
    def reset_to_defaults(cls) -> bool:
        """Reset configuration to default values."""
        try:
            cls._config = cls.DEFAULT_CONFIG.copy()
            return cls._save_config(cls._config)
        except Exception as e:
            logger.error(f"Failed to reset config: {e}")
            return False