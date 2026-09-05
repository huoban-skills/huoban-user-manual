"""Offline Windows annotation regression checks; no browser or account required."""
import importlib.util
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


a, b, r = load('annotate'), load('browser'), load('render')


def png(width, height):
    stream = io.BytesIO()
    Image.new('RGB', (width, height), 'white').save(stream, format='PNG')
    return stream.getvalue()


class WindowsTests(unittest.TestCase):
    def test_font_selection_matches_platform(self):
        for platform, expected in [('win32', 'fonts'), ('darwin', '/System/Library/Fonts/'),
                                   ('linux', '/usr/share/fonts/')]:
            with self.subTest(platform=platform), patch.object(a.sys, 'platform', platform), \
                 patch.object(a.ImageFont, 'truetype', return_value='font') as truetype:
                self.assertEqual(a._font(20), 'font')
                self.assertIn(expected.lower(), str(truetype.call_args.args[0]).lower())

    def test_native_font_size(self):
        small, large = a._font(16), a._font(32)
        self.assertEqual((small.size, large.size), (16, 32))
        self.assertGreater(large.getbbox('1')[3], small.getbbox('1')[3])
        if sys.platform == 'win32':
            self.assertIn('fonts', str(large.path).lower())

    def test_sized_fallback_without_system_fonts(self):
        original = a.ImageFont.truetype
        def no_system_font(font, *args, **kwargs):
            if isinstance(font, (str, os.PathLike)):
                raise OSError('No system fonts')
            return original(font, *args, **kwargs)
        with patch.object(a.ImageFont, 'truetype', side_effect=no_system_font):
            self.assertEqual(a._font(32).size, 32)

    def test_actual_pixel_ratios(self):
        for scale in (1, 1.25, 1.5, 2):
            with self.subTest(scale=scale):
                g = b.screenshot_geometry(png(int(800 * scale), int(600 * scale)), [800, 600], 'viewport')
                self.assertEqual(g['css_to_image_scale'], [scale, scale])
                self.assertEqual(200 * scale / g['css_to_image_scale'][0], 200)
        g = b.screenshot_geometry(png(1001, 750), [800, 600], 'viewport')
        self.assertEqual(g['css_to_image_scale'], [1001 / 800, 1.25])

    def test_partial_images_do_not_offer_viewport_conversion(self):
        for kind in ('element', 'full_page'):
            g = b.screenshot_geometry(png(800, 1200), [800, 600], kind)
            self.assertNotIn('css_to_image_scale', g)

    def test_grid_crop_and_numbered_boxes_unicode_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / '中文 截图.png')
            Path(path).write_bytes(png(1200, 800))
            a.grid(path, (10, 90))
            a.check_measured(path, (10, 90))
            with self.assertRaises(SystemExit):
                a.check_measured(path, None)
            self.assertEqual(a.annotate(path, [(20, 20, 35, 35), (60, 60, 75, 75)], [], [], (10, 90)), (1200, 640))
            with Image.open(path) as im:
                pixels = list(im.get_flattened_data()) if hasattr(im, 'get_flattened_data') else list(im.getdata())
                self.assertGreater(pixels.count((217, 119, 87)), 100)
                # Digit pixels inside the colored first badge remain white.
                self.assertGreater(sum(im.getpixel((x, y)) == (255, 255, 255)
                                       for x in range(232, 240) for y in range(122, 134)), 5)

    def test_shot_writes_utf8_evidence_and_scale(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'images' / '截图.png'
            class Page:
                url = 'https://example.invalid/'
                def wait_for_load_state(self, *args, **kwargs): pass
                def title(self): return '中文与特殊字符 🧭'
                def evaluate(self, js):
                    return [800, 600] if js == '[innerWidth, innerHeight]' else []
                def screenshot(self, **kwargs):
                    data = png(1000, 750)
                    Path(kwargs['path']).write_bytes(data)
                    return data
            args = SimpleNamespace(prep=None, prep_hover=None, prep_mouse=None, prep_after=None,
                                   blur=None, mask=None, highlight=None, selector=None,
                                   full_page=False, path=str(path))
            with patch.object(b, 'run', side_effect=lambda fn: fn(Page(), [])):
                b.cmd_shot(args)
            meta = json.loads(Path(str(path) + '.meta.json').read_text(encoding='utf-8'))
            self.assertEqual(meta['title'], '中文与特殊字符 🧭')
            self.assertEqual(meta['screenshot']['css_to_image_scale'], [1.25, 1.25])
            metas, _ = r.load_evidence(Path(tmp))
            self.assertTrue(metas)

    def test_hl_uses_current_interpreter_and_sibling_browser(self):
        with patch.object(sys, 'argv', [str(HERE / 'hl.py'), '中文 图.png', '按钮|0']), \
             patch('subprocess.run', return_value=SimpleNamespace(returncode=0)) as run, \
             patch.dict(os.environ):
            with self.assertRaises(SystemExit) as result:
                runpy.run_path(str(HERE / 'hl.py'), run_name='__main__')
            self.assertEqual(result.exception.code, 0)
            for call in run.call_args_list:
                self.assertEqual(call.args[0][:2], [sys.executable, str(HERE / 'browser.py')])


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    unittest.main()
