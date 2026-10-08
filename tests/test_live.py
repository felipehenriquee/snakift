import time
import unittest

from cobra import config, live
from cobra.logic import CAIXA, GiftOrder

OPTS = {'live_bomba': 'TikTok', 'live_ligados': ['Rosa', 'Donut']}


class TestGiftOrders(unittest.TestCase):
    def test_known_gift_is_one_throw_per_unit(self):
        orders = live.gift_orders('Rosa', 1, 5, 'bia', OPTS)
        self.assertEqual(orders, [GiftOrder('rosa', 0, '@bia: Rosa x5')] * 5)
        self.assertEqual(live.gift_orders('donut ', 30, 1, 'leo', OPTS), [GiftOrder('rosquinha', 0, '@leo: donut ')])
        for name in ('Doughnut', 'Rosquinha'):                       # outros nomes da rosquinha
            self.assertTrue(live.is_known(name), name)

    def test_unknown_gift_is_a_box_worth_all_the_coins(self):
        self.assertEqual(live.gift_orders('Galaxy', 1000, 3, 'ana', OPTS), [GiftOrder(CAIXA, 3000, '@ana: Galaxy x3')])
        self.assertFalse(live.is_known('Galaxy'))
        self.assertTrue(live.is_known('ROSA'))
        self.assertFalse(live.is_known('Rose'))                    # a Rose (1 moeda) ficou de fora

    def test_bomb_gift_is_the_tiktok_one_by_default(self):
        self.assertEqual(config.LIVE_BOMBA_PADRAO, 'TikTok')
        self.assertEqual([o.kind for o in live.gift_orders('TikTok', 1, 2, 'x', live.default_options())],
                         [live.BOMBA] * 2)
        other = dict(OPTS, live_bomba='Rosa')                       # escolhido na tela da live
        self.assertEqual([o.kind for o in live.gift_orders('Rosa', 1, 1, 'x', other)], [live.BOMBA])

    def test_disabled_gifts_become_a_box_never_ignored(self):
        self.assertEqual(live.gift_orders('GG', 1, 3, 'x', OPTS), [GiftOrder(CAIXA, 3, '@x: GG x3')])
        self.assertEqual(live.gift_orders('Squirrel', 1, 1, 'x', OPTS), [GiftOrder(CAIXA, 1, '@x: Squirrel')])  # desligado
        self.assertTrue(live.is_enabled('Rosa', OPTS))
        self.assertFalse(live.is_enabled('gg', OPTS))

    def test_by_default_only_gifts_with_a_look_in_the_game_are_on(self):
        opts = live.default_options()
        for name in ('Rosa', 'Donut', 'Squirrel', 'Hand Heart', 'Mãos em coração', 'Slow Motion'):
            self.assertTrue(live.is_enabled(name, opts), name)
        for name in ('Galaxy', 'Rose', 'Singing Mushroom'):
            self.assertFalse(live.is_enabled(name, opts), name)

    def test_gifts_outside_the_game_become_a_box_worth_the_coins(self):
        opts = live.default_options()
        self.assertEqual(live.gift_orders('Singing Mushroom', 99, 1, 'ana', opts),
                         [GiftOrder(CAIXA, 99, '@ana: Singing Mushroom')])
        self.assertEqual(live.gift_orders('Together togethe', 199, 2, 'leo', opts),
                         [GiftOrder(CAIXA, 398, '@leo: Together togethe x2')])
        self.assertEqual([o.kind for o in live.gift_orders('Squirrel', 1, 2, 'x', opts)], ['esquilo'] * 2)
        self.assertEqual([o.kind for o in live.gift_orders('Hand Heart', 100, 1, 'x', opts)], ['coracao'])
        self.assertEqual([o.kind for o in live.gift_orders('Slow Motion', 1, 2, 'x', opts)], ['caracol'] * 2)

    def test_bomb_can_be_any_gift_even_turned_off(self):
        opts = dict(live.default_options(), live_bomba='Galaxy')
        self.assertEqual([o.kind for o in live.gift_orders('Galaxy', 1000, 1, 'x', opts)], [live.BOMBA])



class TestLeaderboard(unittest.TestCase):
    def test_counts_gifts_and_coins(self):
        board = live.Leaderboard()
        board.add(live.Tribute('ana', 'Ana', None, 299, 1))
        board.add(live.Tribute('leo', 'Leo', None, 30, 30))
        board.add(live.Tribute('leo', 'Leo', None, 1, 1))
        top = board.top(3)
        self.assertEqual([(tb.user, tb.coins, tb.gifts) for tb in top], [('ana', 299, 1), ('leo', 31, 31)])

    def test_top_3_by_coins(self):
        board = live.Leaderboard()
        for user, coins in (('ana', 5), ('leo', 100), ('bia', 1), ('ana', 200), ('rui', 30), ('bia', 1)):
            board.add(live.Tribute(user, user.title(), None, coins))
        self.assertEqual([(t.user, t.coins) for t in board.top(3)], [('ana', 205), ('leo', 100), ('rui', 30)])

    def test_keeps_the_photo_once_it_comes(self):
        board = live.Leaderboard()
        board.add(live.Tribute('ana', 'Ana', None, 1))
        board.add(live.Tribute('ana', 'Ana', 'https://x/a.jpg', 1))
        board.add(live.Tribute('ana', 'Ana', None, 1))
        self.assertEqual(board.top()[0].avatar, 'https://x/a.jpg')


class TestCatalog(unittest.TestCase):
    def test_gift_list_from_tiktok(self):
        info = {'gifts': [{'name': 'Lion', 'diamond_count': 29999, 'image': {'url_list': ['https://x/lion.webp']}},
                          {'name': 'Rose', 'diamond_count': 1, 'image': {'url_list': ['https://x/rose.png']}},
                          {'name': 'Rose', 'diamond_count': 1}, {'bad': 1}]}
        items = live.parse_gift_list(info)
        self.assertEqual([(i['nome'], i['moedas']) for i in items], [('Rose', 1), ('Lion', 29999)])
        self.assertTrue(live.image_path(items[1]['imagem']).endswith('.webp'))

    def test_default_catalog_without_file(self):
        names = [i['nome'] for i in live.load_catalog('/nao/existe.json')]
        self.assertIn('TikTok', names)
        self.assertIn('Rose', names)


if __name__ == '__main__':
    unittest.main()
