"""Versões sem texto dos botões JOGAR da interface chapada (assets/ui), para o jogo escrever o texto traduzido.

    python menu_buttons.py

Os botões originais (ui/botoes/jogar_capa_*.png e jogar_card_*.png) têm "JOGAR" desenhado na imagem;
em português o jogo usa os originais, nos outros idiomas usa estas versões (mesmo tamanho, cor
e cantos, mas sem o ícone e o texto). Mesmo desenho de btn_primary em tools/ui/ui_flat.py.
"""
import os

from PIL import Image, ImageDraw

UI = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'ui')
OUT = os.path.join(UI, 'botoes')
K = 4                                                                    # supersampling, como no ui_flat.py
PINK = {'normal': (255, 61, 139), 'hover': (255, 92, 160), 'pressionado': (224, 38, 116)}
BUTTONS = {'jogar_capa': (320, 64, 14), 'jogar_card': (322, 50, 12)}    # largura, altura, raio


def blank(w, h, radius, state):
    im = Image.new('RGBA', (w * K, h * K), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w * K - 1, h * K - 1), radius=radius * K, fill=PINK[state] + (255,))
    return im.resize((w, h), Image.LANCZOS)


if __name__ == '__main__':
    for name, (w, h, r) in BUTTONS.items():
        for st in PINK:
            blank(w, h, r, st).save(os.path.join(OUT, f'{name}_vazio_{st}.png'))
    print('ok')
