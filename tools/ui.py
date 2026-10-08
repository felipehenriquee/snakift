"""Painéis da interface (placar e quadro de fim de jogo), um estilo por tema.

São renderizados com a câmera de frente (front_camera): mundo +x = direita, +y = cima,
+z = para fora da tela. O painel é uma moldura com um miolo claro rebaixado, onde o
jogo escreve os textos; a decoração do tema fica na moldura e pode passar das bordas.
"""
import numpy as np
from sdf import Part, Scene, C, rbox, sphere, capsule, ellipsoid, fbm, vnoise, mix, rot_axis, length, _hash
import models as m

PPU = 100                   # px por unidade nos painéis
MARGIN = 0.6                # folga do canvas em volta da moldura (para a decoração), em unidades
SS = 2                      # supersampling dos painéis (são grandes; 2 já fica liso)
BORDER = 0.2                # largura da moldura em volta do miolo
DEPTH = 0.09                # meia-espessura da moldura

PANELS = {                  # tamanho da moldura em unidades (x 100 = px)
    'placar': (4.6, 1.3),
    'placar_aberto': (8.4, 1.3),    # placar estendido para a direita, com quanto vale cada presente
    'fim': (6.4, 4.6),
}

# moldura, miolo, texto, destaque
THEME_UI = {
    'classico': (C('#c48a52'), C('#fff8e8'), '#3b2a1a', '#2f8a2f'),
    'rosa': (C('#ff8fb1'), C('#fff2f6'), '#7a1f3d', '#e0306a'),
    'rosquinha': (C('#e8a352'), C('#fff6fb'), '#6b3a1f', '#e0559c'),
    'esquilo': (C('#7d5f48'), C('#f3e3c8'), '#3e2414', '#d9531a'),
    'coracao': (C('#ffd6ec'), C('#fff5fb'), '#7a1f5d', '#ff3d8b'),
    'caracol': (C('#8d9bc4'), C('#eef3ff'), '#2d3a66', '#6a4bd1'),
    'queimado': (C('#3a302b'), C('#efe9e4'), '#2b2523', '#e0561b'),
}


def text_colors():
    return {t: {'texto': v[2], 'destaque': v[3]} for t, v in THEME_UI.items()}


def layout(kind):
    """Tamanho do canvas, âncora (centro da moldura) e área do miolo, em px."""
    w, h = PANELS[kind]
    cw, ch = round((w + 2 * MARGIN) * PPU), round((h + 2 * MARGIN) * PPU)
    ox, oy = cw // 2, ch // 2
    iw, ih = round((w - 2 * BORDER) * PPU), round((h - 2 * BORDER) * PPU)
    return dict(w=cw, h=ch, ox=ox, oy=oy, area=[ox - iw // 2, oy - ih // 2, iw, ih])


def turned(parts, pivot, M):
    """Gira peças já prontas em volta de `pivot` (M = matriz local -> mundo)."""
    pivot = np.asarray(pivot, float)

    def wrap(pt):
        T = lambda q: (q - pivot) @ M + pivot
        return Part(lambda q: pt.sdf(T(q)), lambda q: pt.color(T(q)), pt.gloss, pt.k)
    return [wrap(pt) for pt in parts]


EXACT_NEAR = 0.35           # perto assim da esfera envolvente, calcula a distância de verdade


def bounded(parts, center, radius):
    """Acelera peças caras: longe da esfera (center, radius) usa só a distância até ela.

    A distância até a esfera é menor que a real; perto dela isso escureceria a sombra suave
    (que procura obstáculos a até ~3,4 unidades e só escurece com distâncias < t / 10),
    por isso dentro de EXACT_NEAR a distância é sempre a verdadeira.
    """
    center = np.asarray(center, float)

    def wrap(pt):
        def sdf(q):
            d = length(q - center) - radius
            near = d < EXACT_NEAR
            if near.any():
                d = d.copy()
                d[near] = pt.sdf(q[near])
            return d
        return Part(sdf, pt.color, pt.gloss, pt.k)
    return [wrap(pt) for pt in parts]


def frame_parts(w, h, frame_col, inner_col, gloss=0.3):
    """Moldura com miolo rebaixado. frame_col pode ser cor ou função de cor."""
    hw, hh = w / 2, h / 2
    iw, ih = hw - BORDER, hh - BORDER

    def frame(q):
        outer = rbox(q, np.array([0, 0, 0.0]), np.array([hw, hh, DEPTH]), 0.12)
        pocket = rbox(q, np.array([0, 0, DEPTH + 0.04]), np.array([iw, ih, 0.1]), 0.05)     # fundo em z = 0.03
        return np.maximum(outer, -pocket)

    return [
        Part(frame, frame_col, gloss),
        # miolo com a face em z = 0.075: bem longe do fundo do recesso, para as cores não se misturarem
        Part(lambda q: rbox(q, np.array([0, 0, 0.0]), np.array([iw - 0.005, ih - 0.005, 0.075]), 0.04), inner_col, 0.15),
    ]


def scattered(w, h, n, seed, band=None):
    """Pontos espalhados sobre a moldura (fora do miolo). band='top' só na faixa de cima."""
    rnd = np.random.default_rng(seed)
    pts = []
    while len(pts) < n:
        x, y = rnd.uniform(-w / 2 + 0.08, w / 2 - 0.08), rnd.uniform(-h / 2 + 0.08, h / 2 - 0.08)
        on_frame = abs(x) > w / 2 - BORDER + 0.03 or abs(y) > h / 2 - BORDER + 0.03
        if band == 'top':
            on_frame = y > h / 2 - BORDER + 0.03
        if on_frame:
            pts.append((x, y))
    return pts


def panel(theme, kind):
    w, h = PANELS[kind]
    frame_col, inner_col = THEME_UI[theme][:2]
    hw, hh = w / 2, h / 2
    big = kind == 'fim'
    parts = []

    if theme == 'classico':
        def wood(q):
            grain = fbm(q * np.array([2.5, 22, 4]), 2)
            return frame_col * (0.82 + 0.3 * grain)[:, None]
        parts += frame_parts(w, h, wood, inner_col)
        corners = [(-hw, hh), (hw, hh)] + ([(-hw, -hh), (hw, -hh)] if big else [])
        for k, (x, y) in enumerate(corners):
            c = np.array([x, y, DEPTH])
            out = np.array([np.sign(x), np.sign(y), 0.0])
            deco = []
            for a in (-0.6, 0.0, 0.6):
                d = rot_axis([0, 0, 1], a) @ out + np.array([0, 0, 0.5])
                deco.append(m.leaf_part(c, d, 1.7 if big else 1.6))
            for j, off in enumerate([(0.1, -0.05), (-0.05, 0.1)]):
                bc = c + np.array([off[0] * -np.sign(x), off[1] * -np.sign(y), 0.06])
                deco.append(Part(lambda q, bc=bc: sphere(q, bc, 0.065), C('#ff4d4d'), 0.8, 0.01))
            parts += bounded(deco, c, 0.45)

    elif theme == 'rosa':
        parts += frame_parts(w, h, frame_col, inner_col, 0.55)
        tilt = rot_axis([1, 0, 0], np.radians(-65))         # rosa virada para a câmera
        spots = [(-hw + 0.05, hh - 0.02), (hw - 0.05, hh - 0.02)]
        if big:
            spots += [(-hw + 0.05, -hh + 0.05), (hw - 0.05, -hh + 0.05), (0, hh + 0.02)]
        for x, y in spots:
            c = np.array([x, y, DEPTH + 0.05])
            deco = turned(m.rose_parts(c, 1.3 if big else 1.0, rings=3, calyx=False), c, tilt)
            for sx in (-1, 1):
                deco.append(m.leaf_part(c + np.array([0.12 * sx, -0.08, -0.04]), np.array([sx, -0.4, 0.4]), 1.3))
            parts += bounded(deco, c, 0.4)

    elif theme == 'rosquinha':
        def dough(q):
            return mix(C('#d9853a'), C('#ffd59a'), np.clip((q[:, 1] + hh) / h, 0, 1) * 0.6 + 0.2)
        parts += frame_parts(w, h, dough, inner_col, 0.2)
        drip_y = hh - BORDER * (0.9 if big else 0.75)

        def icing(q):
            x = q[:, 0]
            wave = 0.05 * np.sin(x * 7.0) + 0.09 * np.maximum(0, np.sin(x * 3.1 + 1.0)) ** 6
            body = rbox(q, np.array([0, 0, 0.02]), np.array([hw + 0.025, hh + 0.025, DEPTH + 0.02]), 0.13)
            return np.maximum(body, (drip_y - wave) - q[:, 1])
        parts.append(Part(icing, lambda q: mix(C('#ff8cc6'), C('#ffb3d9'), vnoise(q * 6)[:, None]), 0.85, 0.01))
        pts = scattered(w, h, 40 if big else round(22 * w / PANELS['placar'][0]), 7, band='top')
        rnd = np.random.default_rng(3)
        A, B, cols = [], [], []
        for x, y in pts:
            a = rnd.uniform(0, np.pi)
            d = np.array([np.cos(a), np.sin(a), 0]) * 0.06
            c = np.array([x, y, DEPTH + 0.04])
            A.append(c - d); B.append(c + d)
            cols.append(m.SPRINKLE_COLS[rnd.integers(len(m.SPRINKLE_COLS))])
        for a, b, col in zip(A, B, cols):       # cada granulado no seu volume pequeno
            parts += bounded([m.capsules_part([a], [b], 0.022, [col], 0.6)], (a + b) / 2, 0.09)

    elif theme == 'esquilo':
        def stone(q):
            qq = q[:, [0, 2, 1]]                            # rachaduras no plano da frente (xy)
            crack, rim = m.cracks(qq, 2.2, 3.0, 0.05)
            base = mix(frame_col, C('#a3805f'), fbm(q * 5, 3)[:, None])
            base = base * (1 - 0.25 * rim)[:, None]
            lava = crack * m.smooth((fbm(q * 1.7 + 2, 2) - 0.45) / 0.08)
            return mix(mix(base, C('#3e2414'), crack), C('#ff6a1a'), lava)
        parts += frame_parts(w, h, stone, inner_col, 0.15)
        for k, (x, y, r) in enumerate([(-hw + 0.05, -hh + 0.05, 0.16), (hw - 0.08, -hh + 0.02, 0.12),
                                       (-hw + 0.25, -hh - 0.02, 0.09)]):
            c = np.array([x, y, DEPTH])
            parts += bounded([Part(lambda q, c=c, r=r: sphere(q, c, r) + 0.015 * vnoise(q * 20), C('#6b4a33'), 0.15, 0.03)],
                             c, r + 0.05)
        if big:     # osso em cima
            a, b = np.array([-0.55, hh + 0.02, DEPTH + 0.05]), np.array([0.55, hh + 0.02, DEPTH + 0.05])
            bone = [Part(lambda q: capsule(q, a, b, 0.05), C('#f1e4c8'), 0.45, 0.01)]
            for e in (a, b):
                for sy in (1, -1):
                    ce = e + np.array([0, 0.065 * sy, 0])
                    bone.append(Part(lambda q, ce=ce: sphere(q, ce, 0.07), C('#f1e4c8'), 0.45, 0.02))
            parts += bone          # comprido e fino: um volume esférico em volta dele deixaria marca na sombra

    elif theme == 'caracol':
        parts += frame_parts(w, h, frame_col, inner_col, 0.6)
        front = np.stack([np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0])], 1)
        s = 0.42 if big else 0.3
        sc = np.array([hw - 0.12, hh - 0.06, DEPTH + 0.08])
        parts += bounded([m.swirl_shell(sc, s, s * 0.6, front)], sc, s + 0.15)
        for k, (x, y) in enumerate(scattered(w, h, 14 if big else round(7 * w / PANELS['placar'][0]), 11)):
            c = np.array([x, y, DEPTH + 0.01])
            parts += bounded([Part(lambda q, c=c: sphere(q, c, 0.04), C('#dff3ff'), 1.0, 0.01)], c, 0.09)

    elif theme == 'queimado':
        def charred(q):
            qq = q[:, [0, 2, 1]]
            crack, rim = m.cracks(qq, 2.6, 5.0, 0.045)
            base = mix(C('#2a2321'), frame_col, fbm(q * np.array([3, 14, 3]), 2)[:, None])   # veio de madeira queimada
            base = base * (1 - 0.3 * rim)[:, None]
            hot = crack * m.smooth((fbm(q * 1.8 + 7, 2) - 0.42) / 0.08)
            return mix(mix(base, C('#100c0b'), crack), C('#ff5a14'), hot)
        parts += frame_parts(w, h, charred, inner_col, 0.15)
        for x in (-hw + 0.15, hw - 0.15):
            start = np.array([x, hh + 0.02, DEPTH])
            puffs = m.smoke_puffs(start, [0.13, 0.1, 0.08] if big else [0.09, 0.07], drift=np.array([0.04 * np.sign(x), 0.13, 0.0]))
            parts += bounded(puffs, start + np.array([0, 0.2, 0]), 0.35)

    return Scene(parts)
