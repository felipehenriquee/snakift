"""Cenário em volta do tabuleiro: cerca e decoração. Não depende do pygame.

A partida acontece só dentro da cerca; fora dela é tudo cenário.
"""
import random
from collections import namedtuple

Prop = namedtuple('Prop', 'cell variant')
FencePiece = namedtuple('FencePiece', 'pos piece')     # pos pode ser fracionária (cerca na borda)


def make_fence(n, on_edge=True):
    """Peças da cerca em volta do tabuleiro.

    on_edge=True: a cerca fica encostada na borda (meia célula para dentro do anel de fora)
    e os cantos são postes. on_edge=False: cada peça fica no centro de uma célula de fora.
    """
    lo, hi = (-0.5, n - 0.5) if on_edge else (-1, n)
    pieces = []
    for i in range(n):
        pieces += [FencePiece((i, lo), 'reta_x'), FencePiece((i, hi), 'reta_x'),
                   FencePiece((lo, i), 'reta_y'), FencePiece((hi, i), 'reta_y')]
    corners = {(lo, lo): 'canto_ES', (hi, lo): 'canto_WS', (lo, hi): 'canto_EN', (hi, hi): 'canto_WN'}
    for pos, piece in corners.items():
        pieces.append(FencePiece(pos, 'poste' if on_edge else piece))
    return pieces


def outside_distance(n, cell):
    """Quantas células a `cell` está fora do tabuleiro (0 = dentro)."""
    gx, gy = cell
    return max(0, -gx, gx - (n - 1), -gy, gy - (n - 1))


def make_props(n, cells, on_edge=True, density=0.2, gap=1, seed=3):
    """Decoração espalhada pelas células de fora da cerca.

    Cada célula decide sozinha (sorteio com semente própria) se tem um prop, então o
    cenário é o mesmo qualquer que seja o tamanho da tela. `gap` = anéis livres em volta da
    cerca, para nenhuma decoração ficar encostada nela.
    """
    min_dist = (1 if on_edge else 2) + gap      # com a cerca no centro das células de fora, ela ocupa um anel
    props = []
    for gx, gy in cells:
        if outside_distance(n, (gx, gy)) < min_dist:
            continue
        rnd = random.Random(f'{seed}:{gx}:{gy}')
        if rnd.random() < density:
            props.append(Prop((gx, gy), rnd.randint(0, 1)))
    return props
