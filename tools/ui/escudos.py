"""Escudos de elo em estilo chapado (flat) com dois tons. Gera assets/ui/escudos/*.png

Progressão de imponência:
  ferro     escudo simples
  bronze    + borda e rebites
  prata     + topo recortado, borda dupla, emblema com divisa
  ouro      + chifres de touro e estrela
  platina   + asas maiores, gema, 3 pontas no topo
  esmeralda + asas grandes, coroa de 3 pontas, gema grande
  diamante  + asas enormes, coroa com gemas, raios atrás
  mestre    + asas douradas máximas, coroa grande, auréola, fita
"""
import os, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'assets', 'ui', 'escudos')
S = 256          # tamanho final
K = 4            # supersampling
N = S * K
CX, CY = N / 2, N * 0.56

TIERS = {
    #            claro       base        escuro      borda       emblema
    'ferro':     ('#c3c8d0', '#9aa1ad', '#7c8390', None,       '#e9ecf1'),
    'bronze':    ('#f2b27a', '#d48a4e', '#a9632f', '#8a4c22',  '#ffe1c4'),
    'prata':     ('#eef2f7', '#c9d1dc', '#a3adbb', '#7f8a99',  '#ffffff'),
    'ouro':      ('#ffe27a', '#f5bf2e', '#d29312', '#a86f05',  '#fff6cf'),
    'platina':   ('#c9fbf2', '#7fe0d0', '#45b5a6', '#2a8a7e',  '#ffffff'),
    'esmeralda': ('#8ff0a8', '#2fca6a', '#16994a', '#0b6d33',  '#d9ffe5'),
    'diamante':  ('#d6efff', '#8fcfff', '#4fa6f0', '#2f78c9',  '#ffffff'),
    'mestre':    ('#d7a6ff', '#a45cf2', '#7330c8', '#4b1690',  '#ffe27a'),
}
GOLD = ('#ffe27a', '#f5bf2e', '#d29312')


def hx(h, a=255):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def shade(h, f):
    r, g, b, a = hx(h)
    return (int(min(255, r * f)), int(min(255, g * f)), int(min(255, b * f)), a)


# ---------------------------------------------------------------- geometria
def bez(p0, p1, p2, n=24):
    t = np.linspace(0, 1, n)[:, None]
    return ((1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t ** 2 * p2).tolist()


def shield_pts(w, h, top_style='flat', cx=CX, cy=CY):
    """Contorno do escudo centrado em (cx, cy). w = meia largura, h = altura total."""
    top = cy - h * 0.48
    mid = cy + h * 0.05
    bot = cy + h * 0.52
    P = []
    if top_style == 'flat':
        P += [(cx - w, top + w * 0.08), (cx - w * 0.6, top), (cx + w * 0.6, top), (cx + w, top + w * 0.08)]
    elif top_style == 'notch':        # recorte no meio
        P += [(cx - w, top), (cx - w * 0.35, top), (cx, top + w * 0.16), (cx + w * 0.35, top), (cx + w, top)]
    elif top_style == 'peaks':        # 3 pontas
        P += [(cx - w, top + w * 0.05), (cx - w * 0.72, top - w * 0.12), (cx - w * 0.4, top + w * 0.06),
              (cx, top - w * 0.2), (cx + w * 0.4, top + w * 0.06), (cx + w * 0.72, top - w * 0.12), (cx + w, top + w * 0.05)]
    elif top_style == 'arch':         # arco elegante
        P += bez(np.array([cx - w, top + w * 0.1]), np.array([cx, top - w * 0.35]), np.array([cx + w, top + w * 0.1]), 30)
    P += [(cx + w, mid)]
    P += bez(np.array([cx + w, mid]), np.array([cx + w * 0.92, bot - h * 0.12]), np.array([cx, bot]), 28)[1:]
    P += bez(np.array([cx, bot]), np.array([cx - w * 0.92, bot - h * 0.12]), np.array([cx - w, mid]), 28)[1:]
    return [tuple(map(float, p)) for p in P]


def scale_pts(P, s, cx=CX, cy=CY):
    return [(cx + (x - cx) * s, cy + (y - cy) * s) for x, y in P]


def two_tone(img, P, light, dark, split_x=CX):
    """Preenche o polígono com tom claro à esquerda e escuro à direita (estilo flat)."""
    m = Image.new('L', img.size, 0); ImageDraw.Draw(m).polygon(P, fill=255)
    lay = Image.new('RGBA', img.size, light)
    img.paste(lay, (0, 0), m)
    half = Image.new('L', img.size, 0); ImageDraw.Draw(half).rectangle((split_x, 0, img.size[0], img.size[1]), fill=255)
    hm = Image.fromarray(np.minimum(np.array(m), np.array(half)))
    img.paste(Image.new('RGBA', img.size, dark), (0, 0), hm)


def poly(img, P, col):
    ImageDraw.Draw(img).polygon(P, fill=col)


def rot_pts(P, ang, c):
    ca, sa = math.cos(ang), math.sin(ang)
    return [(c[0] + (x - c[0]) * ca - (y - c[1]) * sa, c[1] + (x - c[0]) * sa + (y - c[1]) * ca) for x, y in P]


def ellipse_pts(c, rx, ry, ang, n=40):
    P = [(c[0] + rx * math.cos(t), c[1] + ry * math.sin(t)) for t in np.linspace(0, 2 * math.pi, n, endpoint=False)]
    return rot_pts(P, ang, c)


def feather(c, length, width, ang):
    """Pena: gota alongada apontando na direção ang."""
    P = []
    for t in np.linspace(0, math.pi, 30):
        r = width * math.sin(t) * (1 - 0.35 * (t / math.pi))
        P.append((c[0] + length * (1 - math.cos(t)) / 2, c[1] + r))
    for t in np.linspace(math.pi, 0, 30):
        r = width * math.sin(t) * (1 - 0.35 * (t / math.pi))
        P.append((c[0] + length * (1 - math.cos(t)) / 2, c[1] - r * 0.6))
    return rot_pts(P, ang, c)


def wings(img, n, length, width, spread, base_y, inner_x, cols, rise=0.0):
    """Asas dos dois lados: n penas abrindo em leque."""
    light, mid, dark = cols
    for side in (-1, 1):
        for i in range(n):
            t = i / max(1, n - 1)
            ang = math.radians(-spread / 2 + spread * t - rise)          # de cima pra baixo
            L = length * (1 - 0.38 * t)
            c = (CX + side * inner_x, base_y + t * width * 1.6)
            a = ang if side == 1 else math.pi - ang
            col = [light, mid, dark][min(2, int(t * 3))]
            P = feather(c, L, width, a if side == 1 else a)
            if side == -1:
                P = feather(c, L, width, math.pi + math.radians(spread / 2 - spread * t + rise))
                P = [(x, y) for x, y in P]
            poly(img, P, col)


def wings2(img, n, length, width, spread, base_y, inner_x, cols, rise=10):
    light, mid, dark = cols
    layers = []
    for i in range(n):
        t = i / max(1, n - 1)
        ang = -spread / 2 + spread * t - rise     # graus; negativo = para cima
        L = length * (1 - 0.42 * t)
        y = base_y + t * width * 1.5
        col = light if t < 0.34 else (mid if t < 0.67 else dark)
        layers.append((L, y, ang, col))
    for L, y, ang, col in reversed(layers):
        for side in (1, -1):
            a = math.radians(ang) if side == 1 else math.pi - math.radians(ang)
            poly(img, feather((CX + side * inner_x, y), L, width, a), col)


def horns(img, base_y, inner_x, cols, size):
    """Chifres de touro dos dois lados (chapados, dois tons), saindo de um encaixe atrás do escudo:
    para fora, sobem num arco e a ponta volta para dentro."""
    light, mid, dark = cols
    for side in (-1, 1):
        P0 = np.array([CX + side * inner_x, base_y])
        P1 = P0 + np.array([side * size * 0.75, size * 0.18])
        P2 = P0 + np.array([side * size * 1.05, -size * 0.75])
        P3 = P0 + np.array([side * size * 0.45, -size * 1.45])
        t = np.linspace(0, 1, 40)[:, None]
        C = (1 - t) ** 3 * P0 + 3 * (1 - t) ** 2 * t * P1 + 3 * (1 - t) * t ** 2 * P2 + t ** 3 * P3
        T = np.gradient(C, axis=0)
        Nrm = np.stack([-T[:, 1], T[:, 0]], 1) / np.linalg.norm(T, axis=1)[:, None]
        wdt = size * 0.26 * (1 - t[:, 0]) ** 0.85
        A, B = C + Nrm * wdt[:, None], C - Nrm * wdt[:, None]
        outer, inner = (A, B) if side == 1 else (B, A)
        poly(img, [tuple(p) for p in np.vstack([C, outer[::-1]])], light)      # metade de fora clara
        poly(img, [tuple(p) for p in np.vstack([C, inner[::-1]])], dark)       # metade de dentro escura
        cx, cy = P0                                                             # encaixe
        r = size * 0.2
        ImageDraw.Draw(img).rounded_rectangle((cx - r, cy - r * 1.1, cx + r, cy + r * 1.1), radius=r * 0.4, fill=mid)


def star_pts(c, r_out, r_in, n=5, rot=-math.pi / 2):
    P = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = rot + i * math.pi / n
        P.append((c[0] + r * math.cos(a), c[1] + r * math.sin(a)))
    return P


def gem(img, c, r, light, base, dark, tall=1.25):
    """Gema lapidada vista de frente (losango com facetas)."""
    x, y = c
    top, bot, l, rr = (x, y - r * tall), (x, y + r * tall), (x - r, y), (x + r, y)
    poly(img, [top, rr, bot, l], base)
    poly(img, [top, (x, y), l], light)
    poly(img, [top, rr, (x, y)], base)
    poly(img, [l, (x, y), bot], base)
    poly(img, [(x, y), rr, bot], dark)
    poly(img, [(x - r * 0.3, y - r * 0.5), (x - r * 0.1, y - r * 0.85), (x + r * 0.05, y - r * 0.5)], (255, 255, 255, 200))


def crown(img, base_y, w, h, peaks, cols, jewels=None):
    light, mid, dark = cols
    x0, x1 = CX - w, CX + w
    P = [(x0, base_y), (x0, base_y - h * 0.45)]
    tips = []
    for i in range(peaks):
        t = (i + 0.5) / peaks
        x = x0 + (x1 - x0) * t
        center = 1 - abs(t - 0.5) * 2
        hh = h * (0.78 + 0.22 * center)
        if i > 0:
            P.append((x0 + (x1 - x0) * (i / peaks), base_y - h * 0.42))
        P.append((x, base_y - hh))
        tips.append((x, base_y - hh))
    P += [(x1, base_y - h * 0.45), (x1, base_y)]
    two_tone(img, P, hx(light), hx(mid))
    band = [(x0, base_y - h * 0.2), (x1, base_y - h * 0.2), (x1, base_y + h * 0.06), (x0, base_y + h * 0.06)]
    two_tone(img, band, hx(mid), hx(dark))
    d = ImageDraw.Draw(img)
    for x, y in tips:
        r = h * 0.12
        d.ellipse((x - r, y - r, x + r, y + r), fill=hx(light))
    if jewels:
        for i, jc in enumerate(jewels):
            t = (i + 0.5) / len(jewels)
            x = x0 + (x1 - x0) * t
            r = h * 0.09
            d.ellipse((x - r, base_y - h * 0.07 - r, x + r, base_y - h * 0.07 + r), fill=hx(jc))


def rays(img, n, r0, r1, col, width_deg=9, cy=None):
    cy = CY if cy is None else cy
    lay = Image.new('RGBA', img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    for i in range(n):
        a = i * 2 * math.pi / n
        w = math.radians(width_deg)
        d.polygon([(CX + r0 * math.cos(a - w / 3), cy + r0 * math.sin(a - w / 3)),
                   (CX + r1 * math.cos(a - w), cy + r1 * math.sin(a - w)),
                   (CX + r1 * math.cos(a + w), cy + r1 * math.sin(a + w)),
                   (CX + r0 * math.cos(a + w / 3), cy + r0 * math.sin(a + w / 3))], fill=col)
    img.alpha_composite(lay)


def ribbon(img, y, w, h, cols):
    light, mid, dark = cols
    # pontas dobradas
    for side in (-1, 1):
        x_in, x_out = CX + side * w * 0.78, CX + side * (w + h * 0.9)
        P = [(x_in, y - h * 0.35), (x_out, y - h * 0.35), (x_out - side * h * 0.45, y + h * 0.15), (x_out, y + h * 0.65), (x_in, y + h * 0.65)]
        poly(img, P, hx(dark))
    P = [(CX - w, y - h * 0.5)] + bez(np.array([CX - w, y - h * 0.5]), np.array([CX, y - h * 0.15]), np.array([CX + w, y - h * 0.5]), 20)[1:] + \
        [(CX + w, y + h * 0.5)] + bez(np.array([CX + w, y + h * 0.5]), np.array([CX, y + h * 0.85]), np.array([CX - w, y + h * 0.5]), 20)[1:]
    two_tone(img, [tuple(p) for p in P], hx(light), hx(mid))


def sparkle(img, c, r, col=(255, 255, 255, 255)):
    poly(img, star_pts(c, r, r * 0.22, 4, 0), col)


# ---------------------------------------------------------------- escudos
def make(tier):
    light, base, dark, rim, emb = TIERS[tier]
    img = Image.new('RGBA', (N, N), (0, 0, 0, 0))
    lvl = list(TIERS).index(tier)
    # tamanho cresce com o elo
    w = N * (0.225 + 0.008 * lvl)
    h = N * (0.53 + 0.016 * lvl)
    top = ['flat', 'flat', 'notch', 'notch', 'peaks', 'arch', 'arch', 'arch'][lvl]

    # ----- atrás do escudo
    if tier == 'mestre':
        rays(img, 16, N * 0.18, N * 0.46, (255, 214, 90, 70), 7)
        halo = Image.new('RGBA', img.size, (0, 0, 0, 0))
        ImageDraw.Draw(halo).ellipse((CX - N * 0.4, CY - N * 0.42, CX + N * 0.4, CY + N * 0.38), fill=(190, 120, 255, 70))
        img.alpha_composite(halo.filter(ImageFilter.GaussianBlur(N * 0.03)))
    if tier == 'diamante':
        rays(img, 12, N * 0.2, N * 0.44, (150, 210, 255, 70), 6)
    if tier == 'ouro':   # o ouro tem chifres de touro no lugar das asas
        horns(img, CY - h * 0.16, w * 0.88, (hx(light), hx(rim), hx(dark)), N * 0.2)
    if lvl >= 4:   # asas a partir da platina
        wc = (GOLD if tier == 'mestre' else (TIERS[tier][0], TIERS[tier][1], TIERS[tier][2]))
        wc = tuple(hx(c) for c in wc)
        n = [0, 0, 0, 3, 4, 5, 6, 7][lvl]
        L = N * [0, 0, 0, 0.16, 0.2, 0.24, 0.28, 0.31][lvl]
        fw = N * [0, 0, 0, 0.035, 0.04, 0.045, 0.048, 0.052][lvl]
        wings2(img, n, L, fw, [0, 0, 0, 40, 55, 65, 75, 85][lvl], CY - h * 0.28, w * 0.75, wc, rise=[0, 0, 0, 5, 10, 14, 18, 22][lvl])

    # ----- corpo do escudo
    P = shield_pts(w, h, top)
    if rim:
        rim_w = [0, 0.06, 0.08, 0.085, 0.09, 0.09, 0.09, 0.095][lvl]
        two_tone(img, P, hx(rim), shade(rim, 0.82))
        if lvl >= 2:   # borda dupla
            P2 = scale_pts(P, 1 - rim_w * 0.55)
            two_tone(img, P2, hx(light), hx(base))
            P3 = scale_pts(P, 1 - rim_w)
            two_tone(img, P3, hx(base), hx(dark))
        else:
            P3 = scale_pts(P, 1 - rim_w)
            two_tone(img, P3, hx(base), hx(dark))
        inner = P3
    else:
        two_tone(img, P, hx(base), hx(dark))
        inner = P
    # faixa clara diagonal (detalhe de material)
    if lvl >= 1:
        m = Image.new('L', img.size, 0); ImageDraw.Draw(m).polygon(scale_pts(inner, 0.99), fill=255)
        stripe = Image.new('L', img.size, 0)
        ImageDraw.Draw(stripe).polygon([(CX - w * 1.2, CY - h * 0.05), (CX - w * 0.6, CY - h * 0.55), (CX - w * 0.35, CY - h * 0.55), (CX - w * 0.95, CY + h * 0.05)], fill=255)
        mm = Image.fromarray(np.minimum(np.array(m), np.array(stripe)))
        img.paste(Image.new('RGBA', img.size, (255, 255, 255, 50)), (0, 0), mm)

    d = ImageDraw.Draw(img)
    # rebites
    if tier == 'bronze':
        for dx, dy in [(-0.68, -0.32), (0.68, -0.32), (-0.55, 0.12), (0.55, 0.12)]:
            r = N * 0.014
            x, y = CX + dx * w, CY + dy * h
            d.ellipse((x - r, y - r, x + r, y + r), fill=hx(rim))

    # ----- emblema
    ec = (CX, CY - h * 0.04)
    if lvl <= 2:
        r = w * (0.34 + 0.04 * lvl)
        two_tone(img, [(ec[0], ec[1] - r * 1.25), (ec[0] + r, ec[1]), (ec[0], ec[1] + r * 1.25), (ec[0] - r, ec[1])], hx(emb), shade(emb, 0.88))
        if lvl == 2:   # divisa abaixo
            yb = ec[1] + r * 1.55
            P = [(ec[0] - r * 1.1, yb - r * 0.35), (ec[0], yb + r * 0.2), (ec[0] + r * 1.1, yb - r * 0.35), (ec[0] + r * 1.1, yb), (ec[0], yb + r * 0.55), (ec[0] - r * 1.1, yb)]
            two_tone(img, P, hx(emb), shade(emb, 0.88))
    elif tier == 'ouro':
        two_tone(img, star_pts(ec, w * 0.5, w * 0.22), hx(emb), shade(emb, 0.9))
    else:
        gcol = {'platina': ('#e9fffb', '#6fe0d0', '#33a596'), 'esmeralda': ('#b6ffcd', '#2fd16e', '#0e8a3e'),
                'diamante': ('#ffffff', '#a9dcff', '#4f9ff0'), 'mestre': ('#ffb3e6', '#ff4fb4', '#c01c7c')}[tier]
        gr = w * [0, 0, 0, 0, 0.33, 0.38, 0.42, 0.42][lvl]
        # moldura dourada da gema nos elos altos
        if lvl >= 5:
            fr = gr * 1.35
            two_tone(img, [(ec[0], ec[1] - fr * 1.25), (ec[0] + fr, ec[1]), (ec[0], ec[1] + fr * 1.25), (ec[0] - fr, ec[1])], hx(GOLD[0]), hx(GOLD[1]))
        gem(img, ec, gr, hx(gcol[0]), hx(gcol[1]), hx(gcol[2]))

    # ----- coroa
    if lvl >= 5:
        cc = GOLD
        cw = w * [0, 0, 0, 0, 0, 0.5, 0.62, 0.74][lvl]
        ch = N * [0, 0, 0, 0, 0, 0.1, 0.12, 0.14][lvl]
        pts = [0, 0, 0, 0, 0, 3, 5, 5][lvl]
        jew = {6: ['#ff6fb4', '#8fcfff', '#ff6fb4'], 7: ['#8ff0a8', '#ff4fb4', '#8fcfff', '#ff4fb4', '#8ff0a8']}.get(lvl)
        crown(img, CY - h * 0.44, cw, ch, pts, cc, jew)

    # ----- fita do mestre
    if tier == 'mestre':
        ribbon(img, CY + h * 0.47, w * 0.95, N * 0.075, ('#ff6fb4', '#e0358f', '#a81866'))

    # ----- brilhos
    if lvl >= 6:
        for c, r in [((CX + w * 1.25, CY - h * 0.45), N * 0.03), ((CX - w * 1.35, CY + h * 0.2), N * 0.022)]:
            sparkle(img, c, r)
    if lvl == 7:
        sparkle(img, (CX + w * 1.05, CY + h * 0.38), N * 0.02)
        sparkle(img, (CX - w * 0.9, CY - h * 0.62), N * 0.025)
    return img.resize((S, S), Image.LANCZOS)


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for t in TIERS:
        make(t).save(os.path.join(OUT, f'escudo_{t}.png'))
    # folha de prévia
    sheet = Image.new('RGBA', (S * 4, S * 2 + 80), (255, 255, 255, 255))
    from PIL import ImageFont
    f = ImageFont.truetype('/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf', 22)
    d = ImageDraw.Draw(sheet)
    for i, t in enumerate(TIERS):
        x, y = (i % 4) * S, (i // 4) * (S + 40)
        sheet.alpha_composite(Image.open(os.path.join(OUT, f'escudo_{t}.png')), (x, y))
        tw = d.textlength(t.capitalize(), font=f)
        d.text((x + (S - tw) / 2, y + S - 6), t.capitalize(), font=f, fill=(42, 26, 58))
    sheet.save(os.path.join(OUT, '..', 'preview_escudos.png'))
    print('ok')
