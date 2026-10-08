"""Ícones dos executáveis (atalho na área de trabalho, barra de tarefas e janela do jogo).

    python tools/icones.py

Gera em assets/icones/:
    snakift.png / snakift.ico            jogo normal: a cobra clássica num fundo roxo (as cores do menu)
    snakift_robo.png / snakift_robo.ico  versão com robô: a mesma cobra com antena e fone de metal, fundo azul
O .ico tem todos os tamanhos que o Windows usa (16 a 256 px); o .png (256 px) é o ícone da janela.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('CAMERA', '34')

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from sdf import Part, Scene, C, Camera, GAME_CAMERA, PPU, render, rot_y, sphere, capsule, torus0, ellipsoid, mix
import models as m
from models import V, smooth

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'icones')
SIZE = 256
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
BACKS = {   # (cor de cima, cor de baixo, brilho atrás da cobra)
    'snakift': ('#4a1f7a', '#22103f', '#ff3d8b'),
    'snakift_robo': ('#14466b', '#0a1f33', '#3de0ff'),
}


def metal(q):
    return mix(C('#5f6873'), C('#e8edf2'), smooth((q[:, 1] - 0.55) / 0.5)[:, None] * 0.8 + 0.1)


def robot_parts():
    """Antena com luz na ponta e fone de metal (arco por cima da cabeça e as duas conchas)."""
    c, r = m.HEAD_C, m.HEAD_R
    P = []
    base = c + V(-0.06, r * 0.96, 0)
    tip = base + V(-0.04, 0.26, 0)
    P.append(Part(lambda q: capsule(q, base, tip, 0.025), metal, 0.9, 0.02))
    P.append(Part(lambda q: ellipsoid(q, base, V(0.07, 0.025, 0.07)), metal, 0.9, 0.02))
    P.append(Part(lambda q: sphere(q, tip + V(0, 0.05, 0), 0.07), C('#ff3b3b'), 1.0, 0.01))
    Mt = np.stack([V(0, 1, 0), V(1, 0, 0), V(0, 0, 1)], 1)       # arco em pé (plano y-z), de orelha a orelha
    arc_c = c + V(-0.08, 0.0, 0)
    P.append(Part(lambda q: np.maximum(torus0((q - arc_c) @ Mt, r + 0.045, 0.03), arc_c[1] - q[:, 1]), metal, 0.9, 0.02))
    for zs in (1, -1):
        cup = c + V(-0.08, 0.0, zs * (r + 0.02))
        P.append(Part(lambda q, cup=cup: ellipsoid(q, cup, V(0.13, 0.15, 0.07)), C('#2b3038'), 0.7, 0.03))
        P.append(Part(lambda q, cup=cup, zs=zs: sphere(q, cup + V(0, 0, zs * 0.06), 0.06), C('#3de0ff'), 1.0, 0.01))
    return P


def portrait(robot):
    """A cabeça da cobra clássica olhando para a câmera, em RGBA, com folga em volta."""
    parts = m.snake_head('classico', portrait=True) + (robot_parts() if robot else [])
    scene = Scene(parts, rot=rot_y(m.DIRS['S']))
    k = 2.5
    cam = Camera(GAME_CAMERA.D, GAME_CAMERA.R, GAME_CAMERA.U, PPU * k)
    w, h = round(224 * k), round(256 * k)                  # o canvas dos objetos do jogo, no zoom do ícone
    img = render(scene, w, h, round(112 * k), round(184 * k), cam=cam)
    im = Image.fromarray(img)
    return im.crop(im.getbbox())


def icon(name, robot):
    top, bottom, glow = BACKS[name]
    s = SIZE * 4                                            # desenha grande e reduz (bordas lisas)
    grad = Image.new('RGBA', (s, s))
    a, b = np.array(Image.new('RGB', (1, 1), top))[0, 0], np.array(Image.new('RGB', (1, 1), bottom))[0, 0]
    t = np.linspace(0, 1, s)[:, None, None]
    grad = Image.fromarray(np.concatenate([(a * (1 - t) + b * t).repeat(s, 1), np.full((s, s, 1), 255)], 2)
                           .astype(np.uint8))
    halo = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse((s * 0.14, s * 0.12, s * 0.86, s * 0.84), fill=glow + 'a0')
    grad.alpha_composite(halo.filter(ImageFilter.GaussianBlur(s * 0.09)))
    mask = Image.new('L', (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.22), fill=255)
    out = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    out.paste(grad, (0, 0), mask)
    head = portrait(robot)
    scale = s * 0.84 / max(head.size)
    head = head.resize((round(head.width * scale), round(head.height * scale)), Image.LANCZOS)
    shadow = Image.new('RGBA', head.size, (0, 0, 0, 0))
    shadow.putalpha(head.getchannel('A').point(lambda v: v * 0.45))
    x, y = (s - head.width) // 2, int(s * 0.95) - head.height
    out.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(s * 0.015)), (x + s // 60, y + s // 40))
    out.alpha_composite(head, (x, y))
    return out.resize((SIZE, SIZE), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, robot in (('snakift', False), ('snakift_robo', True)):
        img = icon(name, robot)
        img.save(os.path.join(OUT, f'{name}.png'))
        img.save(os.path.join(OUT, f'{name}.ico'), sizes=ICO_SIZES)
        print('ok', name)


if __name__ == '__main__':
    main()
