import importlib.util
import os
import random
import tempfile
import unittest


@unittest.skipUnless(importlib.util.find_spec('pygame'), 'sem pygame')
class TestRenderScreens(unittest.TestCase):
    """Desenha cada tela da partida uma vez (sem janela): pega erros que só aparecem ao desenhar."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
        os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
        import pygame
        from cobra.assets import Assets
        from cobra.manifest import load_manifest
        from cobra.render import Renderer
        pygame.init()
        cls.pygame = pygame
        screen = pygame.display.set_mode((1280, 720))
        cls.man = load_manifest()
        cls.renderer = Renderer(screen, Assets(cls.man))
        cls.tmp = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()           # sem pygame.quit(): as fontes em cache (widgets) não sobrevivem a reiniciar

    def state(self, live=False):
        from cobra.logic import GameState
        from cobra.robot import choose
        s = GameState(self.man.food_to_theme, n=11, rng=random.Random(1), bomb_theme=self.man.bomb_theme, live=live)
        for _ in range(30):
            s.queue = [choose(s)]
            s.update(s.step_time)
        return s

    def test_playing_paused_and_live(self):
        from cobra import live
        s = self.state(live=True)
        live.apply_orders(s, live.gift_orders('Galaxy', 40, 1, 'ana', live.default_options()))
        live.apply_orders(s, live.gift_orders('TikTok', 1, 1, 'leo', live.default_options()))
        for _ in range(90):                     # arremessos, caixa, duendes do obrigado
            s.update(1 / 60)
            self.renderer.draw(s)
        self.renderer.draw(s, paused=True)

    def test_game_over_screens(self):
        from cobra import config, profile, rank
        from cobra.live import Tribute
        from cobra.result import Result
        for won in (True, False):
            s = self.state()
            r = rank.Rank(0, 4, config.RANQUE_PDL_DIVISAO - 1)     # Ferro IV quase subindo: a vitória sobe (confete)
            score = rank.target(r, s.n) * 2 if won else 1
            s.score, s.dead = score, True
            out = rank.apply_match(r, score, 0, s.n, 60.0)
            res = Result(s, os.path.join(self.tmp.name, f'recordes_{won}.json'), out)
            res.xp_info = (out.xp, 1, profile.level({'arenas': {}}))
            res.new_skin = 'bronze' if won else None
            for _ in range(80):                 # ranque: a barra anima, sobe e solta o confete
                s.update(0.1)
                self.renderer.draw(s, result=res)
            for _ in range(2):                  # nome do recorde, resumo
                res.confirm()
                self.renderer.draw(s, result=res)
            res.toggle_table()
            self.renderer.draw(s, result=res)
            res.phase = 'top'                   # pódio da live (robô): com e sem espectadores
            res.supporters = [Tribute('ana', 'Ana', None, 10, 3)]
            self.renderer.draw(s, result=res)
            res.supporters = []
            self.renderer.draw(s, result=res)


if __name__ == '__main__':
    unittest.main()
