"""Configurações do jogador: idioma, último tamanho de arena, skin, som... Não depende do pygame."""
import os

from . import config, i18n, storage

VOLUMES = {'geral': 'volume', 'musica': 'volume_musica', 'efeitos': 'volume_efeitos'}   # controle -> chave
VOLUME_MAX = 10             # cada volume vai de 0 (mudo) a 10 (100%), de 10 em 10%


def _volume(data, key, legacy=None):
    """Volume salvo (0..10); sem ele, 10, ou 0 se a opção antiga de ligar/desligar (legacy) estava desligada."""
    v = data.get(key)
    if isinstance(v, int) and not isinstance(v, bool):
        return min(max(v, 0), VOLUME_MAX)
    return 0 if legacy is not None and data.get(legacy) is False else VOLUME_MAX


def volume_action(prefs, action):
    """Ações 'vol_<geral|musica|efeitos>_<up|down>' dos botões − e +. Devolve True se era uma delas."""
    parts = action.split('_') if isinstance(action, str) else []
    if len(parts) != 3 or parts[0] != 'vol' or parts[1] not in VOLUMES or parts[2] not in ('up', 'down'):
        return False
    key = VOLUMES[parts[1]]
    prefs[key] = min(max(prefs.get(key, VOLUME_MAX) + (1 if parts[2] == 'up' else -1), 0), VOLUME_MAX)
    return True


def player_name(prefs, saved_name):
    """Nome do jogador: no modo live, o @ da live; senão, o nome salvo (records 'ultimo_nome')."""
    user = (prefs.get('tiktok') or '').strip().lstrip('@')
    return '@' + user if prefs.get('modo') == 'live' and user else saved_name


def default_path():
    return os.path.join(storage.data_dir(), 'configuracoes.json')


def load(path):
    """{'idioma', 'arena', 'skin', 'cenario_muda', 'cobra_muda', 'volume', 'volume_musica', 'volume_efeitos',
    'modo', 'tiktok', 'live_bomba', 'live_ligados'}.

    volume (geral), volume_musica e volume_efeitos: de 0 (mudo) a VOLUME_MAX.

    modo: 'offline' ou 'live' (presentes da live do TikTok); tiktok: o @ da live; live_bomba: presente da live
    que vira bomba; live_ligados: presentes da live que viram eles mesmos (None = os que têm visual no jogo; os outros
    viram a caixa de presente).

    Sem arquivo: idioma do sistema, arena padrão, skin clássica e as duas trocas de tema ligadas.
    """
    data = storage.read_json(path)
    data = data if isinstance(data, dict) else {}
    lang, arena, skin = data.get('idioma'), data.get('arena'), data.get('skin')
    return {'idioma': lang if lang in i18n.LANGUAGES else i18n.detect_language(),
            'arena': arena if arena in config.ARENAS else config.N,
            'skin': skin if isinstance(skin, str) and skin else 'classica',
            'cenario_muda': data.get('cenario_muda') is not False,
            'cobra_muda': data.get('cobra_muda') is not False,
            'mostrar_fps': data.get('mostrar_fps') is True,     # contador de FPS no canto (tecla F3)
            'volume': _volume(data, 'volume'),
            'volume_musica': _volume(data, 'volume_musica', legacy='musica'),
            'volume_efeitos': _volume(data, 'volume_efeitos', legacy='efeitos'),
            'modo': 'live' if data.get('modo') == 'live' else 'offline',
            'tiktok': data.get('tiktok') if isinstance(data.get('tiktok'), str) else '',
            'live_bomba': data.get('live_bomba') if isinstance(data.get('live_bomba'), str) else config.LIVE_BOMBA_PADRAO,
            'live_ligados': [n for n in data['live_ligados'] if isinstance(n, str)]
            if isinstance(data.get('live_ligados'), list) else None}


def save(path, data):
    storage.write_json(path, data)
