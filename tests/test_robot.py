import random
import unittest

from cobra import robot
from cobra.logic import Bomb, GameState
from cobra.result import Result

FOOD_TO_THEME = {'rosa': 'rosa', 'rosquinha': 'rosquinha', 'esquilo': 'esquilo', 'caracol': 'caracol', 'maca': 'classico'}


class TestAutopilot(unittest.TestCase):
    def test_robot_plays_alone_and_eats(self):
        s = GameState(FOOD_TO_THEME, rng=random.Random(1))
        s.controller = robot.choose
        for _ in range(600):                    # 600 passos sem ninguém apertar nada
            s.step()
            if s.over:
                break
        self.assertFalse(s.dead)
        self.assertGreater(len(s.snake), 10)
        self.assertTrue(s.practice)

    def test_robot_fills_the_whole_arena(self):
        for n in (6, 7):                                # par (ciclo por todas as casas) e ímpar (canto fora)
            for seed in range(5):
                s = GameState(FOOD_TO_THEME, n=n, rng=random.Random(seed))
                s.controller = robot.choose
                steps = 0
                while not s.over and steps < 20000:
                    s.step()
                    steps += 1
                self.assertTrue(s.won, (n, seed, len(s.snake)))
                self.assertEqual(len(s.snake), n * n)

    def test_cycle_covers_the_arena(self):
        for n in (11, 15, 18):
            for seed in range(10):                              # um labirinto sorteado por partida
                cells, order, skip = robot.cycle(n, seed)
                self.assertEqual(len(set(cells)), n * n - (1 if n % 2 else 0))
                for a, b in zip(cells, cells[1:] + cells[:1]):  # cada casa vizinha da próxima, e fecha
                    self.assertEqual(abs(a[0] - b[0]) + abs(a[1] - b[1]), 1)

    def test_each_match_draws_a_different_path(self):
        seen = set()
        for seed in range(10):
            s = GameState(FOOD_TO_THEME, n=11, rng=random.Random(seed))
            seen.add(tuple(robot._game_cycle(s)[0]))
        self.assertGreater(len(seen), 8)

    def test_live_robot_still_avoids_bombs_when_it_can(self):
        s = GameState(FOOD_TO_THEME, rng=random.Random(1), bomb_theme='queimado')
        head = s.snake[0]
        s.snake = [head, (head[0] - 1, head[1]), (head[0] - 2, head[1])]      # cobra virada para a direita
        s.dir = 'E'
        s.food = (head[0] + 2, head[1])                                       # maçã logo à frente...
        s.bomb = Bomb((head[0] + 1, head[1]), 999.0)                          # ...com a bomba no caminho
        self.assertNotEqual(robot.choose(s), 'E')
        self.assertNotEqual(robot.choose(s, avoid_bombs=False), 'E')          # tem outro caminho: desvia

    def test_live_robot_takes_the_bomb_as_last_resort(self):
        s = GameState(FOOD_TO_THEME, n=3, rng=random.Random(1), bomb_theme='queimado')
        s.snake = [(0, 0), (1, 0), (2, 0), (2, 1), (1, 1)]                    # a única saída da cabeça é (0, 1)...
        s.dir = 'W'
        s.food = (2, 2)
        s.bomb = Bomb((0, 1), 999.0)                                          # ...e a bomba está lá
        self.assertEqual(robot.choose(s, avoid_bombs=False), 'S')             # pega a bomba para não se trancar

    def test_bomb_on_the_cycle_does_not_trap_the_robot_in_a_loop(self):
        # partida da live em que uma bomba parada na próxima casa do ciclo fazia a cobra voltar no ciclo e rodar
        # atrás da cauda num circuito de 6 casas, sem comer, até a fome destravar (~650 passos)
        from cobra import live
        from cobra.manifest import load_manifest
        man = load_manifest()
        s = GameState(man.food_to_theme, n=18, rng=random.Random(705), bomb_theme=man.bomb_theme, apple_tier=7,
                      live=True)
        s.controller = lambda st: robot.choose(st, avoid_bombs=False)
        opts = live.default_options()
        hungry, last, f = 0, None, 0
        while len(s.snake) < 20 and not s.over:
            if f % 700 == 0:
                live.apply_orders(s, live.gift_orders('TikTok', 1, 1, 'x', opts))
            if f % 900 == 0:
                live.apply_orders(s, live.gift_orders('Donut', 30, 1, 'x', opts))
            if f % 2400 == 0:
                live.apply_orders(s, live.gift_orders('Galaxy', 80, 1, 'x', opts))
            s.update(1 / 15)
            s.events.clear()
            f += 4
            prog = (len(s.snake), s.score)
            hungry = 0 if prog != last else hungry + 1
            last = prog
            self.assertLess(hungry, 200 * 4)            # quadros sem comer (antes: ~650 passos = ~2600 quadros)
        self.assertFalse(s.dead)

    def test_practice_match_skips_rank_and_records(self):
        s = GameState(FOOD_TO_THEME, rng=random.Random(1))
        s.practice, s.score, s.dead = True, 999, True
        r = Result(s, '/nao/existe.json')
        self.assertEqual(r.phase, 'resumo')     # sem tela de ranque e sem pedir o nome do recorde
        self.assertFalse(r.can_show_table)


if __name__ == '__main__':
    unittest.main()
