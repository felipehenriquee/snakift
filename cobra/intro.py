"""Abertura: a câmera começa longe e se aproxima até o enquadramento do jogo."""
import math

import pygame

from . import config
from .render import Renderer

MIP_STEP = 0.71         # razão entre as cópias reduzidas da cena grande
FADE_START = 0.85       # a partir daqui (fração da abertura) funde com o quadro exato do jogo


def ease_in_out(t):
    """0..1 -> 0..1, começa e termina devagar."""
    t = min(max(t, 0.0), 1.0)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


class Intro:
    """Desenha a cena uma vez numa superfície maior que a tela e vai aproximando.

    O recorte que vai para a tela encolhe em volta do centro do tabuleiro até ficar do
    tamanho da tela. No finzinho a imagem se funde com o quadro do jogo desenhado na tela
    normal (a cena grande difere dele em detalhes de reamostragem), então não há salto
    quando a partida começa.
    """

    def __init__(self, canvas, assets, state, duration=config.INTRO_SEGUNDOS, zoom=config.INTRO_ZOOM,
                 perspective=config.PERSPECTIVA, skin='classica'):
        self.canvas = canvas
        self.duration = duration
        self.zoom0 = zoom
        self.t = 0.0
        w, h = canvas.get_size()
        # centro do tabuleiro na tela do jogo: a câmera se aproxima mirando nele
        probe = Renderer(canvas, assets, perspective)
        probe.skin = skin
        probe.draw(state, hud=False)
        self.final = canvas.copy()          # quadro exato em que a abertura termina
        self.focus = fx, fy = probe.board_center()
        # folga em volta da tela para o recorte mais aberto (zoom inicial) caber inteiro;
        # a superfície grande fica centralizada igual à tela, só que com a folga dos lados
        mx = math.ceil(max(fx, w - fx) * (1 / zoom - 1)) + 1
        my = math.ceil(max(fy, h - fy) * (1 / zoom - 1)) + 1
        self.offset = (mx, my)
        big = pygame.Surface((w + 2 * mx, h + 2 * my))
        # mesmo zoom do jogo: a superfície grande é a mesma câmera, só que vendo mais em volta
        big_renderer = Renderer(big, assets, perspective, zoom=probe.proj.zoom)
        big_renderer.skin = skin
        big_renderer.draw(state, hud=False)
        # cópias reduzidas: cada quadro escala a partir da menor que ainda tem pixels de sobra
        self.levels = [(1.0, big)]
        k = 1.0
        while k * MIP_STEP >= zoom * 0.99:
            k *= MIP_STEP
            self.levels.append((k, pygame.transform.smoothscale_by(big, k)))

    @property
    def done(self):
        return self.t >= self.duration

    def skip(self):
        self.t = self.duration

    def draw(self, dt):
        self.t += dt
        progress = min(self.t / self.duration, 1.0)
        z = self.zoom0 + (1 - self.zoom0) * ease_in_out(progress)
        w, h = self.canvas.get_size()
        fx, fy = self.focus
        # recorte (na superfície grande) que vai ocupar a tela: o foco fica no mesmo lugar da tela
        left = self.offset[0] + fx - fx / z
        top = self.offset[1] + fy - fy / z
        cw, ch = w / z, h / z
        k, src = min((lv for lv in self.levels if lv[0] >= z * 0.999), key=lambda lv: lv[0])
        rect = pygame.Rect(round(left * k), round(top * k), round(cw * k), round(ch * k))
        rect = rect.clip(src.get_rect())
        pygame.transform.smoothscale(src.subsurface(rect), (w, h), self.canvas)
        if progress > FADE_START:
            self.final.set_alpha(round(255 * (progress - FADE_START) / (1 - FADE_START)))
            self.canvas.blit(self.final, (0, 0))
