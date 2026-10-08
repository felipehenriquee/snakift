"""Screenshots do jogo sem abrir janela (SDL_VIDEODRIVER=dummy), para conferir o visual.

    python tools/screenshots.py [--out _nao_usados/screenshots] [--perspectivas 0 0.15]

Joga uma partida roteirizada (a cobra come três comidas e faz curvas) e salva um PNG por
valor de perspectiva, com a cobra no meio de um passo. Também salva três quadros da abertura
(câmera longe, no meio da aproximação e chegando).
"""
import argparse
import os
import random
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame

from cobra import config
from cobra.assets import Assets
from cobra.intro import Intro
from cobra.logic import DIRS, GameState
from cobra.manifest import load_manifest
from cobra.render import Renderer

MOVES = 'EEESSSSWWWWWWWNNNNEEE'
EAT_AT = {2: 'rosa', 9: 'esquilo', 16: 'rosquinha'}     # passo -> comida colocada logo à frente


def play(state):
    for k, d in enumerate(MOVES):
        state.queue_turn(d)
        if k in EAT_AT:
            hx, hy = state.snake[0]
            dx, dy = DIRS[d]
            state.food, state.food_kind = (hx + dx, hy + dy), EAT_AT[k]
        state.step()
    state.food, state.food_kind = (8, 2), 'maca'          # a maçã volta a cobra para o tema clássico
    state.wave_t = 99.0                         # onda de troca de cenário já terminou
    state.acc = state.step_time * 0.5           # cobra no meio do passo (posições interpoladas)
    state.queue_turn('S')
    state.popups = []                           # o roteiro não passa por update(), então os "+10" não expirariam


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, '_nao_usados', 'screenshots'))
    ap.add_argument('--perspectivas', nargs='+', type=float, default=[0.0, 0.15])
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    pygame.init()
    pygame.display.set_mode((1, 1))
    canvas = pygame.Surface((config.WIN_W, config.WIN_H))
    man = load_manifest()
    assets = Assets(man)
    for p in args.perspectivas:
        state = GameState(man.food_to_theme, rng=random.Random(1))
        play(state)
        Renderer(canvas, assets, perspective=p).draw(state)
        path = os.path.join(args.out, f'perspectiva_{p:g}'.replace('.', '_') + '.png')
        pygame.image.save(canvas, path)
        print(path)

    # bomba na tela e, ao lado, a cobra queimada depois de pegar uma
    from cobra.logic import Bomb
    state = GameState(man.food_to_theme, rng=random.Random(1), bomb_theme=man.bomb_theme)
    play(state)
    state.bomb = Bomb((7, 7), state.play_time + 30)
    Renderer(canvas, assets).draw(state)
    pygame.image.save(canvas, os.path.join(args.out, 'bomba.png'))
    hx, hy = state.snake[0]
    dx, dy = DIRS[state.dir]
    state.queue = []
    state.bomb = Bomb((hx + dx, hy + dy), state.play_time + 30)
    state.food = (2, 8)
    state.step()                                # pega a bomba
    state.wave_t, state.time = 99.0, state.time + 0.3
    Renderer(canvas, assets).draw(state)
    path = os.path.join(args.out, 'queimado.png')
    pygame.image.save(canvas, path)
    print(path)

    # fim de jogo: a partida roteirizada termina no tema rosquinha
    state = GameState(man.food_to_theme, rng=random.Random(1))
    play(state)
    state.play_time, state.dead = 83.0, True
    Renderer(canvas, assets).draw(state)
    path = os.path.join(args.out, 'fim_de_jogo.png')
    pygame.image.save(canvas, path)
    print(path)

    intro = Intro(canvas, assets, GameState(man.food_to_theme, rng=random.Random(1)))
    for name, frac in (('intro_longe', 0.0), ('intro_meio', 0.5), ('intro_chegando', 0.85)):
        intro.t = frac * intro.duration
        intro.draw(0.0)
        path = os.path.join(args.out, name + '.png')
        pygame.image.save(canvas, path)
        print(path)
    pygame.quit()


if __name__ == '__main__':
    main()
