# Copyright (C) 2026 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import ctypes
import logging
import platform
import subprocess
import sys
from pathlib import Path
from typing import List, Optional
from resource_loader import writable_resource_path

# ==================== Log-Level Konfiguration ====================
# Mögliche Werte:
#   logging.DEBUG    - Alle Meldungen (sehr ausführlich)
#   logging.INFO     - Normale Meldungen (empfohlen für Datei)
#   logging.WARNING  - Nur Warnungen und Fehler (empfohlen für Konsole)
#   logging.ERROR    - Nur Fehler
#   logging.CRITICAL - Nur kritische Fehler

FILE_LOG_LEVEL = logging.INFO
CONSOLE_LOG_LEVEL = logging.WARNING

# Subprocess Timeouts (Sekunden)
WMIC_TIMEOUT = 5
DXDIAG_TIMEOUT = 15

# dxdiag-Output-Datei (im App-Verzeichnis, wird nach Auswertung gelöscht)
DXDIAG_OUTPUT_FILE = "dxdiag_output.txt"
# ================================================================


def _run_hidden_command(cmd: List[str], timeout: float) -> Optional[str]:
    """Führt einen Subprocess aus und gibt stdout zurück (oder None bei Fehler).

    Nutzt creationflags um Fenster zu verstecken (Windows-spezifisch).
    """
    kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": timeout,
    }
    # Windows: kein Fenster aufblitzen lassen
    if platform.system() == "Windows":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        result = subprocess.run(cmd, **kwargs)
        if result.returncode == 0:
            return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    except Exception:
        pass
    return None


def _get_windows_wmi(wmi_class: str, field: str) -> List[str]:
    """Holt Werte via WMIC (Fallback: PowerShell bei neueren Windows)."""
    results = []

    # Methode 1: WMIC (ältere Windows)
    output = _run_hidden_command(
        ["wmic", "path", wmi_class, "get", field, "/value"],
        WMIC_TIMEOUT
    )
    if output:
        for line in output.splitlines():
            line = line.strip()
            if line.startswith(f"{field}="):
                value = line.split("=", 1)[1].strip()
                if value and value not in results:
                    results.append(value)

    # Methode 2: PowerShell (Windows 11 24H2+, wo wmic entfernt wurde)
    if not results:
        ps_script = f"(Get-CimInstance -ClassName {wmi_class}).{field}"
        output = _run_hidden_command(
            ["powershell", "-NoProfile", "-Command", ps_script],
            WMIC_TIMEOUT
        )
        if output:
            for line in output.splitlines():
                value = line.strip()
                if value and value.lower() != field.lower() and value not in results:
                    results.append(value)

    return results


def get_gpu_info() -> List[str]:
    """Ermittelt alle verfügbaren GPUs (dediziert und integriert)."""
    gpu_list: List[str] = []

    if platform.system() == "Windows":
        # Methode 1: WMIC / PowerShell
        gpu_list = _get_windows_wmi("Win32_VideoController", "Name")

        # Methode 2: dxdiag als Fallback
        if not gpu_list:
            gpu_list = _get_gpu_info_dxdiag()

    # Fallback
    if not gpu_list:
        gpu_list = ["Unknown"]

    return gpu_list


def _get_gpu_info_dxdiag() -> List[str]:
    """Fallback: GPU-Info via dxdiag.

    Schreibt dxdiag_output.txt IM APP-VERZEICHNIS (nicht Temp).
    Löscht die Datei nach Auswertung oder bei Fehler.
    """
    gpu_list: List[str] = []
    dxdiag_file = Path(DXDIAG_OUTPUT_FILE).absolute()

    try:
        kwargs = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "timeout": DXDIAG_TIMEOUT,
        }
        if platform.system() == "Windows":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        try:
            subprocess.run(
                ["dxdiag", "/t", str(dxdiag_file)],
                **kwargs
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return []

        if not dxdiag_file.exists():
            return []

        content = dxdiag_file.read_text(encoding="utf-8", errors="ignore")

        in_display_section = False
        for line in content.splitlines():
            if "Display Devices" in line:
                in_display_section = True
            elif in_display_section:
                if "Card name:" in line:
                    gpu_name = line.split("Card name:", 1)[1].strip()
                    if gpu_name and gpu_name != "n/a" and gpu_name not in gpu_list:
                        gpu_list.append(gpu_name)
                elif line.strip() == "":
                    in_display_section = False

    except Exception:
        pass
    finally:
        # Datei IMMER löschen (auch bei Exception)
        if dxdiag_file.exists():
            try:
                dxdiag_file.unlink()
            except OSError:
                pass

    return gpu_list


def get_cpu_info() -> str:
    """Ermittelt die CPU-Informationen."""
    processor = platform.processor() or "Unknown"

    if platform.system() == "Windows":
        cpu_list = _get_windows_wmi("Win32_Processor", "Name")
        if cpu_list:
            processor = cpu_list[0]

    return processor


def get_ram_info() -> str:
    """Ermittelt die RAM-Größe in GB."""
    if platform.system() == "Windows":
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetPhysicallyInstalledSystemMemory.argtypes = [
                ctypes.POINTER(ctypes.c_ulonglong)
            ]
            kernel32.GetPhysicallyInstalledSystemMemory.restype = ctypes.c_bool

            mem_kb = ctypes.c_ulonglong()
            if kernel32.GetPhysicallyInstalledSystemMemory(ctypes.byref(mem_kb)):
                ram_gb = mem_kb.value / (1024 * 1024)
                return f"{ram_gb:.1f} GB"
        except Exception:
            pass

    # Fallback: psutil (falls installiert)
    try:
        import psutil
        total_gb = psutil.virtual_memory().total / (1024 ** 3)
        return f"{total_gb:.1f} GB"
    except ImportError:
        pass
    except Exception:
        pass

    return "Unknown"


class _UnicodeSafeConsoleHandler(logging.StreamHandler):
    """Console-Handler der auch bei Encoding-Problemen nicht crasht."""

    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            try:
                stream.write(msg + self.terminator)
            except UnicodeEncodeError:
                # Ersatzzeichen für nicht-darstellbare Zeichen
                cleaned = msg.encode("ascii", "replace").decode("ascii")
                stream.write(cleaned + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)


def _close_existing_handlers(logger: logging.Logger):
    """Schließt existierende Handler sicher."""
    for handler in logger.handlers[:]:
        try:
            logger.removeHandler(handler)
            handler.close()
        except Exception:
            pass


def _setup_file_handler(log_file: Path) -> Optional[logging.Handler]:
    """Erstellt einen File-Handler für die Log-Datei.

    Löscht die alte Log-Datei ZUERST, damit bei jedem Start
    eine frische Datei erstellt wird.
    """
    # Alte Log-Datei explizit löschen
    if log_file.exists():
        try:
            log_file.unlink()
        except OSError as e:
            print(f"Warning: Could not delete old log file: {e}", file=sys.stderr)

    # Neuen File-Handler erstellen
    try:
        handler = logging.FileHandler(
            log_file,
            mode="w",
            encoding="utf-8",
        )
        return handler
    except OSError as e:
        print(f"Warning: Could not setup file logging: {e}", file=sys.stderr)
        return None


def setup_logging(version: str) -> str:
    """Initialize logging system with file and console handlers.

    Args:
        version: App-Version (z.B. "2.8.0").

    Returns:
        Pfad zur Log-Datei.
    """
    log_file = Path(writable_resource_path("project_lyrica.log"))

    # Log-Verzeichnis erstellen falls nötig
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Alte Handler entfernen
    _close_existing_handlers(root_logger)

    # ---- File Handler (immer frisch) ----
    file_handler = _setup_file_handler(log_file)
    if file_handler is not None:
        file_handler.setLevel(FILE_LOG_LEVEL)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%d-%m-%Y - %H:%M:%S"
        ))
        root_logger.addHandler(file_handler)

    # ---- Console Handler ----
    console_handler = _UnicodeSafeConsoleHandler()
    console_handler.setLevel(CONSOLE_LOG_LEVEL)
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S"
    ))
    root_logger.addHandler(console_handler)

    # ---- System-Info loggen ----
    setup_logger = logging.getLogger("ProjectLyrica.Logger")

    os_name = platform.system()
    if os_name == "Windows":
        os_version = platform.release()
        os_display = f"Windows {os_version}"
    else:
        os_display = platform.platform()

    sys_info = [
        f"Project Lyrica v{version}",
        f"OS: {os_display}",
        f"Python: {sys.version.split()[0]}",
        f"Processor: {get_cpu_info()}",
        f"RAM: {get_ram_info()}",
    ]

    # GPU-Info
    gpus = get_gpu_info()
    if len(gpus) == 1:
        sys_info.append(f"GPU: {gpus[0]}")
    else:
        for i, gpu in enumerate(gpus, 1):
            sys_info.append(f"GPU {i}: {gpu}")

    setup_logger.info("=" * 60)
    for info in sys_info:
        setup_logger.info(info)
    setup_logger.info("=" * 60)

    return str(log_file)