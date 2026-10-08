import json
import os
import tempfile
import unittest
from types import SimpleNamespace

from cobra import rank, records
from cobra.result import Result


def game(score, play_time=30.0, n=11):
    return SimpleNamespace(score=score, eaten=score // 10, play_time=play_time, won=False, n=n, time=0.0)


def save_tables(path, tables, name='bia'):
    records.save(path, {'tabelas': tables, 'ultimo_nome': name})


def table(*scores):
    return [{'nome': f'j{i}', 'pontos': s, 'tempo': 1.0, 'data': ''} for i, s in enumerate(scores)]


FULL = (100, 80, 60, 40, 20)                            # uma tabela cheia (5 recordes)
F11, F15, F18 = (11, 'ferro'), (15, 'ferro'), (18, 'ferro')


class TestRecords(unittest.TestCase):
    def test_qualifies(self):
        self.assertFalse(records.qualifies([], 0))
        self.assertTrue(records.qualifies([], 1))
        full = table(*FULL)
        self.assertEqual(len(full), records.MAX_RECORDS)
        self.assertFalse(records.qualifies(full, 20))   # empatar com o último não basta
        self.assertTrue(records.qualifies(full, 21))

    def test_add_keeps_order_and_top_5(self):
        recs, pos = records.add(table(*FULL), 'ana', 55, 12.0, 11, 'prata')
        self.assertEqual(pos, 3)
        self.assertEqual([r['pontos'] for r in recs], [100, 80, 60, 55, 40])
        self.assertEqual((recs[3]['arena'], recs[3]['elo']), (11, 'prata'))

    def test_position_where_score_would_enter(self):
        full = table(*FULL)
        self.assertEqual(records.position(full, 105), 0)
        self.assertEqual(records.position(full, 55), 3)
        self.assertEqual(records.position(full, 25), 4)
        self.assertIsNone(records.position(full, 20))           # empata com o último: não entra
        self.assertEqual(records.position([], 1), 0)
        self.assertIsNone(records.position([], 0))

    def test_tie_goes_after_older_record(self):
        recs, pos = records.add(table(50, 50), 'ana', 50, 1.0)
        self.assertEqual(pos, 2)

    def test_name_is_trimmed(self):
        recs, _ = records.add([], '  um nome muito comprido demais aqui  ', 10, 1.0)
        self.assertEqual(recs[0]['nome'], 'um nome muito comprido demais aqui'[:records.MAX_NAME])

    def test_missing_or_broken_file_is_empty_table(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(records.load(os.path.join(d, 'nada.json'))['tabelas'], {})
            broken = os.path.join(d, 'r.json')
            with open(broken, 'w') as f:
                f.write('{isso não é json')
            self.assertEqual(records.load(broken)['tabelas'], {})

    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'sub', 'recordes.json')
            save_tables(path, {(11, 'ferro'): table(30, 20), (11, 'ouro'): table(70), (18, 'bronze'): table(90)}, 'ana')
            data = records.load(path)
            self.assertEqual({k: [r['pontos'] for r in v] for k, v in data['tabelas'].items()},
                             {(11, 'ferro'): [30, 20], (11, 'ouro'): [70], (18, 'bronze'): [90]})
            self.assertEqual(records.table(data, 11, 'ouro')[0]['pontos'], 70)
            self.assertEqual(records.table(data, 15, 'ouro'), [])
            self.assertEqual(records.best(data), 90)
            self.assertEqual(data['ultimo_nome'], 'ana')
            self.assertFalse(os.path.exists(path + '.tmp'))


    def test_per_arena_file_goes_to_iron(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'recordes.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({'por_arena': {'11': table(*range(100, 0, -10)), '15': table(50)}, 'ultimo_nome': 'ana'}, f)
            tables = records.load(path)['tabelas']
            self.assertEqual({k: [r['pontos'] for r in v] for k, v in tables.items()},
                             {F11: [100, 90, 80, 70, 60], F15: [50]})      # sem o elo: Ferro, os 5 melhores

    def test_old_single_table_file_is_split_by_arena(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'recordes.json')
            old = table(100, 80, 60, 40)
            old[1]['arena'] = 15                        # recordes novos guardavam a arena
            old[2]['arena'] = 18                        # os antigos não: eram todos 11x11
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({'recordes': old, 'ultimo_nome': 'ana'}, f)
            tables = records.load(path)['tabelas']
            self.assertEqual({k: [r['pontos'] for r in v] for k, v in tables.items()}, {F11: [100, 40], F15: [80], F18: [60]})


class TestSupporters(unittest.TestCase):
    def test_coins_add_up_across_matches_and_keep_the_top(self):
        from cobra.live import Tribute
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'recordes.json')
            data = records.load(path)
            records.add_supporters(data, [Tribute('ana', 'Ana', 'https://x/a.jpg', 100), Tribute('leo', 'Leo', None, 30)])
            records.save(path, data)
            data = records.load(path)
            records.add_supporters(data, [Tribute('leo', 'Leo', 'https://x/l.jpg', 200), Tribute('zero', 'Z', None, 0)])
            records.save(path, data)
            sup = records.load(path)['doadores']
            self.assertEqual([(s['usuario'], s['moedas']) for s in sup], [('leo', 230), ('ana', 100)])
            self.assertEqual(sup[0]['foto'], 'https://x/l.jpg')

    def test_limit(self):
        from cobra.live import Tribute
        data = records.add_supporters({'doadores': []}, [Tribute(f'u{i}', '', None, i + 1) for i in range(30)])
        self.assertEqual(len(data['doadores']), records.MAX_SUPPORTERS)
        self.assertEqual(data['doadores'][0]['usuario'], 'u29')


class TestResult(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, 'recordes.json')

    def tearDown(self):
        self.dir.cleanup()

    def test_record_asks_name_then_saves_and_offers_table(self):
        save_tables(self.path, {F11: table(80, 40)})
        r = Result(game(60), self.path)
        self.assertEqual(r.phase, 'nome')
        self.assertEqual(r.name, 'bia')                 # já vem com o último nome
        self.assertFalse(r.is_best)
        self.assertFalse(r.can_show_table)
        for _ in range(3):
            r.backspace()
        for ch in 'Ana':
            r.type_char(ch)
        r.confirm()
        self.assertEqual((r.phase, r.rank), ('resumo', 1))
        self.assertTrue(r.can_show_table)
        r.toggle_table()
        self.assertEqual(r.phase, 'tabela')
        r.toggle_table()
        self.assertEqual(r.phase, 'resumo')
        with open(self.path, encoding='utf-8') as f:
            saved = json.load(f)
        self.assertEqual([(x['nome'], x['pontos']) for x in saved['por_arena_elo']['11']['ferro']],
                         [('j0', 80), ('Ana', 60), ('j1', 40)])
        self.assertEqual(saved['ultimo_nome'], 'Ana')

    def test_best_score(self):
        save_tables(self.path, {F11: table(80)})
        r = Result(game(90), self.path)
        self.assertTrue(r.is_best)
        r.confirm()
        self.assertEqual(r.rank, 0)
        self.assertTrue(r.is_best)

    def test_no_record_goes_straight_to_summary(self):
        save_tables(self.path, {F11: table(*FULL)})
        r = Result(game(5), self.path)
        self.assertEqual(r.phase, 'resumo')
        self.assertFalse(r.can_show_table)
        r.toggle_table()                                # sem recorde, R não faz nada
        self.assertEqual(r.phase, 'resumo')

    def test_each_arena_has_its_own_table(self):
        save_tables(self.path, {F11: table(*FULL), F15: table(500)})
        r = Result(game(50, n=18), self.path)           # 18x18 ainda sem recordes: 50 entra em 1º
        self.assertEqual(r.phase, 'nome')
        self.assertTrue(r.is_best)
        r.confirm()
        r15 = Result(game(50, n=15), self.path)         # na 15x15 entra em 2º
        r15.confirm()
        self.assertEqual(r15.rank, 1)
        tables = records.load(self.path)['tabelas']
        self.assertEqual([x['pontos'] for x in tables[F18]], [50])
        self.assertEqual([x['pontos'] for x in tables[F15]], [500, 50])
        self.assertEqual(len(tables[F11]), 5)           # a 11x11 não mudou
        self.assertEqual(tables[F11][0]['pontos'], 100)

    def test_each_league_has_its_own_table(self):
        from cobra import rank
        save_tables(self.path, {F11: table(*FULL)})
        out = rank.apply_match(rank.Rank(2, 3, 0), 50, 0, 11)          # partida começada no Prata
        r = Result(game(50), self.path, out)
        self.assertEqual(r.league, 'prata')
        r.continue_rank()
        self.assertEqual(r.phase, 'nome')               # 50 não entra no Ferro, mas é o 1º do Prata
        r.confirm()
        tables = records.load(self.path)['tabelas']
        self.assertEqual([x['pontos'] for x in tables[11, 'prata']], [50])
        self.assertEqual([x['pontos'] for x in tables[F11]], list(FULL))

    def test_rank_screen_comes_first_then_record(self):
        from cobra import rank
        out = rank.apply_match(rank.START, 60, 6, 11)
        r = Result(game(60), self.path, out)
        self.assertEqual(r.phase, 'ranque')
        r.continue_rank()
        self.assertEqual(r.phase, 'nome')               # 60 entra na tabela vazia
        r2 = Result(game(0), self.path, out)
        r2.continue_rank()
        self.assertEqual(r2.phase, 'resumo')            # zero não é recorde

    def test_live_match_shows_podium_between_rank_and_record(self):
        out = rank.apply_match(rank.START, 60, 6, 11)
        live_game = game(60)
        live_game.live = True
        r = Result(live_game, self.path, out)
        self.assertEqual(r.phase, 'ranque')
        r.continue_rank()
        self.assertEqual(r.phase, 'top')                # pódio de quem mais mandou presentes
        r.continue_rank()
        self.assertEqual(r.phase, 'nome')               # 60 entra na tabela vazia

    def test_offline_match_skips_podium(self):
        out = rank.apply_match(rank.START, 60, 6, 11)
        r = Result(game(60), self.path, out)
        r.continue_rank()
        self.assertEqual(r.phase, 'nome')

    def test_name_length_limit(self):
        r = Result(game(10), self.path)
        r.name = ''
        for ch in 'x' * 30:
            r.type_char(ch)
        self.assertEqual(len(r.name), records.MAX_NAME)

    def test_live_record_uses_the_at_and_keeps_offline_name(self):
        data = records.load(self.path)
        data['ultimo_nome'] = 'Felipe'
        records.save(self.path, data)
        r = Result(game(60), self.path, live_name='@felipe_live')
        self.assertEqual(r.name, '@felipe_live')
        r.phase = 'nome'
        r.confirm()
        self.assertEqual(r.records[r.rank]['nome'], '@felipe_live')
        self.assertEqual(records.load(self.path)['ultimo_nome'], 'Felipe')     # o nome do offline não muda


if __name__ == '__main__':
    unittest.main()
