# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.
# Source code: https://github.com/VanilleIce/ProjectLyrica

import logging, platform, sys, subprocess, ctypes
from ctypes import wintypes

def setup_logging(version):
    LOG_FILE = "project_lyrica.log"
    system_info = [
        f"Project Lyrica v{version}",
        f"OS: {platform.platform()}",
        f"Python: {sys.version.split()[0]}",
        f"Architecture: {platform.architecture()[0]}"
    ]
    
    # Processor info
    processor_info = platform.processor()
    if platform.system() == "Windows":
        try:
            result = subprocess.check_output(
                'wmic cpu get name /value', 
                shell=True,
                text=True,
                stderr=subprocess.DEVNULL
            ).strip()
            if "Name=" in result:
                processor_info = result.split("Name=", 1)[1].strip()
        except: pass
    system_info.append(f"Processor: {processor_info}")
    
    # RAM info (Windows only)
    if platform.system() == "Windows":
        try:
            kernel32 = ctypes.windll.kernel32
            mem_kb = wintypes.DWORDLONG()
            kernel32.GetPhysicallyInstalledSystemMemory(ctypes.byref(mem_kb))
            ram_gb = mem_kb.value / 1024 / 1024
            system_info.append(f"RAM: {ram_gb:.1f} GB (installed)")
        except: pass
    
    # GPU info (Windows only)
    if platform.system() == "Windows":
        try:
            import winreg
            system_info.append("GPU Info:")
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
            )
            for i in range(10):
                try:
                    subkey = winreg.EnumKey(key, i)
                    gpu_key = winreg.OpenKey(key, subkey)
                    name = winreg.QueryValueEx(gpu_key, "DriverDesc")[0]
                    driver_version = winreg.QueryValueEx(gpu_key, "DriverVersion")[0]
                    system_info.append(f"  - {name} | v{driver_version}")
                    winreg.CloseKey(gpu_key)
                except OSError: break
        except: pass
    
    # Logging setup
    logging.basicConfig(
        filename=LOG_FILE,
        filemode='w',
        level=logging.INFO,
        format='%(asctime)s - %(filename)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Log system info
    logging.info("=" * 70)
    for info in system_info:
        logging.info(info)
    logging.info("=" * 70)
    
    return LOG_FILE