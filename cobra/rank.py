"""Ranque (elo) por arena: ligas, divisões e PDL. Não depende do pygame.

Ferro IV -> Ferro I -> Bronze IV -> ... -> Diamante I -> Mestre. Cada divisão pede
RANQUE_PDL_DIVISAO PDL; o Mestre não tem divisões e acumula PDL.

Vitória (bateu a meta da liga):
    base da liga + % acima da meta + minutos jogados x presentes
    (% acima da meta = (pontos - meta) / meta x 100: meta 315 e 800 pontos = 154% = +154 PDL)
Derrota:
    -(base da liga + % que faltou para a meta) + minutos jogados x presentes
    (se o tempo x presentes for maior que a perda, o total fica positivo e o jogador ganha esses PDL)
    (% que faltou = (meta - pontos) / meta x 100: meta 150 e 120 pontos = 20% = -20 PDL)
    (o tempo x presentes só diminui a perda: derrota nunca dá PDL)
Nos dois casos: -RANQUE_PDL_POR_BOMBA por bomba e o bônus por entrar nos recordes da arena.

Quedas: com PDL acima de 0, a derrota para no 0. Só quem já está com 0 e perde cai uma divisão
(ficando com 100 - a perda, nunca menos de 0). Ninguém cai de liga: do Bronze IV não se volta
ao Ferro, e o Mestre não volta ao Diamante.
"""
import math
import os
from collections import namedtuple

from . import config, storage
from .logic import apple_weights, points_for

Rank = namedtuple('Rank', 'tier division pdl')      # tier = índice em RANQUE_LIGAS; division 4..1 (0 no Mestre)
START = Rank(0, config.RANQUE_DIVISOES, 0)

# step: um trecho da animação da barra: (elo mostrado, PDL de, PDL até, evento ao terminar: 'sobe'/'cai'/None)
Step = namedtuple('Step', 'rank pdl_from pdl_to event')
# diff = pontos - meta; margin = parte do PDL que vem dessa diferença (+ % acima da meta / - % que faltou);
# minutes x gifts = time_bonus
Outcome = namedtuple('Outcome', 'arena won score target base gifts diff margin minutes time_bonus '
                                 'bombs bomb_penalty record_pos record_bonus delta before after steps xp')

ROMAN = {4: 'IV', 3: 'III', 2: 'II', 1: 'I', 0: ''}


def tier_id(r):
    return config.RANQUE_LIGAS[r.tier][0]


def is_top(r):
    return r.tier == len(config.RANQUE_LIGAS) - 1


def food_value(tier, arena):
    """Valor médio de uma comida (antes do tamanho) numa partida desse elo: maçãs do elo pelos pesos (a
    comum, as automáticas a mais e as que os presentes espalham); numa fração das vezes é um presente, que vale
    a maçã mais cara do elo + o valor dele (os presentes que aparecem sozinhos, e às vezes a caixa)."""
    weights = apple_weights(tier)
    apple = sum(points_for(a) * w for a, w in weights.items()) / sum(weights.values())
    kinds = sorted(set(config.LIVE_PRESENTES.values()))
    gift_value = (1 - config.CAIXA_CHANCE_OFFLINE) * sum(points_for(k) for k in kinds) / len(kinds) \
        + config.CAIXA_CHANCE_OFFLINE * config.CAIXA_ITENS_OFFLINE
    gift = max(points_for(a) for a in weights) + gift_value
    g = config.RANQUE_PRESENTES_POR_COMIDA.get(arena, 0.05)
    return (1 - g) * apple + g * gift


def target(r, arena):
    """Pontos para vencer a partida: os pontos esperados comendo as comidas da meta da liga (mais na arena
    maior). Como cada comida vale valor x tamanho, depois de k comidas são ≈ valor médio x (k x inicial +
    k(k+1)/2). Arredondada de 10 em 10 (de 50 em 50 a partir de 1000)."""
    k = config.RANQUE_LIGAS[r.tier][1] * config.RANQUE_ARENA.get(arena, 1.0)
    pts = food_value(r.tier, arena) * (k * config.TAMANHO_INICIAL + k * (k + 1) / 2)
    step = 50 if pts >= 1000 else 10
    return int(round(pts / step) * step)


def order(r):
    """Número que cresce com o elo (para comparar: Ferro IV < Ferro III < ... < Mestre)."""
    return r.tier * (config.RANQUE_DIVISOES + 1) + (config.RANQUE_DIVISOES - r.division if not is_top(r) else 0)


def promote(r):
    if r.division > 1:
        return Rank(r.tier, r.division - 1, 0)
    nxt = r.tier + 1
    return Rank(nxt, 0 if nxt == len(config.RANQUE_LIGAS) - 1 else config.RANQUE_DIVISOES, 0)


def demote(r):
    """Uma divisão abaixo, sem sair da liga (None no IV de cada liga e no Mestre)."""
    if is_top(r) or r.division >= config.RANQUE_DIVISOES:
        return None
    return Rank(r.tier, r.division + 1, 0)


def round_pdl(x):
    """Arredonda meio para cima (2,5 -> 3), como se espera de pontos; o round do Python daria 2."""
    return math.floor(x + 0.5)


def record_bonus(record_pos):
    """PDL por entrar nos recordes: +10 no #1, +8 no #2 ... +2 no #5 (record_pos 0 = 1º; None = não entrou)."""
    if record_pos is None:
        return 0
    return max(0, config.RANQUE_BONUS_RECORDE - config.RANQUE_BONUS_RECORDE_PASSO * record_pos)


def apply_match(r, score, gifts, arena, play_time=0.0, bombs=0, record_pos=None):
    """Resultado da partida no ranque: novo elo e os trechos para animar a barra de PDL."""
    tgt = target(r, arena)
    won = score >= tgt
    full = config.RANQUE_PDL_DIVISAO
    base = config.RANQUE_LIGAS[r.tier][2]
    diff = score - tgt
    minutes = play_time / 60
    time_bonus = round_pdl(minutes * gifts * config.RANQUE_TEMPO_X_PRESENTES)
    bomb_penalty = bombs * config.RANQUE_PDL_POR_BOMBA
    rec_bonus = record_bonus(record_pos)
    if won:
        margin = round_pdl(diff / tgt * 100)                # % acima da meta
        delta = max(0, base + margin + time_bonus - bomb_penalty + rec_bonus)
    else:
        margin = -round_pdl(-diff / tgt * 100)              # negativo: a % que faltou para a meta
        base = -base
        delta = base + margin + time_bonus - bomb_penalty + rec_bonus      # pode dar positivo: ganha os PDL

    steps, cur, start = [], r, r.pdl
    if delta >= 0:
        pdl = r.pdl + delta
        while pdl >= full and not is_top(cur):              # sobe (pode passar mais de uma divisão)
            steps.append(Step(cur, start, full, 'sobe'))
            cur, pdl, start = promote(cur), pdl - full, 0
        steps.append(Step(cur, start, pdl, None))
    elif r.pdl > 0:                                         # tinha PDL: perde até o 0, sem cair
        pdl = max(0, r.pdl + delta)
        steps.append(Step(cur, start, pdl, None))
    else:                                                   # já estava no 0: cai uma divisão (na mesma liga)
        lower = demote(cur)
        if lower is None:                                   # IV da liga (ou Mestre): fica no 0
            pdl = 0
            steps.append(Step(cur, 0, 0, None))
        else:
            pdl = max(0, full + delta)
            steps.append(Step(cur, 0, 0, 'cai'))
            cur = lower
            steps.append(Step(cur, full, pdl, None))
    after = Rank(cur.tier, cur.division, pdl)
    xp = match_xp(r, score, gifts, arena, play_time, bombs, record_pos)
    return Outcome(arena, won, score, tgt, base, gifts, diff, margin, minutes, time_bonus, bombs, bomb_penalty,
                   record_pos, rec_bonus, delta, r, after, steps, xp)


def match_xp(r, score, gifts, arena, play_time=0.0, bombs=0, record_pos=None):
    """XP da partida (para o nível do perfil): o cálculo da vitória, mas com os pontos inteiros.

    base da liga + pontos / meta x 100 (a % da meta que fez) + minutos x presentes - bombas + recorde;
    nunca negativo, então ganhando ou perdendo o jogador sempre ganha XP.
    """
    base = config.RANQUE_LIGAS[r.tier][2]
    time_bonus = round_pdl(play_time / 60 * gifts * config.RANQUE_TEMPO_X_PRESENTES)
    return max(0, base + round_pdl(score / target(r, arena) * 100) + time_bonus
               - bombs * config.RANQUE_PDL_POR_BOMBA + record_bonus(record_pos))


# ---------------------------------------------------------------- arquivo
def default_path():
    return os.path.join(storage.data_dir(), 'ranque.json')


def load(path):
    """{arena: Rank}. Arena sem registro começa no Ferro IV."""
    data = storage.read_json(path)
    data = data if isinstance(data, dict) else {}
    ids = [t[0] for t in config.RANQUE_LIGAS]
    out = {}
    for arena in config.ARENAS:
        d = data.get(str(arena))
        try:
            tier = ids.index(d['liga'])
            division = 0 if tier == len(ids) - 1 else max(1, min(config.RANQUE_DIVISOES, int(d['divisao'])))
            out[arena] = Rank(tier, division, max(0, int(d['pdl'])))
        except (TypeError, KeyError, ValueError):
            out[arena] = START
    return out


def save(path, ranks):
    storage.write_json(path, {str(a): {'liga': tier_id(r), 'divisao': r.division, 'pdl': r.pdl}
                              for a, r in sorted(ranks.items())})
