# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.
# Source code: https://github.com/VanilleIce/ProjectLyrica

import requests
import re
import socket
import json

def check_update(current_version: str, repo: str):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            if s.connect_ex(("api.github.com", 443)) != 0:
                return ("no_connection", "", "")
        
        response = requests.get(
            f"https://api.github.com/repos/{repo}/releases/latest",
            timeout=(3, 5),
            headers={"User-Agent": "ProjectLyrica/UpdateChecker"},
            verify=True
        )
        
        response.raise_for_status()
        
        data = response.json()
        latest = data.get('tag_name', '')
        url = data.get('html_url', '')
        
        if not latest:
            return ("error", "", "")
        
        if version_tuple(latest) > version_tuple(current_version):
            return ("update", latest, url)
        else:
            return ("current", latest, url)
            
    except requests.exceptions.RequestException:
        return ("error", "", "")
    except json.JSONDecodeError:
        return ("error", "", "")
    except Exception:
        return ("error", "", "")

def version_tuple(v: str):
    return tuple(
        int(part) 
        for part in re.sub(r'[^0-9.]', '', v).split('.') 
        if part.isdigit()
    )