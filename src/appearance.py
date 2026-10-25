"""Local themes, accessible text colours, and quota presentation."""
from datetime import datetime, date
import re
import time

THEMES = {
    'cream': ('奶油白', '#eee7df', '#a6607a'),
    'lilac': ('雾灰紫', '#e4dce9', '#9367a1'),
    'blue': ('冰川蓝', '#dce7ef', '#357f9f'),
    'sage': ('鼠尾草', '#dee7dc', '#4f8266'),
    'peach': ('蜜桃杏', '#f0dfd2', '#ad6853'),
    'graphite': ('石墨灰', '#353b46', '#99bfdc'),
}

def valid_color(value, fallback):
    return value if isinstance(value,str) and re.fullmatch(r'#[0-9a-fA-F]{6}',value) else fallback

def mix(a,b,fraction):
    rgb=lambda s:[int(s[n:n+2],16) for n in (1,3,5)]
    return '#'+''.join(f'{round(x*(1-fraction)+y*fraction):02x}' for x,y in zip(rgb(a),rgb(b)))

def luminance(color):
    rgb=[int(color[n:n+2],16)/255 for n in (1,3,5)]
    rgb=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
    return sum(v*w for v,w in zip(rgb,[.2126,.7152,.0722]))

def palette(settings, system_dark=False):
    key=settings.get('color_theme','cream')
    _,bg,accent=THEMES.get(key,THEMES['cream'])
    if key=='custom':
        bg=valid_color(settings.get('custom_body'),bg)
        accent=valid_color(settings.get('custom_accent'),accent)
    mode=settings.get('theme','auto')
    if (mode=='dark' or (mode=='auto' and system_dark)) and luminance(bg)>.2:
        bg=mix(bg,'#171b23',.78);accent=mix(accent,'#ffffff',.35)
    contrast=lambda a,b:(max(luminance(a),luminance(b))+.05)/(min(luminance(a),luminance(b))+.05)
    fg=max(('#ffffff','#17141d'),key=lambda c:contrast(bg,c))
    if contrast(bg,fg)<4.5:fg='#000000'
    dark=fg=='#ffffff'
    muted=mix(bg,fg,.77)
    if contrast(bg,muted)<4.5:muted=fg
    return dict(bg=bg,accent=accent,fg=fg,muted=muted,
                top=mix(bg,'#ffffff',.15 if dark else .52),
                track=mix(bg,fg,.17),shadow='#15131b',edge=mix(bg,'#000000',.13),
                quota_colors=settings.get('quota_colors','paired'))

def visible_quotas(snapshot,selected,density):
    if not selected:return []
    if density=='compact':return [selected]
    # Keep windows in the same bucket together; never invent a five-hour window.
    same=[q for q in snapshot.get('quotas',[]) if q.get('bucket')==selected.get('bucket')]
    return sorted(same,key=lambda q:q.get('duration') or float('inf'))[:2]

def short_countdown(reset,now=None):
    if not reset:return '时间未知'
    delta=reset-(time.time() if now is None else now)
    if delta<=0:return '待确认重置'
    minutes=max(1,int((delta+59)//60))
    days,remain=divmod(minutes,1440);hours,mins=divmod(remain,60)
    if days:return f'{days}天{hours}时'
    return f'{hours}时{mins}分' if hours else f'{mins}分'

def reset_caption(reset,now=None):
    if not reset:return '重置时间未知'
    now=time.time() if now is None else now
    if reset<=now:return '已到重置时间 · 等待确认'
    dt=datetime.fromtimestamp(reset)
    prefix='今日' if dt.date()==datetime.fromtimestamp(now).date() else dt.strftime('%m/%d')
    return f'{prefix} {dt:%H:%M} · {short_countdown(reset,now)}后'

def status_caption(snapshot,settings,error=False,busy=False,demo=False,now=None):
    now=time.time() if now is None else now
    checked=snapshot.get('checked_at')
    if demo:return '演示数据'
    if busy:return '正在更新…'
    if error or (checked and now-checked>settings.get('interval',300)*2+60):return '数据待更新 · 右键刷新'
    if not checked:return '等待首次更新'
    try:
        renewal=date.fromisoformat(settings.get('renewal_date',''))
        days=(renewal-datetime.fromtimestamp(now).date()).days
        if days<0:return '续费日期已过 · 请核对'
        if days<=7:return f'{renewal:%m/%d} 续费 · 手动设置'
    except (ValueError,TypeError):pass
    return '更新于 '+datetime.fromtimestamp(checked).strftime('%H:%M')

def pedestal_position(anchor,size,width,height):
    screen=anchor.get('displayBounds') or dict(x=0,y=0,width=1920,height=1080)
    left,top=screen['x']+8,screen['y']+8
    right,bottom=screen['x']+screen['width']-8,screen['y']+screen['height']-8
    x=anchor['x']+size/2-width/2
    # A shallow tray touches the mascot's feet; 54 px includes native controls.
    y=anchor['y']+__import__('math').ceil(size*208/192)-12
    placement='integrated'
    if y+height>bottom:
        y=anchor['y']-height-6;placement='above'
    return round(max(left,min(x,right-width))),round(max(top,min(y,bottom-height))),placement
