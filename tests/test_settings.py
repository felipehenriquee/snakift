import json
import os
import tempfile
import unittest

from cobra import settings


class TestVolumes(unittest.TestCase):
    def _load(self, data):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'configuracoes.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
            return settings.load(path)

    def test_volumes_start_at_max(self):
        prefs = self._load({})
        for key in settings.VOLUMES.values():
            self.assertEqual(prefs[key], settings.VOLUME_MAX)

    def test_old_on_off_options_become_volume(self):
        prefs = self._load({'musica': False, 'efeitos': True})
        self.assertEqual(prefs['volume_musica'], 0)
        self.assertEqual(prefs['volume_efeitos'], settings.VOLUME_MAX)

    def test_saved_volumes_are_kept_and_clamped(self):
        prefs = self._load({'volume': 4, 'volume_musica': 99, 'volume_efeitos': -3})
        self.assertEqual((prefs['volume'], prefs['volume_musica'], prefs['volume_efeitos']), (4, 10, 0))

    def test_minus_and_plus_buttons(self):
        prefs = {'volume': 10, 'volume_musica': 0}
        self.assertTrue(settings.volume_action(prefs, 'vol_geral_down'))
        self.assertTrue(settings.volume_action(prefs, 'vol_geral_up'))
        self.assertTrue(settings.volume_action(prefs, 'vol_geral_up'))     # não passa de 100%
        self.assertTrue(settings.volume_action(prefs, 'vol_musica_down'))  # nem de 0%
        self.assertTrue(settings.volume_action(prefs, 'vol_efeitos_down'))
        self.assertEqual(prefs, {'volume': 10, 'volume_musica': 0, 'volume_efeitos': 9})
        self.assertFalse(settings.volume_action(prefs, 'resume'))
        self.assertFalse(settings.volume_action(prefs, None))


class TestPlayerName(unittest.TestCase):
    def test_live_mode_uses_the_at(self):
        self.assertEqual(settings.player_name({'modo': 'live', 'tiktok': 'felipe'}, 'Felipe'), '@felipe')
        self.assertEqual(settings.player_name({'modo': 'live', 'tiktok': '@felipe'}, 'Felipe'), '@felipe')

    def test_offline_or_without_at_uses_saved_name(self):
        self.assertEqual(settings.player_name({'modo': 'offline', 'tiktok': 'felipe'}, 'Felipe'), 'Felipe')
        self.assertEqual(settings.player_name({'modo': 'live', 'tiktok': ''}, 'Felipe'), 'Felipe')


if __name__ == '__main__':
    unittest.main()
