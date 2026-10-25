"""DPI boundary: native pixels for UI; logical coordinates only at Win32 calls.

Never run Tk creation, geometry, event processing or idle callbacks inside a
logical context. Saved pet anchors remain in their existing logical units.
"""
import ctypes
from ctypes import wintypes as W
from contextlib import contextmanager
from functools import wraps

u=ctypes.WinDLL('user32',use_last_error=True)
u.SetThreadDpiAwarenessContext.argtypes=[ctypes.c_void_p]
u.SetThreadDpiAwarenessContext.restype=ctypes.c_void_p
u.SetProcessDpiAwarenessContext.argtypes=[ctypes.c_void_p]
u.SetProcessDpiAwarenessContext.restype=W.BOOL
u.GetParent.argtypes=[W.HWND];u.GetParent.restype=W.HWND
u.GetWindowRect.argtypes=[W.HWND,ctypes.POINTER(W.RECT)]
u.GetCursorPos.argtypes=[ctypes.POINTER(W.POINT)]
u.SetWindowPos.argtypes=[W.HWND,W.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.UINT]
u.SetWindowPos.restype=W.BOOL


def initialize_native_dpi():
    # Python or an embedding host may already have selected the process mode.
    # The UI thread still explicitly uses PMv2 before creating any Tk windows.
    u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    if not u.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4)):
        raise ctypes.WinError(ctypes.get_last_error())


@contextmanager
def dpi_context(value):
    previous=u.SetThreadDpiAwarenessContext(ctypes.c_void_p(value))
    if not previous:raise ctypes.WinError(ctypes.get_last_error())
    try:yield
    finally:u.SetThreadDpiAwarenessContext(previous)


def native_ui(method):
    @wraps(method)
    def call(*args,**kwargs):
        with dpi_context(-4):return method(*args,**kwargs)
    return call


def logical_coordinates(method):
    """Only for read-only Win32 coordinate adapters, never Tk/UI methods."""
    @wraps(method)
    def call(*args,**kwargs):
        with dpi_context(-1):return method(*args,**kwargs)
    return call


def logical_window_position(window):
    hwnd=u.GetParent(window.winfo_id()) or window.winfo_id()
    with dpi_context(-1):
        rect=W.RECT()
        if not u.GetWindowRect(hwnd,ctypes.byref(rect)):
            raise ctypes.WinError(ctypes.get_last_error())
    return rect.left,rect.top


def position_logical_window(hwnd,x,y):
    # Position only: the native UI owns the size. No implicit bitmap resizing.
    with dpi_context(-1):
        if not u.SetWindowPos(hwnd,None,round(x),round(y),0,0,0x1|0x4|0x10|0x200):
            raise ctypes.WinError(ctypes.get_last_error())


def logical_pointer_event(event):
    if not hasattr(event,'widget'):return event
    from types import SimpleNamespace
    with dpi_context(-1):
        point=W.POINT()
        if not u.GetCursorPos(ctypes.byref(point)):
            raise ctypes.WinError(ctypes.get_last_error())
    return SimpleNamespace(**{**vars(event),'x_root':point.x,'y_root':point.y})
