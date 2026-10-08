"""Skins liberadas pelo elo. Não depende do pygame.

Cada skin de metal é liberada quando o jogador chega à liga de mesmo nome em qualquer arena
(config.SKIN_ELO); a clássica e as que não estão na tabela já começam liberadas. O maior elo
já alcançado vem do perfil (o maior elo de cada arena) e do elo atual.
"""
from . import config

LEAGUES = [liga for liga, *_ in config.RANQUE_LIGAS]


def required_tier(skin):
    """Índice da liga que libera a skin (0 = já começa liberada, ou está em config.SKINS_LIBERADAS)."""
    if skin in config.SKINS_LIBERADAS:
        return 0
    liga = config.SKIN_ELO.get(skin)
    return LEAGUES.index(liga) if liga in LEAGUES else 0


def best_tier(profile_data=None, ranks=None):
    """Maior liga já alcançada em qualquer arena (pelo maior elo do perfil e pelo elo atual)."""
    tiers = [0]
    if profile_data:
        tiers += [s['pico'].tier for s in profile_data['arenas'].values() if s.get('pico') is not None]
    if ranks:
        tiers += [r.tier for r in ranks.values()]
    return max(tiers)


def is_unlocked(skin, tier):
    return required_tier(skin) <= tier


def newly_unlocked(skins, tier_before, tier_after):
    """Skins liberadas ao passar da liga tier_before para tier_after, da mais fraca para a mais forte."""
    new = [s for s in skins if tier_before < required_tier(s) <= tier_after]
    return sorted(new, key=required_tier)
