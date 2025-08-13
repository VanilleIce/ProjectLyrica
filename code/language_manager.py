# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import xml.etree.ElementTree as ET
from pathlib import Path
from config_manager import ConfigManager
import logging
from tkinter import messagebox
import traceback

from resource_loader import resource_path

logger = logging.getLogger("ProjectLyrica.LanguageManager")

class LanguageManager:
    """Handles language translations and keyboard layouts for the application."""
    
    _translations = {}
    _current_lang = None
    _languages = []
    _default_lang = 'en_US'
    _default_layout = 'QWERTY'

    @classmethod
    def init(cls):
        """Initialize language manager with config settings."""
        try:
            config = ConfigManager.get_config()
            cls._current_lang = config.get("selected_language", cls._default_lang)
            cls._languages = cls._load_languages()
            cls._get_translations(cls._default_lang)
        except Exception as e:
            logger.critical(f"LanguageManager init failed: {e}\n{traceback.format_exc()}")
            cls._current_lang = cls._default_lang
            cls._languages = []

    @classmethod
    def _load_languages(cls):
        """Load available languages from configuration file."""
        lang_file = Path(resource_path('resources/config/lang.xml'))
        try:
            if not lang_file.exists():
                raise FileNotFoundError(f"Language config file not found: {lang_file}")
                
            tree = ET.parse(lang_file)
            languages = []
            
            for lang in tree.findall('language'):
                try:
                    code = lang.get('code')
                    name = lang.text.strip() if lang.text else None
                    layout = lang.get('key_layout', cls._default_layout)
                    
                    if not code or not name:
                        logger.warning(f"Skipping invalid language entry: {ET.tostring(lang, encoding='unicode')}")
                        continue
                        
                    languages.append((code, name, layout))
                except Exception as e:
                    logger.error(f"Error processing language entry: {e}")
                    continue
                    
            if not languages:
                logger.error("No valid languages found in config file")
                messagebox.showerror(
                    "Error", 
                    "No valid languages configured. Using default English."
                )
                return [(cls._default_lang, "English", cls._default_layout)]
                
            return languages
            
        except Exception as e:
            logger.error(f"Language load error: {e}\n{traceback.format_exc()}")
            messagebox.showerror(
                "Error", 
                f"Failed to load languages. Using default English.\nError: {str(e)}"
            )
            return [(cls._default_lang, "English", cls._default_layout)]

    @classmethod
    def _get_translations(cls, lang_code):
        """Load translations for specified language code."""
        if not lang_code:
            return cls._get_translations(cls._default_lang)
            
        if lang_code in cls._translations:
            return cls._translations[lang_code]
        
        lang_file = Path(resource_path(f'resources/lang/{lang_code}.xml'))
        try:
            if not lang_file.exists():
                raise FileNotFoundError(f"Translation file not found: {lang_file}")
                
            tree = ET.parse(lang_file)
            translations = {}
            
            for t in tree.findall('translation'):
                try:
                    key = t.get('key')
                    text = t.text.strip() if t.text else ""
                    if key:
                        translations[key] = text
                except Exception as e:
                    logger.error(f"Error processing translation key {key}: {e}")
                    continue
                    
            cls._translations[lang_code] = translations
            return translations
            
        except FileNotFoundError:
            logger.warning(f"Translation file not found for {lang_code}, falling back to {cls._default_lang}")
            if lang_code != cls._default_lang:
                return cls._get_translations(cls._default_lang)
            return {}
        except ET.ParseError as e:
            logger.error(f"XML parse error in {lang_file}: {e}")
            messagebox.showerror(
                "Error", 
                f"Invalid translation file format for {lang_code}"
            )
            return {}
        except Exception as e:
            logger.error(f"Translation error for {lang_code}: {e}\n{traceback.format_exc()}")
            return {}

    @classmethod
    def get(cls, key):
        """Get translation for the given key."""
        if not key:
            return ""
            
        lang = cls._current_lang or cls._default_lang
        try:
            trans = cls._get_translations(lang).get(key)
            if trans is not None:
                return trans
                
            if lang != cls._default_lang:
                trans = cls._get_translations(cls._default_lang).get(key)
                if trans is not None:
                    return trans
                    
            logger.warning(f"Translation key not found: {key}")
            return f"[{key}]"
            
        except Exception as e:
            logger.error(f"Error getting translation for {key}: {e}")
            return f"[{key}]"

    @classmethod
    def set_language(cls, lang_code):
        """Set the current application language with proper key mapping persistence."""
        if not lang_code:
            logger.error("Attempt to set empty language code")
            return False
            
        try:
            layout = cls._default_layout
            lang_name = "Unknown"
            for code, name, lyt in cls._languages:
                if code == lang_code:
                    layout = lyt
                    lang_name = name
                    break
            else:
                logger.warning(f"Layout not found for {lang_code}, using default")
            try:
                key_map = KeyboardLayoutManager.load_layout_silently(layout)
                logger.info(f"Loaded {len(key_map)} keys from {layout} layout")
            except Exception as e:
                logger.error(f"Failed to load layout {layout}: {e}")
                key_map = KeyboardLayoutManager.load_layout_silently(cls._default_layout)

            config_update = {
                "selected_language": lang_code,
                "keyboard_layout": layout,
                "key_mapping": key_map
            }

            logger.debug(f"Preparing to save config: {config_update}")

            success = ConfigManager.save(config_update)
            if not success:
                logger.error("Failed to save language configuration!")
                return False

            cls._current_lang = lang_code
            logger.info(f"Successfully set language to {lang_name} ({lang_code})")
            return True

        except Exception as e:
            logger.error(f"Critical error in set_language: {e}\n{traceback.format_exc()}")
            return False

    @classmethod
    def get_languages(cls):
        """Get list of available languages."""
        return cls._languages if cls._languages else [(cls._default_lang, "English", cls._default_layout)]


class KeyboardLayoutManager:
    """Handles loading and managing keyboard layouts."""

    _layout_cache = {}
    
    @staticmethod
    def load(name):
        """Load keyboard layout by name."""
        if not name:
            name = LanguageManager._default_layout
            
        try:
            return KeyboardLayoutManager.load_layout_silently(name)
            
        except Exception as e:
            logger.error(f"Failed to load layout {name}: {e}\n{traceback.format_exc()}")
            raise RuntimeError(f"Could not load keyboard layout: {name}") from e

    @staticmethod
    def load_layout_silently(layout_name):
        """Loads layout without log messages"""
        if layout_name in KeyboardLayoutManager._layout_cache:
            return KeyboardLayoutManager._layout_cache[layout_name]
            
        file_path = Path(resource_path(f'resources/layouts/{layout_name.lower()}.xml'))
        try:
            if not file_path.exists():
                return {}
                
            tree = ET.parse(file_path)
            xml_mapping = {}
            
            for key in tree.findall('key'):
                key_id = key.get('id')
                key_text = key.text.strip() if key.text else ""
                if key_id:
                    xml_mapping[key_id] = key_text
                    
            KeyboardLayoutManager._layout_cache[layout_name] = xml_mapping
            return xml_mapping
            
        except Exception:
            return {}