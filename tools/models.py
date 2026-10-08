"""Modelos 3D (SDF) de todas as peças: comidas, cobras temáticas, tiles e props."""
import numpy as np
from sdf import *
from sdf import _hash

Y = UP
CAM_H = TO_CAM                   # direção horizontal que aponta para a câmera
rng0 = np.random.default_rng


def V(*a):
    return np.array(a, float)


def at(fn, c, M=None):
    c = np.asarray(c, float)
    if M is None:
        return lambda p: fn(p - c)
    return lambda p: fn((p - c) @ M)


def smooth(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


# ================================================================= blocos
def eye_parts(c, r, look, sleepy=None):
    """Olho fofinho: branco + pupila + brilho. sleepy = cor da pálpebra."""
    c = np.asarray(c, float); look = norm(look)
    pc = c + look * r * 0.5
    hl = c + look * r * 0.78 + norm(Y + 0.3 * np.cross(look, Y)) * r * 0.42

    def white_col(q):
        out = np.broadcast_to(V(1, 1, 1), (len(q), 3)).copy()
        if sleepy is not None:
            lid = smooth(((q[:, 1] - c[1]) - r * 0.1) / (r * 0.12))
            out = mix(out, sleepy, lid)
        return out
    parts = [Part(lambda q: sphere(q, c, r), white_col, 0.7)]
    parts.append(Part(lambda q: sphere(q, pc, r * 0.62), C('#1d1626'), 0.9))
    if sleepy is None:
        parts.append(Part(lambda q: sphere(q, hl, r * 0.2), V(1, 1, 1), 0.2))
    return parts


def bend_ellipsoid_part(base, M, w, ln, th, col_fn, bend=3.0, gloss=0.35, k=0.0, pos=0.85):
    """Pétala/folha: elipsoide fino com curvatura. M colunas = (largura, comprimento, normal)."""
    base = np.asarray(base, float)
    pc = base + M[:, 1] * ln * pos
    rad = V(w, ln, th)

    def loc(p):
        q = (p - pc) @ M
        q = q.copy()
        q[:, 2] -= bend * q[:, 0] ** 2 + 0.6 * bend * (q[:, 1] / ln) ** 2 * ln * 0.3
        return q
    return Part(lambda p: ellipsoid0(loc(p), rad) * 0.75, lambda p: col_fn(loc(p), rad), gloss, k)


def frame_from(width_dir, length_dir):
    l = norm(length_dir)
    w = norm(width_dir - (width_dir @ l) * l)
    n = np.cross(w, l)
    return np.stack([w, l, n], 1)


def petal_frame(theta, phi):
    rd = V(np.cos(theta), 0, np.sin(theta))
    td = V(-np.sin(theta), 0, np.cos(theta))
    v = Y * np.cos(phi) + rd * np.sin(phi)
    return frame_from(td, v)


def rose_parts(c, s=1.0, deep=C('#c8082f'), tip=C('#ff5a78'), rings=3, calyx=True):
    c = np.asarray(c, float)
    parts = []

    def pcol(q, rad):
        t = np.clip((q[:, 1] / rad[1] + 1) / 2, 0, 1)
        edge = np.clip(np.abs(q[:, 0]) / rad[0], 0, 1) ** 4
        return mix(deep, tip, np.clip(t ** 1.6 + 0.25 * edge, 0, 1))
    spec = [(3, 8, 0.075, 0.115, 0.024, 0.012, 0.03, 0.0),
            (5, 34, 0.10, 0.14, 0.026, 0.03, 0.0, 0.35),
            (6, 60, 0.12, 0.155, 0.028, 0.045, -0.03, 0.95)][:rings]
    for cnt, phi, w, ln, th, rb, hb, off in spec:
        for i in range(cnt):
            th_ = off + 2 * np.pi * i / cnt
            M = petal_frame(th_, np.radians(phi))
            base = c + s * V(rb * np.cos(th_), hb, rb * np.sin(th_))
            parts.append(bend_ellipsoid_part(base, M, w * s, ln * s, th * s, pcol, bend=2.2 / s, gloss=0.4, k=0.006 * s))
    parts.append(Part(lambda q: ellipsoid(q, c + s * V(0, 0.09, 0), s * V(0.045, 0.085, 0.045)), deep * 0.85, 0.4, 0.01 * s))
    if calyx:
        parts.append(Part(lambda q: sphere(q, c + s * V(0, -0.03, 0), 0.06 * s), C('#3f9a3a'), 0.3, 0.02 * s))
    return parts


def leaf_part(base, direction, s=1.0, col=C('#43b04a'), col2=C('#8fe07a'), twist=0.0):
    direction = norm(direction)
    side = np.cross(direction, Y)
    if np.linalg.norm(side) < 1e-3:
        side = V(1, 0, 0)
    side = rot_axis(direction, twist) @ norm(side)
    M = frame_from(side, direction)

    def lcol(q, rad):
        rib = np.exp(-(q[:, 0] / (rad[0] * 0.08)) ** 2)
        t = np.clip((q[:, 1] / rad[1] + 1) / 2, 0, 1)
        return mix(mix(col, col2, t * 0.6), col2 * 1.05, rib * 0.7)
    return bend_ellipsoid_part(base, M, 0.075 * s, 0.15 * s, 0.018 * s, lcol, bend=-2.5 / s, gloss=0.35, k=0.005)


def capsules_part(A, B, rad, cols, gloss=0.5, k=0.0):
    A = np.asarray(A, float); B = np.asarray(B, float); cols = np.asarray(cols, float)
    BA = B - A
    bb = (BA * BA).sum(-1)
    rad = np.broadcast_to(np.asarray(rad, float), (len(A),))

    def dall(q):
        pa = q[:, None, :] - A[None]
        h = np.clip((pa * BA[None]).sum(-1) / bb[None], 0, 1)
        return length(pa - h[..., None] * BA[None]) - rad[None]
    return Part(lambda q: dall(q).min(1), lambda q: cols[dall(q).argmin(1)], gloss, k)


SPRINKLE_COLS = [C('#ffffff'), C('#ffe066'), C('#6ff0c0'), C('#ffa94d'), C('#ff5c9e'), C('#5cc8ff'), C('#b388ff')]


def sprinkles_on_sphere(c, r, n, seed, max_polar=58, L=0.065, rad=0.014):
    g = rng0(seed)
    A, B, cols = [], [], []
    for _ in range(n):
        pol = np.radians(g.uniform(0, max_polar))
        az = g.uniform(0, 2 * np.pi)
        nn = V(np.sin(pol) * np.cos(az), np.cos(pol), np.sin(pol) * np.sin(az))
        p = np.asarray(c) + nn * r
        tdir = np.cross(nn, norm(g.normal(size=3)))
        tdir = norm(tdir)
        A.append(p - tdir * L / 2); B.append(p + tdir * L / 2)
        cols.append(SPRINKLE_COLS[g.integers(len(SPRINKLE_COLS))])
    return capsules_part(A, B, rad, cols, 0.6)


def swirl_shell(c, Rr, T, M, cin=C('#ff4fd8'), cmid=C('#a24cff'), cout=C('#4d6bff'), turns=2.4):
    """Concha espiral; M colunas = (u, v, normal da face da espiral)."""
    c = np.asarray(c, float)

    def loc(p):
        return (p - c) @ M

    def groove(q):
        rho = np.sqrt(q[:, 0] ** 2 + q[:, 1] ** 2) / Rr
        th = np.arctan2(q[:, 1], q[:, 0])
        s = (th / (2 * np.pi) - turns * np.log(rho + 0.06) / np.log(1.06 / 0.06) * 1.0) % 1.0
        return np.exp(-((s - 0.5) / 0.09) ** 2), rho

    def sdf(p):
        q = loc(p)
        g, _ = groove(q)
        return ellipsoid0(q, V(Rr, Rr, T)) * 0.9 + 0.012 * g

    def col(p):
        q = loc(p)
        g, rho = groove(q)
        base = np.where((rho < 0.5)[:, None], mix(cin, cmid, np.clip(rho / 0.5, 0, 1)), mix(cmid, cout, np.clip((rho - 0.5) / 0.5, 0, 1)))
        return mix(base, base * 0.45 + C('#2a0a4a') * 0.2, g * 0.9)
    return Part(sdf, col, 0.55)


# ================================================================= COMIDAS
def food_rose():
    """O presente "Rosa" da live: uma rosa vermelho-coral bem aberta, com muitas pétalas em espiral (o miolo mais
    escuro e fechado, as de fora abertas e curvadas para fora, as bordas mais claras) e duas folhas verde-escuras
    embaixo, sem caule à mostra. A flor inclina para a câmera, para o miolo aparecer (como o ícone do TikTok)."""
    c = V(0, 0.0, 0)
    deep, coral, light = C('#8a0c12'), C('#e2302c'), C('#f7785f')

    def pcol(q, rad):
        t = np.clip((q[:, 1] / rad[1] + 1) / 2, 0, 1)                    # 0 na base da pétala, 1 na borda
        side = np.clip(np.abs(q[:, 0]) / rad[0], 0, 1) ** 3
        col = mix(deep, coral, smooth(t * 1.4))
        return mix(col, light, np.clip(smooth((t - 0.62) / 0.38) * 0.75 + side * 0.25, 0, 1))
    # (pétalas, abertura em graus, largura, comprimento, espessura, raio da base, altura da base, curva)
    spec = [(3, 4, 0.070, 0.120, 0.022, 0.012, 0.11, 5.0),          # miolo: pétalas em pé, enroladas
            (4, 14, 0.095, 0.150, 0.024, 0.030, 0.08, 4.2),
            (5, 26, 0.120, 0.170, 0.026, 0.050, 0.06, 3.6),
            (6, 40, 0.145, 0.185, 0.026, 0.068, 0.04, 3.0),          # em concha, abrindo
            (7, 56, 0.165, 0.195, 0.026, 0.085, 0.02, 2.4)]
    parts = []
    g = rng0(17)                                                          # pétalas um pouco diferentes: natural
    for ring, (cnt, phi, w, ln, th, rb, hb, bend) in enumerate(spec):
        for i in range(cnt):
            ang = ring * 0.55 + 2 * np.pi * i / cnt + g.uniform(-0.18, 0.18)  # cada anel girado: espiral
            k = g.uniform(0.88, 1.12)
            M = petal_frame(ang, np.radians(phi + g.uniform(-6, 6)))
            base = c + V(rb * np.cos(ang), hb, rb * np.sin(ang))
            parts.append(bend_ellipsoid_part(base, M, w * k, ln * k, th, pcol, bend=bend, gloss=0.22, k=0.006))
    parts.append(Part(lambda q: ellipsoid(q, c + V(0, 0.13, 0), V(0.04, 0.07, 0.04)), deep * 0.9, 0.4, 0.01))
    parts.append(Part(lambda q: ellipsoid(q, c + V(0, 0.0, 0), V(0.11, 0.07, 0.11)), deep * 0.8, 0.3, 0.02))  # fecha embaixo
    green, green_light = C('#0f5a2b'), C('#2f8c4a')
    for side in (1, -1):                                                    # duas folhas embaixo, para a frente
        d = norm(V(0.7 * side, -0.55, 0.45))
        parts.append(leaf_part(c + V(0.06 * side, -0.05, 0.07), d, 1.3, col=green, col2=green_light, twist=0.6 * side))
    tilt = rot_axis(norm(np.cross(Y, CAM_H)), np.radians(14))             # inclina um pouco para a câmera
    return Scene(parts, rot=tilt, offset=(0, 0.46, 0), scale=1.45)


# maçãs dos elos: casca (escura, clara), brilho do lado do sol, folha (escura, clara)
APPLE_PAL = {
    'bronze': ('#6e3510', '#d4823e', '#ffc58a', '#7a4a1c', '#e0a463'),
    'prata': ('#6a737e', '#dfe5ec', '#ffffff', '#8d97a3', '#eef2f7'),
    'ouro': ('#8a5600', '#ffc21f', '#fff0a0', '#a86e00', '#ffd86a'),
    'platina': ('#1f7d72', '#7fe0d0', '#e6fffb', '#2a8a7e', '#b9f5ea'),
    'esmeralda': ('#085a2a', '#2fd16e', '#b6ffcd', '#0b6d33', '#8ff0a8'),
    'diamante': ('#2a64b8', '#9fd6ff', '#ffffff', '#4f9ff0', '#d6efff'),
    'mestre': ('#3d1078', '#a45cf2', '#ffd27a', '#c08a10', '#ffe27a'),
}


def food_apple(tier=None):
    """Maçã: volta a cobra para o tema clássico. tier: maçã de um elo (de metal ou pedra, mais brilhante)."""
    c = V(0, 0.33, 0)
    top, bottom = c + V(0, 0.33, 0), c + V(0, -0.34, 0)

    def body(q):
        d = ellipsoid0(q - c, V(0.34, 0.31, 0.34))
        d = -smin(-d, sphere(q, top, 0.11), 0.07)          # covinha do cabo
        return -smin(-d, sphere(q, bottom, 0.07), 0.05)    # covinha de baixo

    dark, light, glow = (C('#b3121f'), C('#ff3b30'), C('#ff8a3d')) if tier is None else \
        tuple(C(h) for h in APPLE_PAL[tier][:3])

    def skin(q):
        streak = fbm(q * V(26, 3, 26) + 4.0, 2)               # listrinhas verticais
        sun = np.clip((q[:, 1] - c[1]) * 2.5 + 0.3 * (q[:, 0] - q[:, 2]), 0, 1)
        col = mix(dark, light, np.clip(streak * 1.3 - 0.15, 0, 1))
        return mix(col, glow, sun * (0.35 if tier is None else 0.5))

    leaf = {} if tier is None else dict(col=C(APPLE_PAL[tier][3]), col2=C(APPLE_PAL[tier][4]))
    parts = [
        Part(body, skin, 0.75 if tier is None else 0.97),
        Part(lambda q: capsule(q, top + V(0, -0.06, 0), top + V(0.04, 0.16, 0), 0.022), C('#6b4430'), 0.2, 0.01),
        leaf_part(top + V(0.03, 0.08, 0), V(0.9, 0.35, 0.4), 1.05, **leaf),
    ]
    return Scene(parts, scale=1.25)


# ================================================================= personagem que joga os presentes
GNOME_POSES = ('parado', 'segura', 'prepara', 'joga')
GNOME_TURN = -np.pi / 2 * 0.45      # virado para a arena (+x), meio girado para a câmera (mostra o rosto)
GNOME_SHOULDER = V(0.0, 0.56, 0.2)  # ombro do braço que arremessa (o do lado da câmera)
# placa que um dos duendes segura acima da cabeça (coordenadas do mundo sem escala, de frente para a câmera):
# centro e meia largura / meia altura. O jogo escreve nela o nome de quem mandou o presente
SIGN_C, SIGN_HALF = V(0.0, 1.62, 0.12), V(0.5, 0.21, 0.025)
SIGN_TILT = rot_axis(V(1, 0, 0), np.radians(-35))       # inclinada para trás: de frente para a câmera e a luz
GNOME_HAND = {                      # mão do braço que arremessa em cada pose
    'parado': V(0.06, 0.32, 0.27),
    'segura': V(0.3, 0.62, 0.2),     # mão na frente, onde o presente surge
    'prepara': V(-0.24, 0.98, 0.24),  # braço para trás, por cima da cabeça
    'joga': V(0.4, 0.92, 0.16),       # braço esticado para a frente: soltou
    'placa': V(0.06, 0.32, 0.27),     # (não arremessa)
}
GIFT_ABOVE_HAND = V(0, 0.1, 0)      # o presente fica um pouco acima da mão
GNOME_SCALE = 1.3                   # o duende é um pouco maior que a cobra


EVIL_TURN = np.pi + np.pi / 2 * 0.45   # duende do mal: virado para a arena (-x), meio girado para a câmera


def gnome(pose, evil=False):
    """Duende de gorro pontudo que fica do lado da cerca e joga os presentes na arena.
    evil: o duende do mal, que joga as bombas (pele de goblin, olhos vermelhos, gorro torto). Ele é espelhado,
    para o braço que arremessa ficar do lado da câmera também do outro lado da arena."""
    if evil:
        skin, tunic, tunic2 = C('#8fc46f'), C('#7a1f3d'), C('#4a0f22')
        hat, hat2, trim, boot = C('#4b2a73'), C('#24123d'), C('#3a3540'), C('#2a2228')
        beard, nose, eye, cheek = C('#4d4a55'), C('#6fa457'), C('#ff2a2a'), None
    else:
        skin, tunic, tunic2 = C('#ffd2b0'), C('#2fbf8f'), C('#22986f')
        hat, hat2, trim, boot = C('#ff3d8b'), C('#c81e63'), C('#fbf7f2'), C('#5a3a2a')
        beard, nose, eye, cheek = C('#fbf7f2'), C('#ffb59a'), C('#2a1a3a'), C('#ff9fb4')
    mz = V(1, 1, -1) if evil else V(1, 1, 1)                        # espelho (só os braços mudam de lado)
    parts = []
    for zs in (1, -1):                                              # botas
        parts.append(Part(lambda q, zs=zs: ellipsoid(q, V(0.06, 0.06, zs * 0.11), V(0.13, 0.07, 0.08)), boot, 0.3))
    parts.append(Part(lambda q: round_cone(q, V(0, 0.14, 0), V(0, 0.56, 0), 0.27, 0.19),
                      lambda q: mix(tunic2, tunic, smooth((q[:, 1] - 0.15) / 0.4)), 0.35, 0.03))   # túnica
    parts.append(Part(lambda q: np.maximum(np.abs(q[:, 1] - 0.3) - 0.035, length(q * V(1, 0, 1)) - 0.262),
                      C('#2a1a1a') if evil else C('#6b4430'), 0.4, 0.0))                          # cinto
    parts.append(Part(lambda q: rbox(q, V(0.24, 0.3, 0), V(0.012, 0.04, 0.05), 0.01),
                      C('#a9a3b5') if evil else C('#ffd23f'), 0.9, 0.0))
    head = V(0.02, 0.8, 0)
    parts.append(Part(lambda q: sphere(q, head, 0.2), skin, 0.35, 0.02))                          # cabeça
    parts.append(Part(lambda q: sphere(q, head + V(0.2, -0.02, 0), 0.065 if evil else 0.055), nose, 0.4, 0.01))
    for zs in (1, -1):
        parts.append(Part(lambda q, zs=zs: sphere(q, head + V(0.17, 0.035, zs * 0.08), 0.034), eye, 0.8))
        if cheek is not None:
            parts.append(Part(lambda q, zs=zs: sphere(q, head + V(0.15, -0.04, zs * 0.12), 0.04), cheek, 0.2, 0.01))
        if evil:            # sobrancelhas bravas (descem para o meio) e orelhas pontudas de goblin
            parts.append(Part(lambda q, zs=zs: capsule(q, head + V(0.17, 0.12, zs * 0.14), head + V(0.2, 0.075, zs * 0.03),
                                                       0.02), C('#1e1a22'), 0.3, 0.005))
            parts.append(Part(lambda q, zs=zs: round_cone(q, head + V(-0.02, 0.0, zs * 0.17),
                                                          head + V(-0.08, 0.1, zs * 0.34), 0.055, 0.008), skin, 0.35, 0.02))
    parts.append(Part(lambda q: ellipsoid(q, head + V(0.1, -0.16, 0), V(0.13, 0.15, 0.17)), beard, 0.25, 0.04))  # barba
    hat_base = head + V(-0.04, 0.16, 0)
    tip = head + (V(-0.36, 0.66, 0.06) if evil else V(-0.24, 0.76, 0.02))   # o do mal é torto
    parts.append(Part(lambda q: round_cone(q, hat_base, tip, 0.19, 0.025),
                      lambda q: mix(hat, hat2, smooth((q[:, 1] - hat_base[1]) / 0.6)), 0.35, 0.02))  # gorro
    parts.append(Part(lambda q: np.maximum(np.abs(length((q - hat_base) * V(1, 0, 1)) - 0.19) - 0.04,
                                           np.abs(q[:, 1] - hat_base[1] + 0.01) - 0.045), trim, 0.2, 0.02))   # aba
    parts.append(Part(lambda q: sphere(q, tip, 0.065), C('#c41e3a') if evil else trim, 0.2, 0.01))   # pompom
    arms = ((GNOME_SHOULDER, GNOME_HAND[pose]), (V(0, 0.56, -0.2), V(0.08, 0.34, -0.27)))
    if pose == 'placa':                 # os dois braços para cima, segurando a placa pelas pontas de baixo
        parts += sign_parts(EVIL_TURN if evil else GNOME_TURN, evil)
        R = rot_y(EVIL_TURN if evil else GNOME_TURN)
        low = SIGN_TILT.T @ V(0, -SIGN_HALF[1] - 0.02, -0.02)            # borda de baixo, já inclinada
        hands = [(SIGN_C + V(xs * (SIGN_HALF[0] - 0.12), 0, 0) + low) @ R for xs in (1, -1)]
        hands.sort(key=lambda h: -h[2])                                # a do lado +z com o ombro +z
        arms = ((GNOME_SHOULDER, hands[0]), (V(0, 0.56, -0.2), hands[1]))
    for shoulder, hand in arms:
        shoulder, hand = shoulder * mz, hand * mz
        elbow = (shoulder + hand) / 2 + V(-0.03, -0.03, 0.04 * np.sign(shoulder[2]))
        parts.append(Part(lambda q, a=shoulder, b=elbow, c=hand: np.minimum(capsule(q, a, b, 0.062),
                                                                            capsule(q, b, c, 0.055)), tunic, 0.35, 0.03))
        parts.append(Part(lambda q, c=hand: sphere(q, c, 0.07), skin, 0.35, 0.02))               # mão
    return Scene(parts, rot=rot_y(EVIL_TURN if evil else GNOME_TURN), scale=GNOME_SCALE)


def sign_parts(turn, evil=False):
    """Placa branca com moldura de madeira, de frente para a câmera (montada no mundo e levada para as
    coordenadas do duende, que é girado por `turn`)."""
    Rt = rot_y(turn).T                                  # local -> mundo (sem escala)

    def to_w(q):
        return ((q @ Rt) - SIGN_C) @ SIGN_TILT + SIGN_C
    board, frame = (C('#f3ecf7'), C('#4b2a73')) if evil else (C('#ffffff'), C('#c98b4a'))   # o do mal: moldura roxa
    return [Part(lambda q: rbox(to_w(q), SIGN_C, SIGN_HALF + V(0.035, 0.035, 0.0), 0.03), frame, 0.3),
            Part(lambda q: rbox(to_w(q), SIGN_C + V(0, 0, 0.018), SIGN_HALF * V(1, 1, 0.6), 0.015), board, 0.2, 0.0)]


def sign_box_world():
    """Cantos da área escrita da placa no mundo (com a escala do duende): (centro, meia largura, meia altura)."""
    up = SIGN_TILT @ V(0, 1, 0)                         # para onde aponta o "cima" da placa inclinada
    return SIGN_C * GNOME_SCALE, SIGN_HALF[0] * GNOME_SCALE, up * SIGN_HALF[1] * GNOME_SCALE


def gnome_hand_world(pose, evil=False):
    """Onde o presente (ou a bomba) fica na mão (coordenadas do mundo, depois de girar e escalar o duende)."""
    mz = V(1, 1, -1) if evil else V(1, 1, 1)
    return ((GNOME_HAND[pose] + GIFT_ABOVE_HAND) * mz) @ rot_y(EVIL_TURN if evil else GNOME_TURN).T * GNOME_SCALE


def food_box():
    """Caixa de presente com fita e laço: os presentes da live que não existem no jogo."""
    c, h = V(0, 0.27, 0), V(0.25, 0.25, 0.25)
    paper, paper2, ribbon, ribbon2 = C('#ff5fa2'), C('#d93a7f'), C('#ffd23f'), C('#e0a419')
    lid_c = c + V(0, h[1] + 0.03, 0)

    def paper_col(q):
        dots = smooth((0.28 - length(((q * 9) % 1.0) - 0.5)) / 0.05)      # bolinhas no papel
        return mix(mix(paper2, paper, smooth((q[:, 1] - 0.05) / 0.4)), C('#ffd1e6'), dots * 0.6)
    parts = [
        Part(lambda q: rbox(q, c, h, 0.035), paper_col, 0.45),
        Part(lambda q: rbox(q, lid_c, V(0.275, 0.05, 0.275), 0.025), paper_col, 0.45, 0.004),     # tampa
        Part(lambda q: np.minimum(rbox(q, c + V(0, 0.03, 0), V(0.06, 0.305, 0.258), 0.01),     # fita em cruz
                                  rbox(q, c + V(0, 0.03, 0), V(0.258, 0.305, 0.06), 0.01)),
             lambda q: mix(ribbon2, ribbon, smooth((q[:, 1] - 0.1) / 0.4)), 0.7, 0.003),
    ]
    top = lid_c + V(0, 0.06, 0)
    for zs in (1, -1):                                                       # laço: duas alças e as pontas
        loop = top + V(zs * 0.12, 0.06, 0)
        parts.append(Part(lambda q, loop=loop: np.abs(ellipsoid(q, loop, V(0.13, 0.08, 0.06))) - 0.02,
                          ribbon, 0.75, 0.02))
    parts.append(Part(lambda q: sphere(q, top + V(0, 0.02, 0), 0.055), ribbon2, 0.75, 0.02))       # nó
    return Scene(parts, scale=1.2)


def food_bomb():
    """Bomba de desenho animado: bola preta brilhante, tampinha, pavio e faísca."""
    c, r = V(0, 0.32, 0), 0.3
    cap = c + V(0.08, r * 0.92, 0)
    parts = [
        Part(lambda q: sphere(q, c, r), lambda q: mix(C('#15151c'), C('#3a3a48'), smooth((q[:, 1] - c[1]) * 3 + 0.2)[:, None]),
             0.9),
        Part(lambda q: capsule(q, cap - V(0.03, 0.06, 0), cap + V(0.02, 0.03, 0), 0.075), C('#6b6b78'), 0.6, 0.01),
    ]
    A = [cap + V(0.02, 0.03, 0), cap + V(0.07, 0.12, 0.0), cap + V(0.16, 0.16, 0.02)]
    B = A[1:] + [cap + V(0.22, 0.24, 0.03)]
    parts.append(capsules_part(A, B, 0.022, [C('#b08a5a')] * 3, 0.2))
    spark = cap + V(0.22, 0.26, 0.03)
    parts.append(Part(lambda q: sphere(q, spark, 0.05), C('#fff2a8'), 0.3, 0.02))
    SA, SB = [], []
    for k in range(6):
        a = k * np.pi / 3 + 0.3
        d = V(np.cos(a), np.sin(a), 0.3 * np.cos(2 * a)) * 0.11
        SA.append(spark); SB.append(spark + d)
    parts.append(capsules_part(SA, SB, 0.016, [C('#ffb52e'), C('#ff6a1a')] * 3, 0.4, 0.01))
    return Scene(parts, scale=1.2)


def food_donut():
    M = rot_axis(R, np.radians(10))           # inclina a face de cima para a câmera
    cc = V(0, 0.36, 0)
    Rm, r = 0.27, 0.14

    def L(p):
        return (p - cc) @ M

    def wave(q):
        a = np.arctan2(q[:, 2], q[:, 0])
        return -0.025 + 0.022 * np.sin(5 * a + 0.4) + 0.012 * np.sin(11 * a)

    def dough(p):
        return torus0(L(p), Rm, r)

    def frost(p):
        q = L(p)
        return np.maximum(torus0(q, Rm, r + 0.018), wave(q) - q[:, 1])

    def frost_col(p):
        q = L(p)
        a = (np.arctan2(q[:, 2], q[:, 0]) + np.pi) / (2 * np.pi)
        t = 0.5 + 0.5 * np.sin(a * 2 * np.pi + 0.8)
        return mix(C('#ff8cc6'), C('#8fd8ff'), t) * 1.0

    def dough_col(p):
        q = L(p)
        return mix(C('#e79a4f'), C('#ffd59a'), np.clip(0.5 - q[:, 1] * 3, 0, 1))
    parts = [Part(dough, dough_col, 0.25), Part(frost, frost_col, 0.85)]
    g = rng0(7)
    A, B, cols = [], [], []
    for _ in range(26):
        th = g.uniform(0, 2 * np.pi); ph = np.radians(g.uniform(25, 85))
        cen = V(np.cos(th), 0, np.sin(th))
        pl = cen * (Rm + (r + 0.018) * np.cos(ph)) + Y * (r + 0.018) * np.sin(ph)
        nl = cen * np.cos(ph) + Y * np.sin(ph)
        td = norm(np.cross(nl, norm(g.normal(size=3))))
        pw, tw = cc + M @ pl, M @ td
        A.append(pw - tw * 0.035); B.append(pw + tw * 0.035)
        cols.append(SPRINKLE_COLS[g.integers(len(SPRINKLE_COLS))])
    parts.append(capsules_part(A, B, 0.014, cols, 0.6))
    return Scene(parts, scale=1.35)


def food_snail():
    return Scene(snail_model(), rot=rot_y(np.radians(-15)), scale=1.45)


def snail_model():
    lime, lime2 = C('#a6e03c'), C('#e2f57a')

    def body_col(q):
        return mix(lime, lime2, np.clip((q[:, 1] - 0.05) * 2.2, 0, 1))
    parts = [
        Part(lambda q: round_cone(q, V(-0.38, 0.07, 0), V(0.22, 0.1, 0), 0.06, 0.11), body_col, 0.55),
        Part(lambda q: capsule(q, V(0.22, 0.1, 0), V(0.33, 0.3, 0), 0.11), body_col, 0.55, 0.05),
        Part(lambda q: sphere(q, V(0.35, 0.36, 0), 0.125), body_col, 0.55, 0.05),
        Part(lambda q: capsule(q, V(0.36, 0.42, 0.05), V(0.4, 0.6, 0.11), 0.022), body_col, 0.5, 0.02),
        Part(lambda q: capsule(q, V(0.36, 0.42, -0.05), V(0.4, 0.6, -0.11), 0.022), body_col, 0.5, 0.02),
    ]
    for zs in (1, -1):
        parts += eye_parts(V(0.41, 0.63, 0.12 * zs), 0.062, V(0.9, -0.1, 0.3 * zs), sleepy=C('#ffd43b'))
    # sorriso
    parts.append(Part(lambda q: capsule(q, V(0.47, 0.33, -0.04), V(0.47, 0.33, 0.04), 0.009), C('#3b5a12'), 0.2))
    M = np.stack([V(1, 0, 0), Y, V(0, 0, 1)], 1)
    parts.append(swirl_shell(V(-0.08, 0.34, 0), 0.27, 0.19, M))
    return parts


def acorn_parts(c, s=1.0, tilt=0.0):
    """Bolota (fruto do carvalho): corpinho marrom liso, chapéu escamado e um cabinho."""
    c = np.asarray(c, float)
    up = norm(V(np.sin(tilt), np.cos(tilt), 0))
    body = c - up * 0.02 * s

    def cap_col(q):
        scales = 0.5 + 0.5 * np.sin(q[:, 0] * 90 / s) * np.sin(q[:, 2] * 90 / s)
        return mix(C('#6e4322'), C('#9a6434'), scales)
    return [Part(lambda q: ellipsoid(q, body, V(0.07, 0.085, 0.07) * s), C('#c98b4a'), 0.7),
            Part(lambda q: np.maximum(ellipsoid(q, c + up * 0.045 * s, V(0.078, 0.05, 0.078) * s),
                                      -((q - c) @ up) + 0.02 * s), cap_col, 0.3, 0.004),
            Part(lambda q: capsule(q, c + up * 0.085 * s, c + up * 0.12 * s + V(0.012, 0, 0) * s, 0.012 * s),
                 C('#5a3a20'), 0.2, 0.004)]


def squirrel_model():
    """Esquilo fofinho segurando uma bolota, com o rabo peludo enrolado para cima."""
    fur, fur2, cream = C('#d9792b'), C('#b85f1c'), C('#f8e4c4')

    def plush(base):
        return lambda q: base * (0.88 + 0.22 * fbm(q * 40, 2))[:, None]
    body_c = V(0.02, 0.26, 0)

    def body_col(q):
        belly = smooth(((q[:, 0] - body_c[0]) / 0.2 - 0.25) / 0.3)
        return plush(mix(fur, cream, belly))(q)
    head_c = V(0.12, 0.55, 0)

    def head_col(q):
        rel = q - head_c
        muzzle = smooth((rel[:, 0] - 0.08) / 0.06) * smooth((0.02 - rel[:, 1]) / 0.08)
        return plush(mix(fur, cream, muzzle))(q)
    parts = [
        Part(lambda q: ellipsoid(q, body_c, V(0.2, 0.24, 0.19)), body_col, 0.15),
        Part(lambda q: sphere(q, head_c, 0.17), head_col, 0.15, 0.05),
        Part(lambda q: ellipsoid(q, head_c + V(0.13, -0.04, 0), V(0.08, 0.065, 0.09)), plush(cream), 0.15, 0.04),
        Part(lambda q: sphere(q, head_c + V(0.205, -0.02, 0), 0.03), C('#5a2a1a'), 0.5, 0.01),     # nariz
    ]
    for zs in (1, -1):
        ear = head_c + V(-0.03, 0.15, zs * 0.09)
        parts.append(Part(lambda q, ear=ear: round_cone(q, ear - V(0, 0.04, 0), ear + V(-0.02, 0.07, zs * 0.01), 0.05, 0.015),
                          plush(fur), 0.15, 0.03))
        parts.append(Part(lambda q, zs=zs: capsule(q, V(0.12, 0.08, zs * 0.11), V(0.2, 0.05, zs * 0.12), 0.05),
                          plush(fur2), 0.15, 0.03))                                          # patas de trás
        parts.append(Part(lambda q, zs=zs: capsule(q, V(0.12, 0.36, zs * 0.12), V(0.2, 0.3, zs * 0.05), 0.035),
                          plush(fur), 0.15, 0.02))                                           # bracinhos
        parts += eye_parts(head_c + V(0.1, 0.05, zs * 0.085), 0.045, V(0.7, 0.1, 0.5 * zs))
        parts.append(Part(lambda q, zs=zs: sphere(q, head_c + V(0.12, -0.04, zs * 0.11), 0.03), C('#ff9fb0'), 0.1))
    parts += acorn_parts(V(0.24, 0.3, 0), 0.9)                                                # a bolota nas mãos
    # rabo: bolinhas peludas num S para cima e para trás
    t = np.linspace(0, 1, 9)
    pts = [V(-0.18 - 0.22 * u + 0.1 * u * u, 0.12 + 0.75 * u, 0.0) + V(0.12 * np.sin(u * 3.0), 0, 0) for u in t]
    rad = [0.11 + 0.07 * np.sin(np.pi * u) for u in t]

    def tail_col(q):
        tip = smooth((q[:, 1] - 0.7) / 0.2)
        return plush(mix(fur, cream, tip * 0.6))(q)
    parts.append(Part(lambda q: np.min([sphere(q, p, r) for p, r in zip(pts, rad)], 0) + 0.012 * vnoise(q * 30),
                      tail_col, 0.12, 0.06))
    return parts


def food_squirrel():
    return Scene(squirrel_model(), rot=rot_y(np.radians(-15)), scale=1.25)


def holo_col(q, k=1.0):
    """Holográfico: rosa, azul-piscina e lilás mudando com a posição, com brilho perolado."""
    t = np.sin((q[:, 0] * 5 + q[:, 1] * 7 - q[:, 2] * 4) * k)
    u = np.sin((q[:, 0] * 3 - q[:, 1] * 5 + q[:, 2] * 6) * k + 1.3)
    col = mix(C('#ff9ad5'), C('#8fe8ff'), smooth((t + 1) / 2))
    col = mix(col, C('#c9a6ff'), smooth((u + 1) / 2) * 0.6)
    return mix(col, C('#ffffff'), smooth((q[:, 1] * 2 - 1.1 + 0.3 * t) / 0.3) * 0.35)


HEART_TILT = rot_axis(V(1, 0, 0), np.radians(-40))     # o coração de frente para a câmera (que olha de cima)


def heart_sdf(q, c, s, tilt=True):
    """Coração 3D (dois lobos e a ponta para baixo), achatado na frente/trás e inclinado para a câmera."""
    p = (q - c) / s
    if tilt:
        p = p @ HEART_TILT
    p = p * V(1, 1, 1.6)
    lobes = np.minimum(sphere(p, V(0.11, 0.06, 0), 0.15), sphere(p, V(-0.11, 0.06, 0), 0.15))
    tip = round_cone(p, V(0, 0.02, 0), V(0, -0.22, 0), 0.19, 0.02)
    return smin(lobes, tip, 0.06) * s / 1.6


def glass_heart_col(c, s):
    """Vidro holográfico do Hand Heart: azul de um lado, rosa do outro, lilás no meio e reflexos brancos."""
    c = np.asarray(c, float)

    def f(q):
        rel = (q - c) / s
        col = mix(C('#7fd8ff'), C('#ff8fd0'), smooth((rel[:, 0] + 0.18) / 0.36))
        col = mix(col, C('#c9a6ff'), np.exp(-(rel[:, 0] / 0.12) ** 2) * 0.45)
        shine = np.exp(-(((rel[:, 0] + 0.11) / 0.06) ** 2 + ((rel[:, 1] - 0.1) / 0.05) ** 2))      # reflexo grande
        shine += 0.7 * np.exp(-(((rel[:, 0] - 0.12) / 0.035) ** 2 + ((rel[:, 1] - 0.12) / 0.03) ** 2))
        return mix(col, C('#ffffff'), np.clip(shine, 0, 1) * 0.9)
    return f


def heart_hands_model():
    """Hand Heart (o presente de 100 moedas do TikTok): coração de vidro holográfico flutuando, um anel de
    arco-íris em diagonal em volta e duas mãos rosa de palmas para cima vindo dos cantos de baixo.
    Montado de frente (plano xy); a cena inteira inclina para a câmera em food_hand_hearts."""
    hc, hs = V(0, 0.7, 0), 1.45
    parts = [Part(lambda q: heart_sdf(q, hc, hs, tilt=False), glass_heart_col(hc, hs), 1.0)]
    M = rot_axis(V(1, 0, 0), np.radians(18)) @ rot_axis(V(0, 0, 1), np.radians(-22))   # órbita quase deitada, em diagonal

    def ring_col(q):
        a = np.arctan2(((q - hc) @ M)[:, 2], ((q - hc) @ M)[:, 0])
        hue = (np.sin(a * 2) + 1) / 2
        col = mix(C('#ff5fd2'), C('#5fe3ff'), hue)
        return mix(col, C('#fff36a'), ((np.sin(a * 3 + 1.2) + 1) / 2) ** 3)
    parts.append(Part(lambda q: torus0((q - hc) @ M, 0.5, 0.017), ring_col, 1.0))
    pink, light, cuff = C('#ff4f9a'), C('#ffbfdc'), C('#fff1f7')
    for xs in (1, -1):                                  # mão direita (xs = 1) e esquerda, palma para cima
        palm = V(xs * 0.24, 0.28, 0.02)

        def hand_col(q, palm=palm):
            return mix(pink, light, smooth((q[:, 1] - palm[1] + 0.12) / 0.28))
        parts.append(Part(lambda q, palm=palm: ellipsoid(q, palm, V(0.14, 0.055, 0.12)), hand_col, 0.5, 0.0))
        elbow = V(xs * 0.5, 0.02, 0.06)                                 # antebraço vindo do canto de baixo
        parts.append(Part(lambda q, palm=palm, elbow=elbow: round_cone(q, palm + V(xs * 0.06, -0.03, 0), elbow, 0.07, 0.085),
                          hand_col, 0.5, 0.04))
        cuff_c = palm + (elbow - palm) * 0.75
        parts.append(Part(lambda q, c=cuff_c, e=elbow, p=palm: np.maximum(capsule(q, c, e, 0.1),
                                                                         -((q - c) @ norm(e - p))), cuff, 0.4, 0.01))
        for k in range(4):                                              # dedos abertos para cima e para fora
            base = palm + V(xs * (0.06 + 0.035 * k), 0.03, 0.05 - 0.035 * k)
            tip = base + V(xs * (0.02 + 0.03 * k), 0.15 - 0.015 * abs(k - 1.5), 0.02)
            parts.append(Part(lambda q, a=base, b=tip: capsule(q, a, b, 0.03), hand_col, 0.5, 0.015))
        thumb = palm + V(-xs * 0.1, 0.02, 0.06)                           # polegar apontando para o coração
        parts.append(Part(lambda q, a=thumb, b=thumb + V(-xs * 0.04, 0.12, 0.0): capsule(q, a, b, 0.033), hand_col,
                          0.5, 0.015))
    return parts


def food_hand_hearts():
    import tema_coracao                     # comida do pacote tema_coracao
    return tema_coracao.food_coracao()


def _food_hand_hearts_antigo():
    return Scene(heart_hands_model(), rot=HEART_TILT, scale=1.0)


def pearl(base_fn):
    """Pele perolada: a cor base com um brilho furta-cor suave por cima."""
    return lambda q: mix(base_fn(q), holo_col(q, 1.6), 0.22)


def bright_gold(q):
    """Ouro claro de joia (moedas, engastes): não escurece perto do chão como o ouro da armadura."""
    n = fbm(q * 24, 2)
    return np.minimum(mix(C('#d8960c'), C('#ffd35a'), smooth((n - 0.3) / 0.5)) * 1.05, 1)


def gem(c, r=0.03):
    """Brilhante: pedrinha branca bem polida."""
    return Part(lambda q: sphere(q, c, r), lambda q: mix(C('#ffffff'), C('#d8ecff'), smooth((q[:, 1] - c[1]) / -r)),
                1.0, 0.004)


def gold_ring(c, R, tube, gold, seed=0):
    """Aro de ouro deitado (horizontal) em volta do ponto c."""
    c = np.asarray(c, float)
    return Part(lambda q: torus0(q - c, R, tube), gold, 0.97, 0.01)


def luxury_heart_gem(c, s=0.6):
    """Coração de cristal holográfico num engaste de ouro."""
    c = np.asarray(c, float)
    return [Part(lambda q: ellipsoid(q, c + V(0, -0.05 * s, 0), V(0.12, 0.035, 0.1) * s / 0.6), gold_col(c, 0.2, 2),
                 0.97, 0.01),
            Part(lambda q: heart_sdf(q, c + V(0, 0.06 * s, 0), s), glass_heart_col(c + V(0, 0.06 * s, 0), s), 1.0,
                 0.01)]


def mini_heart(c, s=0.35, k=0.01):
    """Coraçãozinho holográfico (enfeite da cobra e do cenário)."""
    return Part(lambda q: heart_sdf(q, c, s), holo_col, 0.95, k)


# ================================================================= COBRAS
THEMES = ['classico', 'rosa', 'rosquinha', 'esquilo', 'caracol', 'coracao', 'caixa', 'queimado']   # queimado = após a bomba
# caixa = caixa de presente da live (presentes sem skin no jogo): modelos em tema_caixa
DIRS = {'E': 0.0, 'S': -np.pi / 2, 'W': np.pi, 'N': np.pi / 2}

HEAD_C, HEAD_R = V(0, 0.42, 0), 0.42
SEG_C, SEG_R = V(0, 0.36, 0), 0.36


def body_color_fn(c, r, top, belly, spots=None, seed=0, flowers=False):
    c = np.asarray(c, float)

    def f(q):
        rel = (q - c) / r
        b = smooth((-rel[:, 1] - 0.15) / 0.35)
        col = mix(top, belly, b)
        hl = smooth((rel[:, 1] - 0.2) / 0.8)
        col = mix(col, np.minimum(top * 1.12, 1), hl * 0.4)
        if flowers:
            cell = np.floor(q * 8 + seed)
            fq = q * 8 + seed - cell
            hsh = _hash(cell)
            d = length(fq - 0.5)
            on = (hsh > 0.45) * (1 - b)
            pet = on * smooth((0.36 - d) / 0.05)
            ctr = on * smooth((0.13 - d) / 0.04)
            pc = np.where((hsh > 0.75)[:, None], C('#ffffff'), C('#ffd1e0'))
            col = mix(mix(col, pc, pet), C('#ffcf3d'), ctr)
        if spots is not None:
            n = vnoise(q * 7 + seed)
            col = mix(col, spots, smooth((n - 0.62) / 0.06) * (1 - b))
        return col
    return f


def face_col(base_fn, c, r, mouth_col=C('#5a1830'), blush=C('#ff8fab')):
    c = np.asarray(c, float)

    def f(q):
        col = base_fn(q)
        rel = q - c
        z = rel[:, 2]
        ym = -0.1 * r / 0.42 + 1.5 * z ** 2
        mouth = np.exp(-((rel[:, 1] - ym) / 0.012) ** 2) * (np.abs(z) < 0.13) * (rel[:, 0] > 0.2)
        cheek = np.zeros(len(q))
        for zs in (1, -1):
            cp = c + norm(V(0.55, -0.05, 0.62 * zs)) * r
            cheek = np.maximum(cheek, np.exp(-(length(q - cp) / 0.06) ** 2))
        col = mix(col, blush, cheek * 0.7)
        return mix(col, mouth_col, mouth)
    return f


def head_eyes(c=HEAD_C, r=HEAD_R, er=0.115, spread=0.5, up=0.45):
    parts = []
    for zs in (1, -1):
        d = norm(V(0.62, up, spread * zs))
        parts += eye_parts(c + d * r * 0.92, er, norm(d + V(0.6, 0, 0)))
    return parts


PAL = {
    'classico': dict(top=C('#79d64f'), belly=C('#e2f7a0'), spots=C('#58b83a')),
    'rosa': dict(top=C('#ff5d8f'), belly=C('#ffd0de'), spots=None),
    'rosquinha': dict(top=C('#f0ad62'), belly=C('#ffd9a0'), spots=None),
    'esquilo': dict(top=C('#d9792b'), belly=C('#f8e4c4'), spots=None),
    'coracao': dict(top=C('#ff9ad5'), belly=C('#eef3ff'), spots=None),
    'caracol': dict(top=C('#a6e03c'), belly=C('#ebf98a'), spots=None),
    'queimado': dict(top=C('#2a2625'), belly=C('#4a4442'), spots=None),
    'skin_ferro': dict(top=C('#646b74'), belly=C('#a3aab3'), spots=None),     # skin: cobra de ferro
    'skin_bronze': dict(top=C('#a8622c'), belly=C('#e0a463'), spots=None),    # skin: cobra de bronze
    'skin_prata': dict(top=C('#a9b3bf'), belly=C('#e8edf2'), spots=None),     # skin: cobra de prata
    'skin_ouro': dict(top=C('#141113'), belly=C('#3b3438'), spots=None),      # skin: cobra preta de armadura de ouro
    'skin_platina': dict(top=C('#fbfdff'), belly=C('#e4eef3'), spots=None),   # skin: branca, máscara e asas
    'skin_esmeralda': dict(top=C('#c8102e'), belly=C('#ff5a6e'), spots=None), # skin: rubi com esmeralda
    'skin_diamante': dict(top=C('#ffffff'), belly=C('#e6eef8'), spots=None),  # skin: branca, coroa e asas
    'skin_mestre': dict(top=C('#1b1724'), belly=C('#2c2638'), spots=None),    # skin: preta, armadura roxa e coroa
}
SKINS = ['skin_ferro', 'skin_bronze', 'skin_prata', 'skin_ouro', 'skin_platina', 'skin_esmeralda', 'skin_diamante', 'skin_mestre']
DIRECTIONAL_BODY = {'skin_esmeralda', 'skin_mestre'}     # skins com corpo que depende da direção (barbatana): corpo_<v>_<dir>   # skins da cobra para o tema padrão (o clássico usa os sprites normais)
# skins de metal: emenda, rebites e crista (todas com metal escovado, emenda no meio e rebites em volta)
METAL_SKINS = {
    'skin_ferro': dict(seam=C('#30353b'), rivet=C('#d3d8de'), crest=C('#4a5059')),
    'skin_bronze': dict(seam=C('#4a2410'), rivet=C('#ffd27a'), crest=C('#6e3a17')),
    'skin_prata': dict(seam=C('#5f6873'), rivet=C('#ffffff'), crest=C('#7d8894')),
}


def frosting_cap(c, r, colA, colB, seed=0, low=-0.05):
    c = np.asarray(c, float)

    def sdf(q):
        rel = q - c
        a = np.arctan2(rel[:, 2], rel[:, 0])
        wave = r * (low + 0.13 * np.sin(6 * a + seed) + 0.06 * np.sin(13 * a + 2 * seed))
        return np.maximum(length(rel) - (r + 0.028), wave - rel[:, 1])

    def col(q):
        rel = q - c
        t = 0.5 + 0.5 * np.sin(np.arctan2(rel[:, 2], rel[:, 0]) * 1 + rel[:, 1] * 4 + seed)
        return mix(colA, colB, t)
    return Part(sdf, col, 0.85)


def burnt(base_fn, seed=0):
    """Fuligem de desenho animado: manchas de cinza e umas brasinhas laranja."""
    def f(q):
        col = base_fn(q)
        ash = smooth((fbm(q * 16 + seed, 2) - 0.6) / 0.08)
        col = mix(col, C('#6e6765'), ash * 0.35)
        cell = np.floor(q * 14 + seed)
        d = length(q * 14 + seed - cell - 0.5)
        ember = (_hash(cell) > 0.94) * smooth((0.3 - d) / 0.1)
        return mix(col, C('#ff7a2a'), ember)
    return f


def metal(base_fn, c, r, seed=0, seam_col=C('#30353b')):
    """Metal escovado com uma emenda escura no meio do segmento (skins de metal)."""
    c = np.asarray(c, float)

    def f(q):
        col = base_fn(q) * (0.82 + 0.3 * fbm(q * V(40, 4, 40) + seed, 2))[:, None]
        seam = np.exp(-((q[:, 1] - c[1]) / (r * 0.06)) ** 2)
        return mix(col, seam_col, seam * 0.85)
    return f


def rivets(c, r, n, size=0.034, phase=0.0, col=C('#d3d8de')):
    """Rebites em volta do segmento, em cima da emenda."""
    c = np.asarray(c, float)
    parts = []
    for k in range(n):
        a = 2 * np.pi * k / n + phase
        p = c + V(np.cos(a) * r, 0, np.sin(a) * r)
        parts.append(Part(lambda q, p=p: sphere(q, p, size), col, 0.95, 0.01))
    return parts


# ----------------------------------------------------------------- skin de ouro
GOLD_DARK, GOLD, GOLD_LIGHT = C('#4a2400'), C('#c98500'), C('#ffd86a')
BLACK, BLACK_HI = C('#141113'), C('#3b3438')
HORN_BASE, HORN_TIP = C('#f6ead0'), C('#3b2a1c')
ARMOR_T = 0.035                 # meia espessura das placas da armadura


def black_skin(c, r):
    """Pele preta brilhante (a cobra por baixo da armadura de ouro)."""
    c = np.asarray(c, float)
    return lambda q: mix(BLACK, BLACK_HI, smooth(((q[:, 1] - c[1]) / r - 0.1) / 0.9) * 0.7)


def gold_col(c, r, seed=0):
    """Ouro polido: escuro embaixo, claro em cima, com um leve escovado."""
    c = np.asarray(c, float)

    def f(q):
        rel = (q - c) / r
        col = mix(GOLD_DARK, GOLD, smooth((rel[:, 1] + 0.1) / 0.6))
        col = mix(col, GOLD_LIGHT, smooth((rel[:, 1] - 0.7) / 0.4) * 0.45)
        return np.minimum(col * (0.9 + 0.16 * fbm(q * V(30, 3, 30) + seed, 2))[:, None], 1)
    return f


def armor_plate(c, r, low, seed=0, fin=True, metal_col=None):
    """Placa de armadura em cima de uma esfera (da altura low*r para cima), com crista no meio.
    metal_col(c, r, seed) -> cor (padrão: o ouro da skin de ouro)."""
    c = np.asarray(c, float)
    gold_col = metal_col or globals()['gold_col']
    outer = r + 2 * ARMOR_T

    def plate(q):
        rel = q - c
        return np.maximum(np.abs(length(rel) - (r + ARMOR_T)) - ARMOR_T, low * r - rel[:, 1])
    parts = [Part(plate, gold_col(c, r, seed), 0.95, 0.0)]
    if fin:                     # crista: uma faixa mais alta de frente para trás
        parts.append(Part(lambda q: np.maximum(np.maximum(np.abs(q[:, 2] - c[2]) - 0.028, length(q - c) - (outer + 0.035)),
                                               r * (low + 0.25) - (q[:, 1] - c[1])), gold_col(c, r, seed + 1), 0.95, 0.015))
    return parts


def ring_rivets(c, r, height, n, size=0.03, phase=0.0, col=None):
    """Rebites (dourados claros por padrão) na borda da placa (círculo na altura `height` acima do centro)."""
    c = np.asarray(c, float)
    col = GOLD_LIGHT if col is None else col
    rad = np.sqrt(max((r + 2 * ARMOR_T) ** 2 - height ** 2, 0))
    return [Part(lambda q, p=c + V(np.cos(a) * rad, height, np.sin(a) * rad): sphere(q, p, size), col, 0.95, 0.01)
            for a in 2 * np.pi * np.arange(n) / n + phase]


def gold_horn(pts, radii, seed=9):
    """Chifre de touro de ouro: tubo afinando ao longo dos pontos `pts`."""
    def sdf(q):
        return np.min([round_cone(q, pts[i], pts[i + 1], radii[i], radii[i + 1]) for i in range(len(pts) - 1)], 0)
    ref = pts[0]
    return Part(sdf, gold_col(ref, 0.6, seed), 0.97, 0.02)


def taurus_helmet(c, r, horn_scale=1.0, spike_scale=1.0):
    """Capacete de ouro de touro: rosto aberto com protetores nas bochechas, faixa preta no alto,
    três espetos, um espetinho na testa e dois chifres enormes de ouro saindo de encaixes nos lados."""
    c = np.asarray(c, float)
    outer = r + 2 * ARMOR_T
    gold = gold_col(c, r, 3)

    def shell(q):
        rel = q - c
        s = np.maximum(np.abs(length(rel) - (r + ARMOR_T)) - ARMOR_T, -(rel[:, 1] + r * 0.5))
        face = np.maximum(np.maximum(rel[:, 1] - r * 0.42, np.abs(rel[:, 2]) - r * 0.48), r * 0.15 - rel[:, 0])
        return np.maximum(s, -face)                     # rosto aberto da testa para baixo

    def brow(q):                    # aba em cima da abertura do rosto
        rel = q - c
        return np.maximum(np.maximum(np.abs(length(rel) - (outer + 0.012)) - 0.022,
                                     np.abs(rel[:, 1] - r * 0.5) - 0.045), r * 0.25 - rel[:, 0])

    def cheeks(q):                  # protetores das bochechas, um degrau para fora
        rel = q - c
        return np.maximum(np.maximum(np.abs(length(rel) - (outer + 0.012)) - 0.022,
                                     np.maximum(rel[:, 1] - r * 0.3, -(rel[:, 1] + r * 0.5))),
                          np.maximum(r * 0.48 - np.abs(rel[:, 2]), -rel[:, 0] - r * 0.1))

    def band(q):                    # faixa preta de frente para trás no alto
        rel = q - c
        return np.maximum(np.maximum(np.abs(rel[:, 2]) - r * 0.16, length(rel) - (outer + 0.02)), r * 0.5 - rel[:, 1])
    parts = [Part(shell, gold, 0.97, 0.0), Part(brow, gold, 0.97, 0.01), Part(cheeks, gold, 0.97, 0.01),
             Part(band, black_skin(c, r), 0.9, 0.0)]

    k = spike_scale                 # espetos: o do meio maior, dois dos lados e um pequeno na testa
    for base, tip, rad in [(V(0, outer - 0.03, 0), V(0, outer + 0.26 * k, 0), 0.085),
                           (V(-0.04, outer * 0.86, r * 0.5), V(-0.06, outer * 0.86 + 0.16 * k, r * 0.68), 0.06),
                           (V(-0.04, outer * 0.86, -r * 0.5), V(-0.06, outer * 0.86 + 0.16 * k, -r * 0.68), 0.06),
                           (V(r * 0.62, r * 0.72, 0), V(r * 0.62 + 0.12 * k, r * 0.72 + 0.1 * k, 0), 0.05)]:
        parts.append(Part(lambda q, a=c + base, b=c + tip, rad=rad: round_cone(q, a, b, rad, 0.006), gold_col(c, r, 5),
                          0.97, 0.015))

    for zs in (1, -1):              # encaixes cilíndricos e chifres
        m0, m1 = c + V(0, r * 0.15, zs * r * 0.82), c + V(0, r * 0.15, zs * r * 1.12)
        parts.append(Part(lambda q, a=m0, b=m1: capsule(q, a, b, 0.11), gold_col(c, r, 8), 0.97, 0.02))
        # curva do chifre: sai para fora e um pouco para baixo, sobe num arco largo e a ponta volta para dentro
        ctrl = [V(0, 0, 0), V(0, -r * 0.2, zs * r * 0.75), V(0.02, r * 1.0, zs * r * 1.25), V(0.1, r * 2.2, zs * r * 0.5)]
        t = np.linspace(0, 1, 18)
        curve = [((1 - u) ** 3) * ctrl[0] + 3 * ((1 - u) ** 2) * u * ctrl[1] + 3 * (1 - u) * u * u * ctrl[2] + u ** 3 * ctrl[3]
                 for u in t]
        pts = [m1 + p * horn_scale for p in curve]
        radii = [(0.105 * (1 - u) ** 0.8 + 0.006) * (0.6 + 0.4 * horn_scale) for u in t]
        parts.append(gold_horn(pts, radii))
    return parts


# ----------------------------------------------------------------- skin de platina
PLAT_LIGHT, PLAT, PLAT_DARK, PLAT_RIM = C('#c9fbf2'), C('#7fe0d0'), C('#45b5a6'), C('#2a8a7e')   # cores do escudo


def shield_2d(y, z, top, w, bot):
    """Distância (aprox.) ao escudo do elo no plano (y para cima, z para o lado): lados retos até o meio,
    ponta embaixo (dois arcos) e três pontas no alto."""
    mid = (top + bot) / 2 + 0.02
    Rr = (mid - bot) ** 2 / (2 * w) + w / 2                    # arcos que se encontram na ponta de baixo
    lens = np.maximum(np.sqrt((z + (Rr - w)) ** 2 + (y - mid) ** 2) - Rr,
                      np.sqrt((z - (Rr - w)) ** 2 + (y - mid) ** 2) - Rr)
    lower = np.where(y < mid, lens, np.abs(z) - w)
    peaks = top + 0.03 * np.cos(z / w * np.pi * 1.5) - 0.01      # pontas no meio e nos cantos
    return np.maximum(lower, y - peaks)


def platinum_mask(c, r):
    """Máscara no formato do escudo de platina, fechada sobre o rosto (frente = +x): duas metades em tons
    de verde-água, borda escura e o diamante no meio."""
    c = np.asarray(c, float)
    top, w, bot = r * 0.92, r * 0.8, -r * 0.4

    def shape(q):
        rel = q - c
        return shield_2d(rel[:, 1], rel[:, 2], top, w, bot)            # escudo fechado: sem rosto

    def sdf_mask(q):
        rel = q - c
        shell = np.abs(length(rel) - (r + 0.035)) - 0.025
        return np.maximum(np.maximum(shell, shape(q)), r * 0.05 - rel[:, 0])

    def col(q):
        rel = q - c
        half = mix(PLAT, PLAT_LIGHT, smooth(rel[:, 2] / 0.02))      # metade clara de um lado, escura do outro
        half = mix(half, PLAT_DARK, smooth(-rel[:, 2] / 0.02) * 0.4)
        edge = smooth((shield_2d(rel[:, 1], rel[:, 2], top, w, bot) + 0.045) / 0.01)
        return mix(half, PLAT_RIM, edge)
    gem_c = c + norm(V(1, -0.05, 0)) * (r + 0.06)

    def gem(q):
        p = np.abs((q - gem_c) @ np.stack([V(0, 1, 0), V(0, 0, 1), V(1, 0, 0)], 1) * V(1, 1.3, 2.2))
        return (p.sum(1) - 0.075) * 0.45
    return [Part(sdf_mask, col, 0.85, 0.0),
            Part(gem, lambda q: mix(C('#ffffff'), C('#b9f5ea'), smooth((gem_c[1] - q[:, 1]) / 0.05)), 1.0, 0.004)]


def angel_wing(c, r, zs):
    """Asa de anjo no lugar da orelha: penas em leque, para cima e para trás."""
    base = c + V(-0.08, r * 0.55, zs * r * 0.72)
    parts = [Part(lambda q: sphere(q, base, 0.07), C('#ffffff'), 0.4, 0.03)]
    for k, (up, back, size) in enumerate([(1.0, 0.1, 1.9), (0.85, 0.45, 1.8), (0.6, 0.8, 1.6), (0.35, 1.0, 1.35),
                                           (0.1, 1.0, 1.1)]):
        d = norm(V(-back, up, zs * 0.75))
        parts.append(leaf_part(base + V(-0.03 * k, -0.025 * k, 0), d, size, col=C('#ffffff'), col2=C('#e2f8f4'),
                               twist=zs * 0.9))
    return parts


def platinum_metal(c, r, seed=0):
    """Metal de platina (as cores do escudo): verde-água claro em cima, escuro embaixo, levemente escovado."""
    c = np.asarray(c, float)

    def f(q):
        rel = (q - c) / r
        col = mix(PLAT_DARK, PLAT, smooth((rel[:, 1] + 0.1) / 0.6))
        col = mix(col, PLAT_LIGHT, smooth((rel[:, 1] - 0.6) / 0.4) * 0.6)
        return np.minimum(col * (0.92 + 0.14 * fbm(q * V(30, 3, 30) + seed, 2))[:, None], 1)
    return f


def platinum_body(variant):
    """Bolinha do corpo: branca, com uma placa de armadura de platina por cima e rebites brancos."""
    c, r = SEG_C, SEG_R
    p = PAL['skin_platina']
    parts = [Part(lambda q: sphere(q, c, r), body_color_fn(c, r, p['top'], p['belly'], None, seed=7), 0.7)]
    parts += armor_plate(c, r, 0.35, seed=7 + variant, fin=variant == 0, metal_col=platinum_metal)
    parts += ring_rivets(c, r, r * 0.35 + 0.02, 8, 0.026, 0.2 + 0.4 * variant, col=C('#ffffff'))
    return parts


def platinum_tail():
    """Cauda branca com placa de platina e ponteira de platina com borda escura."""
    c, r, tip = V(0, 0.3, 0), 0.3, V(-0.62, 0.1, 0)
    p = PAL['skin_platina']
    skin = body_color_fn(SEG_C, SEG_R, p['top'], p['belly'], None, seed=5)
    parts = [Part(lambda q: sphere(q, c, r), skin, 0.7), Part(lambda q: round_cone(q, c, tip, 0.27, 0.05), skin, 0.7, 0.06)]
    parts += armor_plate(c, r, 0.35, seed=5, fin=False, metal_col=platinum_metal)
    parts += ring_rivets(c, r, r * 0.35 + 0.02, 6, 0.024, col=C('#ffffff'))
    a = c + (tip - c) * 0.6
    parts.append(Part(lambda q: round_cone(q, a, tip + V(-0.03, 0, 0), 0.14, 0.06), platinum_metal(c, r, 6), 0.95, 0.02))
    parts.append(Part(lambda q: torus0((q - a) @ np.stack([V(0, 1, 0), V(1, 0, 0), V(0, 0, 1)], 1), 0.14, 0.02),
                      PLAT_RIM, 0.9, 0.01))
    return parts


def platinum_head():
    """Cabeça da skin de platina: branca, sem rosto, com a máscara do escudo de platina fechada e asas de
    anjo como orelhas."""
    c, r = HEAD_C, HEAD_R
    p = PAL['skin_platina']
    base = body_color_fn(c, r, p['top'], p['belly'], None, seed=3)
    parts = [Part(lambda q: sphere(q, c, r), base, 0.7)]
    parts += platinum_mask(c, r)
    for zs in (1, -1):
        parts += angel_wing(c, r, zs)
    return parts


# ----------------------------------------------------------------- skin de esmeralda
EMERALD_D, EMERALD, EMERALD_L = C('#065a2a'), C('#16a34f'), C('#8ff0b8')
RUBY_D, RUBY, RUBY_L = C('#6e0016'), C('#d0102e'), C('#ff8a9a')


def emerald_col(q, seed=0.0):
    """Esmeralda lapidada: faixas de facetas claras e escuras, com brilhos."""
    facet = (np.sin(q[:, 0] * 9 + q[:, 1] * 6 + seed) + np.sin(q[:, 2] * 8 - q[:, 1] * 5 + seed * 2)) * 0.5
    col = mix(EMERALD_D, EMERALD, smooth((facet + 0.7) / 1.0))
    col = mix(col, EMERALD_D, smooth(-q[:, 1] * 2.0) * 0.3)                  # mais escura embaixo
    return mix(col, EMERALD_L, smooth((facet - 0.7) / 0.15) * 0.6)


def ruby_skin(c, r):
    """Pele de rubi: vermelho profundo, mais claro e brilhante no alto."""
    c = np.asarray(c, float)

    def f(q):
        rel = (q - c) / r
        col = mix(RUBY_D, RUBY, smooth((rel[:, 1] + 0.6) / 0.9))
        return mix(col, RUBY_L, smooth((rel[:, 1] - 0.55) / 0.4) * 0.5)
    return f


def fin_profile(x, y, z):
    """Perfil de barbatana de tubarão (unidades da barbatana): ergue-se em y, ponta varrida para -x, espessura em z."""
    t = np.clip(y / 0.44, 0, 1)
    xf = 0.3 - 0.66 * t ** 0.65                                          # borda da frente: curva, varrida para trás
    xb = -0.3 - 0.06 * t + 0.14 * np.sin(np.pi * t)                      # borda de trás: côncava
    d2 = np.maximum(np.maximum(-y - 0.12, y - 0.4), np.maximum(x - xf, xb - x))
    return np.maximum(d2, np.abs(z) - (0.06 * (1 - t) + 0.02))


def shark_fin(base, size, seed=0.0, col=None):
    """Barbatana de tubarão (de esmeralda, ou da cor `col`) em cima de `base`, apontando para trás (-x): borda
    da frente curva, borda de trás côncava, fininha nas laterais e mais fina na ponta."""
    base = np.asarray(base, float)

    def sdf(q):
        p = (q - base) / size
        return fin_profile(p[:, 0], p[:, 1], p[:, 2]) * size * 0.6
    return Part(sdf, col or (lambda q: emerald_col(q * 1.3, seed)), 0.95, 0.02)


def emerald_metal(c, r, seed):
    """Cor das placas de armadura de esmeralda (para armor_plate)."""
    return lambda q: mix(emerald_col(q * 1.2, seed), EMERALD_D, 0.3)     # um tom abaixo da barbatana


def emerald_body(variant, direction=None):
    """Segmento de rubi coberto por uma placa de armadura de esmeralda (o rubi aparece embaixo e nas juntas),
    com rebites de rubi; com direção, a barbatana de esmeralda nas costas, apontando para trás do movimento."""
    c, r = SEG_C, SEG_R
    parts = [Part(lambda q: sphere(q, c, r), ruby_skin(c, r), 0.95)]
    parts += armor_plate(c, r, 0.15, seed=7 + variant, fin=False, metal_col=emerald_metal)
    parts += ring_rivets(c, r, r * 0.15 + 0.02, 8, 0.026, 0.2 + 0.4 * variant, col=RUBY)
    if direction is not None:                          # a cena gira para a direção (build.scene_for); aqui +x é a frente
        parts.append(shark_fin(c + V(0.04, r * 0.92, 0), 1.0 if variant == 0 else 0.8, seed=variant))
    return parts


def emerald_tail():
    """Cauda de rubi com uma barbatana pequena e a ponta de esmeralda."""
    c, tip = V(0, 0.3, 0), V(-0.62, 0.1, 0)
    skin = ruby_skin(c, 0.3)
    parts = [Part(lambda q: sphere(q, c, 0.3), skin, 0.95), Part(lambda q: round_cone(q, c, tip, 0.27, 0.05), skin, 0.95, 0.06),
             shark_fin(V(0.02, 0.58, 0), 0.6, seed=3)]
    parts += armor_plate(c, 0.3, 0.15, seed=5, fin=False, metal_col=emerald_metal)
    parts += ring_rivets(c, 0.3, 0.045 + 0.02, 6, 0.024, col=RUBY)
    a = c + (tip - c) * 0.62
    parts.append(Part(lambda q: round_cone(q, a, tip + V(-0.04, 0, 0), 0.12, 0.03), lambda q: emerald_col(q, 5), 0.95, 0.02))
    return parts


def emerald_head():
    """Capacete de esmeralda cobrindo a cabeça de rubi; na frente, um rubi em losango ocupando quase o rosto
    (o "olho"); em cima, um moicano de cristais de esmeralda da testa até a nuca."""
    c, r = HEAD_C, HEAD_R
    parts = [Part(lambda q: sphere(q, c, r), ruby_skin(c, r), 0.9)]

    gy, GH, GW = c[1] + 0.1, 0.44, 0.4                                  # rubi em losango no rosto (+x)

    def rhomb(q):                                       # 0 no centro do losango, 1 na borda
        return np.abs(q[:, 1] - gy) / GH + np.abs(q[:, 2] - c[2]) / GW

    def gem(q):                                         # lapidado: a frente sobe em pirâmide até o centro
        rel = q - c
        outer = length(rel) - (r + 0.16 - 0.14 * np.clip(rhomb(q), 0, 1))
        return np.maximum(np.maximum(outer, (rhomb(q) - 1) * 0.15), -rel[:, 0])

    def helmet(q):                                     # casco com o buraco do rosto onde fica o rubi
        rel = q - c
        shell = np.maximum(np.abs(length(rel) - (r + 0.03)) - 0.03, -(rel[:, 1] + r * 0.45))
        return np.maximum(shell, -np.maximum((rhomb(q) - 0.97) * 0.15, -rel[:, 0]))
    parts.append(Part(helmet, lambda q: emerald_col(q, 1.0), 0.95, 0.0))
    gem_c = V(c[0] + r, gy, c[2])

    def gem_col(q):
        rel = q - gem_c
        facet = smooth((np.abs(rel[:, 1]) * 0.9 - np.abs(rel[:, 2])) / 0.02)
        col = mix(RUBY, RUBY_D, facet * 0.5 + smooth(-rel[:, 1] / 0.2) * 0.3)
        glow = np.exp(-((rel[:, 1] - 0.06) ** 2 + (rel[:, 2] + 0.05) ** 2) / 0.003)
        return mix(col, C('#ffd0d8'), np.clip(glow, 0, 1) * 0.9)
    parts.append(Part(gem, gem_col, 1.0, 0.0))
    for k, (x, h) in enumerate([(0.08, 0.2), (-0.06, 0.3), (-0.2, 0.33), (-0.32, 0.26), (-0.41, 0.17)]):   # moicano
        root = c + V(x, np.sqrt(max(r * r - x * x, 0)) - 0.02, 0)
        tip = root + V(-0.08, h, 0)
        parts.append(Part(lambda q, a=root, b=tip: np.maximum(round_cone(q, a, b, 0.1, 0.015), np.abs(q[:, 2] - c[2]) - 0.06),
                          lambda q, k=k: emerald_col(q * 1.4, k), 0.95, 0.02))
    return parts


# ----------------------------------------------------------------- skin de diamante
DIA_DARK, DIA_LIGHT = C('#1a3d8f'), C('#a9d2ff')                 # cores do escudo de diamante (aro escuro e claro)
DIA_ICE, DIA_SHADE = C('#eef6ff'), C('#8fb6e6')                  # cristal de diamante


def diamond_col(q, seed=0.0):
    """Diamante lapidado: facetas poligonais de bordas nítidas, do branco ao azul gelado, com faíscas."""
    dirs = (V(1, 0.3, 0.2), V(-0.2, 1, 0.5), V(0.4, -0.3, 1), V(0.7, 0.7, -0.6))
    v = sum(np.sign(np.sin(q @ norm(n) * 8 + seed * (k + 1))) for k, n in enumerate(dirs)) / 4
    col = mix(DIA_SHADE, DIA_ICE, 0.55 + 0.45 * v)
    spark = np.sin(q @ norm(V(1, 1, 1)) * 40 + seed) > 0.97
    return mix(col, C('#ffffff'), spark * 0.8)


def diamond_metal(c, r, seed):
    """Cor das placas de armadura de diamante (para armor_plate)."""
    return lambda q: diamond_col(q * 1.3, seed)


def diamond_gem(c, size, stretch=(1.0, 1.0, 1.0), axes=None):
    """Diamante lapidado (octaedro) de `size`; stretch alonga em cada eixo (local x, y, z)."""
    c = np.asarray(c, float)
    M = np.eye(3) if axes is None else axes
    k = 1.0 / np.asarray(stretch, float)

    def sdf(q):
        p = np.abs(((q - c) @ M) * k)
        return (p.sum(1) - size) * 0.57 * min(stretch)

    def col(q):
        p = (q - c) @ M
        facet = np.sign(p[:, 0]) * 0.25 + np.sign(p[:, 1]) * 0.35 + np.sign(p[:, 2]) * 0.15
        return mix(DIA_SHADE, DIA_ICE, np.clip(0.55 + facet, 0, 1))
    return Part(sdf, col, 1.0, 0.0)


def shield_wing_ear(c, r, zs):
    """Orelha em asa: o leque de penas das asas do escudo de diamante (shields.wings), abrindo para cima e
    para fora no lado zs da cabeça, com as mesmas cores (azul escuro na base, azul claro na ponta)."""
    parts, size = [], 1.24 * 0.8
    root = c + V(-0.1, r * 0.45, zs * r * 0.78)
    for i in range(4):
        ang = np.radians(62 - 22 * i)                               # a de cima aponta mais para cima
        d = norm(V(-0.3, np.sin(ang) + 0.25, zs * np.cos(ang) * 0.7))   # para fora, para cima e um pouco para trás
        side = norm(np.cross(V(1, 0, 0), d))
        M = np.stack([d, side, np.cross(d, side)], 1)               # colunas = eixos da pena
        length_i = (0.46 - 0.07 * i) * size
        base = root + V(-0.02 * i, -0.07 * i, 0)
        cc = base + d * length_i * 0.5
        rad = np.array([length_i * 0.5, 0.075 * size, 0.04])

        def col(q, cc=cc, d=d, length_i=length_i):
            tip = np.clip(((q - cc) @ d) / length_i + 0.5, 0, 1)    # 0 na base, 1 na ponta
            return mix(DIA_DARK * 1.4, DIA_LIGHT, tip)
        parts.append(Part(lambda q, cc=cc, M=M, rad=rad: ellipsoid0((q - cc) @ M, rad), col, 0.7, 0.02))
    return parts


def diamond_crown(c, r):
    """Coroa de diamantes no lugar dos olhos: um aro de cristal em volta da frente da cabeça, na altura dos
    olhos, com cinco pontas de diamante subindo (a do meio maior) e pedrinhas no aro."""
    c = np.asarray(c, float)
    y0 = 0.22                                                       # altura do aro em relação ao centro

    def band(q):
        rel = q - c
        ring = np.abs(length(rel * V(1, 0, 1)) - (r * np.sqrt(1 - (y0 / r) ** 2) + 0.03)) - 0.035
        d = np.maximum(ring, np.abs(rel[:, 1] - y0) - 0.06)
        return np.maximum(d, -rel[:, 0] + 0.02)                     # só a metade da frente
    parts = [Part(band, lambda q: diamond_col(q * 1.6, 2.0), 0.97, 0.01)]
    R = r * np.sqrt(1 - (y0 / r) ** 2) + 0.06
    for k, ang in enumerate(np.radians([-70, -35, 0, 35, 70])):
        out = V(np.cos(ang), 0, np.sin(ang))
        h = 0.34 if k == 2 else (0.26 if k in (1, 3) else 0.18)
        up = norm(out * 0.15 + V(0, 1, 0))
        side = norm(np.cross(up, out))
        M = np.stack([side, up, np.cross(side, up)], 1)
        tipc = c + out * R + V(0, y0 + 0.06, 0) + up * h * 0.5
        parts.append(diamond_gem(tipc, 1.0, (0.085, h * 0.62, 0.06), M))       # ponta de diamante
        parts.append(diamond_gem(c + out * (R + 0.005) + V(0, y0 - 0.005, 0), 1.0, (0.035, 0.045, 0.03),
                                 np.stack([side, V(0, 1, 0), out], 1)))       # pedrinha no aro
    return parts


def diamond_body(variant):
    """Bolinha do corpo: branca, com placa de armadura de diamante, crista de cristal e rebites de diamante."""
    c, r = SEG_C, SEG_R
    p = PAL['skin_diamante']
    parts = [Part(lambda q: sphere(q, c, r), body_color_fn(c, r, p['top'], p['belly'], None, seed=9), 0.7)]
    parts += armor_plate(c, r, 0.2, seed=9 + variant, fin=variant == 0, metal_col=diamond_metal)
    parts += ring_rivets(c, r, r * 0.2 + 0.02, 8, 0.026, 0.2 + 0.4 * variant, col=DIA_LIGHT)
    return parts


def diamond_tail():
    """Cauda branca com placa de diamante e a ponta de cristal de diamante."""
    c, r, tip = V(0, 0.3, 0), 0.3, V(-0.62, 0.1, 0)
    p = PAL['skin_diamante']
    skin = body_color_fn(SEG_C, SEG_R, p['top'], p['belly'], None, seed=5)
    parts = [Part(lambda q: sphere(q, c, r), skin, 0.7), Part(lambda q: round_cone(q, c, tip, 0.27, 0.05), skin, 0.7, 0.06)]
    parts += armor_plate(c, r, 0.2, seed=5, fin=False, metal_col=diamond_metal)
    parts += ring_rivets(c, r, r * 0.2 + 0.02, 6, 0.024, col=DIA_LIGHT)
    a = c + (tip - c) * 0.6
    parts.append(Part(lambda q: round_cone(q, a, tip + V(-0.04, 0, 0), 0.13, 0.03), lambda q: diamond_col(q * 1.4, 4),
                      0.97, 0.02))
    return parts


def diamond_head():
    """Cabeça da skin de diamante: branca, sem olhos, com uma coroa de diamantes na altura dos olhos e as asas
    do escudo de diamante como orelhas."""
    c, r = HEAD_C, HEAD_R
    p = PAL['skin_diamante']
    parts = [Part(lambda q: sphere(q, c, r), body_color_fn(c, r, p['top'], p['belly'], None, seed=3), 0.7)]
    parts += diamond_crown(c, r)
    for zs in (1, -1):
        parts += shield_wing_ear(c, r, zs)
    return parts


# ----------------------------------------------------------------- skin de mestre
MASTER_DARK, MASTER_LIGHT, MASTER_FACE = C('#2f0d5e'), C('#b47cff'), C('#7a3ed6')     # cores do escudo de mestre
MASTER_GOLD = C('#ffd23a')


def master_metal(c, r, seed=0):
    """Metal roxo do escudo de mestre: escuro embaixo, claro em cima, levemente escovado."""
    c = np.asarray(c, float)

    def f(q):
        rel = (q - c) / r
        col = mix(MASTER_DARK, MASTER_FACE * 0.8, smooth((rel[:, 1] + 0.1) / 0.9) * 0.8)
        col = mix(col, MASTER_LIGHT, smooth((rel[:, 1] - 0.8) / 0.25) * 0.35)
        return np.minimum(col * (0.9 + 0.16 * fbm(q * V(30, 3, 30) + seed, 2))[:, None], 1)
    return f


def master_skin(c, r, seed=0):
    p = PAL['skin_mestre']
    return body_color_fn(c, r, p['top'], p['belly'], None, seed=seed)


def side_fin(c, r, zs, size, col):
    """Barbatana lateral (da cor da pele) saindo do lado zs da bolinha, quase deitada e varrida para trás."""
    c = np.asarray(c, float)
    out = norm(V(0, -0.1, zs))                      # para fora e um pouco para baixo
    up = norm(np.cross(out, V(1, 0, 0))) * zs       # normal da barbatana (perpendicular ao plano dela)
    base = c + out * r * 0.8

    def sdf(q):
        rel = (q - base) / size
        return fin_profile(rel[:, 0], rel @ out, rel @ up) * size * 0.6
    return Part(sdf, col, 0.75, 0.03)


def master_body(variant, direction=None):
    """Bolinha preta com placa de armadura roxa e rebites dourados; com direção, a barbatana roxa em cima da
    armadura e as barbatanas pretas nas laterais (a cena gira para a direção; +x é a frente)."""
    c, r = SEG_C, SEG_R
    skin = master_skin(c, r, 11)
    parts = [Part(lambda q: sphere(q, c, r), skin, 0.75)]
    parts += armor_plate(c, r, 0.55, seed=11 + variant, fin=False, metal_col=master_metal)
    parts += ring_rivets(c, r, r * 0.55 + 0.02, 8, 0.026, 0.2 + 0.4 * variant, col=MASTER_GOLD)
    if direction is not None:
        k = 1.0 if variant == 0 else 0.85
        parts.append(shark_fin(c + V(0.04, r * 0.92, 0), k, col=master_metal(c, r, 3 + variant)))
        for zs in (1, -1):
            parts.append(side_fin(c, r, zs, 0.9 * k, skin))
    return parts


def master_tail():
    """Cauda preta com placa roxa, barbatanas pequenas (roxa em cima, pretas nos lados) e ponta roxa."""
    c, r, tip = V(0, 0.3, 0), 0.3, V(-0.62, 0.1, 0)
    skin = master_skin(SEG_C, SEG_R, 5)
    parts = [Part(lambda q: sphere(q, c, r), skin, 0.75), Part(lambda q: round_cone(q, c, tip, 0.27, 0.05), skin, 0.75, 0.06)]
    parts += armor_plate(c, r, 0.55, seed=5, fin=False, metal_col=master_metal)
    parts += ring_rivets(c, r, r * 0.55 + 0.02, 6, 0.024, col=MASTER_GOLD)
    parts.append(shark_fin(V(0.02, 0.58, 0), 0.6, col=master_metal(c, r, 4)))
    for zs in (1, -1):
        parts.append(side_fin(c, r, zs, 0.5, skin))
    a = c + (tip - c) * 0.62
    parts.append(Part(lambda q: round_cone(q, a, tip + V(-0.04, 0, 0), 0.12, 0.03), master_metal(c, r, 6), 0.95, 0.02))
    return parts


def master_crown(c, r):
    """Coroa roxa enterrada até o meio do rosto: uma faixa larga da metade do rosto até perto do alto (a borda
    desce em V na frente), aberta em cima, com pontas e bolinhas douradas e gemas douradas na frente."""
    c = np.asarray(c, float)
    metal = master_metal(c, r, 2)

    def shell(q):
        rel = q - c
        front = smooth((rel[:, 0] / r - 0.3) / 0.7)
        edge = -0.02 - 0.1 * front * (1 - smooth(np.abs(rel[:, 2]) / (r * 0.6)))   # borda em V no meio do rosto
        d = np.maximum(np.abs(length(rel) - (r + 0.035)) - 0.035, edge - rel[:, 1])
        return np.maximum(d, rel[:, 1] - 0.27)          # aberta em cima: o alto da cabeça (preto) aparece
    parts = [Part(shell, metal, 0.9, 0.0)]
    rim_y = 0.24                                    # pontas da coroa em volta do alto
    rad = np.sqrt(r * r - rim_y ** 2) + 0.03
    for k, ang in enumerate(np.radians(np.arange(0, 360, 45))):
        out = V(np.cos(ang), 0, np.sin(ang))
        a = c + out * rad + V(0, rim_y, 0)
        h = 0.24 if k == 0 else 0.19
        b = a + norm(out * 0.25 + V(0, 1, 0)) * h
        parts.append(Part(lambda q, a=a, b=b: round_cone(q, a, b, 0.07, 0.018), metal, 0.9, 0.02))
        parts.append(Part(lambda q, b=b: sphere(q, b + V(0, 0.02, 0), 0.035), MASTER_GOLD, 0.95, 0.01))
    band = lambda q: np.maximum(np.abs(length((q - c) * V(1, 0, 1)) - (rad + 0.005)) - 0.03,
                                np.abs(q[:, 1] - c[1] - rim_y + 0.02) - 0.045)
    parts.append(Part(band, master_metal(c, r, 8), 0.95, 0.01))
    for ang in np.radians([0, 40, -40]):            # gemas douradas na frente da coroa
        out = V(np.cos(ang), 0, np.sin(ang))
        g = c + out * (r + 0.07) + V(0, 0.08, 0)
        size = 0.06 if ang == 0 else 0.04
        parts.append(Part(lambda q, g=g, s=size: (np.abs(q - g).sum(1) - s) * 0.57,
                          lambda q, g=g: mix(MASTER_GOLD, C('#fff2b0'), smooth((q[:, 1] - g[1]) / 0.03)), 1.0, 0.0))
    return parts


def master_head():
    """Cabeça da skin de mestre: preta, sem olhos nem boca, com a coroa roxa cobrindo metade do rosto."""
    c, r = HEAD_C, HEAD_R
    parts = [Part(lambda q: sphere(q, c, r), master_skin(c, r, 3), 0.75)]
    return parts + master_crown(c, r)


def armored_head(portrait=False):
    """Cabeça da cobra de ouro: preta, sem olhos, dentro do capacete de touro (o rosto aberto mostra só o preto).
    No jogo os chifres e os espetos são menores, para caberem no canvas dos objetos; no retrato, enormes."""
    c, r = HEAD_C, HEAD_R
    parts = [Part(lambda q: sphere(q, c, r), black_skin(c, r), 0.8)]
    return parts + taurus_helmet(c, r, 1.0 if portrait else 0.55, 1.0 if portrait else 0.55)


def armored_body(variant):
    """Bolinha do corpo: preta, com uma placa de armadura de ouro por cima."""
    c, r = SEG_C, SEG_R
    parts = [Part(lambda q: sphere(q, c, r), black_skin(c, r), 0.8)]
    parts += armor_plate(c, r, 0.55, seed=7 + variant, fin=variant == 0)
    parts += ring_rivets(c, r, r * 0.55 + 0.02, 7, 0.026, 0.2 + 0.4 * variant)
    return parts


def armored_tail():
    """Cauda preta com placa de ouro na bolinha e uma ponteira de ouro."""
    c, r, tip = V(0, 0.3, 0), 0.3, V(-0.62, 0.1, 0)
    skin = black_skin(c, r)
    parts = [Part(lambda q: sphere(q, c, r), skin, 0.8), Part(lambda q: round_cone(q, c, tip, 0.27, 0.05), skin, 0.8, 0.06)]
    parts += armor_plate(c, r, 0.55, seed=5, fin=False)
    parts += ring_rivets(c, r, r * 0.55 + 0.02, 6, 0.024)
    a = c + (tip - c) * 0.68
    parts.append(Part(lambda q: round_cone(q, a, tip + V(-0.03, 0, 0), 0.13, 0.06), gold_col(c, r, 6), 0.95, 0.02))
    return parts


def smoke_puffs(start, sizes, drift=V(-0.05, 0.15, 0.03)):
    """Bolinhas de fumaça subindo a partir de `start`."""
    parts, p = [], np.asarray(start, float)
    for i, r in enumerate(sizes):
        col = mix(C('#7d7876'), C('#c9c4c1'), i / max(len(sizes) - 1, 1))
        parts.append(Part(lambda q, p=p.copy(), r=r: sphere(q, p, r) + 0.012 * vnoise(q * 30), col, 0.1, 0.04))
        p = p + drift * (1 + i * 0.3)
    return parts


def snake_head(theme, portrait=False):
    if theme == 'skin_ouro':
        return armored_head(portrait)
    if theme == 'skin_esmeralda':
        return emerald_head()
    if theme == 'skin_diamante':
        return diamond_head()
    if theme == 'skin_mestre':
        return master_head()
    if theme == 'skin_platina':
        return platinum_head()
    if theme == 'coracao':                  # tema de luxo do pacote tema_coracao
        import tema_coracao
        return tema_coracao.snake_head()
    if theme == 'caixa':                    # cobra de caixinhas de presente
        import tema_caixa
        return tema_caixa.snake_head()
    p = PAL[theme]
    c, r = HEAD_C, HEAD_R
    base = body_color_fn(c, r, p['top'], p['belly'], p['spots'], seed=3, flowers=theme == 'rosa')
    if theme == 'queimado':
        base = burnt(base, 3)
    if theme == 'coracao':
        base = pearl(base)
    mt = METAL_SKINS.get(theme)
    if mt:
        base = metal(base, c, r, 3, mt['seam'])
    parts = []
    hfn = face_col(base, c, r)
    if theme == 'rosquinha':
        hfn = face_col(lambda q: mix(C('#e8973f'), C('#ffd59a'), np.clip(0.5 - (q[:, 1] - c[1]) * 2, 0, 1)), c, r)
    head_gloss = 0.9 if mt else {'rosquinha': 0.2, 'coracao': 0.95}.get(theme, 0.45)
    parts.append(Part(lambda q: sphere(q, c, r), hfn, head_gloss))
    if mt:                          # crista de metal e rebites
        parts.append(Part(lambda q: capsule(q, c + V(-0.32, r * 0.78, 0), c + V(0.12, r * 0.97, 0), 0.055),
                          mt['crest'], 0.9, 0.02))
        parts += rivets(c, r, 8, 0.036, 0.4, mt['rivet'])
    if theme == 'classico':
        A = [V(0.38, 0.3, 0), V(0.56, 0.29, 0), V(0.56, 0.29, 0)]
        B = [V(0.56, 0.29, 0), V(0.64, 0.31, 0.04), V(0.64, 0.31, -0.04)]
        parts.append(capsules_part(A, B, 0.022, [C('#ff4d6d')] * 3, 0.6))
    if theme == 'esquilo':                  # orelhinhas de esquilo e o tufo na testa
        for zs in (1, -1):
            ear = c + V(-0.12, r * 0.82, zs * r * 0.42)
            parts.append(Part(lambda q, ear=ear: round_cone(q, ear, ear + V(-0.04, 0.16, zs * 0.03), 0.09, 0.02),
                              lambda q: C('#d9792b') * (0.88 + 0.22 * fbm(q * 40, 2))[:, None], 0.15, 0.04))
            parts.append(Part(lambda q, ear=ear: round_cone(q, ear + V(0.04, 0.0, 0), ear + V(0.0, 0.12, zs * 0.02),
                                                            0.05, 0.012), C('#ffb59a'), 0.2, 0.01))
    if theme == 'coracao':                  # tiara de ouro com pérolas e um coração de cristal na frente
        gold = gold_col(c, r, 11)
        y = r * 0.62
        ring_r = np.sqrt(r * r - y * y) + 0.015
        parts.append(Part(lambda q: torus0((q - c - V(0, y, 0)) @ rot_axis(V(0, 0, 1), np.radians(-12)), ring_r, 0.03),
                          gold, 0.97, 0.01))
        for k, a in enumerate(np.radians([-150, -110, -70, 70, 110, 150])):         # pontas com pérolas
            base_p = c + V(np.cos(a) * ring_r * 0.95, y + 0.02, np.sin(a) * ring_r * 0.95)
            tip_p = base_p + V(0, 0.09 + 0.03 * (k in (2, 3)), 0)
            parts.append(Part(lambda q, a_=base_p, b_=tip_p: round_cone(q, a_, b_, 0.028, 0.012), gold, 0.97, 0.01))
            parts.append(Part(lambda q, p_=tip_p: sphere(q, p_, 0.03), C('#fff8fb'), 1.0, 0.004))
        parts += luxury_heart_gem(c + V(ring_r * 0.92, y + 0.1, 0), 0.55)
    if theme == 'rosa':
        parts += rose_parts(c + V(-0.05, r * 0.92, 0), 0.75)
        parts.append(leaf_part(c + V(-0.05, r * 0.95, 0.05), V(-0.3, 0.4, 1), 0.9))
        parts.append(leaf_part(c + V(-0.08, r * 0.95, -0.05), V(-0.5, 0.4, -1), 0.9))
    if theme == 'rosquinha':
        parts.append(frosting_cap(c, r, C('#ff8cc6'), C('#8fd8ff'), seed=1.0, low=0.1))
        parts.append(sprinkles_on_sphere(c, r + 0.03, 22, seed=11, max_polar=45))
    if theme == 'caracol':
        for zs in (1, -1):
            parts.append(Part(lambda q, zs=zs: capsule(q, c + V(0.1, 0.25, 0.12 * zs), c + V(0.22, 0.55, 0.2 * zs), 0.035), base, 0.5, 0.04))
            parts += eye_parts(c + V(0.24, 0.6, 0.21 * zs), 0.1, V(1, -0.15, 0.25 * zs), sleepy=C('#ffd43b'))
        return parts
    if theme == 'queimado':     # olhos arregalados, cabelinho chamuscado e fumaça
        parts += head_eyes(c, r, er=0.14, spread=0.45, up=0.5)
        A = [c + V(-0.05, r * 0.95, z) for z in (-0.08, 0.0, 0.08)]
        B = [a + V(-0.02 + 0.03 * k, 0.12, 0.02 * (k - 1)) for k, a in enumerate(A)]
        parts.append(capsules_part(A, B, 0.018, [C('#1a1616')] * 3, 0.2, 0.01))
        parts += smoke_puffs(c + V(-0.12, r + 0.2, 0), [0.1, 0.08, 0.065])
        return parts
    parts += head_eyes(c, r)
    return parts


def snake_body(theme, variant, direction=None):
    """direction: só nas skins de DIRECTIONAL_BODY (a barbatana aponta para trás do movimento)."""
    if theme == 'skin_esmeralda':
        return emerald_body(variant, direction)
    if theme == 'skin_diamante':
        return diamond_body(variant)
    if theme == 'skin_mestre':
        return master_body(variant, direction)
    if theme == 'skin_ouro':
        return armored_body(variant)
    if theme == 'skin_platina':
        return platinum_body(variant)
    if theme == 'coracao':
        import tema_coracao
        return tema_coracao.snake_body(theme, variant)
    if theme == 'caixa':
        import tema_caixa
        return tema_caixa.snake_body(theme, variant)
    p = PAL[theme]
    c, r = SEG_C, SEG_R
    base = body_color_fn(c, r, p['top'], p['belly'], p['spots'] if variant == 0 or theme == 'classico' else None, seed=7 + variant, flowers=theme == 'rosa')
    if theme == 'queimado':
        base = burnt(base, 7 + variant)
    if theme == 'coracao':
        base = pearl(base)
    mt = METAL_SKINS.get(theme)
    if mt:
        base = metal(base, c, r, 7 + variant, mt['seam'])
    parts = []
    if theme == 'rosquinha':
        dcol = lambda q: mix(C('#e8973f'), C('#ffd59a'), np.clip(0.5 - (q[:, 1] - c[1]) * 2, 0, 1))
        parts.append(Part(lambda q: sphere(q, c, r), dcol, 0.2))
        cols = [(C('#ff8cc6'), C('#ffb3d9')), (C('#8fd8ff'), C('#c7a6ff'))][variant]
        parts.append(frosting_cap(c, r, *cols, seed=2.0 + variant))
        parts.append(sprinkles_on_sphere(c, r + 0.03, 18, seed=20 + variant, max_polar=50))
        return parts
    parts.append(Part(lambda q: sphere(q, c, r), base, 0.9 if mt else {'esquilo': 0.25, 'coracao': 0.95}.get(theme, 0.45)))
    if mt:
        parts += rivets(c, r, 8, 0.032, 0.2 + 0.4 * variant, mt['rivet'])
    top = c + V(0, r, 0)
    if theme == 'rosa':
        if variant == 0:
            parts += rose_parts(top + V(0, -0.02, 0), 0.7, rings=3)
            parts.append(leaf_part(top + V(0, 0.0, 0.03), V(0.6, 0.35, 1), 0.85))
            parts.append(leaf_part(top + V(0, 0.0, -0.03), V(-0.6, 0.35, -1), 0.85))
        else:
            for ang in (0.4, 2.5, 4.4):
                parts.append(leaf_part(top + V(0, -0.02, 0), V(np.cos(ang), 0.55, np.sin(ang)), 0.85))
            parts += rose_parts(top + V(0, 0.03, 0), 0.42, rings=1, calyx=False)
    if theme == 'esquilo':                  # bolota nas costas (ou uma folha de outono)
        if variant == 0:
            parts += acorn_parts(top + V(0, 0.06, 0), 1.3)
        else:
            parts.append(leaf_part(top + V(0, -0.01, 0), V(0.6, 0.35, 0.8), 1.0, col=C('#e0601f'), col2=C('#ffb340')))
    if theme == 'coracao':                  # faixa de ouro cravejada e, no alto, coração de cristal ou pérola
        gold = gold_col(c, r, 13 + variant)
        parts.append(gold_ring(c, r + 0.005, 0.034, gold))
        for k in range(8):
            a = 2 * np.pi * k / 8 + 0.2 + variant * 0.4
            parts.append(gem(c + V(np.cos(a) * (r + 0.035), 0.0, np.sin(a) * (r + 0.035)), 0.026))
        if variant == 0:
            parts += luxury_heart_gem(top + V(0, 0.02, 0), 0.6)
        else:
            parts.append(Part(lambda q: ellipsoid(q, top + V(0, -0.01, 0), V(0.09, 0.03, 0.09)), gold, 0.97, 0.01))
            parts.append(Part(lambda q: sphere(q, top + V(0, 0.06, 0), 0.075),
                              lambda q: mix(C('#fff6fb'), holo_col(q, 2.0), 0.18), 1.0, 0.004))
    if theme == 'queimado' and variant == 0:
        parts += smoke_puffs(top + V(0, 0.08, 0), [0.07, 0.055])
    if theme == 'caracol':
        M = np.stack([R, Y, np.cross(R, Y)], 1)
        M[:, 2] = -norm(np.cross(M[:, 0], M[:, 1]))
        Mf = np.stack([R, Y, CAM_H], 1)
        cols = [(C('#ff4fd8'), C('#a24cff'), C('#4d6bff')), (C('#5cf0ff'), C('#4d8bff'), C('#a24cff'))][variant]
        parts.append(swirl_shell(c + V(0, r + 0.12, 0), 0.24, 0.16, Mf, *cols))
    return parts


def snake_tail(theme):
    if theme == 'skin_esmeralda':
        return emerald_tail()
    if theme == 'skin_diamante':
        return diamond_tail()
    if theme == 'skin_mestre':
        return master_tail()
    if theme == 'skin_ouro':
        return armored_tail()
    if theme == 'skin_platina':
        return platinum_tail()
    if theme == 'coracao':
        import tema_coracao
        return tema_coracao.snake_tail()
    if theme == 'caixa':
        import tema_caixa
        return tema_caixa.snake_tail()
    p = PAL[theme]
    c = V(0, 0.3, 0)
    tip = V(-0.62, 0.1, 0)
    base = body_color_fn(SEG_C, SEG_R, p['top'], p['belly'], p['spots'], seed=5, flowers=theme == 'rosa')
    if theme == 'queimado':
        base = burnt(base, 5)
    if theme == 'coracao':
        base = pearl(base)
    mt = METAL_SKINS.get(theme)
    if mt:
        base = metal(base, c, 0.3, 5, mt['seam'])
    if theme == 'rosquinha':
        base = lambda q: mix(C('#e8973f'), C('#ffd59a'), np.clip(0.5 - (q[:, 1] - c[1]) * 2, 0, 1))
    tail_gloss = 0.9 if mt else (0.95 if theme == 'coracao' else 0.4)
    parts = [Part(lambda q: sphere(q, c, 0.3), base, tail_gloss),
             Part(lambda q: round_cone(q, c, tip, 0.27, 0.05), base, tail_gloss, 0.06)]
    if mt:
        parts += rivets(c, 0.3, 6, 0.03, col=mt['rivet'])
    if theme == 'rosa':
        parts.append(leaf_part(tip + V(0.02, 0.0, 0), V(-1, 0.6, 0.2), 1.1))
        parts += rose_parts(V(-0.05, 0.6, 0), 0.4, rings=2, calyx=False)
    if theme == 'rosquinha':
        parts.append(frosting_cap(c, 0.3, C('#ff8cc6'), C('#8fd8ff'), seed=3.0, low=0.05))
        parts.append(sprinkles_on_sphere(c, 0.33, 10, seed=31, max_polar=40))
    if theme == 'esquilo':                  # tufo de rabo de esquilo na ponta
        for p, r in [(V(-0.5, 0.18, 0), 0.11), (V(-0.62, 0.3, 0), 0.12), (V(-0.66, 0.45, 0), 0.1)]:
            parts.append(Part(lambda q, p=p, r=r: sphere(q, p, r) + 0.012 * vnoise(q * 30),
                              lambda q: mix(C('#d9792b'), C('#f8e4c4'), smooth((q[:, 1] - 0.35) / 0.15))
                              * (0.88 + 0.22 * fbm(q * 40, 2))[:, None], 0.12, 0.05))
    if theme == 'coracao':                  # faixa de ouro, ponteira de ouro e um coração de cristal na ponta
        gold = gold_col(c, 0.3, 17)
        parts.append(gold_ring(c, 0.305, 0.03, gold))
        a = c + (tip - c) * 0.7
        parts.append(Part(lambda q: round_cone(q, a, tip + V(-0.02, 0, 0), 0.115, 0.055), gold, 0.97, 0.02))
        parts += luxury_heart_gem(tip + V(-0.04, 0.08, 0), 0.5)
    if theme == 'caracol':
        parts.append(Part(lambda q: ellipsoid(q, V(-0.35, 0.02, 0), V(0.36, 0.018, 0.2)), C('#c9f0ff'), 1.0))
    if theme == 'queimado':
        parts += smoke_puffs(tip + V(0.02, 0.1, 0), [0.06, 0.045])
    return parts


# ================================================================= TILES
TILE_PAL = {
    'classico': (C('#7fd44a'), C('#6cc23e'), C('#a0734a'), 'grass'),
    'rosa': (C('#ffa9c4'), C('#ff95b5'), C('#b5745f'), 'flowers'),
    'rosquinha': (C('#ffb8de'), C('#a9ddff'), C('#f6c27f'), 'sprinkles'),
    'esquilo': (C('#8cc05a'), C('#7cb04c'), C('#7a5232'), 'forest'),
    'coracao': (C('#fbf2f6'), C('#f4e6ef'), C('#e9cfdd'), 'marble'),     # mármore com veios de ouro
    'caracol': (C('#86cfa0'), C('#74c094'), C('#8b93a3'), 'rain'),
    'queimado': (C('#5c5552'), C('#4f4845'), C('#2c2826'), 'ash'),
}


def cracks(q, scale, seed, width):
    """Rachaduras no chão (plano xz): 1 perto da fronteira entre células de Voronoi.

    Devolve (rachadura, borda escura em volta da rachadura).
    """
    p = np.stack([q[:, 0], q[:, 2]], 1) * scale + seed
    cell = np.floor(p)
    f1 = np.full(len(p), 9.0)
    f2 = np.full(len(p), 9.0)
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            c = cell + np.array([dx, dz])
            c3 = np.stack([c[:, 0], np.zeros(len(c)), c[:, 1]], 1)
            pt = c + 0.1 + 0.8 * np.stack([_hash(c3), _hash(c3 + 17.3)], 1)
            d = length(p - pt)
            f2 = np.where(d < f1, f1, np.minimum(f2, d))
            f1 = np.minimum(f1, d)
    gap = f2 - f1
    return smooth((width - gap) / (width * 0.5)), smooth((width * 3.5 - gap) / (width * 2.5))


def tile(theme, variant):
    if theme == 'coracao':
        import tema_coracao
        return tema_coracao.tile(theme, variant)
    if theme == 'caixa':
        import tema_caixa
        return tema_caixa.tile(theme, variant)
    ca, cb, side, kind = TILE_PAL[theme]
    top = [ca, cb][variant]
    seed = 13 * variant + THEMES.index(theme)

    def col(q):
        out = np.broadcast_to(top, (len(q), 3)).copy()
        n = fbm(q * 6 + seed, 3)
        out *= (0.93 + 0.12 * n)[:, None]
        cell = np.floor(q * 5 + seed * 0.37)
        f = q * 5 + seed * 0.37 - cell
        hsh = _hash(cell * V(1, 0, 1))
        d = np.sqrt((f[:, 0] - 0.5) ** 2 + (f[:, 2] - 0.5) ** 2)
        if kind == 'grass' or kind == 'jungle':
            blade = smooth((fbm(q * V(22, 1, 22) + seed, 2) - 0.6) / 0.08)
            out = mix(out, top * (1.18 if kind == 'grass' else 0.78), blade * 0.7)
            if kind == 'jungle':
                peb = (hsh > 0.88) * smooth((0.22 - d) / 0.05)
                out = mix(out, C('#c9b28f'), peb)
        if kind == 'cracked':
            out = mix(out, C('#cf9a62'), smooth((fbm(q * 4 + seed * 3, 3) - 0.55) / 0.15) * 0.45)    # manchas de poeira
            big, rim = cracks(q, 2.6, seed * 1.7, 0.05)
            small, _ = cracks(q, 6.5, seed * 2.3 + 5, 0.035)
            out *= (1 - 0.22 * rim)[:, None]                                # borda escurecida
            out = mix(out, C('#3e2414'), np.maximum(big, small * 0.8))
            glow = big * smooth((fbm(q * 2.2 + seed, 2) - 0.5) / 0.08)      # lava em parte das rachaduras grandes
            out = mix(out, C('#ff6a1a'), glow * 0.9)
            out = mix(out, C('#ffc23a'), glow * smooth((0.02 - (1 - big)) / 0.02) * 0.6)
            peb = (hsh > 0.9) * smooth((0.16 - d) / 0.05)
            out = mix(out, C('#8d6a52'), peb)
        if kind == 'forest':                # folhas de outono caídas e bolotinhas
            blade = smooth((fbm(q * V(22, 1, 22) + seed, 2) - 0.6) / 0.08)
            out = mix(out, top * 1.15, blade * 0.6)
            leaf = (hsh > 0.45) * smooth((0.24 - np.abs(f[:, 0] - 0.5) * 1.4 - np.abs(f[:, 2] - 0.5) * 0.7) / 0.04)
            lc = np.where((hsh > 0.85)[:, None], C('#ffb340'), np.where((hsh > 0.74)[:, None], C('#e0601f'), C('#c8412a')))
            out = mix(out, lc, leaf)
            nut = (_hash(cell * V(1, 0, 1) + 7) > 0.93) * smooth((0.1 - d) / 0.03)
            out = mix(out, C('#8a5a2e'), nut)
        if kind == 'marble':                # mármore claro com veios cinza-rosados e de ouro
            n1 = fbm(q * V(3, 1, 3) + seed, 3)
            vein = smooth((0.035 - np.abs(np.sin((q[:, 0] * 2.2 + q[:, 2] * 1.3 + n1 * 3.5) * 3.0)) * 0.12) / 0.02)
            out = mix(out, C('#d9c3cf'), vein * 0.55)
            n2 = fbm(q * V(2, 1, 2) + seed + 11, 3)
            gold_v = smooth((0.014 - np.abs(n2 - 0.5)) / 0.007)              # veio fino de ouro
            out = mix(out, C('#e4b23c'), gold_v * 0.95)
            out = mix(out, C('#fff9e6'), gold_v * smooth((q[:, 0] + q[:, 2]) * 3 % 1 - 0.7) * 0.4)
        if kind == 'holo':                  # chão furta-cor com coraçõezinhos
            out = mix(out, holo_col(q, 0.6), 0.5)
            hx = (f[:, 0] - 0.5) * 2.4
            hz = (f[:, 2] - 0.55) * 2.4
            heart = (hx ** 2 + hz ** 2 - 0.3) ** 3 - hx ** 2 * (-hz) ** 3        # curva do coração no plano
            on = (hsh > 0.55) * smooth(-heart / 0.02)
            out = mix(out, np.where((hsh > 0.86)[:, None], C('#ff7ac6'), C('#ffffff')), on * 0.85)
        if kind == 'ash':
            soot = smooth((fbm(q * 3 + seed * 2, 3) - 0.5) / 0.12)
            out = mix(out, C('#2b2725'), soot * 0.6)                       # manchas de fuligem
            out = mix(out, C('#9a938f'), smooth((fbm(q * 11 + seed, 2) - 0.62) / 0.06) * 0.5)   # cinza clara
            crack, rim = cracks(q, 3.0, seed * 1.3 + 9, 0.035)
            out = mix(out, C('#1c1918'), crack * 0.8)
            glow = crack * smooth((fbm(q * 2.5 + seed + 4, 2) - 0.55) / 0.08)
            out = mix(out, C('#ff5a14'), glow)
            ember = (hsh > 0.86) * smooth((0.1 - d) / 0.05)               # brasinhas soltas
            out = mix(out, mix(C('#ff6a1a'), C('#ffd23a'), smooth((0.05 - d) / 0.03)), ember)
        if kind == 'flowers':
            fl = (hsh > 0.72) * smooth((0.2 - d) / 0.05)
            ctr = (hsh > 0.72) * smooth((0.08 - d) / 0.03)
            pc = np.where((hsh > 0.86)[:, None], C('#ffffff'), C('#ff6f97'))
            out = mix(mix(out, pc, fl), C('#ffd84d'), ctr)
        if kind == 'sprinkles':
            ang = hsh * 6.283
            dirv = np.stack([np.cos(ang), np.sin(ang)], 1)
            rel = np.stack([f[:, 0] - 0.5, f[:, 2] - 0.5], 1)
            along = (rel * dirv).sum(1)
            perp = rel[:, 0] * dirv[:, 1] - rel[:, 1] * dirv[:, 0]
            spr = (hsh > 0.45) * smooth((0.06 - np.abs(perp)) / 0.02) * smooth((0.2 - np.abs(along)) / 0.03)
            idx = (hsh * 97).astype(int) % len(SPRINKLE_COLS)
            out = mix(out, np.array(SPRINKLE_COLS)[idx], spr)
        if kind == 'rain':
            pud = smooth((fbm(q * 3.0 + seed * 2, 3) - 0.6) / 0.04)
            out = mix(out, C('#b7c8ff'), pud * 0.85)
            drop = (hsh > 0.8) * smooth((0.12 - d) / 0.04)
            out = mix(out, C('#ecfbff'), drop * 0.8)
        sidec = side * (0.9 + 0.15 * fbm(q * 10, 2))[:, None]
        if kind == 'marble':                # filete de ouro na borda de cima
            sidec = mix(sidec, C('#e4b23c'), np.exp(-((q[:, 1] + 0.05) / 0.012) ** 2))
        if kind == 'sprinkles':
            jam = np.exp(-((q[:, 1] + 0.16) / 0.03) ** 2)
            sidec = mix(sidec, C('#ff6f97'), jam)
            sidec = mix(sidec, C('#fff3e0'), smooth((q[:, 1] + 0.07) / 0.03))
        return mix(sidec, out, smooth((q[:, 1] + 0.035) / 0.02))
    gl = {'sprinkles': 0.55, 'rain': 0.35, 'holo': 0.6, 'marble': 0.8}.get(kind, 0.12)
    return Scene([Part(lambda q: rbox(q, V(0, -0.15, 0), V(0.5, 0.15, 0.5), 0.035), col, gl)])


# ================================================================= PROPS
def prop(theme, i):
    if theme == 'coracao':
        import tema_coracao
        return tema_coracao.prop(theme, i)
    if theme == 'caixa':
        import tema_caixa
        return tema_caixa.prop(theme, i)
    parts = []
    if theme == 'classico':
        if i == 0:   # arbusto
            g = C('#4fb84a')
            for c, r in [(V(0, 0.28, 0), 0.3), (V(0.2, 0.22, 0.12), 0.22), (V(-0.18, 0.2, -0.1), 0.22), (V(0.02, 0.5, -0.02), 0.2)]:
                parts.append(Part(lambda q, c=c, r=r: sphere(q, c, r) + 0.015 * vnoise(q * 25), lambda q: g * (0.85 + 0.3 * vnoise(q * 9))[:, None], 0.15, 0.08))
            for c in [V(0.2, 0.5, 0.15), V(-0.1, 0.62, 0.12), V(0.3, 0.3, 0.3)]:
                parts.append(Part(lambda q, c=c: sphere(q, c, 0.05), C('#ff5d5d'), 0.7))
        else:        # pedra
            parts.append(Part(lambda q: ellipsoid(q, V(0, 0.16, 0), V(0.32, 0.2, 0.26)) + 0.02 * vnoise(q * 8), lambda q: C('#a7adb8') * (0.85 + 0.3 * fbm(q * 9, 2))[:, None], 0.2))
            parts.append(Part(lambda q: ellipsoid(q, V(0.25, 0.08, 0.2), V(0.14, 0.1, 0.12)), C('#9aa1ad'), 0.2, 0.02))
            parts.append(Part(lambda q: ellipsoid(q, V(-0.05, 0.3, 0.0), V(0.2, 0.06, 0.18)), C('#7dcf5a'), 0.1, 0.03))
    elif theme == 'rosa':
        if i == 0:   # roseira
            g = C('#3fa046')
            for c, r in [(V(0, 0.3, 0), 0.32), (V(0.2, 0.22, 0.15), 0.22), (V(-0.2, 0.22, -0.1), 0.22)]:
                parts.append(Part(lambda q, c=c, r=r: sphere(q, c, r) + 0.015 * vnoise(q * 25), lambda q: g * (0.85 + 0.3 * vnoise(q * 9))[:, None], 0.15, 0.08))
            for c, s in [(V(0.05, 0.6, 0.05), 0.75), (V(0.25, 0.42, 0.25), 0.6), (V(-0.22, 0.42, 0.12), 0.6)]:
                parts += rose_parts(c, s, rings=2, calyx=False)
        else:        # vaso com rosa
            parts.append(Part(lambda q: round_cone(q, V(0, 0.02, 0), V(0, 0.32, 0), 0.17, 0.24), lambda q: mix(C('#e07a4f'), C('#f29b6b'), np.clip(q[:, 1] * 3, 0, 1)), 0.3))
            parts.append(Part(lambda q: torus0(q - V(0, 0.36, 0), 0.24, 0.045), C('#f2a27a'), 0.3, 0.02))
            parts.append(Part(lambda q: ellipsoid(q, V(0, 0.37, 0), V(0.21, 0.03, 0.21)), C('#6b4430'), 0.1))
            parts.append(Part(lambda q: capsule(q, V(0, 0.37, 0), V(0, 0.75, 0), 0.025), C('#3d9b3a'), 0.3))
            parts.append(leaf_part(V(0, 0.5, 0), V(0.8, 0.5, 0.3), 1.0))
            parts.append(leaf_part(V(0, 0.58, 0), V(-0.8, 0.5, -0.2), 0.9))
            parts += rose_parts(V(0, 0.8, 0), 1.0)
    elif theme == 'rosquinha':
        if i == 0:   # cupcake
            def wrap(q):
                a = np.arctan2(q[:, 2], q[:, 0])
                return mix(C('#ff9cc9'), C('#ffffff'), (np.sin(a * 14) > 0).astype(float) * 0.7)
            parts.append(Part(lambda q: round_cone(q, V(0, 0.0, 0), V(0, 0.28, 0), 0.19, 0.26) + 0.006 * np.sin(np.arctan2(q[:, 2], q[:, 0]) * 14), wrap, 0.3))
            for y, r, rr in [(0.36, 0.22, 0.09), (0.47, 0.15, 0.08), (0.56, 0.08, 0.07)]:
                parts.append(Part(lambda q, y=y, r=r, rr=rr: torus0(q - V(0, y, 0), r, rr), C('#bfe6ff'), 0.85, 0.04))
            parts.append(Part(lambda q: sphere(q, V(0, 0.68, 0), 0.075), C('#ff2f5f'), 0.95, 0.01))
            parts.append(sprinkles_on_sphere(V(0, 0.36, 0), 0.27, 16, seed=4, max_polar=70))
        else:        # pirulito
            Mf = np.stack([R, Y, CAM_H], 1)
            parts.append(Part(lambda q: capsule(q, V(0, 0.0, 0), V(0, 0.62, 0), 0.025), V(1, 1, 1), 0.4))
            parts.append(swirl_shell(V(0, 0.82, 0), 0.24, 0.06, Mf, C('#ff5c9e'), C('#ffe066'), C('#5cc8ff'), turns=3.0))
            parts.append(Part(lambda q: ellipsoid(q, V(0, 0.03, 0), V(0.1, 0.025, 0.1)), C('#ffffff'), 0.3))
    elif theme == 'esquilo':
        if i == 0:   # árvore de outono: tronco e copa laranja
            bark = lambda q: C('#7a4a28') * (0.85 + 0.3 * fbm(q * V(6, 30, 6), 2))[:, None]
            parts.append(Part(lambda q: round_cone(q, V(0, 0.0, 0), V(0, 0.55, 0), 0.11, 0.07), bark, 0.2))
            for c, r, col in [(V(0, 0.72, 0), 0.3, C('#e0702a')), (V(0.2, 0.62, 0.12), 0.2, C('#f29a33')),
                              (V(-0.18, 0.64, -0.08), 0.21, C('#d14f22')), (V(0.02, 0.92, 0.02), 0.18, C('#f6b440'))]:
                parts.append(Part(lambda q, c=c, r=r: sphere(q, c, r) + 0.02 * vnoise(q * 18),
                                  lambda q, col=col: col * (0.85 + 0.3 * vnoise(q * 9))[:, None], 0.15, 0.08))
        else:        # toco com cogumelos e bolotas
            ring = lambda q: mix(C('#c99a62'), C('#e2bd85'), (np.sin(length(q * V(1, 0, 1)) * 60) + 1) / 2)
            parts.append(Part(lambda q: np.maximum(capsule(q, V(0, 0.0, 0), V(0, 0.3, 0), 0.24), q[:, 1] - 0.3),
                              lambda q: C('#7a4a28') * (0.85 + 0.3 * fbm(q * V(6, 30, 6), 2))[:, None], 0.2))
            parts.append(Part(lambda q: np.maximum(np.abs(q[:, 1] - 0.3) - 0.01, length(q * V(1, 0, 1)) - 0.22), ring, 0.3))
            parts += acorn_parts(V(0.05, 0.38, 0.02), 1.3)
            parts += acorn_parts(V(0.3, 0.06, 0.18), 1.1, 0.5)
            parts += acorn_parts(V(-0.28, 0.05, 0.2), 1.0, -0.6)
    elif theme == 'coracao':
        gold = gold_col(V(0, 0.3, 0), 0.4, 21 + i)
        if i == 0:   # coração de cristal num pedestal de ouro (coluna canelada sobre base de mármore)
            parts.append(Part(lambda q: rbox(q, V(0, 0.04, 0), V(0.2, 0.04, 0.2), 0.015), C('#f6ecf2'), 0.8))
            fluted = lambda q: np.maximum(length(q * V(1, 0, 1)) - 0.1 - 0.008 * np.cos(np.arctan2(q[:, 2], q[:, 0]) * 12),
                                          np.abs(q[:, 1] - 0.22) - 0.15)
            parts.append(Part(fluted, bright_gold, 0.97, 0.01))
            parts.append(Part(lambda q: rbox(q, V(0, 0.38, 0), V(0.14, 0.025, 0.14), 0.012), bright_gold, 0.97, 0.01))
            parts.append(Part(lambda q: heart_sdf(q, V(0, 0.6, 0), 0.95), glass_heart_col(V(0, 0.6, 0), 0.95), 1.0))
        else:        # pilha de moedas de ouro com pérolas e um brilhante
            coins = [(V(0, 0.02, 0), 0), (V(0.01, 0.06, 0.0), 1), (V(-0.01, 0.1, 0.01), 2), (V(0.0, 0.14, -0.01), 3),
                     (V(0.2, 0.02, 0.12), 4), (V(0.21, 0.06, 0.1), 5), (V(-0.2, 0.02, 0.1), 6)]
            for c0, k in coins:
                parts.append(Part(lambda q, c0=c0: np.maximum(length((q - c0) * V(1, 0, 1)) - 0.12,
                                                              np.abs(q[:, 1] - c0[1]) - 0.018) - 0.006,
                                  bright_gold, 0.97))
            for p_ in (V(-0.12, 0.05, -0.16), V(0.14, 0.04, -0.14), V(-0.3, 0.04, -0.05)):
                parts.append(Part(lambda q, p_=p_: sphere(q, p_, 0.045), C('#fff6fb'), 1.0, 0.004))
            parts.append(gem(V(0, 0.2, 0), 0.05))
    elif theme == 'caracol':
        if i == 0:   # cogumelo
            def cap(q):
                cell = np.floor(q * 11)
                f = q * 11 - cell
                d = length(f - 0.5)
                dot = (_hash(cell) > 0.55) * smooth((0.32 - d) / 0.05)
                return mix(C('#ff4d4d'), C('#ffffff'), dot)
            parts.append(Part(lambda q: round_cone(q, V(0, 0.0, 0), V(0, 0.32, 0), 0.1, 0.075), C('#fff4e6'), 0.3))
            parts.append(Part(lambda q: np.maximum(ellipsoid(q, V(0, 0.36, 0), V(0.33, 0.25, 0.33)), 0.34 - q[:, 1]), cap, 0.6, 0.02))
            parts.append(Part(lambda q: ellipsoid(q, V(0, 0.35, 0), V(0.31, 0.02, 0.31)), C('#f7e3cc'), 0.2))
        else:        # ampulheta (câmera lenta)
            wood = C('#b07a4a')
            parts.append(Part(lambda q: rbox(q, V(0, 0.03, 0), V(0.24, 0.03, 0.24), 0.02), wood, 0.3))
            parts.append(Part(lambda q: rbox(q, V(0, 0.79, 0), V(0.24, 0.03, 0.24), 0.02), wood, 0.3))
            for x, z in [(0.19, 0.19), (-0.19, 0.19), (0.19, -0.19), (-0.19, -0.19)]:
                parts.append(Part(lambda q, x=x, z=z: capsule(q, V(x, 0.05, z), V(x, 0.77, z), 0.022), wood * 0.9, 0.3))
            glass = lambda q: np.minimum(round_cone(q, V(0, 0.07, 0), V(0, 0.41, 0), 0.15, 0.03), round_cone(q, V(0, 0.75, 0), V(0, 0.41, 0), 0.15, 0.03))
            parts.append(Part(glass, lambda q: mix(C('#cfefff'), C('#ffe08a'), smooth((0.25 - q[:, 1]) / 0.03) + smooth((q[:, 1] - 0.62) / 0.02)), 0.95))
    elif theme == 'queimado':
        def charcoal(q):
            ang = np.arctan2(q[:, 2], q[:, 0])
            bark = smooth((np.sin(ang * 9 + 3 * vnoise(q * 6)) - 0.6) / 0.2)     # rachaduras verticais do carvão
            hot = bark * smooth((fbm(q * 4, 2) - 0.5) / 0.1)
            return mix(mix(C('#2a2523'), C('#121010'), bark[:, None]), C('#ff5a14'), hot[:, None])
        if i == 0:   # tronco queimado soltando fumaça
            parts.append(Part(lambda q: round_cone(q, V(0, 0.0, 0), V(0, 0.5, 0), 0.2, 0.15) + 0.01 * vnoise(q * 18), charcoal, 0.15))
            parts.append(Part(lambda q: ellipsoid(q, V(0, 0.52, 0), V(0.14, 0.025, 0.14)), C('#6b4a33'), 0.1, 0.02))
            for a, b in [(V(0.05, 0.38, 0), V(0.28, 0.55, 0.05)), (V(-0.05, 0.3, 0.02), V(-0.24, 0.42, -0.06))]:
                parts.append(Part(lambda q, a=a, b=b: capsule(q, a, b, 0.045), charcoal, 0.15, 0.03))
            parts += smoke_puffs(V(0.02, 0.66, 0), [0.1, 0.085, 0.07])
        else:        # brasas com foguinho
            for c, rad in [(V(-0.16, 0.1, 0.06), V(0.22, 0.13, 0.18)), (V(0.18, 0.09, -0.08), V(0.18, 0.11, 0.16)),
                           (V(0.06, 0.08, 0.26), V(0.13, 0.08, 0.12))]:
                parts.append(Part(lambda q, c=c, rad=rad: ellipsoid(q, c, rad) + 0.01 * vnoise(q * 20), charcoal, 0.15, 0.03))
            for c, h, w in [(V(0.0, 0.12, 0.0), 0.5, 0.15), (V(0.14, 0.1, 0.08), 0.32, 0.09), (V(-0.13, 0.1, -0.04), 0.26, 0.07)]:
                parts.append(Part(lambda q, c=c, h=h, w=w: round_cone(q, c, c + V(0, h, 0), w, 0.01),
                                  lambda q, c=c, h=h: mix(C('#ff4d14'), C('#ffe066'), smooth((q[:, 1] - c[1]) / h * 1.2 - 0.1)[:, None]),
                                  0.5, 0.02))
    return Scene(parts)
