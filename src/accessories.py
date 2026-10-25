"""Side accessories; local-only rasterization and collision-free placement."""
import math
import time
from appearance import mix, short_countdown, luminance
from usage_core import period_label
from smooth_surface import Image, ImageDraw, font_at

STYLES = {'dial': '侧边表盘', 'arc': '环抱弧线', 'battery': '像素电池', 'bookmark': '斜挂书签',
          'feather': '轻羽', 'wing': '展开羽翼', 'crystal': '水晶吊坠'}
CELL_WIDTH, HEIGHT = 112, 160


def side_position(anchor, size, width, height, preferred='auto', work=None, gap=4, insets=(0,0)):
    screen = anchor.get('displayBounds') or dict(x=0,y=0,width=1920,height=1080)
    left,top,right,bottom = work or (screen['x'],screen['y'],screen['x']+screen['width'],screen['y']+screen['height'])
    left+=8; top+=8; right-=8; bottom-=8
    # Include the native 120px toolbar, even for a small mascot. Never clamp
    # horizontally into this region when the requested side does not fit.
    center=anchor['x']+size/2
    half=max(size/2,64)
    inset_left,inset_right=insets
    edges={'left':center-half-gap-width+inset_right, 'right':center+half+gap-inset_left}
    preferred=preferred if preferred in ('left','right') else 'right'
    order=[preferred,'left' if preferred=='right' else 'right']
    # Reference: lower edge below the native pet's 40px toolbar.
    # These are accessory coordinates only; never resize or move native controls.
    baseline=anchor['y']+size*208/192+6+40+4
    # The user's two reference lines place the v20 artwork 24 screen pixels
    # higher at 150% DPI. Translate by 16 logical pixels; keep raster size,
    # typography, artwork proportions and horizontal placement unchanged.
    desired_y=max(anchor['y'],baseline-height)-16
    y=round(max(top,min(desired_y,bottom-height)))
    # Do not shift further upward merely to fit within the work area.
    if y < desired_y-1 or height>bottom-top:
        return None
    for side in order:
        x=round(edges[side])
        if left<=x+inset_left and x+width-inset_right<=right:
            return x,y,side
    return None


def ink_insets(image, logical_width):
    """Position visible artwork, not the transparent padding around it."""
    box=image.getbbox()
    if box is None:return (0,0)
    scale=image.width/logical_width
    return (max(0,math.floor(box[0]/scale)-2),
            max(0,math.floor((image.width-box[2])/scale)-2))



def quota_palette(p, quota):
    """Stable duration identity: moving, hiding or merging a side cannot recolor it."""
    result=dict(p)
    duration=quota.get('duration')
    known=isinstance(duration,(int,float)) and math.isfinite(duration) and duration>0
    role=('short' if duration<1440 else 'long') if known else 'unknown'
    paired=p.get('quota_colors','paired')=='paired'
    dark=luminance(p['bg'])<.2
    if paired and known:
        result['accent']=('#75cce5' if dark else '#237e9f') if role=='short' else ('#c6a3ee' if dark else '#9562b8')
    accent=result['accent']
    if paired and role=='short':
        body,shade,edge,vein,fine='#303743','#485464','#8b9bb0','#adbdd0','#6c7d93'
    elif paired and role=='long':
        body,shade,edge,vein,fine='#f4f0e9','#e1d8eb','#b5a5c8','#ac99bd','#c4b6d1'
    else:
        body,shade,edge=mix(p['bg'],'#ffffff',.82),mix(accent,'#eee8f5',.82),mix(accent,'#b7adcc',.7)
        vein,fine=mix(accent,'#9c8bae',.6),mix(accent,'#cec4dd',.7)
    result.update(role=role,plume_body=body,plume_shade=shade,plume_edge=edge,
                  plume_vein=vein,plume_fine=fine,plume_track=mix(body,vein,.45))
    return result


def progress_points(points, value):
    """Trim by path length; None and zero contain no active progress."""
    if value is None or value<=0 or len(points)<2:return []
    if value>=100:return list(points)
    lengths=[math.dist(a,b) for a,b in zip(points,points[1:])]
    target=sum(lengths)*value/100
    result=[points[0]];walked=0
    for a,b,length in zip(points,points[1:],lengths):
        if walked+length>=target and length:
            t=(target-walked)/length
            result.append(tuple(x+(y-x)*t for x,y in zip(a,b)))
            break
        result.append(b);walked+=length
    return result


def progress_stroke(draw, points, value, accent, track, width):
    draw.line(points,fill=track,width=max(1,round(width)),joint='curve')
    active=progress_points(points,value)
    if len(active)>1:draw.line(active,fill=accent,width=max(1,round(width)),joint='curve')


def feather(scale,p,side,value=None):
    """Approved intact plume; a length-accurate colored shaft shows remaining quota."""
    layer=Image.new('RGBA',(round(CELL_WIDTH*scale),round(HEIGHT*scale)))
    d=ImageDraw.Draw(layer)
    def points(seq):return [((56+(x-35)*.64)*scale,(24+y*.64)*scale) for x,y in seq]
    def curve(a,b,c,e):
        return [tuple((1-t)**3*a[j]+3*(1-t)**2*t*b[j]+3*(1-t)*t*t*c[j]+t**3*e[j] for j in (0,1)) for t in [i/32 for i in range(33)]]
    def path(start,segments,color,edge=None):
        seq=[start];a=start
        for b,c,e in segments:seq+=curve(a,b,c,e);a=e
        pts=points(seq);d.polygon(pts,fill=color)
        if edge:d.line(pts+[pts[0]],fill=edge,width=max(1,round(.64*scale)),joint='curve')
    p=p if 'plume_body' in p else quota_palette(p,{})
    accent=p['accent'];edge=p['plume_edge']
    path((18,6),[
        ((50,31),(65,66),(46,123)),((43,109),(37,104),(31,98)),
        ((27,93),(24,87),(23,81)),((25,83),(27,85),(29,86)),
        ((22,75),(17,65),(16,58)),((18,60),(20,62),(22,63)),
        ((13,47),(12,24),(18,6))],p['plume_body'],edge)
    path((18,6),[((44,27),(54,53),(49,82)),((47,101),(46,112),(46,123)),
                ((65,66),(50,31),(18,6))],p['plume_shade'])
    def seam(a,b,c,e,color,width):
        d.line(points(curve(a,b,c,e)),fill=color,width=max(1,round(width*.64*scale)),joint='curve')
    seam((20,11),(33,34),(49,60),(46,116),p['plume_vein'],2)
    seam((20,12),(42,37),(53,78),(47,129),p['plume_vein'],1.35)
    for a,b,c,e in [((19,38),(28,51),(35,56),(41,59)),((22,58),(30,70),(39,76),(47,80)),
                    ((29,80),(34,91),(42,95),(48,97)),((37,35),(40,36),(43,40),(45,44)),
                    ((45,56),(49,58),(51,63),(52,67)),((48,78),(49,81),(51,85),(51,89))]:
        seam(a,b,c,e,p['plume_fine'],.8)
    d.ellipse(points([(42,124),(52,134)]),fill=p['plume_shade'],outline=edge,width=max(1,round(.64*scale)))
    d.ellipse(points([(45,127),(49,131)]),fill=accent)
    shaft=list(reversed(points(curve((20,12),(42,37),(53,78),(47,125)))))
    progress_stroke(d,shaft,value,accent,p['plume_track'],2.4*scale)
    if side=='right':layer=layer.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    return layer


def wing(scale,p,accent,value,side):
    """Connected shoulder, layered coverts and swept flight feathers."""
    p=p if 'plume_body' in p else quota_palette(p,{})
    layer=Image.new('RGBA',(round(CELL_WIDTH*scale),round(HEIGHT*scale)))
    d=ImageDraw.Draw(layer)
    def pts(seq):return [((56+(x-56)*.84)*scale,(y*.78+24)*scale) for x,y in seq]
    def curve(a,b,c,e):
        return [tuple((1-t)**3*a[j]+3*(1-t)**2*t*b[j]+3*(1-t)*t*t*c[j]+t**3*e[j] for j in (0,1)) for t in [i/24 for i in range(25)]]
    def path(start,segments,fill,edge=None):
        seq=[start];a=start
        for b,c,e in segments:seq+=curve(a,b,c,e);a=e
        xy=pts(seq);d.polygon(xy,fill=fill)
        if edge:d.line(xy+[xy[0]],fill=edge,width=max(1,round(.85*scale)),joint='curve')
    # Rounded shoulder and a bent leading edge distinguish a wing from a leaf.
    # Broad flight feathers fan downward/outward with rounded individual tips.
    path((27,99),[
        ((20,87),(20,66),(27,49)),((33,31),(49,20),(70,15)),
        ((73,14),(77,11),(80,8)),((81,21),(75,32),(66,40)),
        ((80,39),(93,32),(101,26)),((105,43),(88,61),(74,66)),
        ((84,63),(94,56),(98,50)),((102,65),(82,83),(65,86)),
        ((74,84),(84,76),(88,70)),((89,85),(70,99),(53,100)),
        ((60,99),(66,94),(71,90)),((70,104),(45,113),(27,99))],
        p['plume_body'],p['plume_edge'])
    for a,b,c,e in [((40,83),(57,61),(83,58),(98,35)),
                     ((38,91),(59,77),(81,77),(95,58)),
                     ((35,97),(51,90),(72,95),(84,79)),
                     ((31,98),(40,106),(57,105),(66,97))]:
        d.line(pts(curve(a,b,c,e)),fill=p['plume_fine'],width=max(1,round(.9*scale)),joint='curve')
    path((26,95),[
        ((21,76),(26,51),(42,36)),((54,26),(66,26),(74,18)),
        ((72,35),(56,44),(49,57)),((48,63),(49,66),(44,70)),
        ((39,69),(38,80),(34,84)),((29,83),(30,94),(26,95))],p['plume_shade'])
    for a,b,c,e in [((28,75),(29,59),(38,44),(53,37)),
                     ((32,81),(35,65),(46,48),(61,36))]:
        d.line(pts(curve(a,b,c,e)),fill=p['plume_vein'],width=max(1,round(.8*scale)),joint='curve')
    root=pts(curve((27,96),(23,75),(30,54),(45,43)))
    progress_stroke(d,root,value,accent,p['plume_track'],2.4*scale)
    if side=='left':layer=layer.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    return layer


def ornament(style, scale, p, accent, value, side):
    if style=='feather':return feather(scale,p,side,value)
    if style=='wing':return wing(scale,p,accent,value,side)
    # Crystal highlights use one light direction on both sides, never mirrored.
    layer=Image.new('RGBA',(round(CELL_WIDTH*scale),round(HEIGHT*scale)))
    mask=Image.new('L',layer.size);md=ImageDraw.Draw(mask)
    def pts(values):return [(round((56+(x-56)*.9)*scale),round((16+y*.9)*scale)) for x,y in values]
    outline=pts([(56,28),(81,51),(72,84),(56,104),(40,84),(31,51)])
    md.polygon(outline,fill=255)
    body=Image.new('RGBA',layer.size,mix(accent,'#ffffff',.83))
    bd=ImageDraw.Draw(body)
    if value:
        bd.rectangle((0,round((16+(104-76*value/100)*.9)*scale),layer.width,layer.height),fill=mix(accent,'#ffffff',.22))
    layer.paste(body,(0,0),mask)
    d=ImageDraw.Draw(layer)
    vein=mix(accent,'#35273e',.22)
    d.ellipse(pts([(52,20),(60,28)]),outline=accent,width=max(1,round(1.2*scale)))
    for vertices in [[(31,51),(56,57),(81,51)],[(56,28),(56,57),(56,104)],[(40,84),(56,57),(72,84)]]:
        d.line(pts(vertices),fill=vein,width=max(1,round(.8*scale)))
    d.line(pts([(45,38),(36,51),(41,68)]),fill='#ffffff',width=max(1,round(1.6*scale)))
    return layer


def remaining(quota):
    used=quota.get('used')
    return None if not isinstance(used,(int,float)) or not math.isfinite(used) else max(0,min(100,100-used))


def render_accessories(quotas, style, p, side='right', stale=False, busy=False,
                       demo=False, pixel_size=None, now=None, text_tone='auto',mirror=False):
    """Render at 4x physical density; floating lettering has a contrasting keyline."""
    quotas=quotas or [{}]
    if mirror:side='left' if side=='right' else 'right'
    width,height=CELL_WIDTH*len(quotas),HEIGHT
    pw,ph=pixel_size or (width,height)
    scale=4*pw/width
    image=Image.new('RGBA',(pw*4,ph*4))
    draw=ImageDraw.Draw(image)
    now=time.time() if now is None else now
    style=style if style in STYLES else 'dial'
    floating_fg=('#ffffff' if text_tone=='light' else '#27212e') if text_tone!='auto' else p['fg']
    floating_muted=('#d9d0df' if text_tone=='light' else '#65576a') if text_tone!='auto' else p['muted']
    boxes=[]
    def rect(box,fill,radius=0):
        scaled=tuple(round(v*scale) for v in box)
        if radius:draw.rounded_rectangle(scaled,radius=radius*scale,fill=fill)
        else:draw.rectangle(scaled,fill=fill)
    def line(points,fill,thickness):
        draw.line([(round(x*scale),round(y*scale)) for x,y in points],fill=fill,width=max(1,round(thickness*scale)))
    def label(x,y,value,size=11,color=None,halo=True,target=None,register=True):
        d=ImageDraw.Draw(target) if target is not None else draw
        font=font_at(round(size*scale));color=color or p['fg']
        if halo:
            color=floating_muted if color==p['muted'] else floating_fg
        stroke=('#25202d' if floating_fg=='#ffffff' else '#ffffff') if halo else None
        sw=max(1,round(.5*scale)) if halo else 0
        d.text((x*scale,y*scale),value,font=font,anchor='mm',fill=color,stroke_width=sw,stroke_fill=stroke)
        if register:
            b=d.textbbox((x*scale,y*scale),value,font=font,anchor='mm',stroke_width=sw)
            boxes.append(tuple(v/scale for v in b))
    base_palette=p
    for index,q in enumerate(quotas):
        p=quota_palette(base_palette,q)
        x=index*CELL_WIDTH; center=x+56
        value=remaining(q)
        number='—' if value is None else f'{value:.1f}'.rstrip('0').rstrip('.') if value%1 else str(int(value))
        number += '%' if value is not None else ''
        period=period_label(q.get('duration')).replace(' 小时','小时').replace(' 天','天').replace(' 分钟','分')
        if len(period)>9:period='额度'
        reset=q.get('reset')
        if stale: timing,caption='数据待更新','右键刷新'
        elif not q:timing,caption=('正在查询' if busy else '暂无数据'),'右键查看'
        elif not reset:timing,caption='时间未知','右键详情'
        elif reset<=now:timing,caption='已到重置时间','等待确认'
        else:timing,caption=short_countdown(reset,now),'后重置'
        # One readable reset line replaces the former two-line footer.
        footer=(timing+'后重置' if caption=='后重置' else
                '待更新·右键刷新' if stale else
                '等待确认重置' if reset and reset<=now else
                '重置时间未知' if q and not reset else timing)
        accent=p['accent']
        warning=None if value is None or value>20 else '#c18b3f' if value>10 else '#d66c7d'
        if style=='bookmark':
            tag=Image.new('RGBA',(round(CELL_WIDTH*scale),round(HEIGHT*scale)))
            td=ImageDraw.Draw(tag)
            vertices=[(20,14),(92,14),(92,155),(56,145),(20,155)]
            td.polygon([(a*scale,b*scale) for a,b in vertices],fill=p['bg'])
            td.rounded_rectangle((20*scale,14*scale,92*scale,17*scale),radius=scale,fill=accent)
            td.rounded_rectangle((51*scale,20*scale,61*scale,22*scale),radius=scale,fill=p['edge'])
            # Rotate only the hanging artwork around its attachment, not the text.
            tag=tag.rotate(5 if side=='right' else -5,Image.Resampling.BICUBIC,
                           center=(56*scale,14*scale))
            image.alpha_composite(tag,(round(x*scale),0))
            line([(center,2),(center,19)],accent,1)
            for yy,txt,sz,col in [(36,period,10,p['muted']),(70,number,20,p['fg']),
                                  (128,footer,9,p['fg'])]:
                label(center,yy,txt,sz,col,False)
            rect((x+34,99,x+78,103),p['track'],1)
            if value:rect((x+34,99,x+34+44*value/100,103),accent,1)
            warning_x,warning_y=center-26,87
        else:
            if style=='dial':
                label(center,16,period,10,p['muted'])
                box=tuple(v*scale for v in (x+20,35,x+92,107))
                draw.arc(box,0,360,fill=p['track'],width=round(4*scale))
                if value:draw.arc(box,-90,-90+360*value/100,fill=accent,width=round(4*scale))
                label(center,71,number,20)
            elif style=='arc':
                pts=[(x+(14+18*math.sin(math.pi*t/160) if side=='right' else 98-18*math.sin(math.pi*t/160)),27+110*t/160) for t in range(161)]
                line(pts,p['track'],3)
                if value:line(progress_points(pts,value),accent,3)
                tx=x+(74 if side=='right' else 38)
                label(tx,54,period,10,p['muted'])
                label(tx,85,number,20)
            elif style in ('feather','wing','crystal'):
                label(center,16,period,10,p['muted'])
                image.alpha_composite(ornament(style,scale,p,accent,value,side),(round(x*scale),0))
                label(center,130,number,20)
            else:
                label(center,16,period,10,p['muted'])
                shell=mix(accent,floating_fg,.55)
                rect((x+39,34,x+73,111),shell,3);rect((x+47,29,x+65,35),shell,1)
                rect((x+43,38,x+69,107),p['bg'],1)
                for cell in range(5):
                    # Empty cells are never reported as full; exact text stays visible.
                    frac=0 if value is None else max(0,min(1,(value-cell*20)/20))
                    y=95-cell*13
                    rect((x+47,y,x+65,y+8),p['track'])
                    if frac:rect((x+47,y,x+47+18*frac,y+8),accent)
                label(center,130,number,20)
            label(center,152,footer,10,p['muted'])
            if style in ('battery','feather','wing','crystal'):warning_x,warning_y=center-38,130
            elif style=='arc':warning_x,warning_y=tx,119
            else:warning_x,warning_y=center,126
        if warning:
            # A separate dot warns without overwriting the cycle's identity color.
            draw.ellipse(tuple(v*scale for v in (warning_x-2,warning_y-2,warning_x+2,warning_y+2)),fill=warning)
        if demo:label(x+103,152,'例',8,p['muted'])
    result=image.resize((pw,ph),Image.Resampling.LANCZOS)
    return result,boxes
