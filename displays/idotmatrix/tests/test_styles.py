"""Offline contract checks. No hub, account, LaunchAgent, or Bluetooth access."""
import asyncio
from dataclasses import replace
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image
import bridge
from style import save_settings
from styles import STYLE_IDS, renderer
from styles.common import Snapshot, Service, normalize, centered, color, word, canvas
from styles.previews import sample
from styles.runtime import Settings, StyleSession, read_settings


class DataTests(unittest.TestCase):
    def test_labels_and_service_slots(self):
        snap = normalize([{'name': 'ChatGPT / Codex', 'meters': [
            {'label': 'Weekly (Opus)', 'left': 2}, {'label': 'Weekly (all models)', 'left': 82},
            {'label': '5-hour session', 'left': 54}]}])
        self.assertEqual(snap.services[0].limits, (None, None))
        self.assertEqual(snap.services[1].limits, (54, 82))

    def test_missing_does_not_become_zero_or_model_specific(self):
        snap = normalize([{'name': 'Claude', 'meters': [
            {'label': 'Weekly (Opus)', 'left': 2}, {'label': '5-hour', 'left': float('nan')}]}])
        self.assertEqual(snap.services[0].limits, (None, None))
        self.assertEqual(word(snap.services[0], 0), '?')

    def test_clamping_and_credits(self):
        snap = sample(120, -5, 0, 82, True)
        self.assertEqual(snap.services[0].limits, (100, 0))
        self.assertEqual(word(snap.services[0], 1), '0')
        self.assertEqual(word(snap.services[1], 0), 'CR')

    def test_every_renderer_handles_missing_and_status(self):
        cases = [sample(), sample(100, 100, 100, 100), sample(0, 0, 0, 0, True),
                 sample(1, 9, 10, 99), Snapshot(), normalize([{'name': 'Claude', 'age_seconds': 240,
                 'meters': [{'label': '5-hour', 'left': 65}]}], offline=True)]
        for style in STYLE_IDS:
            for snap in cases:
                for page in (0, 1) if style in ('big-jewels', 'service-spotlight') else (0,):
                    im = renderer(style)(snap, page=page)
                    self.assertEqual((im.size, im.mode), ((32, 32), 'RGB'))
            offline = renderer(style)(replace(sample(), offline=True))
            self.assertEqual(offline.getpixel((31, 0)), (255, 40, 30))

    def test_text_centers_dont_move_with_digit_count(self):
        for cx in (8, 13, 24, 26):
            for val in ('1', '65', '100', 'CR', '?'):
                im = canvas()
                centered(im.load(), cx, 0, val, (255, 255, 255))
                bbox = im.getbbox()
                self.assertEqual((bbox[0]+bbox[2]-1)/2, cx)

    def test_mochi_only_claude_five_changes_the_scene(self):
        draw = renderer('baby-mochi')
        a = draw(sample(72, 89, 54, 82))
        b = draw(sample(72, 86, 48, 79))
        self.assertEqual(a.crop((0, 0, 32, 19)).tobytes(), b.crop((0, 0, 32, 19)).tobytes())
        self.assertNotEqual(a.tobytes(), b.tobytes())
        fresh = sample()
        stale = replace(fresh, services=(replace(fresh.services[0], stale=True), fresh.services[1]))
        self.assertEqual(draw(stale).getpixel((31, 0)), (255, 175, 0))
        # Header logo follows the affected service's dimming, not the other service's.
        self.assertEqual(draw(stale).getpixel((25, 15)), draw(fresh).getpixel((25, 15)))


class RuntimeTests(unittest.TestCase):
    def test_nibble_then_still_and_refill(self):
        session = StyleSession()
        cfg = Settings('baby-mochi')
        self.assertIsNone(session.plan(sample(100), cfg).settle)
        plan = session.plan(sample(72), cfg)
        self.assertEqual((len(plan.frames), plan.seconds, plan.loop), (14, .84, False))
        self.assertEqual(plan.settle.tobytes(), renderer('baby-mochi')(sample(72)).tobytes())
        self.assertIsNone(session.plan(sample(72, 50, 35, 70), cfg).settle)
        self.assertIsNone(session.plan(sample(72, 50, 35, 70), cfg).settle)
        self.assertEqual(session.plan(sample(100), cfg).seconds, .6)

    def test_freshness_and_switches_suppress_catch_up_animation(self):
        cfg = Settings('baby-mochi')
        for middle in [replace(sample(72), offline=True),
                       replace(sample(72), services=(Service((72, 23), stale=True, present=True), Service())),
                       Snapshot()]:
            session = StyleSession()
            session.plan(sample(100), cfg)
            self.assertIsNone(session.plan(middle, cfg).settle)
            self.assertIsNone(session.plan(sample(35), cfg).settle)
        session = StyleSession()
        session.plan(sample(100), cfg)
        session.plan(sample(72), Settings('spectrum'))
        self.assertIsNone(session.plan(sample(35), cfg).settle)

    def test_rotation_is_explicit(self):
        for style in ('big-jewels', 'service-spotlight'):
            self.assertEqual(len(StyleSession().plan(sample(), Settings(style)).frames), 1)
            plan = StyleSession().plan(sample(), Settings(style, rotate=True))
            self.assertTrue(plan.loop)
            self.assertEqual(plan.durations_ms, [3000, 3000])

    def test_atomic_selector_and_invalid_config_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'settings.json'
            self.assertEqual(read_settings(path)[0].style, 'legacy')
            cfg = Settings('baby-mochi')
            save_settings(path, cfg)
            self.assertEqual(read_settings(path)[0], cfg)
            path.write_text('{"style":"../../bad"}')
            loaded, error = read_settings(path, cfg)
            self.assertEqual(loaded, cfg)
            self.assertIsNotNone(error)
            path.write_text('{')
            self.assertEqual(read_settings(path, cfg)[0], cfg)
            save_settings(path, Settings('diamonds'))
            self.assertEqual(read_settings(path)[0].style, 'diamonds')
            path.unlink()
            self.assertEqual(read_settings(path)[0].style, 'legacy')
        for bad in ({'style': 'baby-mochi', 'rotate': True}, {'style': 'big-jewels', 'page': 2},
                    {'style': 'spectrum', 'seconds': float('nan')}, {'style': 'big-jewels', 'rotate': 'false'}):
            with self.assertRaises(ValueError):
                Settings.from_dict(bad)


class BridgeTests(unittest.TestCase):
    def plan(self):
        session = StyleSession()
        cfg = Settings('baby-mochi')
        session.plan(sample(100), cfg)
        return session.plan(sample(65), cfg)

    def test_encoding_and_loop_metadata(self):
        plan = self.plan()
        kind, data = bridge.encode_presentation(plan)
        im = Image.open(io.BytesIO(data))
        self.assertEqual(kind, 'gif')
        self.assertNotIn('loop', im.info)
        total = 0
        for index in range(im.n_frames):
            im.seek(index)
            total += im.info['duration']
        self.assertEqual(total, 840)
        rotate = StyleSession().plan(sample(), Settings('big-jewels', rotate=True))
        self.assertEqual(Image.open(io.BytesIO(bridge.encode_presentation(rotate)[1])).info['loop'], 0)

    def test_transient_upload_always_settles_to_png(self):
        async def check():
            for results in ([True, True], [False, True], [True, False]):
                with patch.object(bridge, 'send', AsyncMock(side_effect=results)) as send, \
                     patch.object(bridge.asyncio, 'sleep', AsyncMock()) as sleep:
                    self.assertEqual(await bridge.send_presentation('fake', self.plan()), results[1])
                    self.assertEqual([c.args[1] for c in send.call_args_list], ['gif', 'png'])
                    if results[0]:
                        sleep.assert_awaited_once_with(.84)
            with patch.object(bridge, 'send', AsyncMock(side_effect=[RuntimeError('failed'), True])) as send:
                with self.assertRaises(RuntimeError):
                    await bridge.send_presentation('fake', self.plan())
                self.assertEqual(send.call_args_list[-1].args[1], 'png')
        asyncio.run(check())

    def test_hub_status_and_default_legacy(self):
        hub = bridge.Hub('http://unused.invalid', '')
        hub.data = {'services': [{'name': 'Claude', 'age_seconds': 200, 'meters': [
            {'label': '5-hour', 'left': 65}, {'label': 'Weekly', 'left': 23}]}]}
        hub.ok = True
        plan = hub.presentation(Settings('baby-mochi'))
        self.assertEqual(plan.frames[0].getpixel((31, 0)), (255, 175, 0))
        hub.ok = False
        self.assertEqual(hub.presentation(Settings('baby-mochi')).frames[0].getpixel((31, 0)), (255, 40, 30))
        # The pre-existing battery renderer is still the no-selection default.
        self.assertEqual(hub.presentation(Settings()).frames[0].tobytes(), hub.frames()[0].tobytes())

    def test_running_loop_reloads_selector_without_replaying_unchanged_animation(self):
        class StopDemo(Exception):
            pass
        async def check(path):
            reads, sleeps = 0, 0
            def fetch(hub):
                nonlocal reads
                reads += 1
                hub.ok = True
                hub.data = {'services': [{'name': 'Claude', 'age_seconds': 0, 'meters': [
                    {'label': '5-hour', 'left': 100 if reads == 1 else 72},
                    {'label': 'Weekly', 'left': 89}]}]}
            async def sleep(seconds):
                nonlocal sleeps
                sleeps += 1
                if sleeps == 3:
                    save_settings(path, Settings('spectrum'))
                if sleeps == 4:
                    raise StopDemo()
            args = SimpleNamespace(address='fake', hub='http://unused.invalid', key='',
                                   all=False, claude=False, style=None, style_config=str(path),
                                   seconds=10, once=False)
            with patch.object(bridge, 'load_config', return_value={}), \
                 patch.object(bridge.Hub, 'fetch', fetch), \
                 patch.object(bridge, 'send_presentation', AsyncMock(return_value=True)) as send, \
                 patch.object(bridge.asyncio, 'sleep', sleep), patch.object(bridge, 'log'):
                with self.assertRaises(StopDemo):
                    await bridge.run(args)
                # Initial still, changed reading, then new style. No upload on unchanged third fetch.
                self.assertEqual(send.await_count, 3)
                plans = [call.args[1] for call in send.call_args_list]
                self.assertIsNone(plans[0].settle)
                self.assertIsNotNone(plans[1].settle)
                self.assertIsNone(plans[2].settle)
                self.assertNotEqual(plans[2].frames[0].tobytes(), plans[1].settle.tobytes())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'style.json'
            save_settings(path, Settings('baby-mochi'))
            asyncio.run(check(path))


if __name__ == '__main__':
    unittest.main()
