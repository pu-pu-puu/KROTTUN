import sys
import os
import ctypes

def is_admin() -> bool:
    """Проверяет, запущен ли процесс с правами Администратора."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def run_as_admin():
    """Перезапускает текущее приложение с повышением прав через UAC."""
    if is_admin():
        return True

    if getattr(sys, 'frozen', False):
        params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
    else:
        params = " ".join([f'"{arg}"' for arg in sys.argv])

    try:
        ret = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            params,
            os.getcwd(),
            1 # SW_SHOWNORMAL
        )
        if ret > 32:
            sys.exit(0)
        return False
    except Exception as e:
        print(f"Ошибка повышения прав: {e}")
        return False
