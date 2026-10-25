import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from usage_core import normalize_quotas, period_label, countdown, next_delay, choose_position, PetState, ALLOWED_METHODS
from pet_tracking import DragAnchor,select_pet
from base_menu import parse_renewal,renewal_caption,fit_menu_position
from usage_core import normalize_account_meta
from datetime import date
from appearance import visible_quotas,status_caption,pedestal_position,palette,luminance


class QuotaTests(unittest.TestCase):
    def test_menu_avoids_preview_at_either_screen_edge(self):
        size=(308,650);work=(0,0,1920,1040)
        for avoid in [(8,250,228,550),(1680,250,1900,550),(800,350,1020,600)]:
            x,y=fit_menu_position(avoid,size,work)
            self.assertGreaterEqual(x,6);self.assertGreaterEqual(y,6)
            self.assertLessEqual(x+308,1914);self.assertLessEqual(y+650,1034)
            self.assertTrue(x+308<=avoid[0] or x>=avoid[2] or y+650<=avoid[1] or y>=avoid[3])

    def test_menu_negative_monitor_and_manual_position(self):
        work=(-1920,0,0,1040)
        x,y=fit_menu_position((-220,300,-10,500),(308,650),work)
        self.assertLessEqual(x+308,-220)
        self.assertEqual(fit_menu_position((0,0,0,0),(308,650),work,(-1800,30)),(-1800,30))
        self.assertEqual(fit_menu_position((0,0,0,0),(308,650),work,(-50,900)),(-314,384))

    def test_week_in_primary_is_not_five_hours(self):
        q=normalize_quotas({'rateLimits':{'primary':{'usedPercent':63,'windowDurationMins':10080,'resetsAt':123}}})
        self.assertEqual(period_label(q[0]['duration']),'周额度')
        self.assertEqual(q[0]['used'],63)

    def test_unknown_does_not_become_zero(self):
        q=normalize_quotas({'rateLimits':{'primary':{'usedPercent':None,'resetsAt':None}}})[0]
        self.assertIsNone(q['used'])
        self.assertEqual(countdown(q['reset']), '重置时间未知')
        self.assertEqual(normalize_quotas({'rateLimits':None}),[])

    def test_multibucket_preferred_and_both_windows_kept(self):
        d={'rateLimits':{'primary':{'usedPercent':99}},'rateLimitsByLimitId':{'codex':{'primary':{'usedPercent':20},'secondary':{'usedPercent':30}},'other':{'primary':{'usedPercent':40}}}}
        self.assertEqual([q['used'] for q in normalize_quotas(d)],[20,30,40])

    def test_nonfinite_and_out_of_range(self):
        for bad in [float('nan'),True,'50']:
            self.assertIsNone(normalize_quotas({'rateLimits':{'primary':{'usedPercent':bad}}})[0]['used'])
        self.assertEqual(normalize_quotas({'rateLimits':{'primary':{'usedPercent':110}}})[0]['used'],100)

    def test_reset_waits_for_server(self):
        self.assertIn('待确认',countdown(100,101))
        self.assertEqual(countdown(161,100),'2 分钟后重置')
        self.assertEqual(countdown(3700,100),'1 小时 0 分钟后重置')

    def test_failure_backoff(self):
        self.assertEqual([next_delay(300,n) for n in range(5)],[300,600,1200,1800,1800])

    def test_layout_leaves_controls_and_handles_edge(self):
        anchor={'x':800,'y':300,'displayBounds':{'x':0,'y':0,'width':1707,'height':960}}
        x,y,placement=choose_position(anchor,112,250,96)
        self.assertEqual((x,y,placement),(731,464,'below'))
        anchor['y']=800
        x,y,placement=choose_position(anchor,112,250,96)
        self.assertEqual(placement,'above')
        self.assertEqual(x,731)
        self.assertLessEqual(y+96,952)

    def test_negative_monitor(self):
        a={'x':-900,'y':200,'displayBounds':{'x':-1920,'y':0,'width':1920,'height':1080}}
        x,y,_=choose_position(a,112,250,96)
        self.assertLess(x,0)
        self.assertGreaterEqual(x,-1912)

    def test_pet_state_retries_partial_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'.codex-global-state.json'
            state=PetState(tmp)
            p.write_text('{',encoding='utf-8')
            self.assertIsNone(state.read())
            p.write_text(json.dumps({'electron-avatar-overlay-open':True,'electron-avatar-overlay-bounds':{'x':10,'y':20}}),encoding='utf-8')
            state.next_read=0
            self.assertEqual(state.read()['anchor']['x'],10)
            p.write_text('{',encoding='utf-8')
            state.next_read=0
            self.assertEqual(state.read()['anchor']['x'],10)

    def test_read_only_protocol(self):
        self.assertEqual(ALLOWED_METHODS,{'initialize','initialized','account/rateLimits/read'})

    def test_drag_tracks_before_saved_position_changes(self):
        drag=DragAnchor(); saved={'x':100,'y':100}
        drag.update(saved,112,(130,140),True,True,0)
        live=drag.update(saved,112,(230,200),True,False,.1)
        self.assertEqual((live['x'],live['y']),(200,160))
        self.assertEqual(drag.update(saved,112,(230,200),False,False,.2),live)
        self.assertEqual(drag.update(saved,112,(230,200),False,False,.3),live)
        self.assertEqual(drag.update({'x':200,'y':160},112,(230,200),False,False,.4),{'x':200,'y':160})

    def test_drag_ignores_other_windows_and_recovers_cancel(self):
        drag=DragAnchor(); saved={'x':100,'y':100}
        drag.update(saved,112,(130,140),True,False,0)
        self.assertEqual(drag.update(saved,112,(230,240),True,False,.1),saved)
        drag.update(saved,112,(130,140),False,False,.2)
        drag.update(saved,112,(130,140),True,True,.3)
        drag.update(saved,112,(230,240),True,True,.4)
        drag.update(saved,112,(230,240),False,False,.5)
        self.assertEqual(drag.update(saved,112,(230,240),False,False,2.1),saved)

    def test_pet_identification_excludes_main_window(self):
        windows=[{'hwnd':1,'rect':(0,0,1000,900),'style':262400,'visible':True},
                 {'hwnd':2,'rect':(90,0,400,900),'style':524456,'visible':True}]
        self.assertEqual(select_pet(windows,{'x':100,'y':100},112)['hwnd'],2)

    def test_renewal_is_validated_without_guessing_next_month(self):
        self.assertEqual(parse_renewal('2026-09-22'),'2026-09-22')
        for bad in ['2026-02-30','2026-9-22','hello']:
            with self.assertRaises(ValueError):parse_renewal(bad)
        self.assertIn('还有 3 天',renewal_caption('2026-09-22',date(2026,9,19)))
        self.assertIn('已过期',renewal_caption('2026-09-22',date(2026,10,1)))
        self.assertEqual(renewal_caption(''),'未设置')

    def test_account_metadata_preserves_unknown_and_excludes_ids(self):
        self.assertIsNone(normalize_account_meta({})['reset_count'])
        out=normalize_account_meta({'rateLimits':{'planType':'prolite'},'rateLimitResetCredits':{'availableCount':0,'credits':[]},'accountId':'private'})
        self.assertEqual(out['reset_count'],0)
        self.assertEqual(out['plan'],'prolite')
        self.assertNotIn('accountId',out)

    def test_visible_quotas_never_invents_windows_or_mixes_buckets(self):
        weekly=dict(bucket='codex',duration=10080,used=20)
        short=dict(bucket='codex',duration=300,used=10)
        other=dict(bucket='other',duration=300,used=30)
        self.assertEqual(visible_quotas({'quotas':[weekly]},weekly,'standard'),[weekly])
        self.assertEqual(visible_quotas({'quotas':[weekly,other,short]},weekly,'standard'),[short,weekly])
        self.assertEqual(visible_quotas({'quotas':[weekly,short]},weekly,'compact'),[weekly])

    def test_stale_status_precedes_renewal_and_never_assumes_reset(self):
        self.assertIn('数据待更新',status_caption({'checked_at':100},{'interval':300,'renewal_date':'2030-01-01'},now=999))
        self.assertIn('数据待更新',status_caption({'checked_at':998},{'interval':300},error=True,now=999))

    def test_pedestal_placement_respects_negative_display_and_bottom(self):
        a=dict(x=-600,y=200,displayBounds=dict(x=-1920,y=0,width=1920,height=1080))
        x,y,place=pedestal_position(a,112,220,122)
        self.assertEqual((x,y,place),(-654,310,'integrated'))
        a['y']=950
        x,y,place=pedestal_position(a,112,220,122)
        self.assertEqual(place,'above');self.assertLess(y+122,a['y'])

    def test_custom_colors_choose_readable_text(self):
        for value in range(0,256,8):
            color='#'+f'{value:02x}'*3
            p=palette(dict(color_theme='custom',custom_body=color,theme='light'))
            for key in ['fg','muted']:
                contrast=(max(luminance(p['bg']),luminance(p[key]))+.05)/(min(luminance(p['bg']),luminance(p[key]))+.05)
                self.assertGreaterEqual(contrast,4.5,(color,key))


if __name__=='__main__':unittest.main()
