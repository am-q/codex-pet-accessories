"""Themed, transient menu with account facts and a locally entered renewal date."""
from datetime import date,datetime
import ctypes
from ctypes import wintypes as W
import re
import time
import tkinter as tk
from tkinter import colorchooser, messagebox
from appearance import THEMES, palette, reset_caption, status_caption
from usage_core import period_label, countdown
from accessories import STYLES
from smooth_surface import sharp_window
from dpi_policy import (native_ui as native_menu, logical_coordinates,
                        logical_window_position, logical_pointer_event, position_logical_window)


def menu_font(points):
    """Use a stable logical font size; the menu scales it to native pixels."""
    return ('Microsoft YaHei UI', -round(points * 96 / 72))


def parse_renewal(value):
    value=value.strip()
    if not value:
        return ''
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
        raise ValueError('请使用 YYYY-MM-DD 格式')
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError('这个日期不存在，请检查年月日') from None


def renewal_caption(value,today=None):
    if not value:
        return '未设置'
    try:
        target=date.fromisoformat(value)
    except ValueError:
        return '日期无效，请修改'
    days=(target-(today or date.today())).days
    suffix=f'还有 {days} 天' if days>0 else '今天 · 请核对账单' if days==0 else '已过期 · 请更新日期'
    return f'{target:%m/%d} · {suffix}'


def fit_menu_position(avoid,size,work,manual=None):
    """Prefer either side of the preview, keeping the panel inside the monitor."""
    ax,ay,ar,ab=avoid
    width,height=size
    left,top,right,bottom=work
    def clamp(x,y):
        return (round(max(left+6,min(x,right-width-6))),
                round(max(top+6,min(y,bottom-height-6))))
    if manual is not None:return clamp(*manual)
    gap=14
    candidates=[(ar+gap,ab-height),(ax-width-gap,ab-height),
                (ax,ay-height-gap),(ax,ab+gap)]
    def score(point):
        x,y=point
        return max(0,min(x+width,ar)-max(x,ax))*max(0,min(y+height,ab)-max(y,ay))
    return min((clamp(*point) for point in candidates),key=score)


@logical_coordinates
def monitor_work_area(x,y):
    class MonitorInfo(ctypes.Structure):
        _fields_=[('cbSize',W.DWORD),('rcMonitor',W.RECT),('rcWork',W.RECT),('dwFlags',W.DWORD)]
    u=ctypes.windll.user32
    u.MonitorFromPoint.argtypes=[W.POINT,W.DWORD];u.MonitorFromPoint.restype=W.HANDLE
    u.GetMonitorInfoW.argtypes=[W.HANDLE,ctypes.POINTER(MonitorInfo)]
    info=MonitorInfo();info.cbSize=ctypes.sizeof(info)
    monitor=u.MonitorFromPoint(W.POINT(round(x),round(y)),2)
    if u.GetMonitorInfoW(monitor,ctypes.byref(info)):
        return info.rcWork.left,info.rcWork.top,info.rcWork.right,info.rcWork.bottom
    return (0,0,1920,1080)


class BaseMenu:
    @native_menu
    def __init__(self,app,x,y):
        self.app=app
        self.p=app.palette()
        self.closed=False
        self.page='info'
        self.choosing_color=False
        self.info_labels={}
        self.win=sharp_window(app.root)
        self.win.withdraw()
        self.panel_size=(308,560)
        self.scale=1.0
        self.move_panel(x,y)
        self.scale=self.window_scale()
        self.win.title('用量配件设置')
        self.win.overrideredirect(True)
        self.win.attributes('-topmost',True)
        self.win.attributes('-toolwindow',True)
        self.win.configure(bg=app.transparent)
        self.win.attributes('-transparentcolor',app.transparent)
        self.canvas=tk.Canvas(self.win,bg=app.transparent,highlightthickness=0)
        self.canvas.pack(fill='both',expand=True)
        self.viewport=tk.Canvas(self.canvas,bg=self.p['bg'],highlightthickness=0)
        self.viewport_item=self.canvas.create_window(16,15,window=self.viewport,anchor='nw',width=276)
        self.scrollbar=tk.Scrollbar(self.canvas,orient='vertical',command=self.viewport.yview,
                                    width=10,bd=0,highlightthickness=0)
        self.viewport.configure(yscrollcommand=self.scrollbar.set)
        self.body=tk.Frame(self.viewport,bg=self.p['bg'])
        self.body_item=self.viewport.create_window(0,0,window=self.body,anchor='nw',width=276)
        self.win.bind('<MouseWheel>',self.scroll)
        self.origin=(x,y)
        self.manual_position=None
        self.drag_origin=None
        self.win.bind('<Escape>',lambda e:self.close())
        self.win.bind('<FocusOut>',lambda e:self.win.after_idle(self.check_focus))
        self.win.bind('<ButtonPress-1>',self.outside_click,add='+')
        self.win.bind('<B1-Motion>',self.drag_panel,add='+')
        self.win.bind('<ButtonRelease-1>',self.end_drag,add='+')
        self.build()
        self.win.deiconify()
        self.win.update_idletasks()
        self.win.focus_force()
        self.win.grab_set()
        self.update_info()

    def window_scale(self):
        u=ctypes.windll.user32
        u.GetDpiForWindow.argtypes=[W.HWND];u.GetDpiForWindow.restype=W.UINT
        u.GetParent.argtypes=[W.HWND];u.GetParent.restype=W.HWND
        return (u.GetDpiForWindow(u.GetParent(self.win.winfo_id())) or 96)/96

    def px(self,value):
        return round(value*self.scale)

    def scale_content(self,parent):
        """Scale immutable widget measurements, never previously scaled values."""
        for widget in parent.winfo_children():
            if not hasattr(widget,'_menu_units'):
                options={}
                for key in ('padx','pady','borderwidth','highlightthickness'):
                    if key in widget.keys():options[key]=float(widget.cget(key))
                if isinstance(widget,(tk.Frame,tk.Canvas)):
                    for key in ('width','height'):options[key]=float(widget.cget(key))
                font=widget.tk.splitlist(widget.cget('font')) if 'font' in widget.keys() else None
                manager=widget.winfo_manager()
                geometry=widget.pack_info() if manager=='pack' else widget.grid_info() if manager=='grid' else {}
                padding={key:tuple(float(x) for x in (value if isinstance(value,tuple) else widget.tk.splitlist(str(value))))
                         for key,value in geometry.items() if key in ('padx','pady','ipadx','ipady')}
                drawing={item:widget.coords(item) for item in widget.find_all()} if isinstance(widget,tk.Canvas) else {}
                widget._menu_units=options,font,manager,padding,drawing
            options,font,manager,padding,drawing=widget._menu_units
            widget.configure(**{key:self.px(value) for key,value in options.items()})
            if font:
                family,size,*style=font
                widget.configure(font=(family,-self.px(abs(int(size))),*style))
            scaled={key:tuple(self.px(x) for x in value) for key,value in padding.items()}
            if manager=='pack':widget.pack_configure(**scaled)
            elif manager=='grid':widget.grid_configure(**scaled)
            for item,coords in drawing.items():widget.coords(item,*(self.px(x) for x in coords))
            self.scale_content(widget)

    def text(self,parent,value,size=9,muted=False,**kwargs):
        return tk.Label(parent,text=value,bg=self.p['bg'],fg=self.p['muted' if muted else 'fg'],
                        font=menu_font(size),anchor='w',**kwargs)

    def button(self,parent,title,command,selected=False):
        bg=self.p['track'] if selected else self.p['top']
        fg=self.p['fg']
        button=tk.Button(parent,text=('✓ '+title) if selected else title,command=command,bg=bg,fg=fg,
                         activebackground=self.p['track'],activeforeground=self.p['fg'],
                         relief='flat',bd=0,padx=10,pady=7,cursor='hand2',
                         highlightthickness=1,highlightbackground=bg,highlightcolor=self.p['accent'],
                         font=menu_font(9))
        button.bind('<Enter>',lambda e:button.configure(bg=self.p['track']))
        button.bind('<Leave>',lambda e:button.configure(bg=bg))
        return button

    def separator(self):
        tk.Frame(self.body,height=1,bg=self.p['track']).pack(fill='x',pady=11)

    def row(self,key,label):
        frame=tk.Frame(self.body,bg=self.p['bg'])
        frame.pack(fill='x',pady=3)
        self.text(frame,label,8,True).pack(side='left')
        value=self.text(frame,'—',8)
        value.pack(side='right')
        self.info_labels[key]=value

    @native_menu
    def build(self):
        self.viewport.yview_moveto(0)
        self.quota_signature=[(q.get('bucket'),q.get('duration')) for q in self.app.snapshot.get('quotas',[])]
        for widget in self.body.winfo_children():
            widget.destroy()
        self.info_labels={}
        head=tk.Frame(self.body,bg=self.p['bg']);head.pack(fill='x')
        title=self.text(head,'用量与订阅',11);title.pack(side='left')
        hint=self.text(head,'拖动可移动',8,True);hint.pack(side='left',padx=(9,0))
        for handle in (head,title,hint):
            handle.configure(cursor='fleur')
            handle.bind('<ButtonPress-1>',self.start_drag)
        self.button(head,'×',self.close).pack(side='right')
        self.segments([('info','用量与设置'),('appearance','样式与位置')],self.page,self.change_page)
        if self.page=='appearance':
            self.build_appearance()
            self.layout()
            return
        self.info_labels['status']=self.text(self.body,'',8,True)
        self.info_labels['status'].pack(fill='x',pady=(0,7))
        for index,q in enumerate(self.app.snapshot.get('quotas',[])):
            name=period_label(q.get('duration'))
            if q.get('bucket') not in ('codex',None):name=str(q.get('name') or q['bucket'])[:14]+' · '+name
            self.row('quota_'+str(index),name)
            self.row('reset_'+str(index),'重置时间')
        if not self.app.snapshot.get('quotas'):self.text(self.body,'暂无额度数据',9,True).pack(anchor='w')
        self.row('plan','当前套餐')
        self.row('credits','可用重置次数')
        self.row('expiry','最近一张到期')
        self.separator()
        renewal=tk.Frame(self.body,bg=self.p['bg']);renewal.pack(fill='x')
        self.text(renewal,'下次续费',9).pack(side='left')
        self.text(renewal,'手动记录',8,True).pack(side='right')
        self.renewal_label=self.text(self.body,renewal_caption(self.app.settings.get('renewal_date')),9)
        self.renewal_label.pack(fill='x',pady=(4,5))
        self.editor=tk.Frame(self.body,bg=self.p['bg']);self.editor.pack(fill='x')
        self.button(self.editor,'设置 / 修改续费日期',self.show_renewal_editor).pack(fill='x')
        self.separator()
        actions=tk.Frame(self.body,bg=self.p['bg']);actions.pack(fill='x')
        self.button(actions,'刷新用量',self.refresh).pack(side='left',fill='x',expand=True,padx=(0,3))
        self.button(actions,'切换配件样式',lambda:self.change_page('appearance')).pack(side='left',fill='x',expand=True,padx=(3,0))
        if len(self.app.snapshot.get('quotas',[]))>1:
            self.button(self.body,'切换额度周期',lambda:self.run(self.app.next_quota)).pack(fill='x',pady=(5,0))
        self.text(self.body,'更新频率',8,True).pack(anchor='w',pady=(10,3))
        self.segments([(60,'1 分钟'),(300,'5 分钟'),(900,'15 分钟')],self.app.settings['interval'],self.set_interval)
        self.button(self.body,('✓ ' if self.app.settings['follow'] else '○ ')+'锁定跟随宠物',self.toggle_follow).pack(fill='x',pady=(10,0))
        self.button(self.body,('✓ ' if self.app.settings.get('auto_start') else '○ ')+'随宠物自动启停',self.toggle_auto_start).pack(fill='x',pady=(6,0))
        self.text(self.body,'宠物开启后约 1 分钟内启动；关闭后自动退出',8,True).pack(anchor='w',pady=(4,0))
        foot=tk.Frame(self.body,bg=self.p['bg']);foot.pack(fill='x',pady=(7,0))
        self.button(foot,'贴回宠物身旁',lambda:self.run(self.app.reset_offset)).pack(side='left')
        self.button(foot,'退出并停用自动启停' if self.app.settings.get('auto_start') else '退出配件',self.exit_accessory).pack(side='right')
        self.layout()

    def toggle_auto_start(self):
        try:self.app.set_auto_start(not self.app.settings.get('auto_start',False))
        except Exception as exc:
            messagebox.showerror('自动启停',str(exc),parent=self.win);return
        self.build();self.update_info(schedule=False)

    def exit_accessory(self):
        try:self.app.exit_from_menu()
        except Exception as exc:messagebox.showerror('退出配件',str(exc),parent=self.win)

    def change_page(self,page):
        self.page=page;self.build();self.update_info(schedule=False)

    def build_appearance(self):
        self.text(self.body,'配件样式',9,True).pack(anchor='w',pady=(12,5))
        grid=tk.Frame(self.body,bg=self.p['bg']);grid.pack(fill='x')
        for index,(key,name) in enumerate(STYLES.items()):
            self.button(grid,name,lambda k=key:self.set_accessory('accessory_style',k),
                        self.app.settings['accessory_style']==key).grid(row=index//2,column=index%2,sticky='ew',padx=2,pady=3)
        grid.columnconfigure(0,weight=1);grid.columnconfigure(1,weight=1)
        self.text(self.body,'双额度布局',9,True).pack(anchor='w',pady=(12,5))
        self.segments([('split','左右分开'),('together','同侧排列')],
                      self.app.settings.get('layout_mode','split'),lambda k:self.set_accessory('layout_mode',k))
        self.text(self.body,'显示哪一侧',9,True).pack(anchor='w',pady=(10,5))
        self.segments([('both','两侧'),('left','仅左侧'),('right','仅右侧')],
                      self.app.settings.get('visible_sides','both'),lambda k:self.set_accessory('visible_sides',k))
        self.text(self.body,'关闭一侧后，可从另一侧菜单恢复。',8,True).pack(anchor='w',pady=5)
        self.button(self.body,'左右额度互换',lambda:self.set_accessory('swap_sides',not self.app.settings.get('swap_sides',False)),
                    self.app.settings.get('swap_sides',False)).pack(fill='x',pady=(4,0))
        self.button(self.body,'镜像配饰朝向',lambda:self.set_accessory('mirror_accessories',not self.app.settings.get('mirror_accessories',False)),
                    self.app.settings.get('mirror_accessories',False)).pack(fill='x',pady=(4,0))
        self.text(self.body,'镜像只改变配饰朝向，文字正常显示。',8,True).pack(anchor='w',pady=5)
        self.text(self.body,'单额度 / 同侧排列的偏好位置',9,True).pack(anchor='w',pady=(12,5))
        self.segments([('auto','自动'),('left','左侧'),('right','右侧')],
                      self.app.settings['accessory_side'],lambda k:self.set_accessory('accessory_side',k))
        self.text(self.body,'边缘不足时合并到可用侧；拖动宠物一起移动。',8,True).pack(anchor='w',pady=5)
        self.text(self.body,'与宠物的距离',9,True).pack(anchor='w',pady=(10,5))
        self.segments([(4,'紧凑'),(12,'标准'),(24,'宽松')],self.app.settings['accessory_gap'],
                      lambda k:self.set_accessory('accessory_gap',k))
        self.separator()
        self.text(self.body,'周期配色',9,True).pack(anchor='w',pady=(2,5))
        self.segments([('paired','周期双色'),('theme','随主题')],
                      self.app.settings.get('quota_colors','paired'),lambda k:self.set_accessory('quota_colors',k))
        self.text(self.body,'双色：短周期蓝 / 黑羽，长周期紫 / 白羽。\n图形与百分比均为剩余量；低额度显示提示点。',8,True,justify='left').pack(anchor='w',pady=5)
        self.text(self.body,'配件底色与主题',9,True).pack(anchor='w',pady=(2,5))
        grid=tk.Frame(self.body,bg=self.p['bg']);grid.pack(fill='x')
        for index,(key,(name,bg,accent)) in enumerate(THEMES.items()):
            cell=tk.Frame(grid,bg=self.p['bg']);cell.grid(row=index//2,column=index%2,sticky='ew',padx=3,pady=3)
            swatch=tk.Canvas(cell,width=18,height=26,bg=self.p['bg'],highlightthickness=0)
            swatch.create_rectangle(1,4,17,19,fill=bg,outline=accent)
            swatch.create_rectangle(1,19,17,23,fill=accent,outline='')
            swatch.pack(side='left')
            self.button(cell,name,lambda k=key:self.set_color(k),self.app.settings.get('color_theme')==key).pack(side='left',fill='x',expand=True)
        grid.columnconfigure(0,weight=1);grid.columnconfigure(1,weight=1)
        self.text(self.body,'自定义颜色',8,True).pack(anchor='w',pady=(12,4))
        row=tk.Frame(self.body,bg=self.p['bg']);row.pack(fill='x')
        self.button(row,'配件底色',lambda:self.pick_color('custom_body')).pack(side='left',expand=True,fill='x',padx=2)
        self.button(row,'额度强调色',lambda:self.pick_color('custom_accent')).pack(side='left',expand=True,fill='x',padx=2)
        self.text(self.body,'桌面文字',9,True).pack(anchor='w',pady=(10,5))
        self.segments([('light','浅色字'),('dark','深色字'),('auto','随主题')],
                      self.app.settings['text_tone'],lambda k:self.set_accessory('text_tone',k))
        self.text(self.body,'深色桌面选浅色字；浅色桌面选深色字。',8,True).pack(anchor='w',pady=5)
        self.separator()
        self.text(self.body,'信息密度',9,True).pack(anchor='w',pady=(0,5))
        self.segments([('standard','标准'),('compact','简洁')],self.app.settings.get('density','standard'),self.set_density)
        self.text(self.body,'标准：最多显示两个周期，可选择左右分开。\n简洁：显示一个周期，菜单可切换。',8,True,justify='left').pack(anchor='w',pady=7)
        self.text(self.body,'明暗模式',9,True).pack(anchor='w',pady=(10,5))
        self.segments([('auto','随系统'),('light','原色'),('dark','深色')],self.app.settings['theme'],self.set_theme)
        self.button(self.body,'恢复默认外观',self.reset_appearance).pack(fill='x',pady=(15,2))

    def rebuild_colors(self):
        scroll=self.viewport.yview()[0]
        self.p=self.app.palette();self.body.configure(bg=self.p['bg']);self.viewport.configure(bg=self.p['bg'])
        self.build();self.update_info(schedule=False)
        self.viewport.yview_moveto(scroll)

    def set_color(self,key):
        self.app.set_appearance('color_theme',key);self.rebuild_colors()

    def set_density(self,value):
        self.app.set_appearance('density',value);self.rebuild_colors()

    def set_accessory(self,key,value):
        self.app.set_appearance(key,value);self.rebuild_colors()

    def reset_appearance(self):
        self.app.settings.update(color_theme='cream',density='standard',theme='auto',accessory_style='dial',accessory_side='auto',text_tone='light',accessory_gap=4,
                                 layout_mode='split',visible_sides='both',swap_sides=False,mirror_accessories=False,quota_colors='paired')
        self.app.theme_var.set('auto')
        self.app.set_appearance('density','standard');self.rebuild_colors()

    def pick_color(self,key):
        self.choosing_color=True
        try:
            current=self.p['bg' if key=='custom_body' else 'accent']
            color=colorchooser.askcolor(color=current,parent=self.win,title='选择配件底色' if key=='custom_body' else '选择额度强调色')[1]
            if color:
                self.app.settings.setdefault('custom_body',self.p['bg'])
                self.app.settings.setdefault('custom_accent',self.p['accent'])
                self.app.settings[key]=color
                self.app.set_appearance('color_theme','custom')
                self.rebuild_colors()
        finally:
            self.choosing_color=False
            if not self.closed:self.win.focus_force();self.win.grab_set()

    def segments(self,items,selected,callback):
        row=tk.Frame(self.body,bg=self.p['bg']);row.pack(fill='x')
        for value,title in items:
            self.button(row,title,lambda v=value:callback(v),value==selected).pack(side='left',expand=True,fill='x',padx=2)

    @native_menu
    def layout(self):
        self.scale_content(self.body)
        self.win.update_idletasks()
        content_pixels=self.body.winfo_reqheight()
        content_height=content_pixels/self.scale
        width,height=308,min(560,round(content_height+31))
        work=monitor_work_area(*(self.manual_position or self.origin))
        height=min(height,round((work[3]-work[1])*0.8),work[3]-work[1]-12)
        app=self.app
        ax,ay,ar,ab=app.avoid_rect()
        x,y=fit_menu_position((ax,ay,ar,ab),(width,height),work,self.manual_position)
        if self.manual_position is not None:self.manual_position=(x,y)
        self.panel_size=(width,height)
        self.canvas.configure(width=self.px(width),height=self.px(height))
        self.canvas.coords(self.viewport_item,self.px(16),self.px(15))
        self.canvas.itemconfigure(self.viewport_item,width=self.px(276))
        self.viewport.itemconfigure(self.body_item,width=self.px(276))
        self.canvas.delete('shell')
        def rounded(x1,y1,x2,y2,r,fill):
            pts=[x1+r,y1,x2-r,y1,x2,y1,x2,y1+r,x2,y2-r,x2,y2,x2-r,y2,x1+r,y2,x1,y2,x1,y2-r,x1,y1+r,x1,y1]
            self.canvas.create_polygon([self.px(v) for v in pts],smooth=True,splinesteps=20,fill=fill,outline='',tags='shell')
        rounded(3,4,width,height,15,self.p['shadow'])
        rounded(0,0,width-3,height-4,15,self.p['bg'])
        self.canvas.tag_lower('shell')
        self.viewport.configure(height=self.px(height-31),scrollregion=(0,0,self.px(276),content_pixels))
        if content_height>height-31:
            self.scrollbar.place(x=self.px(293),y=self.px(15),width=self.px(10),height=self.px(height-31))
        else:
            self.scrollbar.place_forget()
        self.canvas.configure(height=self.px(height))
        self.win.geometry(f'{self.px(width)}x{self.px(height)}')
        self.win.update_idletasks()
        self.move_panel(x,y)

    def move_panel(self,x,y):
        position_logical_window(ctypes.windll.user32.GetParent(self.win.winfo_id()),x,y)

    def start_drag(self,event):
        event=logical_pointer_event(event)
        self.drag_origin=(event.x_root,event.y_root,*logical_window_position(self.win))

    @native_menu
    def drag_panel(self,event):
        if not self.drag_origin:return
        event=logical_pointer_event(event)
        sx,sy,x,y=self.drag_origin
        target=(x+event.x_root-sx,y+event.y_root-sy)
        work=monitor_work_area(event.x_root,event.y_root)
        self.manual_position=fit_menu_position((0,0,0,0),self.panel_size,work,target)
        self.move_panel(*self.manual_position)
        self.sync_dpi()

    def sync_dpi(self):
        scale=self.window_scale()
        if scale!=self.scale:
            scroll=self.viewport.yview()[0]
            self.scale=scale
            self.layout()
            self.viewport.yview_moveto(scroll)

    def end_drag(self,event):
        self.drag_origin=None

    @native_menu
    def scroll(self,event):
        if self.body.winfo_reqheight()>self.viewport.winfo_height():
            self.viewport.yview_scroll(-int(event.delta/120),'units')

    @native_menu
    def show_renewal_editor(self):
        for child in self.editor.winfo_children():child.destroy()
        self.date_var=tk.StringVar(value=self.app.settings.get('renewal_date',''))
        self.error_var=tk.StringVar()
        self.text(self.editor,'按账单填写 YYYY-MM-DD',8,True).pack(anchor='w',pady=(2,5))
        entry=tk.Entry(self.editor,textvariable=self.date_var,font=menu_font(10),
                       bg=self.p['top'],fg=self.p['fg'],insertbackground=self.p['fg'],relief='flat',
                       highlightthickness=1,highlightbackground=self.p['track'],highlightcolor=self.p['accent'])
        entry.pack(fill='x',ipady=5)
        entry.bind('<Return>',lambda e:self.save_renewal())
        tk.Label(self.editor,textvariable=self.error_var,bg=self.p['bg'],fg=self.p['fg'],font=menu_font(8)).pack(anchor='w')
        row=tk.Frame(self.editor,bg=self.p['bg']);row.pack(fill='x')
        self.button(row,'保存',self.save_renewal,True).pack(side='left',expand=True,fill='x',padx=(0,3))
        self.button(row,'清除',self.clear_renewal).pack(side='left',expand=True,fill='x',padx=3)
        self.button(row,'取消',self.build).pack(side='left',expand=True,fill='x',padx=(3,0))
        self.layout();entry.focus_set()

    def save_renewal(self):
        try:value=parse_renewal(self.date_var.get())
        except ValueError as exc:
            self.error_var.set(str(exc));return
        self.app.settings['renewal_date']=value
        self.app.persist()
        self.build();self.update_info(schedule=False)

    def clear_renewal(self):
        self.date_var.set('');self.save_renewal()

    @native_menu
    def update_info(self,schedule=True):
        if self.closed:return
        self.sync_dpi()
        signature=[(q.get('bucket'),q.get('duration')) for q in self.app.snapshot.get('quotas',[])]
        if signature!=self.quota_signature:self.build()
        app=self.app; q=app.selected() or {}; account=app.snapshot.get('account') or {}
        checked=app.snapshot.get('checked_at')
        status='演示数据' if app.demo else '正在更新…' if app.busy else '更新失败 · 保留上次数据' if app.error else ('更新于 '+datetime.fromtimestamp(checked).strftime('%H:%M:%S') if checked else '等待首次更新')
        if not app.demo and not app.busy and checked and time.time()-checked>app.settings['interval']*2+60:
            status='数据待更新 · 上次 '+datetime.fromtimestamp(checked).strftime('%H:%M')
        used=q.get('used');reset=q.get('reset')
        plan=account.get('plan')
        names={'prolite':'Pro Lite','pro':'Pro','plus':'Plus','free':'Free','team':'Team','business':'Business','enterprise':'Enterprise','edu':'Edu'}
        values={'status':status,
                'plan':names.get(plan,plan or '暂未返回'),'credits':str(account['reset_count'])+' 次' if account.get('reset_count') is not None else '暂未返回',
                'expiry':datetime.fromtimestamp(account['reset_credit_expires']).strftime('%m/%d %H:%M') if account.get('reset_credit_expires') else '暂无到期信息'}
        for index,quota in enumerate(app.snapshot.get('quotas',[])):
            used=quota.get('used');reset=quota.get('reset')
            values['quota_'+str(index)]=f'已用 {used:g}% · 余 {100-used:g}%' if used is not None else '未知'
            values['reset_'+str(index)]=datetime.fromtimestamp(reset).strftime('%m/%d %H:%M:%S') if reset else '未知'
        for key,value in values.items():
            if key in self.info_labels:self.info_labels[key].configure(text=value)
        if self.page=='info':self.renewal_label.configure(text=renewal_caption(app.settings.get('renewal_date')))
        if schedule:self.win.after(1000,self.update_info)

    def refresh(self):self.app.refresh(manual=True);self.update_info(schedule=False)
    def run(self,callback):self.close();callback()
    def set_interval(self,value):
        self.app.interval_var.set(value);self.app.set_interval();self.build();self.update_info(schedule=False)
    def set_theme(self,value):
        self.app.theme_var.set(value);self.app.set_theme();self.rebuild_colors()
    def toggle_follow(self):
        self.app.follow_var.set(not self.app.settings['follow']);self.app.set_follow();self.build();self.update_info(schedule=False)
    def check_focus(self):
        if not self.closed and not self.choosing_color and self.win.focus_get() is None:self.close()
    def outside_click(self,event):
        event=logical_pointer_event(event)
        x,y=logical_window_position(self.win)
        width,height=self.panel_size
        if not(x<=event.x_root<x+width and y<=event.y_root<y+height):self.close()
    def close(self):
        if self.closed:return
        self.closed=True
        try:self.win.grab_release();self.win.destroy()
        except tk.TclError:pass
        if self.app.popup is self:self.app.popup=None
