import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock
from clap_control.main import Application
from clap_control.settings import Settings,load_settings
from clap_control.scenes import APIError
from test_detector import signal,pcm


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)
        self.api=Mock()
        self.api.scenes.return_value=[{'entity_id':'scene.a'},{'entity_id':'scene.b'}]
        self.app=Application(self.directory,self.api)

    def test_settings_survive_and_supervisor_override(self):
        values=Settings(sensitivity=70,test_mode=True,scenes=['scene.a']).to_dict()
        self.app.save_settings(values)
        self.assertEqual(load_settings(self.directory)[0].sensitivity,70)
        (self.directory/'options.json').write_text(json.dumps({'sensitivity':30}))
        self.assertEqual(load_settings(self.directory)[0].sensitivity,30)

    def test_validation(self):
        for values in ({'clap_count':4},{'enabled':1},{'scenes':['light.a']},
                       {'cooldown_seconds':float('nan')},{'sensitivity':True},{'unknown':1}):
            with self.subTest(values=values),self.assertRaises(ValueError):Settings.parse(values)

    def test_missing_scene_rejected(self):
        with self.assertRaises(ValueError):self.app.save_settings(Settings(scenes=['scene.missing']).to_dict())

    def test_old_generation_dropped(self):
        self.app.settings=Settings(scenes=['scene.a'])
        self.app.activate(-1,time.monotonic())
        self.app.activate(0,time.monotonic()-10)
        self.api.activate.assert_not_called()

    def test_event_failure_keeps_committed_position(self):
        self.app.settings=Settings(scenes=['scene.a','scene.b'])
        self.api.request.side_effect=APIError('offline')
        self.app.activate(0,time.monotonic())
        self.assertEqual(self.app.state.value['index'],0)
        self.assertEqual(self.app.status()['activations'],1)
        self.assertEqual(self.app.status()['event_error'],'offline')
        self.app.activate(0,time.monotonic())
        self.assertEqual(self.app.state.value['index'],1)

    def test_real_pcm_to_sequence_test_mode(self):
        self.app.settings=Settings(test_mode=True)
        x=signal([(1,.3),(1.5,.3),(2,.3),(2.5,.3)],seconds=4)
        for i in range(0,len(x),160):self.app.on_frame(pcm(x[i:i+160]),i/16000)
        self.assertEqual(self.app.status()['sequences'],1)
        self.assertTrue(self.app.triggers.empty())
        self.api.activate.assert_not_called()

    def test_audio_disconnect_resets_sequence(self):
        x=signal([(1,.3)])
        for i in range(0,19200,160):self.app.on_frame(pcm(x[i:i+160]),i/16000)
        self.assertEqual(self.app.sequence.pending,1)
        self.app.on_audio_status('error','disconnected')
        self.app.on_frame(bytes(320),1.3)
        self.assertEqual(self.app.sequence.pending,0)
