import base64
import ctypes
import json
import os
import sys
import tempfile
import threading
import time
import stat
from ctypes import wintypes
from typing import List, Optional, Dict, Any
from core.proxy_model import ProxyItem
from core.paths import get_user_data_dir

_lock = threading.Lock()
_crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
_k32 = ctypes.WinDLL("kernel32")
_k32.LocalFree.argtypes = [ctypes.c_void_p]
_ENTROPY = b"ProxyTUN/v2"
_MAGIC = b"PTv2:"

class StorageError(Exception):
    """Исключение при ошибках шифрования или доступа к хранилищу."""
    pass

class _BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

def _blob(b: bytes):
    buf = ctypes.create_string_buffer(b, len(b))
    return _BLOB(len(b), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf

def _dpapi(data: bytes, encrypt: bool) -> bytes:
    """Шифрует или дешифрует байты с привязкой к текущему пользователю Windows (DPAPI)."""
    if encrypt:
        inp, buf_in = _blob(data)
        ent, buf_ent = _blob(_ENTROPY)
        out = _BLOB()
        if not _crypt32.CryptProtectData(ctypes.byref(inp), None, ctypes.byref(ent), None, None, 0x1, ctypes.byref(out)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            _k32.LocalFree(out.pbData)
    else:
        # Пробуем расшифровать с текущей энтропией v2, при неудаче пробуем v1
        last_err = None
        for cand_entropy in (_ENTROPY, b"ProxyTUN/v1"):
            inp, buf_in = _blob(data)
            ent, buf_ent = _blob(cand_entropy)
            out = _BLOB()
            if _crypt32.CryptUnprotectData(ctypes.byref(inp), None, ctypes.byref(ent), None, None, 0x1, ctypes.byref(out)):
                try:
                    return ctypes.string_at(out.pbData, out.cbData)
                finally:
                    _k32.LocalFree(out.pbData)
            else:
                last_err = ctypes.get_last_error()
        raise ctypes.WinError(last_err or 0)

def get_secure_storage_path() -> str:
    return os.path.join(get_user_data_dir(), "proxies.dat")

def _check_not_reparse(path: str):
    """Проверяет, что целевой файл не подменен через точку повторного разбора / symlink (R5)."""
    if os.path.lexists(path):
        try:
            st = os.lstat(path)
            if hasattr(st, "st_file_attributes") and (st.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                raise RuntimeError(f"Файл {path} является точкой повторного разбора (reparse point)")
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise

def _atomic_write_file(path: str, data: bytes, is_binary: bool = True):
    """Атомарная запись с повторами при блокировке антивирусом или индексатором."""
    _check_not_reparse(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "wb" if is_binary else "w"
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-")
    try:
        with os.fdopen(fd, mode, encoding=None if is_binary else "utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        
        # Повторные попытки при временной блокировке антивирусом Windows
        for attempt in range(5):
            try:
                _check_not_reparse(path)
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.1 * (attempt + 1))
    except Exception:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass
        raise

_MIGRATED = lambda: os.path.join(get_user_data_dir(), ".migrated")

_MIGRATION_ERROR: Optional[str] = None

def get_migration_error() -> Optional[str]:
    return _MIGRATION_ERROR

def _migrate_from_localappdata() -> List[ProxyItem]:
    r"""
    Безопасно переносит данные из старого %LOCALAPPDATA%\ProxyTUN в защищенный каталог (B-2).
    Операция строго однократная и только для чтения (без os.remove), что полностью исключает
    уязвимости Arbitrary File Deletion / LPE.
    """
    global _MIGRATION_ERROR
    marker = _MIGRATED()
    if os.path.exists(marker):
        return []

    items: List[ProxyItem] = []
    try:
        local_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "ProxyTUN")
        if os.path.lexists(local_dir):
            st = os.lstat(local_dir)
            if not (hasattr(st, "st_file_attributes") and (st.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)):
                # 1. Проверяем старый зашифрованный proxies.dat
                old_dat = os.path.join(local_dir, "proxies.dat")
                if os.path.exists(old_dat):
                    try:
                        st = os.lstat(old_dat)
                        if not (hasattr(st, "st_file_attributes") and (st.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)):
                            with open(old_dat, "rb") as f:
                                content = f.read().strip()
                            if content:
                                b64_data = content[len(_MAGIC):] if content.startswith(_MAGIC) else content
                                raw_cipher = base64.b64decode(b64_data)
                                decrypted = _dpapi(raw_cipher, False)
                                raw = json.loads(decrypted.decode("utf-8"))
                                items = [ProxyItem.from_dict(item) for item in raw if isinstance(item, dict)]
                                if items:
                                    save_proxies(items)
                    except Exception as e:
                        _MIGRATION_ERROR = f"Сбой миграции из предыдущей версии: {e}. Добавьте прокси заново."

                # 2. Если proxies.dat не было, проверяем proxies.json
                if not items:
                    old_json = os.path.join(local_dir, "proxies.json")
                    if os.path.exists(old_json):
                        try:
                            st = os.lstat(old_json)
                            if not (hasattr(st, "st_file_attributes") and (st.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)):
                                with open(old_json, "r", encoding="utf-8") as f:
                                    raw = json.load(f)
                                items = [ProxyItem.from_dict(item) for item in raw if isinstance(item, dict)]
                                if items:
                                    save_proxies(items)
                        except Exception as e:
                            _MIGRATION_ERROR = f"Сбой миграции из предыдущей версии: {e}. Добавьте прокси заново."

                # 3. Переносим settings.json
                old_settings = os.path.join(local_dir, "settings.json")
                new_settings = get_settings_path()
                if os.path.exists(old_settings) and not os.path.exists(new_settings):
                    try:
                        st = os.lstat(old_settings)
                        if not (hasattr(st, "st_file_attributes") and (st.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)):
                            with open(old_settings, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            if isinstance(data, dict):
                                _atomic_write_file(new_settings, json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"), is_binary=True)
                    except Exception:
                        pass
    finally:
        # Однократный маркер ставится в защищенный каталог даже если переносить было нечего (B-2)
        try:
            _atomic_write_file(marker, b"1", is_binary=True)
        except Exception:
            pass

    return items

def save_proxies(proxies: List[ProxyItem], filepath: Optional[str] = None):
    """
    Атомарно сохраняет список прокси с обязательным шифрованием DPAPI.
    Никогда не откатывается к сохранению в открытом виде.
    """
    path = filepath or get_secure_storage_path()
    payload = json.dumps([p.to_dict() for p in proxies], ensure_ascii=False).encode("utf-8")

    try:
        encrypted = _dpapi(payload, True)
    except Exception as e:
        raise StorageError(f"Сбой шифрования Windows DPAPI: {e}") from e

    enc_payload = _MAGIC + base64.b64encode(encrypted)

    with _lock:
        _atomic_write_file(path, enc_payload, is_binary=True)

def load_proxies(filepath: Optional[str] = None) -> List[ProxyItem]:
    """Загружает и расшифровывает список прокси из защищенного хранилища."""
    path = filepath or get_secure_storage_path()
    if not os.path.exists(path):
        return _migrate_from_localappdata()

    with _lock:
        try:
            with open(path, "rb") as f:
                content = f.read().strip()
                if not content:
                    return []

            if content.startswith(_MAGIC):
                b64_data = content[len(_MAGIC):]
            else:
                # Попытка прочитать v1 (без префикса _MAGIC)
                b64_data = content

            raw_cipher = base64.b64decode(b64_data)
            decrypted = _dpapi(raw_cipher, False)
            raw = json.loads(decrypted.decode("utf-8"))
            return [ProxyItem.from_dict(item) for item in raw if isinstance(item, dict)]
        except OSError as e:
            # DPAPI ошибка: запуск под другой учетной записью администратора / пользователя
            raise StorageError("Не удалось расшифровать proxies.dat (доступ ограничен текущим профилем пользователя Windows).") from e
        except Exception as e:
            backup_path = path + f".corrupted.{int(time.time())}.bak"
            try:
                import shutil
                shutil.copy2(path, backup_path)
            except Exception:
                pass
            raise StorageError(f"Ошибка загрузки хранилища прокси: {e}") from e

def get_settings_path() -> str:
    return os.path.join(get_user_data_dir(), "settings.json")

def load_settings() -> Dict[str, Any]:
    """Загружает пользовательские параметры (маршрутизация Telegram и др.)."""
    path = get_settings_path()
    defaults = {
        "bypass_telegram": False,
        "v": 2
    }
    if not os.path.exists(path):
        return defaults
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                # Если настройки были перенесены из старой версии без ключа 'v',
                # сбрасываем bypass_telegram в False, чтобы Telegram шел через туннель без необходимости MTProto
                if data.get("v") != 2:
                    data["bypass_telegram"] = False
                    data["v"] = 2
                defaults.update(data)
    except Exception:
        pass
    return defaults

def save_setting(key: str, value: Any):
    """Атомарно сохраняет отдельный параметр конфигурации."""
    path = get_settings_path()
    with _lock:
        current = load_settings()
        current[key] = value
        payload = json.dumps(current, indent=2, ensure_ascii=False)
        _atomic_write_file(path, payload.encode("utf-8"), is_binary=True)
