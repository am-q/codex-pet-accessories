"""Read-only Windows geometry tracking. Never sends input or moves the pet."""
import ctypes
from ctypes import wintypes as W
import os
import time
from dpi_policy import logical_coordinates

U = ctypes.WinDLL('user32', use_last_error=True)
K = ctypes.WinDLL('kernel32', use_last_error=True)
CALLBACK = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
U.EnumWindows.argtypes = [CALLBACK, W.LPARAM]
U.GetWindowRect.argtypes = [W.HWND, ctypes.POINTER(W.RECT)]
U.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
U.GetWindowLongW.argtypes = [W.HWND, ctypes.c_int]
U.GetWindowLongW.restype = ctypes.c_long
U.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, ctypes.c_int]
U.IsWindow.argtypes = [W.HWND]
U.IsWindowVisible.argtypes = [W.HWND]
U.GetCursorPos.argtypes = [ctypes.POINTER(W.POINT)]
U.GetAsyncKeyState.argtypes = [ctypes.c_int]
U.GetAsyncKeyState.restype = ctypes.c_short
U.WindowFromPoint.argtypes = [W.POINT]
U.WindowFromPoint.restype = W.HWND
U.GetAncestor.argtypes = [W.HWND,W.UINT]
U.GetAncestor.restype = W.HWND
K.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
K.OpenProcess.restype = W.HANDLE
K.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, ctypes.POINTER(W.DWORD)]
K.CloseHandle.argtypes = [W.HANDLE]


@logical_coordinates
def window_rect(hwnd):
    rect = W.RECT()
    if not U.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return (rect.left, rect.top, rect.right-rect.left, rect.bottom-rect.top)


@logical_coordinates
def codex_windows():
    result, processes = [], {}
    def visit(hwnd, _):
        pid = W.DWORD()
        U.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in processes:
            name = ''
            handle = K.OpenProcess(0x1000, False, pid.value)
            if handle:
                try:
                    buf, length = ctypes.create_unicode_buffer(32768), W.DWORD(32768)
                    if K.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(length)):
                        name = os.path.basename(buf.value).lower()
                finally:
                    K.CloseHandle(handle)
            processes[pid.value] = name
        if processes[pid.value] != 'chatgpt.exe':
            return True
        rect = window_rect(hwnd)
        if rect and rect[2] > 0 and rect[3] > 0:
            title = ctypes.create_unicode_buffer(256)
            U.GetWindowTextW(hwnd, title, 256)
            result.append({'hwnd':hwnd,'rect':rect,'visible':bool(U.IsWindowVisible(hwnd)),
                           'style':U.GetWindowLongW(hwnd,-20) & 0xffffffff, 'title':title.value})
        return True
    U.EnumWindows(CALLBACK(visit), 0)
    return result


def select_pet(windows, anchor, size):
    cx, cy = anchor['x']+size/2, anchor['y']+size/2
    candidates=[]
    for window in windows:
        x,y,w,h=window['rect']
        # This version's pet has LAYERED + TOOLWINDOW + TOPMOST. The main
        # window does not have this combination. Do not depend on its title.
        if not window['visible'] or window['style'] & 0x80088 != 0x80088:
            continue
        if x-16 <= cx <= x+w+16 and y-16 <= cy <= y+h+16:
            candidates.append(window)
    return min(candidates,key=lambda q:q['rect'][2]*q['rect'][3]) if candidates else None


class LivePetTracker:
    """Track an actual user drag, including motion inside a fixed overlay window.

    The desktop overlay may cover an entire screen edge; its HWND rectangle is
    not the pet rectangle. Cursor deltas bridge the saved anchor while dragging.
    No mouse input is injected and no Codex window is modified.
    """
    def __init__(self):
        self.window=None
        self.drag=DragAnchor()
        self.next_find=0
        self.mode='saved'

    @logical_coordinates
    def update(self,state):
        if not state:
            return state
        saved=state['anchor']
        if self.window and not U.IsWindow(self.window):
            self.window=None
        if not self.window and time.monotonic() >= self.next_find:
            candidate=select_pet(codex_windows(),saved,state['size'])
            self.window=candidate['hwnd'] if candidate else None
            self.next_find=time.monotonic()+3
        point=W.POINT()
        U.GetCursorPos(ctypes.byref(point))
        pressed=bool(U.GetAsyncKeyState(1) & 0x8000)
        under=U.WindowFromPoint(point) if pressed and not self.drag.was_down else None
        under=U.GetAncestor(under,2) if under else None
        owned=bool(self.window and under==self.window)
        anchor=self.drag.update(saved,state['size'],(point.x,point.y),pressed,owned,time.monotonic())
        self.mode='drag' if self.drag.start else 'live' if self.window else 'saved'
        result={**state,'anchor':anchor}
        if self.window:
            result['open']=state['open'] and bool(U.IsWindowVisible(self.window))
        return result


class DragAnchor:
    """Pure state machine, independently tested without controlling the pet."""
    def __init__(self):
        self.was_down=False
        self.start=None
        self.origin=None
        self.anchor=None
        self.released_at=None

    def update(self,saved,size,point,down,owned,now):
        x,y=point
        inside=saved['x']-6<=x<=saved['x']+size+6 and saved['y']-6<=y<=saved['y']+size*208/192+6
        if down and not self.was_down and owned and inside:
            self.start=point
            self.origin=dict(saved)
            self.released_at=None
        if self.start and down:
            self.anchor={**saved,'x':self.origin['x']+x-self.start[0],'y':self.origin['y']+y-self.start[1]}
        elif self.start:
            self.start=None
            self.released_at=now
        elif self.released_at is not None:
            # Wait briefly for the saved layout, avoiding a snap back on release.
            changed=(saved['x'],saved['y']) != (self.origin['x'],self.origin['y'])
            if changed or now-self.released_at>=1.5:
                self.released_at=None
                self.anchor=dict(saved)
        else:
            self.anchor=dict(saved)
        self.was_down=down
        return dict(self.anchor or saved)


if __name__=='__main__':
    import json
    U.SetProcessDpiAwarenessContext.argtypes=[ctypes.c_void_p]
    U.SetProcessDpiAwarenessContext(ctypes.c_void_p(-1))
    from usage_core import PetState
    state=PetState().read()
    windows=codex_windows()
    print(json.dumps({'windows':windows,'selected':select_pet(windows,state['anchor'],state['size']) if state else None},ensure_ascii=False))
