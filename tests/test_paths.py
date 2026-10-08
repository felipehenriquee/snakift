import importlib.util
import json
import os
import unittest

from cobra import config
from cobra.manifest import SPRITES_DIR


class TestPaths(unittest.TestCase):
    """As pastas de assets/ existem e cada skin tem o seu retrato (para não quebrar ao mudar as pastas)."""

    def test_asset_folders_exist(self):
        for folder in (SPRITES_DIR, config.UI_DIR, config.FONT_DIR, config.AUDIO_DIR):
            self.assertTrue(os.path.isdir(folder), folder)

    def test_every_skin_has_a_portrait(self):
        with open(os.path.join(SPRITES_DIR, 'manifest.json'), encoding='utf-8') as f:
            names = json.load(f)['skins']['lista']
        for name in names:
            path = os.path.join(SPRITES_DIR, 'avatares', f"{'classico' if name == 'classica' else name}.png")
            self.assertTrue(os.path.exists(path), path)

    @unittest.skipUnless(importlib.util.find_spec('pygame'), 'sem pygame')
    def test_menu_finds_the_portraits(self):
        from cobra import menu
        self.assertTrue(os.path.exists(menu.ASSETS['avatar'].format(nome='mestre')))
        self.assertTrue(os.path.exists(menu.ASSETS['cabeca'].format(pasta='skins/mestre')))


if __name__ == '__main__':
    unittest.main()
