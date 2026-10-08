"""Carregamento dos sprites. Precisa de uma janela aberta (convert_alpha)."""
import os

import pygame

from . import config
from .logic import DIRS
from .manifest import SPRITES_DIR


class Assets:
    def __init__(self, manifest, base=SPRITES_DIR):
        self.manifest = manifest
        self.base = base
        self.spr = {t: self._load_theme(t) for t in manifest.themes}   # tema -> nome -> imagem
        self.food_img = {f: self._load(f'comidas/{f}.png') for f in manifest.foods}
        if os.path.exists(os.path.join(base, 'comidas', 'caixa.png')):      # presentes da live que não existem
            self.food_img['caixa'] = self._load('comidas/caixa.png')
        self.shadow = self._load('sombra.png')
        self.bomb = self._load('comidas/bomba.png') if manifest.bomb_theme else None
        # duende que joga os presentes: character['segura'] etc. (vazio se a pasta de sprites não tem)
        poses = manifest.character['poses'] if manifest.character else ()
        self.character = {p: self._load(f'personagem/{p}.png') for p in poses}
        poses = manifest.villain['poses'] if manifest.villain and self.bomb is not None else ()
        self.villain = {p: self._load(f'personagem/mal_{p}.png') for p in poses}     # o do mal, que joga as bombas
        # escudos chapados da interface nova (os mesmos do perfil): shields['ferro'] etc.
        shield = os.path.join(config.UI_DIR, 'escudos', 'escudo_{}.png')
        self.shields = {t: pygame.image.load(shield.format(t)).convert_alpha()
                        for t, *_ in config.RANQUE_LIGAS if os.path.exists(shield.format(t))}
        # skins da cobra (a 'classica' usa os sprites do tema): skins[nome]['cabeca_E'] etc.
        self.skins = {name: self._load_skin(name) for name in manifest.skins if name != 'classica'}
        # retratos das skins em alta resolução (perfil, pausa, skin liberada); sem o arquivo, a cabeça do jogo
        self.avatars = {}
        for name in manifest.skins:
            path = os.path.join(base, 'avatares', f"{'classico' if name == 'classica' else name}.png")
            if os.path.exists(path):
                self.avatars[name] = pygame.image.load(path).convert_alpha()
            else:
                self.avatars[name] = self.spr['classico']['cabeca_S'] if name == 'classica' else self.skins[name]['cabeca_S']

    def _load(self, path):
        return pygame.image.load(os.path.join(self.base, path)).convert_alpha()

    def _load_skin(self, name):
        s = {}
        for d in DIRS:
            s[f'cabeca_{d}'] = self._load(f'skins/{name}/cabeca_{d}.png')
            s[f'cauda_{d}'] = self._load(f'skins/{name}/cauda_{d}.png')
        for v in (0, 1):
            s[f'corpo_{v}'] = self._load(f'skins/{name}/corpo_{v}.png')
            for d in DIRS:                  # skins com barbatana têm um corpo por direção (corpo_<v>_<dir>)
                if os.path.exists(os.path.join(self.base, f'skins/{name}/corpo_{v}_{d}.png')):
                    s[f'corpo_{v}_{d}'] = self._load(f'skins/{name}/corpo_{v}_{d}.png')
        return s

    def _load_theme(self, t):
        s = {}
        for d in DIRS:
            s[f'cabeca_{d}'] = self._load(f'{t}/cabeca_{d}.png')
            s[f'cauda_{d}'] = self._load(f'{t}/cauda_{d}.png')
        for v in (0, 1):
            s[f'corpo_{v}'] = self._load(f'{t}/corpo_{v}.png')
            s[f'tile_{v}'] = self._load(f'{t}/tile_{v}.png')
            s[f'prop_{v}'] = self._load(f'{t}/prop_{v}.png')
        for piece in self.manifest.fence_pieces:
            s[f'cerca_{piece}'] = self._load(f'{t}/cerca_{piece}.png')
        return s
