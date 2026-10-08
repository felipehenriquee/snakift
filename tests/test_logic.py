import random
import unittest

from cobra import config
from cobra.logic import GameState, apple_weights, is_apple, points_for
from cobra.manifest import load_manifest

from cobra.logic import CAIXA, Bomb, BonusApple, Gift

FOOD_TO_THEME = {'rosa': 'rosa', 'rosquinha': 'rosquinha', 'esquilo': 'esquilo', 'caracol': 'caracol', 'maca': 'classico'}


def new_state(n=config.N):
    return GameState(FOOD_TO_THEME, n=n, rng=random.Random(0))


ALL_APPLES = dict(FOOD_TO_THEME, **{m: 'classico' for m in config.MACAS.values()})


class TestEloApples(unittest.TestCase):
    def test_iron_only_has_the_plain_apple(self):
        self.assertEqual(apple_weights(0), {'maca': 1.0})

    def test_each_previous_league_weighs_half(self):
        w = apple_weights(3)                                         # Ouro
        self.assertEqual(w, {'maca_ouro': 1.0, 'maca_prata': 0.5, 'maca_bronze': 0.25, 'maca': 0.125})

    def test_missing_sprites_are_skipped(self):
        self.assertEqual(apple_weights(2, available={'maca', 'maca_bronze'}), {'maca_bronze': 0.5, 'maca': 0.25})

    def test_apple_values_grow_5_by_5(self):
        values = [points_for(config.MACAS[liga]) for liga, *_ in config.RANQUE_LIGAS]
        self.assertEqual(values, [1, 5, 10, 15, 20, 25, 30, 35])

    def test_spawn_draws_apples_of_the_league_with_weights(self):
        s = GameState(ALL_APPLES, rng=random.Random(3), apple_tier=2)       # Prata
        seen = {}
        for _ in range(4000):
            s.spawn_food()
            seen[s.food_kind] = seen.get(s.food_kind, 0) + 1
        self.assertEqual(set(seen), {'maca_prata', 'maca_bronze', 'maca'})    # só maçãs, nada acima do elo
        self.assertAlmostEqual(seen['maca_prata'] / 4000, 4 / 7, delta=0.03)  # pesos 1 : 1/2 : 1/4
        self.assertAlmostEqual(seen['maca_bronze'] / 4000, 2 / 7, delta=0.03)

    def test_food_is_always_an_apple(self):
        s = GameState(ALL_APPLES, rng=random.Random(1), apple_tier=7)
        for theme in ('classico', 'rosa', 'esquilo'):
            s.theme = theme
            for _ in range(100):
                s.spawn_food()
                self.assertTrue(is_apple(s.food_kind))

    def test_elo_apple_is_worth_more_and_keeps_the_theme(self):
        s = GameState(ALL_APPLES, rng=random.Random(0), apple_tier=1)
        s.theme = 'esquilo'
        s.food, s.food_kind = (6, 5), 'maca_bronze'
        s.step()
        self.assertEqual((s.score, s.eaten, s.theme), (5 * 4, 0, 'esquilo'))   # uma maçã só não volta ao clássico

    def test_fifty_apples_in_a_row_bring_back_the_classic_theme(self):
        s = GameState(ALL_APPLES, rng=random.Random(0), apple_tier=1)
        s.theme = 'esquilo'
        s.apples_streak = config.MACAS_PARA_VOLTAR - 2
        self.assertEqual(s.apples_to_reset, 2)
        s.food, s.food_kind = (6, 5), 'maca'                                 # a de ferro não é mais especial
        s.step()
        self.assertEqual((s.theme, s.apples_to_reset), ('esquilo', 1))
        s.food, s.food_kind = (7, 5), 'maca_bronze'                          # qualquer elo conta
        s.step()
        self.assertEqual((s.old_theme, s.theme, s.apples_to_reset), ('esquilo', 'classico', 0))

    def test_a_gift_resets_the_count(self):
        s = GameState(ALL_APPLES, rng=random.Random(0), apple_tier=1)
        s.food = (0, 0)
        s.theme, s.apples_streak = 'rosa', config.MACAS_PARA_VOLTAR - 1
        s.gifts_on_board = on_board(((6, 5), 'esquilo', 0))
        s.step()
        self.assertEqual((s.theme, s.apples_streak, s.apples_to_reset), ('esquilo', 0, config.MACAS_PARA_VOLTAR))

    def test_burnt_apples_give_no_points_and_the_tenth_heals(self):
        s = GameState(ALL_APPLES, rng=random.Random(0), apple_tier=7)
        s.theme, s.slow_apples = 'queimado', config.MACAS_PARA_DESQUEIMAR - 2
        s.food, s.food_kind = (6, 5), 'maca_mestre'
        s.step()                                                             # 9ª: ainda queimada, sem pontos
        self.assertEqual((s.theme, s.score, s.apples_to_reset), ('queimado', 0, 1))
        s.food, s.food_kind = (7, 5), 'maca_mestre'
        s.step()                                                             # 10ª: volta ao normal
        self.assertEqual((s.theme, s.score), ('classico', 0))

    def test_a_gift_heals_the_burn(self):
        s = GameState(ALL_APPLES, rng=random.Random(0), apple_tier=7)
        s.theme, s.food = 'queimado', (0, 0)
        s.gifts_on_board = on_board(((6, 5), 'rosa', 0))
        s.step()
        self.assertEqual(s.theme, 'rosa')
        self.assertGreater(s.score, 0)                                       # o presente dá pontos

    def test_slow_snake_speeds_up_with_each_apple(self):
        s = GameState(ALL_APPLES, rng=random.Random(0), apple_tier=1)
        for theme in ('caracol', 'queimado'):
            s.theme, s.slow_apples = theme, 0
            slow = s.step_time
            s.slow_apples = config.MACAS_PARA_ACELERAR // 2
            self.assertLess(s.step_time, slow)                               # mais rápida a cada maçã
            s.slow_apples = config.MACAS_PARA_ACELERAR
            self.assertAlmostEqual(s.step_time, config.STEP[config.START_THEME])   # 10ª: velocidade normal


def on_board(*gifts):
    """Presentes já caídos e acomodados (prontos para pegar)."""
    return [Gift(cell, kind, None, value=value, settled=True) for cell, kind, value in gifts]


class TestGifts(unittest.TestCase):
    def test_items_landing_on_a_full_arena_never_hide_under_the_snake(self):
        s = GameState(FOOD_TO_THEME, n=3, rng=random.Random(0), live=True)
        s.snake = [(x, y) for y in range(3) for x in (range(3) if y % 2 == 0 else range(2, -1, -1))][:9]
        s.food = None
        s.bonus_apples = [BonusApple((1, 1), 'maca', (1, 1), 0.0, 0.0, None)]     # caiu em cima, sem casa livre
        s.gifts_on_board = [Gift((1, 0), 'rosa', None, 0.0, 0.0, 0, '@ana: Rosa')]
        s._update_gifts()
        self.assertEqual(s.bonus_apples, [])                                    # a maçã some
        self.assertEqual(s.gifts_on_board, [])                                  # o presente volta para a fila
        self.assertEqual([o.kind for o in s.pending], ['rosa'])

    def test_offline_gift_appears_after_interval_is_thrown_and_expires(self):
        s = new_state()
        s.food = (0, 0)
        s.snake = [(5, 10), (4, 10), (3, 10)]
        s.next_gift, s.next_bomb = 0.05, 999
        s.update(0.1)
        self.assertEqual(len(s.gifts_on_board), 1)
        g = s.gifts_on_board[0]
        self.assertIn(g.kind, ('rosa', 'rosquinha', 'esquilo', 'caracol'))
        self.assertNotIn(g.cell, s.snake + [s.food])
        self.assertAlmostEqual(g.lands - g.thrown, GameState.throw_time())
        self.assertAlmostEqual(g.expires - g.lands, config.PRESENTE_DURACAO)
        s.play_time = g.expires - config.PRESENTE_PISCA + 0.1               # sem andar a cobra
        self.assertTrue(s.blinking(g))
        s.play_time = g.expires
        s._update_gifts()
        self.assertEqual(s.gifts_on_board, [])

    def test_live_gifts_come_only_from_requests_and_do_not_expire(self):
        s = GameState(FOOD_TO_THEME, rng=random.Random(0), live=True)
        s.food = (0, 0)
        s.next_gift = 0.0
        s._update_gifts()
        self.assertEqual(s.gifts_on_board, [])                              # sem presente por tempo
        s.request_gift('rosa', label='@bia: Rosa')
        s._update_gifts()
        g = s.gifts_on_board[0]
        self.assertEqual((g.kind, g.label, g.expires), ('rosa', '@bia: Rosa', None))

    def test_thank_you_gnomes_walk_in_a_line(self):
        s = GameState(FOOD_TO_THEME, rng=random.Random(0), live=True)
        s._thank('bom', '@ana: Rosa')
        s._thank('bom', '@ana: Rosa')                       # o mesmo enquanto o dela anda: sem outro duende
        s._thank('bom', '@leo: Donut')
        s._thank('mal', '@bia: TikTok')                     # o do mal tem a fila dele
        self.assertEqual([(th.side, th.label, th.start) for th in s.thanks],
                         [('bom', '@ana: Rosa', 0.0), ('bom', '@leo: Donut', config.AGRADECIMENTO_INTERVALO),
                          ('mal', '@bia: TikTok', 0.0)])
        s.play_time = 100.0                                 # todos já atravessaram: saem da lista
        s._thank('bom', '@ana: Rosa')
        self.assertEqual([(th.label, th.start) for th in s.thanks], [('@ana: Rosa', 100.0)])

    def test_thank_you_line_has_a_limit(self):
        s = GameState(FOOD_TO_THEME, rng=random.Random(0), live=True)
        for i in range(20):
            s._thank('bom', f'@user{i}: Rosa')
        waiting = [th for th in s.thanks if th.start > s.play_time]
        self.assertEqual(len(waiting), config.AGRADECIMENTO_FILA)

    def test_thrown_live_gift_gets_a_thank_you(self):
        s = GameState(FOOD_TO_THEME, rng=random.Random(0), live=True)
        s.food = (0, 0)
        s.request_gift('rosa', label='@bia: Rosa')
        s._update_gifts()
        self.assertEqual([(th.side, th.label) for th in s.thanks], [('bom', '@bia: Rosa')])

    def test_queue_is_thrown_one_after_another_and_faster(self):
        s = new_state()
        s.food, s.next_gift, s.next_bomb = (0, 0), 999, 999
        for _ in range(5):
            s.request_gift('rosa')
        s._update_gifts()
        s._update_gifts()
        self.assertEqual((len(s.gifts_on_board), len(s.pending)), (1, 4))  # um na mão por vez
        first = s.gifts_on_board[0]
        self.assertLess(first.pace, 1.0)                                    # fila cheia: mais rápido
        s.play_time = first.thrown + (config.PRESENTE_SURGE + config.PRESENTE_PREPARA) * first.pace
        s._update_gifts()                                                   # soltou: pega o próximo
        self.assertEqual((len(s.gifts_on_board), len(s.pending)), (2, 3))
        self.assertEqual(len({g.cell for g in s.gifts_on_board}), 2)        # cada um numa casa

    def test_full_arena_waits_for_room(self):
        s = GameState(FOOD_TO_THEME, n=3, rng=random.Random(0), live=True)
        s.snake, s.food = [(0, 0), (1, 0), (2, 0)], None
        s.gifts_on_board = on_board(((0, 1), 'rosa', 0), ((1, 1), 'rosa', 0), ((2, 1), 'rosa', 0), ((0, 2), 'rosa', 0),
                                    ((1, 2), 'rosa', 0), ((2, 2), 'rosa', 0))
        s.request_gift('esquilo')
        s._update_gifts()
        self.assertEqual(len(s.pending), 1)                                 # nenhuma casa livre: espera
        s.spawn_food()
        self.assertIsNone(s.food)                                           # a maçã também espera
        self.assertFalse(s.won)

    def test_apple_never_spawns_on_snake_or_gifts(self):
        s = new_state()
        s.gifts_on_board = on_board(*[((x, 0), 'rosa', 0) for x in range(11)])
        for _ in range(300):
            s.spawn_food()
            self.assertNotIn(s.food, s.snake + [g.cell for g in s.gifts_on_board])

    def test_gift_landing_on_the_snake_slides_to_a_free_cell(self):
        s = new_state()
        s.food = (0, 0)
        s.gifts_on_board = [Gift((4, 5), 'esquilo', None, 0.0, 0.0)]          # caiu bem no corpo
        s._update_gifts()
        g = s.gifts_on_board[0]
        self.assertTrue(g.settled)
        self.assertNotIn(g.cell, s.snake)
        self.assertEqual(abs(g.cell[0] - 4) + abs(g.cell[1] - 5), 1)        # a casa livre mais perto

    def test_gift_gives_points_grows_changes_theme_and_bursts(self):
        s = GameState(ALL_APPLES, rng=random.Random(0), apple_tier=7)
        s.food = (0, 0)
        s.gifts_on_board = on_board(((6, 5), 'esquilo', 0))
        s.step()
        top = s.top_apple_points                                             # a maçã mais cara do elo (Mestre)
        self.assertEqual((len(s.snake), s.score, s.eaten), (4, (top + 10) * 4, 1))   # (maçã + esquilo) x tamanho
        self.assertEqual((s.old_theme, s.theme), ('classico', 'esquilo'))
        self.assertEqual(s.gifts_on_board, [])
        self.assertEqual(len(s.popups), 1)
        self.assertEqual(len(s.bonus_apples), 10)                            # esquilo vale 10 maçãs
        self.assertEqual(s.food, (0, 0))                                     # a maçã continua lá

    def test_gift_box_spreads_as_many_apples_as_coins_up_to_the_limit(self):
        self.assertEqual(GameState.gift_apples(CAIXA, 5), 5)
        self.assertEqual(GameState.gift_apples(CAIXA, 299), 299)
        self.assertEqual((GameState.gift_apples('rosa'), GameState.gift_apples('rosquinha')), (10, 30))
        s = GameState(ALL_APPLES, rng=random.Random(0), apple_tier=1)
        s.food = (0, 0)
        s.gifts_on_board = on_board(((6, 5), CAIXA, 3))
        s.step()
        self.assertEqual((s.score, s.eaten, len(s.bonus_apples)), ((s.top_apple_points + 3) * 4, 1, 3))   # + moedas

    def test_gift_points_are_top_apple_plus_gift_value_times_size(self):
        s = new_state()                                                      # Ferro: maçã 1
        s.gifts_on_board = on_board(((6, 5), 'esquilo', 0), ((8, 5), 'rosquinha', 0))
        s.food, s.food_kind = (7, 5), 'maca'
        s.step()                                                             # esquilo com 4: (1 + 10) x 4
        s.step()                                                             # maçã com 5: 1 x 5
        s.bonus_apples = [b for b in s.bonus_apples if b.cell != (9, 5)]
        s.step()                                                             # rosquinha com 6: (1 + 30) x 6
        self.assertEqual(s.score, 11 * 4 + 1 * 5 + 31 * 6)
        self.assertEqual(s.eaten, 2)                                         # a maçã não conta como presente

    def test_match_starts_with_the_arena_apples_and_refills_them(self):
        for n, count in ((11, 5), (15, 7), (18, 10)):
            s = GameState(FOOD_TO_THEME, n=n, rng=random.Random(0))
            s.update(0.01)                                                   # o primeiro quadro já enche
            self.assertEqual(len(s.extra_food) + (s.food is not None), count, n)
        s = new_state()
        s.food = (0, 0)
        s._update_extra_food()
        cell, kind = s.extra_food[0]
        s.snake = [(cell[0] - 1, cell[1]), (cell[0] - 2, cell[1]), (cell[0] - 3, cell[1])]
        s.dir, s.queue = 'E', []
        s.step()                                                             # come uma: pontos, cresce e ela sai
        self.assertEqual((len(s.snake), s.score), (4, 4 * points_for(kind)))
        self.assertNotIn((cell, kind), s.extra_food)
        s._update_extra_food()                                               # e outra aparece na hora
        self.assertEqual(len(s.extra_food) + 1, s.apples_on_field)

    def test_bomb_only_explodes_after_it_lands(self):
        s = new_state()
        s.food = (0, 0)
        s.next_bomb, s.next_gift = 0.0, 999
        s._update_bomb()
        self.assertGreater(s.bomb.lands, s.play_time)
        s.bomb = s.bomb._replace(cell=(6, 5))
        s.step()                                                             # ainda na mão do duende do mal
        self.assertEqual((s.bombs, s.theme), (0, 'classico'))
        s.play_time = s.bomb.lands
        s.bomb = s.bomb._replace(cell=(7, 5), settled=True)
        s.step()                                                             # caiu: explode
        self.assertEqual((s.bombs, s.theme), (1, 'queimado'))

    def test_gift_can_only_be_taken_after_it_lands(self):
        s = new_state()
        s.food, s.next_gift, s.next_bomb = (0, 0), 999, 999
        s.request_gift('esquilo')
        s._update_gifts()
        s.gifts_on_board[0] = s.gifts_on_board[0]._replace(cell=(6, 5))    # bem na frente da cabeça
        s.step()                                                             # ainda na mão do duende: passa por cima
        self.assertEqual((len(s.snake), s.eaten), (3, 0))
        s.play_time = s.gifts_on_board[0].lands
        s.gifts_on_board[0] = s.gifts_on_board[0]._replace(cell=(7, 5), settled=True)
        s.step()                                                             # caiu: agora pega
        self.assertEqual((len(s.snake), s.eaten), (4, 1))

    def test_live_bombs_come_only_when_requested_and_almost_together(self):
        s = GameState(FOOD_TO_THEME, rng=random.Random(0), live=True)
        s.food, s.next_bomb = (0, 0), 0.0
        s._update_bomb()
        self.assertIsNone(s.bomb)                                           # sem bomba por tempo na live
        self.assertEqual(s.flying_bombs, [])
        for _ in range(10):
            s.request_bomb('@x: TikTok')
        for _ in range(12):                                                 # 10 bombas: quase todas juntas
            s._update_bomb()
            s.play_time += config.ARREMESSO_INTERVALO
        self.assertEqual(s.bomb_requests, 0)
        flying = s.flying_bombs + [b for b in s.bonus_apples if b.kind == 'bomba']
        self.assertEqual(len(flying), 10)                                   # cada uma de um duende do mal
        self.assertLess(max(b.thrown for b in s.flying_bombs) - min(b.thrown for b in s.flying_bombs),
                        10 * config.ARREMESSO_INTERVALO + 1e-9)

    def test_eating_a_gift_spreads_apples(self):
        s = GameState(ALL_APPLES, rng=random.Random(2), apple_tier=2)       # Prata
        s.food = (0, 0)
        s.gifts_on_board = on_board(((6, 5), 'rosa', 0))
        s.step()
        self.assertEqual(len(s.bonus_apples), 10)                            # rosa vale 10
        cells = [b.cell for b in s.bonus_apples]
        self.assertEqual(len(set(cells)), len(cells))
        for b in s.bonus_apples:
            self.assertNotIn(b.cell, s.snake + [s.food])
            self.assertIn(b.kind, ('maca', 'maca_bronze', 'maca_prata'))
            self.assertEqual(b.origin, (6, 5))
            self.assertGreater(b.lands, s.play_time)
        self.assertEqual(s.bursts[0][0], (6, 5))

    def test_spread_apple_is_eaten_like_an_apple_after_landing(self):
        s = new_state()
        s.food = (0, 0)
        s.bonus_apples = [BonusApple((6, 5), 'maca', (1, 1), 0.0, 5.0, 20.0)]
        s.step()                                                             # ainda voando: passa por cima
        self.assertEqual(len(s.snake), 3)
        s.play_time = 5.0
        s.bonus_apples = [BonusApple((7, 5), 'maca', (1, 1), 0.0, 5.0, 20.0)]
        s.step()
        self.assertEqual((len(s.snake), s.score, s.eaten, s.bonus_apples), (4, 1 * 4, 0, []))
        self.assertEqual(s.food, (0, 0))                                     # a maçã comum continua lá

    def test_big_gift_can_fill_every_free_cell(self):
        s = GameState(ALL_APPLES, rng=random.Random(0), apple_tier=3)
        s.food = (0, 0)
        s.gifts_on_board = on_board(((6, 5), CAIXA, 29999))
        s.step()
        taken = set(s.snake) | {s.food} | {b.cell for b in s.bonus_apples}
        self.assertEqual(len(taken), 11 * 11)                                # a arena toda: cobra, maçã e maçãs
        self.assertLessEqual(max(b.born for b in s.bonus_apples) - s.play_time, config.MACA_BONUS_ESPALHAR)
        s.spawn_food()                                                       # sem casa para a maçã comum: espera
        self.assertFalse(s.won)

    def test_gift_box_opens_into_apples_and_bombs(self):
        s = GameState(ALL_APPLES, rng=random.Random(3), apple_tier=2)
        s.food = (0, 0)
        s.gifts_on_board = on_board(((6, 5), CAIXA, 10))
        s.step()
        kinds = [b.kind for b in s.bonus_apples]
        self.assertEqual(len(kinds), 10)
        self.assertEqual(kinds.count('bomba'), round(10 * config.CAIXA_FRACAO_BOMBAS))
        for b in s.bonus_apples:                                             # nada some: maçãs nem bombas
            self.assertIsNone(b.expires)

    def test_gift_box_turns_the_snake_into_the_box_theme(self):
        # cada skin de presente só aparece com o presente dela: a caixa tem a sua (nunca a de outro presente)
        for seed in range(10):
            s = GameState(ALL_APPLES, rng=random.Random(seed), apple_tier=1)
            s.food, s.theme = (0, 0), 'rosquinha'
            s.gifts_on_board = on_board(((6, 5), CAIXA, 10))
            s.step()
            self.assertEqual(s.theme, config.CAIXA_TEMA)
            self.assertEqual(s.apples_to_reset, config.MACAS_PARA_VOLTAR)

    def test_bomb_then_ten_apples_go_back_to_normal(self):
        s = GameState(ALL_APPLES, rng=random.Random(0), apple_tier=1)
        s.theme = 'rosa'
        s._explode((3, 3))                                      # bomba: queimada
        self.assertEqual(s.theme, s.bomb_theme)
        for _ in range(config.MACAS_PARA_DESQUEIMAR - 1):
            self.assertIsNone(s._apple_theme('maca'))
        self.assertEqual(s._apple_theme('maca'), 'classico')    # a 10ª maçã tira do queimado

    def test_box_bomb_explodes_without_growing_and_keeps_the_gnome_bomb(self):
        s = new_state()
        s.food = (0, 0)
        s.bomb = Bomb((0, 9), 99.0, settled=True)
        s.score = 100
        s.bonus_apples = [BonusApple((6, 5), 'bomba', (1, 1), 0.0, 0.0, 9.0)]
        s.step()
        self.assertEqual((s.bombs, s.theme, s.score), (1, 'queimado', 100 - 10 * 4))
        self.assertEqual(len(s.snake), 2)                                    # perdeu 1 de tamanho
        self.assertEqual(s.bonus_apples, [])
        self.assertIsNotNone(s.bomb)                                         # a do duende do mal continua lá

    def test_bomb_wipes_only_the_apples_around_it(self):
        s = new_state()                                                      # a cabeça vai para (6, 5): a bomba
        s.food = (0, 0)
        s.bonus_apples = [BonusApple((7, 6), 'maca', (1, 1), 0.0, 0.0, None),       # diagonal: some
                          BonusApple((6, 4), 'maca_ouro', (1, 1), 0.0, 0.0, None),  # em cima: some
                          BonusApple((8, 5), 'maca', (1, 1), 0.0, 0.0, None),       # a 2 casas: fica
                          BonusApple((5, 6), 'bomba', (1, 1), 0.0, 0.0, 9.0)]       # bomba da caixa: fica
        s.extra_food = [((7, 4), 'maca'), ((2, 2), 'maca')]                  # automáticas: a do lado some
        s.bomb = Bomb((6, 5), 99.0, settled=True)
        s.step()
        self.assertEqual(sorted(b.cell for b in s.bonus_apples), [(5, 6), (8, 5)])
        self.assertEqual(s.extra_food, [((2, 2), 'maca')])
        self.assertEqual(len(s.vanished), 3)
        self.assertEqual(s.food, (0, 0))                                     # longe: a maçã comum continua

    def test_bomb_next_to_the_main_apple_moves_it(self):
        s = new_state()
        s.food = (7, 5)                                                      # ao lado da bomba
        s.bomb = Bomb((6, 5), 99.0, settled=True)
        s.step()
        self.assertIsNotNone(s.food)
        self.assertGreater(max(abs(s.food[0] - 6), abs(s.food[1] - 5)), config.BOMBA_RAIO)   # fora da explosão
        self.assertEqual([k for _, k, _ in s.vanished], ['maca'])

    def test_live_bombs_stay_on_the_map_until_taken(self):
        s = GameState(FOOD_TO_THEME, rng=random.Random(0), live=True, bomb_theme='queimado')
        s.food = (0, 0)
        s.request_bomb('@leo: TikTok')
        s.request_bomb('@bia: TikTok')
        for _ in range(int(60 / 0.05)):                         # 1 minuto: muito mais que BOMBA_DURACAO
            s.play_time += 0.05
            s._update_bomb()
        bombs = [b for b in s.bonus_apples if b.kind == 'bomba']
        self.assertEqual(len(bombs), 2)                         # as duas ficaram (o duende jogou uma depois da outra)
        self.assertTrue(all(b.expires is None for b in bombs))
        self.assertIsNone(s.bomb)

    def test_offline_bomb_still_expires(self):
        s = new_state()
        s.food = (0, 0)
        s.next_bomb = 0.0
        s._update_bomb()
        self.assertIsNotNone(s.bomb.expires)
        s.play_time = s.bomb.expires
        s._update_bomb()
        self.assertTrue(s.bomb is None or s.bomb.thrown >= s.play_time)    # sumiu (pode já ter outra a caminho)

    def test_box_bombs_stay_on_the_map(self):
        s = new_state()
        s.food = (0, 0)
        s.gifts_on_board = on_board(((6, 5), CAIXA, 10))
        s.step()                                                             # abre a caixa: maçãs e bombas
        bombs = [b for b in s.bonus_apples if b.kind == 'bomba']
        self.assertTrue(bombs)
        self.assertTrue(all(b.expires is None for b in bombs))              # não somem
        s.play_time += 999
        s._update_gifts()
        self.assertEqual(len([b for b in s.bonus_apples if b.kind == 'bomba']), len(bombs))

    def test_full_field_gift_turns_bombs_into_apples(self):
        s = GameState(FOOD_TO_THEME, n=5, rng=random.Random(0), live=True, bomb_theme='queimado')
        cells = [(x, y) for y in range(5) for x in (range(5) if y % 2 == 0 else range(4, -1, -1))]
        s.snake = cells[:20][::-1]
        s.food = cells[20]
        s.bonus_apples = [BonusApple(c, 'bomba', c, 0.0, 0.0, None) for c in cells[21:25]]
        s.request_gift('rosa', label='@ana: Rosa')                           # rosa vale 10: as 4 bombas viram maçãs
        s._update_gifts()
        self.assertEqual([b.kind for b in s.bonus_apples if b.kind == 'bomba'], [])
        self.assertEqual(len(s.bonus_apples), 4)
        self.assertEqual(len(s.pending), 0)

    def test_offline_box_comes_with_ten_items(self):
        old = config.CAIXA_CHANCE_OFFLINE
        config.CAIXA_CHANCE_OFFLINE = 1.0
        try:
            s = new_state()
            s.food, s.next_gift = (0, 0), 0.0
            s._update_gifts()
            self.assertEqual((s.gifts_on_board[0].kind, s.gifts_on_board[0].value), (CAIXA, config.CAIXA_ITENS_OFFLINE))
        finally:
            config.CAIXA_CHANCE_OFFLINE = old

    def test_spread_apple_landing_on_the_snake_slides_to_a_free_cell(self):
        s = new_state()
        s.food = (0, 0)
        s.bonus_apples = [BonusApple((4, 5), 'maca', (1, 1), 0.0, 0.0, None)]     # caiu no corpo
        s._update_gifts()
        cell = s.bonus_apples[0].cell
        self.assertNotIn(cell, s.snake)
        self.assertEqual(abs(cell[0] - 4) + abs(cell[1] - 5), 1)

    def test_spread_apples_do_not_expire(self):
        s = new_state()
        s.food = (0, 0)
        s.bonus_apples = [BonusApple((7, 5), 'maca', (1, 1), 0.0, 1.0, None)]
        s.play_time = 9999.0
        s._update_gifts()
        self.assertEqual(len(s.bonus_apples), 1)
        self.assertFalse(s.blinking(s.bonus_apples[0]))

    def full_field(self):
        """Arena 5x5 com a cobra em 17 casas, a maçã principal e 5 maçãs espalhadas: sem casa livre sobrando."""
        s = GameState(FOOD_TO_THEME, n=5, rng=random.Random(0), live=True, bomb_theme='queimado')
        cells = [(x, y) for y in range(5) for x in (range(5) if y % 2 == 0 else range(4, -1, -1))]
        s.snake = cells[:17][::-1]
        s.food = cells[17]
        s.bonus_apples = [BonusApple(c, 'maca', c, 0.0, 0.0, None) for c in cells[18:23]]
        return s

    def test_full_field_still_thanks_right_away(self):
        s = self.full_field()
        s.request_gift('rosa', label='@ana: Rosa')
        s.request_bomb('@leo: TikTok')
        self.assertEqual(sorted(th.side for th in s.thanks), ['bom', 'mal'])   # o duende da placa sai na hora
        self.assertEqual((s.last_sender, s.last_bomb_sender), ('@ana: Rosa', '@leo: TikTok'))

    def test_full_field_bombs_turn_apples_into_bombs(self):
        s = self.full_field()
        for _ in range(3):
            s.request_bomb('@leo: TikTok')
        s._update_bomb()
        kinds = [b.kind for b in s.bonus_apples]
        self.assertEqual((kinds.count('bomba'), kinds.count('maca')), (3, 2))     # 3 bombas = 3 maçãs viram bomba
        self.assertEqual(s.bomb_requests, 0)
        self.assertEqual(s.flying_bombs, [])
        self.assertIsNotNone(s.food)                                         # a maçã principal fica

    def test_requested_bomb_is_thrown_right_away(self):
        s = new_state()
        s.next_bomb = 999
        s.request_bomb()
        s._update_bomb()
        self.assertEqual(len(s.flying_bombs), 1)

    def test_several_gifts_are_thrown_almost_together(self):
        s = GameState(FOOD_TO_THEME, rng=random.Random(0), live=True)
        s.food = (0, 0)
        for _ in range(8):
            s.request_gift('rosa', label='@ana: Rosa')
        for _ in range(9):
            s._update_gifts()
            s.play_time += config.ARREMESSO_INTERVALO
        self.assertEqual(len(s.pending), 0)
        self.assertEqual(len(s.gifts_on_board), 8)                          # vários duendes ao mesmo tempo


class TestMovement(unittest.TestCase):
    def test_moves_forward(self):
        s = new_state()
        s.food = (0, 0)
        s.step()
        self.assertEqual(s.snake, [(6, 5), (5, 5), (4, 5)])

    def test_ignores_reverse_direction(self):
        s = new_state()
        s.food = (0, 0)
        s.queue_turn('W')
        s.step()
        self.assertEqual(s.dir, 'E')
        self.assertFalse(s.dead)

    def test_turn_queue_is_limited(self):
        s = new_state()
        for d in 'NSNSNS':
            s.queue_turn(d)
        self.assertEqual(len(s.queue), config.MAX_QUEUED_TURNS)

    def test_update_steps_by_theme_speed(self):
        s = new_state()
        s.food = (0, 0)
        s.update(config.STEP['classico'] * 2 + 0.001)
        self.assertEqual(s.snake[0], (7, 5))


class TestCollisions(unittest.TestCase):
    def test_wall_kills(self):
        s = new_state()
        s.food = (0, 0)
        s.snake = [(config.N - 1, 5), (config.N - 2, 5), (config.N - 3, 5)]
        s.step()
        self.assertTrue(s.dead)

    def test_self_collision_kills(self):
        s = new_state()
        s.food = (0, 0)
        s.snake = [(5, 5), (6, 5), (6, 6), (5, 6), (4, 6), (4, 5)]
        s.dir = 'S'
        s.step()
        self.assertTrue(s.dead)

    def test_can_move_into_cell_the_tail_leaves(self):
        s = new_state()
        s.food = (0, 0)
        s.snake = [(5, 5), (6, 5), (6, 6), (5, 6)]
        s.dir = 'S'
        s.step()
        self.assertFalse(s.dead)


class TestEating(unittest.TestCase):
    def test_eating_an_apple_grows_and_scores(self):
        s = new_state()
        s.food, s.food_kind = (6, 5), 'maca'
        s.step()
        self.assertEqual(len(s.snake), 4)
        self.assertEqual((s.score, s.eaten), (1 * 4, 0))       # valor x tamanho (já com o segmento novo)
        self.assertNotIn(s.food, s.snake)

    def test_eating_shows_points_popup_that_expires(self):
        s = new_state()
        s.food, s.food_kind = (6, 5), 'maca'
        s.step()
        self.assertEqual([(p.cell, p.points, p.kind) for p in s.popups], [((6, 5), 1 * 4, 'maca')])
        s.food = (0, 0)
        s.update(config.POPUP_SEGUNDOS * 0.5)
        self.assertEqual(len(s.popups), 1)
        s.update(config.POPUP_SEGUNDOS * 0.6)
        self.assertEqual(s.popups, [])

    def test_play_time_counts_until_game_over(self):
        s = new_state()
        s.food = (0, 0)
        s.update(0.1)
        self.assertAlmostEqual(s.play_time, 0.1)
        s.dead = True
        s.update(5.0)
        self.assertAlmostEqual(s.play_time, 0.1)
        s.reset()
        self.assertEqual(s.play_time, 0.0)

    def test_reset_clears_points(self):
        s = new_state()
        s.food, s.food_kind = (6, 5), 'rosquinha'
        s.step()
        s.reset()
        self.assertEqual((s.score, s.eaten, s.popups), (0, 0, []))

    def test_filling_the_board_wins_without_crashing(self):
        n = 4
        path = []       # percorre o tabuleiro em zigue-zague
        for y in range(n):
            xs = range(n) if y % 2 == 0 else reversed(range(n))
            path += [(x, y) for x in xs]
        s = new_state(n)
        s.snake = list(reversed(path[:-1]))     # ocupa tudo menos a última célula
        s.dir = 'W'
        s.food, s.food_kind = path[-1], 'rosa'
        s.step()
        self.assertTrue(s.won)
        self.assertFalse(s.dead)
        self.assertIsNone(s.food)
        s.update(1.0)       # o jogo parado não deve quebrar


class TestArenas(unittest.TestCase):
    def test_every_arena_starts_in_the_middle_and_hits_its_own_wall(self):
        for n in config.ARENAS:
            s = new_state(n)
            c = n // 2
            self.assertEqual(s.snake[0], (c, c))
            self.assertTrue(all(0 <= x < n and 0 <= y < n for x, y in s.snake + [s.food]))
            s.food = (0, 0)
            s.bomb_theme = None
            for _ in range(n - c - 1):              # anda até encostar na parede da direita
                s.step()
            self.assertFalse(s.dead)
            s.step()
            self.assertTrue(s.dead, n)


class TestBomb(unittest.TestCase):
    def place_bomb_ahead(self, s):
        hx, hy = s.snake[0]
        s.bomb = Bomb((hx + 1, hy), s.play_time + config.BOMBA_DURACAO)

    def test_bomb_appears_after_interval_and_expires(self):
        s = new_state()
        s.food = (0, 0)
        s.snake = [(5, 10), (4, 10), (3, 10)]          # longe da parede por um tempo
        s.next_bomb = 0.05
        s.update(0.06)
        self.assertIsNotNone(s.bomb)
        self.assertNotIn(s.bomb.cell, s.snake)
        self.assertNotEqual(s.bomb.cell, s.food)
        s.play_time = s.bomb.expires                    # tempo da bomba acabou
        s.update(0.0)
        self.assertIsNone(s.bomb)
        self.assertGreater(s.next_bomb, s.play_time)

    def test_eating_bomb_burns_slows_and_costs_points(self):
        s = new_state()
        s.food, s.score = (0, 0), 100
        self.place_bomb_ahead(s)
        s.step()
        self.assertEqual(s.score, 100 - 10 * 4)          # 10 x o tamanho (4, com a cabeça na bomba)
        self.assertEqual(s.theme, 'queimado')
        self.assertEqual(s.step_time, config.STEP['caracol'])
        self.assertEqual(len(s.snake), 2)               # bomba tira 1 de tamanho
        self.assertEqual(s.eaten, 0)
        self.assertIsNone(s.bomb)
        self.assertEqual(s.popups[-1].points, -config.BOMBA_PENALIDADE * 4)
        self.assertEqual(s.bombs, 1)

    def test_bomb_keeps_at_least_head_and_tail(self):
        s = new_state()
        s.food = (0, 0)
        s.snake, s.prev = s.snake[:2], s.prev[:2]
        self.place_bomb_ahead(s)
        s.step()
        self.assertEqual(len(s.snake), config.BOMBA_TAMANHO_MINIMO)

    def test_score_never_goes_negative(self):
        s = new_state()
        s.food, s.score = (0, 0), 4
        self.place_bomb_ahead(s)
        s.step()
        self.assertEqual(s.score, 0)

    def test_one_apple_is_not_enough_to_heal_the_burn(self):
        s = new_state()
        s.food = (0, 0)
        self.place_bomb_ahead(s)
        s.step()
        s.food, s.food_kind = (7, 5), 'maca'
        s.step()
        self.assertEqual(s.theme, 'queimado')                                # só na 10ª (ou com um presente)
        self.assertEqual(s.apples_to_reset, config.MACAS_PARA_DESQUEIMAR - 1)

    def test_no_new_bomb_while_burnt(self):
        s = new_state()
        s.food = (0, 0)
        s.theme = 'queimado'
        s.next_bomb = 0.0
        s.update(0.01)
        self.assertIsNone(s.bomb)

    def test_food_never_spawns_on_bomb(self):
        s = new_state()
        s.bomb = Bomb((2, 2), 99.0)
        for _ in range(300):
            s.spawn_food()
            self.assertNotEqual(s.food, (2, 2))

    def test_bombs_can_be_disabled(self):
        s = GameState(FOOD_TO_THEME, rng=random.Random(0), bomb_theme=None)
        s.food = (0, 0)
        s.next_bomb = 0.0
        s.update(0.01)
        self.assertIsNone(s.bomb)


class TestManifest(unittest.TestCase):
    def test_every_food_maps_to_a_theme_with_speed(self):
        man = load_manifest()
        for theme in man.food_to_theme.values():
            self.assertIn(theme, man.backgrounds)
        for theme in man.themes:
            self.assertIn(theme, config.STEP)
        self.assertIn(config.START_THEME, man.themes)


if __name__ == '__main__':
    unittest.main()
