"""Peças da interface chapada: cache de imagens e fontes, retângulo de cantos suaves e o Botao.

Tudo aqui é desenhado na resolução base da interface (1280x720); quem usa escala o resultado.
"""
import os

import pygame

from . import config

# paleta da interface chapada (a mesma do mockup do perfil)
INK = (0x2A, 0x1A, 0x3A)            # texto escuro
MUTED = (0x8A, 0x7F, 0x99)          # texto secundário
PINK = (0xFF, 0x3D, 0x8B)
PINK_HOVER = (0xFF, 0x5C, 0xA0)
PINK_PRESSED = (0xE0, 0x26, 0x74)
PINK_LIGHT = (0xFF, 0xE0, 0xEC)     # fundo de etiquetas
WHITE = (255, 255, 255)
CARD_BORDER = (0xED, 0xE7, 0xF3)
STAT_FILL = (0xF5, 0xF2, 0xFA)      # caixinhas
HOVER_FILL = (0xEC, 0xE5, 0xF6)
PRESSED_FILL = (0xE2, 0xDA, 0xF0)
TRACK = (0xEF, 0xE9, 0xF6)          # trilho das barras
LOSS = (0xE5, 0x48, 0x4D)           # perdeu PDL / pontos
LOSS_LIGHT = (0xFD, 0xEC, 0xEC)
DIM = (20, 10, 40, 110)             # escurece o que fica atrás de um quadro
SHADOW = (20, 10, 40, 50)

_images = {}
_fonts = {}
_rects = {}


def load_image(path):
    """Imagem com convert_alpha, carregada uma vez só (cache global)."""
    if path not in _images:
        _images[path] = pygame.image.load(path).convert_alpha()
    return _images[path]


def fonte(peso, tamanho, folder=config.FONT_DIR):
    """Poppins (Regular / Medium / Bold) em cache; sem o arquivo, uma fonte do sistema parecida."""
    key = (peso, tamanho)
    if key not in _fonts:
        path = os.path.join(folder, f'Poppins-{peso}.ttf')
        if os.path.exists(path):
            _fonts[key] = pygame.font.Font(path, tamanho)
        else:
            _fonts[key] = pygame.font.SysFont('poppins,nunito,montserrat,arial', tamanho, bold=peso == 'Bold')
    return _fonts[key]


def rounded_rect(tamanho, raio, cor, borda=None):
    """Retângulo de cantos suaves: desenhado em 3x e reduzido com smoothscale (o border_radius do pygame
    serrilha). borda = (cor, espessura). Em cache, então pode ser chamado a cada quadro."""
    w, h = tamanho
    key = (w, h, raio, tuple(cor), borda)
    if key not in _rects:
        k = 3
        big = pygame.Surface((w * k, h * k), pygame.SRCALPHA)
        big.fill((*(borda[0] if borda else cor)[:3], 0))     # transparente da mesma cor: a borda não escurece ao reduzir
        if borda:
            bcor, bw = borda
            pygame.draw.rect(big, bcor, big.get_rect(), border_radius=raio * k)
            inner = big.get_rect().inflate(-2 * bw * k, -2 * bw * k)
            pygame.draw.rect(big, cor, inner, border_radius=max(0, (raio - bw) * k))
        else:
            pygame.draw.rect(big, cor, big.get_rect(), border_radius=raio * k)
        _rects[key] = pygame.transform.smoothscale(big, (w, h))
    return _rects[key]


def circle(raio, cor):
    """Círculo suave (mesma técnica do rounded_rect)."""
    return rounded_rect((2 * raio, 2 * raio), raio, cor)


class Botao:
    """Botão de sprite com os estados normal / hover / pressionado (mesmo tamanho).

    prefix: caminho do sprite sem o estado, ex.: '<ui>/botoes/fechar' -> fechar_normal.png etc.
    hotkey: tecla de atalho opcional (o menu procura por ela, ex.: Enter no Jogar, Esc no Voltar).
    label: texto escrito por cima (com ▶), para botões cujo texto vem traduzido. Se ele for igual ao
    texto que já está desenhado no sprite (baked), usa o sprite original; senão usa a versão
    '<prefix>_vazio' e escreve o texto.
    """

    def __init__(self, prefix, pos, action, hotkey=None, label=None, baked=None, font=None):
        self.prefix, self.action, self.hotkey = prefix, action, hotkey
        self.label, self.baked, self.font = label, baked, font
        normal = load_image(f'{prefix}_normal.png')
        self.rect = pygame.Rect(pos, normal.get_size())

    def _sprite(self, state):
        if self.label is not None and self.label != self.baked:
            return load_image(f'{self.prefix}_vazio_{state}.png')
        return load_image(f'{self.prefix}_{state}.png')

    def draw(self, surface, state):
        surface.blit(self._sprite(state), self.rect)
        if self.label is not None and self.label != self.baked and self.font is not None:
            img = self.font.render(self.label, True, (255, 255, 255))
            tri = round(self.font.get_height() * 0.42)
            gap = round(tri * 0.9)
            x = self.rect.centerx - (tri + gap + img.get_width()) / 2
            cy = self.rect.centery
            pygame.draw.polygon(surface, (255, 255, 255),
                                [(x, cy - tri * 0.6), (x + tri, cy), (x, cy + tri * 0.6)])
            surface.blit(img, img.get_rect(midleft=(round(x + tri + gap), cy)))


def card(surface, rect, raio=24, fill=WHITE, shadow=True, borda=None):
    """Cartão chapado: sombra suave embaixo (opcional) e o retângulo de cantos suaves."""
    rect = pygame.Rect(rect)
    if shadow:
        surface.blit(rounded_rect(rect.size, raio, SHADOW), rect.move(0, 6))
    surface.blit(rounded_rect(rect.size, raio, fill, borda), rect)
    return rect


def bar(surface, rect, frac, fill, track=TRACK):
    """Barra de progresso de pontas redondas (frac de 0 a 1)."""
    rect = pygame.Rect(rect)
    r = rect.height // 2
    surface.blit(rounded_rect(rect.size, r, track), rect)
    w = round(rect.width * min(max(frac, 0.0), 1.0))
    if w >= rect.height:
        surface.blit(rounded_rect((w, rect.height), r, fill), rect.topleft)
    elif w > 0:
        surface.blit(circle(r, fill), rect.topleft)


def volume_row(surface, rect, label, level, font, button, level_max=10):
    """Linha de volume: nome, botão −, barra, botão + e a porcentagem. button(rect, texto) desenha cada botão
    (quem chama registra o clique); devolve os retângulos (menos, mais)."""
    rect = pygame.Rect(rect)
    h = rect.height
    name = font.render(label, True, INK)
    surface.blit(name, name.get_rect(midleft=(rect.left, rect.centery)))
    pct_w, label_w = 64, round(rect.width * 0.3)
    minus = pygame.Rect(rect.left + label_w, rect.top, h, h)
    plus = pygame.Rect(rect.right - pct_w - h, rect.top, h, h)
    track = pygame.Rect(minus.right + 14, rect.centery - 5, plus.left - 14 - minus.right - 14, 10)
    bar(surface, track, level / level_max, PINK)
    button(minus, '−')
    button(plus, '+')
    pct = font.render(f'{round(100 * level / level_max)}%', True, INK)
    surface.blit(pct, pct.get_rect(midright=(rect.right, rect.centery)))
    return minus, plus


class FpsMeter:
    """Contador de FPS no canto da tela: o atual (média do último meio segundo) e o pior dos últimos 2 s,
    que mostra as travadinhas. Verde a partir de 55, amarelo a partir de 30, vermelho abaixo."""

    def __init__(self):
        self.frames = []            # (hora, duração do quadro)
        self.now = 0.0

    def tick(self, dt):
        self.now += dt
        self.frames.append((self.now, dt))
        while self.frames and self.frames[0][0] < self.now - 2.0:
            self.frames.pop(0)

    def draw(self, surface):
        recent = [d for t, d in self.frames if t >= self.now - 0.5]
        if not recent:
            return
        fps = len(recent) / max(sum(recent), 1e-6)
        worst = 1 / max(max(d for _, d in self.frames), 1e-6)
        color = (40, 170, 90) if worst >= 55 else (220, 160, 20) if worst >= 30 else LOSS
        text = fonte('Bold', 16).render(f'{fps:.0f} FPS', True, WHITE)
        sub = fonte('Medium', 12).render(f'pior {worst:.0f}', True, WHITE)
        w, h = max(text.get_width(), sub.get_width()) + 20, text.get_height() + sub.get_height() + 8
        pill = pygame.Rect(0, 0, w, h)
        pill.bottomright = (surface.get_width() - 10, surface.get_height() - 10)
        surface.blit(rounded_rect(pill.size, 10, color), pill)
        surface.blit(text, text.get_rect(midtop=(pill.centerx, pill.top + 4)))
        surface.blit(sub, sub.get_rect(midtop=(pill.centerx, pill.top + 4 + text.get_height())))


def flat_button(surface, rect, label, font, state='normal', primary=True):
    """Botão chapado desenhado: rosa com texto branco (primário) ou lilás claro com texto escuro."""
    rect = pygame.Rect(rect)
    if primary:
        fill, color = {'normal': PINK, 'hover': PINK_HOVER, 'pressionado': PINK_PRESSED}[state], WHITE
    else:
        fill, color = {'normal': STAT_FILL, 'hover': HOVER_FILL, 'pressionado': PRESSED_FILL}[state], INK
    surface.blit(rounded_rect(rect.size, min(12, rect.height // 2), fill), rect)
    img = font.render(label, True, color)
    if img.get_width() > rect.width - 20:
        k = (rect.width - 20) / img.get_width()
        img = pygame.transform.smoothscale(img, (rect.width - 20, max(1, round(img.get_height() * k))))
    surface.blit(img, img.get_rect(center=rect.center))
