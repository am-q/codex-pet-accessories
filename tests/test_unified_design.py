import sys, unittest, math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from accessories import STYLES,render_accessories,ornament,quota_palette,progress_points,HEIGHT
from appearance import palette

NOW=1800000000

class UnifiedDesignTests(unittest.TestCase):
    def setUp(self):
        self.p=palette(dict(theme='dark'))
        self.short=dict(duration=300,used=28,reset=NOW+8000)
        self.long=dict(duration=10080,used=62,reset=NOW+200000)

    def render(self,quotas,style,side='right',**kw):
        return render_accessories(quotas,style,self.p,side,now=NOW,**kw)

    def test_same_side_merge_preserves_each_cycle_pixels(self):
        for style in STYLES:
            for order in ([self.short,self.long],[self.long,self.short]):
                with self.subTest(style=style,first=order[0]['duration']):
                    merged,_=self.render(order,style)
                    for index,q in enumerate(order):
                        single,_=self.render([q],style)
                        self.assertEqual(merged.crop((index*112,0,(index+1)*112,HEIGHT)).tobytes(),single.tobytes())

    def test_single_week_keeps_white_material_and_distinct_cycle_color(self):
        short,long=quota_palette(self.p,self.short),quota_palette(self.p,self.long)
        self.assertNotEqual(short['accent'],long['accent'])
        from appearance import luminance
        self.assertLess(luminance(short['plume_body']),.1)
        self.assertGreater(luminance(long['plume_body']),.8)
        for side in ('left','right'):
            alone,_=self.render([self.long],'battery',side)
            pair,_=self.render([self.short,self.long],'battery',side)
            self.assertEqual(alone.tobytes(),pair.crop((112,0,224,HEIGHT)).tobytes())

    def test_feather_and_wing_progress_is_visible_monotonic_and_intact(self):
        for style in ('feather','wing'):
            for q in (self.short,self.long):
                p=quota_palette(self.p,q)
                rgb=tuple(int(p['accent'][i:i+2],16) for i in (1,3,5))+(255,)
                counts=[];masks=[]
                for value in (0,25,50,75,100):
                    im=ornament(style,4,p,p['accent'],value,'left')
                    counts.append(dict((color,count) for count,color in im.getcolors(im.width*im.height)).get(rgb,0))
                    masks.append(im.getchannel('A').tobytes())
                with self.subTest(style=style,period=q['duration']):
                    self.assertTrue(all(a<b for a,b in zip(counts,counts[1:])),counts)
                    self.assertTrue(all(mask==masks[0] for mask in masks))
                    filled=counts[-1]-counts[0]
                    self.assertAlmostEqual((counts[2]-counts[0])/filled,.5,delta=.06)
                    unknown=ornament(style,4,p,p['accent'],None,'left')
                    empty=ornament(style,4,p,p['accent'],0,'left')
                    self.assertEqual(unknown.tobytes(),empty.tobytes())

    def test_progress_uses_length_not_number_of_segments(self):
        points=[(0,0),(10,0),(10,30)]
        self.assertEqual(progress_points(points,50),[(0,0),(10,0),(10,10)])
        self.assertEqual(progress_points(points,0),[])
        self.assertEqual(progress_points(points,None),[])
        self.assertEqual(progress_points(points,100),points)

    def test_non_directional_styles_keep_same_orientation(self):
        for style in ('battery','dial','crystal'):
            original,_=self.render([self.short],style,'left')
            mirrored,_=self.render([self.short],style,'left',mirror=True)
            other,_=self.render([self.short],style,'right')
            self.assertEqual(original.tobytes(),mirrored.tobytes())
            self.assertEqual(original.tobytes(),other.tobytes())

    def test_direction_changes_keep_text_positions(self):
        for style in ('bookmark','feather','wing'):
            normal,boxes=self.render([self.short],style,'left')
            mirrored,other_boxes=self.render([self.short],style,'left',mirror=True)
            self.assertEqual(boxes,other_boxes)
            self.assertNotEqual(normal.tobytes(),mirrored.tobytes())
            if style!='bookmark':
                self.assertEqual(normal.crop((0,119,112,HEIGHT)).tobytes(),mirrored.crop((0,119,112,HEIGHT)).tobytes())

    def test_bookmark_lower_ends_tilt_outward(self):
        body=tuple(int(self.p['bg'][i:i+2],16) for i in (1,3,5))+(255,)
        centers=[]
        for side in ('left','right'):
            im,_=self.render([self.short],'bookmark',side)
            xs=[x for x in range(112) if im.getpixel((x,82))==body]
            self.assertTrue(xs)
            centers.append(sum(xs)/len(xs))
        self.assertLess(centers[0],56)
        self.assertGreater(centers[1],56)

    def test_low_quota_warning_does_not_overwrite_text_or_cycle_color(self):
        for style in STYLES:
            q={**self.short,'used':95}
            im,boxes=self.render([q],style,'left')
            warning=(214,108,125,255)
            dots=[(x,y) for y in range(HEIGHT) for x in range(112) if im.getpixel((x,y))[3]>230 and max(abs(a-b) for a,b in zip(im.getpixel((x,y))[:3],warning[:3]))<20]
            self.assertTrue(dots,style)
            for x,y in dots:
                self.assertFalse(any(l<=x<=r and t<=y<=b for l,t,r,b in boxes),(style,x,y,boxes))
            self.assertEqual(quota_palette(self.p,q)['accent'],quota_palette(self.p,self.short)['accent'])

    def test_toolbar_baseline_layout_keeps_text_disjoint_at_native_dpi(self):
        self.assertEqual(HEIGHT,160)
        for style in STYLES:
            for scale in (1.5,2):
                for q,stale in ((self.long,False),(self.short,True),({},False)):
                    im,boxes=self.render([q],style,stale=stale,pixel_size=(round(112*scale),round(HEIGHT*scale)))
                    with self.subTest(style=style,scale=scale,stale=stale):
                        self.assertEqual(im.size,(round(112*scale),round(HEIGHT*scale)))
                        for i,(l,t,r,b) in enumerate(boxes):
                            self.assertTrue(0<=l<r<=112 and 0<=t<b<=HEIGHT,(l,t,r,b))
                            for ll,tt,rr,bb in boxes[i+1:]:
                                self.assertFalse(min(r,rr)>max(l,ll) and min(b,bb)>max(t,tt),boxes)

    def test_theme_option_keeps_custom_color_and_unknown_duration_is_neutral(self):
        p=palette(dict(color_theme='custom',custom_body='#303030',custom_accent='#df8e56',quota_colors='theme'))
        self.assertEqual(quota_palette(p,self.short)['accent'],p['accent'])
        self.assertEqual(quota_palette(p,self.long)['accent'],p['accent'])
        for duration in (None,0,float('nan')):
            self.assertEqual(quota_palette(self.p,dict(duration=duration))['role'],'unknown')

if __name__=='__main__':unittest.main()
