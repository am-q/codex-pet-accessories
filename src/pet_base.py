"""Small Windows/Tk companion, with vendored Pillow for per-pixel alpha."""
from __future__ import annotations

import argparse
import sys
import ctypes
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
import traceback
import winreg

from usage_core import PetState, choose_position, countdown, next_delay, period_label, read_usage
from pet_tracking import LivePetTracker
from pet_lifecycle import (log_event, status, log_exception, enable_crash_log,
                           should_auto_start, exit_reason, configure_auto_start)
from base_menu import BaseMenu, monitor_work_area, fit_menu_position
from smooth_surface import (AlphaSurface, render_canvas, sharp_window, native_ui,
                            logical_window_position, logical_pointer_event)
from dpi_policy import initialize_native_dpi, position_logical_window
from appearance import palette, visible_quotas
from accessory_layout import plan_accessories
from accessories import STYLES, CELL_WIDTH, HEIGHT, side_position, render_accessories, ink_insets
from runtime_support import application_version, emit_report, resource_path, standalone, startup_launcher

HERE = Path(__file__).resolve().parent
DATA = Path(os.environ.get('CODEX_PET_DATA_DIR') or (Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'CodexPetAccessories'))
DEFAULTS = {'interval': 300, 'follow': True, 'offset_x': 0, 'offset_y': 0, 'theme': 'auto', 'version': 2, 'color_theme': 'cream', 'density': 'standard', 'accessory_style': 'dial', 'accessory_side': 'auto', 'text_tone':'light', 'accessory_gap':4, 'layout_mode':'split', 'visible_sides':'both', 'swap_sides':False, 'mirror_accessories':False, 'quota_colors':'paired','auto_start':False}


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def system_dark():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
            return winreg.QueryValueEx(key, 'AppsUseLightTheme')[0] == 0
    except OSError:
        return False


class App:
    @native_ui
    def __init__(self, root, demo=False):
        self.root, self.demo = root, demo
        saved_settings = {} if demo else load_json(DATA / 'settings.json', {})
        self.settings = {**DEFAULTS, **saved_settings}
        if saved_settings.get('version') != 2:
            self.settings.update(version=2,follow=True,offset_x=0,offset_y=0)
            if not demo:
                save_json(DATA/'settings.json',self.settings)
        if self.settings['interval'] not in (60, 300, 900):
            self.settings['interval'] = 300
        if self.settings.get('accessory_style') not in STYLES:self.settings['accessory_style']='dial'
        if self.settings.get('accessory_side') not in ('auto','left','right'):self.settings['accessory_side']='auto'
        if self.settings.get('text_tone') not in ('auto','light','dark'):self.settings['text_tone']='light'
        if self.settings.get('accessory_gap') not in (4,12,24):self.settings['accessory_gap']=4
        if self.settings.get('layout_mode') not in ('split','together'):self.settings['layout_mode']='split'
        if self.settings.get('visible_sides') not in ('both','left','right'):self.settings['visible_sides']='both'
        for key in ('swap_sides','mirror_accessories','auto_start'):
            if not isinstance(self.settings.get(key),bool):self.settings[key]=False
        if self.settings.get('quota_colors') not in ('paired','theme'):self.settings['quota_colors']='paired'
        if not demo:save_json(DATA/'settings.json',self.settings)
        self.layout_plan=[]
        self.layout_columns=2
        self.ink_cache={}
        self.actual_side='right'
        self.current_state=None
        self.pet = PetState()
        self.tracker = LivePetTracker()
        self.snapshot = load_json(DATA / 'usage.json', {}) if not demo else {
            'checked_at': time.time(), 'quotas': [{'bucket': 'codex', 'name': 'codex', 'slot': 'primary', 'used': 63, 'duration': 10080, 'reset': time.time()+7200}]}
        self.busy, self.error, self.failures = False, '', 0
        self.last_request = -1000.0
        self.next_refresh = time.monotonic()
        self.reset_checked = set()
        self.index = 0
        self.events = queue.Queue()
        self.cancel_query = threading.Event()
        self.worker = None
        self.closed = False
        self.lifecycle_heartbeat=0
        self.pet_closed_since=None
        self.last_tick_error=-1000.0
        self.dragging = False
        self.anchor_base = None
        self.placement = 'right'
        self.popup = None
        self.hint_until = 0
        self.last_render = None
        self.last_geometry = None
        self.current_visible = True
        self.last_alive_check = 0
        self.codex_alive = True
        self.root.title('Codex 用量配件')
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-toolwindow', True)
        self.transparent = '#ff00ff'
        self.root.configure(bg=self.transparent)
        self.width, self.height = CELL_WIDTH, HEIGHT
        self.canvas = tk.Canvas(root, width=self.width, height=self.height, bg=self.transparent, highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind('<ButtonPress-1>', self.press)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind('<ButtonRelease-1>', self.release)
        self.canvas.bind('<Button-3>', self.menu)
        root.bind('<Escape>', lambda e: self.collapse())
        self.interval_var = tk.IntVar(value=self.settings['interval'])
        self.follow_var = tk.BooleanVar(value=self.settings['follow'])
        self.theme_var = tk.StringVar(value=self.settings['theme'])
        root.protocol('WM_DELETE_WINDOW', lambda:self.close('window_close'))
        root.geometry(f'{self.width}x{self.height}+800+650')
        root.update_idletasks()
        self.surface=AlphaSurface(root)
        self.secondary=sharp_window(root)
        self.secondary.withdraw()
        self.secondary.title('Codex 用量配件 · 另一侧')
        self.secondary.overrideredirect(True)
        self.secondary.attributes('-topmost',True)
        self.secondary.attributes('-toolwindow',True)
        self.secondary.configure(bg=self.transparent)
        self.secondary.geometry(f'{CELL_WIDTH}x{HEIGHT}+800+650')
        self.secondary_canvas=tk.Canvas(self.secondary,width=CELL_WIDTH,height=HEIGHT,bg=self.transparent,highlightthickness=0)
        self.secondary_canvas.pack()
        for event,callback in [('<ButtonPress-1>',self.press),('<B1-Motion>',self.drag),
                               ('<ButtonRelease-1>',self.release),('<Button-3>',self.menu),
                               ('<Enter>',self.hover_enter),('<Leave>',self.hover_leave)]:
            self.secondary_canvas.bind(event,callback)
        self.secondary.bind('<Escape>',lambda e:self.collapse())
        root.update_idletasks()
        self.secondary_surface=AlphaSurface(self.secondary)
        self.secondary_visible=False
        self.secondary_geometry=None
        self.tooltip=None
        self.hover_job=None
        self.canvas.bind('<Enter>',self.hover_enter)
        self.canvas.bind('<Leave>',self.hover_leave)
        self.sync_size()
        self.tick()

    def selected(self):
        quotas = self.snapshot.get('quotas') or []
        if not quotas:
            return None
        return quotas[self.index % len(quotas)]

    def palette(self):
        return palette(self.settings,system_dark())

    def displayed(self):
        if self.layout_plan:return self.layout_plan[0]['quotas']
        return visible_quotas(self.snapshot,self.selected(),self.settings.get('density','standard'))

    def sync_size(self):
        width=CELL_WIDTH*max(1,len(self.displayed()))
        if (width,HEIGHT)!=(self.width,self.height):
            self.width,self.height=width,HEIGHT
            self.canvas.configure(width=self.surface.target_size(width,HEIGHT)[0],height=self.surface.target_size(width,HEIGHT)[1])
            self.last_render=self.last_geometry=None

    def layout_insets(self,quotas,side):
        now=time.time();p=self.palette();checked=self.snapshot.get('checked_at')
        stale=bool(self.error) or bool(checked and now-checked>self.settings['interval']*2+60)
        mirror=self.settings.get('mirror_accessories',False)
        key=(json.dumps(quotas,sort_keys=True),self.settings['accessory_style'],side,mirror,
             tuple(p.values()),self.settings['text_tone'],stale,self.busy,self.demo,int(now/60))
        if key not in self.ink_cache:
            if len(self.ink_cache)>16:self.ink_cache.clear()
            image,_=render_accessories(quotas,self.settings['accessory_style'],p,side,stale,
                self.busy,self.demo,now=now,text_tone=self.settings['text_tone'],mirror=mirror)
            self.ink_cache[key]=ink_insets(image,CELL_WIDTH*max(1,len(quotas)))
        return self.ink_cache[key]

    def set_appearance(self,key,value):
        self.settings[key]=value
        self.persist()
        self.last_render=self.last_geometry=None
        self.sync_size()
        self.follow()
        self.render()

    def hover_enter(self,event):
        self.hover_leave()
        self.hover_job=self.root.after(650,self.show_tooltip)

    def hover_leave(self,event=None):
        if self.hover_job:
            self.root.after_cancel(self.hover_job);self.hover_job=None
        if self.tooltip:
            self.tooltip.destroy();self.tooltip=None

    @native_ui
    def avoid_rect(self):
        x,y=logical_window_position(self.root)
        bounds=(x,y,x+self.width,y+self.height)
        if self.secondary_visible:
            sx,sy=logical_window_position(self.secondary)
            bounds=(min(x,sx),min(y,sy),max(x+self.width,sx+CELL_WIDTH),max(y+self.height,sy+HEIGHT))
        state=self.current_state
        if self.settings['follow'] and state and not self.demo:
            a=state['anchor'];size=state['size']
            # Reserve the upper message bubble and lower native controls too.
            bounds=(min(bounds[0],a['x']-110),min(bounds[1],a['y']-90),
                    max(bounds[2],a['x']+size+110),
                    max(bounds[3],a['y']+size*208/192+48))
        return bounds

    @native_ui
    def show_tooltip(self):
        self.hover_job=None
        if self.popup or not self.current_visible:return
        tip=self.tooltip=sharp_window(self.root)
        tip.withdraw()
        hwnd=ctypes.windll.user32.GetParent(tip.winfo_id())
        position_logical_window(hwnd,*logical_window_position(self.root))
        scale=(self.surface.u.GetDpiForWindow(hwnd) or 96)/96
        p=self.palette()
        tk.Label(tip,text='\n'.join(self.detail_lines()),justify='left',
                 padx=round(10*scale),pady=round(8*scale),
                 bg=p['bg'],fg=p['fg'],font=('Microsoft YaHei UI',-round(12*scale))).pack()
        tip.update_idletasks()
        work=monitor_work_area(*logical_window_position(self.root))
        width,height=tip.winfo_reqwidth(),tip.winfo_reqheight()
        x,y=fit_menu_position(self.avoid_rect(),(round(width/scale),round(height/scale)),work)
        tip.geometry(f'{width}x{height}')
        position_logical_window(hwnd,x,y)
        tip.deiconify()

    @native_ui
    def render(self):
        self.sync_size()
        if not self.layout_plan:return
        now=time.time();p=self.palette()
        checked=self.snapshot.get('checked_at')
        stale=bool(self.error) or bool(checked and now-checked>self.settings['interval']*2+60)
        key=(json.dumps(self.snapshot,sort_keys=True),json.dumps(self.settings,sort_keys=True),
             self.busy,self.error,int(now/60),stale,tuple(p.values()),self.index,
             tuple((plan['side'],json.dumps(plan['quotas'],sort_keys=True)) for plan in self.layout_plan))
        if key==self.last_render:return
        for index,plan in enumerate(self.layout_plan):
            surface=self.surface if index==0 else self.secondary_surface
            width=CELL_WIDTH*len(plan['quotas'])
            size=surface.target_size(width,HEIGHT)
            image,bounds=render_accessories(plan['quotas'],self.settings['accessory_style'],p,
                plan['side'],stale,self.busy,self.demo,size,now,self.settings['text_tone'],
                self.settings.get('mirror_accessories',False))
            surface.present_image(image)
            if index==0:self.full_image,self.text_bounds=image,bounds
        # Cache only a frame that actually reached every visible surface.
        self.last_render=key

    def detail_lines(self):
        lines=[]
        for q in self.snapshot.get('quotas',[]):
            used=q.get('used')
            lines.append(f"{period_label(q['duration'])} · 已用 {used:g}%" if used is not None else f"{period_label(q['duration'])} · 未知")
            reset=q.get('reset')
            lines.append(datetime.fromtimestamp(reset).strftime('%m/%d %H:%M:%S 重置') if reset else '重置时间未知')
        checked=self.snapshot.get('checked_at')
        lines.append('更新于 '+(datetime.fromtimestamp(checked).strftime('%H:%M:%S') if checked else '尚未成功'))
        if self.error:
            lines.append('暂未更新，请稍后重试')
        return lines

    @native_ui
    def show_details(self):
        from types import SimpleNamespace
        x,y=logical_window_position(self.root)
        self.menu(SimpleNamespace(x_root=x+self.width,y_root=y))

    def collapse(self):
        if self.popup:self.popup.close()
        self.hover_leave()

    @native_ui
    def press(self, event):
        self.dragging = False
        event=logical_pointer_event(event)
        self.drag_start = (event.x_root, event.y_root, *logical_window_position(self.root))
        self.drag_anchor=dict(self.free_anchor) if hasattr(self,'free_anchor') else dict(x=800,y=650)
        self.drag_secondary=logical_window_position(self.secondary)

    @native_ui
    def drag(self, event):
        event=logical_pointer_event(event)
        sx, sy, wx, wy = self.drag_start
        dx, dy = event.x_root-sx, event.y_root-sy
        if abs(dx)+abs(dy) > 5:
            self.dragging = True
            if self.settings['follow']:
                self.hint_until=time.monotonic()+2
                return
            self.free_anchor={**self.drag_anchor,'x':self.drag_anchor['x']+dx,'y':self.drag_anchor['y']+dy}
            self.move_window(wx+dx, wy+dy)
            if self.secondary_visible:
                self.move_surface(self.secondary_surface,*[v+d for v,d in zip(self.drag_secondary,(dx,dy))],CELL_WIDTH,HEIGHT)

    @native_ui
    def move_surface(self,surface,x,y,width,height):
        position_logical_window(surface.hwnd,x,y)
        pixel_size=surface.target_size(width,height)
        canvas=self.canvas if surface is self.surface else self.secondary_canvas
        canvas.configure(width=pixel_size[0],height=pixel_size[1])
        surface.root.geometry(f'{pixel_size[0]}x{pixel_size[1]}')
        surface.root.update_idletasks()
        position_logical_window(surface.hwnd,x,y)
        if surface.pixel_size!=pixel_size:self.last_render=None

    def move_window(self,x,y):
        self.move_surface(self.surface,x,y,self.width,self.height)

    @native_ui
    def release(self, event):
        if self.dragging:
            if self.settings['follow']:
                self.dragging=False
                return
            x, y = logical_window_position(self.root)
            if self.settings['follow'] and self.anchor_base:
                self.settings['offset_x'] = x-self.anchor_base[0]
                self.settings['offset_y'] = y-self.anchor_base[1]
            else:
                self.settings['position'] = [x, y]
                self.settings['free_anchor']=self.free_anchor
            self.persist()
            self.dragging = False
            self.last_geometry = None
        else:
            self.show_details()

    def persist(self):
        if not self.demo:
            save_json(DATA / 'settings.json', self.settings)

    def set_interval(self):
        self.settings['interval'] = self.interval_var.get()
        self.next_refresh = time.monotonic()+self.settings['interval']
        self.persist()

    @native_ui
    def set_follow(self):
        self.settings['follow'] = self.follow_var.get()
        self.settings.update(offset_x=0,offset_y=0)
        self.settings['position'] = list(logical_window_position(self.root))
        if not self.settings['follow'] and self.current_state:
            self.settings['free_anchor']=dict(self.current_state['anchor'])
        self.persist()
        self.last_geometry = None

    def set_theme(self):
        self.settings['theme'] = self.theme_var.get()
        self.persist()
        self.last_render = None

    def reset_offset(self):
        self.settings.update(offset_x=0, offset_y=0, follow=True)
        self.follow_var.set(True)
        self.persist()
        self.last_geometry = None

    def next_quota(self):
        self.index += 1
        self.last_render = None

    @native_ui
    def menu(self, event):
        event=logical_pointer_event(event)
        self.hover_leave()
        if self.popup:
            self.popup.close()
        self.popup=BaseMenu(self,event.x_root,event.y_root)

    def refresh(self, manual=False):
        now = time.monotonic()
        if self.demo or self.busy or now-self.last_request < 30:
            return
        self.busy, self.last_request = True, now
        self.last_render = None
        def worker():
            try:
                self.events.put(('success', read_usage(cancel=self.cancel_query)))
            except Exception as exc:
                msg = str(exc) if isinstance(exc, (RuntimeError, TimeoutError)) else '查询失败，请稍后重试'
                self.events.put(('error', msg))
        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    @native_ui
    def follow(self):
        state=None if self.demo else self.pet.read()
        if not self.demo:state=self.tracker.update(state)
        self.current_state=state
        visible=self.demo or not self.settings['follow'] or (bool(state and state['open']) and self.codex_alive)
        if self.dragging and not self.settings['follow']:return
        if self.settings['follow'] and state and not self.demo:
            anchor=state['anchor'];size=state['size']
        else:
            x,y=self.settings.get('position',[600,500])
            anchor=dict(self.settings.get('free_anchor') or dict(x=x+160,y=y))
            size=112
        self.free_anchor=dict(anchor)
        work=monitor_work_area(anchor['x']+size/2,anchor['y']+size/2)
        quotas=visible_quotas(self.snapshot,self.selected(),self.settings.get('density','standard'))
        plans=plan_accessories(quotas,self.settings,anchor,size,work,self.layout_insets) if visible else []
        old_signature=[(p['side'],p['quotas']) for p in self.layout_plan]
        self.layout_plan=plans
        if old_signature!=[(p['side'],p['quotas']) for p in plans]:self.last_render=None
        visible=bool(plans)
        if visible!=self.current_visible:
            self.current_visible=visible
            if visible:
                self.root.deiconify();self.next_refresh=min(self.next_refresh,time.monotonic())
            else:
                if self.popup:self.popup.close()
                self.hover_leave();self.root.withdraw()
            self.last_geometry=self.last_render=None
        secondary_visible=len(plans)>1
        if secondary_visible!=self.secondary_visible:
            self.secondary_visible=secondary_visible
            if secondary_visible:self.secondary.deiconify()
            else:self.secondary.withdraw()
            self.secondary_geometry=None;self.last_render=None
        if not visible:return
        self.actual_side=self.placement=plans[0]['side']
        self.layout_columns=len(plans[0]['quotas']);self.sync_size()
        self.anchor_base=(plans[0]['x'],plans[0]['y'])
        for index,plan in enumerate(plans):
            width=CELL_WIDTH*len(plan['quotas'])
            geometry=(width,HEIGHT,plan['x'],plan['y'])
            previous=self.last_geometry if index==0 else self.secondary_geometry
            surface=self.surface if index==0 else self.secondary_surface
            if geometry!=previous or surface.pixel_size!=surface.target_size(width,HEIGHT):
                self.hover_leave()
                self.move_surface(surface,plan['x'],plan['y'],width,HEIGHT)
                if index==0:self.last_geometry=geometry
                else:self.secondary_geometry=geometry

        # Geometry may be unchanged while another window covers the accessories.
        # Match the live pet's stack every follow tick without activating anything.
        # Tk's secondary is owned by the main surface and must remain above it.
        if not self.demo and self.settings['follow'] and self.tracker.window:
            reference=self.tracker.window
            surfaces=([self.secondary_surface] if self.secondary_visible else [])+[self.surface]
            for surface in surfaces:
                surface.follow_stack_below(reference)
                reference=surface.hwnd

    def set_auto_start(self,enabled):
        if not self.demo:configure_auto_start(DATA,HERE/'pet_base.py',enabled)
        self.settings['auto_start']=bool(enabled)
        self.persist()

    def exit_from_menu(self):
        if self.settings.get('auto_start'):self.set_auto_start(False)
        self.close('user_exit')

    @native_ui
    def tick(self):
        if self.closed:return
        try:self.tick_once()
        except Exception:
            now=time.monotonic()
            if not self.demo and now-self.last_tick_error>=5:
                log_exception(DATA,'tick_error',sys.exc_info());self.last_tick_error=now
        finally:
            if not self.closed:self.root.after(25 if self.tracker.drag.start else 80,self.tick)

    def tick_once(self):
        if self.closed:
            return
        if not self.demo and (DATA / 'stop.flag').exists():
            (DATA / 'stop.flag').unlink(missing_ok=True)
            self.close('stop_request')
            return
        now = time.monotonic()
        while not self.events.empty():
            kind, value = self.events.get_nowait()
            self.busy = False
            if kind == 'success':
                self.snapshot, self.error, self.failures = value, '', 0
                if not self.demo:
                    save_json(DATA / 'usage.json', value)
            else:
                self.error = value
                self.failures += 1
            self.next_refresh = now+next_delay(self.settings['interval'], self.failures)
            self.last_render = None
        if now-self.last_alive_check >= 5:
            self.codex_alive = desktop_running()
            self.last_alive_check = now
        if not self.demo:
            reason=exit_reason(self.codex_alive,self.pet.read(),self.settings.get('auto_start',False))
            if reason=='codex_exit':
                self.close(reason);return
            if reason=='pet_closed':
                if self.pet_closed_since is None:self.pet_closed_since=now
                if now-self.pet_closed_since>=2:self.close(reason);return
            else:self.pet_closed_since=None
        self.sync_size()
        self.follow()
        if not self.demo and now-self.lifecycle_heartbeat>=30:
            status(DATA,'running',visible=self.current_visible,tracking=self.tracker.mode,auto_start=self.settings.get('auto_start',False))
            self.lifecycle_heartbeat=now
        if self.current_visible and not self.demo:
            if now >= self.next_refresh:
                self.refresh()
            # One extra check after each advertised reset, never pretend a reset succeeded.
            for q in self.snapshot.get('quotas', []):
                reset = q.get('reset')
                if reset and reset not in self.reset_checked and 2 < time.time()-reset < 300 and not self.busy and not self.error and now-self.last_request >= 30:
                    self.reset_checked.add(reset)
                    self.refresh()
        self.render()

    def close(self,reason='close_request'):
        if self.closed:return
        self.closed = True
        if not self.demo:log_event(DATA,'exit_requested',reason=reason)
        self.root.withdraw();self.secondary.withdraw()
        self.hover_leave()
        if self.popup:self.popup.close()
        self.cancel_query.set()
        if self.worker and self.worker.is_alive():
            self.worker.join(timeout=10)
        self.root.destroy()
        if not self.demo:
            status(DATA,'closed',reason=reason)
            log_event(DATA,'closed',reason=reason,query_worker_alive=bool(self.worker and self.worker.is_alive()))


def desktop_running():
    """Process-name-only check; no window inspection or UI automation."""
    from ctypes import wintypes
    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [('dwSize',wintypes.DWORD),('cntUsage',wintypes.DWORD),('th32ProcessID',wintypes.DWORD),('th32DefaultHeapID',ctypes.c_size_t),('th32ModuleID',wintypes.DWORD),('cntThreads',wintypes.DWORD),('th32ParentProcessID',wintypes.DWORD),('pcPriClassBase',wintypes.LONG),('dwFlags',wintypes.DWORD),('szExeFile',wintypes.WCHAR*260)]
    k = ctypes.windll.kernel32
    k.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD,wintypes.DWORD]
    k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k.Process32FirstW.argtypes = [wintypes.HANDLE,ctypes.POINTER(PROCESSENTRY32W)]
    k.Process32NextW.argtypes = k.Process32FirstW.argtypes
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = k.CreateToolhelp32Snapshot(2,0)
    if handle == ctypes.c_void_p(-1).value:
        return True
    try:
        entry=PROCESSENTRY32W();entry.dwSize=ctypes.sizeof(entry)
        ok=k.Process32FirstW(handle,ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() in ('chatgpt.exe','codex.exe'):
                # The CLI alone is not the desktop application.
                if entry.szExeFile.lower() == 'chatgpt.exe':
                    return True
            ok=k.Process32NextW(handle,ctypes.byref(entry))
        return False
    finally:
        k.CloseHandle(handle)


def main():
    global DATA
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir')
    parser.add_argument('--report',help='Write a diagnostic result to an explicit JSON file')
    parser.add_argument('--auto-start',action='store_true')
    parser.add_argument('--configure-auto-start',choices=('on','off'))
    parser.add_argument('--stop',action='store_true')
    parser.add_argument('--demo',action='store_true')
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--preview',action='store_true',help='Temporary framed visual QA window; no network')
    args=parser.parse_args()
    if args.data_dir:DATA=Path(args.data_dir).resolve()
    if args.configure_auto_start or args.stop:
        enabled=args.configure_auto_start=='on' and not args.stop
        configure_auto_start(DATA,HERE/'pet_base.py',enabled)
        settings=load_json(DATA/'settings.json',{});settings['auto_start']=enabled
        save_json(DATA/'settings.json',settings)
        if args.stop:(DATA/'stop.flag').write_text('user-stop',encoding='utf-8')
        emit_report({'auto_start':enabled,'configured':True},args.report);return
    if args.auto_start:
        settings=load_json(DATA/'settings.json',{})
        if not should_auto_start(settings,desktop_running(),PetState().read()):return

    if args.check:
        start=time.monotonic()
        data=read_usage()
        emit_report({'query_seconds':round(time.monotonic()-start,2),**data},args.report)
        return
    initialize_native_dpi()
    mutex=None
    if not args.demo and not args.smoke and not args.preview:
        k=ctypes.WinDLL('kernel32',use_last_error=True)
        k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p]
        k.CreateMutexW.restype=ctypes.c_void_p
        mutex=k.CreateMutexW(None,False,'Local\\CodexPetAccessories')
        if ctypes.get_last_error()==183:
            return
    if not (args.demo or args.smoke or args.preview):
        enable_crash_log(DATA)
        log_event(DATA,'starting',automatic=args.auto_start)
    root=sharp_window()
    app=App(root,demo=args.demo or args.smoke or args.preview)
    if app.closed:return
    if not (args.demo or args.smoke or args.preview):
        def record_startup():
            save_json(DATA/'startup.json', {'version':application_version(),'accessory_style':app.settings['accessory_style'],'accessory_side':app.actual_side,'color_theme':app.settings.get('color_theme'),'density':app.settings.get('density'),'renderer':'supersampled-per-pixel-alpha','pixel_size':app.surface.pixel_size,'pid':os.getpid(),'started_at':time.time(),'visible':bool(root.winfo_viewable()),'x':logical_window_position(root)[0],'y':logical_window_position(root)[1],'placement':app.placement,'panels':[dict(side=p['side'],x=p['x'],y=p['y'],cycles=len(p['quotas'])) for p in app.layout_plan],'tracking':app.tracker.mode,'follow':app.settings['follow']})
        root.after(1200,record_startup)
    if args.preview:
        root.overrideredirect(False)
        root.attributes('-toolwindow',False)
        root.title('用量配件 - 界面预览')
        root.after(120000,app.close)
    root.report_callback_exception=lambda *err: log_exception(DATA,'callback_error',err)
    if args.smoke:
        def smoke():
            for style in STYLES:
                app.set_appearance('accessory_style',style)
                assert app.full_image.getbbox()
            app.show_details();assert app.popup
            app.collapse();assert app.popup is None
            assert '63%' in '\n'.join(app.detail_lines())
            from types import SimpleNamespace
            app.menu(SimpleNamespace(x_root=800,y_root=650))
            menu=app.popup
            menu.show_renewal_editor()
            menu.date_var.set('2026-02-30');menu.save_renewal()
            assert menu.error_var.get()
            menu.date_var.set('2030-01-01');menu.save_renewal()
            assert app.settings['renewal_date']=='2030-01-01'
            assert '01/01' in menu.renewal_label.cget('text')
            menu.set_theme('dark')
            root.update_idletasks()
            assert menu.panel_size[1]<=560,menu.panel_size
            menu.close()
            emit_report({'ui':'ok','styles':list(STYLES),'geometry':root.geometry(),
                         'version':application_version(),'standalone':standalone(),
                         'scheduler_resource':resource_path('pet_lifecycle_task.ps1').is_file(),
                         'auto_start_uses_executable':standalone() and startup_launcher(HERE/'pet_base.py')[1] is None},args.report)
            app.close()
        root.after(600,smoke)
    root.mainloop()
    if not (args.demo or args.smoke or args.preview):log_event(DATA,'mainloop_ended',closed=app.closed)
    if mutex:
        ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(mutex))


if __name__=='__main__':
    try:main()
    except BaseException:
        log_exception(DATA,'fatal_error',sys.exc_info())
        raise
