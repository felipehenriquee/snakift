"""Resetar a conta: apaga tudo o que foi jogado. Não depende do pygame.

Zera o elo (PDL) de todas as arenas, o perfil (nível, XP e estatísticas) e os recordes de pontos. Ficam o ranque de
quem mandou presentes nas lives, o nome do jogador e as configurações (som, idioma, live). As skins de elo voltam a
ficar bloqueadas, porque dependem do maior elo alcançado (quem chama devolve a skin equipada para a clássica).
"""
from . import config, profile, rank, records


def reset(records_path, rank_path, profile_path):
    data = records.load(records_path)
    data['tabelas'] = {}                        # recordes de pontos: somem; 'doadores' e 'ultimo_nome' ficam
    records.save(records_path, data)
    rank.save(rank_path, {arena: rank.START for arena in config.ARENAS})
    profile.save(profile_path, {'arenas': {arena: profile.empty_stats() for arena in config.ARENAS}})
