import sys,unittest,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from accessories import side_position,render_accessories,remaining,STYLES,CELL_WIDTH,HEIGHT,ink_insets
from appearance import palette

class AccessoryTests(unittest.TestCase):
    def test_sides_and_edge_flip(self):
        a=dict(x=500,y=300,displayBounds=dict(x=0,y=0,width=1920,height=1080))
        self.assertEqual(side_position(a,112,112,174,'left'),(376,284,'left'))
        self.assertEqual(side_position(a,112,112,174,'right'),(624,284,'right'))
        a['x']=1760
        self.assertEqual(side_position(a,112,112,174,'right')[2],'left')
        a['x']=10
        self.assertEqual(side_position(a,112,112,174,'left')[2],'right')

    def test_negative_monitor_and_work_area(self):
        a=dict(x=-500,y=200,displayBounds=dict(x=-1920,y=0,width=1920,height=1080))
        self.assertEqual(side_position(a,112,112,174,'right',(-1920,0,0,1040)),(-376,184,'right'))
        a['y']=890
        self.assertIsNone(side_position(a,112,112,174,'right',(-1920,0,0,1040)))

    def test_no_space_does_not_overlap(self):
        a=dict(x=80,y=100,displayBounds=dict(x=0,y=0,width=270,height=300))
        self.assertIsNone(side_position(a,112,112,174))
        a['displayBounds']['width']=380
        self.assertIsNotNone(side_position(a,112,112,174))
        self.assertIsNone(side_position(a,112,224,174))

    def test_render_states_and_text_bounds(self):
        now=time.time()
        for style in STYLES:
            for side in ('left','right'):
                for used in (None,0,40,99.5,100):
                    with self.subTest(style=style,side=side,used=used):
                        q=dict(used=used,duration=10080,reset=now+6*86400)
                        image,boxes=render_accessories([q],style,palette({}),side,now=now)
                        self.assertEqual(image.size,(112,HEIGHT))
                        self.assertIsNotNone(image.getbbox())
                        for l,t,r,b in boxes:self.assertTrue(l>=0 and t>=0 and r<=112 and b<=HEIGHT,(l,t,r,b))
                        self.assertEqual(image.getpixel((0,0))[3],0)
        for style in STYLES:
            q=dict(used=50,duration=300,reset=now-1)
            image,_=render_accessories([q,q],style,palette({'theme':'dark'}),stale=True,pixel_size=(336,round(HEIGHT*1.5)))
            self.assertEqual(image.size,(336,round(HEIGHT*1.5)))
            missing,_=render_accessories([],style,palette({}),busy=True)
            self.assertIsNotNone(missing.getbbox())

    def test_unknown_and_numeric_edges(self):
        for v in (None,'40',float('nan'),float('inf')):self.assertIsNone(remaining({'used':v}))
        self.assertEqual(remaining({'used':120}),0)
        self.assertEqual(remaining({'used':-4}),100)

    def test_visible_ink_not_padding_sets_distance(self):
        now=time.time();a=dict(x=500,y=300)
        for style in STYLES:
            for side in ('left','right'):
                q=dict(used=45,duration=10080,reset=now+6*86400)
                image,_=render_accessories([q],style,palette({}),side,now=now)
                inset=ink_insets(image,112)
                x,y,actual=side_position(a,112,112,174,side,gap=4,insets=inset)
                self.assertEqual(actual,side)
                self.assertEqual(x+inset[0]-620,4) if side=='right' else self.assertEqual(492-(x+112-inset[1]),4)
                bbox=image.getbbox()
                self.assertGreaterEqual(x+bbox[0],624) if side=='right' else self.assertLessEqual(x+bbox[2],488)
                # Physical-pixel antialiasing must preserve the logical safety gap.
                for factor in (1.5,2):
                    large,_=render_accessories([q],style,palette({}),side,now=now,pixel_size=(round(112*factor),round(HEIGHT*factor)))
                    bb=large.getbbox()
                    self.assertGreaterEqual(x+bb[0]/factor,620) if side=='right' else self.assertLessEqual(x+bb[2]/factor,492)
                if style=='battery' and side=='right':self.assertLess(x,610)

if __name__=='__main__':unittest.main()
