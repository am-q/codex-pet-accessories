"""Capture only this process's synthetic demo windows, never the desktop."""
import argparse
import ctypes
from ctypes import wintypes as W
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from PIL import Image, ImageTk
import tkinter as tk
import pet_base
from accessories import render_accessories
from dpi_policy import initialize_native_dpi
from smooth_surface import sharp_window


def capture_owned_window(window):
    """PrintWindow is restricted to the exact HWND owned by this process."""
    user = ctypes.WinDLL('user32', use_last_error=True)
    gdi = ctypes.WinDLL('gdi32', use_last_error=True)
    user.GetParent.argtypes = [W.HWND]; user.GetParent.restype = W.HWND
    user.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
    user.GetWindowRect.argtypes = [W.HWND, ctypes.POINTER(W.RECT)]
    user.GetDC.argtypes = [W.HWND]; user.GetDC.restype = W.HDC
    user.ReleaseDC.argtypes = [W.HWND, W.HDC]
    user.PrintWindow.argtypes = [W.HWND, W.HDC, W.UINT]
    user.RedrawWindow.argtypes = [W.HWND, ctypes.c_void_p, W.HANDLE, W.UINT]
    gdi.CreateCompatibleDC.argtypes = [W.HDC]; gdi.CreateCompatibleDC.restype = W.HDC
    gdi.SelectObject.argtypes = [W.HDC, W.HANDLE]; gdi.SelectObject.restype = W.HANDLE
    gdi.DeleteDC.argtypes = [W.HDC]
    gdi.DeleteObject.argtypes = [W.HANDLE]
    class Header(ctypes.Structure):
        _fields_ = [('size', W.DWORD), ('width', W.LONG), ('height', W.LONG),
                    ('planes', W.WORD), ('bits', W.WORD), ('compression', W.DWORD),
                    ('image_size', W.DWORD), ('xppm', W.LONG), ('yppm', W.LONG),
                    ('colors', W.DWORD), ('important', W.DWORD)]
    class BitmapInfo(ctypes.Structure):
        _fields_ = [('header', Header), ('colors', W.DWORD * 3)]
    gdi.CreateDIBSection.argtypes = [W.HDC, ctypes.POINTER(BitmapInfo), W.UINT,
                                    ctypes.POINTER(ctypes.c_void_p), W.HANDLE, W.DWORD]
    gdi.CreateDIBSection.restype = W.HANDLE
    window.deiconify(); window.lift()
    window.update_idletasks(); window.update()
    hwnd = user.GetParent(window.winfo_id()) or window.winfo_id()
    owner = W.DWORD()
    user.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
    import os
    if owner.value != os.getpid():
        raise RuntimeError('Refusing to capture a window outside this demo process')
    rectangle = W.RECT()
    if not user.GetWindowRect(hwnd, ctypes.byref(rectangle)):
        raise ctypes.WinError(ctypes.get_last_error())
    width, height = rectangle.right - rectangle.left, rectangle.bottom - rectangle.top
    info = BitmapInfo(); info.header = Header(ctypes.sizeof(Header), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
    dc = user.GetDC(hwnd); memory = gdi.CreateCompatibleDC(dc)
    bits = ctypes.c_void_p()
    bitmap = gdi.CreateDIBSection(dc, ctypes.byref(info), 0, ctypes.byref(bits), None, 0)
    if not bitmap or not memory:
        raise ctypes.WinError(ctypes.get_last_error())
    previous = gdi.SelectObject(memory, bitmap)
    try:
        for attempt in range(6):
            window.update_idletasks(); window.update()
            # Paint this HWND and its children; no screen or desktop capture.
            user.RedrawWindow(hwnd, None, None, 0x0001 | 0x0004 | 0x0080 | 0x0100)
            if user.PrintWindow(hwnd, memory, 2 if attempt % 2 == 0 else 0):
                gdi.GdiFlush()
                captured = Image.frombytes('RGB', (width, height),
                                          ctypes.string_at(bits, width * height * 4), 'raw', 'BGRX')
                if max(hi - lo for lo, hi in captured.getextrema()) >= 20:
                    return captured
            time.sleep(0.1)
        raise RuntimeError('Demo capture is blank; refusing to save it')
    finally:
        gdi.SelectObject(memory, previous); gdi.DeleteObject(bitmap)
        gdi.DeleteDC(memory); user.ReleaseDC(hwnd, dc)


def host_window(width, height):
    root = sharp_window()
    root.overrideredirect(True)
    root.geometry(f'{width}x{height}+30+30')
    root.title('Codex Pet Accessories — synthetic demonstration')
    canvas = tk.Canvas(root, width=width, height=height, bg='#171a28', highlightthickness=0)
    canvas.pack()
    root._photos = []
    return root, canvas


def text(canvas, x, y, value, size=18, fill='#f0f1f9', anchor='w', bold=False):
    canvas.create_text(x, y, text=value, anchor=anchor, fill=fill,
                       font=('Microsoft YaHei UI', -size, 'bold' if bold else 'normal'))


def picture(root, canvas, image, x, y, anchor='center'):
    photo = ImageTk.PhotoImage(image, master=root)
    root._photos.append(photo)
    canvas.create_image(x, y, image=photo, anchor=anchor)


def preview(root, canvas, pet, quotas, colors, x, y, scale=2):
    pet_width = round(112 * scale)
    picture(root, canvas, pet.resize((pet_width, round(pet_width * 208 / 192)), Image.Resampling.LANCZOS), x, y)
    for offset, quota, side in ((-174 * scale / 2, quotas[0], 'left'), (174 * scale / 2, quotas[1], 'right')):
        accessory, _ = render_accessories([quota], 'feather', colors, side, demo=True,
                                          pixel_size=(round(112 * scale), round(160 * scale)),
                                          now=quotas[0]['demo_now'], text_tone='light')
        picture(root, canvas, accessory, round(x + offset), round(y + 30 * scale))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pet-sheet', required=True, type=Path)
    args = parser.parse_args()
    sheet = Image.open(args.pet_sheet).convert('RGBA')
    if sheet.size != (1536, 2288):
        raise ValueError('Expected the credited 192×208-cell reference sheet')
    pet = sheet.crop((0, 0, 192, 208))
    initialize_native_dpi()
    output = ROOT / 'docs'
    now = time.time()
    quotas = [{'bucket': 'demo', 'name': 'demo', 'slot': 'primary', 'used': 28,
               'duration': 300, 'reset': now + 102 * 60, 'demo_now': now},
              {'bucket': 'demo', 'name': 'demo', 'slot': 'secondary', 'used': 46,
               'duration': 10080, 'reset': now + (3 * 24 + 6) * 3600}]
    with (tempfile.TemporaryDirectory(prefix='codex-synthetic-demo-') as folder,
         mock.patch.object(pet_base, 'DATA', Path(folder)),
         mock.patch.object(pet_base, 'load_json', side_effect=AssertionError('Private settings access forbidden')),
         mock.patch.object(pet_base.PetState, 'read', side_effect=AssertionError('Real pet state access forbidden')),
         mock.patch.object(pet_base, 'read_usage', side_effect=AssertionError('Account access forbidden')),
         mock.patch.object(pet_base.LivePetTracker, 'update', side_effect=AssertionError('Real tracking forbidden')),
         mock.patch.object(pet_base, 'system_dark', return_value=False)):
        app_root = sharp_window()
        app = pet_base.App(app_root, demo=True)
        try:
            app.settings.update(accessory_style='feather', theme='light', text_tone='light',
                                color_theme='cream', renewal_date='2030-01-01')
            app.snapshot = {'checked_at': now, 'plan': 'Demo', 'quotas': quotas}
            app.last_render = None; app.follow(); app.render()
            colors = app.palette()
            app.show_details(); app.popup.change_page('appearance')
            app_root.update()
            settings = capture_owned_window(app.popup.win)
            app.collapse()
            settings = settings.convert('RGBA')
            pixels = settings.load()
            for row in range(settings.height):
                for column in range(settings.width):
                    if pixels[column, row][:3] == (255, 0, 255):
                        pixels[column, row] = (0, 0, 0, 0)
            app_root.withdraw()

            hero, canvas = host_window(1400, 820)
            try:
                text(canvas, 65, 70, 'Codex Pet Accessories', 34, bold=True)
                text(canvas, 65, 120, '跟随宠物的轻量用量配件  /  Usage at a glance', 19, '#b8bfd7')
                text(canvas, 1325, 70, '虚拟数据 · DEMO', 18, '#d8bdf7', anchor='e', bold=True)
                preview(hero, canvas, pet, quotas, colors, 700, 410)
                text(canvas, 515, 655, '5 小时周期 · 剩余 72%', 19, '#b7ccff', anchor='center')
                text(canvas, 885, 655, '每周周期 · 剩余 54%', 19, '#d9bcfa', anchor='center')
                text(canvas, 700, 735, '独立演示窗口 · 未连接账户 · 非用户桌面截图', 17, '#939bb5', anchor='center')
                text(canvas, 700, 776, 'Pet: HanaAyane / 小蕾米 · remielle-codex-pet', 15, '#939bb5', anchor='center')
                capture_owned_window(hero).save(output / 'demo-pet-accessories.png', optimize=True)
            finally:
                hero.destroy()

            design, canvas = host_window(1400, 1040)
            try:
                text(canvas, 60, 65, '样式与位置  /  Appearance & position', 30, bold=True)
                text(canvas, 60, 110, '应用实际设置面板，使用隔离的演示配置', 18, '#b8bfd7')
                text(canvas, 1320, 65, '虚拟数据 · DEMO', 18, '#d8bdf7', anchor='e', bold=True)
                preview(design, canvas, pet, quotas, colors, 390, 480, 1.65)
                text(canvas, 390, 755, '七种样式 · 左右布局 · 周期双色', 20, '#e3d6f4', anchor='center')
                text(canvas, 390, 805, '右侧面板可向下滚动查看更多设置', 17, '#aab2cd', anchor='center')
                picture(design, canvas, settings, 820, 145, anchor='nw')
                text(canvas, 390, 950, '所有额度与日期均为示例，不读取个人配置', 17, '#939bb5', anchor='center')
                text(canvas, 390, 995, 'Pet: HanaAyane / 小蕾米 · remielle-codex-pet', 15, '#939bb5', anchor='center')
                capture_owned_window(design).save(output / 'demo-settings.png', optimize=True)
            finally:
                design.destroy()
            assert not list(Path(folder).iterdir()), 'Demo wrote runtime data'
        finally:
            app.close()
    print(json.dumps({'screenshots': ['demo-pet-accessories.png', 'demo-settings.png'],
                      'data': 'synthetic', 'desktop_captured': False, 'account_access': False}))


if __name__ == '__main__':
    main()
