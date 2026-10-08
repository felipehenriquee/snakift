"""Tema 'coracao' (presente Hand Heart): visual de luxo com ouro, pérola e cristal iridescente.

Modelos do pacote tema_coracao (original em _nao_usados/tema_coracao_original), adaptados para a câmera atual do jogo:
o gerador (build.py) usa estas funções para a comida, a cobra, o chão, os props e a cerca do tema.
"""
import numpy as np
from sdf import *
import sdf
import models as m
from fences import ARM, PIECES
from models import V, smooth, head_eyes, face_col

CAM_H = sdf.TO_CAM                          # direção horizontal que aponta para a câmera (no pacote: a isométrica)
FACE = np.stack([R, UP, CAM_H], 1)          # moldura virada para a câmera (x=direita da tela, y=cima, z=câmera)
FACE[:, 2] = np.cross(FACE[:, 0], FACE[:, 1])

GOLD_L, GOLD, GOLD_D = C('#fff2c2'), C('#f0b021'), C('#a3620a')
PEARL = C('#fbf7fb')
PLUM = C('#5a2366')
FUNDO = '#3d1a52'


# ================================================================ materiais
def gold_col(q):
    g = 0.5 + 0.5 * np.sin(q[:, 1] * 18 + q[:, 0] * 7 + q[:, 2] * 5)
    return mix(mix(GOLD_D, GOLD, 0.65 + 0.35 * g), GOLD_L, smooth((q[:, 1] % 0.5 - 0.42) / 0.06) * 0.3)


def irid(q, c, phase=0.0, white=0.35):
    """Perolado/iridescente: o tom muda com a direção da superfície (imita o brilho de cristal)."""
    rel = norm_rows(q - np.asarray(c, float))
    t = (rel @ (-sdf.D)) * 0.55 + rel[:, 1] * 0.35 + rel @ R * 0.3 + phase
    pal = 0.74 + 0.26 * np.cos(2 * np.pi * (t[:, None] + np.array([0.0, 0.33, 0.67])))
    pal = np.clip(pal * np.array([1.0, 0.94, 1.02]), 0, 1)
    return mix(pal, PEARL, white)


def norm_rows(v):
    return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)


# ================================================================ formas
def heart_sdf(q, c, s, M=FACE):
    """Coração 3D gordinho. M colunas = (direita, cima, frente) do coração."""
    p = ((q - np.asarray(c, float)) @ M) / s
    p = p * V(1, 1, 1.45)                      # mais fino na profundidade
    d = None
    for sx in (-1, 1):
        lobe = V(0.42 * sx, 0.2, 0)
        di = smin(sphere(p, lobe, 0.5), round_cone(p, lobe, V(0, -0.86, 0), 0.5, 0.05), 0.12)
        d = di if d is None else smin(d, di, 0.18)
    return d * s / 1.45


def heart_col(c, s, M=FACE):
    def f(q):
        p = ((q - np.asarray(c, float)) @ M) / s
        base = irid(q, c + M @ V(0, -0.2, -0.5) * s, 0.15, 0.0)
        core = np.exp(-((p[:, 0] / 0.55) ** 2 + ((p[:, 1] + 0.05) / 0.5) ** 2)) * (p[:, 2] > 0)
        pink = smooth((p[:, 0] + 0.2) / 0.6) * smooth((p[:, 1] + 0.3) / 0.6)
        out = mix(base, C('#ff8cc8'), pink * 0.6)
        out = mix(out, C('#7fdcff'), smooth((-p[:, 0] - 0.15) / 0.4) * 0.6)
        return mix(out, V(1, 1, 1), core * 0.45)
    return f


def heart_part(c, s, M=FACE, k=0.0):
    return Part(lambda q: heart_sdf(q, c, s, M), heart_col(c, s, M), 0.98, k)


def octa(q, c, s):
    p = np.abs(q - np.asarray(c, float))
    return (p.sum(1) - s) * 0.577


def gem_part(c, s, col):
    return Part(lambda q: octa(q, c, s), lambda q: mix(col, V(1, 1, 1), smooth((q[:, 1] - c[1]) / s) * 0.6), 0.98)


def orbit_ring(c, Rr, r, M):
    c = np.asarray(c, float)

    def d(q):
        return torus0((q - c) @ M, Rr, r)

    def col(q):
        p = (q - c) @ M
        a = (np.arctan2(p[:, 2], p[:, 0]) / (2 * np.pi)) % 1.0
        rb = 0.65 + 0.35 * np.cos(2 * np.pi * (a[:, None] * 1.0 + np.array([0.0, 0.33, 0.67])))
        return mix(rb, V(1, 1, 1), 0.15)
    return Part(d, col, 0.98)


# ================================================================ COMIDA
def open_hand(sx, F):
    """Mão aberta, palma para cima, dedos abrindo para fora (sx=+1 direita, -1 esquerda)."""
    W = lambda x, y, z: F @ V(x * sx, y, z)

    def col(q):
        y = (q @ F)[:, 1]
        c = mix(C('#ff3f8e'), C('#ff9cc9'), smooth((y - 0.18) / 0.3))
        return mix(c, C('#fff3f9'), smooth((y - 0.58) / 0.16))
    P = []
    # antebraço: punhos juntos embaixo, no centro
    P.append(Part(lambda q, a=W(0.31, 0.5, 0.03), b=W(0.1, 0.04, 0.03): round_cone(q, a, b, 0.105, 0.125), col, 0.55))
    # palma inclinada (lado de fora mais alto)
    Mp = F @ rot_axis(V(0, 0, 1), 0.38 * sx)
    pc = W(0.34, 0.55, 0.03)
    P.append(Part(lambda q: ellipsoid((q - pc) @ Mp, V(0, 0, 0), V(0.19, 0.065, 0.16)), col, 0.55, 0.07))
    # dedos em leque, para fora e para cima
    for i, z in enumerate((-0.105, -0.035, 0.035, 0.1)):
        L = [0.86, 1.0, 0.97, 0.82][i]
        a = W(0.47, 0.6, z)
        b = W(0.47 + 0.13 * L, 0.6 + 0.13 * L, z * 1.15)
        c = W(0.47 + 0.2 * L, 0.6 + 0.26 * L, z * 1.25)
        P.append(Part(lambda q, a=a, b=b: capsule(q, a, b, 0.04), col, 0.55, 0.03))
        P.append(Part(lambda q, a=b, b=c: round_cone(q, a, b, 0.039, 0.032), col, 0.55, 0.02))
    # polegar para cima e para dentro, na frente
    P.append(Part(lambda q, a=W(0.25, 0.58, 0.14), b=W(0.2, 0.72, 0.2): round_cone(q, a, b, 0.048, 0.036), col, 0.55, 0.04))
    P.append(Part(lambda q, a=W(0.2, 0.72, 0.2), b=W(0.14, 0.8, 0.2): round_cone(q, a, b, 0.036, 0.032), col, 0.55, 0.02))
    return P


def sparkle_part(c, s):
    """Brilho de 4 pontas (estrelinha) virado para a câmera."""
    c = np.asarray(c, float)

    def d(q):
        p = (q - c) @ FACE
        x, y, z = np.abs(p[:, 0]), np.abs(p[:, 1]), np.abs(p[:, 2])
        star = np.minimum(np.maximum(x * 0.25 + y, 0) - s * 0.25 + 0 * x, np.maximum(y * 0.25 + x, 0) - s * 0.25)
        return np.maximum(np.minimum(capsule(p, V(-s, 0, 0), V(s, 0, 0), s * 0.12), capsule(p, V(0, -s, 0), V(0, s, 0), s * 0.12)), -1) * 1.0
    return Part(d, V(1, 1, 1), 0.3)


def food_coracao():
    c0 = V(0, 1.02, 0)
    s = 0.44
    Mh = FACE @ rot_axis(V(0, 0, 1), np.radians(-6))
    P = [heart_part(c0, s, Mh)]
    P += open_hand(1, FACE) + open_hand(-1, FACE)
    Mr = FACE @ rot_axis(V(0, 0, 1), np.radians(-20)) @ rot_axis(V(1, 0, 0), np.radians(-38))
    P.append(orbit_ring(c0 + FACE @ V(0, -0.04, 0), 0.56, 0.022, Mr))
    P.append(sparkle_part(c0 + FACE @ V(-0.48, 0.38, 0.1), 0.07))
    P.append(sparkle_part(c0 + FACE @ V(0.5, -0.3, 0.1), 0.05))
    return Scene(P, scale=0.8)          # do tamanho das outras comidas


# ================================================================ COBRA
def pearl_body(c, r, phase=0.0):
    return lambda q: mix(irid(q, c, phase, 0.2), C('#ffd6ec'), 0.15)


def gold_belt(c, r, h=-0.04):
    cc = np.asarray(c, float) + V(0, h, 0)
    rr = np.sqrt(max(r * r - h * h, 1e-6))
    return Part(lambda q: torus0(q - cc, rr + 0.004, 0.032), gold_col, 0.95, 0.01)


def heart_jewel(top, s, M=FACE):
    """Gema de coração com engaste de ouro."""
    P = [Part(lambda q: round_cone(q, top + V(0, -0.03, 0), top + V(0, 0.05, 0), 0.07, 0.04), gold_col, 0.95, 0.02)]
    P.append(heart_part(top + V(0, 0.05 + s * 0.75, 0), s, M))
    return P


def snake_head(theme=None):
    c, r = m.HEAD_C, m.HEAD_R
    base = pearl_body(c, r)
    P = [Part(lambda q: sphere(q, c, r), face_col(base, c, r, mouth_col=C('#b0306a'), blush=C('#ffa3cc')), 0.75)]
    P += head_eyes(c, r)
    # tiara: aro de ouro + pontas + coração na frente
    tc = c + V(-0.04, r * 0.7, 0)
    P.append(Part(lambda q: torus0(q - tc, 0.3, 0.04), gold_col, 0.95, 0.02))
    for i in range(7):
        a = np.pi * (i / 6) - np.pi / 2              # meia volta virada pra frente (+x)
        b = tc + V(0.3 * np.cos(a), 0, 0.3 * np.sin(a))
        h = 0.13 + 0.09 * np.cos(a * 1.0)
        P.append(Part(lambda q, b=b, h=h: round_cone(q, b, b + V(0, h, 0), 0.035, 0.012), gold_col, 0.95, 0.015))
        P.append(Part(lambda q, b=b, h=h: sphere(q, b + V(0, h + 0.012, 0), 0.024), PEARL, 0.9))
    Mh = np.stack([V(0, 0, -1), UP, V(1, 0, 0)], 1)    # coração da tiara virado para a frente da cabeça
    P.append(Part(lambda q: round_cone(q, tc + V(0.3, -0.02, 0), tc + V(0.3, 0.12, 0), 0.06, 0.035), gold_col, 0.95, 0.02))
    P.append(heart_part(tc + V(0.33, 0.27, 0), 0.19, Mh))
    return P


def snake_body(theme, v):
    c, r = m.SEG_C, m.SEG_R
    P = [Part(lambda q: sphere(q, c, r), pearl_body(c, r, 0.2 * v), 0.75), gold_belt(c, r)]
    top = c + V(0, r - 0.01, 0)
    if v == 0:
        P += heart_jewel(top, 0.17)
    else:
        P.append(Part(lambda q: round_cone(q, top + V(0, -0.03, 0), top + V(0, 0.04, 0), 0.075, 0.05), gold_col, 0.95, 0.02))
        P.append(Part(lambda q: sphere(q, top + V(0, 0.11, 0), 0.075), lambda q: irid(q, top + V(0, 0.11, 0), 0.5, 0.6), 0.95))
    return P


def snake_tail(theme=None):
    c = V(0, 0.3, 0)
    tip = V(-0.62, 0.1, 0)
    base = pearl_body(m.SEG_C, m.SEG_R, 0.4)
    P = [Part(lambda q: sphere(q, c, 0.3), base, 0.75),
         Part(lambda q: round_cone(q, c, tip, 0.27, 0.05), base, 0.75, 0.06),
         Part(lambda q: round_cone(q, tip + V(0.12, 0.02, 0), tip + V(-0.08, 0.0, 0), 0.07, 0.03), gold_col, 0.95, 0.02),
         Part(lambda q: torus0((q - V(-0.25, 0.22, 0)) @ np.stack([UP, V(1, 0, 0) * -1, V(0, 0, 1)], 1), 0.19, 0.028), gold_col, 0.95, 0.01)]
    Mh = np.stack([V(0, 0, 1), UP, V(-1, 0, 0)], 1)
    P.append(heart_part(tip + V(-0.1, 0.12, 0), 0.1, Mh))
    return P


# ================================================================ CENÁRIO
def tile(theme, v):
    top_c = [C('#fbf3f6'), C('#f6b6d2')][v]
    vein_c = [C('#e0a93a'), C('#fff5fa')][v]
    seed = 3 + 5 * v

    def col(q):
        n = fbm(q * 3.0 + seed, 4)
        vein = np.abs(np.sin((q[:, 0] * 1.3 + q[:, 2] * 2.1) * 5 + n * 9))
        v1 = smooth((0.06 - vein) / 0.05)
        v2 = smooth((0.03 - np.abs(np.sin((q[:, 0] * 2.7 - q[:, 2] * 1.1) * 7 + n * 11))) / 0.03) * 0.5
        out = mix(top_c * (0.94 + 0.1 * n)[:, None], vein_c, np.clip(v1 * 0.95 + v2 * 0.7, 0, 1))
        edge = np.maximum(np.abs(q[:, 0]), np.abs(q[:, 2]))
        trim = smooth((edge - 0.43) / 0.01) * smooth((0.475 - edge) / 0.01)
        out = mix(out, gold_col(q), trim)
        side = mix(PLUM * (0.9 + 0.15 * fbm(q * 12, 2))[:, None], gold_col(q), smooth((q[:, 1] + 0.06) / 0.02) * 1.0)
        side = mix(side, gold_col(q), np.exp(-((q[:, 1] + 0.25) / 0.012) ** 2))
        return mix(side, out, smooth((q[:, 1] + 0.035) / 0.02))
    return Scene([Part(lambda q: rbox(q, V(0, -0.15, 0), V(0.5, 0.15, 0.5), 0.035), col, 0.7)])


def prop(theme, i):
    P = []
    if i == 0:      # pedestal de ouro com coração de cristal
        fl = lambda q: gold_col(q) * (0.9 + 0.1 * np.sin(np.arctan2(q[:, 2], q[:, 0]) * 16))[:, None]
        P.append(Part(lambda q: rbox(q, V(0, 0.05, 0), V(0.27, 0.05, 0.27), 0.03), gold_col, 0.95))
        P.append(Part(lambda q: round_cone(q, V(0, 0.1, 0), V(0, 0.18, 0), 0.2, 0.12), gold_col, 0.95, 0.02))
        P.append(Part(lambda q: capsule(q, V(0, 0.18, 0), V(0, 0.52, 0), 0.085), fl, 0.95, 0.03))
        P.append(Part(lambda q: round_cone(q, V(0, 0.52, 0), V(0, 0.6, 0), 0.1, 0.17), gold_col, 0.95, 0.02))
        P.append(Part(lambda q: ellipsoid(q, V(0, 0.62, 0), V(0.2, 0.03, 0.2)), PLUM * 1.2, 0.6, 0.01))
        P.append(heart_part(V(0, 0.98, 0), 0.3))
        Mr = FACE @ rot_axis(V(1, 0, 0), np.radians(72)) @ rot_axis(V(0, 0, 1), np.radians(15))
        P.append(orbit_ring(V(0, 0.98, 0), 0.4, 0.018, Mr))
    else:           # caixa de presente de pérola com laço de ouro
        bc, bh = V(0, 0.26, 0), V(0.27, 0.26, 0.27)
        P.append(Part(lambda q: rbox(q, bc, bh, 0.04), lambda q: irid(q, bc, 0.1, 0.55), 0.8))
        P.append(Part(lambda q: rbox(q, V(0, 0.55, 0), V(0.3, 0.06, 0.3), 0.03), lambda q: irid(q, V(0, 0.55, 0), 0.3, 0.5), 0.8))
        P.append(Part(lambda q: rbox(q, V(0, 0.3, 0), V(0.06, 0.32, 0.305), 0.015), gold_col, 0.95))
        P.append(Part(lambda q: rbox(q, V(0, 0.3, 0), V(0.305, 0.32, 0.06), 0.015), gold_col, 0.95))
        for sx in (1, -1):
            Mb = rot_axis(V(0, 0, 1), sx * 0.5)
            P.append(Part(lambda q, Mb=Mb, sx=sx: torus0(((q - V(0.13 * sx, 0.7, 0)) @ Mb)[:, [1, 0, 2]] * V(1, 1, 1), 0.1, 0.03), gold_col, 0.95, 0.02))
        P.append(Part(lambda q: sphere(q, V(0, 0.66, 0), 0.06), gold_col, 0.95, 0.02))
        P.append(heart_part(V(0, 0.8, 0.0) + CAM_H * 0.05, 0.1))
    return Scene(P)

# ================================================================ CERCA (no formato de peças do jogo)
def fence(piece):
    """Poste de ouro com pérola no centro; travessas de ouro com gotinhas iridescentes até a borda da célula."""
    P3 = lambda d, y: np.array([d[0], y, d[2]])
    P = [Part(lambda q: rbox(q, V(0, 0.2, 0), V(0.055, 0.2, 0.055), 0.02), gold_col, 0.95),
         Part(lambda q: rbox(q, V(0, 0.03, 0), V(0.075, 0.03, 0.075), 0.015), gold_col, 0.95, 0.01),
         Part(lambda q: sphere(q, V(0, 0.47, 0), 0.065), lambda q: irid(q, V(0, 0.47, 0), 0.2, 0.55), 0.95, 0.02)]
    for arm in PIECES[piece]:
        b = ARM[arm] * 0.5
        for y, r in ((0.08, 0.026), (0.36, 0.03)):
            P.append(Part(lambda q, b=b, y=y, r=r: capsule(q, V(0, y, 0), P3(b, y), r), gold_col, 0.95))
        pp = b * 0.55
        P.append(Part(lambda q, pp=pp: smin(round_cone(q, P3(pp, 0.1), P3(pp, 0.2), 0.022, 0.045),
                                             round_cone(q, P3(pp, 0.2), P3(pp, 0.34), 0.045, 0.02), 0.03),
                      lambda q, pp=pp: irid(q, P3(pp, 0.22), 0.4, 0.6), 0.9))
    return Scene(P)
