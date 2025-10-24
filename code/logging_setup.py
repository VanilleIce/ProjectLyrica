# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import logging, platform, subprocess, sys, ctypes
from ctypes import wintypes
from pathlib import Path

def setup_logging(version):
    """Initialize logging system with file and console handlers."""
    log_file = Path("project_lyrica.log").absolute()
    
    # Create log directory if needed
    log_file.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()

    # File handler
    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%d-%m-%Y - %H:%M'
    ))
    root_logger.addHandler(file_handler)

    # Unicode-safe console handler
    class UnicodeSafeConsoleHandler(logging.StreamHandler):
        def emit(self, record):
            try:
                msg = self.format(record)
                stream = self.stream
                stream.write(msg + self.terminator)
                self.flush()
            except UnicodeEncodeError:
                cleaned_msg = msg.encode('ascii', 'replace').decode('ascii')
                stream.write(cleaned_msg + self.terminator)
                self.flush()
            except Exception:
                self.handleError(record)
    
    console_handler = UnicodeSafeConsoleHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    root_logger.addHandler(console_handler)

    setup_logger = logging.getLogger("ProjectLyrica.Logger")

    # System info logging
    sys_info = [
        f"Project Lyrica v{version}",
        f"OS: {platform.platform()}",
        f"Python: {sys.version.split()[0]}",
    ]

    # CPU info
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
        except (subprocess.TimeoutExpired, Exception):
            pass  # Use default processor info
    
    sys_info.append(f"Processor: {processor}")

    # RAM info
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
        except Exception:
            pass
    
    sys_info.append(ram_info)

    # GPU info
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
        except (subprocess.TimeoutExpired, Exception):
            pass
    
    sys_info.append(gpu_info)

    # Log system info
    setup_logger.info("=" * 60)
    for info in sys_info:
        setup_logger.info(info)
    setup_logger.info("=" * 60)
    
    return str(log_file)