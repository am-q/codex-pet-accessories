"""Pure layout planning; each result owns a separate, narrow native window."""
from accessories import CELL_WIDTH, HEIGHT, side_position


def quota_sides(quotas, settings):
    quotas=quotas or [{}]
    visible=settings.get('visible_sides','both')
    reverse=settings.get('swap_sides',False)
    preferred=settings.get('accessory_side','right')
    preferred=preferred if preferred in ('left','right') else 'right'
    if len(quotas)>1:
        pair=list(reversed(quotas[:2])) if reverse else quotas[:2]
        return [(side,[q]) for side,q in zip(('left','right'),pair) if visible in ('both',side)]
    side=('left' if preferred=='right' else 'right') if reverse else preferred
    if visible in ('left','right'):side=visible
    return [(side,quotas)]


def plan_accessories(quotas, settings, anchor, size, work, insets):
    assignments=quota_sides(quotas,settings)
    allowed=('left','right') if settings.get('visible_sides','both')=='both' else (settings['visible_sides'],)
    gap=settings.get('accessory_gap',4)
    def place(side,items):
        candidate=side_position(anchor,size,CELL_WIDTH*len(items),HEIGHT,side,work,gap,insets(items,side))
        if candidate and candidate[2]==side:
            return dict(x=candidate[0],y=candidate[1],side=side,quotas=items)
    if settings.get('layout_mode','split')=='together':
        items=[q for _,group in assignments for q in group]
        preferred=settings.get('accessory_side','right')
        order=sorted(allowed,key=lambda s:s!=preferred)
        for side in order:
            result=place(side,items)
            if result:return [result]
        for side in order:
            result=place(side,items[:1])
            if result:return [result]
        return []
    result=[p for side,items in assignments if (p:=place(side,items))]
    if len(result)==len(assignments):return result
    # A single cycle may move to the other enabled side at a screen edge.
    if len(assignments)==1:
        for side in allowed:
            p=place(side,assignments[0][1])
            if p:return [p]
    # At an edge, keep both cycles on the safe side if there is enough room.
    if len(assignments)>1:
        items=[q for _,group in assignments for q in group]
        for side in allowed:
            p=place(side,items)
            if p:return [p]
    return result
