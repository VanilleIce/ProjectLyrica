import logging, platform, sys

def setup_logging(version):
    LOG_FILE = "project_lyrica.log"
    system_info = []
    
    try:
        system_info = [
            f"Project Lyrica v{version}",
            f"OS: {platform.platform()}",
            f"Python: {sys.version.split()[0]}",
            f"Architecture: {platform.architecture()[0]}",
            f"Processor: {platform.processor() or 'Unknown'}"
        ]
    
        if platform.system() == "Windows":
            try:
                import ctypes
                # RAM-Informationen
                kernel32 = ctypes.windll.kernel32
                ctypes.windll.kernel32.GetPhysicallyInstalledSystemMemory.restype = ctypes.POINTER(ctypes.c_ulonglong)
                mem_kb = ctypes.c_ulonglong()
                kernel32.GetPhysicallyInstalledSystemMemory(ctypes.byref(mem_kb))
                ram_gb = mem_kb.value / 1024 / 1024
                system_info.append(f"RAM: {ram_gb:.1f} GB (installed)")
                
                try:
                    import winreg
                    system_info.append("GPU Info:")
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}")
                    for i in range(10):
                        try:
                            subkey = winreg.EnumKey(key, i)
                            gpu_key = winreg.OpenKey(key, subkey)
                            try:
                                name = winreg.QueryValueEx(gpu_key, "DriverDesc")[0]
                                driver_version = winreg.QueryValueEx(gpu_key, "DriverVersion")[0]
                                system_info.append(f"  - {name} | v{driver_version}")
                            finally:
                                winreg.CloseKey(gpu_key)
                        except OSError:
                            break
                except Exception:
                    system_info.append("GPU: Registry access failed")
            except Exception:
                system_info.append("System info: Partial data only")
                
        logging.basicConfig(
            filename=LOG_FILE,
            filemode='w',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
    except Exception as e:
        if not system_info:
            system_info = [
                f"Project Lyrica v{version}",
                f"Logging setup failed: {e}"
            ]
        try:
            logging.basicConfig(
                filename=LOG_FILE,
                filemode='w',
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        except:
            pass
    try:
        logging.info("=" * 70)
        for info in system_info:
            logging.info(info)
        logging.info("=" * 70)
    except Exception as e:
        print(f"Final logging failed: {e}")
    
    return LOG_FILE