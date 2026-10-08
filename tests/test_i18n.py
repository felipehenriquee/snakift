import os
import re
import tempfile
import unittest
from unittest import mock

from cobra import i18n, settings


class TestTranslations(unittest.TestCase):
    def tearDown(self):
        i18n.set_language(i18n.DEFAULT)

    def test_every_language_has_every_key_with_same_placeholders(self):
        keys = set(i18n.STRINGS[i18n.DEFAULT])
        for lang in i18n.LANGUAGES:
            self.assertEqual(set(i18n.STRINGS[lang]), keys, lang)
            for k in keys:
                fields = lambda s: sorted(re.findall(r'{(\w+)}', s))
                self.assertEqual(fields(i18n.STRINGS[lang][k]), fields(i18n.STRINGS[i18n.DEFAULT][k]), (lang, k))

    def test_switch_language(self):
        i18n.set_language('en')
        self.assertEqual(i18n.t('menu.play'), 'PLAY')
        self.assertEqual(i18n.t('over.rank', n=3), '#3 in the high scores!')
        i18n.set_language('pt')
        self.assertEqual(i18n.t('over.rank', n=3), '3º lugar nos recordes!')

    def test_unknown_language_and_key(self):
        i18n.set_language('xx')
        self.assertEqual(i18n.language(), i18n.DEFAULT)
        self.assertEqual(i18n.t('nao.existe'), 'nao.existe')

    def test_next_language_cycles(self):
        self.assertEqual(i18n.next_language('pt'), 'en')
        self.assertEqual(i18n.next_language('en'), 'pt')

    def test_detect_language_from_environment(self):
        with mock.patch.dict(os.environ, {'LANGUAGE': '', 'LC_ALL': '', 'LC_MESSAGES': '', 'LANG': 'pt_BR.UTF-8'}):
            self.assertEqual(i18n.detect_language(), 'pt')
        with mock.patch.dict(os.environ, {'LANGUAGE': '', 'LC_ALL': '', 'LC_MESSAGES': '', 'LANG': 'en_US.UTF-8'}):
            self.assertEqual(i18n.detect_language(), 'en')


class TestSettings(unittest.TestCase):
    def test_save_and_load_language(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'configuracoes.json')
            settings.save(path, {'idioma': 'en'})
            self.assertEqual(settings.load(path)['idioma'], 'en')

    def test_arena_is_saved_and_validated(self):
        from cobra import config
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'configuracoes.json')
            self.assertEqual(settings.load(path)['arena'], config.N)
            settings.save(path, {'idioma': 'pt', 'arena': 18})
            self.assertEqual(settings.load(path)['arena'], 18)
            settings.save(path, {'idioma': 'pt', 'arena': 13})        # tamanho que não existe
            self.assertEqual(settings.load(path)['arena'], config.N)

    def test_theme_change_options_default_on_and_are_saved(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'configuracoes.json')
            prefs = settings.load(path)
            self.assertEqual((prefs['cenario_muda'], prefs['cobra_muda'], prefs['skin']), (True, True, 'classica'))
            prefs.update(cenario_muda=False, skin='ferro')
            settings.save(path, prefs)
            again = settings.load(path)
            self.assertEqual((again['cenario_muda'], again['cobra_muda'], again['skin']), (False, True, 'ferro'))

    def test_missing_or_bad_file_uses_system_language(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'configuracoes.json')
            with mock.patch.object(i18n, 'detect_language', return_value='en'):
                self.assertEqual(settings.load(path)['idioma'], 'en')
                settings.save(path, {'idioma': 'klingon'})
                self.assertEqual(settings.load(path)['idioma'], 'en')


if __name__ == '__main__':
    unittest.main()
