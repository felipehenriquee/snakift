"""Leitura do manifest.json dos sprites. Não depende do pygame."""
import json
import os
from dataclasses import dataclass, field

from . import config

SPRITES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), config.SPRITES)


def hex_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


@dataclass(frozen=True)
class Manifest:
    axis_gx: tuple          # deslocamento na tela (px) de um passo em gx
    axis_gy: tuple          # deslocamento na tela (px) de um passo em gy
    depth_w: tuple          # profundidade = gx * depth_w[0] + gy * depth_w[1] (maior = mais perto da câmera)
    obj_size: tuple         # canvas dos objetos (cobra, comida, props, cercas, sombra)
    obj_anchor: tuple       # pixel do objeto que fica no centro do tile, no chão
    tile_size: tuple
    tile_anchor: tuple      # pixel do tile que fica no centro da face de cima
    fence_pieces: tuple     # peças de cerca disponíveis (vazio se a pasta não tem cerca)
    backgrounds: dict       # tema -> cor de fundo (r, g, b)
    food_to_theme: dict     # comida -> tema que ela ativa
    ui_panels: dict = field(default_factory=dict)   # 'placar'/'fim' -> {'size', 'anchor', 'area'}; vazio = sem painéis
    ui_colors: dict = field(default_factory=dict)   # tema -> (cor do texto, cor de destaque)
    bomb_theme: str = None  # tema ao pegar a bomba (None = pasta de sprites sem bomba)
    rank_tiers: tuple = ()  # ligas com escudo em ranque/escudo_<liga>.png (vazio = sem escudos)
    skins: tuple = ('classica',)    # skins da cobra no tema padrão; 'classica' = os sprites do tema
    character: dict = None  # duende que joga os presentes: {'poses', 'size', 'anchor', 'hand': {pose: (x, y)}}
    villain: dict = None    # duende do mal, que joga as bombas (mesmo formato)

    @property
    def themes(self):
        return list(self.backgrounds)

    @property
    def foods(self):
        return list(self.food_to_theme)

    def depth(self, gx, gy):
        return gx * self.depth_w[0] + gy * self.depth_w[1]


def load_manifest(base=SPRITES_DIR):
    with open(os.path.join(base, 'manifest.json'), encoding='utf-8') as f:
        man = json.load(f)
    return Manifest(
        axis_gx=tuple(man['projecao']['gx']),
        axis_gy=tuple(man['projecao']['gy']),
        depth_w=tuple(man['projecao']['profundidade']),
        obj_size=tuple(man['objeto']['tamanho']),
        obj_anchor=tuple(man['objeto']['ancora']),
        tile_size=tuple(man['tile']['tamanho']),
        tile_anchor=tuple(man['tile']['ancora']),
        fence_pieces=tuple(man.get('cerca', {}).get('pecas', ())),
        backgrounds={t: hex_rgb(v['fundo']) for t, v in man['temas'].items()},
        food_to_theme=dict(man['comida_para_tema']),
        ui_panels={k: {'size': tuple(v['tamanho']), 'anchor': tuple(v['ancora']), 'area': tuple(v['area'])}
                   for k, v in man.get('ui', {}).items() if isinstance(v, dict) and 'area' in v},
        ui_colors={t: (hex_rgb(c['texto']), hex_rgb(c['destaque'])) for t, c in man.get('ui', {}).get('cores', {}).items()},
        bomb_theme=man.get('bomba', {}).get('tema'),
        rank_tiers=tuple(man.get('ranque', {}).get('ligas', ())),
        skins=tuple(man.get('skins', {}).get('lista', ('classica',))),
        character=_character(man.get('personagem')),
        villain=_character(man.get('personagem_mal')),
    )


def _character(d):
    if not isinstance(d, dict):
        return None
    sign = d.get('placa')
    return {'poses': tuple(d['poses']), 'size': tuple(d['tamanho']), 'anchor': tuple(d['ancora']),
            'hand': {p: tuple(v) for p, v in d['mao'].items()},
            'sign': (tuple(sign['centro']), tuple(sign['tamanho'])) if isinstance(sign, dict) else None}
