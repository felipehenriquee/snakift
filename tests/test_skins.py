import unittest

from cobra import config, profile, skins
from cobra.rank import Rank

FERRO, BRONZE, PRATA, OURO, PLATINA = 0, 1, 2, 3, 4
ALL = ('classica', 'ferro', 'bronze', 'prata', 'ouro')


class TestSkins(unittest.TestCase):
    def setUp(self):                    # as regras do elo, sem as skins liberadas para teste
        self.saved = config.SKINS_LIBERADAS
        config.SKINS_LIBERADAS = set()

    def tearDown(self):
        config.SKINS_LIBERADAS = self.saved

    def test_test_unlocked_skins_skip_the_league(self):
        config.SKINS_LIBERADAS = {'mestre'}
        self.assertTrue(skins.is_unlocked('mestre', FERRO))
        self.assertFalse(skins.is_unlocked('diamante', FERRO))

    def test_classic_and_iron_start_unlocked(self):
        self.assertTrue(skins.is_unlocked('classica', FERRO))
        self.assertTrue(skins.is_unlocked('ferro', FERRO))
        self.assertFalse(skins.is_unlocked('bronze', FERRO))

    def test_each_metal_skin_needs_its_league(self):
        self.assertTrue(skins.is_unlocked('prata', PRATA))
        self.assertFalse(skins.is_unlocked('ouro', PRATA))
        self.assertTrue(skins.is_unlocked('ouro', PLATINA))

    def test_best_tier_uses_any_arena_peak_and_current_rank(self):
        data = {'arenas': {n: profile.empty_stats() for n in (11, 15, 18)}}
        data['arenas'][15]['pico'] = Rank(PRATA, 2, 0)
        ranks = {11: Rank(BRONZE, 3, 10), 15: Rank(BRONZE, 4, 0), 18: Rank(FERRO, 4, 0)}
        self.assertEqual(skins.best_tier(data, ranks), PRATA)
        self.assertEqual(skins.best_tier(None, {11: Rank(OURO, 4, 0)}), OURO)
        self.assertEqual(skins.best_tier(), FERRO)

    def test_newly_unlocked_when_reaching_a_league(self):
        self.assertEqual(skins.newly_unlocked(ALL, FERRO, BRONZE), ['bronze'])
        self.assertEqual(skins.newly_unlocked(ALL, BRONZE, BRONZE), [])
        self.assertEqual(skins.newly_unlocked(ALL, BRONZE, OURO), ['prata', 'ouro'])     # equipa a última
        self.assertEqual(skins.newly_unlocked(ALL, OURO, PLATINA), [])

    def test_emerald_skin_needs_emerald_league(self):
        ESMERALDA = 5
        self.assertFalse(skins.is_unlocked('esmeralda', PLATINA))
        self.assertTrue(skins.is_unlocked('esmeralda', ESMERALDA))
        self.assertEqual(skins.newly_unlocked(ALL + ('platina', 'esmeralda'), PLATINA, ESMERALDA), ['esmeralda'])

    def test_diamond_skin_needs_diamond_league(self):
        ESMERALDA, DIAMANTE = 5, 6
        self.assertFalse(skins.is_unlocked('diamante', ESMERALDA))
        self.assertTrue(skins.is_unlocked('diamante', DIAMANTE))

    def test_master_skin_needs_master_league(self):
        DIAMANTE, MESTRE = 6, 7
        self.assertFalse(skins.is_unlocked('mestre', DIAMANTE))
        self.assertTrue(skins.is_unlocked('mestre', MESTRE))


if __name__ == '__main__':
    unittest.main()
