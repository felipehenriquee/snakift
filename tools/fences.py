"""Cercas em volta do tabuleiro: uma por tema, montadas peça a peça.

Cada peça ocupa uma célula (1x1) e tem um poste no centro; as travessas vão do centro
até a borda da célula na direção de cada "braço", então peças vizinhas se encaixam.
  reta_x            braços E e W (corre ao longo de gx)
  reta_y            braços N e S (corre ao longo de gy)
  canto_ES ...      canto com braços para E e S (canto de cima-esquerda do tabuleiro), etc.
  poste             só o poste (usado nos cantos quando a cerca fica encostada na borda)
"""
import numpy as np
from sdf import Part, Scene, rbox, sphere, C, fbm

PIECES = {
    'reta_x': 'EW',
    'reta_y': 'NS',
    'canto_ES': 'ES',
    'canto_WS': 'WS',
    'canto_EN': 'EN',
    'canto_WN': 'WN',
    'poste': '',
}
ARM = {'E': np.array([1.0, 0, 0]), 'W': np.array([-1.0, 0, 0]),
       'S': np.array([0, 0, 1.0]), 'N': np.array([0, 0, -1.0])}

FENCE_PAL = {   # poste, travessa, topo do poste
    'classico': (C('#f6f1e7'), C('#ece3d3'), C('#ff6b6b')),
    'rosa': (C('#ff8fb1'), C('#ffc4d6'), C('#ff3f6f')),
    'rosquinha': (C('#fff3e0'), C('#ff8cc6'), C('#8fd8ff')),
    'esquilo': (C('#8a5a32'), C('#a8703e'), C('#c98b4a')),       # troncos, com bolota no topo
    'coracao': (C('#d9a21b'), C('#f0c64a'), C('#fff6fb')),       # ouro, com pérola no topo
    'caracol': (C('#a7adb8'), C('#c3c9d3'), C('#a6e03c')),
    'caixa': (C('#9b6bff'), C('#ffd23f'), C('#ff5fa2')),         # poste roxo, travessas de fita dourada, bolinha rosa
    'queimado': (C('#2f2a27'), C('#3b3532'), C('#ff7a2a')),       # madeira chamuscada, pontas em brasa
}

POST_H, POST_W = 0.36, 0.055        # altura e meia-largura do poste
RAIL_Y = (0.13, 0.27)               # altura das duas travessas
RAIL_T = 0.022                      # meia-espessura da travessa


def _textured(col, wood):
    if not wood:
        return col
    return lambda q: col * (0.88 + 0.24 * fbm(q * np.array([4, 30, 4]), 2))[:, None]


def fence(theme, piece):
    if theme == 'coracao':                  # cerca de ouro e pérola do pacote tema_coracao
        import tema_coracao
        return tema_coracao.fence(piece)
    post, rail, cap = FENCE_PAL[theme]
    wood = theme in ('esquilo', 'queimado')
    arms = PIECES[piece]
    parts = [
        Part(lambda q: rbox(q, np.array([0, POST_H / 2, 0]), np.array([POST_W, POST_H / 2, POST_W]), 0.02), _textured(post, wood), 0.3),
        Part(lambda q: sphere(q, np.array([0, POST_H + 0.03, 0]), 0.055), cap, 0.6, 0.02),
    ]
    for a in arms:
        d = ARM[a]
        half = np.abs(d) * 0.25 + (1 - np.abs(d)) * np.array([RAIL_T, RAIL_T, RAIL_T])
        for y in RAIL_Y:
            c = d * 0.25 + np.array([0, y, 0])
            parts.append(Part(lambda q, c=c, half=half: rbox(q, c, half, 0.012), _textured(rail, wood), 0.3))
        # ripa no meio do braço
        pc = d * 0.3
        parts.append(Part(lambda q, pc=pc: rbox(q, pc + np.array([0, 0.15, 0]), np.array([0.035, 0.15, 0.035]), 0.015),
                          _textured(post, wood), 0.3))
    return Scene(parts)
