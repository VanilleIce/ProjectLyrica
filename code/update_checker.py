# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import requests, re, socket, logging
from typing import Tuple
from urllib.parse import urljoin

logger = logging.getLogger("ProjectLyrica.UpdateChecker")

def version_tuple(v: str) -> Tuple[int, int, int]:
    """Convert version string to comparable tuple."""
    try:
        clean = re.sub(r'[^0-9.]', '', v)
        parts = clean.split('.')
        while len(parts) < 3:
            parts.append('0')
        return tuple(map(int, parts))
    except (ValueError, TypeError) as e:
        logger.error(f"Version parsing failed for '{v}': {e}")
        return (0, 0, 0)

def check_update(current_version: str, repo: str) -> Tuple[str, str, str]:
    """
    Check for updates on GitHub.
    
    Returns:
        Tuple: (status, latest_version, url)
        status: "update", "current", "no_connection", or "error"
    """
    # Connection check
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            if s.connect_ex(("api.github.com", 443)) != 0:
                logger.warning("No internet connection for update check")
                return ("no_connection", "", "")
    except socket.error as e:
        logger.warning(f"Socket error during connection check: {e}")
        return ("no_connection", "", "")
    
    # GitHub API request
    try:
        logger.info("Checking for application updates...")
        
        base_url = "https://api.github.com/"
        endpoint = f"repos/{repo}/releases/latest"
        api_url = urljoin(base_url, endpoint)
        
        response = requests.get(
            api_url,
            timeout=5,
            headers={
                "User-Agent": "ProjectLyrica",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        
        # Rate limit check
        if response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers:
            remaining = int(response.headers['X-RateLimit-Remaining'])
            if remaining == 0:
                logger.warning("GitHub API rate limit exceeded")
                return ("error", "", "")
        
        response.raise_for_status()
        data = response.json()
        
        latest = data.get('tag_name', '').lstrip('v')
        url = data.get('html_url', '')
        
        if not latest:
            logger.error("GitHub API response did not contain a version tag")
            return ("error", "", "")
        
        logger.info(f"Version check: Local={current_version}, GitHub={latest}")
        
        current_ver = version_tuple(current_version)
        latest_ver = version_tuple(latest)
        
        if latest_ver > current_ver:
            logger.info(f"Update available: {current_version} → {latest}")
            return ("update", latest, url)
        elif latest_ver == current_ver:
            logger.info(f"Using latest version: {current_version}")
            return ("current", latest, url)
        else:
            logger.info(f"Local version is newer: {current_version} (GitHub has {latest})")
            return ("current", latest, url)
            
    except requests.exceptions.Timeout:
        logger.warning("GitHub API request timed out")
        return ("error", "", "")
    except requests.exceptions.HTTPError as e:
        logger.error(f"GitHub API request failed with HTTP error: {e.response.status_code if hasattr(e, 'response') else 'Unknown'}")
        return ("error", "", "")
    except requests.exceptions.RequestException as e:
        logger.error(f"GitHub API request failed: {str(e)}")
        return ("error", "", "")
    except Exception as e:
        logger.error(f"Unexpected error during update check: {str(e)}")
        return ("error", "", "")

def check_for_updates(current_version: str, repo: str) -> Tuple[str, str, str]:
    """Wrapper function for backward compatibility"""
    return check_update(current_version, repo)