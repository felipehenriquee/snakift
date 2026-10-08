"""Mini renderizador SDF (numpy) com câmera configurável e luz estilo 'clay 3D'.

Convenções do mundo:  y = cima;  1 unidade = 1 tile do grid;  mundo +x = grid gx;  mundo +z = grid gy.
Câmera ortográfica definida por azimute (giro em torno do eixo vertical) e elevação
(inclinação para baixo). Escolha a câmera com a variável de ambiente CAMERA
(o build.py faz isso com --camera):
  '34'      visão 3/4: grid alinhado à tela (+x = direita, +z = baixo), tile 96x68
  'giro20'  visão 3/4 girada 20° para a direita
  'iso'     isométrica clássica: tile losango 96x48 (+x = baixo-direita, +z = baixo-esquerda)
"""
import os

import numpy as np

CAMERAS = {
    # elevação de 45,1° para o tile ter exatamente 68 px de altura (96 * sen(e) = 68)
    '34': dict(azimute=0.0, elevacao=float(np.degrees(np.arcsin(68 / 96))), ppu=96.0),
    'giro20': dict(azimute=20.0, elevacao=50.0, ppu=54.0),
    'iso': dict(azimute=45.0, elevacao=30.0, ppu=96 / np.sqrt(2)),
}
CAMERA = os.environ.get('CAMERA', '34')
if CAMERA not in CAMERAS:
    raise SystemExit(f'CAMERA desconhecida: {CAMERA!r}. Opções: {", ".join(CAMERAS)}')

AZIMUTE = np.radians(CAMERAS[CAMERA]['azimute'])     # giro da câmera em torno do eixo vertical
ELEVACAO = np.radians(CAMERAS[CAMERA]['elevacao'])   # inclinação da câmera para baixo
PPU = CAMERAS[CAMERA]['ppu']                         # px por unidade de mundo
SS = 3                                               # supersampling (anti-alias)

_sa, _ca = np.sin(AZIMUTE), np.cos(AZIMUTE)
_se, _ce = np.sin(ELEVACAO), np.cos(ELEVACAO)
TO_CAM = np.array([_sa, 0.0, _ca])             # direção horizontal que aponta para a câmera
D = np.array([-_ce * _sa, -_se, -_ce * _ca])   # direção da câmera
R = np.array([_ca, 0.0, -_sa])                 # direita da tela
U = np.cross(R, D)                             # cima da tela
UP = np.array([0.0, 1.0, 0.0])

# tamanho na tela da face de cima de um tile (caixa que envolve o quadrado 1x1 projetado)
TILE_PX = [round(float((abs(_ca) + abs(_sa)) * PPU), 2), round(float((abs(_sa) + abs(_ca)) * _se * PPU), 2)]


def screen_px(v):
    """Vetor do mundo -> deslocamento na tela em px (x para a direita, y para baixo)."""
    return [round(float(np.dot(v, R) * PPU), 4) + 0.0, round(float(-np.dot(v, U) * PPU), 4) + 0.0]   # + 0.0 tira o -0.0


def projection():
    """Como o jogo converte célula do grid em posição na tela e em profundidade."""
    return {
        'camera': CAMERA,
        'gx': screen_px([1, 0, 0]),
        'gy': screen_px([0, 0, 1]),
        'profundidade': [round(float(TO_CAM[0]), 4), round(float(TO_CAM[2]), 4)],
    }


def norm(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


LIGHT = norm(0.8 * UP - 0.55 * R - 0.35 * D)
HALF = norm(LIGHT - D)


class Camera:
    """Câmera ortográfica: direção, eixos da tela, px por unidade e luz (que vem de cima-esquerda)."""

    def __init__(self, d, r, u, ppu, light=None):
        self.D, self.R, self.U, self.PPU = norm(d), norm(r), norm(u), ppu
        self.LIGHT = norm(light) if light is not None else norm(0.8 * UP - 0.55 * self.R - 0.35 * self.D)
        self.HALF = norm(self.LIGHT - self.D)


GAME_CAMERA = Camera(D, R, U, PPU)


def front_camera(ppu):
    """Câmera olhando de frente (para -z), para a interface: +x = direita, +y = cima."""
    # luz mais de frente que a do jogo: a face do painel olha para a câmera e precisa ficar clara
    return Camera([0, 0, -1], [1, 0, 0], [0, 1, 0], ppu, light=[-0.35, 0.45, 0.8])


def C(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])


# ---------------------------------------------------------------- primitivas
def length(v):
    return np.sqrt((v * v).sum(-1))


def sphere(p, c, r):
    return length(p - c) - r


def ellipsoid0(q, rad):
    k0 = length(q / rad)
    k1 = length(q / (rad * rad))
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


def ellipsoid(p, c, rad):
    return ellipsoid0(p - c, np.asarray(rad, float))


def capsule(p, a, b, r):
    pa = p - a
    ba = b - a
    h = np.clip(pa @ ba / (ba @ ba), 0, 1)
    return length(pa - h[:, None] * ba) - r


def round_cone(p, a, b, r1, r2):
    a = np.asarray(a, float); b = np.asarray(b, float)
    ba = b - a
    l2 = ba @ ba
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / l2
    pa = p - a
    y = pa @ ba
    z = y - l2
    x = pa * l2 - y[:, None] * ba
    x2 = (x * x).sum(-1)
    y2 = y * y * l2
    z2 = z * z * l2
    k = np.sign(rr) * rr * rr * x2
    r_a = np.sqrt(x2 + z2) * il2 - r2
    r_b = np.sqrt(x2 + y2) * il2 - r1
    r_c = (np.sqrt(np.maximum(x2 * a2 * il2, 0)) + y * rr) * il2 - r1
    return np.where(np.sign(z) * a2 * z2 > k, r_a, np.where(np.sign(y) * a2 * y2 < k, r_b, r_c))


def torus0(q, Rm, r):
    return np.sqrt((np.sqrt(q[:, 0] ** 2 + q[:, 2] ** 2) - Rm) ** 2 + q[:, 1] ** 2) - r


def rbox(p, c, half, rr):
    q = np.abs(p - c) - (np.asarray(half) - rr)
    return length(np.maximum(q, 0)) + np.minimum(q.max(-1), 0) - rr


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def rot_axis(axis, ang):
    """Matriz local->mundo (colunas = eixos locais)."""
    x, y, z = norm(axis)
    c, s = np.cos(ang), np.sin(ang)
    return np.array([
        [c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
        [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
        [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)]])


def rot_y(ang):
    return rot_axis(UP, ang)


# ---------------------------------------------------------------- ruído
def _hash(i):
    n = i[..., 0] * 127.1 + i[..., 1] * 311.7 + i[..., 2] * 74.7
    return (np.sin(n) * 43758.5453) % 1.0


def vnoise(p):
    fl = np.floor(p)
    f = p - fl
    u = f * f * (3 - 2 * f)
    out = 0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                h = _hash(fl + np.array([dx, dy, dz]))
                w = (u[:, 0] if dx else 1 - u[:, 0]) * (u[:, 1] if dy else 1 - u[:, 1]) * (u[:, 2] if dz else 1 - u[:, 2])
                out = out + h * w
    return out


def fbm(p, oct=3):
    s, a, tot = 0, 0.5, 0
    for _ in range(oct):
        s = s + a * vnoise(p)
        tot += a
        p = p * 2.03 + 1.7
        a *= 0.5
    return s / tot


def mix(a, b, t):
    t = np.asarray(t)
    if t.ndim == 1:
        t = t[:, None]
    return a * (1 - t) + b * t


# ---------------------------------------------------------------- cena
class Part:
    def __init__(self, sdf, col, gloss=0.3, k=0.0):
        self.sdf, self.col, self.gloss, self.k = sdf, col, gloss, k

    def color(self, q):
        if callable(self.col):
            return self.col(q)
        return np.broadcast_to(np.asarray(self.col, float), (len(q), 3))


class Scene:
    def __init__(self, parts, rot=None, offset=(0, 0, 0), scale=1.0):
        self.parts = [p for p in parts if p is not None]
        self.scale = scale
        self.rot = rot
        self.offset = np.asarray(offset, float)

    def local(self, p):
        q = p - self.offset
        q = q @ self.rot if self.rot is not None else q
        return q / self.scale

    def dist(self, p):
        q = self.local(p)
        d = None
        for pt in self.parts:
            di = pt.sdf(q)
            if d is None:
                d = di
            elif pt.k > 0:
                d = smin(d, di, pt.k)
            else:
                d = np.minimum(d, di)
        return d * self.scale

    def material(self, p):
        q = self.local(p)
        ds = np.stack([pt.sdf(q) for pt in self.parts], 1)
        w = np.exp(-(ds - ds.min(1, keepdims=True)) / 0.004)
        w /= w.sum(1, keepdims=True)
        col = np.zeros((len(q), 3))
        gl = np.zeros(len(q))
        for i, pt in enumerate(self.parts):
            wi = w[:, i]
            m = wi > 1e-3
            if m.any():
                col[m] += wi[m, None] * pt.color(q[m])
                gl[m] += wi[m] * pt.gloss
        return col, gl


# ---------------------------------------------------------------- render
def render(scene, W, H, ox, oy, ss=SS, cam=None):
    """Renderiza a cena; o ponto de mundo (0,0,0) cai no pixel (ox, oy). cam: câmera do jogo por padrão."""
    cam = cam or GAME_CAMERA
    D, R, U, PPU, LIGHT, HALF = cam.D, cam.R, cam.U, cam.PPU, cam.LIGHT, cam.HALF
    h, w = H * ss, W * ss
    jj, ii = np.meshgrid(np.arange(w), np.arange(h))
    sx = ((jj + 0.5) / ss - ox) / PPU
    sy = (oy - (ii + 0.5) / ss) / PPU
    P = sx.reshape(-1, 1) * R + sy.reshape(-1, 1) * U
    O = P - D * 20
    n = len(O)
    t = np.full(n, 16.5)
    active = np.ones(n, bool)
    hit = np.zeros(n, bool)
    for _ in range(160):
        idx = np.nonzero(active)[0]
        if len(idx) == 0:
            break
        pos = O[idx] + D * t[idx, None]
        d = scene.dist(pos)
        hn = d < 0.0007
        hit[idx[hn]] = True
        t[idx[~hn]] += np.maximum(d[~hn] * 0.85, 0.0004)
        stop = hn | (t[idx] > 23.5)
        active[idx[stop]] = False

    img = np.zeros((n, 4))
    hid = np.nonzero(hit)[0]
    if len(hid):
        p = O[hid] + D * t[hid, None]
        # normal (tetraedro)
        e = 0.0015
        ks = np.array([[1, -1, -1], [-1, -1, 1], [-1, 1, -1], [1, 1, 1]], float)
        nrm = sum(k * scene.dist(p + k * e)[:, None] for k in ks)
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
        alb, gl = scene.material(p)
        # oclusão ambiente
        occ = np.zeros(len(p)); sca = 1.0
        for i in range(5):
            hh = 0.01 + 0.11 * i / 4
            occ += (hh - scene.dist(p + nrm * hh)) * sca
            sca *= 0.9
        ao = np.clip(1 - 2.2 * occ, 0, 1)
        # sombra suave
        sh = np.ones(len(p))
        tt = np.full(len(p), 0.02)
        for _ in range(28):
            hh = scene.dist(p + nrm * 0.004 + LIGHT * tt[:, None])
            sh = np.minimum(sh, np.clip(10 * hh / tt, 0, 1))
            tt += np.clip(hh, 0.01, 0.12)
        sh = sh * sh * (3 - 2 * sh)
        ndl = nrm @ LIGHT
        diff = np.clip((ndl + 0.3) / 1.3, 0, 1) * (0.35 + 0.65 * sh)
        sky = 0.5 + 0.5 * nrm[:, 1]
        amb = (0.5 + 0.25 * sky) * (0.4 + 0.6 * ao)
        spec = gl * np.clip(nrm @ HALF, 0, 1) ** (20 + 70 * gl) * sh * 0.8
        fres = (1 - np.clip(-(nrm @ D), 0, 1)) ** 3
        light_col = np.array([1.0, 0.98, 0.94])
        col = alb * (0.75 * diff[:, None] * light_col + amb[:, None] * np.array([0.97, 0.97, 1.03]))
        col += spec[:, None] + fres[:, None] * (0.25 * alb + 0.08) * ao[:, None]
        col = 1 - np.exp(-col * 1.7)             # tone map suave
        col = col ** 1.05
        img[hid, :3] = np.clip(col, 0, 1)
        img[hid, 3] = 1
    img = img.reshape(h, w, 4)
    # downsample com alpha pré-multiplicado
    img[..., :3] *= img[..., 3:]
    img = img.reshape(H, ss, W, ss, 4).mean((1, 3))
    a = img[..., 3:]
    img[..., :3] = np.where(a > 0, img[..., :3] / np.maximum(a, 1e-6), 0)
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
