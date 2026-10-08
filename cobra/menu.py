"""Interface chapada (sprites em assets/ui): capa e perfil, que é o "lobby" das partidas.

Tudo é desenhado numa Surface de 1280x720 (BASE) e escalado para a janela mantendo a proporção,
com faixas pretas; as posições do mouse são convertidas de volta para 1280x720.

Capa: fundo, cobra (sobe e desce), logo, JOGAR e X (sair).
Perfil: logo pequeno, ícones de configurações/recordes/voltar, cabeçalho do jogador (foto com o
lápis da skin, nome, nível, XP), 5 estatísticas e um card por arena com elo, PDL e o JOGAR dela.
Recordes, configurações e skins abrem como cartões por cima do perfil.
"""
import math
import os

import pygame

from . import account, config, i18n, profile, rank, records, settings, skins
from .i18n import t
from .render import draw_records_table, rank_label
from . import live
from .live import live_available
from .manifest import SPRITES_DIR as SPRITES     # pasta dos sprites do jogo (assets/sprites)
from .widgets import (CARD_BORDER, DIM, HOVER_FILL, INK, LOSS, MUTED, PINK, PINK_LIGHT, PRESSED_FILL, STAT_FILL,
                      WHITE, Botao, bar, circle, flat_button, fonte, load_image, rounded_rect, volume_row)

UI = config.UI_DIR
ASSETS = {
    'capa_fundo': os.path.join(UI, 'capa', 'capa_fundo.png'),
    'capa_cobra': os.path.join(UI, 'capa', 'capa_cobra.png'),
    'logo': os.path.join(UI, 'capa', 'logo_snakift.png'),
    'logo_pequeno': os.path.join(UI, 'capa', 'logo_snakift_pequeno.png'),
    'botao': os.path.join(UI, 'botoes', '{nome}'),                      # + _<estado>.png
    'escudo': os.path.join(UI, 'escudos', 'escudo_{elo}.png'),
    'fontes': config.FONT_DIR,
    'avatar': os.path.join(SPRITES, 'avatares', '{nome}.png'),          # retrato da skin (alta resolução)
    'cabeca': os.path.join(SPRITES, '{pasta}', 'cabeca_S.png'),         # sem o retrato: a cabeça do jogo
}

BASE = (1280, 720)
BAKED_PLAY = 'JOGAR'            # texto que já vem desenhado nos sprites jogar_*

# cores (a paleta fica em widgets.py)
DOT = (0xE9, 0xE1, 0xF2)
BG_TINT = (20, 10, 40, 60)

# capa
CAPA_LOGO_Y = 40
CAPA_JOGAR = (480, 620)         # canto de cima-esquerda (no resultado da arte o botão fica centralizado em x=640)
CAPA_FECHAR = (1188, 22)
CAPA_COBRA_BOB = (1.6, 5)       # velocidade e altura do sobe e desce

# perfil
LOGO_PEQUENO = (40, 30)
ICONES = [('config', 'settings', (1072, 18)), ('trofeu', 'records', (1130, 18)), ('voltar', 'back', (1188, 18))]
PAINEL = pygame.Rect(40, 86, 1200, 606)
PAINEL_RAIO = 24
AVATAR_C, AVATAR_R, AVATAR_CABECA = (114, 156), 42, 72
EDITAR = (134, 176)
NOME = (176, 116)
XP_BARRA = pygame.Rect(176, 158, 300, 6)
XP_TEXTO_Y = 174
STAT_X, STAT_Y, STAT_TAM, STAT_RAIO = (616, 734, 852, 970, 1088), 119, (108, 74), 14
CARD_X, CARD_Y, CARD_TAM, CARD_RAIO = (72, 456, 840), 220, (368, 444), 20
GRADE = (272, 22, 72)           # miniatura da arena: posição no card e tamanho
ESCUDO = (20, 116, 64)
PDL_BARRA = (23, 190, 322, 8)
NUMEROS_X = (23, 132, 241)
JOGAR_CARD = (23, 373)
SUBTITULO = {11: 'arena.sub.11', 15: 'arena.sub.15', 18: 'arena.sub.18'}

PARENT = {'records': 'profile', 'skins': 'profile', 'settings': 'profile', 'profile': 'main',
          'modo': 'main', 'live_cfg': 'modo', 'conta': 'settings'}                                    # para onde o Voltar leva
LIVE_GRID = (6, 2)              # tela "Presentes da live": colunas x linhas por página
LIVE_CARD = (140, 150)
USER_CHARS = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._')   # @ do TikTok
USER_MAX = 24


def format_duration(seconds):
    """Tempo jogado: '1h 25m' ou '12m 30s'."""
    s = int(seconds)
    if s >= 3600:
        return f'{s // 3600}h {s % 3600 // 60:02d}m'
    return f'{s // 60}m {s % 60:02d}s'


def wrap(text, font, width):
    """Quebra o texto em linhas que cabem em `width` px (quebra nos espaços)."""
    lines, cur = [], ''
    for word in text.split():
        test = f'{cur} {word}'.strip()
        if cur and font.size(test)[0] > width:
            lines.append(cur)
            cur = word
        else:
            cur = test
    return lines + [cur] if cur else lines


def F(peso, tamanho):
    return fonte(peso, tamanho, ASSETS['fontes'])


def mini_grid(n, size):
    """N x N pontinhos com uma cobrinha rosa de 4 a 6 pontos (feita uma vez por arena)."""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    step = size / n
    dot = max(2, round(step * 0.78))
    c = n // 2
    length = 6 if n <= 11 else (5 if n <= 15 else 4)
    snake = {(c - 3 + k, c) for k in range(min(4, length))} | {(c, c - 1 - k) for k in range(length - 4)}
    for gy in range(n):
        for gx in range(n):
            col = PINK if (gx, gy) in snake else DOT
            cell = pygame.Rect(0, 0, dot, dot)
            cell.center = (round(step * (gx + 0.5)), round(step * (gy + 0.5)))
            pygame.draw.rect(surf, col, cell, border_radius=max(1, dot // 3))
    return surf


class Menu:
    """screen: 'main' (capa), 'profile', 'skins', 'records' ou 'settings'.

    prefs: configurações do jogador ({'idioma', 'arena', 'skin', ...}); save_prefs() grava depois de cada mudança.
    Os métodos públicos que recebem posições (hover, press, release, button_at) usam coordenadas da tela
    em que o menu é desenhado; por dentro elas viram coordenadas de 1280x720.
    """

    def __init__(self, records_path, prefs, save_prefs, rank_path=None, profile_path=None, skins=('classica',)):
        self.view = pygame.Surface(BASE)
        self.view_rect = pygame.Rect((0, 0), BASE)         # onde a view foi desenhada na última vez
        self.capa_fundo = load_image(ASSETS['capa_fundo'])
        self.capa_cobra = load_image(ASSETS['capa_cobra'])
        self.logo = load_image(ASSETS['logo'])
        self.logo_pequeno = load_image(ASSETS['logo_pequeno'])
        self.bg_blur = self._blurred_background()
        self.records_path, self.rank_path, self.profile_path = records_path, rank_path, profile_path
        self.skins = list(skins)
        self.prefs, self.save_prefs = prefs, save_prefs
        self.arena = prefs['arena']             # arena da próxima partida
        self.profile_data = None
        self.player_name = ''
        self.name_text, self.name_editing = '', False      # editando o nome na tela das skins
        self.account_reset_at = -99.0                      # quando a conta foi resetada (aviso na tela)
        self.top_score = 0
        self.ranks, self.tables = {}, {}
        self.best_tier = 0                      # maior liga já alcançada (libera as skins)
        self.records_arena = self.arena
        self.records_league = records.FIRST_LEAGUE  # elo da tabela de recordes mostrada
        self.supporters = []                        # recordes de quem mais mandou presentes nas lives
        self.mode_choice = prefs.get('modo', 'offline')     # tela do modo: escolha, @ digitado, digitando?
        self.user_text = prefs.get('tiktok', '')
        self.editing = self.mode_error = False
        self._time = 0.0
        self.live_catalog, self.live_catalog_default, self.live_page = [], True, 0
        self.screen = 'main'
        self.focus = 0                          # botão selecionado (teclado e mouse)
        self.show_focus = False                 # realça o selecionado: mouse em cima ou depois das setas
        self.pressed = None                     # ação do botão com o mouse apertado em cima
        self.buttons = []                       # (retângulo em 1280x720, ação, tecla de atalho) do último quadro
        self._cache = {}

    # ------------------------------------------------------------ fundo e caches
    def _blurred_background(self):
        """capa_fundo bem desfocado (1/16 e de volta, 2 vezes) e escurecido; feito uma vez."""
        img = self.capa_fundo.copy()
        for _ in range(2):
            small = pygame.transform.smoothscale(img, (BASE[0] // 16, BASE[1] // 16))
            img = pygame.transform.smoothscale(small, BASE)
        tint = pygame.Surface(BASE, pygame.SRCALPHA)
        tint.fill(BG_TINT)
        img.blit(tint, (0, 0))
        return img.convert()

    def _cached(self, key, make):
        if key not in self._cache:
            self._cache[key] = make()
        return self._cache[key]

    def _shield(self, tier, size):
        return self._cached(('escudo', tier, size), lambda: pygame.transform.smoothscale(
            load_image(ASSETS['escudo'].format(elo=tier)), (size, size)))

    def _avatar_img(self, skin, size):
        """Retrato da skin (ou a cabeça do jogo), recortado e reduzido para caber em size x size."""
        def make():
            folder = 'classico' if skin == 'classica' else os.path.join('skins', skin)
            path = ASSETS['avatar'].format(nome='classico' if skin == 'classica' else skin)
            if not os.path.exists(path):
                path = ASSETS['cabeca'].format(pasta=folder)
            if not os.path.exists(path):
                return None
            full = load_image(path)
            full = full.subsurface(full.get_bounding_rect())
            k = min(size / full.get_height(), size * 1.25 / full.get_width())    # pela altura (os chifres sobram um pouco)
            return pygame.transform.smoothscale(full, (round(full.get_width() * k), round(full.get_height() * k)))
        return self._cached(('avatar', skin, size), make)

    # ------------------------------------------------------------ desenho
    def draw(self, surface, time):
        """Desenha na view de 1280x720 e escala para `surface` mantendo a proporção (faixas pretas)."""
        self.buttons = []
        self._time = time
        v = self.view
        if self.screen == 'main':
            self._draw_capa(v, time)
        else:
            v.blit(self.bg_blur, (0, 0))
            if self.screen == 'profile':
                self._draw_profile(v)
            else:
                self._draw_overlay_card(v)
        sw, sh = surface.get_size()
        k = min(sw / BASE[0], sh / BASE[1])
        size = (round(BASE[0] * k), round(BASE[1] * k))
        self.view_rect = pygame.Rect(((sw - size[0]) // 2, (sh - size[1]) // 2), size)
        if size == BASE:
            surface.blit(v, self.view_rect)
        else:
            surface.fill((0, 0, 0))
            surface.blit(pygame.transform.smoothscale(v, size), self.view_rect)

    def _button_state(self, index, action):
        if self.pressed == action:
            return 'pressionado'
        return 'hover' if self.show_focus and index == self.focus else 'normal'

    def _add_botao(self, surface, botao):
        index = len(self.buttons)
        botao.draw(surface, self._button_state(index, botao.action))
        self.buttons.append((botao.rect, botao.action, botao.hotkey))

    def _botao(self, nome, pos, action, hotkey=None, label=None, font=None):
        return Botao(ASSETS['botao'].format(nome=nome), pos, action, hotkey, label, BAKED_PLAY, font)

    def _draw_capa(self, v, time):
        v.blit(self.capa_fundo, (0, 0))
        speed, height = CAPA_COBRA_BOB
        v.blit(self.capa_cobra, (0, round(math.sin(time * speed) * height)))
        v.blit(self.logo, self.logo.get_rect(midtop=(BASE[0] // 2, CAPA_LOGO_Y)))
        self._add_botao(v, self._botao('jogar_capa', CAPA_JOGAR, 'play', pygame.K_RETURN, t('menu.play'), F('Bold', 21)))
        self._add_botao(v, self._botao('fechar', CAPA_FECHAR, 'quit', pygame.K_ESCAPE))

    def _text(self, v, text, peso, size, color, pos, anchor='topleft', max_w=None):
        img = F(peso, size).render(text, True, color)
        if max_w is not None and img.get_width() > max_w:
            img = pygame.transform.smoothscale(img, (round(max_w), round(img.get_height() * max_w / img.get_width())))
        rect = img.get_rect(**{anchor: pos})
        v.blit(img, rect)
        return rect

    # ------------------------------------------------------------ perfil (lobby)
    def _draw_profile(self, v):
        """Perfil igual ao mockup: os botões entram na ordem do foco (JOGAR das arenas, lápis, ícones)."""
        data = self.profile_data or {'arenas': {n: profile.empty_stats() for n in config.ARENAS}}
        v.blit(self.logo_pequeno, LOGO_PEQUENO)
        v.blit(rounded_rect(PAINEL.size, PAINEL_RAIO, WHITE), PAINEL)

        # cards de modo, com o JOGAR de cada arena
        played = {a: data['arenas'].get(a, profile.empty_stats())['partidas'] for a in config.ARENAS}
        most = max(played, key=played.get) if any(played.values()) else None
        for i, arena in enumerate(config.ARENAS):
            self._draw_mode_card(v, i, arena, data, arena == most)

        # cabeçalho do jogador
        v.blit(circle(AVATAR_R, PINK_LIGHT), (AVATAR_C[0] - AVATAR_R, AVATAR_C[1] - AVATAR_R))
        avatar = self._avatar_img(self.prefs.get('skin', 'classica'), AVATAR_CABECA)
        if avatar:
            v.blit(avatar, avatar.get_rect(center=AVATAR_C))
        self._add_botao(v, self._botao('editar_avatar', EDITAR, 'skins'))
        name = self._text(v, settings.player_name(self.prefs, self.player_name), 'Bold', 28, INK, NOME, max_w=250)
        lvl, xp, per = profile.level(data)
        badge_txt = F('Bold', 12).render(t('profile.level_badge', n=lvl), True, WHITE)
        badge = pygame.Rect(0, 0, badge_txt.get_width() + 20, 22)
        badge.midleft = (name.right + 10, name.centery)
        v.blit(rounded_rect(badge.size, 11, PINK), badge)
        v.blit(badge_txt, badge_txt.get_rect(center=badge.center))
        bar(v, XP_BARRA, xp / per, PINK)
        self._text(v, t('profile.xp', xp=xp, total=per), 'Regular', 12, MUTED, (XP_BARRA.left, XP_TEXTO_Y))
        self._text(v, t('profile.to_level', n=per - xp, l=lvl + 1), 'Regular', 12, MUTED,
                   (XP_BARRA.right, XP_TEXTO_Y), 'topright')

        # 5 caixinhas de estatística
        tot = profile.totals(data)
        stats = [(str(self.top_score) if self.top_score else '-', t('profile.top_score')),
                 (str(tot['partidas']), t('profile.games')), (f"{profile.win_rate(tot)}%", t('profile.wins')),
                 (str(tot['presentes']), t('profile.gifts')), (format_duration(tot['tempo']), t('profile.time'))]
        for x, (value, label) in zip(STAT_X, stats):
            v.blit(rounded_rect(STAT_TAM, STAT_RAIO, STAT_FILL), (x, STAT_Y))
            self._text(v, value, 'Bold', 22, INK, (x + 16, STAT_Y + 10), max_w=STAT_TAM[0] - 22)
            self._text(v, label, 'Regular', 12, MUTED, (x + 16, STAT_Y + 46), max_w=STAT_TAM[0] - 22)

        # ícones do topo
        for nome, action, pos in ICONES:
            self._add_botao(v, self._botao(nome, pos, action, pygame.K_ESCAPE if action == 'back' else None))
        photo = pygame.Rect(0, 0, 2 * AVATAR_R, 2 * AVATAR_R)
        photo.center = AVATAR_C
        self.buttons.append((photo, 'skins', None))                         # clicar na foto também troca a skin

    def _draw_mode_card(self, v, i, arena, data, most_played):
        x, y = CARD_X[i], CARD_Y
        v.blit(rounded_rect(CARD_TAM, CARD_RAIO, WHITE, (CARD_BORDER, 1)), (x, y))
        st = data['arenas'].get(arena, profile.empty_stats())
        r = self.ranks.get(arena, rank.START)
        self._text(v, f'{arena}×{arena}', 'Bold', 34, INK, (x + 23, y + 18))
        self._text(v, t(SUBTITULO.get(arena, 'arena.sub.11')), 'Regular', 13, MUTED, (x + 23, y + 62))
        gx, gy, gs = GRADE
        v.blit(self._cached(('grade', arena, gs), lambda: mini_grid(arena, gs)), (x + gx, y + gy))
        if most_played:
            tag = F('Bold', 11).render(t('profile.most_played'), True, PINK)
            box = pygame.Rect(x + 23, y - 10, tag.get_width() + 20, 24)
            v.blit(rounded_rect(box.size, 12, PINK_LIGHT), box)
            v.blit(tag, tag.get_rect(center=box.center))
        ex, ey, es = ESCUDO
        v.blit(self._shield(rank.tier_id(r), es), (x + ex, y + ey))
        self._text(v, rank_label(r), 'Bold', 22, INK, (x + 89, y + 128), max_w=250)
        peak = st['pico'] or r
        self._text(v, t('profile.peak', name=rank_label(peak)), 'Regular', 12, MUTED, (x + 89, y + 156), max_w=250)
        bx, by, bw, bh = PDL_BARRA
        full = config.RANQUE_PDL_DIVISAO
        bar(v, (x + bx, y + by, bw, bh), 1.0 if rank.is_top(r) else r.pdl / full, INK)
        if rank.is_top(r):
            self._text(v, t('rank.bar_master', pdl=r.pdl), 'Regular', 12, MUTED, (x + bx, y + 210))
        else:
            self._text(v, t('rank.bar', pdl=r.pdl, total=full), 'Regular', 12, MUTED, (x + bx, y + 210))
            self._text(v, t('profile.to_next', n=full - r.pdl, name=rank_label(rank.promote(r))), 'Regular', 12, MUTED,
                       (x + bx + bw, y + 210), 'topright')
        numbers = [(f"{st['vitorias']} · {st['derrotas']}", t('profile.vd')),
                   (f"{profile.win_rate(st)}%", t('profile.wins')), (str(st['melhor']), t('profile.record'))]
        for nx, (value, label) in zip(NUMEROS_X, numbers):
            self._text(v, value, 'Bold', 16, INK, (x + nx, y + 252))
            self._text(v, label, 'Regular', 12, MUTED, (x + nx, y + 274))
        jx, jy = JOGAR_CARD
        self._add_botao(v, self._botao('jogar_card', (x + jx, y + jy), f'arena_{arena}', None, t('menu.play'),
                                       F('Bold', 16)))

    # ------------------------------------------------------------ recordes, configurações, skins
    def _flat_button(self, v, label, action, center, width, active=False, height=50):
        """Botão chapado desenhado (painéis): rosa quando ativo, lilás claro senão."""
        state = self._button_state(len(self.buttons), action)
        rect = pygame.Rect(0, 0, width, height)
        rect.center = (round(center[0]), round(center[1]))
        flat_button(v, rect, label, F('Medium', 17), state, primary=active)
        self.buttons.append((rect, action, pygame.K_ESCAPE if action == 'back' else None))

    def _draw_overlay_card(self, v):
        dim = pygame.Surface(BASE, pygame.SRCALPHA)
        dim.fill(DIM)
        v.blit(dim, (0, 0))
        v.blit(self.logo_pequeno, LOGO_PEQUENO)
        card = pygame.Rect((0, 0), (1040 if self.screen in ('skins', 'live_cfg') else 760, 600))
        card.center = (BASE[0] // 2, BASE[1] // 2 + 20)
        v.blit(rounded_rect(card.size, PAINEL_RAIO, WHITE), card)
        title = {'records': 'records.title', 'settings': 'settings.title', 'skins': 'skins.title',
                 'modo': 'mode.title', 'live_cfg': 'livecfg.title', 'conta': 'account.title'}[self.screen]
        self._text(v, t(title), 'Bold', 30, INK, (card.centerx, card.top + 26), 'midtop')
        back_y = card.bottom - 50
        if self.screen == 'records':
            tabs = [(f'{n}×{n}', f'tab_{n}', n == self.records_arena) for n in config.ARENAS]
            tabs.append((t('records.gifts_tab'), 'tab_presentes', self.records_arena == 'presentes'))
            tab_w = 150
            x0 = card.centerx - (tab_w + 14) * (len(tabs) - 1) / 2
            for i, (label, action, on) in enumerate(tabs):
                self._flat_button(v, label, action, (x0 + i * (tab_w + 14), card.top + 105), tab_w, active=on, height=42)
            if self.records_arena == 'presentes':
                self._draw_supporters(v, card, back_y)
                self._flat_button(v, t('menu.back'), 'back', (card.centerx, back_y), 240)
                return
            self._draw_league_picker(v, card.centerx, card.top + 170)
            self._text(v, t('records.elo_hint', elo=t(f'tier.{self.records_league}')), 'Medium', 15, MUTED,
                       (card.centerx, card.top + 212), 'midtop')
            box = (card.left + 60, card.top + 240, card.width - 120, back_y - card.top - 280)
            draw_records_table(v, F('Medium', 18), self.tables.get((self.records_arena, self.records_league), []),
                               box, INK, PINK)
        elif self.screen == 'settings':
            lang = i18n.LANGUAGES[i18n.language()]
            yes_no = lambda on: t('settings.on' if on else 'settings.off')
            options = [(t('settings.language', lang=lang), 'language'),
                       (t('settings.scenery', v=yes_no(self.prefs.get('cenario_muda', True))), 'toggle_scenery'),
                       (t('settings.snake', v=yes_no(self.prefs.get('cobra_muda', True))), 'toggle_snake')]
            for i, (label, action) in enumerate(options):
                self._flat_button(v, label, action, (card.centerx, card.top + 120 + 72 * i), 520)
            self._draw_volumes(v, pygame.Rect(card.centerx - 260, card.top + 318, 520, 44), 60)
            if self._time - self.account_reset_at < 3.0:      # acabou de resetar
                self._text(v, t('account.done'), 'Bold', 16, PINK, (card.centerx, card.top + 492), 'midtop')
            self._flat_button(v, t('menu.back'), 'back', (card.centerx - 135, back_y), 240)
            self._danger_button(v, t('account.button'), 'account_reset', (card.centerx + 135, back_y), 240)
            return
        elif self.screen == 'conta':                  # resetar a conta: confirma antes (não dá para desfazer)
            y = card.top + 110
            for key, color in (('account.warn1', INK), ('account.warn2', INK), ('account.keep', MUTED),
                               ('account.undo', LOSS)):
                for line in wrap(t(key), F('Medium', 18), card.width - 120):
                    self._text(v, line, 'Medium', 18, color, (card.centerx, y), 'midtop', max_w=card.width - 80)
                    y += 28
                y += 14
            self._flat_button(v, t('account.no'), 'back', (card.centerx - 135, back_y), 240)
            self._danger_button(v, t('account.yes'), 'account_yes', (card.centerx + 135, back_y), 240)
            return
        elif self.screen == 'modo':
            self._draw_mode(v, card, back_y)
            return
        elif self.screen == 'live_cfg':
            self._draw_live_cfg(v, card, back_y)
        else:
            self._draw_skins(v, card)
        self._flat_button(v, t('menu.back'), 'back', (card.centerx, back_y), 240)

    def _danger_button(self, v, label, action, center, width, height=50):
        """Botão vermelho (ação que apaga coisas)."""
        state = self._button_state(len(self.buttons), action)
        rect = pygame.Rect(0, 0, width, height)
        rect.center = (round(center[0]), round(center[1]))
        fill = {'normal': LOSS, 'hover': (225, 70, 70), 'pressionado': (190, 40, 40)}[state]
        v.blit(rounded_rect(rect.size, 12, fill), rect)
        self._text(v, label, 'Bold', 16, WHITE, rect.center, 'center', max_w=width - 20)
        self.buttons.append((rect, action, None))

    def _draw_volumes(self, v, first, gap):
        """Linhas de volume (som geral, música e efeitos) com os botões − e +, a partir do retângulo `first`."""
        for i, (name, key) in enumerate(settings.VOLUMES.items()):
            row = first.move(0, i * gap)

            def button(rect, text, name=name):
                action = f"vol_{name}_{'down' if text == '−' else 'up'}"
                flat_button(v, rect, text, F('Bold', 22), self._button_state(len(self.buttons), action), primary=False)
                self.buttons.append((rect, action, None))
            volume_row(v, row, t(f'sound.{"master" if name == "geral" else "music" if name == "musica" else "sfx"}'),
                       self.prefs.get(key, settings.VOLUME_MAX), F('Medium', 18), button, settings.VOLUME_MAX)

    def _draw_mode(self, v, card, back_y):
        """Escolha do modo: offline (presentes por tempo) ou live do TikTok (presentes da live, com o @)."""
        options = [('offline', 'mode.offline', 'mode.offline_desc'), ('live', 'mode.live', 'mode.live_desc')]
        w, h, gap = 300, 120, 24
        for i, (mode, title, desc) in enumerate(options):
            rect = pygame.Rect(0, 0, w, h)
            rect.center = (round(card.centerx + (i - 0.5) * (w + gap)), card.top + 160)
            action = f'mode_{mode}'
            state = self._button_state(len(self.buttons), action)
            on = self.mode_choice == mode
            fill = PINK_LIGHT if on else {'normal': STAT_FILL, 'hover': HOVER_FILL, 'pressionado': PRESSED_FILL}[state]
            v.blit(rounded_rect(rect.size, 18, fill, (PINK, 2) if on else None), rect)
            self._text(v, t(title), 'Bold', 22, PINK if on else INK, (rect.centerx, rect.top + 30), 'midtop')
            for k, line in enumerate(wrap(t(desc), F('Regular', 14), w - 36)):
                self._text(v, line, 'Regular', 14, MUTED, (rect.centerx, rect.top + 66 + 20 * k), 'midtop', max_w=w - 24)
            self.buttons.append((rect, action, None))
        if self.mode_choice == 'live':
            self._text(v, t('mode.user_label'), 'Medium', 15, MUTED, (card.centerx, card.top + 250), 'midtop')
            field = pygame.Rect(0, 0, 420, 54)
            field.center = (card.centerx, card.top + 310)
            border = LOSS if self.mode_error else (PINK if self.editing else CARD_BORDER)
            v.blit(rounded_rect(field.size, 14, WHITE, (border, 2)), field)
            cursor = '|' if self.editing and int(self._time * 2) % 2 == 0 else ' '
            text = '@' + self.user_text + cursor if (self.user_text or self.editing) else t('mode.user_placeholder')
            self._text(v, text, 'Medium', 20, INK if self.user_text else MUTED, field.center, 'center',
                       max_w=field.width - 24)
            self.buttons.append((field, 'mode_field', None))
            hint = 'mode.user_missing' if self.mode_error else 'mode.hint' if live_available() else 'mode.lib_missing'
            self._text(v, t(hint), 'Regular', 13, LOSS if hint != 'mode.hint' else MUTED,
                       (card.centerx, card.top + 350), 'midtop', max_w=card.width - 80)
            self._flat_button(v, t('livecfg.open'), 'live_cfg', (card.centerx, card.top + 410), 320, height=46)
        self._flat_button(v, t('menu.back'), 'back', (card.centerx - 140, back_y), 240)
        index = len(self.buttons)
        flat_button(v, pygame.Rect(card.centerx + 20, back_y - 25, 240, 50), t('mode.continue'), F('Bold', 17),
                    self._button_state(index, 'mode_ok'), primary=True)
        self.buttons.append((pygame.Rect(card.centerx + 20, back_y - 25, 240, 50), 'mode_ok', pygame.K_RETURN))

    def _draw_live_cfg(self, v, card, back_y):
        """Presentes da live: clicar liga/desliga a interação com o jogo; a bombinha escolhe o presente da bomba."""
        items = self.live_catalog
        per = LIVE_GRID[0] * LIVE_GRID[1]
        pages = max(1, -(-len(items) // per))
        self.live_page = min(self.live_page, pages - 1)
        self._text(v, t('livecfg.hint'), 'Regular', 14, MUTED, (card.centerx, card.top + 74), 'midtop',
                   max_w=card.width - 60)
        cw, ch = LIVE_CARD
        gap = 14
        x0 = card.centerx - (LIVE_GRID[0] * cw + (LIVE_GRID[0] - 1) * gap) / 2
        start = self.live_page * per
        for k, item in enumerate(items[start:start + per]):
            i = start + k
            rect = pygame.Rect(round(x0 + (k % LIVE_GRID[0]) * (cw + gap)),
                               card.top + 110 + (k // LIVE_GRID[0]) * (ch + gap), cw, ch)
            is_bomb = live.is_bomb(item['nome'], self.prefs)
            on = live.is_enabled(item['nome'], self.prefs) or is_bomb
            state = self._button_state(len(self.buttons), f'livegift_{i}')
            fill = STAT_FILL if state == 'normal' else HOVER_FILL
            border = (LOSS, 2) if is_bomb else ((PINK, 2) if on else None)
            v.blit(rounded_rect(rect.size, 16, fill if on else WHITE, border or (CARD_BORDER, 1)), rect)
            self.buttons.append((rect, f'livegift_{i}', None))
            icon = self._gift_icon(item, 54)
            if not on:
                icon = self._cached(('apagado', id(icon)), lambda icon=icon: self._faded(icon))
            v.blit(icon, icon.get_rect(center=(rect.centerx, rect.top + 46)))
            self._text(v, item['nome'], 'Bold', 14, INK if on else MUTED, (rect.centerx, rect.top + 82), 'midtop',
                       max_w=cw - 14)
            coins = t('livecfg.coins_unknown') if item['moedas'] is None else \
                t('live.coin' if item['moedas'] == 1 else 'live.coins', n=item['moedas'])
            self._text(v, coins, 'Regular', 12, MUTED, (rect.centerx, rect.top + 102),
                       'midtop', max_w=cw - 14)
            boxed = on and not is_bomb and not live.is_known(item['nome'])     # sem visual no jogo: vira caixa
            tag = 'livecfg.bomb' if is_bomb else ('livecfg.box' if boxed else 'livecfg.on' if on else 'livecfg.off')
            text = F('Bold', 11).render(t(tag), True, WHITE if is_bomb else (PINK if on else MUTED))
            pill = pygame.Rect(0, 0, text.get_width() + 16, 20)
            pill.midbottom = (rect.centerx, rect.bottom - 8)
            v.blit(rounded_rect(pill.size, 10, LOSS if is_bomb else (PINK_LIGHT if on else STAT_FILL)), pill)
            v.blit(text, text.get_rect(center=pill.center))
            if not is_bomb:                                     # bombinha: escolhe este como o da bomba
                b = pygame.Rect(rect.right - 30, rect.top + 6, 24, 24)
                hover = self._button_state(len(self.buttons), f'livebomb_{i}') != 'normal'
                pygame.draw.circle(v, (60, 52, 66) if hover else (150, 142, 160), b.center, 9)
                pygame.draw.line(v, (255, 196, 0), (b.centerx + 5, b.centery - 6), (b.centerx + 9, b.centery - 10), 2)
                self.buttons.append((b, f'livebomb_{i}', None))
        if pages > 1:
            self._flat_button(v, '<', 'livepage_-1', (card.left + 60, back_y), 70)
            self._text(v, t('livecfg.page', n=self.live_page + 1, total=pages), 'Medium', 14, MUTED,
                       (card.left + 160, back_y), 'center')
            self._flat_button(v, '>', 'livepage_1', (card.left + 260, back_y), 70)
        if self.live_catalog_default:
            self._text(v, t('livecfg.default_list'), 'Regular', 13, MUTED, (card.centerx, back_y - 46), 'center',
                       max_w=card.width - 60)

    def _gift_icon(self, item, size):
        """Ícone do presente da live (baixado ao conectar); sem ícone, uma moeda com a inicial."""
        path = live.image_path(item['imagem']) if item.get('imagem') else None
        if path and os.path.exists(path):
            try:
                img = load_image(path)
                return self._cached(('icone', path, size), lambda: pygame.transform.smoothscale(img, (size, size)))
            except (pygame.error, OSError):
                pass
        def coin():
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.circle(surf, (255, 200, 60), (size // 2, size // 2), size // 2 - 2)
            pygame.draw.circle(surf, (230, 160, 20), (size // 2, size // 2), size // 2 - 2, width=3)
            letter = F('Bold', size // 2).render(item['nome'][:1].upper(), True, WHITE)
            surf.blit(letter, letter.get_rect(center=(size // 2, size // 2 + 1)))
            return surf
        return self._cached(('moeda', item['nome'], size), coin)

    def type_key(self, key, char):
        """Digitando o @ na tela do modo ou o nome na das skins. Devolve True se usou a tecla
        (na do modo, o Enter fica com o botão Continuar)."""
        if self.screen == 'skins' and self.name_editing:
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._save_name()
            elif key == pygame.K_ESCAPE:                # cancela: volta o nome que estava
                self.name_editing = False
            elif key == pygame.K_BACKSPACE:
                self.name_text = self.name_text[:-1]
            elif char and char.isprintable() and len(self.name_text) < records.MAX_NAME:
                self.name_text += char
            return True
        if self.screen != 'modo' or not self.editing:
            return False
        if key == pygame.K_BACKSPACE:
            self.user_text = self.user_text[:-1]
        elif char and char in USER_CHARS and len(self.user_text) < USER_MAX:
            self.user_text += char
        elif char == '@' or key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
            pass
        else:
            return False
        self.mode_error = False
        return True

    def _draw_supporters(self, v, card, back_y):
        """Recordes de quem mais mandou presentes nas lives: posição, foto, @ e total de moedas."""
        self._text(v, t('records.gifts_hint'), 'Medium', 15, MUTED, (card.centerx, card.top + 150), 'midtop')
        if not self.supporters:
            self._text(v, t('records.gifts_empty'), 'Regular', 16, MUTED, (card.centerx, card.top + 300), 'center',
                       max_w=card.width - 80)
            return
        top, bottom = card.top + 185, back_y - 40
        cols = 2 if len(self.supporters) > 5 else 1
        rows_per = -(-len(self.supporters) // cols)
        row_h = min(56, (bottom - top) / rows_per)
        col_w = (card.width - 120) / cols
        for i, sup in enumerate(self.supporters):
            x = card.left + 60 + (i // rows_per) * col_w
            y = top + (i % rows_per) * row_h + row_h / 2
            medal = [(0xF5, 0xB7, 0x00), (0xA9, 0xB4, 0xC2), (0xC9, 0x7A, 0x3A)]
            pos_col = medal[i] if i < 3 else MUTED
            self._text(v, f'{i + 1}.', 'Bold', 18, pos_col, (x + 30, y), 'midright')
            photo = self._supporter_photo(sup, 40)
            v.blit(photo, photo.get_rect(midleft=(round(x + 40), round(y))))
            self._text(v, '@' + sup['usuario'], 'Bold', 17, INK, (x + 90, y), 'midleft', max_w=col_w - 230)
            coins = t('live.coin' if sup['moedas'] == 1 else 'live.coins', n=sup['moedas'])
            self._text(v, coins, 'Medium', 16, PINK, (x + col_w - 20, y), 'midright')

    def _supporter_photo(self, sup, size):
        """Foto redonda do espectador (baixada pela live); sem foto, a inicial numa bolinha."""
        def make():
            path = live.image_path(sup['foto']) if sup.get('foto') else None
            out = pygame.Surface((size, size), pygame.SRCALPHA)
            img = None
            if path and os.path.exists(path):
                try:
                    img = pygame.image.load(path).convert_alpha()
                except (pygame.error, OSError):
                    img = None
            if img is not None:
                side = min(img.get_size())
                crop = img.subsurface(pygame.Rect((img.get_width() - side) // 2, (img.get_height() - side) // 2, side, side))
                out.blit(pygame.transform.smoothscale(crop, (size, size)), (0, 0))
                mask = pygame.Surface((size, size), pygame.SRCALPHA)
                pygame.draw.circle(mask, (255, 255, 255, 255), (size // 2, size // 2), size // 2)
                out.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            else:
                pygame.draw.circle(out, PINK_LIGHT, (size // 2, size // 2), size // 2)
                letter = F('Bold', size // 2).render((sup['usuario'] or '?')[0].upper(), True, PINK)
                out.blit(letter, letter.get_rect(center=(size // 2, size // 2 + 1)))
            return out
        return self._cached(('foto', sup.get('foto'), sup['usuario'], size), make)

    def _draw_league_picker(self, v, cx, cy):
        """Fileira com o escudo de cada elo: escolhe de qual elo é a tabela de recordes."""
        size, gap = 54, 10
        leagues = [liga for liga, *_ in config.RANQUE_LIGAS]
        x = cx - (len(leagues) * size + (len(leagues) - 1) * gap) / 2
        for liga in leagues:
            rect = pygame.Rect(round(x), round(cy - size / 2), size, size)
            action = f'elo_{liga}'
            state = self._button_state(len(self.buttons), action)
            on = liga == self.records_league
            fill = PINK_LIGHT if on else {'normal': STAT_FILL, 'hover': HOVER_FILL, 'pressionado': PRESSED_FILL}[state]
            v.blit(rounded_rect(rect.size, 14, fill, (PINK, 2) if on else None), rect)
            icon = self._shield(liga, 46)
            v.blit(icon, icon.get_rect(center=rect.center))
            self.buttons.append((rect, action, None))
            x += size + gap

    def _draw_skins(self, v, card):
        """Um cartão por skin; clicar equipa. As bloqueadas ficam apagadas, com cadeado e o elo que as libera."""
        equipped = self.prefs.get('skin', 'classica')
        n = len(self.skins)
        gap = 20
        cw = min(180, (card.width - 60 - gap * (n - 1)) / n)
        x0 = card.centerx - (n * cw + (n - 1) * gap) / 2
        for i, name in enumerate(self.skins):
            box = pygame.Rect(round(x0 + i * (cw + gap)), card.top + 100, round(cw), 300)
            on = name == equipped
            unlocked = skins.is_unlocked(name, self.best_tier)
            state = self._button_state(len(self.buttons), f'skin_{name}') if unlocked else 'normal'
            fill = {'normal': STAT_FILL, 'hover': HOVER_FILL, 'pressionado': PRESSED_FILL}[state]
            v.blit(rounded_rect(box.size, CARD_RAIO, fill, (PINK, 2) if on else None), box)
            img = self._avatar_img(name, round(min(130, cw * 0.7)))
            if img:
                if not unlocked:
                    img = self._cached(('apagada', name, img.get_size()), lambda img=img: self._faded(img))
                v.blit(img, img.get_rect(center=(box.centerx, box.top + 110)))
            if not unlocked:
                self._lock(v, (box.right - 28, box.top + 28))
            self._text(v, t(f'skin.{name}'), 'Bold', 20, INK if unlocked else MUTED, (box.centerx, box.top + 210),
                       'midtop', max_w=cw - 16)
            if on or not unlocked:
                liga = config.SKIN_ELO.get(name, '')
                label = t('skins.selected') if on else t('skins.locked', name=t(f'tier.{liga}'))
                tag = F('Bold', 11).render(label, True, PINK if on else MUTED)
                pill = pygame.Rect(0, 0, min(tag.get_width() + 20, box.width - 12), 24)
                pill.center = (box.centerx, box.top + 262)
                v.blit(rounded_rect(pill.size, 12, PINK_LIGHT if on else WHITE), pill)
                v.blit(tag, tag.get_rect(center=pill.center))
            if unlocked:
                self.buttons.append((box, f'skin_{name}', None))
        self._draw_name_field(v, card)

    def _draw_name_field(self, v, card):
        """Nome do jogador, embaixo das skins: clique para editar; no modo live mostra o @ (sem editar)."""
        live_name = settings.player_name(self.prefs, None)
        self._text(v, t('skins.name_label'), 'Medium', 15, MUTED, (card.centerx, card.top + 412), 'midtop')
        field = pygame.Rect(0, 0, 420, 50)
        field.center = (card.centerx, card.top + 462)
        if live_name:
            v.blit(rounded_rect(field.size, 14, STAT_FILL), field)
            self._text(v, live_name, 'Medium', 20, INK, field.center, 'center', max_w=field.width - 24)
            hint = 'skins.name_live'
        else:
            v.blit(rounded_rect(field.size, 14, WHITE, (PINK if self.name_editing else CARD_BORDER, 2)), field)
            cursor = '|' if self.name_editing and int(self._time * 2) % 2 == 0 else ' '
            text = self.name_text + cursor if self.name_editing else self.player_name
            self._text(v, text, 'Medium', 20, INK, field.center, 'center', max_w=field.width - 24)
            self.buttons.append((field, 'name_field', None))
            hint = 'skins.name_hint'
        self._text(v, t(hint), 'Regular', 13, MUTED, (card.centerx, field.bottom + 8), 'midtop',
                   max_w=card.width - 80)

    def _save_name(self):
        """Grava o nome digitado (é o nome que aparece no perfil e que vem pronto no recorde)."""
        self.name_editing = False
        name = self.name_text.strip()[:records.MAX_NAME]
        if not name or name == self.player_name:
            return
        data = records.load(self.records_path)
        data['ultimo_nome'] = name
        try:
            records.save(self.records_path, data)
        except OSError:                     # sem permissão: vale só nesta sessão
            pass
        self.player_name = name

    @staticmethod
    def _faded(img):
        """Versão apagada (cinza e clara) do retrato de uma skin bloqueada."""
        out = pygame.transform.grayscale(img) if hasattr(pygame.transform, 'grayscale') else img.copy()
        out.fill((255, 255, 255, 110), special_flags=pygame.BLEND_RGBA_MULT)
        return out

    @staticmethod
    def _lock(v, center):
        """Cadeadinho chapado."""
        x, y = center
        pygame.draw.circle(v, MUTED, (x, y - 4), 7, width=3)
        body = pygame.Rect(0, 0, 20, 15)
        body.midtop = (x, y - 2)
        v.blit(rounded_rect(body.size, 4, MUTED), body)

    # ------------------------------------------------------------ ações
    def to_view(self, pos):
        """Posição na tela em que o menu é desenhado -> coordenadas de 1280x720 (None fora da área)."""
        if not self.view_rect.collidepoint(pos):
            return None
        k = self.view_rect.width / BASE[0]
        return ((pos[0] - self.view_rect.left) / k, (pos[1] - self.view_rect.top) / k)

    def _hit(self, pos):
        p = self.to_view(pos)
        if p is None:
            return None
        for i in range(len(self.buttons) - 1, -1, -1):          # o último registrado fica por cima
            if self.buttons[i][0].collidepoint(p):
                return i
        return None

    def button_at(self, pos):
        i = self._hit(pos)
        return self.buttons[i][1] if i is not None else None

    def hover(self, pos):
        """Mouse em cima de um botão: ele vira o selecionado."""
        i = self._hit(pos)
        if i is not None:
            self.focus = i
        self.show_focus = i is not None
        return i is not None

    def press(self, pos):
        """Mouse apertado: o botão embaixo dele mostra o estado "pressionado"."""
        self.pressed = self.button_at(pos)

    def release(self, pos):
        """Mouse solto: devolve a ação se ele foi solto em cima do mesmo botão em que apertou."""
        action = self.button_at(pos)
        pressed, self.pressed = self.pressed, None
        return action if action is not None and action == pressed else None

    def hotkey_action(self, key):
        """Ação do botão com essa tecla de atalho na tela atual (Enter = Jogar na capa, Esc = fechar/voltar)."""
        for _, action, hotkey in self.buttons:
            if hotkey == key:
                return action
        return None

    def switch_tab(self, step):
        """← →: troca a aba nos recordes; nas outras telas, anda pelos botões."""
        if self.screen == 'records':
            tabs = list(config.ARENAS) + ['presentes']
            i = (tabs.index(self.records_arena) + step) % len(tabs)
            self.records_arena = tabs[i]
            self.focus = i
            self.show_focus = True
        else:
            self.move_focus(step)

    def move_focus(self, step):
        if self.buttons:
            self.focus = (self.focus + step) % len(self.buttons)
            self.show_focus = True

    def focused_action(self):
        return self.buttons[self.focus][1] if 0 <= self.focus < len(self.buttons) else None

    def open_lobby(self):
        """Abre o perfil (lobby), recarregando elo, estatísticas, nome e o recorde #1."""
        self.profile_data = profile.load(self.profile_path) if self.profile_path else None
        self.ranks = rank.load(self.rank_path) if self.rank_path else {}
        self.best_tier = skins.best_tier(self.profile_data, self.ranks)
        data = records.load(self.records_path)
        self.player_name = data['ultimo_nome']
        self.top_score = records.best(data)
        self._open('profile')
        self.focus = config.ARENAS.index(self.arena) if self.arena in config.ARENAS else 0     # JOGAR da última arena

    def activate(self, action):
        """Executa a ação de um botão. Devolve 'play' (com self.arena escolhida) ou 'quit' quando o app precisa agir."""
        if self.name_editing and action != 'name_field':     # clicou fora do campo do nome: salva
            self._save_name()
        if action == 'name_field':
            if not self.name_editing:
                self.name_text, self.name_editing = self.player_name, True
            return None
        if action == 'play':                    # JOGAR da capa: escolhe o modo (offline / live do TikTok)
            self._open('modo')
            self.mode_choice = self.prefs.get('modo', 'offline')
            self.user_text = self.prefs.get('tiktok', '').lstrip('@')
            self.editing = self.mode_choice == 'live' and not self.user_text
            self.mode_error = False
        elif action in ('mode_offline', 'mode_live', 'mode_field'):
            self.mode_choice = 'offline' if action == 'mode_offline' else 'live'
            self.editing = self.mode_choice == 'live'
            self.mode_error = False
        elif action == 'live_cfg':                # tela "Presentes da live"
            self.live_catalog = live.load_catalog()
            self.live_catalog_default = not os.path.exists(live.catalog_path())
            bomb = self.prefs.get('live_bomba', config.LIVE_BOMBA_PADRAO)
            if bomb and not any(live.is_bomb(i['nome'], self.prefs) for i in self.live_catalog):
                self.live_catalog.insert(0, {'nome': bomb, 'moedas': 0, 'imagem': ''})
            # primeiro os que têm visual no jogo, depois os outros (cada grupo continua na ordem de moedas)
            self.live_catalog.sort(key=lambda i: not live.is_known(i['nome']))
            self.live_page = 0
            self._open('live_cfg')
        elif action and action.startswith('livegift_'):     # liga / desliga a interação com o jogo
            name = self.live_catalog[int(action.split('_')[1])]['nome']
            if not live.is_bomb(name, self.prefs):
                on = [i['nome'] for i in self.live_catalog if live.is_enabled(i['nome'], self.prefs)]
                was_on = live.is_enabled(name, self.prefs)
                on = [n for n in on if live._key(n) != live._key(name)] + ([] if was_on else [name])
                self.prefs['live_ligados'] = on
                self.save_prefs()
        elif action and action.startswith('livebomb_'):     # este presente vira a bomba (qualquer um)
            self.prefs['live_bomba'] = self.live_catalog[int(action.split('_')[1])]['nome']
            self.save_prefs()
        elif action and action.startswith('livepage_'):
            self.live_page = max(0, self.live_page + int(action.split('_')[1]))
        elif action == 'mode_ok':
            if self.mode_choice == 'live' and not self.user_text:
                self.mode_error = self.editing = True
                return None
            self.prefs['modo'], self.prefs['tiktok'] = self.mode_choice, self.user_text
            self.save_prefs()
            self.open_lobby()
            return 'mode'                       # o app liga ou desliga a conexão com a live
        elif action and action.startswith('arena_'):
            self.arena = int(action.split('_')[1])
            self.prefs['arena'] = self.arena
            self.save_prefs()
            return 'play'
        elif action == 'records':
            data = records.load(self.records_path)
            self.tables, self.supporters = data['tabelas'], data['doadores']
            self.records_arena = self.arena if self.arena in config.ARENAS else config.ARENAS[0]
            self.records_league = rank.tier_id(self.ranks.get(self.records_arena, rank.START))   # elo atual
            self._open('records')
            self.focus = config.ARENAS.index(self.records_arena)
        elif action == 'tab_presentes':
            self.records_arena = 'presentes'
            self.focus = len(config.ARENAS)
        elif action and action.startswith('tab_'):
            self.records_arena = int(action.split('_')[1])
            self.focus = config.ARENAS.index(self.records_arena)
        elif action and action.startswith('elo_'):
            self.records_league = action[len('elo_'):]
        elif action == 'settings':
            self._open('settings')
        elif action == 'skins':
            self._open('skins')
            skin = self.prefs.get('skin', 'classica')
            self.focus = self.skins.index(skin) if skin in self.skins else 0
        elif action and action.startswith('skin_'):
            skin = action[len('skin_'):]
            if skins.is_unlocked(skin, self.best_tier):
                self.prefs['skin'] = skin
                self.save_prefs()
        elif action == 'language':
            lang = i18n.next_language(i18n.language())
            i18n.set_language(lang)
            self.prefs['idioma'] = lang
            self.save_prefs()
        elif action in ('toggle_scenery', 'toggle_snake'):
            key = {'toggle_scenery': 'cenario_muda', 'toggle_snake': 'cobra_muda'}[action]
            self.prefs[key] = not self.prefs.get(key, True)
            self.save_prefs()
        elif settings.volume_action(self.prefs, action):         # − e + do som geral, da música e dos efeitos
            self.save_prefs()
        elif action == 'account_reset':
            self._open('conta')
        elif action == 'account_yes':                     # apaga tudo o que foi jogado (menos os presenteadores)
            account.reset(self.records_path, self.rank_path, self.profile_path)
            if not skins.is_unlocked(self.prefs.get('skin', 'classica'), 0):
                self.prefs['skin'] = 'classica'           # a skin de elo volta a ficar bloqueada
                self.save_prefs()
            self.profile_data = profile.load(self.profile_path) if self.profile_path else None
            self.ranks = rank.load(self.rank_path) if self.rank_path else {}
            self.best_tier = skins.best_tier(self.profile_data, self.ranks)
            self.top_score = records.best(records.load(self.records_path))
            self.tables = {}
            self.account_reset_at = self._time
            self._open('settings')
        elif action == 'back':
            self._go_back()
        elif action == 'quit':
            return action
        return None

    def _go_back(self):
        parent = PARENT.get(self.screen, 'main')
        if parent == 'profile':
            self.open_lobby()
        else:
            self._open(parent)

    def reset(self):
        """Volta para a capa."""
        self._open('main')

    def escape(self):
        """Esc: volta uma tela; na capa, sai do jogo."""
        if self.screen == 'main':
            return 'quit'
        self._go_back()
        return None

    def _open(self, screen):
        self.screen = screen
        self.name_editing = False          # trocou de tela: o campo do nome para de editar
        self.focus = 0
        self.show_focus = False
        self.pressed = None
