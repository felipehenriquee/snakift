"""Escudos do ranque: um por liga, cada liga mais enfeitada que a anterior.

Renderizados com a câmera de frente (front_camera): +x = direita, +y = cima, +z = para fora.
Formato de escudo clássico (topo reto, ponta embaixo) com aro de metal, miolo e uma gema;
a partir da Platina ganham asas, e o Mestre ganha coroa. O número da divisão (IV..I) é
escrito pelo jogo, então basta um escudo por liga.
"""
import numpy as np
from sdf import Part, Scene, C, sphere, capsule, round_cone, rbox, ellipsoid, fbm, mix, rot_axis, length
import models as m

PPU = 120
CANVAS = dict(w=380, h=280, ox=190, oy=160)     # (ox, oy) = pixel do ponto (0, 0) do mundo

# liga: (aro escuro, aro claro, miolo, gema)
TIERS = {
    'ferro': (C('#2c3036'), C('#6d747d'), C('#5a6069'), C('#3a3f46')),
    'bronze': (C('#4f2510'), C('#b0653a'), C('#9a5530'), C('#ffa060')),
    'prata': (C('#4f5761'), C('#d5dce4'), C('#a9b3be'), C('#ffffff')),
    'ouro': (C('#7a4a05'), C('#ffcf3a'), C('#e8a812'), C('#ff2d4a')),
    'platina': (C('#1a5c59'), C('#8ee8da'), C('#3fb3a5'), C('#e8fffb')),
    'esmeralda': (C('#0b4a27'), C('#4fd68a'), C('#1f9a58'), C('#19f08a')),
    'diamante': (C('#1a3d8f'), C('#a9d2ff'), C('#4f8fe8'), C('#f2fbff')),
    'mestre': (C('#2f0d5e'), C('#b47cff'), C('#7a3ed6'), C('#ffd23a')),
}
ORDER = list(TIERS)


def shield2d(x, y, grow=0.0):
    """Distância 2D até o contorno do escudo (negativo dentro). grow > 0 encolhe o contorno."""
    qx = np.abs(x) - 0.5 + 0.1
    qy = np.abs(y - 0.37) - 0.25 + 0.1
    top = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2) + np.minimum(np.maximum(qx, qy), 0) - 0.1
    lens = np.maximum(np.hypot(x - 0.55, y - 0.15) - 1.05, np.hypot(x + 0.55, y - 0.15) - 1.05)
    lens = np.maximum(lens, y - 0.22)                    # só a parte de baixo (a ponta)
    return np.minimum(top, lens) + grow


def slab(d2, z, half, r):
    """Extrusão arredondada de uma forma 2D (d2) com meia-espessura `half`."""
    wx, wz = d2 + r, np.abs(z) - half + r
    return np.hypot(np.maximum(wx, 0), np.maximum(wz, 0)) + np.minimum(np.maximum(wx, wz), 0) - r


def metal(dark, light, seed):
    def f(q):
        t = np.clip((q[:, 1] + 0.8) / 1.5, 0, 1)
        brushed = fbm(q * np.array([3, 30, 3]) + seed, 2)
        return mix(dark, light, (t * 0.75 + brushed * 0.35)[:, None])
    return f


def gem(c, size, col, stretch=1.3):
    """Gema lapidada: octaedro esticado na vertical."""
    c = np.asarray(c, float)
    k = np.array([1.0, 1.0 / stretch, 1.0])

    def sdf(q):
        p = np.abs((q - c) * k)
        return (p.sum(1) - size) * 0.57 / stretch

    def col_fn(q):
        p = (q - c) * k
        facet = np.sign(p[:, 0]) * 0.25 + np.sign(p[:, 1]) * 0.3       # facetas com brilhos diferentes
        return np.clip(col * (0.85 + facet[:, None] * 0.3), 0, 1)
    return Part(sdf, col_fn, 0.95, 0.0)


def wings(dark, light, size):
    """Asas em leque: penas presas atrás do escudo, abrindo para cima e para fora."""
    parts = []
    n = 4 if size > 1.1 else 3
    for sx in (1, -1):
        for i in range(n):
            ang = np.radians(48 - 24 * i)                       # a de cima aponta mais para cima
            d = np.array([sx * np.cos(ang), np.sin(ang), 0.0])
            perp = np.cross([0, 0, 1.0], d)
            M = np.stack([d, perp, [0, 0, 1.0]], 1)             # colunas = eixos da pena
            length_i = (0.46 - 0.07 * i) * size
            base = np.array([sx * 0.36, 0.42 - 0.12 * i, -0.08 - 0.01 * i])
            c = base + d * length_i * 0.5
            rad = np.array([length_i * 0.5, 0.075, 0.04])

            def col(q, c=c, d=d, length_i=length_i):
                tip = np.clip(((q - c) @ d) / length_i + 0.5, 0, 1)     # 0 na base, 1 na ponta
                return mix(dark * 1.4, light, tip[:, None])
            parts.append(Part(lambda q, c=c, M=M, rad=rad: m.ellipsoid0((q - c) @ M, rad), col, 0.7, 0.02))
    return parts


def crown(gold):
    parts = [Part(lambda q: rbox(q, np.array([0, 0.7, 0.0]), np.array([0.34, 0.065, 0.07]), 0.03), gold, 0.9)]
    for x in (-0.27, 0.0, 0.27):
        a, b = np.array([x, 0.74, 0.0]), np.array([x * 1.15, 0.98 if x == 0 else 0.92, 0.0])
        parts.append(Part(lambda q, a=a, b=b: round_cone(q, a, b, 0.07, 0.025), gold, 0.9, 0.02))
        parts.append(Part(lambda q, b=b: sphere(q, b + np.array([0, 0.03, 0]), 0.045), C('#ffffff'), 0.9, 0.01))
    for x in (-0.17, 0.17):
        parts.append(gem([x, 0.7, 0.07], 0.045, C('#ff3d55'), 1.0))
    return parts


def shield(tier):
    dark, light, face, gem_col = TIERS[tier]
    level = ORDER.index(tier)
    seed = level * 3.7
    parts = [
        Part(lambda q: slab(shield2d(q[:, 0], q[:, 1]), q[:, 2], 0.12, 0.05), metal(dark, light, seed), 0.85),
        # miolo um pouco rebaixado, para o aro aparecer como moldura
        Part(lambda q: slab(shield2d(q[:, 0], q[:, 1], 0.11), q[:, 2] - 0.02, 0.1, 0.04),
             metal(face * 0.8, np.minimum(face * 1.15, 1), seed + 1), 0.8),
    ]
    # rebites no aro (até a Prata), gema no centro (do Bronze para cima)
    if level <= 2:
        for x, y in ((-0.36, 0.52), (0.36, 0.52), (0, -0.58)):
            parts.append(Part(lambda q, c=np.array([x, y, 0.12]): sphere(q, c, 0.045), light, 0.9, 0.01))
    if level >= 1:
        parts.append(gem([0, 0.12, 0.13], 0.1 + 0.025 * level, gem_col, 1.35))
    # faixa em V embaixo da gema (Prata para cima)
    if level >= 2:
        for sx in (1, -1):
            a, b = np.array([0, -0.22, 0.11]), np.array([sx * 0.3, 0.02, 0.11])
            parts.append(Part(lambda q, a=a, b=b: capsule(q, a, b, 0.035), light, 0.9, 0.02))
    if level >= 4:
        parts += wings(dark, light, 1.0 + 0.12 * (level - 4))
    if tier == 'mestre':
        parts += crown(C('#ffd23a'))
    return Scene(parts)
