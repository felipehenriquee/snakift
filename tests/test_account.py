import os
import tempfile
import unittest

from cobra import account, config, profile, rank, records
from cobra.live import Tribute


class AccountResetTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.paths = [os.path.join(self.dir.name, f) for f in ('recordes.json', 'ranque.json', 'perfil.json')]
        rec_path, rank_path, prof_path = self.paths
        arena = config.ARENAS[0]
        data = records.load(rec_path)
        data['tabelas'][(arena, 'ferro')] = [{'nome': 'Ana', 'pontos': 500}]
        data['ultimo_nome'] = 'Ana'
        records.add_supporters(data, [Tribute('fulano', 'Fulano', None, 300)])
        records.save(rec_path, data)
        rank.save(rank_path, {a: rank.Rank(3, 2, 40) for a in config.ARENAS})
        prof = profile.load(prof_path)
        profile.record_match(prof, arena, 900, 4, 120.0, True, rank.Rank(3, 2, 40), xp=150)
        profile.save(prof_path, prof)

    def tearDown(self):
        self.dir.cleanup()

    def test_reset_erases_what_was_played(self):
        account.reset(*self.paths)
        rec_path, rank_path, prof_path = self.paths
        self.assertEqual(records.load(rec_path)['tabelas'], {})
        self.assertEqual(rank.load(rank_path), {a: rank.START for a in config.ARENAS})
        self.assertEqual(profile.load(prof_path), {'arenas': {a: profile.empty_stats() for a in config.ARENAS}})

    def test_reset_keeps_the_gifters_and_the_name(self):
        account.reset(*self.paths)
        data = records.load(self.paths[0])
        self.assertEqual(data['ultimo_nome'], 'Ana')
        self.assertEqual([(s['usuario'], s['moedas']) for s in data['doadores']], [('fulano', 300)])


if __name__ == '__main__':
    unittest.main()
