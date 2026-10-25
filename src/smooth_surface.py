"""Supersampled UI raster + true per-pixel Windows alpha, no color-key edges."""
import ctypes
from ctypes import wintypes as W
from functools import lru_cache
from pathlib import Path
import os
import tkinter.font as tkfont

from PIL import Image,ImageDraw,ImageFont,ImageFilter


@lru_cache(maxsize=48)
def font_at(size):
    fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    for name in ('msyh.ttc', 'msyh.ttf', 'simhei.ttf', 'segoeui.ttf'):
        path = fonts / name
        if path.exists():return ImageFont.truetype(str(path),size)
    raise RuntimeError('No supported Windows font was found.')


def render_canvas(canvas,width,height,pixel_size=None):
    """Supersample geometry before presenting in the window coordinate space."""
    pw,ph=pixel_size or (width,height)
    factor=4
    sx,sy=pw/width*factor,ph/height*factor
    result=Image.new('RGBA',(pw*factor,ph*factor))
    for item in canvas.find_all():
        kind=canvas.type(item)
        coords=canvas.coords(item)
        color=canvas.itemcget(item,'fill')
        if not color:continue
        points=[v*(sx if i%2==0 else sy) for i,v in enumerate(coords)]
        target=result
        shadow='soft-shadow' in canvas.gettags(item)
        if shadow:target=Image.new('RGBA',result.size)
        draw=ImageDraw.Draw(target)
        if shadow:
            rgb=canvas.winfo_rgb(color)
            color=tuple(v//257 for v in rgb)+(72,)
        if kind=='oval':draw.ellipse(points,fill=color)
        elif kind=='rectangle':draw.rectangle(points,fill=color)
        elif kind=='polygon':
            if 'silhouette' in canvas.gettags(item):
                draw.polygon(points,fill=color)
                continue
            # These polygons are exclusively the app's round_rect helper.
            xs,ys=points[::2],points[1::2]
            radius=max(0,points[0]-min(xs))
            draw.rounded_rectangle((min(xs),min(ys),max(xs),max(ys)),radius=radius,fill=color)
        elif kind=='text':
            spec=tkfont.Font(root=canvas,font=canvas.itemcget(item,'font')).actual()
            size=spec['size']
            logical_px=abs(size) if size<0 else size*96/72
            font=font_at(max(1,round(logical_px*sy)))
            text=canvas.itemcget(item,'text')
            box=draw.textbbox((0,0),text,font=font)
            x,y=points;anchor=canvas.itemcget(item,'anchor')
            if anchor=='e':x-=box[2]-box[0]
            elif anchor=='center':x-=(box[2]-box[0])/2
            y-=(box[3]-box[1])/2+box[1]
            draw.text((x,y),text,font=font,fill=color)
        if shadow:
            target=target.filter(ImageFilter.GaussianBlur(1.0*factor))
            result=Image.alpha_composite(result,target)
    # Pillow downsamples RGBA with premultiplied-alpha handling; no matte halo.
    return result.resize((pw,ph),Image.Resampling.LANCZOS)


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_=[('biSize',W.DWORD),('biWidth',W.LONG),('biHeight',W.LONG),('biPlanes',W.WORD),('biBitCount',W.WORD),('biCompression',W.DWORD),('biSizeImage',W.DWORD),('biXPelsPerMeter',W.LONG),('biYPelsPerMeter',W.LONG),('biClrUsed',W.DWORD),('biClrImportant',W.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_=[('bmiHeader',BITMAPINFOHEADER),('bmiColors',W.DWORD*3)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_=[('BlendOp',W.BYTE),('BlendFlags',W.BYTE),('SourceConstantAlpha',W.BYTE),('AlphaFormat',W.BYTE)]



from dpi_policy import (dpi_context, logical_coordinates, native_ui,
                        logical_window_position, logical_pointer_event)


def sharp_window(master=None):
    """Realize each accessory HWND as per-monitor-v2, disabling bitmap stretch."""
    import tkinter as tk
    with dpi_context(-4):
        window=tk.Tk() if master is None else tk.Toplevel(master)
        # Keep the shared font baseline stable for existing raster/tooltips.
        # The settings menu supplies its own native-pixel fonts and layout.
        if master is None:window.tk.call('tk','scaling',96/72)
        window.overrideredirect(True)
        window.attributes('-topmost',True)
        window.attributes('-toolwindow',True)
        window.update_idletasks()
    return window


class AlphaSurface:
    def __init__(self,root):
        self.root=root
        self.image=None
        self.pixel_size=None
        self.alpha_recoveries=0
        self.u=ctypes.WinDLL('user32',use_last_error=True)
        self.g=ctypes.WinDLL('gdi32',use_last_error=True)
        u,g=self.u,self.g
        u.GetParent.argtypes=[W.HWND];u.GetParent.restype=W.HWND
        self.hwnd=u.GetParent(root.winfo_id()) or root.winfo_id()
        u.GetWindowLongW.argtypes=[W.HWND,ctypes.c_int];u.GetWindowLongW.restype=ctypes.c_long
        u.SetWindowLongW.argtypes=[W.HWND,ctypes.c_int,ctypes.c_long]
        u.GetWindowRect.argtypes=[W.HWND,ctypes.POINTER(W.RECT)]
        u.GetDpiForWindow.argtypes=[W.HWND];u.GetDpiForWindow.restype=W.UINT
        u.SetThreadDpiAwarenessContext.argtypes=[ctypes.c_void_p];u.SetThreadDpiAwarenessContext.restype=ctypes.c_void_p
        u.UpdateLayeredWindow.argtypes=[W.HWND,W.HDC,ctypes.POINTER(W.POINT),ctypes.POINTER(W.SIZE),W.HDC,ctypes.POINTER(W.POINT),W.DWORD,ctypes.POINTER(BLENDFUNCTION),W.DWORD]
        u.UpdateLayeredWindow.restype=W.BOOL
        g.CreateCompatibleDC.argtypes=[W.HDC];g.CreateCompatibleDC.restype=W.HDC
        g.CreateDIBSection.argtypes=[W.HDC,ctypes.POINTER(BITMAPINFO),W.UINT,ctypes.POINTER(ctypes.c_void_p),W.HANDLE,W.DWORD]
        g.CreateDIBSection.restype=W.HBITMAP
        g.SelectObject.argtypes=[W.HDC,W.HANDLE];g.SelectObject.restype=W.HANDLE
        g.DeleteObject.argtypes=[W.HANDLE];g.DeleteDC.argtypes=[W.HDC]
        self.enable_alpha()

    def enable_alpha(self):
        style=self.u.GetWindowLongW(self.hwnd,-20)
        # Clear previous color-key/global-alpha state before switching modes.
        self.u.SetWindowLongW(self.hwnd,-20,style & ~0x80000)
        self.u.SetWindowLongW(self.hwnd,-20,style | 0x80000)

    def follow_stack_below(self,reference):
        """Reorder only this accessory HWND, without moving it or taking focus."""
        u=self.u
        u.IsWindowVisible.argtypes=[W.HWND];u.IsWindowVisible.restype=W.BOOL
        u.GetWindow.argtypes=[W.HWND,W.UINT];u.GetWindow.restype=W.HWND
        u.SetWindowPos.argtypes=[W.HWND,W.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.UINT]
        u.SetWindowPos.restype=W.BOOL
        if not reference or reference==self.hwnd:
            return False
        if not u.IsWindowVisible(reference) or not u.IsWindowVisible(self.hwnd):
            return False
        if u.GetWindow(self.hwnd,3)==reference:  # GW_HWNDPREV: already adjacent.
            return False
        # NOSIZE | NOMOVE | NOACTIVATE | NOOWNERZORDER. Reference is read-only;
        # hWnd (the window being changed) is always our own accessory surface.
        return bool(u.SetWindowPos(self.hwnd,reference,0,0,0,0,0x1|0x2|0x10|0x200))

    def target_size(self,width,height):
        # Only the immutable logical design size and the monitor DPI determine
        # the bitmap size. Never infer DPI from the previous window dimensions.
        # Production HWNDs are per-monitor-v2, so these pixels reach the screen
        # directly; legacy/unaware test windows report 96 DPI and stay logical.
        scale=(self.u.GetDpiForWindow(self.hwnd) or 96)/96
        return max(1,round(width*scale)),max(1,round(height*scale))

    def present(self,canvas,width,height):
        size=self.target_size(width,height)
        rgba=render_canvas(canvas,width,height,size)
        self.present_image(rgba)

    def present_image(self,rgba):
        size=rgba.size
        pixels=rgba.convert('RGBa').tobytes('raw','BGRa')
        u,g=self.u,self.g
        dc=g.CreateCompatibleDC(None)
        if not dc:raise ctypes.WinError(ctypes.get_last_error())
        bitmap=old=None
        try:
            info=BITMAPINFO()
            info.bmiHeader=BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER),size[0],-size[1],1,32,0,len(pixels),0,0,0,0)
            bits=ctypes.c_void_p()
            bitmap=g.CreateDIBSection(dc,ctypes.byref(info),0,ctypes.byref(bits),None,0)
            if not bitmap:raise ctypes.WinError(ctypes.get_last_error())
            ctypes.memmove(bits,pixels,len(pixels))
            old=g.SelectObject(dc,bitmap)
            origin=W.POINT(0,0);dimensions=W.SIZE(*size);blend=BLENDFUNCTION(0,0,255,1)
            with dpi_context(-4):
                ok=u.UpdateLayeredWindow(self.hwnd,None,None,ctypes.byref(dimensions),dc,ctypes.byref(origin),0,ctypes.byref(blend),2)
                if not ok and ctypes.get_last_error()==87:
                    # Tk can reset layering when a never-painted window is
                    # hidden then shown. Re-arm per-pixel alpha and retry once.
                    # https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-setlayeredwindowattributes
                    self.enable_alpha()
                    ok=u.UpdateLayeredWindow(self.hwnd,None,None,ctypes.byref(dimensions),dc,ctypes.byref(origin),0,ctypes.byref(blend),2)
                    if ok:self.alpha_recoveries+=1
                if not ok:raise ctypes.WinError(ctypes.get_last_error())
            self.image=rgba
            self.pixel_size=size
        finally:
            if old:g.SelectObject(dc,old)
            if bitmap:g.DeleteObject(bitmap)
            g.DeleteDC(dc)
