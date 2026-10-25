import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from accessory_layout import quota_sides,plan_accessories
from accessories import render_accessories,ornament,ink_insets,CELL_WIDTH,HEIGHT
from appearance import palette

class SplitTests(unittest.TestCase):
    def setUp(self):
        self.quotas=[dict(duration=300,used=20,reset=1800010000),dict(duration=10080,used=45,reset=1800090000)]
        self.settings=dict(layout_mode='split',visible_sides='both',accessory_side='right',accessory_gap=4)
        self.anchor=dict(x=500,y=300)
        self.work=(0,0,1920,1040)

    def insets(self,quotas,side):
        im,_=render_accessories(quotas,'feather',palette({}),side,now=1800000000)
        return ink_insets(im,CELL_WIDTH*len(quotas))

    def plans(self):return plan_accessories(self.quotas,self.settings,self.anchor,112,self.work,self.insets)

    def test_cycle_identity_and_swap_before_hiding(self):
        self.assertEqual([(s,qs[0]['duration']) for s,qs in quota_sides(self.quotas,self.settings)],[('left',300),('right',10080)])
        self.settings.update(visible_sides='right')
        self.assertEqual(quota_sides(self.quotas,self.settings),[('right',[self.quotas[1]])])
        self.settings.update(swap_sides=True)
        self.assertEqual(quota_sides(self.quotas,self.settings),[('right',[self.quotas[0]])])

    def test_separate_windows_reserve_pet_and_controls(self):
        plans=self.plans();self.assertEqual(len(plans),2)
        for p in plans:
            im,_=render_accessories(p['quotas'],'feather',palette({}),p['side'],now=1800000000)
            box=im.getbbox()
            if p['side']=='left':self.assertLessEqual(p['x']+box[2],488)
            else:self.assertGreaterEqual(p['x']+box[0],624)

    def test_disabled_side_never_returns_at_screen_edge(self):
        self.settings['visible_sides']='left';self.anchor['x']=0
        self.assertEqual(self.plans(),[])
        self.settings['visible_sides']='right';self.anchor['x']=1770
        self.assertEqual(self.plans(),[])

    def test_edge_merge_and_restore(self):
        self.anchor['x']=0;plans=self.plans()
        self.assertEqual(len(plans),1);self.assertEqual(plans[0]['side'],'right')
        self.assertEqual(plans[0]['quotas'],self.quotas)
        self.anchor['x']=500;self.assertEqual(len(self.plans()),2)

    def test_single_cycle_not_duplicated(self):
        self.quotas=self.quotas[1:]
        self.assertEqual(len(self.plans()),1)
        self.settings['visible_sides']='left'
        self.assertEqual(self.plans()[0]['side'],'left')
        self.quotas=[];self.assertEqual(len(self.plans()),1)

    def test_mirroring_keeps_text_identical(self):
        p=palette({})
        normal,_=render_accessories(self.quotas[:1],'feather',p,'left',now=1800000000)
        flipped,_=render_accessories(self.quotas[:1],'feather',p,'left',now=1800000000,mirror=True)
        self.assertEqual(normal.crop((0,119,112,HEIGHT)).tobytes(),flipped.crop((0,119,112,HEIGHT)).tobytes())
        self.assertNotEqual(normal.crop((0,24,112,74)).tobytes(),flipped.crop((0,24,112,74)).tobytes())
        low=ornament('feather',4,p,p['accent'],10,'left')
        high=ornament('feather',4,p,p['accent'],90,'left')
        self.assertEqual(low.getchannel('A').tobytes(),high.getchannel('A').tobytes())
        self.assertNotEqual(low.tobytes(),high.tobytes())

    def test_movement_both_sides_and_negative_monitor(self):
        before=self.plans();self.anchor.update(x=540,y=330);after=self.plans()
        for a,b in zip(before,after):self.assertEqual((b['x']-a['x'],b['y']-a['y']),(40,30))
        self.anchor['x']=-600;self.work=(-1920,0,0,1040)
        self.assertEqual(len(self.plans()),2)
        self.anchor['y']=1040-HEIGHT+1;self.assertEqual(self.plans(),[])

    def test_together_respects_visibility_and_swap(self):
        self.settings.update(layout_mode='together',visible_sides='left',swap_sides=True)
        plans=self.plans();self.assertEqual(len(plans),1)
        self.assertEqual(plans[0]['side'],'left');self.assertEqual(plans[0]['quotas'],[self.quotas[1]])

if __name__=='__main__':unittest.main()
