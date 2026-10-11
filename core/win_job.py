import ctypes
import logging
from ctypes import wintypes

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.CreateJobObjectW.restype = wintypes.HANDLE
_k32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
_k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
_k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
_k32.GetCurrentProcess.restype = wintypes.HANDLE

JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JobObjectExtendedLimitInformation = 9

class _IO(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in ("a", "b", "c", "d", "e", "f")]

class _BASIC(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD)
    ]

class _EXT(ctypes.Structure):
    _fields_ = [
        ("Basic", _BASIC),
        ("Io", _IO),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t)
    ]

_job = None

def _ensure_job_created() -> bool:
    global _job
    if _job is not None:
        return True
    try:
        _job = _k32.CreateJobObjectW(None, None)
        if not _job:
            logging.error("CreateJobObjectW failed with error code: %d", ctypes.get_last_error())
            return False
        info = _EXT()
        info.Basic.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not _k32.SetInformationJobObject(
            _job, 
            JobObjectExtendedLimitInformation, 
            ctypes.byref(info), 
            ctypes.sizeof(info)
        ):
            logging.error("SetInformationJobObject failed with error code: %d", ctypes.get_last_error())
            return False
        return True
    except Exception as e:
        logging.error("Exception in _ensure_job_created: %s", e)
        return False

def bind_self_to_job() -> bool:
    """
    Помещает текущий процесс ProxyTUN в Job Object с флагом KILL_ON_JOB_CLOSE.
    Все дочерние процессы (sing-box, WebView2) автоматически наследуют этот Job Object.
    При закрытии ProxyTUN ядро Windows немедленно уничтожает все процессы без окон гонки.
    """
    if not _ensure_job_created():
        return False
    try:
        cur = _k32.GetCurrentProcess()
        res = _k32.AssignProcessToJobObject(_job, cur)
        if not res:
            logging.warning("AssignProcessToJobObject(self) returned code: %d", ctypes.get_last_error())
            return False
        return True
    except Exception as e:
        logging.warning("Failed to bind self to Job Object: %s", e)
        return False

def bind_to_lifetime(popen) -> bool:
    """
    Явно привязывает конкретный дочерний процесс к Job Object как дополнительная гарантия.
    """
    if not _ensure_job_created():
        return False
    try:
        if hasattr(popen, '_handle') and popen._handle:
            res = _k32.AssignProcessToJobObject(_job, wintypes.HANDLE(int(popen._handle)))
            return bool(res)
    except Exception as e:
        logging.warning("Failed to bind subprocess to Job Object: %s", e)
    return False
