import requests
import re
import socket
import json

def check_update(current_version: str, repo: str):
    """Prüft auf Updates - Rückgabe: (status, latest_version, url)"""
    try:
        # Verbindungsprüfung mit Timeout
        try:
            socket.create_connection(("api.github.com", 443), timeout=2)
        except (socket.timeout, OSError):
            return ("no_connection", "", "")
        
        response = requests.get(
            f"https://api.github.com/repos/{repo}/releases/latest",
            timeout=(3, 5),
            headers={"User-Agent": "ProjectLyrica/UpdateChecker"},
            verify=True
        )
        
        # HTTP-Status prüfen
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
    cleaned = re.sub(r'[^0-9.]', '', v)
    parts = cleaned.split('.')
    return tuple(int(part) for part in parts if part.isdigit())