import os
import tempfile
import unittest

from cobra import config, profile, rank
from cobra.rank import Rank


class TestProfile(unittest.TestCase):
    def test_starts_empty_for_every_arena(self):
        with tempfile.TemporaryDirectory() as d:
            data = profile.load(os.path.join(d, 'perfil.json'))
            self.assertEqual(set(data['arenas']), set(config.ARENAS))
            self.assertEqual(profile.level(data), (1, 0, profile.XP_PER_LEVEL))
            self.assertEqual(profile.win_rate(data['arenas'][11]), 0)

    def test_matches_add_up_per_arena(self):
        data = profile.load('/caminho/que/nao/existe.json')
        profile.record_match(data, 11, 180, 12, 65.0, True, Rank(0, 3, 10), xp=300)
        profile.record_match(data, 11, 90, 5, 30.0, False, Rank(0, 3, 0), xp=50)
        profile.record_match(data, 15, 300, 20, 120.0, True, Rank(1, 4, 0), xp=220)
        s11 = data['arenas'][11]
        self.assertEqual((s11['partidas'], s11['vitorias'], s11['derrotas']), (2, 1, 1))
        self.assertEqual((s11['presentes'], s11['pontos'], s11['melhor']), (17, 270, 180))
        self.assertEqual(profile.win_rate(s11), 50)
        tot = profile.totals(data)
        self.assertEqual((tot['partidas'], tot['pontos'], tot['melhor']), (3, 570, 300))
        self.assertEqual(tot['xp'], 570)
        self.assertEqual(profile.level(data), (2, 70, 500))

    def test_peak_only_goes_up(self):
        data = profile.load('/nada.json')
        profile.record_match(data, 11, 0, 0, 1, True, Rank(2, 2, 30))     # Prata II
        profile.record_match(data, 11, 0, 0, 1, False, Rank(2, 3, 80))    # caiu para Prata III
        self.assertEqual(data['arenas'][11]['pico'], Rank(2, 2, 0))
        profile.record_match(data, 11, 0, 0, 1, True, Rank(3, 4, 5))      # Ouro IV
        self.assertEqual(data['arenas'][11]['pico'], Rank(3, 4, 0))

    def test_rank_order(self):
        seq = [Rank(0, 4, 0), Rank(0, 3, 0), Rank(0, 1, 0), Rank(1, 4, 0), Rank(6, 1, 0), Rank(7, 0, 0)]
        self.assertEqual([rank.order(r) for r in seq], sorted(rank.order(r) for r in seq))
        self.assertEqual(len({rank.order(r) for r in seq}), len(seq))

    def test_old_profile_keeps_its_level(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'perfil.json')
            with open(path, 'w') as f:                  # arquivo de antes do XP: o nível vinha dos pontos
                json.dump({'arenas': {'11': {'partidas': 4, 'pontos': 1200}}}, f)
            data = profile.load(path)
            self.assertEqual(data['arenas'][11]['xp'], 1200)
            self.assertEqual(profile.level(data)[0], 3)

    def test_match_xp_uses_whole_points_and_never_is_negative(self):
        t = rank.target(Rank(0, 4, 0), 11)
        # 120% da meta, 10 presentes, 2 minutos, Ferro: 25 + 120 + 2 x 10
        self.assertEqual(rank.match_xp(Rank(0, 4, 0), t + t // 5, 10, 11, 120), 165)
        lost = rank.apply_match(Rank(0, 3, 50), t - t * 3 // 10, 4, 11, play_time=90)
        self.assertFalse(lost.won)
        self.assertEqual(lost.xp, 25 + 70 + 6)                # 70% da meta: perdeu PDL, mas ganhou XP
        self.assertEqual(rank.match_xp(Rank(0, 4, 0), 0, 0, 11, 0, bombs=40), 0)

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'perfil.json')
            data = profile.load(path)
            profile.record_match(data, 18, 400, 25, 200.5, True, Rank(3, 2, 40))
            profile.save(path, data)
            again = profile.load(path)
            self.assertEqual(again['arenas'][18]['pontos'], 400)
            self.assertEqual(again['arenas'][18]['pico'], Rank(3, 2, 0))
            self.assertEqual(again['arenas'][11]['partidas'], 0)


if __name__ == '__main__':
    unittest.main()
