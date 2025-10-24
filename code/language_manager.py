# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from config_manager import ConfigManager
from tkinter import messagebox

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
        config = ConfigManager.get_config()
        
        ui_settings = config.get("ui_settings", {})
        cls._current_lang = ui_settings.get("selected_language")
            
        cls._languages = cls._load_languages()
        
        if cls._current_lang:
            cls._get_translations(cls._current_lang)
        else:
            cls._current_lang = cls._default_lang
            cls._get_translations(cls._default_lang)

    @classmethod
    def _load_languages(cls):
        """Load available languages from configuration file."""
        lang_file = Path(resource_path('resources/config/lang.xml'))
        
        if not lang_file.exists():
            logger.error(f"Language config file not found: {lang_file}")
            return [(cls._default_lang, "English", cls._default_layout)]
            
        tree = ET.parse(lang_file)
        languages = []
        
        for lang in tree.findall('language'):
            code = lang.get('code')
            name = lang.text.strip() if lang.text else None
            layout = lang.get('key_layout', cls._default_layout)
            
            if code and name:
                languages.append((code, name, layout))
                    
        if not languages:
            logger.error("No valid languages found in config file")
            return [(cls._default_lang, "English", cls._default_layout)]
            
        return languages

    @classmethod
    def _get_translations(cls, lang_code):
        """Load translations for specified language code."""
        if not lang_code:
            return cls._get_translations(cls._default_lang)
            
        if lang_code in cls._translations:
            return cls._translations[lang_code]
        
        lang_file = Path(resource_path(f'resources/lang/{lang_code}.xml'))
        if not lang_file.exists():
            if lang_code != cls._default_lang:
                return cls._get_translations(cls._default_lang)
            return {}
            
        tree = ET.parse(lang_file)
        translations = {}
        
        for t in tree.findall('translation'):
            key = t.get('key')
            text = t.text.strip() if t.text else ""
            if key:
                translations[key] = text
                    
        cls._translations[lang_code] = translations
        return translations

    @classmethod
    def get(cls, key):
        """Get translation for the given key."""
        if not key:
            return ""
            
        lang = cls._current_lang or cls._default_lang
        
        trans = cls._get_translations(lang).get(key)
        if trans is not None:
            return trans

        if lang != cls._default_lang:
            trans = cls._get_translations(cls._default_lang).get(key)
            if trans is not None:
                return trans
                
        logger.warning(f"Translation key not found: {key} in language {lang}")
        return f"[{key}]"

    @classmethod
    def set_language(cls, lang_code):
        """Set the current application language with proper key mapping persistence."""
        if not lang_code:
            return False
            
        layout = cls._default_layout
        for code, name, lyt in cls._languages:
            if code == lang_code:
                layout = lyt
                break

        try:
            from language_manager import KeyboardLayoutManager
            key_map = KeyboardLayoutManager.load_layout_silently(layout)
        except Exception as e:
            logger.error(f"Failed to load layout {layout}: {e}")
            key_map = KeyboardLayoutManager.load_layout_silently(cls._default_layout)

        config_update = {
            "ui_settings": {
                "selected_language": lang_code,
                "keyboard_layout": layout
            },
            "key_mapping": key_map
        }

        success = ConfigManager.save(config_update)
        if not success:
            logger.error("Failed to save language configuration!")
            return False

        cls._current_lang = lang_code
        logger.info(f"Successfully set language to {lang_code}")
        return True

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
            
        return KeyboardLayoutManager.load_layout_silently(name)

    @staticmethod
    def load_layout_silently(layout_name):
        """Loads layout without log messages"""
        if layout_name in KeyboardLayoutManager._layout_cache:
            return KeyboardLayoutManager._layout_cache[layout_name]
            
        file_path = Path(resource_path(f'resources/layouts/{layout_name.lower()}.xml'))
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