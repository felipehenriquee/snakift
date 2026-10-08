"""Gera todos os sprites (cobras, comidas, tiles, props, cercas, painéis da interface) e o manifest.json.

    python build.py [--camera 34|giro20|iso] [--out PASTA] [--partes sprites ui escudos skins avatares macas personagem]

--partes escolhe o que gerar (padrão: tudo). "ui" sozinho refaz só os painéis do placar e
do fim de jogo, mantendo os sprites do jogo e o resto do manifest como estão. "skins" sozinho
refaz só as skins da cobra, recortadas no canvas de objetos que já está no manifest (rápido;
se alguma skin não couber nele, avisa para refazer com "sprites"). "avatares" refaz os retratos
das skins (cabeça de frente em alta resolução, para o perfil e a tela de skins) em avatares/<skin>.png.
"macas" refaz só as maçãs dos elos (comidas/maca_<elo>.png) e a caixa de presente da live
(comidas/caixa.png), recortadas no canvas de objetos atual. "comidas" refaz essas e também as comidas
dos presentes e a bomba (comidas/<nome>.png).
"personagem" refaz o duende que joga os presentes (personagem/<pose>.png, com canvas próprio).

Por padrão grava em ../sprites_<camera>. Cada grupo (objetos e tiles) é renderizado num
canvas folgado e depois recortado pela caixa que envolve todos os sprites do grupo, então
nada fica cortado e todos os sprites do grupo têm o mesmo tamanho e a mesma âncora.
"""
import argparse
import json
import os
import sys
import time

ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
ap.add_argument('--camera', default='34')
ap.add_argument('--out')
ap.add_argument('--partes', nargs='+', choices=['sprites', 'ui', 'escudos', 'skins', 'avatares', 'macas', 'comidas', 'personagem'],
                default=['sprites', 'ui', 'escudos', 'avatares', 'personagem'])
ap.add_argument('--paineis', nargs='+', help='com --partes ui: só estes painéis (ex.: placar_aberto)')
ARGS = ap.parse_args()
os.environ['CAMERA'] = ARGS.camera      # o sdf.py lê a câmera ao ser importado

import numpy as np
from multiprocessing import Pool
from PIL import Image, ImageDraw, ImageFilter
from sdf import (render, Scene, rot_y, projection, front_camera, Camera, GAME_CAMERA, PPU, ELEVACAO, TILE_PX, CAMERA,
                 screen_px)
import models as m
import fences as fc
import ui
import shields

OUT = ARGS.out or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets',
                               'sprites' if CAMERA == '34' else f'sprites_{CAMERA}')
# canvas folgado usado na renderização; (ox, oy) = pixel do centro do tile, no chão
BIG = {
    'objeto': dict(w=224, h=256, ox=112, oy=184),
    'tile': dict(w=144, h=136, ox=72, oy=56),
    'personagem': dict(w=300, h=330, ox=140, oy=270),
}
MARGIN = 1          # px livres em volta do recorte
AVATAR_ZOOM = 3     # retratos das skins: 3x o tamanho do sprite do jogo (nítidos mesmo ampliados)


def ui_jobs():
    """Painéis da interface: canvas fixo (ui.layout), câmera de frente, sem recorte."""
    kinds = ARGS.paineis or list(ui.PANELS)
    return [(f'{t}/ui_{k}.png', 'ui', (t, k), 'ui') for t in ui.THEME_UI for k in kinds]


def shield_jobs():
    """Escudos do ranque: canvas fixo (shields.CANVAS), câmera de frente, sem recorte."""
    return [(f'ranque/escudo_{t}.png', 'escudo', (t,), 'escudo') for t in shields.ORDER]


def jobs():
    J = food_jobs() + apple_jobs()
    for t in m.THEMES:
        for d in m.DIRS:
            J.append((f'{t}/cabeca_{d}.png', 'head', (t, d), 'objeto'))
            J.append((f'{t}/cauda_{d}.png', 'tail', (t, d), 'objeto'))
        for v in (0, 1):
            J.append((f'{t}/corpo_{v}.png', 'body', (t, v), 'objeto'))
            J.append((f'{t}/tile_{v}.png', 'tile', (t, v), 'tile'))
            J.append((f'{t}/prop_{v}.png', 'prop', (t, v), 'objeto'))
        for piece in fc.PIECES:
            J.append((f'{t}/cerca_{piece}.png', 'fence', (t, piece), 'objeto'))
    return J + skin_jobs()


def skin_jobs():
    """Skins da cobra: só cabeça, corpo e cauda."""
    J = []
    for skin in m.SKINS:
        name = skin.replace('skin_', '')
        for d in m.DIRS:
            J.append((f'skins/{name}/cabeca_{d}.png', 'head', (skin, d), 'objeto'))
            J.append((f'skins/{name}/cauda_{d}.png', 'tail', (skin, d), 'objeto'))
        for v in (0, 1):
            J.append((f'skins/{name}/corpo_{v}.png', 'body', (skin, v), 'objeto'))
            if skin in m.DIRECTIONAL_BODY:            # barbatana: um corpo por direção
                for d in m.DIRS:
                    J.append((f'skins/{name}/corpo_{v}_{d}.png', 'body', (skin, v, d), 'objeto'))
    return J


def avatar_jobs():
    """Retrato de cada skin (a 'classica' é a cabeça do tema classico), olhando para a câmera."""
    return [(f'avatares/{s.replace("skin_", "")}.png', 'portrait', (s, 'S'), 'avatar')
            for s in ['classico'] + m.SKINS]


def food_jobs():
    """Comidas e presentes (cada presente troca para o tema de mesmo nome) e a bomba."""
    return [(f'comidas/{name}.png', fn.__name__, (), 'objeto')
            for name, fn in [('rosa', m.food_rose), ('rosquinha', m.food_donut), ('esquilo', m.food_squirrel),
                             ('caracol', m.food_snail), ('coracao', m.food_hand_hearts),
                             ('maca', m.food_apple), ('bomba', m.food_bomb)]]


def apple_jobs():
    """Maçãs dos elos (bronze, prata... mestre; a do ferro é a maçã comum) e a caixa de presente da live."""
    return [(f'comidas/maca_{t}.png', 'apple', (t,), 'objeto') for t in m.APPLE_PAL] + \
        [('comidas/caixa.png', 'food_box', (), 'objeto')]


def character_jobs():
    """Duendes: o que joga os presentes (personagem/<pose>.png) e o do mal, que joga as bombas (mal_<pose>.png)."""
    return [(f'personagem/{"mal_" if evil else ""}{pose}.png', 'gnome', (pose, evil), 'personagem')
            for evil in (False, True) for pose in m.GNOME_POSES] + \
        [(f'personagem/{"mal_" if evil else ""}placa.png', 'gnome', ('placa', evil), 'personagem')    # os da placa
         for evil in (False, True)]


def save_character(results, evil=False):
    """Recorta as poses de um duende na mesma caixa e devolve o trecho do manifest (âncora e mão de cada pose)."""
    imgs = {path: img for path, (g, img) in results.items()
            if g == 'personagem' and os.path.basename(path).startswith('mal_') == evil}
    if not imgs:
        return None
    x0, y0, x1, y1 = crop_box(list(imgs.values()))
    for path, img in imgs.items():
        save(path, img[y0:y1, x0:x1])
    cv = BIG['personagem']
    ax, ay = cv['ox'] - x0, cv['oy'] - y0
    hands = {}
    for pose in m.GNOME_POSES:
        dx, dy = screen_px(m.gnome_hand_world(pose, evil))
        hands[pose] = [round(ax + dx, 1), round(ay + dy, 1)]
    sc, hw, hh = m.sign_box_world()     # área da placa (o jogo escreve quem mandou o presente / a bomba)
    cw, ch = screen_px(sc)
    left, right = screen_px(sc - m.V(hw, 0, 0)), screen_px(sc + m.V(hw, 0, 0))
    top, bot = screen_px(sc + hh), screen_px(sc - hh)          # hh: vetor "meia altura" da placa inclinada
    sign = {'centro': [round(ax + cw, 1), round(ay + ch, 1)],
            'tamanho': [round(right[0] - left[0], 1), round(bot[1] - top[1], 1)]}
    return {'placa': sign, 'poses': list(m.GNOME_POSES) + ['placa'],
            'arquivo': f'personagem/{"mal_" if evil else ""}<pose>.png',
            'tamanho': [int(x1 - x0), int(y1 - y0)],
            'ancora': [int(ax), int(ay)], 'mao': hands,
            'nota': 'ancora = pé no chão (centro da célula); mao = onde o jogo desenha o presente em cada pose'}


def food_to_theme():
    """Cada comida troca a cobra e o cenário para um tema; as maçãs (de qualquer elo) voltam para o clássico."""
    out = {'rosa': 'rosa', 'rosquinha': 'rosquinha', 'esquilo': 'esquilo', 'caracol': 'caracol', 'coracao': 'coracao',
           'maca': 'classico'}
    out.update({f'maca_{t}': 'classico' for t in m.APPLE_PAL})
    return out


def skins_manifest():
    return {'lista': ['classica'] + [k.replace('skin_', '') for k in m.SKINS], 'arquivo': 'skins/<skin>/<peca>.png'}


def scene_for(kind, args):
    if kind == 'head': return Scene(m.snake_head(args[0]), rot=rot_y(m.DIRS[args[1]]))
    if kind == 'portrait': return Scene(m.snake_head(args[0], portrait=True), rot=rot_y(m.DIRS[args[1]]))
    if kind == 'tail': return Scene(m.snake_tail(args[0]), rot=rot_y(m.DIRS[args[1]]))
    if kind == 'apple': return m.food_apple(*args)
    if kind == 'gnome': return m.gnome(*args)
    if kind == 'body': return Scene(m.snake_body(*args), rot=rot_y(m.DIRS[args[2]]) if len(args) > 2 else None)
    if kind == 'tile': return m.tile(*args)
    if kind == 'prop': return m.prop(*args)
    if kind == 'fence': return fc.fence(*args)
    return getattr(m, kind)()


def work(job):
    path, kind, args, group = job
    if group == 'ui':
        L = ui.layout(args[1])
        return path, group, render(ui.panel(*args), L['w'], L['h'], L['ox'], L['oy'], ss=ui.SS, cam=front_camera(ui.PPU))
    if group == 'escudo':
        c = shields.CANVAS
        return path, group, render(shields.shield(*args), c['w'], c['h'], c['ox'], c['oy'], cam=front_camera(shields.PPU))
    if group == 'avatar':
        k = AVATAR_ZOOM
        cam = Camera(GAME_CAMERA.D, GAME_CAMERA.R, GAME_CAMERA.U, PPU * k)
        cv = BIG['objeto']
        return path, group, render(scene_for(kind, args), cv['w'] * k, cv['h'] * k, cv['ox'] * k, cv['oy'] * k, cam=cam)
    cv = BIG[group]
    return path, group, render(scene_for(kind, args), cv['w'], cv['h'], cv['ox'], cv['oy'])


def touches_edge(alpha):
    return bool(alpha[0].any() or alpha[-1].any() or alpha[:, 0].any() or alpha[:, -1].any())


def crop_box(images):
    """Caixa (x0, y0, x1, y1) que envolve o alpha de todas as imagens, com margem."""
    a = np.max([im[..., 3] for im in images], 0)
    ys, xs = np.nonzero(a)
    h, w = a.shape
    return (max(xs.min() - MARGIN, 0), max(ys.min() - MARGIN, 0),
            min(xs.max() + 1 + MARGIN, w), min(ys.max() + 1 + MARGIN, h))


def shadow(w, h, ox, oy):
    im = Image.new('L', (w, h), 0)
    rx = 0.43 * PPU
    ry = rx * np.sin(ELEVACAO)       # círculo no chão visto de cima/frente
    ImageDraw.Draw(im).ellipse((ox - rx, oy - ry, ox + rx, oy + ry), fill=110)
    im = im.filter(ImageFilter.GaussianBlur(6))
    out = Image.new('RGBA', (w, h), (40, 20, 50, 0))
    out.putalpha(im)
    return out


def ui_manifest():
    out = {k: dict(tamanho=[L['w'], L['h']], ancora=[L['ox'], L['oy']], area=L['area'], arquivo=f'<tema>/ui_{k}.png')
           for k, L in ((k, ui.layout(k)) for k in ui.PANELS)}
    out['cores'] = ui.text_colors()
    out['nota'] = 'area = retangulo (x, y, largura, altura) do miolo claro, onde o jogo escreve os textos'
    return out


def shield_manifest():
    c = shields.CANVAS
    return {'ligas': shields.ORDER, 'arquivo': 'ranque/escudo_<liga>.png', 'tamanho': [c['w'], c['h']],
            'centro': [c['ox'], c['oy']], 'nota': 'centro = pixel do meio do escudo'}


def save(path, img):
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    Image.fromarray(img).save(full, optimize=True)


def main():
    t0 = time.time()
    # painéis primeiro: são os mais demorados, assim rodam em paralelo com o resto
    only_skins = 'skins' in ARGS.partes and 'sprites' not in ARGS.partes
    only_apples = ('macas' in ARGS.partes or 'comidas' in ARGS.partes) and 'sprites' not in ARGS.partes
    J = ((ui_jobs() if 'ui' in ARGS.partes else []) + (shield_jobs() if 'escudos' in ARGS.partes else [])
         + (jobs() if 'sprites' in ARGS.partes else []) + (skin_jobs() if only_skins else [])
         + (apple_jobs() if only_apples else []) + (food_jobs() if 'comidas' in ARGS.partes and 'sprites' not in ARGS.partes else []) + (character_jobs() if 'personagem' in ARGS.partes else [])
         + (avatar_jobs() if 'avatares' in ARGS.partes else []))
    results = {}
    with Pool(os.cpu_count()) as p:
        for i, (path, group, img) in enumerate(p.imap_unordered(work, J)):
            results[path] = (group, img)
            print(f'{i + 1}/{len(J)} {path}', flush=True)

    clipped = [path for path, (_, img) in results.items() if touches_edge(img[..., 3])]
    if clipped:
        sys.exit(f'Sprites encostando na borda do canvas (aumente BIG ou ui.MARGIN): {clipped}')

    for path, (g, img) in results.items():
        if g in ('ui', 'escudo'):
            save(path, img)
        elif g == 'avatar':                 # cada retrato recortado no próprio contorno
            x0, y0, x1, y1 = crop_box([img])
            save(path, img[y0:y1, x0:x1])
    character, villain = save_character(results), save_character(results, evil=True)
    if 'sprites' not in ARGS.partes:
        with open(os.path.join(OUT, 'manifest.json'), encoding='utf-8') as f:
            man = json.load(f)
        if only_skins or only_apples:       # recorta no canvas de objetos que o jogo já usa
            (w, h), (ax, ay) = man['objeto']['tamanho'], man['objeto']['ancora']
            x0, y0 = BIG['objeto']['ox'] - ax, BIG['objeto']['oy'] - ay
            for path, (g, img) in results.items():
                if g != 'objeto':
                    continue
                outside = img[..., 3].copy()
                outside[y0:y0 + h, x0:x0 + w] = 0
                if outside.any():
                    sys.exit(f'{path} não cabe no canvas atual dos objetos: refaça com --partes sprites')
                save(path, img[y0:y0 + h, x0:x0 + w])
            if only_skins:
                man['skins'] = skins_manifest()
            if only_apples:
                man['comida_para_tema'] = food_to_theme()
        if 'ui' in ARGS.partes:
            man['ui'] = ui_manifest()
        if 'escudos' in ARGS.partes:
            man['ranque'] = shield_manifest()
        if character:
            man['personagem'] = character
        if villain:
            man['personagem_mal'] = villain
        with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as f:
            json.dump(man, f, indent=2, ensure_ascii=False)
        print(f'ok: {len(J)} imagens ({", ".join(ARGS.partes)}) em {os.path.normpath(OUT)} ({time.time() - t0:.0f} s)')
        return

    canvas = {}
    for group, cv in BIG.items():
        if group == 'personagem':           # o duende tem canvas próprio (save_character)
            continue
        x0, y0, x1, y1 = crop_box([img for g, img in results.values() if g == group])
        canvas[group] = dict(w=int(x1 - x0), h=int(y1 - y0), ox=int(cv['ox'] - x0), oy=int(cv['oy'] - y0))
        for path, (g, img) in results.items():
            if g == group:
                save(path, img[y0:y1, x0:x1])

    ob = canvas['objeto']
    shadow(ob['w'], ob['h'], ob['ox'], ob['oy']).save(os.path.join(OUT, 'sombra.png'))

    bg = {'classico': '#a9dcf2', 'rosa': '#ffe1ea', 'rosquinha': '#fbe3f4', 'esquilo': '#f2dcb8', 'caracol': '#c8d3f0',
          'coracao': '#3d1a52', 'caixa': '#e9ddff', 'queimado': '#57504d'}
    man = {
        'px_por_unidade': round(float(PPU), 3),
        'tile_px': TILE_PX,
        'projecao': dict(projection(), nota='tela = origem + gx * projecao.gx + gy * projecao.gy; '
                                            'desenhe em ordem crescente de gx * profundidade[0] + gy * profundidade[1]'),
        'objeto': {'tamanho': [ob['w'], ob['h']], 'ancora': [ob['ox'], ob['oy']],
                   'nota': 'ancora = pixel que fica no centro do tile, no chao (vale para cobra, comida, props, cercas e sombra)'},
        'tile': {'tamanho': [canvas['tile']['w'], canvas['tile']['h']], 'ancora': [canvas['tile']['ox'], canvas['tile']['oy']],
                 'nota': 'ancora = centro da face de cima'},
        'cerca': {'pecas': list(fc.PIECES), 'arquivo': '<tema>/cerca_<peca>.png',
                  'nota': 'cada peca ocupa uma celula; os bracos vao do centro ate a borda da celula'},
        'direcoes': {'E': '+gx', 'S': '+gy', 'W': '-gx', 'N': '-gy'},
        'temas': {t: {'fundo': bg[t]} for t in m.THEMES},
        # cada comida troca a cobra e o cenário para um tema; a maçã volta para o clássico
        'comida_para_tema': food_to_theme(),
        # skins da cobra para o tema padrão (a 'classica' são os sprites normais do tema classico)
        'skins': skins_manifest(),
        # a bomba não é comida: aparece de vez em quando e, se a cobra pegar, troca para o tema queimado
        'bomba': {'arquivo': 'comidas/bomba.png', 'tema': 'queimado'},
    }
    old = {}
    if os.path.exists(os.path.join(OUT, 'manifest.json')):      # partes não refeitas: mantém o que já existe
        with open(os.path.join(OUT, 'manifest.json'), encoding='utf-8') as f:
            old = json.load(f)
    for key, part, make in (('ui', 'ui', ui_manifest), ('ranque', 'escudos', shield_manifest),
                            ('personagem', 'personagem', lambda: character),
                            ('personagem_mal', 'personagem', lambda: villain)):
        if part in ARGS.partes:
            man[key] = make()
        elif key in old:
            man[key] = old[key]
    if CAMERA == '34':
        man['direcoes'] = {'E': '+gx (direita)', 'S': '+gy (baixo)', 'W': '-gx (esquerda)', 'N': '-gy (cima)'}
    with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(man, f, indent=2, ensure_ascii=False)
    print(f'ok: {len(J)} sprites em {os.path.normpath(OUT)} ({time.time() - t0:.0f} s)')
    print('canvas:', canvas)


if __name__ == '__main__':
    main()
