# Copyright (C) 2026 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config_manager import ConfigManager
from resource_loader import resource_path

logger = logging.getLogger("ProjectLyrica.LanguageManager")


# ==================== Sprachen & Layouts ====================

# Format: code : {"name": Anzeigename, "layout": Layoutname}

LANGUAGES: Dict[str, Dict[str, str]] = {
    "ar_AR": {"name": "العربية",              "layout": "ARABIC"},
    "da_DK": {"name": "Dansk",                "layout": "QWERTY"},
    "de_DE": {"name": "Deutsch",              "layout": "QWERTZ"},
    "en_EN": {"name": "English (British)",    "layout": "QWERTY"},
    "en_US": {"name": "English (Amerika)",    "layout": "QWERTY"},
    "es_ES": {"name": "Español",              "layout": "QWERTY"},
    "fr_FR": {"name": "Français",             "layout": "AZERTY"},
    "id_ID": {"name": "Bahasa Indonesia",     "layout": "QWERTY"},
    "it_IT": {"name": "Italiano",             "layout": "QWERTY"},
    "ja_JA": {"name": "日本語",                "layout": "JIS"},
    "ko_KR": {"name": "한국어",                "layout": "QWERTY"},
    "mg_MG": {"name": "Malagasy",             "layout": "QWERTY"},
    "nl_NL": {"name": "Nederlands",           "layout": "QWERTY"},
    "pl_PL": {"name": "Polski",               "layout": "QWERTY"},
    "pt_PT": {"name": "Português",            "layout": "QWERTY"},
    "ru_RU": {"name": "Русский",              "layout": "ЙЦУКЕН"},
    "th_TH": {"name": "ไทย",                   "layout": "QWERTY"},
    "vi_VN": {"name": "Tiếng Việt",           "layout": "QWERTY"},
    "zh_ZH": {"name": "中文",                  "layout": "QWERTY"},
}

class LanguageManager:
    """Handles language translations and keyboard layouts for the application."""

    _translations: Dict[str, Dict[str, str]] = {}
    _current_lang: Optional[str] = None
    _default_lang = 'en_US'
    _default_layout = 'QWERTY'

    # Warnung nur einmal pro fehlendem Key ausgeben
    _warned_missing_keys: set = set()

    # ==================== Initialisierung ====================

    @classmethod
    def init(cls):
        """Initialize language manager with config settings."""
        config = ConfigManager.get_config()
        ui_settings = config.get("ui_settings", {})
        cls._current_lang = ui_settings.get("selected_language")

        if not cls._current_lang or cls._current_lang not in LANGUAGES:
            cls._current_lang = cls._default_lang

        cls._get_translations(cls._current_lang)

        logger.info(f"LanguageManager initialized with '{cls._current_lang}'")

    # ==================== Public API ====================

    @classmethod
    def get_current_lang(cls) -> str:
        """Gibt den aktuellen Sprachcode zurück."""
        return cls._current_lang or cls._default_lang

    @classmethod
    def get(cls, key: str) -> str:
        """Get translation for the given key."""
        if not key:
            return ""

        lang = cls.get_current_lang()

        trans = cls._get_translations(lang).get(key)
        if trans is not None:
            return trans

        if lang != cls._default_lang:
            trans = cls._get_translations(cls._default_lang).get(key)
            if trans is not None:
                return trans

        warn_id = f"{lang}:{key}"
        if warn_id not in cls._warned_missing_keys:
            cls._warned_missing_keys.add(warn_id)
            logger.warning(f"Translation key not found: '{key}' in language '{lang}'")

        return f"[{key}]"

    @classmethod
    def get_languages(cls) -> List[Tuple[str, str, str]]:
        """Get available languages as list of (code, name, layout) tuples.

        Wird aus dem LANGUAGES-Dict generiert. Für Rückwärtskompatibilität
        mit bestehendem Code (settings_window etc.).
        """
        return [
            (code, info["name"], info["layout"])
            for code, info in sorted(LANGUAGES.items(), key=lambda x: x[1]["name"])
        ]

    @classmethod
    def set_language(cls, lang_code: str) -> bool:
        """Set the current application language with proper key mapping persistence."""
        if not lang_code or lang_code not in LANGUAGES:
            logger.error(f"Unknown language code: {lang_code}")
            return False

        layout = LANGUAGES[lang_code]["layout"]

        # Layout-Mapping laden (case-insensitive)
        key_map = KeyboardLayoutManager.load_layout_silently(layout)

        if not key_map:
            logger.warning(f"Layout '{layout}' empty, falling back to default")
            layout = cls._default_layout
            key_map = KeyboardLayoutManager.load_layout_silently(layout)

        config_update = {
            "ui_settings": {
                "selected_language": lang_code,
                "keyboard_layout": layout
            },
            "key_mapping": key_map
        }

        if not ConfigManager.save(config_update):
            logger.error("Failed to save language configuration!")
            return False

        cls._current_lang = lang_code
        cls._get_translations(lang_code)

        logger.info(f"Successfully set language to '{lang_code}' (layout: {layout})")
        return True

    @classmethod
    def get_fallback_layout_for_lang(cls, lang_code: str) -> str:
        """Gibt das Standard-Layout für einen Sprachcode zurück."""
        if not lang_code:
            return cls._default_layout

        # Direkt im LANGUAGES-Dict suchen
        if lang_code in LANGUAGES:
            return LANGUAGES[lang_code]["layout"]

        # Fallback: Base-Language versuchen (z.B. "de" → "de_DE")
        base_lang = lang_code.split('_')[0]
        for code, info in LANGUAGES.items():
            if code.split('_')[0] == base_lang:
                return info["layout"]

        return cls._default_layout

    @classmethod
    def clear_caches(cls):
        """Cache leeren (z.B. nach Sprachdatei-Änderungen)."""
        cls._translations.clear()
        cls._warned_missing_keys.clear()
        KeyboardLayoutManager.clear_cache()
        logger.info("LanguageManager caches cleared")

    # ==================== Private Helpers ====================

    @classmethod
    def _get_translations(cls, lang_code: str, _depth: int = 0) -> Dict[str, str]:
        """Load translations for specified language code."""
        if _depth > 2:
            logger.error(f"Translation fallback recursion detected for '{lang_code}'")
            return {}

        if not lang_code:
            return cls._get_translations(cls._default_lang, _depth + 1)

        if lang_code in cls._translations:
            return cls._translations[lang_code]

        lang_file = Path(resource_path(f'resources/lang/{lang_code}.xml'))
        if not lang_file.exists():
            if lang_code != cls._default_lang:
                logger.warning(f"Language file not found: {lang_code}, falling back to default")
                return cls._get_translations(cls._default_lang, _depth + 1)
            return {}

        try:
            tree = ET.parse(lang_file)
        except ET.ParseError as e:
            logger.error(f"Could not parse {lang_code}.xml: {e}")
            if lang_code != cls._default_lang:
                return cls._get_translations(cls._default_lang, _depth + 1)
            return {}

        translations = {}
        for t in tree.findall('translation'):
            key = t.get('key')
            text = t.text.strip() if t.text else ""
            if key:
                translations[key] = text

        cls._translations[lang_code] = translations
        return translations


class KeyboardLayoutManager:
    """Handles loading and managing keyboard layouts."""

    _layout_cache: Dict[str, Dict[str, str]] = {}

    @staticmethod
    def load(name: Optional[str]) -> Dict[str, str]:
        """Load keyboard layout by name."""
        if not name:
            name = LanguageManager._default_layout
        return KeyboardLayoutManager.load_layout_silently(name)

    @staticmethod
    def _find_layout_file(layout_name: str) -> Optional[Path]:
        """Findet eine Layout-Datei case-insensitive."""
        layouts_dir = Path(resource_path("resources/layouts"))

        if not layouts_dir.exists():
            return None

        target_lower = layout_name.lower()

        # Direkte Suche mit gängigen Case-Varianten
        candidates = [
            layouts_dir / f"{layout_name}.xml",
            layouts_dir / f"{layout_name.upper()}.xml",
            layouts_dir / f"{layout_name.lower()}.xml",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate

        # Fallback: Alle .xml-Dateien durchsuchen (case-insensitive)
        for xml_file in layouts_dir.glob("*.xml"):
            if xml_file.stem.lower() == target_lower:
                return xml_file

        return None

    @staticmethod
    def load_layout_silently(layout_name: str) -> Dict[str, str]:
        """Loads layout without log messages (case-insensitive)."""
        if not layout_name:
            layout_name = LanguageManager._default_layout

        cache_key = layout_name.lower()

        if cache_key in KeyboardLayoutManager._layout_cache:
            return KeyboardLayoutManager._layout_cache[cache_key]

        file_path = KeyboardLayoutManager._find_layout_file(layout_name)
        if file_path is None:
            logger.debug(f"Layout file not found for: {layout_name}")
            return {}

        try:
            tree = ET.parse(file_path)
        except ET.ParseError as e:
            logger.error(f"Could not parse layout '{layout_name}': {e}")
            return {}

        xml_mapping = {}
        for key in tree.findall('key'):
            key_id = key.get('id')
            key_text = key.text.strip() if key.text else ""
            if key_id:
                xml_mapping[key_id] = key_text

        KeyboardLayoutManager._layout_cache[cache_key] = xml_mapping
        return xml_mapping

    @staticmethod
    def clear_cache():
        """Cache leeren."""
        KeyboardLayoutManager._layout_cache.clear()