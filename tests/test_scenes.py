from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from clap_control.scenes import SceneCycle, APIError, HomeAssistant
from clap_control.settings import Settings
from clap_control.state import State


class SceneTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.api=Mock()
        self.state=State(Path(self.temp.name)/'state.json')
        self.cycle=SceneCycle(self.api,self.state)

    def test_cycles(self):
        for count in (1,2,3,17):
            with self.subTest(count=count):
                scenes=[f'scene.s{i}' for i in range(count)]
                state=State(Path(self.temp.name)/f'{count}.json')
                cycle=SceneCycle(self.api,state)
                actual=[cycle.trigger(Settings(scenes=scenes))['scene'] for _ in range(count*2)]
                self.assertEqual(actual,scenes*2)

    def test_unavailable_does_not_advance(self):
        settings=Settings(scenes=['scene.a','scene.b'])
        self.cycle.trigger(settings)
        self.api.activate.side_effect=APIError('unavailable')
        with self.assertRaises(APIError):
            self.cycle.trigger(settings)
        self.assertEqual(self.state.value['index'],0)
        self.assertEqual(State(self.state.path).value['index'],0)
        self.api.activate.side_effect=None
        self.assertEqual(self.cycle.trigger(settings)['scene'],'scene.b')

    def test_test_disabled_and_empty(self):
        for settings in (Settings(test_mode=True,scenes=['scene.a']),
                         Settings(enabled=False,scenes=['scene.a']),Settings()):
            self.assertIsNone(self.cycle.trigger(settings))
        self.api.activate.assert_not_called()

    def test_storage_failure_blocks_more_actions(self):
        with patch.object(self.state,'commit',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.cycle.trigger(Settings(scenes=['scene.a']))
        with self.assertRaises(APIError):
            self.cycle.trigger(Settings(scenes=['scene.a']))
        self.assertEqual(self.api.activate.call_count,1)

    def test_unknown_scene_state_is_valid(self):
        api=HomeAssistant('secret')
        api.request=Mock(return_value={'state':'unknown'})
        api.activate('scene.a')
        self.assertEqual(api.request.call_count,2)

    def test_unavailable_api_state(self):
        api=HomeAssistant('secret')
        api.request=Mock(return_value={'state':'unavailable'})
        with self.assertRaises(APIError): api.activate('scene.a')
        self.assertEqual(api.request.call_count,1)

    def test_network_loss_sanitized(self):
        api=HomeAssistant('secret')
        api.opener.open=Mock(side_effect=TimeoutError('secret'))
        with self.assertRaises(APIError) as caught: api.activate('scene.a')
        self.assertNotIn('secret',str(caught.exception))
