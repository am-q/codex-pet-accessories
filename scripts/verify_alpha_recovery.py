"""Real Windows alpha lifecycle regression; only disposable accessory windows."""
import ctypes,json,sys
from pathlib import Path
from unittest.mock import patch
source=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]/'src'
sys.path.insert(0,str(source));sys.dont_write_bytecode=True
from dpi_policy import initialize_native_dpi
initialize_native_dpi()
from smooth_surface import sharp_window,AlphaSurface,Image
from ctypes import wintypes as W
u=ctypes.WinDLL('user32',use_last_error=True)
u.SetLayeredWindowAttributes.argtypes=[W.HWND,W.DWORD,ctypes.c_ubyte,W.DWORD]
owner=sharp_window();checks=0
try:
    for master in (None,owner):
        for iteration in range(3):
            window=sharp_window(master);surface=AlphaSurface(window)
            window.configure(bg='#ff00ff')
            rgba=Image.new('RGBA',surface.target_size(112,160),(0,0,0,0))
            rgba.paste((100,70,180,200),(20,20,60,100))
            try:
                # Exact regression: hidden before its first successful ULW frame.
                window.withdraw();window.update();window.deiconify();window.update()
                surface.present_image(rgba)
                assert surface.alpha_recoveries==1
                assert surface.image is rgba and surface.pixel_size==rgba.size
                checks+=1
                for repeat in range(3):
                    assert u.SetLayeredWindowAttributes(surface.hwnd,0,255,2)
                    count=surface.alpha_recoveries
                    surface.present_image(rgba)
                    assert surface.alpha_recoveries==count+1
                    surface.present_image(rgba)
                    assert surface.alpha_recoveries==count+1, 'Unnecessary alpha reset'
                    checks+=1
                window.withdraw();window.update();window.deiconify();window.update()
                surface.present_image(rgba);checks+=1
                # Persistent or unrelated failures must propagate with bounded retries.
                real=surface.u
                class Failure:
                    def __init__(self,error):self.error=error;self.calls=0
                    def __getattr__(self,name):return getattr(real,name)
                    def UpdateLayeredWindow(self,*args):
                        self.calls+=1;ctypes.set_last_error(self.error);return False
                for error,expected_calls in ((87,2),(5,1)):
                    failure=Failure(error);surface.u=failure
                    try:
                        try:surface.present_image(rgba.copy())
                        except OSError as exc:assert exc.winerror==error
                        else:raise AssertionError('Failure swallowed')
                        assert failure.calls==expected_calls
                        assert surface.image is rgba, 'Failed frame committed'
                    finally:surface.u=real
                    checks+=1
                surface.present_image(rgba)
            finally:window.destroy()
finally:owner.destroy()
# Application-level render cache: retry the same data after a failed frame.
from pet_base import App
root=sharp_window();app=App(root,demo=True)
try:
    app.last_render=None
    with patch.object(app.surface,'present_image',side_effect=OSError('injected render failure')):
        try:app.render()
        except OSError:pass
        else:raise AssertionError('Expected injected failure')
    assert app.last_render is None
    app.render();assert app.last_render is not None
    checks+=1
finally:app.close()
print(json.dumps(dict(result='ok',checks=checks,hidden_before_first_paint=True,
                      primary_and_secondary=True,bounded_retry=True,failed_frame_not_cached=True)))
