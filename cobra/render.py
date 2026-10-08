"""Desenho do jogo em visão 3/4, com perspectiva falsa opcional (a projeção vem do manifest).

O chão e a decoração cobrem a tela inteira; a partida acontece só dentro da cerca.
"""
import math
import re
import os
import random
from collections import namedtuple

import pygame

from . import config, live, rank, records, settings
from . import i18n
from .i18n import t
from .logic import CAIXA, DIR_FROM_DELTA, apple_weights, is_apple, points_for
from .projection import Projection
from .scenery import make_fence, make_props, outside_distance
from .widgets import (CARD_BORDER, DIM, HOVER_FILL, INK, LOSS, LOSS_LIGHT, MUTED, PINK, PINK_LIGHT, STAT_FILL, WHITE,
                      bar, card, circle, flat_button, fonte, rounded_rect, volume_row)

# key = ordem de desenho; dy = deslocamento vertical em px (pulo, balanço); shadow = desenha sombra embaixo
Thrower = namedtuple('Thrower', 'name char poses cell items image effect')     # image(item) -> sprite
SPARKLE_COLORS = ((255, 255, 255), (255, 245, 170))         # estrelinhas do duende bom
SMOKE_COLORS = ((92, 60, 120), (60, 40, 80), (150, 60, 90))    # fumacinha do duende do mal
JUMP_HEIGHT = 34        # px do pulo dos duendes quando o lado deles vence
THANKS_BAND = 92        # px reservados embaixo da cerca para a placa de obrigado (fica fora da arena)
WALK_ROW = 1.6          # linhas abaixo da cerca de baixo por onde os duendes do obrigado andam
BOARD_ON_BODY = 0.4     # a placa cobre essa fração de baixo do duende (pernas); cabeça e chapéu aparecem
WALK_HOP = 7            # px do pulinho de cada passo do duende do obrigado
BOARD_FILL, BOARD_EDGE = (255, 248, 232), (139, 90, 43)     # placa de obrigado: madeira clara com borda escura
BOARD_MAX_W = 460       # largura máxima da placa de obrigado (px da tela)
# pódio da live (fim da partida do robô): (fundo, borda, texto do @) de cada lugar: dourado, prateado e bronze
PODIUM = (((0xFF, 0xE0, 0x8A), (0xD9, 0xA4, 0x00), (0x6B, 0x4A, 0x00)),
          ((0xE6, 0xEB, 0xF1), (0x9A, 0xA6, 0xB4), (0x3C, 0x46, 0x52)),
          ((0xF2, 0xC8, 0xA0), (0xB8, 0x6B, 0x2E), (0x5C, 0x30, 0x0E)))
# anchor: pixel do pé da imagem (None = o dos objetos, do manifest)
Drawable = namedtuple('Drawable', 'key img gx gy dy shadow anchor', defaults=(None,))

PROPS_NO_CHAO = 3        # decoração a 3+ casas da arena vai desenhada junto com o chão (em cache)
TILE_POP = 10           # px que o tile sobe quando o tema troca
ICON_ANGLE_STEP = 5     # graus: itens girando no ar usam imagens giradas em passos (em cache)
PROP_POP = 14
FIELD_SEARCH = 40       # até quantas células além do tabuleiro procurar tiles visíveis
MIN_SCALE = 0.3         # linhas tão ao fundo que ficam menores que isso não são desenhadas

# interface (estilo chapado; a paleta fica em widgets.py)
HUD_POS = (24, 20)          # canto de cima-esquerda do placar
HUD_PAD = 10
HUD_CHIP = (104, 62)        # caixinha de pontos / recorde / presentes / tempo
HUD_GIFT_W = 54             # caixinha de cada presente, com o placar aberto
HUD_BOMB_GIFT_W = 46        # na live, a caixinha da bomba é mais larga: "presente da live = bomba"
HUD_GAP = 8
HUD_TOGGLE_W = 30           # botão > / < na ponta do placar
HUD_LIVE_DOT_W = 26         # espaço da bolinha do estado da live, depois do botão
HINT_FILL = (20, 10, 40, 130)
OVERLAY_SIZE = (680, 560)   # quadro de fim de jogo
PAUSE_SIZE = (680, 700)     # quadro de pausa (mais alto: tem os volumes)
OVERLAY_PAD = (40, 34)
BUTTON_H = 50
PRIMARY_ACTIONS = ('restart', 'continue', 'save', 'resume')


def draw_records_table(surface, font, recs, box, text, accent, highlight=None, highlight_fill=None):
    """Tabela "usuario     100": posição e nome à esquerda, pontos à direita, 10 linhas em `box`.

    A linha `highlight` (índice) sai na cor de destaque. Sem recordes, mostra um aviso.
    """
    bx, by, bw, bh = box
    if not recs:
        img = font.render(t('records.empty'), True, text)
        surface.blit(img, img.get_rect(center=(round(bx + bw / 2), round(by + bh * 0.4))))
        return
    row_h = bh / records.MAX_RECORDS
    left, right = bx + bw * 0.14, bx + bw * 0.86
    for i, rec in enumerate(recs):
        y = by + row_h * 0.5 + i * row_h
        color = accent if i == highlight else text
        if i == highlight and highlight_fill is not None:          # faixa de destaque atrás da linha
            band = min(row_h * 0.9, 44)
            row = pygame.Rect(round(bx + bw * 0.06), round(y - band / 2), round(bw * 0.88), round(band))
            surface.blit(rounded_rect(row.size, min(12, row.height // 2), highlight_fill), row)
        pos = font.render(f'{i + 1}.', True, color)
        name = font.render(rec['nome'], True, color)
        pts = font.render(str(rec['pontos']), True, color)
        surface.blit(pos, pos.get_rect(midright=(round(left + 26), round(y))))
        surface.blit(name, name.get_rect(midleft=(round(left + 38), round(y))))
        surface.blit(pts, pts.get_rect(midright=(round(right), round(y))))


def rank_label(r):
    """'Ferro IV', 'Mestre'..."""
    return f"{t('tier.' + rank.tier_id(r))} {rank.ROMAN[r.division]}".strip()


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ease_out_back(x):
    """Passa um pouco do 1 e volta (o presente "estoura" ao surgir na mão)."""
    x = min(max(x, 0.0), 1.0)
    c = 1.7
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


# linha do tempo da tela do ranque (segundos desde o fim da partida)
RANK_REVEAL = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5)     # cada linha do cálculo aparece
RANK_BAR_START = 1.8
RANK_STEP = 0.9                            # duração de cada trecho da barra
RANK_PAUSE = 0.6                           # pausa depois de subir/cair (comemoração)
CONFETTI = [(255, 92, 158), (92, 200, 255), (255, 224, 102), (111, 240, 192), (255, 160, 80), (180, 120, 255)]


def format_time(seconds):
    """Segundos -> 'm:ss'."""
    s = int(seconds)
    return f'{s // 60}:{s % 60:02d}'
POPUP_OUTLINE = (60, 30, 50)
GIFT_IN_HAND = 0.6      # tamanho do presente na mão do duende (cresce até o normal no voo)
POPUP_RISE = 60         # px que o "+10" sobe até sumir
POPUP_LIFT = 70         # px acima do chão onde ele nasce (acima da cabeça da cobra)


def popup_color(points, kind=None):
    """Cor do "+N" pela comida (o número depende do tamanho da cobra, então não diz qual foi)."""
    if points < 0:
        return (255, 80, 60)        # vermelho: perdeu pontos (bomba)
    base = points_for(kind) if kind else points
    if base >= 30:
        return (255, 214, 64)       # dourado: rosquinha
    if base >= 10:
        return (255, 255, 255)
    return (210, 230, 255)          # maçã


class Renderer:
    def __init__(self, screen, assets, perspective=config.PERSPECTIVA, fence_on_edge=config.CERCA_NA_BORDA, zoom=None):
        """zoom: força o zoom da câmera (a abertura usa o mesmo do jogo); None = o que fizer a arena caber."""
        self.forced_zoom = zoom
        self.screen = screen
        self.assets = assets
        self.man = assets.manifest
        self.perspective = perspective
        self.fence_on_edge = fence_on_edge
        self.font = fonte('Bold', 22)
        self.small = fonte('Regular', 13)
        self.chip_font = fonte('Regular', 12)
        self.chip_bold = fonte('Bold', 13)
        self.label_font = fonte('Medium', 15)
        self.label_bold = fonte('Bold', 15)
        self.value_font = fonte('Bold', 22)
        self.title_font = fonte('Bold', 34)
        self.big_font = fonte('Bold', 72)
        self.popup_font = fonte('Bold', 34)
        self._popup_imgs = {}       # pontos -> texto "+N" com contorno
        self.button_font = fonte('Bold', 16)
        self.thanks_fonts = (fonte('Medium', 20), fonte('Bold', 26), fonte('Medium', 16))   # placa de obrigado
        self._boards = {}           # placas de obrigado prontas: (lado, pedido, idioma) -> imagem
        self.buttons = []           # (retângulo, ação) dos botões desenhados no último quadro
        self.mouse = None           # posição do mouse na tela lógica (para o destaque do botão)
        self.legend_open = False    # tabela "quanto vale cada presente", ao lado do placar
        self.best_score = 0         # 1º lugar dos recordes da arena jogada (o app atualiza)
        self.rank_info = None       # (elo, meta) da arena jogada, para o placar (o app atualiza)
        self.skin = 'classica'      # skin da cobra no tema padrão (o app atualiza)
        self.prefs = {}             # configurações do jogador (a pausa mostra os volumes; o app atualiza)
        self.player_name = ''       # nome no menu de pausa (o app atualiza)
        self.live_info = None       # (@, (estado, motivo, segundos)) da conexão com a live, no modo live
        self.autopilot = False      # robô jogando (aviso no placar)
        self.minimal_hud = False    # só o placar e o elo (o robô das lives): sem dicas, avisos e estado da live
        self._gift_icons = {}       # (presente da live, tamanho) -> ícone (legenda e placa de obrigado)
        self._celebrating = None    # fim da partida: 'bom' (vitória) ou 'mal' (derrota): esse lado pula
        self._avatars = {}          # fotos dos espectadores (top da live), já redondas
        self.scenery_changes = True # configurações: o cenário troca de tema com os presentes?
        self.snake_changes = True   # e a cobra? (só o visual; as regras do tema continuam valendo)
        self._shields = {}
        self._legend_icons = {}
        self._bboxes = {}           # sprite -> parte visível (get_bounding_rect)
        self._rotated = {}          # (ícone, passo do giro) -> ícone girado
        self._rings = {}            # (momento, tamanho) -> anel do presente estourando
        self._confetti = (None, [])     # (resultado, partículas) dos confetes da vitória
        self.proj = None
        self._setup_for = None      # (n, tamanho da tela) da última preparação
        self._scaled = {}           # (imagem, nível de escala) -> imagem escalada
        self._board_key = None      # tema do chão em cache; None = no meio da onda; 'vazio' = nada desenhado

    def set_screen(self, screen):
        """Troca a superfície de desenho (por exemplo quando a janela muda de proporção)."""
        self.screen = screen

    # ------------------------------------------------------------ preparação
    def _setup(self, state):
        """Monta projeção, cenário e o chão plano (de novo só se o tabuleiro ou a tela mudarem)."""
        key = (state.n, self.screen.get_size())
        if key == self._setup_for:
            return
        self._setup_for = key
        n = state.n
        w_scr, h_scr = self.screen.get_size()
        self.proj = Projection(self.man, n, self.perspective)
        self.fence = make_fence(n, self.fence_on_edge)

        # zoom para o tabuleiro com a cerca caber abaixo do placar (arenas grandes afastam a câmera)
        (ow, oh), (oax, oay) = self.man.obj_size, self.man.obj_anchor

        def extents():
            lefts, rights, tops, bottoms = [], [], [], []
            for gx, gy in [f.pos for f in self.fence]:
                x, y, s = self.proj.project(gx, gy)
                lefts.append(x - oax * s)
                rights.append(x + (ow - oax) * s)
                tops.append(y - oay * s)
                bottoms.append(y + (oh - oay) * s)
            return max(rights) - min(lefts), min(tops), max(bottoms)
        self.walk_row = max(f.pos[1] for f in self.fence) + WALK_ROW     # faixa dos duendes do obrigado
        width, top, bottom = extents()
        if self.forced_zoom is not None:
            self.proj.zoom = self.forced_zoom
        else:
            self.proj.zoom = min(1.0, 0.96 * w_scr / width,
                                 0.97 * (h_scr - config.HUD_H - THANKS_BAND) / (bottom - top))
        _, top, bottom = extents()
        mid_y = (config.HUD_H + h_scr - THANKS_BAND) / 2           # embaixo fica a faixa da placa de obrigado
        self.proj.center = (w_scr / 2, mid_y - (top + bottom) / 2)
        self.fence_bottom = mid_y + (bottom - top) / 2              # pé da cerca de baixo na tela: a placa fica abaixo

        # todas as células que aparecem na tela (com folga para os objetos altos de baixo)
        (tw, th), (tax, tay) = self.man.tile_size, self.man.tile_anchor
        self.field = []
        for gy in range(-FIELD_SEARCH, n + FIELD_SEARCH):
            for gx in range(-FIELD_SEARCH, n + FIELD_SEARCH):
                x, y, s = self.proj.project(gx, gy)
                if s / self.proj.zoom < MIN_SCALE:
                    continue
                if -tw * s < x < w_scr + tw * s and -th * s < y < h_scr + oay * s:
                    self.field.append((gx, gy))
        self.props = make_props(n, self.field, self.fence_on_edge, config.DENSIDADE_PROPS, config.FOLGA_CERCA)
        # decoração longe da arena: nada que se mexe passa na frente dela, então vai desenhada junto com o chão
        # (uma vez por tema) em vez de ser redesenhada a cada quadro
        self.far_props = {p for p in self.props if outside_distance(n, p.cell) >= PROPS_NO_CHAO}
        self._props_baked = False
        xs = [c[0] for c in self.field]
        ys = [c[1] for c in self.field]
        self.field_box = (min(xs), min(ys), max(xs), max(ys))

        # chão plano (sem perspectiva, já na escala do zoom): caixa que envolve todos os tiles,
        # com espaço para o pulo. Montar o chão já reduzido deixa tiles e fatias bem mais baratos.
        z = self.proj.zoom
        fx, fy = [], []
        for gx, gy in self.field:
            xf, yf = self.proj.flat(gx, gy)
            fx += [(xf - tax) * z, (xf - tax + tw) * z]
            fy += [(yf - tay - TILE_POP) * z, (yf - tay + th) * z]
        left, top = math.floor(min(fx)), math.floor(min(fy))
        self.board_origin = (left, top)
        # opacos: o chão cobre a tela toda (a cor de fundo só aparece nas frestas), e opaco é mais rápido
        self.board_flat = pygame.Surface((math.ceil(max(fx)) - left, math.ceil(max(fy)) - top))
        self.board = pygame.Surface((w_scr, h_scr))
        self._board_key = 'vazio'   # nada desenhado ainda: o primeiro quadro faz o chão inteiro
        self._wave_id = None        # onda já em andamento no chão em cache (origem, temas)
        self._wave_new = None       # chão inteiro já no tema novo da onda (a onda vai revelando ele)
        self._wave_stage = 0        # preparo do chão novo: 0 = pintar os tiles, 1 = aplicar a perspectiva
        self._old_props = False     # o chão de antes da onda tinha a decoração longe desenhada nele
        # células do chão na ordem de desenho (de trás para a frente), com a posição no chão plano
        self._field_order = [(c, self.proj.flat(*c)) for c in
                             sorted(self.field, key=lambda c: (self.man.depth(*c), c[0]))]
        self._tiles = {}            # (tema, variante, fora da cerca) -> tile na escala do zoom

    def _scaled_img(self, img, s):
        """Imagem escalada (com cache) e a escala realmente usada."""
        if self.perspective == 0 and self.proj.zoom == 1:
            return img, 1.0
        level = round(s / config.SCALE_STEP)
        key = (img, level)
        if key not in self._scaled:
            sq = level * config.SCALE_STEP
            w, h = img.get_size()
            self._scaled[key] = pygame.transform.smoothscale(img, (max(1, round(w * sq)), max(1, round(h * sq))))
        return self._scaled[key], level * config.SCALE_STEP

    def _tile_img(self, theme, variant, outside):
        """Tile na escala do zoom (o de fora da cerca, escurecido), com cache."""
        key = (theme, variant, outside)
        if key not in self._tiles:
            img = self.assets.spr[theme][f'tile_{variant}']
            if outside and config.ESCURECER_FORA > 0:
                k = round(255 * (1 - config.ESCURECER_FORA))
                img = img.copy()
                img.fill((k, k, k), special_flags=pygame.BLEND_RGB_MULT)
            z = self.proj.zoom
            if z != 1:
                img = pygame.transform.smoothscale(img, (round(img.get_width() * z), round(img.get_height() * z)))
            self._tiles[key] = img
        return self._tiles[key]

    def _wave_reach(self, state):
        """Maior distância (em células) da origem da onda até o canto mais longe do cenário."""
        x0, y0, x1, y1 = self.field_box
        ox, oy = state.wave_origin
        return max(abs(x0 - ox), abs(x1 - ox)) + max(abs(y0 - oy), abs(y1 - oy))

    # ------------------------------------------------------------ desenho
    def draw(self, state, hud=True, result=None, paused=False):
        """result: o que o quadro de fim de jogo mostra (cobra.result.Result); paused: menu de pausa."""
        self.buttons = []
        self._celebrating = self._winner(state, result)
        self._setup(state)
        self._draw_board(state)
        self._draw_objects(self._objects(state))
        self._draw_thanks(state)
        self._draw_bursts(state)
        self._draw_in_air(state)
        self._draw_popups(state)
        if hud:
            self._draw_hud(state, result)
        if paused and not state.over:
            self._draw_pause(state)

    def board_center(self):
        """Ponto da tela onde fica o centro do tabuleiro (depois do primeiro draw)."""
        return self.proj.center

    def _scene_theme(self, state, cell):
        """Tema do cenário numa célula (e o pulo do tile); fixo no padrão se a troca estiver desligada."""
        return state.theme_at(cell) if self.scenery_changes else (config.START_THEME, 0.0)

    def _background(self, state):
        if not self.scenery_changes:
            return self.man.backgrounds[config.START_THEME]
        a, b = self.man.backgrounds[state.old_theme], self.man.backgrounds[state.theme]
        r = state.background_mix()
        return tuple(int(a[i] + (b[i] - a[i]) * r) for i in range(3))

    def _draw_board(self, state):
        """Chão em cache: só é refeito quando muda.

        Na troca de tema, o chão inteiro no tema novo é montado uma vez, em dois quadros (pintar os tiles /
        aplicar a perspectiva), e a onda vai revelando ele: a cada quadro, em cada fileira, as células que a onda
        já alcançou são copiadas do chão novo (uma cópia por fileira, barata). Quando a onda passa, o chão novo
        vira o chão em cache, sem refazer nada.
        """
        if not self.scenery_changes:
            key = config.START_THEME                        # cenário fixo: nada de onda
        else:
            key = state.theme if state.wave_passed(self._wave_reach(state)) else None
        wave = (state.wave_origin, state.old_theme, state.theme)
        if self._board_key == 'vazio' or (key is not None and key != self._board_key):
            if self._wave_new is not None and wave == self._wave_id and self._wave_stage == 2:
                self.board.blit(self._wave_new, (0, 0))    # a onda acabou: o chão novo já está pronto
            else:
                self._render_board(state)
            self._wave_new = None
            self._props_baked = key is not None and self._bake_props(state)
        elif key is None:
            if wave != self._wave_id:                       # começou uma onda: prepara o chão no tema novo
                self._wave_stage = 0
                self._old_props = self._props_baked         # o chão antigo tem a decoração longe desenhada?
            self._props_baked = False
            if self._wave_stage == 0:
                self._paint_flat(state, theme=state.theme)
                self._wave_stage = 1
            elif self._wave_stage == 1:
                self._wave_new = self.board.copy()
                self._warp_flat(self._wave_new)
                self._wave_stage = 2
            else:
                self._reveal_wave(state)
        self._wave_id = wave
        self._board_key = key
        self.screen.blit(self.board, (0, 0))

    def _reveal_wave(self, state):
        """Copia do chão novo as células que a onda já alcançou (distância à origem < raio), fileira por fileira."""
        r = state.wave_t * config.WAVE_SPEED
        ox, oy = state.wave_origin
        w_scr, h_scr = self.board.get_size()
        x0f, y0f, x1f, y1f = self.field_box
        for gy in range(y0f, y1f + 1):
            m = r - abs(gy - oy)                            # nesta fileira: |gx - ox| < m
            if m <= 0:
                continue
            lo, hi = max(x0f, math.floor(ox - m) + 1), min(x1f, math.ceil(ox + m) - 1)
            if hi < lo:
                continue
            xa, ya, _ = self.proj.project(lo - 0.5, gy - 0.5)
            xb, yb, _ = self.proj.project(hi + 0.5, gy + 0.5)
            xa2, _, _ = self.proj.project(lo - 0.5, gy + 0.5)      # com perspectiva, a fileira é um trapézio
            xb2, _, _ = self.proj.project(hi + 0.5, gy - 0.5)
            left, right = max(0, math.floor(min(xa, xa2))), min(w_scr, math.ceil(max(xb, xb2)))
            top, bottom = max(0, math.floor(ya)), min(h_scr, math.ceil(yb))
            if right > left and bottom > top:
                area = pygame.Rect(left, top, right - left, bottom - top)
                self.board.blit(self._wave_new, area, area)

    def _bake_props(self, state):
        """Desenha a decoração longe da arena (e as sombras dela) no chão em cache. Devolve True."""
        spr, screen = self.assets.spr, self.screen
        self.screen = self.board                        # _blit_object desenha em self.screen
        try:
            objs = [self._drawable(spr[self._scene_theme(state, p.cell)[0]][f'prop_{p.variant}'], *p.cell)
                    for p in self.far_props]
            self._draw_objects(objs)
        finally:
            self.screen = screen
        return True

    def _render_board(self, state):
        self._paint_flat(state)
        self._warp_flat(self.board)

    def _paint_flat(self, state, theme=None):
        """Desenha os tiles no chão plano (sem perspectiva, já na escala do zoom). theme: todas as células nesse
        tema (o chão novo da onda); None = o tema de cada célula agora."""
        flat, (left, top) = self.board_flat, self.board_origin
        z = self.proj.zoom
        tax, tay = self.man.tile_anchor[0] * z, self.man.tile_anchor[1] * z
        self._flat_bg = self._background(state) if theme is None else self.man.backgrounds[theme]
        flat.fill(self._flat_bg)
        for (gx, gy), (xf, yf) in self._field_order:      # de trás para a frente
            th, pop = self._scene_theme(state, (gx, gy)) if theme is None else (theme, 0.0)
            img = self._tile_img(th, (gx + gy) % 2, outside_distance(state.n, (gx, gy)) > 0)
            yf -= math.sin(pop * math.pi) * TILE_POP
            flat.blit(img, (round(xf * z - tax - left), round(yf * z - tay - top)))

    def _warp_flat(self, target):
        """Passa o chão plano para `target` (do tamanho da tela), aplicando a perspectiva."""
        flat, (left, top) = self.board_flat, self.board_origin
        z = self.proj.zoom
        target.fill(self._flat_bg)
        cx, cy = self.proj.center
        if self.perspective == 0:           # sem perspectiva o chão plano já é a imagem final
            target.blit(flat, (round(cx + left), round(cy + top)))
            return
        # com perspectiva: fatias finas, cada uma encolhida pela escala da sua altura, para as
        # bordas virarem retas convergentes (e não uma escadinha por linha). Só a parte de cada
        # fatia que cai dentro da tela é escalada.
        fw, fh = flat.get_size()
        w_scr, h_scr = target.get_size()
        for y in range(0, fh, config.BOARD_SLICE):
            hgt = min(config.BOARD_SLICE, fh - y)
            yf0, yf1 = (top + y) / z, (top + y + hgt) / z     # de volta para px planos sem zoom
            sy0, sy1 = round(self.proj.screen_y(yf0)), round(self.proj.screen_y(yf1))
            if sy1 <= max(sy0, 0) or sy0 >= h_scr:
                continue
            s = self.proj.scale_at((yf0 + yf1) / 2)       # o zoom já está no chão plano
            if s < MIN_SCALE:
                continue
            j0 = max(0, math.floor(-cx / s - left))
            j1 = min(fw, math.ceil((w_scr - cx) / s - left))
            if j1 <= j0:
                continue
            strip = flat.subsurface((j0, y, j1 - j0, hgt))
            strip = pygame.transform.smoothscale(strip, (max(1, round((j1 - j0) * s)), sy1 - sy0))
            target.blit(strip, (round(cx + (left + j0) * s), sy0))

    def _prop_on_board(self, state, p):
        """A decoração longe da arena já está no chão em cache? Fora da onda, se foi desenhada nele; durante a
        onda, só onde o chão antigo ainda aparece (a onda não chegou), se ele tinha a decoração."""
        if self._props_baked:
            return True
        if self._board_key is not None or not self._old_props:
            return False
        if self._wave_stage < 2:                            # ainda montando o chão novo: aparece o antigo inteiro
            return True
        ox, oy = state.wave_origin
        return abs(p.cell[0] - ox) + abs(p.cell[1] - oy) >= state.wave_t * config.WAVE_SPEED

    def _objects(self, state):
        spr = self.assets.spr
        objs = []
        for p in self.props:
            if p in self.far_props and self._prop_on_board(state, p):     # já está desenhada no chão
                continue
            th, pop = self._scene_theme(state, p.cell)
            objs.append(self._drawable(spr[th][f'prop_{p.variant}'], *p.cell, -math.sin(pop * math.pi) * PROP_POP))
        if self.man.fence_pieces:
            for f in self.fence:
                th, pop = self._scene_theme(state, f.pos)
                objs.append(self._drawable(spr[th][f'cerca_{f.piece}'], *f.pos, -math.sin(pop * math.pi) * PROP_POP,
                                           shadow=False))
        if state.food is not None:
            bob = math.sin(state.time * 4) * 5
            objs.append(self._drawable(self.assets.food_img[state.food_kind], *state.food, bob - 6))
        for i, (cell, kind) in enumerate(getattr(state, 'extra_food', [])):     # maçãs automáticas a mais
            bob = math.sin(state.time * 4 + 1.3 * (i + 1)) * 5
            objs.append(self._drawable(self.assets.food_img[kind], *cell, bob - 6))
        for i, b in enumerate(state.bonus_apples):          # maçãs espalhadas pelo estouro de um presente
            if not state.landed(b) or (state.blinking(b) and int(state.time * 8) % 2):
                continue
            since = state.play_time - b.lands
            bounce = abs(math.sin(since * 16)) * 16 * max(0.0, 1 - since / 0.45)
            wobble = math.sin(state.time * 9 + i) * 2 if b.kind == 'bomba' else math.sin(state.time * 4 + i) * 4
            objs.append(self._drawable(self._bonus_img(b), *b.cell, wobble - 6 - bounce))
        for i, g in enumerate(state.gifts_on_board):
            if not state.landed(g):             # na mão ou no ar: desenhado por _draw_in_air
                continue
            if state.blinking(g) and int(state.time * 8) % 2:                   # pisca antes de sumir
                continue
            bob = math.sin(state.time * 5 + 1 + i * 0.7) * 6
            since = state.play_time - g.lands                                   # quiquezinho ao cair
            bounce = abs(math.sin(since * 14)) * 22 * max(0.0, 1 - since / 0.5)
            objs.append(self._drawable(self._gift_img(g), *g.cell, bob - 8 - bounce))
        for th in self._throwers(state):        # duendes do lado da cerca (desenhados depois da cerca da linha)
            pose = self._throw_pose(state, th.items)
            phase = th.cell[1] * 0.9 + (th.name == 'mal') * 1.3                  # cada um respira no seu tempo
            breath = math.sin(state.time * 2.2 + phase) * 1.5 if pose == 'parado' else 0.0
            breath -= self._jump(state, th.name, th.cell[1])
            objs.append(self._drawable(th.poses[pose], *th.cell, breath, bias=0.6, anchor=th.char['anchor']))
        objs += self._walker_objects(state)     # duendes atravessando a faixa de baixo com a placa de obrigado
        if state.bomb_landed() and self.assets.bomb is not None:            # no ar ela é desenhada por _draw_in_air
            blink_off = state.bomb_blinking() and int(state.time * 8) % 2     # pisca rápido antes de sumir
            if not blink_off:
                wobble = math.sin(state.time * 9) * 2                         # tremidinha de pavio aceso
                since = state.play_time - state.bomb.lands
                bounce = abs(math.sin(since * 14)) * 18 * max(0.0, 1 - since / 0.5)
                objs.append(self._drawable(self.assets.bomb, *state.bomb.cell, wobble - 4 - bounce))
        objs.extend(self._snake_objects(state))
        return objs

    def _drawable(self, img, gx, gy, dy=0.0, shadow=True, bias=0.0, anchor=None):
        """Ordem de desenho: profundidade (gy na visão 3/4) e, no empate, gx."""
        return Drawable((self.man.depth(gx, gy) + bias, gx), img, gx, gy, dy, shadow, anchor)

    def _snake_spr(self, theme):
        """Sprites da cobra num tema: no tema padrão (ou com a troca desligada), os da skin escolhida."""
        if not self.snake_changes:
            theme = config.START_THEME
        if theme == config.START_THEME and self.skin in self.assets.skins:
            return self.assets.skins[self.skin]
        return self.assets.spr[theme]

    def _snake_objects(self, state):
        alpha = state.alpha
        pos = []        # posição interpolada de cada segmento
        for i, c in enumerate(state.snake):
            p = state.prev[i] if i < len(state.prev) else c
            pos.append((p[0] + (c[0] - p[0]) * alpha, p[1] + (c[1] - p[1]) * alpha))

        objs = []
        for i in range(len(pos) - 1):        # bolinhas intermediárias deixam o corpo contínuo
            mx, my = (pos[i][0] + pos[i + 1][0]) / 2, (pos[i][1] + pos[i + 1][1]) / 2
            objs.append(self._drawable(self._snake_spr(state.segment_theme(i))[f'corpo_{(i + 1) % 2}'], mx, my,
                                       shadow=False))     # a sombra fica por baixo da dos vizinhos: não precisa
        for i in range(1, len(pos) - 1):
            spr = self._snake_spr(state.segment_theme(i))
            a, b = state.snake[i - 1], state.snake[i]     # direção do segmento (rumo à cabeça): skins com barbatana
            d = DIR_FROM_DELTA.get((a[0] - b[0], a[1] - b[1]), state.dir)
            objs.append(self._drawable(spr.get(f'corpo_{i % 2}_{d}', spr[f'corpo_{i % 2}']), *pos[i]))

        t1, t0 = state.snake[-1], state.snake[-2]
        tail_dir = DIR_FROM_DELTA.get((t0[0] - t1[0], t0[1] - t1[1]), state.dir)
        objs.append(self._drawable(self._snake_spr(state.segment_theme(len(pos)))[f'cauda_{tail_dir}'], *pos[-1]))
        objs.append(self._drawable(self._snake_spr(state.theme)[f'cabeca_{state.dir}'], *pos[0], bias=0.01))
        return objs

    def _blit_object(self, img, gx, gy, dy=0.0, anchor=None):
        x, y, s = self.proj.project(gx, gy)
        img, s = self._scaled_img(img, s)
        ax, ay = anchor or self.man.obj_anchor
        self.screen.blit(img, (round(x - ax * s), round(y + (dy - ay) * s)))

    def _draw_objects(self, objs):
        """Sombras primeiro, depois os objetos de trás para a frente. Caminho rápido (são centenas por quadro com a
        cobra grande ou a arena cheia de maçãs): a projeção é feita aqui mesmo, sem chamar funções por objeto, e
        tudo vai para a tela numa chamada só (blits)."""
        p = self.proj
        mid, ax_x, ax_y, ay_x, ay_y = p.mid, p.ax, p.ay, p.bx, p.by
        pa, pk, zoom = p.a, p.k, p.zoom
        cx, cy = p.center
        step = config.SCALE_STEP
        fixed = self.perspective == 0 and zoom == 1
        cache = self._scaled
        oax, oay = self.man.obj_anchor
        seq = []
        add = seq.append

        def place(img, gx, gy, dy, anchor):
            dx, dgy = gx - mid, gy - mid
            xf, yf = dx * ax_x + dgy * ay_x, dx * ax_y + dgy * ay_y
            s = (pa + pk * yf) * zoom
            x, y = cx + xf * s, cy + (pa * yf + pk * yf * yf / 2) * zoom
            if fixed:
                sq = 1.0
            else:
                level = round(s / step)
                key = (img, level)
                scaled = cache.get(key)
                sq = level * step
                if scaled is None:
                    w, h = img.get_size()
                    scaled = cache[key] = pygame.transform.smoothscale(img, (max(1, round(w * sq)),
                                                                             max(1, round(h * sq))))
                img = scaled
            ax, ay = anchor or (oax, oay)
            add((img, (round(x - ax * sq), round(y + (dy - ay) * sq))))

        shadow = self.assets.shadow
        for o in objs:
            if o.shadow:
                place(shadow, o.gx, o.gy, 0.0, None)
        objs = sorted(objs, key=lambda o: o.key)
        for o in objs:
            place(o.img, o.gx, o.gy, o.dy, o.anchor)
        self.screen.blits(seq, doreturn=False)

    # ------------------------------------------------------------ duendes que jogam presentes e bombas
    def _winner(self, state, result):
        """Fim da partida: 'bom' (vitória: bateu a meta) ou 'mal' (derrota); None durante a partida."""
        if not state.over:
            return None
        if result is not None and result.rank_outcome is not None:
            return 'bom' if result.rank_outcome.won else 'mal'
        target = self.rank_info[1] if self.rank_info is not None else None
        return 'bom' if state.won or (target is not None and state.score >= target) else 'mal'

    def _jump(self, state, side, row):
        """Altura (px) do pulo de comemoração do duende: só o lado que venceu pula, cada um no seu ritmo."""
        if self._celebrating != side:
            return 0.0
        return abs(math.sin(state.time * 7.0 + row * 0.8)) * JUMP_HEIGHT

    def _sides(self, state):
        """As duas fileiras de duendes fora da cerca: (nome, manifest, imagens, coluna, itens, imagem do item, efeito).
        A da esquerda joga os presentes; a do mal, à direita, joga as bombas."""
        lo, hi = (-1, state.n) if self.fence_on_edge else (-2, state.n + 1)
        out = []
        if self.assets.character:
            out.append(('bom', self.man.character, self.assets.character, lo, state.gifts_on_board, self._gift_img,
                        SPARKLE_COLORS))
        if self.assets.villain:
            bombs = ([state.bomb] if state.bomb is not None else []) + list(getattr(state, 'flying_bombs', []))
            out.append(('mal', self.man.villain, self.assets.villain, hi, bombs,
                        lambda _: self.assets.bomb, SMOKE_COLORS))
        return out

    def _throwers(self, state):
        """Todos os duendes que arremessam: uma fileira inteira de cada lado. Cada item no ar sai do duende livre
        mais perto de onde ele cai (vários jogam ao mesmo tempo); os que já caíram ficam com o da linha deles. Cada
        um: (nome, manifest, poses, casa, itens que jogou, imagem do item, cores do efeito na mão)."""
        out = []
        for name, char, poses, col, items, image, effect in self._sides(state):
            rows = list(range(state.n))
            mine = {gy: [] for gy in rows}
            busy = set()
            for it in sorted(items, key=lambda it: it.thrown):
                flying = not state.landed(it)
                free = [gy for gy in rows if gy not in busy] if flying else rows
                gy = min(free or rows, key=lambda gy: (abs(gy - it.cell[1]), gy))
                if flying:
                    busy.add(gy)
                mine[gy].append(it)
            out += [Thrower(name, char, poses, (col, gy), mine[gy], image, effect) for gy in rows]
        return out

    # ------------------------------------------------------------ duendes do obrigado
    def _walkers(self, state):
        """Duendes atravessando a faixa de baixo agora: (Thanks, manifest, imagens, coluna, pulinho em px).
        O do bem anda da esquerda para a direita (sai da fileira dele) e o do mal ao contrário."""
        sides = {name: (char, poses, col) for name, char, poses, col, *_ in self._sides(state)}
        if not sides:
            return []
        lo = min(col for _, _, col in sides.values()) - 1
        hi = max(col for _, _, col in sides.values()) + 1
        walk = config.AGRADECIMENTO_CAMINHADA
        out = []
        for th in state.thanks:
            if th.side not in sides:
                continue
            p = (state.play_time - th.start) / walk
            if not 0 <= p < 1:
                continue
            char, poses, _ = sides[th.side]
            x = lo + (hi - lo) * (p if th.side == 'bom' else 1 - p)
            hop = -abs(math.sin((state.play_time - th.start) * 7.5)) * WALK_HOP
            out.append((th, char, poses, x, hop))
        return out

    def _walker_objects(self, state):
        return [self._drawable(poses['parado'], x, self.walk_row, hop, bias=0.6, anchor=char['anchor'])
                for _, char, poses, x, hop in self._walkers(state)]

    def _thanks_board(self, th):
        """Imagem pronta da placa de obrigado (em cache: o texto não muda enquanto o duende anda):
        "Obrigado, @fulano" e, embaixo, o presente (ou a bomba)."""
        key = (th.side, th.label, i18n.language())
        if key not in self._boards:
            if len(self._boards) > 40:
                self._boards.clear()
            small, big, gift = self.thanks_fonts
            who, _, what = th.label.partition(': ')
            head = [small.render(t('thanks.title') + ' ', True, MUTED),
                    big.render(who, True, LOSS if th.side == 'mal' else PINK)]
            sub = None
            if what:                                    # o ícone do presente (e "x5" se foram vários)
                m = re.match(r'^(.*?)(?: x(\d+))?$', what)
                icon = self._live_gift_icon(m.group(1), 34)
                count = gift.render(f'x{m.group(2)}', True, INK) if m.group(2) else None
                sub = pygame.Surface((icon.get_width() + (count.get_width() + 6 if count else 0), 36), pygame.SRCALPHA)
                sub.blit(icon, icon.get_rect(midleft=(0, 18)))
                if count:
                    sub.blit(count, count.get_rect(midleft=(icon.get_width() + 6, 18)))
            line_w = sum(i.get_width() for i in head)
            k = min(1.0, (BOARD_MAX_W - 36) / max(line_w, sub.get_width() if sub else 0))
            if k < 1.0:
                scale = lambda i: pygame.transform.smoothscale(i, (max(1, round(i.get_width() * k)),
                                                                   max(1, round(i.get_height() * k))))
                head, sub = [scale(i) for i in head], scale(sub) if sub else None
                line_w = sum(i.get_width() for i in head)
            line_h = max(i.get_height() for i in head)
            bw = max(line_w, sub.get_width() if sub else 0) + 36
            bh = line_h + (sub.get_height() if sub else 0) + 14
            board = rounded_rect((bw, bh), 12, BOARD_FILL, (BOARD_EDGE, 4)).copy()
            px = bw / 2 - line_w / 2
            for img in head:                                    # "Obrigado," e o @ na mesma linha
                board.blit(img, img.get_rect(midleft=(round(px), round(6 + line_h / 2))))
                px += img.get_width()
            if sub:
                board.blit(sub, sub.get_rect(midtop=(bw // 2, 6 + line_h - 2)))
            self._boards[key] = board
        return self._boards[key]

    def _draw_thanks(self, state):
        """Placa de cada duende do obrigado, na frente do corpo dele (a cabeça aparece por cima), em tamanho fixo
        na tela para ler bem."""
        for th, char, poses, gx, hop in self._walkers(state):
            img = self._thanks_board(th)
            x, y, s = self.proj.project(gx, self.walk_row)
            board = img.get_rect(centerx=round(x))
            board.top = round(max(y + hop * s - BOARD_ON_BODY * char['anchor'][1] * s, self.fence_bottom + 4))
            board.bottom = min(board.bottom, self.screen.get_height() - 4)
            self.screen.blit(img, board)

    def _gift_img(self, gift):
        """Sprite do presente (a caixa de presente para os da live que não existem no jogo)."""
        return self.assets.food_img.get(gift.kind) or self.assets.food_img.get(CAIXA) or self.assets.food_img['rosa']

    @staticmethod
    def _phases(item):
        """Fim de cada etapa do arremesso (surgir, preparar), já no ritmo do item."""
        surge = config.PRESENTE_SURGE * item.pace
        return surge, surge + config.PRESENTE_PREPARA * item.pace

    def _throw_pose(self, state, items):
        """Pose pelo último item jogado: segura (surgindo na mão); prepara (braço para trás); joga (soltou)."""
        if not items:
            return 'parado'
        item = max(items, key=lambda it: it.thrown)
        phase = state.play_time - item.thrown
        surge, ready = self._phases(item)
        if phase < surge:
            return 'segura'
        if phase < ready:
            return 'prepara'
        return 'joga' if state.play_time < item.lands + 0.25 else 'parado'

    def _hand_on_screen(self, th, pose):
        """Onde fica o item na mão do duende naquela pose (pixel da tela) e a escala ali."""
        x, y, s = self.proj.project(*th.cell)
        (ax, ay), (hx, hy) = th.char['anchor'], th.char['hand'][pose]
        return x + (hx - ax) * s, y + (hy - ay) * s, s

    def _item_icon(self, img, scale, angle=0.0):
        """Sprite recortado, no tamanho que ele tem na arena com essa escala (e girado)."""
        icon = self._legend_icon(img, max(4, round(self._bbox(img).height * scale)))
        if not angle:
            return icon
        step = round(angle / ICON_ANGLE_STEP) % round(360 / ICON_ANGLE_STEP)     # giro em passos, com cache
        key = (icon, step)
        if key not in self._rotated:
            if len(self._rotated) > 4000:
                self._rotated.clear()
            self._rotated[key] = pygame.transform.rotate(icon, step * ICON_ANGLE_STEP)
        return self._rotated[key]

    def _bbox(self, img):
        """Retângulo da parte visível do sprite (em cache: get_bounding_rect varre a imagem toda)."""
        box = self._bboxes.get(img)
        if box is None:
            box = self._bboxes[img] = img.get_bounding_rect()
        return box

    def _draw_in_air(self, state):
        """Itens surgindo na mão do duende (com brilho ou fumaça), indo para trás e voando em arco até a casa."""
        for th in self._throwers(state):
            for item in th.items:
                if state.play_time < item.lands:
                    self._draw_throw(state, th, item)


    def _draw_bursts(self, state):
        """Presente comido estourando (anel de brilho e faíscas), as maçãs voando em arco até as casas delas e as
        maçãs extras sumindo (encolhem e somem) quando a cobra pega a bomba."""
        oax, oay = self.man.obj_anchor
        for cell, kind, born in state.vanished:
            k = (state.time - born) / 0.4
            if not 0 <= k < 1:
                continue
            img = self.assets.food_img.get(kind) or self.assets.food_img[config.ALIMENTO_PADRAO]
            box = self._bbox(img)
            x, y, s = self.proj.project(*cell)
            icon = self._item_icon(img, s * (1 - k) * (1 + 0.3 * math.sin(k * math.pi)))
            icon.set_alpha(round(255 * (1 - k)))
            self.screen.blit(icon, icon.get_rect(center=(round(x + (box.centerx - oax) * s),
                                                         round(y + (box.centery - oay - 6) * s - 20 * k * s))))
            r = round((10 + 30 * k) * s)
            pygame.draw.circle(self.screen, (200, 190, 200), (round(x), round(y - 30 * s)), r, max(1, round(4 * (1 - k))))
        for cell, born in state.bursts:
            k = (state.time - born) / 0.6
            if not 0 <= k < 1:
                continue
            x, y, s = self.proj.project(*cell)
            y -= 40 * s
            ring = self._burst_ring(k, s)
            self.screen.blit(ring, ring.get_rect(center=(round(x), round(y))))
            for i in range(10):
                a = i * 2 * math.pi / 10 + born
                d = (15 + 80 * ease_out(k)) * s
                px, py = x + math.cos(a) * d, y + math.sin(a) * d * 0.7 - 30 * k * s
                size = (9 * (1 - k) + 2) * s
                col = SPARKLE_COLORS[i % 2]
                pts = [(px + math.cos(b) * (size if j % 2 == 0 else size * 0.3), py + math.sin(b) * (size if j % 2 == 0 else size * 0.3))
                       for j, b in enumerate(math.pi / 4 * j - math.pi / 2 for j in range(8))]
                pygame.draw.polygon(self.screen, col, pts)
        oax, oay = self.man.obj_anchor
        for b in state.bonus_apples:
            if state.landed(b) or state.play_time < b.born:
                continue
            t = min(1.0, (state.play_time - b.born) / max(1e-6, b.lands - b.born))
            img = self._bonus_img(b)
            box = self._bbox(img)
            x0, y0, s0 = self.proj.project(*b.origin)
            x1, y1, s1 = self.proj.project(*b.cell)
            self._blit_object(self.assets.shadow, b.origin[0] + (b.cell[0] - b.origin[0]) * t,
                              b.origin[1] + (b.cell[1] - b.origin[1]) * t)
            s = s0 + (s1 - s0) * t
            arc = (60 + 0.35 * math.hypot(x1 - x0, y1 - y0)) * 4 * t * (1 - t) * s
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t - arc + (box.centery - oay - 6) * s
            icon = self._item_icon(img, s, angle=360 * t)
            self.screen.blit(icon, icon.get_rect(center=(round(x + (box.centerx - oax) * s), round(y))))

    def _burst_ring(self, k, s):
        """Anel de brilho do presente estourando, no momento k (0..1) e na escala s (em cache, em passos)."""
        kq, size = round(k * 24), max(1, round(240 * s))
        key = (kq, size)
        if key not in self._rings:
            if len(self._rings) > 600:
                self._rings.clear()
            k = kq / 24
            ring = pygame.Surface((240, 240), pygame.SRCALPHA)
            pygame.draw.circle(ring, (255, 236, 160, round(200 * (1 - k))), (120, 120), round(20 + 95 * ease_out(k)),
                               max(1, round(10 * (1 - k))))
            self._rings[key] = pygame.transform.smoothscale(ring, (size, size))
        return self._rings[key]

    def _bonus_img(self, b):
        """Sprite de um item espalhado por um presente: a maçã dele ou a bomba (da caixa de presente)."""
        if b.kind == 'bomba' and self.assets.bomb is not None:
            return self.assets.bomb
        return self.assets.food_img.get(b.kind) or self.assets.food_img[config.ALIMENTO_PADRAO]

    def _draw_throw(self, state, th, item):
        img = th.image(item)
        phase = state.play_time - item.thrown
        surge, ready = self._phases(item)
        if phase < surge:                                               # surge na mão
            k = phase / surge
            x, y, s = self._hand_on_screen(th, 'segura')
            self._draw_sparkles((x, y), s, k, th.effect)
            grow = ease_out_back(k)
            if grow > 0.05:
                icon = self._item_icon(img, s * grow * GIFT_IN_HAND)
                self.screen.blit(icon, icon.get_rect(center=(round(x), round(y))))
            return
        if phase < ready:                                               # braço para trás
            x, y, s = self._hand_on_screen(th, 'prepara')
            icon = self._item_icon(img, s * GIFT_IN_HAND)
            self.screen.blit(icon, icon.get_rect(center=(round(x), round(y))))
            return
        t = min(1.0, (phase - ready) / (config.PRESENTE_VOO * item.pace))
        x0, y0, s0 = self._hand_on_screen(th, 'joga')
        gx, gy = item.cell                                              # onde ele vai ficar na arena
        x1, y1, s1 = self.proj.project(gx, gy)
        box = self._bbox(img)
        oax, oay = self.man.obj_anchor
        x1, y1 = x1 + (box.centerx - oax) * s1, y1 + (box.centery - oay - 6) * s1
        cx, cy = th.cell                                                # sombra correndo pelo chão
        self._blit_object(self.assets.shadow, cx + (gx - cx) * t, cy + (gy - cy) * t)
        arc = (70 + 0.3 * math.hypot(x1 - x0, y1 - y0)) * 4 * t * (1 - t) * s1
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t - arc
        spin = -360 * t if th.name == 'bom' else 360 * t                # cada um gira para um lado
        icon = self._item_icon(img, s0 * GIFT_IN_HAND + (s1 - s0 * GIFT_IN_HAND) * t, angle=spin)
        self.screen.blit(icon, icon.get_rect(center=(round(x), round(y))))

    def _draw_sparkles(self, center, s, k, colors):
        """Estrelinhas (ou fumacinha, no duende do mal) girando em volta da mão enquanto o item aparece."""
        cx, cy = center
        fade = max(0.0, 1 - k)
        for i in range(5):
            a = i * 2 * math.pi / 5 + k * 4
            r = (16 + 22 * k) * s
            size = (7 + 5 * math.sin(k * 9 + i)) * s * (0.4 + 0.6 * fade)
            px, py = cx + math.cos(a) * r, cy + math.sin(a) * r * 0.8
            col = colors[i % len(colors)]
            if size <= 1:
                continue
            if colors is SMOKE_COLORS:                                      # fumaça: bolinhas que crescem
                pygame.draw.circle(self.screen, col, (round(px), round(py)), round(size * (1 + k)))
            else:
                pts = [(px + math.cos(b) * (size if j % 2 == 0 else size * 0.3),
                        py + math.sin(b) * (size if j % 2 == 0 else size * 0.3))
                       for j, b in enumerate(math.pi / 4 * j - math.pi / 2 for j in range(8))]
                pygame.draw.polygon(self.screen, col, pts)

    def _popup_img(self, points, kind=None):
        if (points, kind) not in self._popup_imgs:
            text = f'{points:+d}'
            fg = self.popup_font.render(text, True, popup_color(points, kind))
            outline = self.popup_font.render(text, True, POPUP_OUTLINE)
            img = pygame.Surface((fg.get_width() + 6, fg.get_height() + 6), pygame.SRCALPHA)
            for dx in (-3, 0, 3):
                for dy in (-3, 0, 3):
                    img.blit(outline, (3 + dx, 3 + dy))
            img.blit(fg, (3, 3))
            self._popup_imgs[points, kind] = img
        return self._popup_imgs[points, kind]

    def _draw_popups(self, state):
        """"+N" subindo de onde a cobra comeu, sumindo no final."""
        for p in state.popups:
            age = min(max((state.time - p.born) / config.POPUP_SEGUNDOS, 0.0), 1.0)
            rise = 1 - (1 - age) ** 2                   # sobe rápido e desacelera
            x, y, s = self.proj.project(*p.cell)
            img, s = self._scaled_img(self._popup_img(p.points, p.kind), s)
            img.set_alpha(round(255 * min(1.0, (1 - age) / 0.4)))   # some nos últimos 40%
            self.screen.blit(img, (round(x - img.get_width() / 2),
                                   round(y - (POPUP_LIFT + POPUP_RISE * rise) * s - img.get_height() / 2)))

    # ------------------------------------------------------------ interface (estilo chapado, como o perfil)
    def _text(self, font, text, color, center, max_w=None, anchor='center'):
        """Texto em `center` (ou no ponto `anchor`); com max_w, encolhe o que não couber (textos traduzidos)."""
        img = font.render(text, True, color)
        if max_w is not None and img.get_width() > max_w:
            k = max_w / img.get_width()
            img = pygame.transform.smoothscale(img, (round(max_w), max(1, round(img.get_height() * k))))
        rect = img.get_rect(**{anchor: (round(center[0]), round(center[1]))})
        self.screen.blit(img, rect)
        return rect

    def _draw_hud(self, state, result=None):
        self._draw_score_card(state)
        if state.over:
            self._draw_game_over(state, result)

    def _draw_score_card(self, state):
        """Placar: cartão branco com caixinhas de pontos, recorde, presentes e tempo.

        O botão > na ponta abre, no mesmo cartão, quanto vale cada presente (sem cobrir o tabuleiro).
        Embaixo, o elo da arena e a dica dos controles.
        """
        beating = state.score > self.best_score             # passou o recorde nesta partida
        cols = [(str(state.score), t('hud.points'), PINK),
                (str(max(self.best_score, state.score)), t('hud.best'), PINK if beating else INK),
                (str(state.eaten), t('hud.gifts'), INK), (format_time(state.play_time), t('hud.time'), INK)]
        rows = self._gift_rows(state) if self.legend_open else []
        cw, ch = HUD_CHIP
        inner = len(cols) * (cw + HUD_GAP) + HUD_TOGGLE_W
        if self.live_info is not None:                          # bolinha do estado da live, no fim do cartão
            inner += HUD_LIVE_DOT_W
        if rows:
            inner += HUD_GAP + 1 + len(rows) * (HUD_GIFT_W + HUD_GAP) + sum(HUD_BOMB_GIFT_W for r in rows if r[4])
        x, y = HUD_POS
        box = card(self.screen, (x, y, inner + 2 * HUD_PAD, ch + 2 * HUD_PAD), 18)
        cx, cy = x + HUD_PAD, y + HUD_PAD
        for value, label, color in cols:
            self.screen.blit(rounded_rect(HUD_CHIP, 12, STAT_FILL), (cx, cy))
            self._text(self.value_font, value, color, (cx + 12, cy + 5), max_w=cw - 18, anchor='topleft')
            self._text(self.chip_font, label, MUTED, (cx + 12, cy + 38), max_w=cw - 18, anchor='topleft')
            cx += cw + HUD_GAP
        if rows:
            pygame.draw.line(self.screen, CARD_BORDER, (cx, cy + 6), (cx, cy + ch - 6))
            cx += 1 + HUD_GAP
            apple_icon = self._legend_icon(self.assets.food_img[config.ALIMENTO_PADRAO], 13)
            for img, label, color, apples, gift in rows:
                w = HUD_GIFT_W + (HUD_BOMB_GIFT_W if gift else 0)
                icon = self._legend_icon(img, 30)
                if gift:                                        # "presente escolhido = bomba"
                    self.screen.blit(gift, gift.get_rect(center=(cx + 18, cy + 22)))
                    self._text(self.chip_bold, '=', MUTED, (cx + 41, cy + 22))
                    self.screen.blit(icon, icon.get_rect(center=(cx + w - 22, cy + 22)))
                else:
                    self.screen.blit(icon, icon.get_rect(center=(cx + w // 2, cy + 22)))
                text = self._text(self.chip_bold, label, color,
                                  (cx + w / 2 - (8 if apples else 0), cy + 50))
                if apples:                                      # "10x 🍎": quantas maçãs o presente espalha
                    self.screen.blit(apple_icon, apple_icon.get_rect(midleft=(text.right + 2, text.centery)))
                cx += w + HUD_GAP
        toggle = pygame.Rect(cx, cy, HUD_TOGGLE_W, ch)          # > abre, < fecha
        hover = self.mouse is not None and toggle.collidepoint(self.mouse)
        self.screen.blit(rounded_rect(toggle.size, 12, HOVER_FILL if hover else STAT_FILL), toggle)
        k = 6
        tx, ty = toggle.center
        pts = [(tx - k / 2, ty - k), (tx + k / 2, ty), (tx - k / 2, ty + k)]
        if self.legend_open:
            pts = [(2 * tx - px, py) for px, py in pts]
        pygame.draw.lines(self.screen, INK, False, pts, 3)
        self.buttons.append((toggle, 'legend'))
        if self.live_info is not None:                          # verde conectado, amarela conectando, vermelha fora
            status = self.live_info[1][0]
            dot = {'conectado': (46, 204, 113), 'conectando': (255, 196, 0)}.get(status, LOSS)
            center = (toggle.right + HUD_LIVE_DOT_W // 2 + 2, toggle.centery)
            pygame.draw.circle(self.screen, CARD_BORDER, center, 10)
            pygame.draw.circle(self.screen, dot, center, 8)

        y = box.bottom + 12
        if self.rank_info is not None:                          # elo da arena
            r, target = self.rank_info
            icon = self._shield(r, 28) if self.assets.shields else None
            line = self.label_font.render(t('rank.hud', name=rank_label(r), pdl=r.pdl, target=target), True, INK)
            iw = icon.get_width() + 8 if icon else 0
            pill = card(self.screen, (x, y, 14 + iw + line.get_width() + 18, 40), 20)
            if icon:
                self.screen.blit(icon, icon.get_rect(midleft=(pill.left + 12, pill.centery)))
            self.screen.blit(line, line.get_rect(midleft=(pill.left + 14 + iw, pill.centery + 1)))
            if state.apples_to_reset and not self.minimal_hud:  # transformada: quanto falta, ao lado do elo
                self._draw_reset_progress(state, pill.right + 10, pill.top, pill.height)
            y = pill.bottom + 10
        elif state.apples_to_reset and not self.minimal_hud:
            y = self._draw_reset_progress(state, x, y, 40) + 10
        if self.minimal_hud:
            return
        if self.autopilot or state.practice:                    # robô jogando / partida de treino
            text = self.label_bold.render(t('robot.on' if self.autopilot else 'robot.practice'), True, WHITE)
            pill = pygame.Rect(x, y, text.get_width() + 28, 34)
            self.screen.blit(rounded_rect(pill.size, 17, PINK if self.autopilot else HINT_FILL), pill)
            self.screen.blit(text, text.get_rect(center=(pill.centerx, pill.centery + 1)))
            y = pill.bottom + 10

    def _draw_reset_progress(self, state, x, y, height=40):
        """Pílula "faltam N maçãs para voltar ao normal", com a maçã e uma barrinha de progresso (da altura da
        pílula do elo, ao lado dela)."""
        left = state.apples_to_reset
        text = self.small.render(t('hud.reset', n=left), True, INK)
        icon = self._legend_icon(self.assets.food_img[config.ALIMENTO_PADRAO], 22)
        w = 14 + icon.get_width() + 8 + max(text.get_width(), 120) + 18
        pill = card(self.screen, (x, y, w, height), 20)
        self.screen.blit(icon, icon.get_rect(midleft=(pill.left + 12, pill.centery)))
        tx = pill.left + 14 + icon.get_width() + 8
        self.screen.blit(text, (tx, pill.top + 5))
        done = 1 - left / state.apples_to_reset_total
        bar(self.screen, (tx, pill.bottom - 11, w - (tx - pill.left) - 16, 5), done, PINK)
        return pill.bottom

    def _gift_rows(self, state):
        """(imagem, texto, cor, mostra maçã) de cada presente (quantas maçãs ele espalha), da maçã do elo da
        partida (valor x tamanho) e da bomba (- valor x tamanho), por último."""
        apple = max(apple_weights(state.apple_tier, self.assets.food_img).items(), key=lambda kv: kv[1])[0]
        rows = [(self.assets.food_img[f], f'{state.gift_apples(f)}x', PINK, True, None) for f in self.man.foods
                if not is_apple(f)]
        rows.append((self.assets.food_img[apple], f'×{points_for(apple)}', PINK, False, None))
        if self.assets.bomb is not None:                # na live: o presente que vira bomba, antes dela
            gift = self._bomb_gift_icon(30) if state.live else None
            rows.append((self.assets.bomb, f'-{config.BOMBA_PENALIDADE}', LOSS, False, gift))
        return rows

    def _bomb_gift_icon(self, size):
        """Ícone do presente da live escolhido como bomba (configurações da live)."""
        return self._live_gift_icon(self.prefs.get('live_bomba') or config.LIVE_BOMBA_PADRAO, size)

    def _live_gift_icon(self, name, size):
        """Ícone de um presente da live pelo nome: o do TikTok (baixado ao conectar); sem ele, o do jogo (se o
        presente existe no jogo); senão, uma moedinha com a inicial. Em cache."""
        key = (live._key(name), size)
        if key not in self._gift_icons:
            if len(self._gift_icons) > 60:
                self._gift_icons.clear()
            item = next((i for i in live.load_catalog() if live._key(i['nome']) == live._key(name)), None)
            path = live.image_path(item['imagem']) if item and item.get('imagem') else None
            icon = None
            if path and os.path.exists(path):
                try:
                    icon = pygame.transform.smoothscale(pygame.image.load(path).convert_alpha(), (size, size))
                except (pygame.error, OSError):
                    icon = None
            kind = {live._key(k): v for k, v in config.LIVE_PRESENTES.items()}.get(live._key(name))
            if icon is None and kind in self.assets.food_img:          # presente do jogo: o desenho dele
                icon = self._legend_icon(self.assets.food_img[kind], size)
            if icon is None:                            # moedinha com a inicial do presente
                icon = pygame.Surface((size, size), pygame.SRCALPHA)
                pygame.draw.circle(icon, (255, 200, 60), (size // 2, size // 2), size // 2 - 1)
                pygame.draw.circle(icon, (230, 160, 20), (size // 2, size // 2), size // 2 - 1, width=2)
                letter = fonte('Bold', size // 2).render(name[:1].upper(), True, WHITE)
                icon.blit(letter, letter.get_rect(center=(size // 2, size // 2 + 1)))
            self._gift_icons[key] = icon
        return self._gift_icons[key]

    def _legend_icon(self, img, size):
        """Sprite de comida recortado e reduzido para caber numa caixa de `size` px (com cache)."""
        key = (img, size)
        if key not in self._legend_icons:
            sprite = img.subsurface(self._bbox(img))
            k = min(size / sprite.get_height(), size * 1.3 / sprite.get_width())
            self._legend_icons[key] = pygame.transform.smoothscale(
                sprite, (max(1, round(sprite.get_width() * k)), max(1, round(sprite.get_height() * k))))
        return self._legend_icons[key]

    def _overlay_card(self, size=OVERLAY_SIZE):
        """Escurece o jogo e desenha o cartão branco central; devolve a área de conteúdo (x, y, w, h)."""
        dim = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        dim.fill(DIM)
        self.screen.blit(dim, (0, 0))
        sw, sh = self.screen.get_size()
        rect = pygame.Rect(0, 0, min(size[0], sw - 40), min(size[1], sh - 40))
        rect.center = (sw // 2, sh // 2)
        card(self.screen, rect, 24)
        px, py = OVERLAY_PAD
        return rect.left + px, rect.top + py, rect.width - 2 * px, rect.height - 2 * py

    def _draw_game_over(self, state, result=None):
        """Quadro de fim de jogo: ranque, nome do recorde, resumo ou tabela."""
        box = self._overlay_card()
        phase = result.phase if result is not None else 'resumo'
        if phase == 'ranque':
            self._draw_rank(state, result, box)
        elif phase == 'nome':
            self._draw_name_entry(state, result, box)
        elif phase == 'tabela':
            self._draw_records(result, box)
        elif phase == 'top':
            self._draw_live_podium(result, box)
        else:
            self._draw_summary(state, result, box)

    def _chip(self, center, size, value, label, value_color=INK):
        """Caixinha de estatística (como as do perfil): valor em cima, legenda embaixo."""
        rect = pygame.Rect(0, 0, *size)
        rect.center = (round(center[0]), round(center[1]))
        self.screen.blit(rounded_rect(rect.size, 14, STAT_FILL), rect)
        self._text(self.value_font, value, value_color, (rect.centerx, rect.top + 10), rect.width - 20, 'midtop')
        self._text(self.chip_font, label, MUTED, (rect.centerx, rect.bottom - 10), rect.width - 20, 'midbottom')

    # ------------------------------------------------------------ ranque
    def _shield(self, r, height):
        """Escudo chapado da liga do elo `r`, reduzido para `height` px de altura (com cache)."""
        key = (rank.tier_id(r), height)
        if key not in self._shields:
            full = self.assets.shields[key[0]]
            full = full.subsurface(full.get_bounding_rect())
            k = height / full.get_height()
            self._shields[key] = pygame.transform.smoothscale(full, (max(1, round(full.get_width() * k)), height))
        return self._shields[key]

    @staticmethod
    def rank_timeline(outcome, elapsed):
        """Estado da animação: (elo mostrado, PDL na barra, último evento ou None, quando ele aconteceu)."""
        steps = outcome.steps
        shown, pdl, event, when = steps[0].rank, steps[0].pdl_from, None, None
        start = RANK_BAR_START
        for i, st in enumerate(steps):
            if elapsed < start:
                break
            frac = (elapsed - start) / RANK_STEP
            shown, pdl = st.rank, st.pdl_from + (st.pdl_to - st.pdl_from) * ease_out(frac)
            if frac >= 1 and st.event:
                event, when = st.event, start + RANK_STEP
                if i + 1 < len(steps):                  # já mostra o elo novo, com a barra do começo
                    shown, pdl = steps[i + 1].rank, steps[i + 1].pdl_from
            start += RANK_STEP + (RANK_PAUSE if st.event else 0)
        return shown, pdl, event, when

    def _draw_rank(self, state, result, box):
        """Elo da arena: escudo, cálculo dos PDL, barra animada e comemoração ao subir."""
        bx, by, bw, bh = box
        out = result.rank_outcome
        el = state.time - result.started
        shown, pdl, event, when = self.rank_timeline(out, el)
        since = el - when if when is not None else None
        cx = bx + bw / 2
        unit = t('rank.unit')

        # título: resultado da partida; depois de subir/cair, a mensagem do novo elo
        if event == 'sobe':
            league_up = shown.tier > out.before.tier
            title = t('rank.new_league', name=t('tier.' + rank.tier_id(shown))) if league_up else \
                t('rank.promoted', name=rank_label(shown))
            color, k = PINK, 1 + 0.35 * max(0.0, 1 - since / 0.35)
        elif event == 'cai':
            title, color, k = t('rank.demoted', name=rank_label(shown)), LOSS, 1.0
        else:
            title, color, k = t('rank.win' if out.won else 'rank.loss'), PINK if out.won else LOSS, 1.0
        img = self.title_font.render(title, True, color)
        w = min(img.get_width() * k, bw)
        img = pygame.transform.smoothscale(img, (round(w), round(img.get_height() * w / img.get_width())))
        self.screen.blit(img, img.get_rect(center=(round(cx), round(by + 26))))

        # escudo (dá um pulo quando troca) e o nome do elo
        pop = 1 + 0.25 * max(0.0, 1 - since / 0.45) if since is not None else 1.0
        sx = bx + bw * 0.17
        icon = self._shield(shown, round(120 * pop))
        self.screen.blit(icon, icon.get_rect(center=(round(sx), round(by + bh * 0.34))))
        self._text(self.font, rank_label(shown), INK, (sx, by + bh * 0.55), max_w=bw * 0.32)

        # cálculo, uma linha de cada vez
        good = PINK if out.won else LOSS
        rows = [(t('rank.points'), f'{out.score} / {out.target}', good),
                (t('rank.victory' if out.won else 'rank.defeat'), f'{out.base:+d} {unit}', good)]
        if out.won:
            rows.append((t('rank.above', n=out.diff, p=out.margin), f'{out.margin:+d} {unit}', PINK))
        else:
            rows.append((t('rank.missing', n=-out.diff, p=-out.margin), f'{out.margin:+d} {unit}', LOSS))
        if out.time_bonus:
            minutes = f'{out.minutes:.1f}'.replace('.', ',' if i18n.language() == 'pt' else '.')
            rows.append((t('rank.time', m=minutes, g=out.gifts), f'{out.time_bonus:+d} {unit}', PINK))
        if out.bombs:
            rows.append((t('rank.bombs', n=out.bombs), f'{-out.bomb_penalty:+d} {unit}', LOSS))
        if out.record_bonus:
            rows.append((t('rank.record', n=out.record_pos + 1), f'{out.record_bonus:+d} {unit}', PINK))
        rows.append((t('rank.total'), f'{out.delta:+d} {unit}', PINK if out.delta >= 0 else LOSS))
        xl, xr = bx + bw * 0.36, bx + bw
        top, bottom = by + bh * 0.16, by + bh * 0.6                # as linhas cabem entre o título e a barra
        row_step = min(36, (bottom - top) / (len(rows) - 0.4))
        for i, (label, value, vcolor) in enumerate(rows):
            if el < RANK_REVEAL[min(i, len(RANK_REVEAL) - 1)]:
                break
            last = i == len(rows) - 1
            y = top + row_step * (i + 0.5) + (row_step * 0.4 if last else 0)
            if last:                                            # linha do total
                ly = round(y - row_step * 0.6)
                pygame.draw.line(self.screen, CARD_BORDER, (round(xl), ly), (round(xr), ly), 2)
            val = (self.value_font if last else self.label_bold).render(value, True, vcolor)
            lab = (self.label_bold if last else self.label_font).render(label, True, INK if last else MUTED)
            room = xr - xl - val.get_width() - 12                   # o rótulo encolhe para não encostar no valor
            if lab.get_width() > room:
                k = room / lab.get_width()
                lab = pygame.transform.smoothscale(lab, (round(room), max(1, round(lab.get_height() * k))))
            self.screen.blit(lab, lab.get_rect(midleft=(round(xl), round(y))))
            self.screen.blit(val, val.get_rect(midright=(round(xr), round(y))))

        # barra de PDL e, embaixo, os PDL e o XP ganho
        full = config.RANQUE_PDL_DIVISAO
        track = pygame.Rect(round(bx), round(by + bh * 0.7), round(bw), 10)
        bar(self.screen, track, 1.0 if rank.is_top(shown) else min(max(pdl, 0), full) / full, PINK)
        label = t('rank.bar_master', pdl=round(pdl)) if rank.is_top(shown) else t('rank.bar', pdl=round(pdl), total=full)
        self._text(self.chip_font, label, MUTED, (track.left, track.bottom + 8), anchor='topleft')
        if result.xp_info is not None and el >= RANK_BAR_START:    # XP ganho (ganhando ou perdendo) e o nível
            gain, level_before, (level, _, _) = result.xp_info
            up = level > level_before
            line = t('rank.level_up' if up else 'rank.xp', xp=gain, level=level)
            self._text(self.label_bold, line, PINK if up else INK, (track.right, track.bottom + 6), max_w=bw * 0.6,
                       anchor='topright')

        if result.new_skin and event == 'sobe' and shown.tier > out.before.tier:     # chegou na liga da skin
            self._draw_skin_unlocked(result.new_skin, (cx, by + bh * 0.83), bw)
        if event == 'sobe' and since < 3.0:
            self._draw_confetti(result, since, box)
        self._button_row([(t('rank.continue'), 'continue')], box)

    def _draw_skin_unlocked(self, skin, center, max_w):
        """Etiqueta rosa clara com o retrato da skin nova: "Skin Prata liberada e equipada!"."""
        text = self.label_bold.render(t('rank.skin_unlocked', name=t(f'skin.{skin}')), True, PINK)
        icon = self._legend_icon(self.assets.avatars[skin], 28) if skin in self.assets.avatars else None
        iw = icon.get_width() + 10 if icon else 0
        pill = pygame.Rect(0, 0, min(max_w, 28 + iw + text.get_width()), 34)
        pill.center = (round(center[0]), round(center[1]))
        self.screen.blit(rounded_rect(pill.size, 17, PINK_LIGHT), pill)
        x = pill.left + 14
        if icon:
            self.screen.blit(icon, icon.get_rect(midleft=(x, pill.centery)))
            x += iw
        self.screen.blit(text, text.get_rect(midleft=(x, pill.centery + 1)))

    def _draw_confetti(self, result, since, box):
        """Confete caindo sobre o quadro depois de subir de elo."""
        bx, by, bw, bh = box
        if self._confetti[0] is not result:                      # partículas novas para cada resultado
            rnd = random.Random(id(result))
            self._confetti = (result, [(rnd.uniform(-0.1, 1.1), rnd.uniform(0.0, 0.5), rnd.uniform(220, 380),
                                        rnd.uniform(-70, 70), rnd.uniform(7, 12), rnd.choice(CONFETTI), rnd.uniform(0, 6))
                                       for _ in range(90)])
        for x0, delay, vy, vx, size, color, phase in self._confetti[1]:
            dt = since - delay
            if dt <= 0:
                continue
            x = bx + bw * x0 + vx * dt
            y = by - 40 + vy * dt + 90 * dt * dt
            if y > by + bh + 40:
                continue
            w = 2 + size * abs(math.sin(dt * 7 + phase))            # "gira" mudando a largura
            pygame.draw.rect(self.screen, color, pygame.Rect(round(x), round(y), round(w), round(size * 0.6)),
                             border_radius=2)

    def _draw_pause(self, state):
        """Menu de pausa: perfil com o elo da arena, volumes do som, aviso dos PDL e os botões continuar/sair."""
        self.buttons = []                               # só os botões da pausa valem agora
        bx, by, bw, bh = self._overlay_card(PAUSE_SIZE)
        self._text(self.title_font, t('pause.title'), INK, (bx + bw / 2, by + 26), max_w=bw)

        # perfil: cabeça da cobra (skin em uso) e nome
        cx, cy = bx + bw * 0.25, by + 162
        self.screen.blit(circle(58, PINK_LIGHT), (round(cx) - 58, round(cy) - 58))
        head = self._legend_icon(self.assets.avatars.get(self.skin, self._snake_spr(config.START_THEME)['cabeca_S']), 84)
        self.screen.blit(head, head.get_rect(center=(round(cx), round(cy))))
        self._text(self.font, self.player_name, INK, (cx, cy + 86), max_w=bw * 0.42)

        # elo da arena: escudo, nome, barra de PDL e a meta
        if self.rank_info is not None:
            r, target = self.rank_info
            rx = bx + bw * 0.5
            if self.assets.shields:
                icon = self._shield(r, 64)
                self.screen.blit(icon, icon.get_rect(midleft=(round(rx), round(cy - 30))))
                tx = rx + icon.get_width() + 14
            else:
                tx = rx
            self._text(self.font, rank_label(r), INK, (tx, cy - 30), max_w=bx + bw - tx, anchor='midleft')
            full = config.RANQUE_PDL_DIVISAO
            track = pygame.Rect(round(rx), round(cy + 22), round(bx + bw - rx), 8)
            bar(self.screen, track, 1.0 if rank.is_top(r) else min(r.pdl, full) / full, INK)
            pdl = t('rank.bar_master', pdl=r.pdl) if rank.is_top(r) else t('rank.bar', pdl=r.pdl, total=full)
            self._text(self.chip_font, pdl, MUTED, (track.left, track.bottom + 8), anchor='topleft')
            chips = [(str(target), t('pause.goal'), INK), (str(state.score), t('pause.score'),
                                                            PINK if state.score >= target else INK),
                     (f'{state.n}×{state.n}', t('pause.arena'), INK)]
            w = (bw - 2 * 12) / 3
            for i, (value, label, color) in enumerate(chips):
                self._chip((bx + w / 2 + i * (w + 12), by + 327), (round(w), 74), value, label, color)

        # som: geral, música e efeitos (− e +)
        for i, (name, key) in enumerate(settings.VOLUMES.items()):
            def button(rect, text, name=name):
                hover = self.mouse is not None and rect.collidepoint(self.mouse)
                flat_button(self.screen, rect, text, self.button_font, 'hover' if hover else 'normal', primary=False)
                self.buttons.append((rect, f"vol_{name}_{'down' if text == '−' else 'up'}"))
            label = t('sound.master' if name == 'geral' else 'sound.music' if name == 'musica' else 'sound.sfx')
            volume_row(self.screen, (round(bx), round(by + 384 + 44 * i), round(bw), 38), label,
                       self.prefs.get(key, settings.VOLUME_MAX), self.label_bold, button, settings.VOLUME_MAX)

        # aviso: sair agora não dá os PDL desta partida
        warn = pygame.Rect(round(bx), round(by + 524), round(bw), 36)
        self.screen.blit(rounded_rect(warn.size, 12, LOSS_LIGHT), warn)
        self._text(self.label_bold, t('pause.warning'), LOSS, warn.center, max_w=warn.width - 24)
        self._button_row([(t('pause.resume'), 'resume'), (t('pause.leave'), 'leave')], (bx, by, bw, bh), y_frac=0.95)

    def _draw_summary(self, state, result, box):
        bx, by, bw, bh = box
        cx = bx + bw / 2
        if result is not None and result.practice:
            title, color = t('over.practice'), INK
        elif result is not None and result.rank is not None:
            title = t('over.new_record') if result.is_best else t('over.rank', n=result.rank + 1)
            color = PINK
        else:
            title, color = t('over.win' if state.won else 'over.lose'), PINK if state.won else INK
        self._text(self.title_font, title, color, (cx, by + 26), max_w=bw)
        ys = (0.22, 0.36, 0.6, (176, 78))
        self._text(self.chip_font, t('over.points'), MUTED, (cx, by + bh * ys[0]))
        self._text(self.big_font, str(state.score), PINK, (cx, by + bh * ys[1]))
        stats = [(str(state.eaten), t('hud.gifts')), (format_time(state.play_time), t('hud.time'))]
        for i, (value, label) in enumerate(stats):
            self._chip((cx + (i - 0.5) * (ys[3][0] + 14), by + bh * ys[2]), ys[3], value, label)
        if result is not None and result.save_error:
            self._text(self.small, t('over.save_error'), LOSS, (cx, by + bh * 0.76), max_w=bw)
        if result is not None and result.can_show_table:
            self._button_row([(t('btn.records'), 'records'), (t('btn.again'), 'restart'), (t('btn.menu'), 'menu')], box)
        else:
            self._button_row([(t('btn.again'), 'restart'), (t('btn.menu'), 'menu')], box)

    def _draw_live_podium(self, result, box):
        """Fim da partida do robô: quem mais mandou presentes, um retângulo por lugar (dourado, prateado e bronze)
        com a foto do espectador à esquerda e, à direita, o @ e embaixo o total de presentes."""
        bx, by, bw, bh = box
        cx = bx + bw / 2
        self._text(self.title_font, t('live.top_title'), INK, (cx, by + 26), max_w=bw)
        top = result.supporters[:3]
        self._button_row([(t('rank.continue'), 'continue')], box)
        if not top:
            self._text(self.label_bold, t('live.top_empty'), MUTED, (cx, by + bh * 0.42), max_w=bw)
            self._text(self.label_font, t('live.top_send'), PINK, (cx, by + bh * 0.52), max_w=bw)
            return
        row_h, gap = 96, 12
        y = by + 84
        for i, sup in enumerate(top):
            fill, edge, ink = PODIUM[i]
            rect = pygame.Rect(round(bx), round(y + i * (row_h + gap)), round(bw), row_h)
            self.screen.blit(rounded_rect(rect.size, 20, fill, (edge, 4)), rect)
            badge = self.label_bold.render(f'{i + 1}º', True, ink)          # lugar, no cantinho
            self.screen.blit(badge, badge.get_rect(topright=(rect.right - 16, rect.top + 10)))
            size = row_h - 24
            ring = pygame.Rect(0, 0, size + 8, size + 8)
            ring.midleft = (rect.left + 16, rect.centery)
            pygame.draw.circle(self.screen, edge, ring.center, ring.width // 2)
            photo = self._avatar(sup, size)
            self.screen.blit(photo, photo.get_rect(center=ring.center))
            tx = ring.right + 20
            room = rect.right - 56 - tx
            self._text(self.value_font, '@' + sup.user, ink, (tx, rect.centery - 16), max_w=room, anchor='midleft')
            gifts = sup.gifts if hasattr(sup, 'gifts') else 0
            line = t('live.gift_count') if gifts == 1 else t('live.gifts_count', n=gifts)
            line += '  ·  ' + t('live.coin' if sup.coins == 1 else 'live.coins', n=sup.coins)
            self._text(self.label_font, line, ink, (tx, rect.centery + 20), max_w=room, anchor='midleft')

    def _avatar(self, sup, size):
        """Foto redonda do espectador (baixada pela conexão com a live); sem foto, a inicial numa bolinha."""
        key = (sup.avatar, sup.user, size)
        if key not in self._avatars:
            img = None
            if sup.avatar and os.path.exists(live.image_path(sup.avatar)):
                try:
                    img = pygame.image.load(live.image_path(sup.avatar)).convert_alpha()
                except (pygame.error, OSError):         # formato que o pygame não abre
                    img = None
            out = pygame.Surface((size, size), pygame.SRCALPHA)
            if img is not None:
                side = min(img.get_size())
                crop = img.subsurface(pygame.Rect((img.get_width() - side) // 2, (img.get_height() - side) // 2,
                                                  side, side))
                out.blit(pygame.transform.smoothscale(crop, (size, size)), (0, 0))
                mask = pygame.Surface((size, size), pygame.SRCALPHA)
                pygame.draw.circle(mask, (255, 255, 255, 255), (size // 2, size // 2), size // 2)
                out.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            else:
                pygame.draw.circle(out, PINK_LIGHT, (size // 2, size // 2), size // 2)
                letter = fonte('Bold', max(14, round(size * 0.42))).render((sup.user or '?')[0].upper(), True, PINK)
                out.blit(letter, letter.get_rect(center=(size // 2, size // 2 + 1)))
            self._avatars[key] = out
        return self._avatars[key]

    def _draw_name_entry(self, state, result, box):
        bx, by, bw, bh = box
        cx = bx + bw / 2
        self._text(self.title_font, t('over.new_record' if result.is_best else 'over.entered'), PINK,
                   (cx, by + 26), max_w=bw)
        self._text(self.big_font, str(state.score), INK, (cx, by + bh * 0.3))
        self._text(self.label_font, t('over.type_name'), MUTED, (cx, by + bh * 0.5))
        field = pygame.Rect(0, 0, round(bw * 0.7), 56)
        field.center = (round(cx), round(by + bh * 0.62))
        self.screen.blit(rounded_rect(field.size, 14, WHITE, (PINK, 2)), field)
        cursor = '|' if int(state.time * 2) % 2 == 0 else ' '      # cursor piscando
        self._text(self.value_font, result.name + cursor, INK, field.center)
        self._button_row([(t('btn.save'), 'save')], box)

    def _draw_records(self, result, box):
        """Tabela "usuario     100": nome à esquerda, pontos à direita; a partida que acabou em destaque."""
        bx, by, bw, bh = box
        title = t('records.title_arena', n=result.arena, elo=t(f'tier.{result.league}'))
        self._text(self.title_font, title, INK, (bx + bw / 2, by + 26), max_w=bw)
        draw_records_table(self.screen, self.label_font, result.records, (bx, by + bh * 0.14, bw, bh * 0.66),
                           INK, PINK, result.rank, PINK_LIGHT)
        self._button_row([(t('btn.back'), 'records'), (t('btn.again'), 'restart'), (t('btn.menu'), 'menu')], box,
                         y_frac=0.95)

    # ------------------------------------------------------------ botões
    def _button_row(self, items, box, y_frac=0.95):
        """Botões chapados lado a lado, centralizados embaixo do quadro. items: (texto, ação).

        Os de ação principal (jogar de novo, continuar, salvar) são rosa; os outros, lilás claro.
        """
        bx, by, bw, bh = box
        gap = 12
        widths = [max(140, self.button_font.size(text)[0] + 40) for text, _ in items]
        k = min(1.0, (bw - gap * (len(items) - 1)) / sum(widths))     # encolhe se não couber
        widths = [round(w * k) for w in widths]
        x = bx + (bw - sum(widths) - gap * (len(items) - 1)) / 2
        for (text, action), w in zip(items, widths):
            rect = pygame.Rect(round(x), round(by + bh * y_frac - BUTTON_H / 2), w, BUTTON_H)
            hover = self.mouse is not None and rect.collidepoint(self.mouse)
            flat_button(self.screen, rect, text, self.button_font, 'hover' if hover else 'normal',
                        primary=action in PRIMARY_ACTIONS)
            self.buttons.append((rect, action))
            x += w + gap

    def button_at(self, pos):
        """Ação do botão em `pos` (coordenadas da tela lógica), ou None."""
        for rect, action in self.buttons:
            if rect.collidepoint(pos):
                return action
        return None
