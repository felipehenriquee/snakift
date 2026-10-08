import os
import tempfile
import unittest

from cobra import config, rank
from cobra.rank import Rank, START

FERRO, BRONZE, PRATA, DIAMANTE, MESTRE = 0, 1, 2, 6, 7


def T(tier=0, arena=11, division=4):
    """Meta da liga (calculada pelo jogo); os testes usam porcentagens dela."""
    return rank.target(Rank(tier, division, 0), arena)


class TestTargets(unittest.TestCase):
    def test_targets_grow_with_the_league_and_are_rounded(self):
        for arena in config.ARENAS:
            targets = [T(i, arena) for i in range(8)]
            self.assertEqual(targets, sorted(set(targets)))
            for t in targets:
                self.assertEqual(t % (50 if t >= 1000 else 10), 0)

    def test_bigger_arenas_ask_for_more(self):
        for i in range(8):
            self.assertLess(T(i, 11), T(i, 15))
            self.assertLess(T(i, 15), T(i, 18))


class TestMatches(unittest.TestCase):
    def test_win_formula_from_the_example(self):
        # 20% acima da meta, 10 presentes, 2 minutos: 25 + 20 + 2 x 10
        out = rank.apply_match(START, T() + T() // 5, 10, 11, play_time=120)
        self.assertTrue(out.won)
        self.assertEqual((out.base, out.margin, out.time_bonus, out.delta), (25, 20, 20, 65))
        self.assertEqual(out.after, Rank(FERRO, 4, 65))

    def test_margin_is_the_percentage_above_the_target(self):
        t = T(0, 18)                                                # Ferro no 18x18
        out = rank.apply_match(START, t + t * 154 // 100, 0, 18)    # 154% acima -> +154 PDL
        self.assertEqual((out.target, out.margin, out.delta), (t, 154, 25 + 154))
        self.assertEqual(out.after, Rank(FERRO, 3, 79))             # sobe uma divisão e sobram 79

    def test_reaching_the_target_exactly_wins(self):
        self.assertTrue(rank.apply_match(START, T(), 0, 11).won)
        self.assertFalse(rank.apply_match(START, T() - 1, 30, 11).won)

    def test_loss_costs_base_plus_missing_percentage_minus_time_gifts(self):
        # faltaram 20%, 5 presentes em 1 minuto: -(25 + 20) + 5
        out = rank.apply_match(Rank(FERRO, 3, 80), T() - T() // 5, 5, 11, play_time=60)
        self.assertFalse(out.won)
        self.assertEqual((out.base, out.margin, out.time_bonus, out.delta), (-25, -20, 5, -40))
        self.assertEqual(out.after, Rank(FERRO, 3, 40))

    def test_missing_percentage_is_at_most_100(self):
        out = rank.apply_match(Rank(FERRO, 3, 80), 0, 0, 18)
        self.assertEqual((out.margin, out.delta), (-100, -125))

    def test_a_loss_with_positive_total_gives_the_pdl(self):
        # faltaram 10%, mas 3 min x 20 presentes = +60: -(25 + 10) + 60 = +25, mesmo sem bater a meta
        out = rank.apply_match(Rank(FERRO, 3, 40), T() - T() // 10, 20, 11, play_time=180)
        self.assertFalse(out.won)
        self.assertEqual(out.delta, 25)
        self.assertEqual(out.after, Rank(FERRO, 3, 65))

    def test_loss_with_pdl_stops_at_zero(self):
        out = rank.apply_match(Rank(BRONZE, 2, 10), T(1) - T(1) // 10, 0, 11)     # perde 25 + 10% com 10 PDL
        self.assertEqual(out.after, Rank(BRONZE, 2, 0))
        self.assertEqual([s.event for s in out.steps], [None])

    def test_only_a_loss_at_zero_drops_a_division(self):
        out = rank.apply_match(Rank(BRONZE, 2, 0), T(1) - T(1) // 10, 0, 11)      # perde 25 + 10% = 35
        self.assertEqual(out.after, Rank(BRONZE, 3, 65))
        self.assertEqual([s.event for s in out.steps], ['cai', None])

    def test_big_loss_at_zero_lands_on_zero(self):
        out = rank.apply_match(Rank(BRONZE, 2, 0), 0, 0, 11)                       # perde 25 + 100%
        self.assertEqual(out.after, Rank(BRONZE, 3, 0))

    def test_never_drops_out_of_a_league(self):
        self.assertEqual(rank.apply_match(Rank(BRONZE, 4, 0), 0, 0, 11).after, Rank(BRONZE, 4, 0))
        self.assertEqual(rank.apply_match(Rank(FERRO, 4, 0), 0, 0, 11).after, Rank(FERRO, 4, 0))
        self.assertEqual(rank.apply_match(Rank(MESTRE, 0, 0), 0, 0, 11).after, Rank(MESTRE, 0, 0))

    def test_promotion_carries_extra_pdl(self):
        out = rank.apply_match(Rank(FERRO, 4, 90), T() + T() * 2 // 5, 5, 11)    # 25 + 40% = 65
        self.assertEqual(out.after, Rank(FERRO, 3, 55))
        self.assertEqual([s.event for s in out.steps], ['sobe', None])

    def test_league_up_from_iron_i_to_bronze_iv(self):
        out = rank.apply_match(Rank(FERRO, 1, 95), T(0, 11, 1) + T(0, 11, 1) // 10, 0, 11)
        self.assertEqual(out.after, Rank(BRONZE, 4, 30))      # 95 + 25 + 10% acima da meta

    def test_master_accumulates(self):
        out = rank.apply_match(Rank(MESTRE, 0, 95), T(MESTRE, 11, 0), 0, 11)
        self.assertEqual(out.after, Rank(MESTRE, 0, 105))

    def test_diamond_i_goes_to_master(self):
        out = rank.apply_match(Rank(DIAMANTE, 1, 95), T(DIAMANTE, 11, 1), 0, 11)
        self.assertEqual(out.after, Rank(MESTRE, 0, 5))

    def test_each_bomb_costs_one_pdl(self):
        win = rank.apply_match(START, T(), 0, 11, bombs=3)
        self.assertEqual(win.delta, 25 - 3)
        loss = rank.apply_match(Rank(FERRO, 3, 60), T() - T() // 10, 0, 11, bombs=2)
        self.assertEqual(loss.delta, -25 - 10 - 2)                 # faltaram 10%

    def test_record_bonus_by_position(self):
        self.assertEqual([rank.record_bonus(p) for p in range(5)], [10, 8, 6, 4, 2])
        self.assertEqual(rank.record_bonus(None), 0)
        self.assertEqual(rank.apply_match(START, T(), 0, 11, record_pos=0).delta, 25 + 10)

    def test_steps_animate_from_old_to_new_pdl(self):
        out = rank.apply_match(Rank(FERRO, 4, 90), T() + T() * 2 // 5, 5, 11)
        self.assertEqual([(s.pdl_from, s.pdl_to) for s in out.steps], [(90, 100), (0, 55)])


class TestStorage(unittest.TestCase):
    def test_each_arena_has_its_own_rank(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'ranque.json')
            ranks = rank.load(path)
            self.assertEqual(set(ranks), set(config.ARENAS))
            self.assertTrue(all(r == START for r in ranks.values()))
            ranks[15] = Rank(PRATA, 2, 40)
            rank.save(path, ranks)
            again = rank.load(path)
            self.assertEqual(again[15], Rank(PRATA, 2, 40))
            self.assertEqual(again[11], START)

    def test_broken_entries_start_over(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'ranque.json')
            with open(path, 'w') as f:
                f.write('{"11": {"liga": "madeira", "divisao": 2, "pdl": 5}, "15": "x"}')
            ranks = rank.load(path)
            self.assertEqual((ranks[11], ranks[15]), (START, START))


if __name__ == '__main__':
    unittest.main()
