import os
import sys
import stat
import time
import re
import ctypes
import hashlib
import shutil
from ctypes import wintypes
from typing import Optional, Dict

_adv = ctypes.WinDLL("advapi32", use_last_error=True)
_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_sh = ctypes.WinDLL("shell32")
_ole = ctypes.WinDLL("ole32")

_k32.LocalFree.argtypes = [wintypes.LPVOID]
_k32.GetCurrentProcess.restype = wintypes.HANDLE
_k32.CloseHandle.argtypes = [wintypes.HANDLE]
_adv.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
_adv.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
_adv.ConvertSidToStringSidW.argtypes = [wintypes.LPVOID, ctypes.POINTER(wintypes.LPWSTR)]

class _GUID(ctypes.Structure):
    _fields_ = [("D1", wintypes.DWORD), ("D2", wintypes.WORD), ("D3", wintypes.WORD), ("D4", ctypes.c_ubyte * 8)]

class _SA(ctypes.Structure):
    _fields_ = [("nLength", wintypes.DWORD), ("lpSD", wintypes.LPVOID), ("bInherit", wintypes.BOOL)]

class _SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", wintypes.LPVOID), ("Attributes", wintypes.DWORD)]

FOLDERID_ProgramData = _GUID(0x62AB5D82, 0xFDC1, 0x4DC3,
                             (ctypes.c_ubyte * 8)(0xA9, 0xDD, 0x07, 0x0D, 0x1D, 0x49, 0x5D, 0x97))

from core.admin_utils import is_admin

# SDDL: Владелец BA (Administrators); Полный доступ SYSTEM и Administrators; Users (BU) — только Read & Execute; Наследование отключено (PAI)
SDDL_SECURE = "O:BAG:SYD:PAI(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;0x1200a9;;;BU)"
# SDDL_PRIVATE: Только SYSTEM и Administrators (без BU / Users) для каталогов пользовательских данных (R6)
SDDL_PRIVATE = "O:BAG:SYD:PAI(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)"

_TOK = {
    "FA": 0x1F01FF, "FR": 0x120089, "FW": 0x120116, "FX": 0x1200A0,
    "GA": 0x10000000, "GR": 0x80000000, "GW": 0x40000000, "GX": 0x20000000,
    "RC": 0x20000, "SD": 0x10000, "WD": 0x40000, "WO": 0x80000,
    "CC": 0x1, "DC": 0x2, "LC": 0x4, "SW": 0x8,
    "RP": 0x10, "WP": 0x20, "DT": 0x40, "LO": 0x80, "CR": 0x100
}
# WRITE_DATA|APPEND|WRITE_EA|DELETE_CHILD|WRITE_ATTR|DELETE|WRITE_DAC|WRITE_OWNER|GENERIC_ALL|GENERIC_WRITE|MAXIMUM_ALLOWED
WRITE_MASK = 0x520D0156
TRUSTED_OWNERS = ("BA", "SY", "S-1-5-32-544", "S-1-5-18")
TRUSTED_WRITERS = {"SY", "BA", "S-1-5-32-544", "S-1-5-18"}

def _mask(rights: str) -> int:
    if rights.lower().startswith("0x"):
        return int(rights, 16)
    m = 0
    for i in range(0, len(rights), 2):
        tok = rights[i:i + 2]
        if tok not in _TOK:
            raise ValueError(tok)  # неизвестный токен → недоверенный каталог
        m |= _TOK[tok]
    return m

def get_system_directory() -> str:
    """Возвращает проверенный системный путь System32 через Win32 API."""
    if os.name == 'nt':
        buf = ctypes.create_unicode_buffer(260)
        _k32.GetSystemDirectoryW(buf, 260)
        return buf.value
    return "/system32"

SYS32 = get_system_directory()

def sys_exe(name: str) -> str:
    """Возвращает абсолютный путь к системной утилите System32 (защита от DLL/Binary Planting)."""
    return os.path.join(SYS32, name)

def get_program_data_dir() -> str:
    """Возвращает путь к ProgramData через Win32 API SHGetKnownFolderPath (не из переменной окружения)."""
    if os.name != 'nt':
        return "/tmp"
    p = ctypes.c_wchar_p()
    if _sh.SHGetKnownFolderPath(ctypes.byref(FOLDERID_ProgramData), 0, None, ctypes.byref(p)) != 0:
        raise OSError("Не удалось определить системный каталог ProgramData через SHGetKnownFolderPath.")
    try:
        return p.value
    finally:
        _ole.CoTaskMemFree(p)

def _sddl_of(path: str) -> str:
    """Получает строку SDDL для дескриптора безопасности каталога."""
    psd, s = wintypes.LPVOID(), wintypes.LPWSTR()
    rc = _adv.GetNamedSecurityInfoW(path, 1, 0x1 | 0x4, None, None, None, None, ctypes.byref(psd))
    if rc:
        raise ctypes.WinError(rc)
    try:
        if not _adv.ConvertSecurityDescriptorToStringSecurityDescriptorW(psd, 1, 0x1 | 0x4, ctypes.byref(s), None):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return s.value
        finally:
            _k32.LocalFree(s)
    finally:
        _k32.LocalFree(psd)

def _sddl_is_trusted(sddl: str) -> bool:
    """Проверяет SDDL дескриптор: владелец BA/SY, PAI флаг защиты, отсутствие прав на запись для посторонних."""
    m = re.match(r"O:([^:]+?)(?:G:|D:)", sddl)
    if not m or m.group(1) not in TRUSTED_OWNERS:
        return False  # владелец не BA/SY → карантин
    dacl = sddl[sddl.find("D:"):]
    if not dacl.startswith("D:P"):  # DACL должен быть защищён от наследования
        return False
    for ace in re.findall(r"\(([^)]*)\)", dacl):
        parts = ace.split(";")
        if len(parts) < 6:
            return False
        typ, rights, trustee = parts[0], parts[2], parts[5]
        if typ == "D":
            continue
        if typ != "A":
            return False  # условные/объектные ACE не ожидаются
        if trustee not in TRUSTED_WRITERS and (_mask(rights) & WRITE_MASK):
            return False
    return True

def _is_trusted_directory(path: str) -> bool:
    """
    Проверяет безопасность каталога:
    - Не является точкой повторного разбора (reparse point / junction / symlink)
    - Владелец BA/SY и отсутствуют права на запись для посторонних
    """
    try:
        st = os.lstat(path)
        if hasattr(st, "st_file_attributes") and (st.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            return False
        return _sddl_is_trusted(_sddl_of(path))
    except Exception:
        return False

def current_user_sid() -> str:
    """Определяет SID пользователя текущего процесса Windows для изоляции профилей (R6)."""
    if os.name != 'nt':
        return "default_user"
    h = wintypes.HANDLE()
    if not _adv.OpenProcessToken(_k32.GetCurrentProcess(), 0x0008, ctypes.byref(h)):  # TOKEN_QUERY
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        size = wintypes.DWORD()
        _adv.GetTokenInformation(h, 1, None, 0, ctypes.byref(size))  # TokenUser
        buf = ctypes.create_string_buffer(size.value)
        if not _adv.GetTokenInformation(h, 1, buf, size, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        sid = ctypes.cast(buf, ctypes.POINTER(_SID_AND_ATTRIBUTES)).contents.Sid
        s = wintypes.LPWSTR()
        if not _adv.ConvertSidToStringSidW(sid, ctypes.byref(s)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            value = s.value
        finally:
            _k32.LocalFree(s)
    finally:
        _k32.CloseHandle(h)
    if not re.fullmatch(r"S-1-[0-9-]+", value):
        raise RuntimeError("Некорректный SID пользователя")
    return value

def _mkdir_secure(path: str, sddl: str = SDDL_SECURE) -> None:
    """Создает каталог с явным защищенным дескриптором безопасности SDDL."""
    psd = wintypes.LPVOID()
    if not _adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, ctypes.byref(psd), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        sa = _SA(ctypes.sizeof(_SA), psd, False)
        if not _k32.CreateDirectoryW(path, ctypes.byref(sa)):
            raise ctypes.WinError(ctypes.get_last_error())  # 183 и 1307 — также строгие ошибки
    finally:
        _k32.LocalFree(psd)
    if not _is_trusted_directory(path):  # Контроль сразу после создания
        raise RuntimeError(f"ProxyTUN: не удалось создать доверенный каталог {path}")

def _ensure_trusted_dir(path: str, sddl: str = SDDL_SECURE) -> None:
    """Изолирует в карантин при компрометации, затем создает каталог с защищенным дескриптором."""
    if os.path.lexists(path) and not _is_trusted_directory(path):
        q_name = f"{path}.quarantine-{int(time.time())}"
        try:
            os.rename(path, q_name)
        except Exception as e:
            raise RuntimeError(f"ProxyTUN: каталог {path} скомпрометирован и не может быть изолирован: {e}")
    if not os.path.exists(path):
        _mkdir_secure(path, sddl)

def get_secure_root() -> str:
    """
    Возвращает корень защищенного каталога %ProgramData%\\ProxyTUN.
    Если каталог уже существовал и был скомпрометирован (чужие права/junction/владелец не BA),
    он немедленно помещается в карантин и создается заново с доверенным SDDL.
    """
    if not is_admin():
        raise PermissionError("Защищённый каталог создаётся только с правами Администратора")

    root = os.path.join(get_program_data_dir(), "ProxyTUN")
    _ensure_trusted_dir(root, SDDL_SECURE)

    for sub in ("bin", "logs"):
        p = os.path.join(root, sub)
        _ensure_trusted_dir(p, SDDL_SECURE)

    return root

def get_secure_bin_dir() -> str:
    """Возвращает проверенный каталог bin внутри защищенного корня."""
    root = get_secure_root()
    return os.path.join(root, "bin")

def get_log_dir() -> str:
    """Возвращает проверенный каталог logs внутри защищенного корня."""
    root = get_secure_root()
    return os.path.join(root, "logs")

def get_user_data_dir() -> str:
    """
    Возвращает защищенный каталог данных пользователя %ProgramData%\\ProxyTUN\\users\\<SID> (R6).
    Права назначены строго для SYSTEM и Administrators (SDDL_PRIVATE), исключая доступ обычных пользователей.
    """
    root = get_secure_root()
    users = os.path.join(root, "users")
    _ensure_trusted_dir(users, SDDL_PRIVATE)
    user_dir = os.path.join(users, current_user_sid())
    _ensure_trusted_dir(user_dir, SDDL_PRIVATE)
    return user_dir

# Зафиксированные SHA-256 хэши проверенных бинарников
PINNED_HASHES: Dict[str, str] = {
    "sing-box.exe": "5c19bb3f8c12d4e85b3d47fe63123a7624b314b58dd7a8e32f51004f1c4d2faf",
    "wintun.dll": "e5da8447dc2c320edc0fc52fa01885c103de8c118481f683643cacc3220dafce"
}

def verify_file_sha256(path: str, expected_hash: str) -> bool:
    """Проверяет SHA-256 хэш файла."""
    if not os.path.exists(path):
        return False
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest().lower() == expected_hash.lower()
    except Exception:
        return False
