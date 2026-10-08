"""Interface chapada (flat) do Snakift. Gera assets/ui/capa e assets/ui/botoes.

Botões em 3 estados com o MESMO tamanho de canvas: normal, hover, pressionado.
"""
import os, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
UI = os.path.join(HERE, '..', '..', 'assets', 'ui')
MENU = os.path.join(HERE, '..', '..', '_nao_usados', 'menu_snakift_v2', 'menu')     # artes do menu antigo
FB = '/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf'
K = 4
W, H = 1280, 720

PINK = {'normal': (255, 61, 139), 'hover': (255, 92, 160), 'pressionado': (224, 38, 116)}
GLASS = {'normal': 46, 'hover': 72, 'pressionado': 28}          # alpha do fundo translúcido
SOFT = {'normal': (244, 240, 250), 'hover': (236, 230, 246), 'pressionado': (226, 218, 240)}   # sobre cartão branco
INK = (42, 26, 58)


def canvas(w, h):
    return Image.new('RGBA', (w * K, h * K), (0, 0, 0, 0))


def down(im):
    return im.resize((im.width // K, im.height // K), Image.LANCZOS)


# ---------------------------------------------------------------- ícones (traço, estilo "line icon")
def icon_play(d, cx, cy, s, col):
    d.polygon([(cx - s * 0.42, cy - s * 0.55), (cx + s * 0.55, cy), (cx - s * 0.42, cy + s * 0.55)], fill=col)


def icon_x(d, cx, cy, s, col, lw):
    r = s * 0.42
    for sg in (1, -1):
        d.line((cx - r, cy - r * sg, cx + r, cy + r * sg), fill=col, width=lw)
    for p in [(cx - r, cy - r), (cx + r, cy + r), (cx - r, cy + r), (cx + r, cy - r)]:
        d.ellipse((p[0] - lw / 2, p[1] - lw / 2, p[0] + lw / 2, p[1] + lw / 2), fill=col)


def icon_back(d, cx, cy, s, col, lw):
    r = s * 0.45
    d.line((cx - r, cy, cx + r, cy), fill=col, width=lw)
    d.line((cx - r, cy, cx - r * 0.1, cy - r * 0.85), fill=col, width=lw)
    d.line((cx - r, cy, cx - r * 0.1, cy + r * 0.85), fill=col, width=lw)
    for p in [(cx - r, cy), (cx + r, cy), (cx - r * 0.1, cy - r * 0.85), (cx - r * 0.1, cy + r * 0.85)]:
        d.ellipse((p[0] - lw / 2, p[1] - lw / 2, p[0] + lw / 2, p[1] + lw / 2), fill=col)


def icon_gear(img, cx, cy, s, col, lw):
    """Engrenagem em traço: contorno de dentes + furo."""
    teeth, ro, ri = 8, s * 0.5, s * 0.36
    P = []
    for i in range(teeth * 4):
        a = i * 2 * math.pi / (teeth * 4) + math.pi / (teeth * 4)
        r = ro if (i % 4) in (1, 2) else ri
        P.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    m = Image.new('L', img.size, 0); dm = ImageDraw.Draw(m)
    dm.polygon(P, fill=255)
    inner = Image.new('L', img.size, 0); di = ImageDraw.Draw(inner)
    # encolhe o contorno para virar traço
    Pi = [(cx + (x - cx) * (1 - lw / ro * 1.15), cy + (y - cy) * (1 - lw / ro * 1.15)) for x, y in P]
    di.polygon(Pi, fill=255)
    ring = np.clip(np.array(m).astype(int) - np.array(inner).astype(int), 0, 255).astype(np.uint8)
    hole = Image.new('L', img.size, 0); dh = ImageDraw.Draw(hole)
    rh = s * 0.15
    dh.ellipse((cx - rh - lw / 2, cy - rh - lw / 2, cx + rh + lw / 2, cy + rh + lw / 2), fill=255)
    dh.ellipse((cx - rh + lw / 2, cy - rh + lw / 2, cx + rh - lw / 2, cy + rh - lw / 2), fill=0)
    mask = Image.fromarray(np.maximum(ring, np.array(hole)))
    img.paste(Image.new('RGBA', img.size, col), (0, 0), mask)


def icon_trophy(d, cx, cy, s, col, lw):
    r = s * 0.5
    top, cupb = cy - r * 0.85, cy + r * 0.15
    # taça
    d.line((cx - r * 0.55, top, cx + r * 0.55, top), fill=col, width=lw)
    d.arc((cx - r * 0.55, top - r * 0.95, cx + r * 0.55, cupb + 0.0), 0, 180, fill=col, width=lw)
    d.line((cx - r * 0.55, top, cx - r * 0.55, top + r * 0.45), fill=col, width=lw)
    d.line((cx + r * 0.55, top, cx + r * 0.55, top + r * 0.45), fill=col, width=lw)
    # alças
    d.arc((cx - r * 0.95, top + r * 0.02, cx - r * 0.35, top + r * 0.6), 90, 270, fill=col, width=lw)
    d.arc((cx + r * 0.35, top + r * 0.02, cx + r * 0.95, top + r * 0.6), 270, 90, fill=col, width=lw)
    # haste e base
    d.line((cx, cupb, cx, cy + r * 0.62), fill=col, width=lw)
    d.line((cx - r * 0.42, cy + r * 0.72, cx + r * 0.42, cy + r * 0.72), fill=col, width=lw)
    for p in [(cx - r * 0.42, cy + r * 0.72), (cx + r * 0.42, cy + r * 0.72)]:
        d.ellipse((p[0] - lw / 2, p[1] - lw / 2, p[0] + lw / 2, p[1] + lw / 2), fill=col)


def icon_pencil(d, cx, cy, s, col, lw):
    r = s * 0.42
    a = (cx - r * 0.7, cy + r * 0.7); b = (cx + r * 0.55, cy - r * 0.55)
    d.line((a, b), fill=col, width=int(lw * 1.6))
    d.polygon([(a[0] - lw * 0.6, a[1] + lw * 0.6), (a[0] - lw * 0.2, a[1] - lw * 1.2), (a[0] + lw * 1.2, a[1] + lw * 0.2)], fill=col)


ICONS = {'fechar': icon_x, 'voltar': icon_back, 'config': None, 'trofeu': icon_trophy}


# ---------------------------------------------------------------- botões
def btn_primary(w, h, label, state, radius=14, font_size=21):
    im = canvas(w, h); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w * K - 1, h * K - 1), radius=radius * K, fill=PINK[state] + (255,))
    f = ImageFont.truetype(FB, font_size * K)
    lw = d.textlength(label, font=f); tri = font_size * 0.62 * K; gap = font_size * 0.55 * K
    x = (w * K - (tri + gap + lw)) / 2; cy = h * K / 2
    icon_play(d, x + tri * 0.42, cy, tri, (255, 255, 255, 255))
    bb = f.getbbox(label)
    d.text((x + tri + gap, cy - (bb[1] + bb[3]) / 2), label, font=f, fill=(255, 255, 255, 255))
    return down(im)


def btn_icon(name, state, size=52, variant='vidro'):
    im = canvas(size, size); d = ImageDraw.Draw(im)
    if variant == 'vidro':     # sobre o fundo roxo
        d.rounded_rectangle((0, 0, size * K - 1, size * K - 1), radius=12 * K, fill=(255, 255, 255, GLASS[state]))
        col = (255, 255, 255, 255)
    else:                      # sobre cartão branco
        d.rounded_rectangle((0, 0, size * K - 1, size * K - 1), radius=12 * K, fill=SOFT[state] + (255,))
        col = INK + (255,)
    cx = cy = size * K / 2; s = size * 0.42 * K; lw = int(2.4 * K)
    if name == 'config':
        icon_gear(im, cx, cy, s * 1.2, col, lw)
    elif name == 'editar':
        icon_pencil(d, cx, cy, s, col, lw)
    else:
        ICONS[name](d, cx, cy, s, col, lw)
    return down(im)


def badge_editar(state, size=24):
    im = canvas(size, size); d = ImageDraw.Draw(im)
    fill = {'normal': INK, 'hover': (70, 48, 92), 'pressionado': (24, 14, 34)}[state]
    d.ellipse((0, 0, size * K - 1, size * K - 1), fill=(255, 255, 255, 255))
    b = 2 * K
    d.ellipse((b, b, size * K - 1 - b, size * K - 1 - b), fill=fill + (255,))
    icon_pencil(d, size * K / 2, size * K / 2, size * 0.5 * K, (255, 255, 255, 255), int(1.6 * K))
    return down(im)


# ---------------------------------------------------------------- capa
def capa_fundo():
    yy = np.linspace(0, 1, H)[:, None]; xx = np.linspace(0, 1, W)[None, :]
    c1, c2 = np.array([96, 52, 150]), np.array([52, 28, 104])
    t = np.clip(0.6 * yy + 0.4 * xx, 0, 1)[..., None]; base = c1 * (1 - t) + c2 * t
    for cx, cy, rx, ry, col, a in [(0.05, 0.85, 0.25, 0.35, (90, 170, 90), 0.3), (0.95, 0.75, 0.2, 0.3, (110, 180, 110), 0.22),
                                   (0.5, 0.45, 0.35, 0.45, (150, 90, 190), 0.45), (0.85, 0.1, 0.25, 0.25, (200, 90, 170), 0.25)]:
        g = np.exp(-(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2))[..., None] * a
        base = base * (1 - g) + np.array(col) * g
    bg = Image.fromarray(base.astype(np.uint8)).convert('RGBA')
    band = Image.open(os.path.join(MENU, 'menu_corpo_fundo.png'))
    a = band.getchannel('A').filter(ImageFilter.GaussianBlur(8))
    rgb = Image.blend(band.convert('RGB').filter(ImageFilter.GaussianBlur(8)), Image.new('RGB', (W, H), (110, 70, 160)), 0.62)
    b2 = rgb.convert('RGBA'); b2.putalpha(a.point(lambda v: int(v * 0.75))); bg.alpha_composite(b2)
    veil = Image.new('RGBA', (W, H), (30, 14, 60, 0))
    vm = np.clip((0.35 - yy) * 1.2, 0, 0.35) + np.clip((yy - 0.75) * 1.0, 0, 0.25)
    veil.putalpha(Image.fromarray((np.repeat(vm, W, 1) * 255).astype(np.uint8))); bg.alpha_composite(veil)
    return bg


def capa_cobra(dy=22):
    head = Image.open(os.path.join(MENU, 'menu_cobra.png'))
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sh = head.getchannel('A').filter(ImageFilter.GaussianBlur(22)).point(lambda v: int(v * 0.5))
    shl = Image.new('RGBA', (W, H), (20, 5, 40, 0)); shl.putalpha(sh)
    out.alpha_composite(shl, (0, dy - 4)); out.alpha_composite(head, (0, dy))
    return out


def logo(size=96, white=(255, 255, 255), pink=(255, 140, 190)):
    f = ImageFont.truetype(FB, size * K)
    tmp = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    w1 = tmp.textlength('Snak', font=f); w2 = tmp.textlength('ift', font=f)
    bb = f.getbbox('Snakift')
    im = Image.new('RGBA', (int(w1 + w2) + 8 * K, bb[3] + 8 * K), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.text((4 * K, 4 * K - bb[1] * 0 ), 'Snak', font=f, fill=white + (255,))
    d.text((4 * K + w1, 4 * K), 'ift', font=f, fill=pink + (255,))
    im = im.crop(im.getbbox())
    return down(im)


if __name__ == '__main__':
    for sub in ('capa', 'botoes'):
        os.makedirs(os.path.join(UI, sub), exist_ok=True)
    capa_fundo().save(os.path.join(UI, 'capa', 'capa_fundo.png'))
    capa_cobra().save(os.path.join(UI, 'capa', 'capa_cobra.png'))
    logo(96).save(os.path.join(UI, 'capa', 'logo_snakift.png'))
    logo(26).save(os.path.join(UI, 'capa', 'logo_snakift_pequeno.png'))
    B = os.path.join(UI, 'botoes')
    for st in ('normal', 'hover', 'pressionado'):
        btn_primary(320, 64, 'JOGAR', st).save(os.path.join(B, f'jogar_capa_{st}.png'))
        btn_primary(322, 50, 'JOGAR', st, radius=12, font_size=16).save(os.path.join(B, f'jogar_card_{st}.png'))
        for n in ('fechar', 'voltar', 'config', 'trofeu'):
            btn_icon(n, st).save(os.path.join(B, f'{n}_{st}.png'))
        badge_editar(st).save(os.path.join(B, f'editar_avatar_{st}.png'))
    print('ok')
