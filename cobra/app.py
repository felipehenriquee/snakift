"""Janela, laço principal, teclado e mouse.

O jogo abre na tela inicial (JOGAR e X para sair). JOGAR abre o perfil, que é o lobby: cada
arena tem o seu JOGAR. Toda partida que começa pelo lobby mostra a abertura (a câmera se
aproxima do tabuleiro); "jogar de novo" vai direto. Sair de uma partida volta ao lobby.
Na partida: setas ou WASD movem a cobra na mesma direção da tela; Esc pausa (e dá para sair); Tab (ou o
botão redondo ao lado do placar) mostra quanto vale cada presente.
No fim de jogo, os botões do quadro podem ser clicados ou usados pelo teclado
(Enter confirma tudo: continuar, salvar o nome do recorde e jogar de novo; R = recordes).
"""
import os

import pygame

from . import audio, config, i18n, live, profile, rank, records, robot, settings, skins
from .assets import Assets
from .intro import Intro
from .logic import GameState
from .manifest import load_manifest
from .menu import Menu
from .render import RANK_BAR_START, Renderer
from .result import Result
from .widgets import FpsMeter

KEYS = {pygame.K_UP: 'N', pygame.K_w: 'N', pygame.K_RIGHT: 'E', pygame.K_d: 'E',
        pygame.K_DOWN: 'S', pygame.K_s: 'S', pygame.K_LEFT: 'W', pygame.K_a: 'W'}
MENU_UP = (pygame.K_UP, pygame.K_w)
MENU_DOWN = (pygame.K_DOWN, pygame.K_s)
CONFIRM = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)     # no menu
ENTER = (pygame.K_RETURN, pygame.K_KP_ENTER)                       # na partida: uma tecla só para confirmar


def open_window():
    """Janela redimensionável que cabe na tela, com a proporção da resolução lógica."""
    dw, dh = pygame.display.get_desktop_sizes()[0]
    k = min(1.0, 0.92 * dw / config.WIN_W, 0.85 * dh / config.WIN_H)
    return pygame.display.set_mode((round(config.WIN_W * k), round(config.WIN_H * k)), pygame.RESIZABLE)


def canvas_size(window_size):
    """Tamanho em que o jogo desenha: o da janela, ou maior (mesma proporção) se a janela for pequena demais.

    Desenhar no tamanho da janela evita escalar a imagem inteira a cada quadro.
    """
    ww, wh = max(window_size[0], 1), max(window_size[1], 1)
    k = max(1.0, config.MIN_W / ww, config.MIN_H / wh)
    return round(ww * k), round(wh * k)


def present(canvas, window):
    """Copia a tela lógica para a janela (mesma proporção, então ocupa a janela toda)."""
    if window.get_size() == canvas.get_size():
        window.blit(canvas, (0, 0))
    else:
        pygame.transform.smoothscale(canvas, window.get_size(), window)


class App:
    """mode: 'menu', 'intro' (câmera se aproximando) ou 'game'."""

    def __init__(self, window):
        self.window = window
        self.canvas = pygame.Surface(canvas_size(window.get_size()))
        self.settings_path = config.CONFIGURACOES_ARQUIVO or settings.default_path()
        self.prefs = settings.load(self.settings_path)
        i18n.set_language(self.prefs['idioma'])
        self.records_path = config.RECORDES_ARQUIVO or records.default_path()
        self.rank_path = config.RANQUE_ARQUIVO or rank.default_path()
        self.profile_path = config.PERFIL_ARQUIVO or profile.default_path()
        self.manifest = load_manifest()
        self.assets = Assets(self.manifest)
        self.renderer = Renderer(self.canvas, self.assets)
        if self.prefs['skin'] not in self.manifest.skins or not self._skin_unlocked(self.prefs['skin']):
            self.prefs['skin'] = 'classica'                 # skin que não existe mais ou ainda não foi liberada
        self.state = GameState(self.manifest.food_to_theme, bomb_theme=self.manifest.bomb_theme)
        self.menu = Menu(self.records_path, self.prefs, self._save_prefs, self.rank_path, self.profile_path,
                         self.manifest.skins)
        self.mode = 'menu'
        self.intro = None
        self.result = None                  # quadro de fim de jogo (recorde, resumo, tabela)
        self.paused = False                 # menu de pausa aberto (Esc durante a partida)
        self.running = True
        self.hand = False                   # cursor de mãozinha em cima de botão
        self.live = None                    # conexão com a live do TikTok (modo live)
        self.audio = audio.Audio(self.prefs)
        self._rank_sounds = set()           # fanfarras da tela do ranque já tocadas nesta partida
        self.autopilot = False              # robô jogando (tecla B); continua ligado nas próximas partidas
        self.robot_mode = config.MODO_ROBO  # build com robô: o robô joga todas as partidas, que contam
        self._end_phase, self._end_t = None, 0.0    # modo robô: fase do fim de partida e há quanto tempo está nela
        if self.robot_mode:                 # tela limpa para a live: só o placar (com os presentes) e o elo
            self.renderer.legend_open = True
            self.renderer.minimal_hud = True
        self._ensure_live()

    def _ensure_live(self):
        """Liga a conexão com a live no modo live (com o @ escolhido) e desliga no modo offline."""
        user = self.prefs.get('tiktok', '').strip().lstrip('@')
        want = self.prefs.get('modo') == 'live' and user
        if self.live is not None and (not want or self.live.username != user):
            self.live.stop()
            self.live = None
        if want and self.live is None:
            self.live = live.LiveConnection(user, options=lambda: self.prefs).start()

    def close(self):
        if self.live is not None:
            self.live.stop()

    def _skin_unlocked(self, skin):
        tier = skins.best_tier(profile.load(self.profile_path), rank.load(self.rank_path))
        return skins.is_unlocked(skin, tier)

    def _live_name(self):
        """O @ da live (nome dos recordes no modo live) ou None no offline."""
        name = settings.player_name(self.prefs, None)
        return name if self.state is not None and self.state.live else None

    def _save_prefs(self):
        try:
            settings.save(self.settings_path, self.prefs)
        except OSError:                     # sem permissão: vale só nesta sessão
            pass

    # ------------------------------------------------------------ modos
    def start_game(self, arena=None, intro=False):
        """Nova partida. arena: tamanho escolhido no menu (None = o da anterior); intro: começa com o zoom."""
        if arena is not None and arena != self.state.n:
            self.state = GameState(self.manifest.food_to_theme, n=arena, bomb_theme=self.manifest.bomb_theme)
        self.state.apple_tier = self._current_rank().tier          # maçãs do elo da arena
        self.state.live = self.prefs.get('modo') == 'live'         # presentes só da live
        self.state.reset()
        if self.robot_mode:                     # o robô joga e a partida vale (pega bomba só em último caso)
            self.state.controller = lambda s: robot.choose(s, avoid_bombs=False)
            self.state.ranked_robot = True
        else:
            self.state.controller = robot.choose if self.autopilot else None
        self._end_phase, self._end_t = None, 0.0
        self.result = None
        self._rank_sounds = set()
        self.board = live.Leaderboard()             # quem mais mandou presentes nesta partida (modo live)
        self.paused = False
        self.refresh_best()
        self.renderer.player_name = settings.player_name(self.prefs, records.load(self.records_path)['ultimo_nome'])
        if intro and config.INTRO_SEGUNDOS > 0:
            self.intro = Intro(self.canvas, self.assets, self.state, skin=self.prefs['skin'])
            self.mode = 'intro'
            self.audio.play('contagem_321_vai')         # o "vai!" cai perto do fim da aproximação
        else:
            self.mode = 'game'

    def _current_rank(self):
        return rank.load(self.rank_path)[self.state.n] if self.state.n in config.ARENAS else rank.START

    def refresh_best(self):
        """1º lugar dos recordes da arena no elo atual e o elo, para o placar."""
        current = self._current_rank()
        table = records.table(records.load(self.records_path), self.state.n, rank.tier_id(current))
        self.renderer.best_score = table[0]['pontos'] if table else 0
        self.renderer.rank_info = (current, rank.target(current, self.state.n))

    def finish_match(self):
        """Fim de partida: aplica o resultado no elo da arena, salva e abre o quadro."""
        outcome = None
        self._save_supporters()
        if self.state.practice:                     # treino (o robô jogou): só o resumo
            self.result = Result(self.state, self.records_path)
            return
        if self.state.n in config.ARENAS:
            ranks = rank.load(self.rank_path)
            table = records.table(records.load(self.records_path), self.state.n, rank.tier_id(ranks[self.state.n]))
            outcome = rank.apply_match(ranks[self.state.n], self.state.score, self.state.eaten, self.state.n,
                                       play_time=self.state.play_time, bombs=self.state.bombs,
                                       record_pos=records.position(table, self.state.score))
            stats = profile.load(self.profile_path)
            tier_before = skins.best_tier(stats, ranks)     # maior liga antes desta partida (para as skins)
            ranks[self.state.n] = outcome.after
            level_before = profile.level(stats)[0]
            profile.record_match(stats, self.state.n, self.state.score, self.state.eaten, self.state.play_time,
                                 outcome.won, outcome.after, outcome.xp)
            xp_info = (outcome.xp, level_before, profile.level(stats))     # para a tela do ranque
            new_skins = skins.newly_unlocked(self.manifest.skins, tier_before, skins.best_tier(stats, ranks))
            if new_skins:                   # chegou na liga de uma skin: libera e já equipa (a mais forte)
                self.prefs['skin'] = new_skins[-1]
                self._save_prefs()
            try:
                rank.save(self.rank_path, ranks)
                profile.save(self.profile_path, stats)
            except OSError:                 # sem permissão: o elo e o perfil valem só nesta sessão
                pass
        self.result = Result(self.state, self.records_path, outcome, live_name=self._live_name())
        if outcome is not None:
            self.result.xp_info = xp_info
            self.result.new_skin = new_skins[-1] if new_skins else None

    def _play_rank_sounds(self):
        """Na tela do ranque: fanfarra quando a barra sobe de elo e o som de subir de nível."""
        res = self.result
        if res is None or res.phase != 'ranque' or res.rank_outcome is None:
            return
        el = self.state.time - res.started
        _, _, event, when = Renderer.rank_timeline(res.rank_outcome, el)
        if event == 'sobe' and ('elo', when) not in self._rank_sounds:
            self._rank_sounds.add(('elo', when))
            self.audio.play('subir_elo')
        up = res.xp_info is not None and res.xp_info[2][0] > res.xp_info[1]
        if up and el >= RANK_BAR_START and 'nivel' not in self._rank_sounds:
            self._rank_sounds.add('nivel')
            self.audio.play('subir_nivel')

    def _save_supporters(self):
        """Live: soma quem mandou presentes nesta partida aos recordes de doadores (valem mesmo com o robô
        jogando, porque os presentes são de espectadores de verdade)."""
        real = list(self.board.users.values())
        if not self.state.live or not real:
            return
        try:
            data = records.load(self.records_path)
            records.save(self.records_path, records.add_supporters(data, real))
        except OSError:                     # sem permissão: fica só no top da partida
            pass

    def go_menu(self):
        if self.result is not None and self.result.phase == 'nome':   # saiu digitando o nome: salva assim mesmo
            self.result.confirm()
        self.paused = False
        self.mode = 'menu'
        self.intro = None
        self.menu.open_lobby()

    def game_action(self, action):
        """Botões do quadro de fim de jogo (clicados ou pelo atalho de teclado)."""
        if action == 'resume':                  # menu de pausa
            self.paused = False
        elif self.paused and settings.volume_action(self.prefs, action):     # − e + dos volumes na pausa
            self._save_prefs()
        elif action == 'leave' and self.paused:  # sai sem terminar: não conta no ranque, perfil nem recordes
            self.go_menu()
        elif action == 'restart' and self.state.over:
            self.start_game()
        elif action == 'menu' and self.state.over:
            self.go_menu()
        elif action == 'legend':                # botão ao lado do placar
            self.renderer.legend_open = not self.renderer.legend_open
        elif action == 'records' and self.result is not None:
            self.result.toggle_table()
        elif action == 'continue' and self.result is not None:
            self.result.continue_rank()
        elif action == 'save' and self.result is not None:
            self.result.confirm()
            self.refresh_best()

    def menu_action(self, action):
        what = self.menu.activate(action)
        if what == 'play':
            self.start_game(self.menu.arena, intro=True)       # vindo do menu: sempre com o zoom
        elif what == 'mode':                                    # escolheu offline / live na tela do modo
            self._ensure_live()
        elif what == 'quit':
            self.running = False

    # ------------------------------------------------------------ eventos
    def to_canvas(self, pos):
        w, h = self.window.get_size()
        return pos[0] * self.canvas.get_width() / w, pos[1] * self.canvas.get_height() / h

    def handle(self, e):
        if e.type == pygame.QUIT:
            self.running = False
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_F3:       # liga / desliga o contador de FPS
            self.prefs['mostrar_fps'] = not self.prefs.get('mostrar_fps', False)
            self._save_prefs()
        elif self.mode == 'menu':
            self.handle_menu(e)
        elif self.mode == 'intro':
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.go_menu()
            elif e.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):     # qualquer tecla ou clique pula
                self.intro.skip()
        else:
            self.handle_game(e)

    def handle_menu(self, e):
        if e.type == pygame.MOUSEMOTION:
            self.menu.hover(self.to_canvas(e.pos))
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.menu.press(self.to_canvas(e.pos))            # mostra o botão "pressionado"
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            action = self.menu.release(self.to_canvas(e.pos))     # vale ao soltar em cima do mesmo botão
            if action:
                self.menu_action(action)
        elif e.type == pygame.KEYDOWN:
            if self.menu.type_key(e.key, e.unicode):        # digitando o @ da live
                return
            if e.key == pygame.K_ESCAPE:
                if self.menu.escape() == 'quit':
                    self.running = False
            elif e.key in (pygame.K_LEFT, pygame.K_a):
                self.menu.switch_tab(-1)
            elif e.key in (pygame.K_RIGHT, pygame.K_d):
                self.menu.switch_tab(1)
            elif e.key in MENU_UP:
                self.menu.move_focus(-1)
            elif e.key in MENU_DOWN:
                self.menu.move_focus(1)
            elif e.key in CONFIRM:          # atalho da tela (Enter = Jogar na capa) ou o botão selecionado
                self.menu_action(self.menu.hotkey_action(pygame.K_RETURN) or self.menu.focused_action())

    def handle_game(self, e):
        state, result = self.state, self.result
        if e.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
            self.renderer.mouse = self.to_canvas(e.pos)
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self.game_action(self.renderer.button_at(self.renderer.mouse))
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                if state.over:
                    self.go_menu()
                else:
                    self.paused = not self.paused       # pausa / continua
            elif self.paused:
                if e.key in ENTER:
                    self.game_action('resume')
            elif result is not None and result.phase in ('ranque', 'top'):     # PDL e pódio da live
                if e.key in ENTER:
                    self.game_action('continue')
            elif result is not None and result.phase == 'nome':     # digitando o nome do recorde
                if e.key in ENTER:
                    self.game_action('save')
                elif e.key == pygame.K_BACKSPACE:
                    result.backspace()
                elif e.unicode:
                    result.type_char(e.unicode)
            elif state.over and e.key == pygame.K_r:
                self.game_action('records')
            elif state.over and e.key in ENTER:
                self.game_action('restart')
            elif e.key == pygame.K_TAB:
                self.game_action('legend')
            elif e.key == pygame.K_b and not state.over and not self.robot_mode:     # robô assume / devolve
                self.autopilot = not self.autopilot
                state.controller = robot.choose if self.autopilot else None
                state.queue = []
            elif e.key in KEYS:
                state.queue_turn(KEYS[e.key])

    # ------------------------------------------------------------ quadro
    def frame(self, dt, time):
        self.renderer.skin = self.prefs['skin']             # o menu pode trocar essas opções
        self.renderer.prefs = self.prefs
        self.renderer.scenery_changes = self.prefs['cenario_muda']
        self.renderer.snake_changes = self.prefs['cobra_muda']
        if self.canvas.get_size() != canvas_size(self.window.get_size()):     # janela redimensionada
            self.canvas = pygame.Surface(canvas_size(self.window.get_size()))
            self.renderer.set_screen(self.canvas)
            if self.mode == 'intro':        # a abertura foi preparada para o tamanho antigo
                self.intro, self.mode = None, 'game'
        orders = self.live.poll() if self.live is not None else []     # presentes que chegaram da live
        tributes = self.live.poll_tributes() if self.live is not None else []
        if self.mode == 'game' and not self.paused and not self.state.over and self.state.live:
            live.apply_orders(self.state, orders)                       # fora da partida eles se perdem
            for tribute in tributes:
                self.board.add(tribute)
        self.renderer.live_info = (self.live.username, self.live.status) if self.live is not None else None
        self.renderer.autopilot = self.autopilot
        self.audio.update_music()               # a trilha segue a configuração (pode mudar no menu)
        if self.mode == 'menu':
            self.menu.draw(self.canvas, time)
        elif self.mode == 'intro':
            self.intro.draw(dt)             # o jogo só começa quando a câmera chega
            if self.intro.done:
                self.intro, self.mode = None, 'game'
        else:
            if not self.paused:                 # pausado: a partida (e o tempo) param
                self.state.update(dt)
            self.audio.play_events(self.state.events)
            self.state.events.clear()
            self._play_rank_sounds()
            if self.state.over and self.result is None:
                self.finish_match()
                if self.state.live:                     # top da live no pódio
                    self.result.supporters = self.board.top(config.LIVE_TOP)
            if self.robot_mode and self.result is not None:
                self._robot_end(dt)
            if self.mode == 'game':
                self.renderer.draw(self.state, result=self.result, paused=self.paused)
        self._update_cursor()

    def _robot_end(self, dt):
        """Modo robô: o fim da partida segue sozinho (os botões também funcionam): tela de PDL, pódio da live,
        recorde salvo com o nome (ou o @ na live) e uma partida nova na mesma arena."""
        res = self.result
        if res.phase != self._end_phase:
            self._end_phase, self._end_t = res.phase, 0.0
        self._end_t += dt
        if res.phase == 'ranque' and self._end_t >= config.ROBO_ESPERA_PDL:
            res.continue_rank()
        elif res.phase == 'top' and self._end_t >= config.ROBO_ESPERA_TOP:
            res.continue_rank()
        elif res.phase == 'nome':
            res.confirm()
        elif res.phase in ('resumo', 'tabela'):
            self.start_game()

    def _update_cursor(self):
        if self.mode == 'menu':
            over = self.menu.button_at(self.to_canvas(pygame.mouse.get_pos())) is not None
        else:
            over = self.mode == 'game' and self.renderer.mouse is not None \
                and self.renderer.button_at(self.renderer.mouse) is not None
        if over != self.hand:
            self.hand = over
            try:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND if over else pygame.SYSTEM_CURSOR_ARROW)
            except pygame.error:            # sistema sem cursores (ex.: sem janela)
                pass


def set_window_icon():
    """Ícone da janela e da barra de tarefas (o da versão com robô tem antena e fone)."""
    name = 'snakift_robo.png' if config.MODO_ROBO else 'snakift.png'
    try:
        pygame.display.set_icon(pygame.image.load(os.path.join(config.ICON_DIR, name)))
    except (pygame.error, FileNotFoundError):
        pass


def main():
    pygame.init()
    try:
        set_window_icon()                   # antes de abrir a janela (alguns sistemas só leem o ícone nela)
        window = open_window()
        pygame.display.set_caption(config.TITLE + (' (robô)' if config.MODO_ROBO else ''))
        app = App(window)
        clock = pygame.time.Clock()
        fps = FpsMeter()
        time = 0.0
        while app.running:
            raw = clock.tick(config.FPS) / 1000
            fps.tick(raw)
            dt = min(raw, config.MAX_DT)
            time += dt
            app.window = pygame.display.get_surface()
            for e in pygame.event.get():
                app.handle(e)
            if not app.running:
                break
            app.frame(dt, time)
            present(app.canvas, app.window)
            if app.prefs.get('mostrar_fps'):
                fps.draw(app.window)
            pygame.display.flip()
        app.close()
    finally:
        pygame.quit()
