"""Guard the DPI boundary that previously caused repeated UI regressions."""
import ast
import ctypes
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'src'
sys.path.insert(0,str(ROOT))
from dpi_policy import dpi_context,native_ui

class DpiPolicyTests(unittest.TestCase):
    def test_ui_methods_cannot_switch_to_logical_dpi(self):
        # Only the monitor query adapter may use logical mode in UI modules.
        for filename in ('pet_base.py','base_menu.py','smooth_surface.py'):
            tree=ast.parse((ROOT/filename).read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    for decorator in node.decorator_list:
                        if isinstance(decorator,ast.Name) and decorator.id=='logical_coordinates':
                            self.assertEqual((filename,node.name),('base_menu.py','monitor_work_area'))
                if isinstance(node,ast.With):
                    for item in node.items:
                        expression=item.context_expr
                        if isinstance(expression,ast.Call) and getattr(expression.func,'id','')=='dpi_context':
                            self.assertNotEqual(ast.literal_eval(expression.args[0]),-1,filename)

    def test_coordinate_adapters_do_not_process_tk_events(self):
        tree=ast.parse((ROOT/'dpi_policy.py').read_text(encoding='utf-8'))
        forbidden={'update','update_idletasks','mainloop','geometry','configure','pack','grid'}
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                self.assertNotIn(node.func.attr,forbidden)

    def test_native_callback_restores_its_callers_context(self):
        u=ctypes.windll.user32
        u.GetThreadDpiAwarenessContext.restype=ctypes.c_void_p
        u.AreDpiAwarenessContextsEqual.argtypes=[ctypes.c_void_p,ctypes.c_void_p]
        @native_ui
        def callback():
            self.assertTrue(u.AreDpiAwarenessContextsEqual(u.GetThreadDpiAwarenessContext(),ctypes.c_void_p(-4)))
            raise ValueError('test exception')
        previous=u.GetThreadDpiAwarenessContext()
        with dpi_context(-1):
            with self.assertRaises(ValueError):callback()
            self.assertTrue(u.AreDpiAwarenessContextsEqual(u.GetThreadDpiAwarenessContext(),ctypes.c_void_p(-1)))
        self.assertTrue(u.AreDpiAwarenessContextsEqual(u.GetThreadDpiAwarenessContext(),previous))

if __name__=='__main__':unittest.main()
