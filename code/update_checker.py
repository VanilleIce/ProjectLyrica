# Copyright (C) 2026 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import logging
import re
import time
from typing import Optional, Tuple

import requests

logger = logging.getLogger("ProjectLyrica.UpdateChecker")

# ==================== Konstanten ====================

# GitHub API Basis
GITHUB_API_BASE = "https://api.github.com/"

# HTTP Timeouts (Sekunden)
CONNECT_TIMEOUT = 3.0
READ_TIMEOUT = 5.0
REQUEST_TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)

# User-Agent (GitHub verlangt das)
USER_AGENT = "ProjectLyrica-UpdateChecker"

# Version-Status
STATUS_UPDATE = "update"
STATUS_CURRENT = "current"
STATUS_NO_CONNECTION = "no_connection"
STATUS_ERROR = "error"

# Rückgabe-Typ: (status, latest_version, url)
UpdateResult = Tuple[str, str, str]


# ==================== Public API ====================

def version_tuple(v: str) -> Tuple[int, ...]:
    """Konvertiert Version-String zu vergleichbarem Tuple.

    Unterstützt Formate wie:
        "1.2.3"       → (1, 2, 3)
        "v1.2.3"      → (1, 2, 3)
        "1.2.3.4"     → (1, 2, 3, 4)
        "1.2.3-beta"  → (1, 2, 3)
        "1.2"         → (1, 2)

    Args:
        v: Version-String.

    Returns:
        Tuple aus Integers. Bei Parsing-Fehler wird (0,) zurückgegeben.
    """
    if not v or not isinstance(v, str):
        return (0,)

    # Pre-Release-Suffix abschneiden (alles nach '-' oder '+')
    clean = re.split(r'[-+]', v, maxsplit=1)[0]

    # Nur Ziffern und Punkte behalten
    clean = re.sub(r'[^0-9.]', '', clean)

    if not clean:
        return (0,)

    parts = clean.split('.')

    try:
        return tuple(int(p) for p in parts if p.isdigit())
    except (ValueError, TypeError) as e:
        logger.warning(f"Version parsing failed for '{v}': {e}")
        return (0,)


def check_update(current_version: str, repo: str) -> UpdateResult:
    """Prüft auf Updates via GitHub API.

    Args:
        current_version: Aktuelle lokale Version (z.B. "2.8.0").
        repo: GitHub Repo im Format "owner/repo".

    Returns:
        Tuple: (status, latest_version, url)

        status ist einer von:
            STATUS_UPDATE         - Update verfügbar
            STATUS_CURRENT        - Aktuelle Version ist aktuell
            STATUS_NO_CONNECTION  - Keine Verbindung zu GitHub
            STATUS_ERROR          - Anderer Fehler
    """
    logger.debug(f"Checking updates: local={current_version}, repo={repo}")

    api_url = f"{GITHUB_API_BASE}repos/{repo}/releases/latest"

    # ==================== Request ====================

    try:
        response = requests.get(
            api_url,
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/vnd.github.v3+json",
            },
        )

        # Rate-Limit prüfen (unabhängig vom Status-Code)
        rate_limit_wait = _check_rate_limit(response)
        if rate_limit_wait is not None:
            return (STATUS_ERROR, "", "")

        # HTTP-Fehler behandeln
        if response.status_code == 404:
            logger.error(f"Repo or release not found: {repo}")
            return (STATUS_ERROR, "", "")

        if response.status_code >= 500:
            logger.error(f"GitHub server error: {response.status_code}")
            return (STATUS_ERROR, "", "")

        response.raise_for_status()
        data = response.json()

    except requests.exceptions.Timeout:
        logger.warning("GitHub API request timed out")
        return (STATUS_ERROR, "", "")

    except requests.exceptions.ConnectionError as e:
        # Netzwerkfehler (DNS, offen, refused)
        logger.warning(f"Cannot reach GitHub: {e}")
        return (STATUS_NO_CONNECTION, "", "")

    except requests.exceptions.HTTPError as e:
        status = (
            e.response.status_code
            if hasattr(e, 'response') and e.response else "?"
        )
        logger.error(f"GitHub API HTTP error: {status}")
        return (STATUS_ERROR, "", "")

    except requests.exceptions.RequestException as e:
        logger.error(f"GitHub API request failed: {e}")
        return (STATUS_ERROR, "", "")

    except ValueError as e:
        # JSON-Parsing
        logger.error(f"Invalid JSON from GitHub API: {e}")
        return (STATUS_ERROR, "", "")

    except Exception as e:
        logger.error(f"Unexpected error during update check: {e}", exc_info=True)
        return (STATUS_ERROR, "", "")

    # ==================== Response auswerten ====================

    latest = (data.get('tag_name') or '').removeprefix('v').strip()
    url = data.get('html_url') or ''

    if not latest:
        logger.error("GitHub API response did not contain a version tag")
        return (STATUS_ERROR, "", "")

    # Versionen vergleichen
    try:
        comparison = _compare_versions(current_version, latest)
    except Exception as e:
        logger.error(f"Version comparison failed: {e}")
        return (STATUS_ERROR, latest, url)

    if comparison < 0:
        logger.info(f"Update available: {current_version} → {latest}")
        return (STATUS_UPDATE, latest, url)
    elif comparison == 0:
        logger.info(f"Using latest version: {current_version}")
        return (STATUS_CURRENT, latest, url)
    else:
        logger.info(f"Local version is newer: {current_version} (GitHub: {latest})")
        return (STATUS_CURRENT, latest, url)


# Backward-compat Alias
check_for_updates = check_update


# ==================== Private Helpers ====================

def _compare_versions(v1: str, v2: str) -> int:
    """Vergleicht zwei Versions-Strings.

    Returns:
        -1 wenn v1 < v2
         0 wenn v1 == v2
         1 wenn v1 > v2
    """
    t1 = version_tuple(v1)
    t2 = version_tuple(v2)

    # Auf gleiche Länge auffüllen mit 0
    max_len = max(len(t1), len(t2))
    t1 = t1 + (0,) * (max_len - len(t1))
    t2 = t2 + (0,) * (max_len - len(t2))

    if t1 < t2:
        return -1
    elif t1 > t2:
        return 1
    return 0


def _check_rate_limit(response: requests.Response) -> Optional[int]:
    """Prüft GitHub Rate-Limit.

    Returns:
        None wenn OK, sonst Anzahl Sekunden bis Reset (falls bekannt).
    """
    remaining_str = response.headers.get('X-RateLimit-Remaining')
    if remaining_str is None:
        return None

    try:
        remaining = int(remaining_str)
    except (ValueError, TypeError):
        return None

    if remaining > 0:
        return None

    # Rate-Limit erreicht - Reset-Zeit holen falls vorhanden
    reset_str = response.headers.get('X-RateLimit-Reset')
    if reset_str:
        try:
            reset_time = int(reset_str)
            wait_seconds = max(0, reset_time - int(time.time()))
            logger.warning(f"GitHub API rate limit exceeded. Reset in {wait_seconds}s")
            return wait_seconds
        except (ValueError, TypeError):
            pass

    logger.warning("GitHub API rate limit exceeded")
    return 0