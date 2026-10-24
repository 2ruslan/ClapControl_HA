import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from clap_control.state import State, atomic_json


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'state.json'

    def test_restart(self):
        state = State(self.path)
        state.commit(['scene.a','scene.b','scene.c'], 1, 'now')
        self.assertEqual(State(self.path).next_index(['scene.a','scene.b','scene.c']), 2)

    def test_atomic_failure_leaves_previous(self):
        atomic_json(self.path, {'a':1})
        with patch('clap_control.state.os.replace', side_effect=OSError('disk')):
            with self.assertRaises(OSError):
                atomic_json(self.path, {'a':2})
        self.assertEqual(json.loads(self.path.read_text()), {'a':1})
        self.assertEqual(len(list(self.path.parent.iterdir())),1)

    def test_reordered_or_removed_scene(self):
        state=State(self.path)
        state.commit(['scene.a','scene.b'], 0, 'now')
        self.assertEqual(state.next_index(['scene.b','scene.a','scene.c']), 2)
        self.assertEqual(state.next_index(['scene.b']), 0)

    def test_corrupt_state_not_overwritten(self):
        self.path.write_text('{broken')
        with self.assertRaises(ValueError):
            State(self.path)
        self.assertEqual(self.path.read_text(),'{broken')
