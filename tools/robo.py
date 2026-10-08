"""Robô jogando a Cobra dos Presentes: abre o jogo e a cobra anda sozinha (para ver se as metas são alcançáveis).

    python tools/robo.py                    # arena 11x11, velocidade normal
    python tools/robo.py --arena 18 --velocidade 3
    python tools/robo.py --frames PASTA     # sem janela: grava um PNG a cada --cada passos (para montar um vídeo)
    python tools/robo.py --live @usuario    # presentes vindos da live do TikTok (precisa do requirements-live.txt)
    python tools/robo.py --mudo             # sem som (por padrão toca efeitos e trilha, nos volumes das configurações)
    python tools/robo.py --espera 8         # segundos na tela de PDL antes de seguir sozinho (padrão 8)
    python tools/robo.py --espera-top 15    # segundos no pódio dos presenteadores (padrão 10)

Ao acabar a partida: tela de PDL; Continuar (clique ou Enter, ou sozinho depois de --espera s) vai para o pódio de
quem mais mandou presentes (só na live), que fica --espera-top s; depois começa outra partida (a live continua).

Estratégia: vai até o presente (se dá tempo) ou a maçã pelo caminho mais curto, mas só se, depois de comer, a cabeça ainda alcança
a cauda (assim não se tranca); senão segue a cauda pelo caminho que mais enrola. Desvia das bombas.
Teclas: Esc sai, espaço pausa, +/- muda a velocidade. Só precisa do pygame (como o jogo).
"""
import argparse
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from cobra import config, live, profile, rank  # noqa: E402
from cobra.logic import GameState  # noqa: E402
from cobra.robot import choose  # noqa: E402


# ---------------------------------------------------------------- janela
def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--arena', type=int, default=11, choices=config.ARENAS)
    ap.add_argument('--velocidade', type=float, default=1.0, help='multiplica a velocidade do jogo')
    ap.add_argument('--semente', type=int, help='sorteio fixo (a mesma partida sempre)')
    ap.add_argument('--frames', help='sem janela: pasta onde gravar os quadros')
    ap.add_argument('--cada', type=int, default=3, help='com --frames: grava um quadro a cada N passos')
    ap.add_argument('--live', metavar='@USUARIO', help='presentes vindos da live do TikTok desse @')
    ap.add_argument('--mudo', action='store_true', help='sem som')
    ap.add_argument('--espera', type=float, default=8.0, help='segundos na tela de PDL antes de seguir sozinho')
    ap.add_argument('--espera-top', type=float, default=10.0, help='segundos no pódio dos presenteadores')
    args = ap.parse_args()
    if args.frames:
        os.environ['SDL_VIDEODRIVER'] = 'dummy'

    import pygame
    from cobra import audio, i18n, settings
    from cobra.assets import Assets
    from cobra.manifest import load_manifest
    from cobra.render import Renderer
    from cobra.result import Result
    from cobra.widgets import FpsMeter

    pygame.init()
    i18n.set_language(i18n.detect_language())
    screen = pygame.display.set_mode((config.MIN_W, config.MIN_H))
    pygame.display.set_caption(f'Snakift - robô jogando {args.arena}x{args.arena}')
    man = load_manifest()
    renderer = Renderer(screen, Assets(man))
    prefs = settings.load(config.CONFIGURACOES_ARQUIVO or settings.default_path())     # volumes das configurações
    sound = None if args.frames or args.mudo else audio.Audio(prefs)
    renderer.prefs = prefs                                       # presente escolhido como bomba (legenda)
    r = rank.Rank(len(config.RANQUE_LIGAS) - 1, 0, 0)            # joga como Mestre (meta e maçãs do Mestre)
    connection = live.LiveConnection(args.live).start() if args.live else None
    steps, games, best = 0, 0, 0
    board = live.Leaderboard()                                   # quem mais mandou presentes na partida

    def robot(s):                       # a partida pede a direção ao robô antes de cada passo (como a tecla B)
        nonlocal steps
        steps += 1
        return choose(s, avoid_bombs=False)             # nas lives: pega a bomba só se senão ficaria preso

    def new_game():
        """Partida nova (a cada uma, outro sorteio; com --semente, sementes seguidas)."""
        seed = None if args.semente is None else args.semente + games
        g = GameState(man.food_to_theme, n=args.arena, rng=random.Random(seed),
                      bomb_theme=man.bomb_theme, apple_tier=r.tier, live=bool(args.live))
        g.controller = robot
        board.__init__()                                # top da live zera a cada partida
        return g
    state = new_game()
    over_for = 0.0                                               # segundos no quadro final
    renderer.player_name = 'Robô'
    renderer.legend_open = True                                  # quanto vale cada presente, sempre à mostra
    renderer.minimal_hud = True                                  # só o placar e o elo (tela limpa para a live)
    renderer.rank_info = (r, rank.target(r, args.arena))
    clock, speed, paused, result, saved = pygame.time.Clock(), args.velocidade, False, None, 0
    fps = FpsMeter()                                             # contador de FPS no canto (sempre ligado)
    last_status = None                                           # estado da live já escrito no terminal
    if args.frames:
        os.makedirs(args.frames, exist_ok=True)

    while True:
        dt = 1 / 30 if args.frames else clock.tick(60) / 1000
        fps.tick(dt)
        go_on = False                                            # Continuar na tela de PDL
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                if connection is not None:
                    connection.stop()
                pygame.quit()
                return
            if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                paused = not paused
            if e.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
                renderer.mouse = e.pos
            clicked = e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and renderer.button_at(e.pos) == 'continue'
            entered = e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER)
            if result is not None and result.phase in ('ranque', 'top') and (clicked or entered):
                go_on = True                                     # Continuar (no pódio, pula a espera)
            if e.type == pygame.KEYDOWN and e.unicode in '+=':
                speed = min(speed * 1.5, 30)
            if e.type == pygame.KEYDOWN and e.unicode == '-':
                speed = max(speed / 1.5, 0.25)
        if connection is not None:
            orders = connection.poll()
            tributes = connection.poll_tributes()
            if not paused and not state.over:
                live.apply_orders(state, orders)
                for tribute in tributes:
                    board.add(tribute)
            renderer.live_info = (connection.username, connection.status)
            if connection.status[:2] != last_status:            # na tela fica só a bolinha: o motivo vai aqui
                last_status = connection.status[:2]
                state_, reason, retry = connection.status
                parts = [i18n.t(f'live.{state_}', u=connection.username)]
                if reason:
                    parts.append(i18n.t(f'live.reason.{reason}'))
                if retry:
                    parts.append(i18n.t('live.retry', s=retry))
                print('[live]', '  ·  '.join(parts))
        if not paused and not state.over:
            # o relógio da partida anda a cada quadro (como no jogo): os passos da cobra saem no ritmo dela e os
            # presentes, bombas e maçãs voando se mexem lisos (antes só andavam a cada passo da cobra)
            state.update(dt * speed)
            if args.frames and steps // args.cada > saved:
                saved = steps // args.cada
                renderer.draw(state)
                pygame.image.save(screen, os.path.join(args.frames, f'{steps:06d}.png'))
        elif state.over:
            state.update(dt)
            if result is None:                                   # quadro do fim, com o que o ranque daria
                out = rank.apply_match(r, state.score, state.eaten, state.n, state.play_time, state.bombs)
                result = Result(state, os.devnull, out)
                result.xp_info = (out.xp, 1, profile.level({'arenas': {}}))
                result.supporters = board.top(3)                 # para o pódio, depois da tela de PDL
                games += 1
                best = max(best, state.score)
                print(f'partida {games}: {state.score} pontos, cobra com {len(state.snake)}, '
                      f'{state.play_time / 60:.1f} min, {state.bombs} bomba(s) (recorde da sessão: {best})')
            over_for += dt
            if not args.frames:
                done_rank = result.phase == 'ranque' and (go_on or over_for >= args.espera)
                if done_rank and args.live:                      # PDL -> pódio dos presenteadores
                    result.phase, over_for = 'top', 0.0
                elif done_rank or (result.phase == 'top' and (go_on or over_for >= args.espera_top)):
                    state, result, over_for = new_game(), None, 0.0      # próxima partida, sozinho (sem live,
                    renderer.best_score = best                           # não há pódio)
            if args.frames:
                for i in range(90):                              # 3 s do quadro final
                    state.update(1 / 30)
                    renderer.draw(state, result=result)
                    pygame.image.save(screen, os.path.join(args.frames, f'{steps:06d}_{i:03d}.png'))
                print(f'fim: {state.score} pontos, cobra com {len(state.snake)}, {state.play_time / 60:.1f} min, '
                      f'{steps} passos')
                pygame.quit()
                return
        if sound is not None:                                    # efeitos (cada um uma vez por quadro) e trilha
            sound.play_events(list(dict.fromkeys(state.events)))
            sound.update_music()
        state.events.clear()
        renderer.draw(state, result=result)
        if not args.frames:
            fps.draw(screen)
        pygame.display.flip()


if __name__ == '__main__':
    main()
