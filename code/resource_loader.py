# Copyright (C) 2026 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import sys
from pathlib import Path
from typing import Union


# ==================== Interne Helfer ====================

# Wie viele Ebenen über dem Script wir maximal suchen,
# um eine EXISTIERENDE Datei zu finden.
_MAX_SEARCH_DEPTH = 3


def _get_script_dir() -> Path:
    """Verzeichnis des aktuell laufenden Scripts (robust)."""
    # 1. __main__.__file__ (zuverlässigster Weg bei direktem Start)
    try:
        import __main__
        main_file = getattr(__main__, '__file__', None)
        if main_file:
            return Path(main_file).resolve().parent
    except Exception:
        pass

    # 2. sys.argv[0] (kann bei .bat relativ sein → auflösen)
    try:
        argv0 = Path(sys.argv[0]).resolve()
        if argv0.suffix.lower() in ('.bat', '.cmd'):
            candidate = argv0.parent / "ProjectLyrica.py"
            if candidate.exists():
                return candidate.parent
            return argv0.parent
        return argv0.parent
    except Exception:
        pass

    # 3. Fallback: cwd
    return Path.cwd()


def _find_existing_resource(relative_path: Path) -> Union[Path, None]:
    """Sucht eine EXISTIERENDE Datei im Script-Dir und darüber.

    Sucht bis zu `_MAX_SEARCH_DEPTH` Ebenen über dem Script-Verzeichnis.

    Returns:
        Pfad zur existierenden Datei oder None.
    """
    script_dir = _get_script_dir()

    current = script_dir
    for _ in range(_MAX_SEARCH_DEPTH + 1):
        candidate = current / relative_path
        if candidate.exists():
            return candidate

        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


# ==================== Öffentliche Funktionen ====================

def resource_path(relative_path: Union[str, Path]) -> str:
    """Gibt den absoluten Pfad zu einer Ressource zurück.

    Im PyInstaller-Modus:
        → _MEIPASS

    Im Dev-Modus:
        1. Suche existierende Ressource im Script-Dir und bis zu
           _MAX_SEARCH_DEPTH Ebenen darüber (erste existierende gewinnt)
        2. Fallback: cwd-absolut

    Args:
        relative_path: Relativer Pfad zur Ressource
                       (z.B. "resources/lang/da_DK.xml").

    Returns:
        Absoluter Pfad als String.
    """
    path = Path(relative_path)

    # PyInstaller: _MEIPASS
    base_path = getattr(sys, '_MEIPASS', None)
    if base_path is not None:
        return str(Path(base_path) / path)

    # 1. Suche existierende Ressource im Script-Dir und darüber
    existing = _find_existing_resource(path)
    if existing is not None:
        return str(existing)

    # 2. Fallback: cwd
    return str(path.absolute())


def writable_resource_path(relative_path: Union[str, Path]) -> str:
    """Gibt einen BESCHREIBBAREN Pfad zu einer Ressource zurück.

    Suchreihenfolge:
        1. PyInstaller-Modus → neben der EXE
        2. Wenn die Datei bereits EXISTIERT → diesen Pfad verwenden
           (sucht im Script-Dir und bis zu 3 Ebenen darüber)
        3. Sonst: Script-Dir (neue Datei wird dort erstellt)

    Das ermöglicht Strukturen wie:
        Lyrica_win\\
        ├── settings.json
        └── code\\
            └── ProjectLyrica.py

    Args:
        relative_path: Relativer Pfad zur Ressource.

    Returns:
        Absoluter Pfad als String.
    """
    path = Path(relative_path)

    if getattr(sys, 'frozen', False):
        # PyInstaller: neben der EXE
        base_path = Path(sys.executable).parent
        return str(base_path / path)

    # 1. Prüfen ob die Datei bereits existiert (auch in übergeordneten Ordnern)
    existing = _find_existing_resource(path)
    if existing is not None:
        return str(existing)

    # 2. Nicht vorhanden → im Script-Verzeichnis neu erstellen
    script_dir = _get_script_dir()
    return str(script_dir / path)