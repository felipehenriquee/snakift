import importlib.util
import os
import tempfile
import unittest
from unittest import mock


@unittest.skipUnless(importlib.util.find_spec('pygame'), 'sem pygame')
class TestRobotMode(unittest.TestCase):
    """Build com robô (config.MODO_ROBO): o robô joga e a partida vale (ranque, perfil e recordes salvos); o fim
    segue sozinho até começar outra partida. Usa uma pasta de dados temporária (não mexe nos dados do jogador)."""

    def test_robot_match_counts_and_next_one_starts(self):
        os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
        os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
        import pygame
        from cobra import config, profile, rank, records
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {'XDG_DATA_HOME': tmp}), \
                mock.patch.object(config, 'MODO_ROBO', True):
            from cobra import app as A
            pygame.init()
            game = A.App(pygame.display.set_mode((1280, 720)))
            self.assertTrue(game.robot_mode)
            game.start_game(11, intro=False)
            phases, t = [], 0.0
            while t < 1500 and phases.count('jogando') < 2:
                game.frame(0.25, t)
                t += 0.25
                phase = game.result.phase if game.result is not None else 'jogando'
                if not phases or phases[-1] != phase:
                    phases.append(phase)
            self.assertEqual(phases[:2], ['jogando', 'ranque'])     # fim: tela de PDL...
            self.assertEqual(phases.count('jogando'), 2)            # ...e uma partida nova, sozinho
            self.assertFalse(game.state.practice)                   # a partida do robô não é treino
            self.assertEqual(profile.load(game.profile_path)['arenas'][11]['partidas'], 1)
            self.assertNotEqual(rank.load(game.rank_path)[11], rank.START)
            self.assertTrue(records.load(game.records_path)['tabelas'])
            self.assertTrue(game.profile_path.startswith(tmp))


if __name__ == '__main__':
    unittest.main()
