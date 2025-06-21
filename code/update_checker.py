# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.
# Source code: https://github.com/VanilleIce/ProjectLyrica

import requests, re, socket, json, logging

logger = logging.getLogger(__name__)

def check_update(current_version: str, repo: str):
    try:
        logger.info(f"Checking for updates - current version: {current_version}")
        
        # Internet connection check
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            if s.connect_ex(("api.github.com", 443)) != 0:
                logger.warning("No internet connection detected")
                return ("no_connection", "", "")
        
        # GitHub API request
        response = requests.get(
            f"https://api.github.com/repos/{repo}/releases/latest",
            timeout=(3, 5),
            headers={"User-Agent": "ProjectLyrica/UpdateChecker"},
            verify=True
        )
        response.raise_for_status()
        data = response.json()
        
        # Extract release info
        latest = data.get('tag_name', '')
        url = data.get('html_url', '')
        if not latest:
            logger.error("No release tag found in GitHub response")
            return ("error", "", "")
        
        # Version comparison
        current_ver = version_tuple(current_version)
        latest_ver = version_tuple(latest)
        
        if latest_ver > current_ver:
            logger.info(f"Update available: {latest}")
            return ("update", latest, url)
        else:
            logger.info("Already using latest version")
            return ("current", latest, url)
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {str(e)}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
    return ("error", "", "")

def version_tuple(v: str):
    cleaned = re.sub(r'[^0-9.]', '', v)
    return tuple(int(part) for part in cleaned.split('.') if part.isdigit())