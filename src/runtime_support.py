"""Runtime paths and external-process boundaries for source and portable builds."""
from contextlib import contextmanager
import ctypes
import json
import os
from pathlib import Path
import sys
import threading

_spawn_lock = threading.RLock()


def standalone():
    return bool(getattr(sys, 'frozen', False))


def resource_path(name):
    if standalone():
        return Path(sys._MEIPASS) / name
    root = Path(__file__).resolve().parent
    return (root.parent if name == 'VERSION' else root) / name


def application_version():
    return resource_path('VERSION').read_text(encoding='utf-8').strip()


def startup_launcher(script):
    if standalone():
        return Path(sys.executable), None
    pythonw = Path(sys.executable).with_name('pythonw.exe')
    if not pythonw.is_file():
        raise RuntimeError('未找到后台启动所需的 pythonw.exe')
    return pythonw, Path(script).resolve()


@contextmanager
def external_process_environment():
    """Prevent bundled DLL search paths from leaking into Codex or PowerShell."""
    environment = os.environ.copy()
    if not standalone() or sys.platform != 'win32':
        yield environment
        return
    bundle = os.path.normcase(os.path.abspath(sys._MEIPASS))
    environment['PATH'] = os.pathsep.join(
        entry for entry in environment.get('PATH', '').split(os.pathsep)
        if entry and not (os.path.normcase(os.path.abspath(entry)) == bundle
                          or os.path.normcase(os.path.abspath(entry)).startswith(bundle + os.sep)))
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetDllDirectoryW.argtypes = [ctypes.c_uint32, ctypes.c_wchar_p]
    kernel.GetDllDirectoryW.restype = ctypes.c_uint32
    kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
    kernel.SetDllDirectoryW.restype = ctypes.c_bool
    with _spawn_lock:
        previous = ctypes.create_unicode_buffer(32768)
        length = kernel.GetDllDirectoryW(len(previous), previous)
        if not kernel.SetDllDirectoryW(None):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            yield environment
        finally:
            if not kernel.SetDllDirectoryW(previous.value if length else None):
                raise ctypes.WinError(ctypes.get_last_error())


def emit_report(payload, path=None):
    encoded = json.dumps(payload, ensure_ascii=False)
    if path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(encoded, encoding='utf-8')
    elif sys.stdout is not None:
        print(encoded)
