# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import logging
import platform
import sys
import subprocess
import ctypes
from ctypes import wintypes
from pathlib import Path

def setup_logging(version):
    """Initialize logging system with file and console handlers.
    
    Args:
        version (str): The application version to log.
    
    Returns:
        str: Path to the log file.
    """
    try:
        log_file = Path("project_lyrica.log").absolute()

        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, 'w', encoding='utf-8') as test_file:
                test_file.write("")
        except (IOError, PermissionError) as e:
            fallback_path = Path.home() / "project_lyrica.log"
            logging.warning(f"Could not write to {log_file}, falling back to {fallback_path}: {e}")
            log_file = fallback_path

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            handler.close()

        try:
            file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
            root_logger.addHandler(file_handler)
        except Exception as e:
            logging.error(f"Failed to setup file logging: {e}")

        class UnicodeSafeConsoleHandler(logging.StreamHandler):
            def emit(self, record):
                try:
                    msg = self.format(record)
                    stream = self.stream
                    try:
                        stream.write(msg + self.terminator)
                        self.flush()
                    except UnicodeEncodeError:
                        cleaned_msg = msg.encode('ascii', 'replace').decode('ascii')
                        stream.write(cleaned_msg + self.terminator)
                        self.flush()
                except Exception:
                    self.handleError(record)
        
        try:
            console_handler = UnicodeSafeConsoleHandler()
            console_handler.setLevel(logging.WARNING)
            console_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            root_logger.addHandler(console_handler)
        except Exception as e:
            logging.error(f"Failed to setup console logging: {e}")

        setup_logger = logging.getLogger("ProjectLyrica.setup")

        sys_info = [
            f"Project Lyrica v{version}",
            f"OS: {platform.platform()}",
            f"Python: {sys.version.split()[0]}",
        ]

        processor = platform.processor()
        if platform.system() == "Windows":
            try:
                output = subprocess.check_output(
                    ['wmic', 'cpu', 'get', 'name', '/value'],
                    shell=True,
                    text=True,
                    stderr=subprocess.DEVNULL,
                    encoding='utf-8',
                    timeout=5
                ).strip()
                if "Name=" in output:
                    processor = output.split("Name=", 1)[1].strip()
            except subprocess.TimeoutExpired:
                setup_logger.warning("CPU info query timed out")
            except Exception as e:
                setup_logger.error(f"CPU info error: {e}")
        sys_info.append(f"Processor: {processor}")

        ram_info = "RAM: Unknown"
        if platform.system() == "Windows":
            try:
                kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
                kernel32.GetPhysicallyInstalledSystemMemory.argtypes = [
                    ctypes.POINTER(ctypes.c_ulonglong)
                ]
                kernel32.GetPhysicallyInstalledSystemMemory.restype = ctypes.c_bool
                
                mem_kb = ctypes.c_ulonglong()
                if kernel32.GetPhysicallyInstalledSystemMemory(ctypes.byref(mem_kb)):
                    ram_gb = mem_kb.value / (1024 * 1024)
                    ram_info = f"RAM: {ram_gb:.1f} GB"
                else:
                    error_code = ctypes.get_last_error()
                    setup_logger.error(
                        f"GetPhysicallyInstalledSystemMemory failed with error code: {error_code}"
                    )
            except Exception as e:
                setup_logger.error(f"RAM detection error: {e}")
        sys_info.append(ram_info)

        gpu_info = "GPU: Unknown"
        if platform.system() == "Windows":
            try:
                output = subprocess.check_output(
                    ['wmic', 'path', 'win32_VideoController', 'get', 'name', '/value'],
                    shell=True,
                    text=True,
                    stderr=subprocess.DEVNULL,
                    encoding='utf-8',
                    timeout=5
                ).strip()
                gpu_names = [
                    line.split('=')[1] 
                    for line in output.splitlines() 
                    if line.startswith('Name=')
                ]
                if gpu_names:
                    gpu_info = f"GPU: {gpu_names[0]}"
                    if len(gpu_names) > 1:
                        setup_logger.info(f"Multiple GPUs detected, logging first one: {gpu_names}")
            except subprocess.TimeoutExpired:
                setup_logger.warning("GPU info query timed out")
            except Exception as e:
                setup_logger.error(f"GPU info error: {e}")
        sys_info.append(gpu_info)

        setup_logger.info("=" * 60)
        for info in sys_info:
            setup_logger.info(info)
        setup_logger.info("=" * 60)
        
        return str(log_file)

    except Exception as e:
        logging.basicConfig(level=logging.INFO)
        logging.error(f"Critical error in logging setup: {e}")
        return "project_lyrica_fallback.log"