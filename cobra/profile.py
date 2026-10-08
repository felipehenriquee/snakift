"""Perfil do jogador: estatísticas por arena, maior elo e nível. Não depende do pygame.

Arquivo perfil.json na pasta de dados:
{"arenas": {"11": {"partidas", "vitorias", "derrotas", "presentes", "pontos", "tempo", "melhor", "xp", "pico"}}}
Vitória/derrota = bateu ou não a meta do ranque. O nível vem do XP: cada partida dá o XP de
rank.match_xp (o cálculo do PDL com os pontos inteiros, então sempre ganha). Perfis antigos, sem
"xp" no arquivo, começam com o XP que tinham (a soma dos pontos), para ninguém perder o nível.
"""
import os

from . import config, rank, storage

XP_PER_LEVEL = 500
FIELDS = ('partidas', 'vitorias', 'derrotas', 'presentes', 'pontos', 'tempo', 'melhor', 'xp')


def default_path():
    return os.path.join(storage.data_dir(), 'perfil.json')


def empty_stats():
    return {'partidas': 0, 'vitorias': 0, 'derrotas': 0, 'presentes': 0, 'pontos': 0, 'tempo': 0.0, 'melhor': 0,
            'xp': 0, 'pico': None}


def _peak_from(d):
    """{'liga', 'divisao'} -> Rank (sem PDL), ou None."""
    ids = [t[0] for t in config.RANQUE_LIGAS]
    try:
        return rank.Rank(ids.index(d['liga']), int(d['divisao']), 0)
    except (TypeError, KeyError, ValueError):
        return None


def load(path):
    """{'arenas': {arena: estatísticas}}; o que faltar ou estiver estragado começa do zero."""
    data = storage.read_json(path)
    raw = data.get('arenas', {}) if isinstance(data, dict) else {}
    arenas = {}
    for arena in config.ARENAS:
        stats = empty_stats()
        src = raw.get(str(arena)) if isinstance(raw, dict) else None
        if isinstance(src, dict):
            for key in FIELDS:
                if isinstance(src.get(key), (int, float)) and src[key] >= 0:
                    stats[key] = src[key]
            if 'xp' not in src:                 # perfil de antes do XP próprio: mantém o nível que tinha
                stats['xp'] = stats['pontos']
            stats['pico'] = _peak_from(src.get('pico'))
        arenas[arena] = stats
    return {'arenas': arenas}


def save(path, data):
    out = {}
    for arena, s in sorted(data['arenas'].items()):
        d = {k: s[k] for k in FIELDS}
        d['tempo'] = round(d['tempo'], 1)
        d['pico'] = {'liga': rank.tier_id(s['pico']), 'divisao': s['pico'].division} if s['pico'] else None
        out[str(arena)] = d
    storage.write_json(path, {'arenas': out})


def record_match(data, arena, score, gifts, play_time, won, rank_after, xp=0):
    """Soma uma partida às estatísticas da arena (e atualiza o maior elo e o XP)."""
    s = data['arenas'].setdefault(arena, empty_stats())
    s['xp'] += xp
    s['partidas'] += 1
    s['vitorias' if won else 'derrotas'] += 1
    s['presentes'] += gifts
    s['pontos'] += score
    s['tempo'] += play_time
    s['melhor'] = max(s['melhor'], score)
    if rank_after is not None and (s['pico'] is None or rank.order(rank_after) > rank.order(s['pico'])):
        s['pico'] = rank.Rank(rank_after.tier, rank_after.division, 0)
    return data


def totals(data):
    t = {k: 0 for k in FIELDS}
    for s in data['arenas'].values():
        for k in FIELDS:
            t[k] = max(t[k], s[k]) if k == 'melhor' else t[k] + s[k]
    return t


def win_rate(stats):
    """Porcentagem de vitórias (0 sem partidas)."""
    return round(100 * stats['vitorias'] / stats['partidas']) if stats['partidas'] else 0


def level(data):
    """(nível, XP dentro do nível, XP por nível). Nível 1 com 0 XP."""
    xp = totals(data)['xp']
    return 1 + xp // XP_PER_LEVEL, xp % XP_PER_LEVEL, XP_PER_LEVEL
