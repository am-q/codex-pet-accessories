"""Windows regression with disposable demo menus; no personal settings are written."""
import ctypes
import json
import sys
import time
from ctypes import wintypes as W
from types import SimpleNamespace
from pathlib import Path

sys.dont_write_bytecode = True
source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0, str(source))
u = ctypes.WinDLL('user32', use_last_error=True)
u.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
from dpi_policy import initialize_native_dpi
initialize_native_dpi()
from smooth_surface import sharp_window, dpi_context, logical_window_position
from pet_base import App

root = sharp_window()
app = App(root, demo=True)
results = []
baselines = {}

def widgets(parent):
    for child in parent.winfo_children():
        yield child
        yield from widgets(child)

def verify(menu, page, scale):
    root.update()
    u.GetWindowRect.argtypes=[W.HWND,ctypes.POINTER(W.RECT)]
    for widget in (menu.canvas,menu.viewport,menu.body,*widgets(menu.body)):
        if not widget.winfo_ismapped():continue
        rect=W.RECT()
        with dpi_context(-4):assert u.GetWindowRect(widget.winfo_id(),ctypes.byref(rect))
        actual=(rect.right-rect.left,rect.bottom-rect.top)
        expected=(widget.winfo_width(),widget.winfo_height())
        assert actual==expected, (page,widget.winfo_class(),actual,expected,'child window stretched')
    sizes = [(w.winfo_class(), w.winfo_reqwidth(), w.winfo_reqheight())
             for w in widgets(menu.body)]
    if page in baselines:
        assert sizes == baselines[page], (page, scale, 'font/layout changed with Tk scaling')
    else:
        baselines[page] = sizes
    assert menu.panel_size[1] <= 560, menu.panel_size
    assert menu.scrollbar.winfo_ismapped(), ('Overflow needs a visible scrollbar', menu.panel_size, menu.body.winfo_reqheight(), menu.win.winfo_ismapped(), menu.scrollbar.place_info())
    menu.viewport.yview_moveto(1)
    root.update()
    assert menu.viewport.yview()[1] >= 0.999, 'Cannot reach bottom settings'
    last = menu.body.winfo_children()[-1]
    bottom = last.winfo_rooty() + last.winfo_height()
    viewport_bottom = menu.viewport.winfo_rooty() + menu.viewport.winfo_height()
    assert bottom <= viewport_bottom + 1, 'Last controls clipped after scrolling'
    results.append(dict(page=page, scale=scale, panel=menu.panel_size,
                        content_height=menu.body.winfo_reqheight(), bottom_accessible=True))

try:
    app.settings['auto_start'] = True
    app.show_details()
    menu = app.popup
    u.GetParent.argtypes=[W.HWND];u.GetParent.restype=W.HWND
    u.GetWindowDpiAwarenessContext.argtypes=[W.HWND];u.GetWindowDpiAwarenessContext.restype=ctypes.c_void_p
    u.AreDpiAwarenessContextsEqual.argtypes=[ctypes.c_void_p,ctypes.c_void_p]
    hwnd=u.GetParent(menu.win.winfo_id())
    assert u.AreDpiAwarenessContextsEqual(u.GetWindowDpiAwarenessContext(hwnd),ctypes.c_void_p(-4)), 'Menu must be PMv2'

    for scale in (96/72, 144/72, 192/72):
        root.tk.call('tk', 'scaling', scale)
        menu.change_page('info')
        verify(menu, 'info', scale)
        menu.show_renewal_editor()
        verify(menu, 'renewal', scale)
        menu.change_page('appearance')
        verify(menu, 'appearance', scale)
    # Changing the global scale while a menu remains open must also be stable.
    root.tk.call('tk', 'scaling', 96/72)
    verify(menu, 'appearance', 96/72)
    menu.change_page('info')
    root.update()
    # Tk must paint the entire native client area; no OS bitmap enlargement.
    u.GetClientRect.argtypes=[W.HWND,ctypes.POINTER(W.RECT)]
    rect=W.RECT()
    with dpi_context(-4):assert u.GetClientRect(hwnd,ctypes.byref(rect))
    assert (rect.right,rect.bottom)==(menu.win.winfo_width(),menu.win.winfo_height())
    assert abs(rect.right-menu.px(menu.panel_size[0]))<=1
    before=logical_window_position(menu.win)
    menu.start_drag(SimpleNamespace(x_root=before[0]+20,y_root=before[1]+20))
    menu.drag_panel(SimpleNamespace(x_root=before[0]+10,y_root=before[1]+30))
    menu.end_drag(None)
    root.update()
    assert logical_window_position(menu.win)==menu.manual_position
    assert menu.panel_size==(308,560)
    # Rescale the same live controls in both directions; preserve unsaved input.
    menu.show_renewal_editor()
    menu.date_var.set('2030-01-02')
    native_scale=menu.scale
    for factor in (1.0,1.25,1.5,2.0,native_scale):
        menu.scale=factor
        menu.layout()
        root.update_idletasks()
        entry=next(w for w in widgets(menu.editor) if w.winfo_class()=='Entry')
        assert int(entry.tk.splitlist(entry.cget('font'))[1])==-round(13*factor)
        assert menu.date_var.get()=='2030-01-02'
    menu.layout();root.update()
    # Let timer callbacks and Tk idle geometry settle as in the real app.
    deadline=time.monotonic()+1.2
    while time.monotonic()<deadline:
        root.update()
        time.sleep(.02)
    verify(menu,'renewal',96/72)
    sizes=[(w.winfo_class(),w.winfo_reqwidth(),w.winfo_reqheight()) for w in widgets(menu.body)]
    assert sizes==baselines['renewal'], 'Repeated DPI changes accumulated rounding'
    print(json.dumps(dict(checks=len(results), native_dpi=round(native_scale*96),
                          native_client=[rect.right,rect.bottom], awareness='PMv2',
                          drag_verified=True, dpi_round_trip=True, results=results), ensure_ascii=False))
finally:
    app.close()
