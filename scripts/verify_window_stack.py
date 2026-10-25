"""Native regression using only disposable test windows; never controls Codex."""
import ctypes,sys,json
from ctypes import wintypes as W
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
u=ctypes.WinDLL('user32',use_last_error=True)
u.SetProcessDpiAwarenessContext.argtypes=[ctypes.c_void_p]
u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-1))
from smooth_surface import sharp_window,AlphaSurface,Image
u.SetWindowPos.argtypes=[W.HWND,W.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.UINT]
u.GetWindow.argtypes=[W.HWND,W.UINT];u.GetWindow.restype=W.HWND
u.GetWindowRect.argtypes=[W.HWND,ctypes.POINTER(W.RECT)]
u.GetForegroundWindow.restype=W.HWND
windows=[]
def make(master=None):
    w=sharp_window(master);windows.append(w)
    w.title('Accessory stack regression (temporary)')
    w.geometry('50x50+30+30');w.update_idletasks()
    a=AlphaSurface(w)
    a.present_image(Image.new('RGBA',a.target_size(50,50),(60,65,80,180)))
    return w,a
def rect(a):
    r=W.RECT();assert u.GetWindowRect(a.hwnd,ctypes.byref(r))
    return r.left,r.top,r.right,r.bottom
def raise_test(a):
    assert u.SetWindowPos(a.hwnd,W.HWND(-1),0,0,0,0,0x1|0x2|0x10|0x200)
checks=0
try:
    main,primary=make();child,secondary=make(main)
    pet,mock_pet=make();blocker,cover=make()
    for double in (False,True):
        if double:child.deiconify()
        else:child.withdraw()
        main.update_idletasks()
        surfaces=[secondary,primary] if double else [primary]
        expected_rects=[rect(a) for a in surfaces]
        expected_bitmaps=[a.image.tobytes() for a in surfaces]
        for cycle in range(8):
            raise_test(cover);raise_test(mock_pet)
            focus=u.GetForegroundWindow()
            reference=mock_pet.hwnd
            for a in surfaces:
                a.follow_stack_below(reference)
                assert u.GetWindow(a.hwnd,3)==reference
                reference=a.hwnd
            assert [rect(a) for a in surfaces]==expected_rects
            assert [a.image.tobytes() for a in surfaces]==expected_bitmaps
            assert u.GetForegroundWindow()==focus,'Focus changed'
            reference=mock_pet.hwnd
            for a in surfaces:
                assert not a.follow_stack_below(reference),'Already-correct stack was reordered'
                reference=a.hwnd
            checks+=1
        pet.withdraw();pet.update_idletasks()
        assert not primary.follow_stack_below(mock_pet.hwnd)
        assert not primary.follow_stack_below(0)
        assert not primary.follow_stack_below(primary.hwnd)
        pet.deiconify();pet.update_idletasks()
    print(json.dumps(dict(result='ok',cover_and_restore_cycles=checks,single_and_dual=True,focus_unchanged=True,geometry_and_pixels_unchanged=True,no_reorder_when_aligned=True)))
finally:
    for w in reversed(windows):
        try:w.destroy()
        except Exception:pass
