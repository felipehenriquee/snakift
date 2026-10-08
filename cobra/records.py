"""Recordes: uma tabela com os 5 melhores para cada arena e cada elo, salva em JSON. Não depende do pygame.

No arquivo: {"por_arena_elo": {"11": {"bronze": [...], "prata": [...]}, "15": {...}}, "ultimo_nome": "..."}.
Na memória: {'tabelas': {(arena, liga): [...]}, 'ultimo_nome': str}. O elo é o da arena no começo da partida.
Formatos antigos (por arena, ou uma tabela só) vão para o Ferro de cada arena, porque não guardavam o elo.
"""
import getpass
import os
import time

from . import config, storage

MAX_RECORDS = 5
MAX_SUPPORTERS = 10     # recordes de quem mais mandou presentes nas lives (soma de todas as partidas)
FIRST_LEAGUE = config.RANQUE_LIGAS[0][0]
MAX_NAME = 25         # cabe um @ do TikTok inteiro (o @ + 24)


def default_path():
    """Arquivo de recordes na pasta de dados do usuário (fica fora do projeto)."""
    return os.path.join(storage.data_dir(), 'recordes.json')


def default_name():
    try:
        name = getpass.getuser()
    except Exception:
        name = ''
    return (name or 'jogador')[:MAX_NAME]


def _valid(r):
    return isinstance(r, dict) and isinstance(r.get('pontos'), int) and isinstance(r.get('nome'), str)


def load(path):
    """Devolve {'tabelas': {(arena, liga): [recordes]}, 'ultimo_nome': str}. Ausente ou estragado = tudo vazio."""
    data = storage.read_json(path)
    if not isinstance(data, dict):
        return {'tabelas': {}, 'ultimo_nome': default_name(), 'doadores': []}
    leagues = [liga for liga, *_ in config.RANQUE_LIGAS]
    tables = {}
    if isinstance(data.get('por_arena_elo'), dict):
        for key, by_league in data['por_arena_elo'].items():
            if str(key).isdigit() and isinstance(by_league, dict):
                for liga, recs in by_league.items():
                    if liga in leagues and isinstance(recs, list):
                        tables[int(key), liga] = [r for r in recs if _valid(r)]
    elif isinstance(data.get('por_arena'), dict):                    # formato antigo, por arena: vai para o Ferro
        for key, recs in data['por_arena'].items():
            if str(key).isdigit() and isinstance(recs, list):
                tables[int(key), FIRST_LEAGUE] = [r for r in recs if _valid(r)]
    elif isinstance(data.get('recordes'), list):                     # mais antigo: uma tabela só
        for r in filter(_valid, data['recordes']):
            arena = r.get('arena', config.N)
            tables.setdefault((arena if isinstance(arena, int) else config.N, FIRST_LEAGUE), []).append(r)
    for key, recs in tables.items():                                 # ordem e limite garantidos
        recs.sort(key=lambda r: -r['pontos'])                        # sort é estável: empates mantêm a ordem
        tables[key] = recs[:MAX_RECORDS]
    return {'tabelas': tables, 'ultimo_nome': str(data.get('ultimo_nome') or default_name()),
            'doadores': _supporters(data.get('doadores'))}


def _supporters(raw):
    """[{'usuario', 'nome', 'foto', 'moedas'}] válidos, do maior para o menor."""
    out = [s for s in (raw if isinstance(raw, list) else [])
           if isinstance(s, dict) and isinstance(s.get('usuario'), str) and isinstance(s.get('moedas'), int)]
    out.sort(key=lambda s: -s['moedas'])
    return out[:MAX_SUPPORTERS]


def add_supporters(data, tributes):
    """Soma os presentes de uma partida (live.Tribute: user, nickname, avatar, coins) aos recordes de doadores."""
    by_user = {s['usuario']: dict(s) for s in data.get('doadores', [])}
    for tb in tributes:
        if not tb.user or tb.coins <= 0:
            continue
        cur = by_user.setdefault(tb.user, {'usuario': tb.user, 'nome': tb.nickname or tb.user, 'foto': None, 'moedas': 0})
        cur['moedas'] += int(tb.coins)
        cur['foto'] = tb.avatar or cur.get('foto')
        cur['nome'] = tb.nickname or cur['nome']
    data['doadores'] = _supporters(list(by_user.values()))
    return data


def save(path, data):
    """data: {'tabelas': {(arena, liga): [...]}, 'ultimo_nome': str}."""
    out = {}
    for (arena, liga), recs in sorted(data['tabelas'].items()):
        if recs:
            out.setdefault(str(arena), {})[liga] = recs
    storage.write_json(path, {'por_arena_elo': out, 'ultimo_nome': data['ultimo_nome'],
                              'doadores': data.get('doadores', [])})


def table(data, arena, liga):
    """Os recordes daquela arena naquele elo (lista vazia se ainda não tem)."""
    return data['tabelas'].get((arena, liga), [])


def best(data):
    """Maior pontuação de todas as tabelas (0 sem recordes)."""
    return max((recs[0]['pontos'] for recs in data['tabelas'].values() if recs), default=0)


def qualifies(recs, score):
    """A pontuação entra na tabela? (zero nunca entra)"""
    if score <= 0:
        return False
    return len(recs) < MAX_RECORDS or score > recs[-1]['pontos']


def position(recs, score):
    """Posição (0 = 1º) em que a pontuação entraria na tabela, ou None se não entra."""
    if not qualifies(recs, score):
        return None
    return next((i for i, r in enumerate(recs) if score > r['pontos']), len(recs))


def add(recs, name, score, play_time, arena=None, liga=None):
    """Nova tabela com a partida inserida (empate: quem fez antes fica na frente) e a posição dela (0 = 1º)."""
    entry = {'nome': name.strip()[:MAX_NAME] or default_name(), 'pontos': score,
             'tempo': round(play_time, 1), 'data': time.strftime('%Y-%m-%d %H:%M')}
    if arena is not None:
        entry['arena'] = arena
    if liga is not None:
        entry['elo'] = liga
    pos = next((i for i, r in enumerate(recs) if score > r['pontos']), len(recs))
    new = recs[:pos] + [entry] + recs[pos:]
    return new[:MAX_RECORDS], pos
