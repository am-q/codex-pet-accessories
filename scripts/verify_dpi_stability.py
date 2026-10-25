"""Exercise real disposable Windows UI, including follow refresh with a menu open."""
import ctypes, hashlib, json, sys, time
from pathlib import Path
from ctypes import wintypes as W
from types import SimpleNamespace
from unittest.mock import patch

sys.dont_write_bytecode=True
source=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]/'src'
sys.path.insert(0,str(source))
u=ctypes.WinDLL('user32',use_last_error=True)
legacy='--legacy' in sys.argv
if legacy:
    u.SetProcessDpiAwarenessContext.argtypes=[ctypes.c_void_p]
    u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-1))
else:
    from dpi_policy import initialize_native_dpi
    initialize_native_dpi()
from smooth_surface import sharp_window,dpi_context,logical_window_position
from pet_base import App,DEFAULTS
from accessories import STYLES,CELL_WIDTH,HEIGHT
from base_menu import monitor_work_area
u.GetWindowRect.argtypes=[W.HWND,ctypes.POINTER(W.RECT)]
u.GetParent.argtypes=[W.HWND];u.GetParent.restype=W.HWND
u.GetThreadDpiAwarenessContext.restype=ctypes.c_void_p
u.AreDpiAwarenessContextsEqual.argtypes=[ctypes.c_void_p,ctypes.c_void_p]
errors=[];checks=0;visuals=[]
root=sharp_window();app=App(root,demo=True)
root.report_callback_exception=lambda *exc:errors.append(str(exc[1]))

def descendants(widget):
    yield widget
    for child in widget.winfo_children():yield from descendants(child)

def verify():
    global checks
    root.update()
    for index,plan in enumerate(app.layout_plan):
        surface=app.surface if index==0 else app.secondary_surface
        width=CELL_WIDTH*len(plan['quotas'])
        expected=surface.target_size(width,HEIGHT)
        r=W.RECT()
        with dpi_context(-4):assert u.GetWindowRect(surface.hwnd,ctypes.byref(r))
        assert (r.right-r.left,r.bottom-r.top)==expected
        assert surface.image.size==expected
        assert logical_window_position(surface.root)==(plan['x'],plan['y'])
        visuals.append([app.settings['accessory_style'],plan['side'],width,
                        hashlib.sha256(surface.image.tobytes()).hexdigest(),plan['x'],plan['y']])
    if app.popup:
        menu=app.popup
        for w in descendants(menu.canvas):
            if not w.winfo_ismapped():continue
            r=W.RECT()
            with dpi_context(-4):assert u.GetWindowRect(w.winfo_id(),ctypes.byref(r))
            assert (r.right-r.left,r.bottom-r.top)==(w.winfo_width(),w.winfo_height()), (w.winfo_class(),r.right-r.left,w.winfo_width())
        assert menu.panel_size[1]<=560
    if not legacy:
        assert u.AreDpiAwarenessContextsEqual(u.GetThreadDpiAwarenessContext(),ctypes.c_void_p(-4)), 'UI context leaked'
    assert not errors,errors
    checks+=1

try:
    with patch('pet_base.time.time',return_value=1800000000):
        app.settings={**DEFAULTS,'follow':False,'color_theme':'cream','theme':'light','text_tone':'light',
                      'free_anchor':{'x':600,'y':250},'auto_start':False}
        app.snapshot={'checked_at':1800000000,'quotas':[
            dict(bucket='codex',duration=300,used=40,reset=1800008000),
            dict(bucket='codex',duration=10080,used=70,reset=1800200000)]}
        for style in STYLES:
            app.settings['accessory_style']=style
            for layout in ('split','together','split'):
                app.settings['layout_mode']=layout
                for frame in range(4):
                    app.settings['free_anchor']={'x':600+frame*3,'y':250+frame*2}
                    app.follow();app.last_render=None;app.render()
                    if frame==0:
                        app.show_details()
                    elif frame==1:app.popup.change_page('appearance')
                    elif frame==2:app.popup.change_page('info');app.popup.show_renewal_editor()
                    else:
                        app.popup.viewport.yview_moveto(1)
                    verify()
                app.collapse()
            print('verified '+style,flush=True)
        for state in ('left','right','both'):
            app.settings['visible_sides']=state
            app.follow();app.last_render=None;app.render();verify()
        app.collapse();app.show_tooltip();root.update()
        tip=app.tooltip
        assert tip is not None
        if not legacy:
            for w in descendants(tip):
                r=W.RECT()
                with dpi_context(-4):assert u.GetWindowRect(w.winfo_id(),ctypes.byref(r))
                assert (r.right-r.left,r.bottom-r.top)==(w.winfo_width(),w.winfo_height())
        app.hover_leave()
        # Keep a menu open while real scheduled refresh callbacks run.
        app.show_details()
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            root.update();time.sleep(.02)
        verify()
    result={'checks':checks,'styles':len(STYLES),'visuals':visuals,'callback_errors':errors,
            'legacy':legacy,'native_dpi':app.surface.u.GetDpiForWindow(app.surface.hwnd)}
    output=next((v[9:] for v in sys.argv if v.startswith('--report=')),None)
    if output:Path(output).write_text(json.dumps(result),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='visuals'}))
finally:app.close()
