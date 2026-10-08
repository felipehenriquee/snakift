"""Tema 'caixa' (caixa de presente da live): a cobra vira uma fila de caixinhas de presente embrulhadas.

Só quem manda um presente que não tem skin no jogo (a caixa) faz a cobra virar esse tema. O corpo são caixinhas com
papel de bolinhas (roxo e verde-água, alternando) e fita dourada em cruz, como a caixa da live; a cabeça usa um laço
grande. Cenário de festa: chão com confete, pilha de presentes e balões, cerca nas cores da fita.
O gerador (build.py) usa estas funções para a cobra, o chão, os props e a cerca do tema.
"""
import numpy as np
from sdf import *
from sdf import _hash
import models as m
from fences import ARM, PIECES
from models import V, smooth, head_eyes, face_col

RIBBON, RIBBON_D = C('#ffd23f'), C('#e0a419')                       # a fita da caixa da live
PAPERS = [(C('#8a4dff'), C('#6a2fd6'), C('#ffd23f'), C('#ff7ac0')),  # papel, sombra, bolinhas (duas cores)
          (C('#2ec4b6'), C('#1d9c91'), C('#ffffff'), C('#ff7ac0'))]
PINK, PINK_D = C('#ff5fa2'), C('#d93a7f')
FUNDO = '#e9ddff'


def paper(v, c, h=0.45, scale=9.0):
    """Papel de presente com bolinhas (duas cores, sorteadas por bolinha), mais escuro embaixo."""
    top, low, dot_a, dot_b = PAPERS[v]
    c = np.asarray(c, float)

    def f(q):
        cell = np.floor(q * scale)
        d = length(((q * scale) % 1.0) - 0.5)
        dots = smooth((0.27 - d) / 0.05)
        dc = np.where((_hash(cell) > 0.5)[:, None], dot_a, dot_b)
        base = mix(low, top, smooth((q[:, 1] - c[1] + h * 0.6) / h))
        return mix(base, dc, dots * 0.9)
    return f


def turned(parts, pivot, M, offset=None):
    """Gira peças prontas em volta de `pivot` (M = matriz local -> mundo); offset: leva peças feitas na origem até lá."""
    pivot = np.asarray(pivot, float)
    T = lambda q: (q - pivot) @ M + (pivot if offset is None else 0)
    return [Part(lambda q, pt=pt: pt.sdf(T(q)), lambda q, pt=pt: pt.color(T(q)), pt.gloss, pt.k) for pt in parts]


def ribbon_col(q):
    return mix(RIBBON_D, RIBBON, smooth((q[:, 1] - 0.1) / 0.5))


def bow(top, s=1.0, col=ribbon_col, knot=RIBBON_D, tails=True):
    """Laço em cima de `top`: duas alças (de lado, no eixo z), o nó e as duas pontas caídas."""
    top = np.asarray(top, float)
    P = []
    for zs in (1, -1):
        loop = top + V(0, 0.07, zs * 0.13) * s
        tilt = rot_axis(V(1, 0, 0), zs * 0.45)
        P.append(Part(lambda q, loop=loop, tilt=tilt: np.abs(ellipsoid((q - loop) @ tilt + loop, loop,
                                                                       V(0.11, 0.085, 0.14) * s)) - 0.022 * s,
                      col, 0.75, 0.02))
        if tails:
            a, b = top + V(0.02, 0.0, zs * 0.05) * s, top + V(0.1, -0.13, zs * 0.17) * s
            P.append(Part(lambda q, a=a, b=b: capsule(q, a, b, 0.03 * s), col, 0.75, 0.02))
    P.append(Part(lambda q: sphere(q, top + V(0, 0.04, 0) * s, 0.06 * s), knot, 0.75, 0.02))
    return P


def box_parts(c, half, v, round_=0.09, ribbon_w=0.055, deco=True):
    """Caixinha embrulhada (centro c, meia-medida half) com fita em cruz por cima e pelos lados."""
    c, half = np.asarray(c, float), np.asarray(half, float)
    P = [Part(lambda q: rbox(q, c, half, round_), paper(v, c, half[1] * 2), 0.5)]
    if deco:
        hx, hy, hz = half + 0.012
        P.append(Part(lambda q: np.minimum(rbox(q, c, V(ribbon_w, hy, hz), round_ * 0.8),
                                           rbox(q, c, V(hx, hy, ribbon_w), round_ * 0.8)),
                      ribbon_col, 0.75, 0.004))
    return P


# ================================================================ COBRA
def snake_head(theme=None):
    """Cabeça redonda de papel roxo (lisa, para o rosto aparecer) com um laço grande em cima."""
    c, r = m.HEAD_C, m.HEAD_R
    top, low = PAPERS[0][:2]
    base = m.body_color_fn(c, r, top, C('#c9b2ff'))
    P = [Part(lambda q: sphere(q, c, r), face_col(base, c, r, mouth_col=C('#3d1a6e'), blush=C('#ff8fc4')), 0.5)]
    P += head_eyes(c, r)
    P += bow(c + V(-0.1, r * 0.93, 0), 1.35)
    return P


def snake_body(theme, v):
    """Uma caixinha de presente por segmento (papel alternando), laço só nas roxas."""
    c = V(0, 0.33, 0)
    half = V(0.3, 0.29, 0.3)
    P = box_parts(c, half, v, 0.1)
    if v == 0:
        P += bow(c + V(0, half[1] + 0.02, 0), 0.85, tails=False)
    return P


def snake_tail(theme=None):
    """Cauda de papel verde-água afinando, com uma fita amarrada e as pontas da fita soltas na ponta."""
    c = V(0, 0.3, 0)
    tip = V(-0.62, 0.12, 0)
    base = paper(1, c, 0.6, 10.0)
    P = [Part(lambda q: sphere(q, c, 0.3), base, 0.5),
         Part(lambda q: round_cone(q, c, tip, 0.27, 0.06), base, 0.5, 0.06)]
    knot = V(-0.3, 0.22, 0)
    Mr = np.stack([UP, V(-1, 0, 0), V(0, 0, 1)], 1)      # aro em pé, em volta da cauda
    P.append(Part(lambda q: torus0((q - knot) @ Mr, 0.2, 0.035), ribbon_col, 0.75, 0.01))
    P += bow(knot + V(0, 0.16, 0), 0.7, tails=False)
    for zs in (1, -1):                                  # as duas pontas da fita, enroladas
        a, b = tip + V(0.04, 0.03, 0), tip + V(-0.16, 0.12, zs * 0.1)
        P.append(Part(lambda q, a=a, b=b: capsule(q, a, b, 0.028), ribbon_col, 0.75, 0.02))
    return P


# ================================================================ CENÁRIO
CONFETTI = [C('#ff5fa2'), C('#ffd23f'), C('#2ec4b6'), C('#8a4dff'), C('#ff8a3d'), C('#ffffff')]
TILE_TOP = [C('#eadcff'), C('#ddc9ff')]
SIDE = C('#8a6bd1')


def tile(theme, v):
    """Chão de festa: lilás claro com confete (quadradinhos girados) e serpentina de vez em quando."""
    top = TILE_TOP[v]
    seed = 5 + 11 * v
    cols = np.array(CONFETTI)

    def col(q):
        out = top * (0.95 + 0.08 * fbm(q * 5 + seed, 3))[:, None]
        cell = np.floor(q * 5 + seed * 0.37)
        f = q * 5 + seed * 0.37 - cell
        hsh = _hash(cell * V(1, 0, 1))
        ang = hsh * 6.283
        rx, rz = f[:, 0] - 0.5, f[:, 2] - 0.5
        u = rx * np.cos(ang) + rz * np.sin(ang)
        w = -rx * np.sin(ang) + rz * np.cos(ang)
        conf = (hsh > 0.15) * smooth((0.15 - np.maximum(np.abs(u), np.abs(w) * 1.6)) / 0.015)
        idx = (hsh * 97).astype(int) % len(cols)
        out = mix(out, cols[idx], conf)
        wave = np.abs(np.sin(q[:, 0] * 4.0 + seed) * 0.12 + 0.18 - ((q[:, 2] + seed * 0.13) % 1.0 - 0.5))
        out = mix(out, cols[(seed + 2) % len(cols)], smooth((0.022 - wave) / 0.01) * 0.85 * (v == 1))
        side = SIDE * (0.9 + 0.15 * fbm(q * 10, 2))[:, None]
        side = mix(side, RIBBON, np.exp(-((q[:, 1] + 0.06) / 0.014) ** 2))           # filete de fita na borda
        return mix(side, out, smooth((q[:, 1] + 0.035) / 0.02))
    return Scene([Part(lambda q: rbox(q, V(0, -0.15, 0), V(0.5, 0.15, 0.5), 0.035), col, 0.35)])


def balloon(c, col, r=0.17):
    c = np.asarray(c, float)
    shade = lambda q: mix(col * 0.75, np.minimum(col * 1.25, 1), smooth((q[:, 1] - c[1] + 0.05) / 0.25))
    return [Part(lambda q: ellipsoid(q, c, V(r, r * 1.2, r)), shade, 0.95),
            Part(lambda q: round_cone(q, c - V(0, r * 1.18, 0), c - V(0, r * 1.32, 0), 0.03, 0.012), col * 0.8, 0.6, 0.01)]


def prop(theme, i):
    P = []
    if i == 0:      # pilha de presentes: um grande verde-água, um roxo em cima (girado) e um rosa do lado
        P += box_parts(V(0, 0.2, 0), V(0.24, 0.2, 0.24), 1, 0.05)
        Mt = rot_axis(UP, np.radians(30))
        top_c, top_h = V(0.0, 0.53, 0.0), V(0.15, 0.13, 0.15)
        P += turned(box_parts(V(0, 0, 0), top_h, 0, 0.04), top_c, Mt, offset=top_c)
        P += bow(top_c + V(0, top_h[1] + 0.01, 0), 0.6)
        sc, sh = V(0.25, 0.1, 0.26), V(0.1, 0.1, 0.1)
        P.append(Part(lambda q: rbox(q, sc, sh, 0.03), lambda q: mix(PINK_D, PINK, smooth((q[:, 1] - 0.02) / 0.2)), 0.5))
        P.append(Part(lambda q: np.minimum(rbox(q, sc, V(0.03, 0.105, 0.105), 0.02), rbox(q, sc, V(0.105, 0.105, 0.03), 0.02)),
                      C('#ffffff'), 0.6, 0.004))
    else:           # cacho de balões preso num pesinho de presente
        P.append(Part(lambda q: rbox(q, V(0, 0.07, 0), V(0.09, 0.07, 0.09), 0.025), lambda q: mix(PINK_D, PINK, 0.5), 0.5))
        P.append(Part(lambda q: np.minimum(rbox(q, V(0, 0.07, 0), V(0.025, 0.075, 0.095), 0.01),
                                           rbox(q, V(0, 0.07, 0), V(0.095, 0.075, 0.025), 0.01)), ribbon_col, 0.75, 0.004))
        knot = V(0, 0.16, 0)
        for c, col in ((V(-0.14, 0.86, 0.05), C('#8a4dff')), (V(0.15, 0.9, -0.04), C('#2ec4b6')),
                       (V(0.0, 1.08, 0.0), C('#ff5fa2'))):
            P += balloon(c, col)
            P.append(Part(lambda q, c=c: capsule(q, knot, c - V(0, 0.22, 0), 0.008), C('#f4f4f4'), 0.3))
    return Scene(P)


# ================================================================ CERCA (no formato de peças do jogo)
FENCE = (C('#9b6bff'), RIBBON, PINK)       # poste roxo, travessas de fita dourada, bolinha rosa no topo
