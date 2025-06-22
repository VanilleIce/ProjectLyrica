# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import requests, re, socket, logging

logger = logging.getLogger("UpdateChecker")

def version_tuple(v):
    clean = re.sub(r'[^0-9.]', '', v)
    parts = clean.split('.')
    while len(parts) < 3:
        parts.append('0')
    return tuple(map(int, parts))

def check_update(current_version: str, repo: str):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2)
        if s.connect_ex(("api.github.com", 443)) != 0:
            logger.warning("No internet connection for update check")
            return ("no_connection", "", "")
    
    try:
        logger.info("Checking for application updates...")
        response = requests.get(
            f"https://api.github.com/repos/{repo}/releases/latest",
            timeout=5,
            headers={"User-Agent": "ProjectLyrica"}
        )
        response.raise_for_status()
        data = response.json()
        
        latest = data.get('tag_name', '')
        url = data.get('html_url', '')
        if not latest:
            logger.error("GitHub API response did not contain a version tag")
            return ("error", "", "")
        
        logger.info(f"Version check: Local={current_version}, GitHub={latest}")
        
        current_ver = version_tuple(current_version)
        latest_ver = version_tuple(latest)
        logger.debug(f"Normalized versions: Local={current_ver}, GitHub={latest_ver}")
        
        if latest_ver > current_ver:
            logger.info(f"Update available: {current_version} → {latest}")
            logger.info(f"Download: {url}")
            return ("update", latest, url)
        elif latest_ver == current_ver:
            logger.info(f"Using latest version: {current_version} (same as GitHub)")
            return ("current", latest, url)
        else:
            logger.info(f"Local version is newer: {current_version} (GitHub has {latest})")
            return ("current", latest, url)
            
    except requests.exceptions.Timeout:
        logger.warning("GitHub API request timed out")
        return ("error", "", "")
    except requests.exceptions.RequestException as e:
        logger.error(f"GitHub API request failed: {str(e)}")
        return ("error", "", "")
    except Exception as e:
        logger.error(f"Unexpected error during update check: {str(e)}")
        return ("error", "", "")