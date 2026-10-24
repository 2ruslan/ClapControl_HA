import json
from pathlib import Path
import tempfile
import unittest
from clap_control.settings import Settings, load_settings


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def write(self, name, value):
        (self.directory / name).write_text(json.dumps(value), encoding='utf-8')

    def test_fresh_install_persists_defaults(self):
        self.assertEqual(load_settings(self.directory), Settings())
        self.assertEqual(json.loads((self.directory/'settings.json').read_text())['version'], 2)

    def test_legacy_supervisor_only_imported_once(self):
        values = Settings(sensitivity=78, scenes=['scene.b','scene.a'], test_mode=True).to_dict()
        self.write('options.json', values)
        self.assertEqual(load_settings(self.directory).to_dict(), values)
        self.write('options.json', {})
        self.assertEqual(load_settings(self.directory).to_dict(), values)

    def test_legacy_ingress_preserved(self):
        baseline = Settings().to_dict()
        values = Settings(clap_count=3, scenes=['scene.b','scene.a']).to_dict()
        self.write('options.json', baseline)
        self.write('settings.json', {'supervisor_options': baseline, 'settings': values})
        self.assertEqual(load_settings(self.directory).to_dict(), values)

    def test_legacy_ingress_preserved_with_empty_options(self):
        values = Settings(sensitivity=90).to_dict()
        self.write('options.json', {})
        self.write('settings.json', {'supervisor_options': Settings().to_dict(), 'settings': values})
        self.assertEqual(load_settings(self.directory).to_dict(), values)

    def test_legacy_pending_supervisor_change_imported(self):
        self.write('options.json', Settings(sensitivity=30).to_dict())
        self.write('settings.json', {'supervisor_options': Settings().to_dict(),
                                     'settings': Settings(sensitivity=70).to_dict()})
        self.assertEqual(load_settings(self.directory).sensitivity, 30)
        self.write('options.json', Settings(sensitivity=20).to_dict())
        self.assertEqual(load_settings(self.directory).sensitivity, 30)

    def test_corrupt_saved_file_not_replaced(self):
        path = self.directory/'settings.json'
        path.write_text('{broken')
        with self.assertRaises(ValueError):
            load_settings(self.directory)
        self.assertEqual(path.read_text(), '{broken')

    def test_supervisor_log_level_does_not_replace_detector_settings(self):
        values = Settings(sensitivity=85, scenes=['scene.a'], log_level='ERROR').to_dict()
        self.write('settings.json', {'version':2, 'settings':values})
        self.write('options.json', {'log_level':'DEBUG'})
        loaded = load_settings(self.directory)
        self.assertEqual(loaded.log_level, 'DEBUG')
        self.assertEqual(loaded.sensitivity, 85)
        self.assertEqual(loaded.scenes, ['scene.a'])

    def test_old_ingress_preserved_with_logging_only_options(self):
        values = Settings(sensitivity=85).to_dict()
        self.write('settings.json', {'supervisor_options':Settings().to_dict(), 'settings':values})
        self.write('options.json', {'log_level':'DEBUG'})
        self.assertEqual(load_settings(self.directory).sensitivity, 85)
