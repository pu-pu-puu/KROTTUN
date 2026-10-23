if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()

import os
import sys
import logging
import threading
from logging.handlers import RotatingFileHandler

# Добавляем корневую директорию проекта в sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.paths import get_log_dir
from core.admin_utils import is_admin, run_as_admin
from gui.app_webview import start_app

def setup_logging():
    """Настраивает ротацию логов приложения в защищенный каталог."""
    try:
        log_dir = get_log_dir()
        log_file = os.path.join(log_dir, "proxytun.log")
        handler = RotatingFileHandler(
            log_file,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8"
        )
        logging.basicConfig(
            level=logging.INFO,
            handlers=[handler],
            format="%(asctime)s [%(levelname)s] (%(threadName)s) %(name)s: %(message)s"
        )
        sys.excepthook = lambda t, v, tb: logging.critical("Неперехваченное системное исключение", exc_info=(t, v, tb))
        threading.excepthook = lambda args: logging.critical(f"Поток {args.thread} аварийно завершился", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
    except Exception:
        pass

def main():
    # Не трогать ProgramData без подтвержденных прав Администратора (R1)
    if not is_admin():
        if not getattr(sys, 'frozen', False):
            run_as_admin()
        else:
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    0,
                    "Для работы KROTTUN и Wintun требуются права Администратора.",
                    "KROTTUN",
                    0x30
                )
            except Exception:
                pass
        return
    setup_logging()
    start_app()

if __name__ == "__main__":
    main()
