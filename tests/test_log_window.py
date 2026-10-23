import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from gui.app_webview import ProxyTunBridgeApi


class FakeWindow:
    def __init__(self):
        self.width,self.height,self.x,self.y=520,760,600,80
        self.native=SimpleNamespace(_scale=1.0)
        self.resizes=[];self.moves=[]
    def resize(self,width,height):
        self.width,self.height=width,height;self.resizes.append((width,height))
    def move(self,x,y):
        self.x,self.y=x,y;self.moves.append((x,y))


class LogWindowTests(unittest.TestCase):
    def test_150_percent_workarea_and_negative_mixed_monitor_restore(self):
        for left in (0,-1920):
            with self.subTest(left=left):
                window=FakeWindow();window.native._scale=1.5
                window.width,window.height=520,600
                window.x,window.y=(60 if left==0 else -1100),40
                original=(window.width,window.height,window.x,window.y)
                api=self.bridge(window)
                # Screen.scale deliberately differs: window.native._scale is
                # the exact multiplier used by installed resize/move backend.
                areas=[SimpleNamespace(x=x,y=0,width=1920,height=1080,scale=1 if x==0 else 2,
                    frame=SimpleNamespace(X=x,Y=0,Width=1920,Height=1040)) for x in (-1920,0)]
                with patch('gui.app_webview.webview',SimpleNamespace(screens=areas)):
                    self.assertTrue(api.set_log_view(True)['success'])
                    self.assertLessEqual(window.height*1.5,1040)
                    self.assertGreaterEqual(window.x*1.5,left)
                    self.assertLessEqual((window.x+window.width)*1.5,left+1920)
                    self.assertTrue(api.set_log_view(False)['success'])
                    self.assertEqual((window.width,window.height,window.x,window.y),original)
    def bridge(self,window):
        api=ProxyTunBridgeApi.__new__(ProxyTunBridgeApi)
        api._window=window;api._lock=threading.RLock()
        return api
    def test_idempotent_expand_restore_and_workarea_clamp(self):
        window=FakeWindow();api=self.bridge(window)
        area=SimpleNamespace(X=0,Y=0,Width=1280,Height=900)
        screens=[SimpleNamespace(x=0,y=0,width=1280,height=960,frame=area)]
        with patch('gui.app_webview.webview',SimpleNamespace(screens=screens)):
            self.assertTrue(api.set_log_view(True)['success'])
            self.assertEqual((window.width,window.height),(1120,820))
            self.assertLessEqual(window.x+window.width,1280)
            self.assertLessEqual(window.y+window.height,900)
            api.set_log_view(True);self.assertEqual(len(window.resizes),1)
            self.assertTrue(api.set_log_view(False)['success'])
            self.assertEqual((window.width,window.height,window.x,window.y),(520,760,600,80))
            api.set_log_view(False);self.assertEqual(len(window.resizes),2)
    def test_small_offset_screen_and_invalid_input_no_window(self):
        window=FakeWindow();window.x=-700;window.y=0
        api=self.bridge(window)
        area=SimpleNamespace(X=-900,Y=0,Width=900,Height=700)
        screens=[SimpleNamespace(x=-900,y=0,width=900,height=700,frame=area)]
        with patch('gui.app_webview.webview',SimpleNamespace(screens=screens)):
            self.assertTrue(api.set_log_view(True)['success'])
            self.assertEqual((window.width,window.height),(900,700))
            self.assertEqual((window.x,window.y),(-900,0))
        for value in (1,'true',None,[]):
            self.assertFalse(api.set_log_view(value)['success'])
        self.assertFalse(self.bridge(None).set_log_view(True)['success'])
