"""Regras do jogo: cobra, comida, presentes, bomba e troca de tema. Não depende do pygame."""
import random
from collections import deque, namedtuple

from . import config

DIRS = {'E': (1, 0), 'S': (0, 1), 'W': (-1, 0), 'N': (0, -1)}   # E = direita, S = baixo, W = esquerda, N = cima
OPP = {'E': 'W', 'W': 'E', 'N': 'S', 'S': 'N'}
DIR_FROM_DELTA = {v: k for k, v in DIRS.items()}

PointsPopup = namedtuple('PointsPopup', 'cell points born kind')    # "+40" na tela; born = state.time; kind = comida
# bomba: jogada pelo duende do mal como os presentes (thrown = começou a jogar, lands = caiu, expires = some;
# pace = fração da duração normal da animação; settled = já conferiu se caiu em cima da cobra)
Bomb = namedtuple('Bomb', 'cell expires thrown lands pace settled', defaults=(0.0, 0.0, 1.0, False))
# presente na arena (na mão do duende, voando ou caído). expires None = não some (presentes da live);
# value = moedas da caixa de presente; label = quem mandou, para mostrar ("@fulano: Rosa x5")
Gift = namedtuple('Gift', 'cell kind expires thrown lands value label pace settled',
                  defaults=(0.0, 0.0, 0, '', 1.0, False))
GiftOrder = namedtuple('GiftOrder', 'kind value label', defaults=(0, ''))    # presente esperando para ser jogado
# maçã (ou bomba, kind 'bomba', só da caixa de presente) espalhada pelo estouro de um presente: sai de `origin`
# em `born`, cai em `lands`; expires None = não some (as bombas somem)
BonusApple = namedtuple('BonusApple', 'cell kind origin born lands expires')
# duende que atravessa a faixa de baixo com a placa "Obrigado, @fulano": lado ('bom'/'mal'), pedido e quando sai
Thanks = namedtuple('Thanks', 'side label start')
CAIXA = 'caixa'         # caixa de presente: presentes da live que não existem no jogo; vale as moedas enviadas


APPLES = set(config.MACAS.values())


def is_apple(food):
    """Maçã (de qualquer elo): alimento comum, volta ao tema clássico e não conta como presente."""
    return food in APPLES


def apple_weights(tier, available=None):
    """{maçã: peso} para uma partida no elo `tier` (índice da liga): a do elo e as anteriores, cada elo para
    trás com MACA_PESO_ANTERIOR do peso do seguinte. available: maçãs que existem nos sprites."""
    leagues = [liga for liga, *_ in config.RANQUE_LIGAS][:tier + 1]
    weights = {}
    for i, liga in enumerate(leagues):
        apple = config.MACAS.get(liga)
        if apple and (available is None or apple in available):
            weights[apple] = config.MACA_PESO_ANTERIOR ** (tier - i)
    return weights or {config.ALIMENTO_PADRAO: 1.0}


def points_for(food):
    """Valor da comida (multiplicado pelo tamanho da cobra ao comer)."""
    return config.PONTOS.get(food, config.PONTOS_PADRAO)


class GameState:
    def __init__(self, food_to_theme, n=config.N, rng=None, bomb_theme=config.BOMBA_TEMA, apple_tier=0, live=False):
        """apple_tier: elo da partida (índice da liga), que define quais maçãs aparecem. live: modo live do
        TikTok (os presentes vêm só da live e das teclas de teste, e não somem)."""
        self.live = live
        self.food_to_theme = dict(food_to_theme)
        self.foods = list(food_to_theme)
        self.gifts = [f for f in self.foods if not is_apple(f)]
        self.apple_tier = apple_tier
        self.controller = None              # função(estado) -> direção: o robô jogando (piloto automático)
        self.n = n
        self.rng = rng or random.Random()
        self.bomb_theme = bomb_theme        # None = sem bombas
        self.reset()

    def reset(self):
        # sorteio desta partida para quem precisar (o robô sorteia o caminho dele), sem gastar números do rng
        self.match_seed = hash(self.rng.getstate()[1]) & 0x7FFFFFFF    # só os números (o hash de None muda a cada execução)
        c = self.n // 2
        self.snake = [(c - i, c) for i in range(config.TAMANHO_INICIAL)]
        self.prev = list(self.snake)    # posições no passo anterior, para interpolar
        self.dir = 'E'
        self.queue = []
        self.theme = self.old_theme = config.START_THEME
        self.wave_origin, self.wave_t = (c, c), 99.0
        self.score = 0                  # pontos
        self.practice = False           # treino (o robô jogou): não conta para ranque e recordes
        self.ranked_robot = False       # modo robô: as partidas do robô contam (ranque, perfil e recordes)
        self.eaten = 0                  # presentes comidos (a maçã, alimento padrão, não conta)
        self.apples_streak = 0          # maçãs seguidas desde o último presente (MACAS_PARA_VOLTAR: volta ao normal)
        self.slow_apples = 0            # maçãs comidas desde que ficou lenta (caracol / queimada): acelera e desqueima
        self.bombs = 0                  # bombas pegas
        self.play_time = 0.0            # segundos de partida (para no fim de jogo)
        self.bomb = None
        self.bomb_queue = deque()       # bombas pedidas (presente da bomba na live, tecla de teste): quem pediu
        self.flying_bombs = []          # bombas da live na mão dos duendes do mal ou voando (várias ao mesmo tempo)
        self.next_throw = self.next_bomb_throw = 0.0     # próximos arremessos (um a cada ARREMESSO_INTERVALO)
        self.last_bomb_sender = ''      # quem mandou a última bomba ("@fulano: TikTok"), para a placa do mal
        self.gifts_on_board = []        # presentes na mão do duende, voando ou caídos na arena
        self.bonus_apples = []          # maçãs espalhadas pelo estouro dos presentes comidos
        self.bursts = []                # (casa, hora) dos presentes que estouraram, para o efeito na tela
        self.vanished = []              # (casa, maçã, hora) das maçãs extras que a bomba fez sumir (efeito)
        self.pending = deque()          # GiftOrder esperando o duende jogar (a live pode mandar vários de uma vez)
        self.last_sender = ''           # quem mandou o último presente da live ("@fulano: Rosa x5")
        self.thanks = []                # Thanks: duendes com a placa "Obrigado, @fulano" (fila de cada lado)
        self.food = None
        self.extra_food = []            # maçãs automáticas além da principal: [(casa, maçã)] (MACAS_AUTOMATICAS)
        self._schedule_bomb()
        self._schedule_gift()
        self.popups = []                # PointsPopup recentes, para o renderer mostrar
        self.events = []                # o que aconteceu (para os sons): ('comeu', comida), ('tema', tema),
                                        # ('bomba',), ('morreu',), ('venceu',); o app esvazia a cada quadro
        self.dead = False
        self.won = False
        self.acc = 0.0
        self.time = 0.0
        self.spawn_food()

    @property
    def over(self):
        return self.dead or self.won

    @property
    def step_time(self):
        """Segundos por passo no tema. Lento (caracol, queimado): cada maçã comida acelera um pouco, até a
        velocidade normal na MACAS_PARA_ACELERAR-ésima."""
        base = config.STEP[self.theme]
        if self.theme not in config.TEMAS_LENTOS:
            return base
        k = min(self.slow_apples, config.MACAS_PARA_ACELERAR) / config.MACAS_PARA_ACELERAR
        return base + (config.STEP[config.START_THEME] - base) * k

    @property
    def alpha(self):
        """Fração do caminho entre o passo anterior e o atual (0..1)."""
        return 1.0 if self.over else min(1.0, self.acc / self.step_time)

    def spawn_food(self, avoid=()):
        """A comida da arena é sempre uma maçã, sorteada entre as do elo pelos pesos, numa casa sem cobra,
        presente ou bomba (nem em `avoid`, se der). Com a arena lotada de presentes, espera abrir espaço (tenta de
        novo a cada quadro)."""
        extras = {c for c, _ in self.extra_food}
        free = [c for c in self._free_cells(avoid_bomb=True, avoid_gift=True) if c not in extras]
        free = [c for c in free if c not in avoid] or free
        if not free:
            self.food = None
            if not self._free_cells():                  # a cobra ocupa tudo: venceu
                self.won = True
                self.events.append(('venceu',))
            return
        self.food = self.rng.choice(free)
        weights = apple_weights(self.apple_tier, self.food_to_theme)
        self.food_kind = self.rng.choices(list(weights), list(weights.values()))[0]

    @property
    def apples_on_field(self):
        """Quantas maçãs do jogo ficam na arena ao mesmo tempo (a principal + as automáticas), pelo tamanho dela."""
        return config.MACAS_AUTOMATICAS.get(self.n, config.MACAS_AUTOMATICAS_PADRAO)

    def _update_extra_food(self):
        """Mantém a arena com apples_on_field maçãs: já começa assim e repõe na hora as que a cobra come."""
        weights = None
        while len(self.extra_food) + 1 < self.apples_on_field:
            free = self._free_cells(avoid_bomb=True, avoid_food=True, avoid_gift=True)
            if not free:                                # arena cheia: repõe quando abrir espaço
                return
            weights = weights or apple_weights(self.apple_tier, self.food_to_theme)
            self.extra_food.append((self.rng.choice(free), self.rng.choices(list(weights), list(weights.values()))[0]))

    @property
    def top_apple_points(self):
        """Valor da maçã mais cara que aparece nesta partida (a do elo)."""
        return max(points_for(a) for a in apple_weights(self.apple_tier, self.food_to_theme))

    @staticmethod
    def gift_apples(kind, value=0):
        """Quantas maçãs o presente espalha ao ser comido: o valor dele (na caixa, as moedas enviadas)."""
        return value if kind == CAIXA else points_for(kind)

    def gift_points(self, kind, value=0):
        """Pontos do presente (antes do tamanho): a maçã mais cara do elo + o valor dele (na caixa, as moedas
        enviadas). Presente vale mais que maçã: incentiva a live a mandar presentes para bater o recorde."""
        return self.top_apple_points + self.gift_apples(kind, value)

    def _taken(self, avoid_bomb=False, avoid_food=False, avoid_gift=False):
        taken = set(self.snake)
        if avoid_bomb and self.bomb is not None:
            taken.add(self.bomb.cell)
        if avoid_bomb:
            taken.update(b.cell for b in self.flying_bombs)
        if avoid_food and self.food is not None:
            taken.add(self.food)
        if avoid_food:
            taken.update(c for c, _ in self.extra_food)
        if avoid_gift:
            taken.update(b.cell for b in self.bonus_apples)
            taken.update(g.cell for g in self.gifts_on_board)
        return taken

    def _free_cells(self, avoid_bomb=False, avoid_food=False, avoid_gift=False):
        taken = self._taken(avoid_bomb, avoid_food, avoid_gift)
        return [(x, y) for x in range(self.n) for y in range(self.n) if (x, y) not in taken]

    def _nearest_free(self, cell, taken):
        """Casa livre mais perto de `cell` (busca em largura pela arena), ou None."""
        seen, todo = {cell}, deque([cell])
        while todo:
            c = todo.popleft()
            if c not in taken:
                return c
            for dx, dy in DIRS.values():
                m = (c[0] + dx, c[1] + dy)
                if 0 <= m[0] < self.n and 0 <= m[1] < self.n and m not in seen:
                    seen.add(m)
                    todo.append(m)
        return None

    @staticmethod
    def throw_time(pace=1.0):
        """Duração do arremesso (surgir na mão + preparar + voar), mais rápido com a fila cheia."""
        return (config.PRESENTE_SURGE + config.PRESENTE_PREPARA + config.PRESENTE_VOO) * pace

    def landed(self, item):
        """O presente (ou a bomba) já caiu na arena; antes disso está na mão do duende ou voando."""
        return item is not None and self.play_time >= item.lands

    def blinking(self, item):
        """O presente (ou a bomba, ou a maçã espalhada) está nos últimos segundos e deve piscar."""
        warn = config.BOMBA_PISCA if isinstance(item, Bomb) or getattr(item, 'kind', '') == 'bomba' \
            else config.PRESENTE_PISCA
        return item is not None and item.expires is not None and item.expires - self.play_time < warn

    # ------------------------------------------------------------ presentes
    def request_gift(self, kind, value=0, label=''):
        """Pede um presente ao duende (da live): ele joga quando chegar a vez. O agradecimento ("Obrigado, @fulano")
        sai na hora, mesmo que o campo esteja lotado e o presente fique esperando na fila."""
        self.pending.append(GiftOrder(kind, value, label))
        if label:
            self.last_sender = label
            self._thank('bom', label)

    def _schedule_gift(self):
        self.next_gift = self.play_time + self.rng.uniform(*config.PRESENTE_INTERVALO)

    def _update_gifts(self):
        """Presentes por tempo (só no modo offline), sumir os que venceram, acomodar os que caíram e jogar o
        próximo da fila quando o duende estiver com a mão livre."""
        if self.gifts and not self.live and self.play_time >= self.next_gift:
            kinds = [g for g in self.gifts if self.food_to_theme[g] != self.theme] or self.gifts
            if self.rng.random() < config.CAIXA_CHANCE_OFFLINE:               # surpresa: maçãs e bombas
                self.request_gift(CAIXA, config.CAIXA_ITENS_OFFLINE)
            else:
                self.request_gift(self.rng.choice(kinds))
            self._schedule_gift()
        self.gifts_on_board = [g for g in self.gifts_on_board if g.expires is None or self.play_time < g.expires]
        self.bursts = [(c, t) for c, t in self.bursts if self.time - t < 1.0]
        self.vanished = [v for v in self.vanished if self.time - v[2] < 0.6]
        self.bonus_apples = [b for b in self.bonus_apples if b.expires is None or self.play_time < b.expires]
        body = set(self.snake)
        drop = set()
        for i, b in enumerate(self.bonus_apples):          # maçã que caiu em cima da cobra (ela passou enquanto
            if b.cell in body and self.landed(b):          # a maçã voava) escorrega para a casa livre mais perto;
                cell = self._nearest_free(b.cell, self._taken(avoid_bomb=True, avoid_food=True, avoid_gift=True))
                if cell is None:                           # sem casa livre (arena cheia): some
                    drop.add(i)
                else:
                    self.bonus_apples[i] = b._replace(cell=cell)
        if drop:
            self.bonus_apples = [b for i, b in enumerate(self.bonus_apples) if i not in drop]
        for i, g in enumerate(self.gifts_on_board):
            if self.landed(g) and not g.settled:
                self.gifts_on_board[i] = self._settle(g, avoid_gift=True)
                if self.gifts_on_board[i] is None:      # arena cheia: volta para a fila do duende (joga de novo)
                    self.pending.appendleft(GiftOrder(g.kind, g.value, g.label))
        self.gifts_on_board = [g for g in self.gifts_on_board if g is not None]
        in_air = sum(self.play_time < g.lands for g in self.gifts_on_board)
        # vários duendes jogam ao mesmo tempo (um arremesso a cada ARREMESSO_INTERVALO, até um por duende da fileira)
        while self.pending and self.play_time >= self.next_throw and in_air < self.n:
            free = self._free_cells(avoid_bomb=True, avoid_food=True, avoid_gift=True)
            if not free:                                            # campo lotado: o presente transforma bombas
                if not self._bombs_to_apples(self.gift_apples(self.pending[0].kind, self.pending[0].value)):
                    break                                           # do campo em maçãs (sem bomba: espera)
                self.pending.popleft()
                continue
            order = self.pending.popleft()
            self.next_throw = self.play_time + config.ARREMESSO_INTERVALO
            in_air += 1
            pace = max(config.PRESENTE_RITMO_MINIMO, 1 / (1 + config.PRESENTE_RITMO_FILA * len(self.pending)))
            lands = self.play_time + self.throw_time(pace)
            expires = None if self.live else lands + config.PRESENTE_DURACAO
            self.gifts_on_board.append(Gift(self.rng.choice(free), order.kind, expires, self.play_time, lands,
                                            order.value, order.label, pace))

    def _thank(self, side, label):
        """Põe na fila o duende que vai atravessar a faixa de baixo com a placa "Obrigado, @fulano" (side: 'bom' para
        presentes, 'mal' para bombas). Sai quando o anterior do mesmo lado já andou AGRADECIMENTO_INTERVALO; o mesmo
        pedido repetido enquanto o duende dele ainda anda não ganha outro, e a fila tem limite."""
        walk = config.AGRADECIMENTO_CAMINHADA
        self.thanks = [th for th in self.thanks if th.start + walk > self.play_time]      # os que já saíram da tela
        mine = [th for th in self.thanks if th.side == side]
        if mine and mine[-1].label == label:
            return
        if sum(th.start > self.play_time for th in mine) >= config.AGRADECIMENTO_FILA:
            return
        start = max(self.play_time, mine[-1].start + config.AGRADECIMENTO_INTERVALO) if mine else self.play_time
        self.thanks.append(Thanks(side, label, start))

    def _settle(self, item, avoid_gift=False):
        """Ao cair: se a casa ficou embaixo da cobra (ela andou durante o voo), escorrega para a livre mais perto.
        Sem casa livre (arena cheia), devolve None: quem chamou tira o item da arena (nada fica escondido embaixo
        do corpo, onde a cobra comeria sem querer ao entrar na casa da cauda)."""
        if item.cell in self.snake:
            taken = self._taken(avoid_bomb=True, avoid_food=True, avoid_gift=True)
            cell = self._nearest_free(item.cell, taken)
            if cell is None:
                return None
            item = item._replace(cell=cell)
        return item._replace(settled=True)

    # ------------------------------------------------------------ bomba
    def _schedule_bomb(self):
        self.next_bomb = self.play_time + self.rng.uniform(*config.BOMBA_INTERVALO)

    def _update_bomb(self):
        """A bomba que aparece sozinha (offline) some quando o tempo acaba; a próxima aparece no horário sorteado.
        A bomba mandada pela live não some: ao cair, fica no mapa até a cobra pegar (vira uma bomba parada, como as
        da caixa, mas sem prazo) e o duende do mal fica livre para jogar a próxima."""
        if self.bomb_theme is None:
            return
        self._update_live_bombs()
        if self.bomb is not None and self.bomb.expires is not None and self.play_time >= self.bomb.expires:
            self.bomb = None
            self._schedule_bomb()
        timer = not self.live and self.play_time >= self.next_bomb     # no modo live, só as pedidas
        if self.bomb is None and timer:                # offline: uma de cada vez, no horário sorteado
            free = self._free_cells(avoid_bomb=True, avoid_food=True, avoid_gift=True)
            if self.theme == self.bomb_theme or not free:   # já queimado (ou arena cheia): fica para depois
                self._schedule_bomb()
                return
            lands = self.play_time + self.throw_time()
            self.bomb = Bomb(self.rng.choice(free), lands + config.BOMBA_DURACAO, self.play_time, lands)
        if self.landed(self.bomb) and not self.bomb.settled:
            self.bomb = self._settle(self.bomb)
            if self.bomb is None:                       # caiu em cima da cobra com a arena cheia: some
                self._schedule_bomb()

    def _update_live_bombs(self):
        """Bombas pedidas pela live: vários duendes do mal jogam ao mesmo tempo (uma a cada ARREMESSO_INTERVALO), e
        cada uma, ao cair, fica no mapa até a cobra pegar (vira uma bomba parada, sem prazo)."""
        while self.bomb_queue and self.play_time >= self.next_bomb_throw and len(self.flying_bombs) < self.n:
            free = self._free_cells(avoid_bomb=True, avoid_food=True, avoid_gift=True)
            if len(free) <= config.BOMBA_CASAS_LIVRES:     # campo lotado (as últimas casas ficam para as maçãs):
                if not self._apple_to_bomb():               # a bomba transforma uma maçã do campo em bomba
                    break                                   # (sem maçã para transformar: espera na fila)
                self.bomb_queue.popleft()
                continue
            self.bomb_queue.popleft()
            pace = max(config.PRESENTE_RITMO_MINIMO, 1 / (1 + config.PRESENTE_RITMO_FILA * len(self.bomb_queue)))
            lands = self.play_time + self.throw_time(pace)
            self.flying_bombs.append(Bomb(self.rng.choice(free), None, self.play_time, lands, pace))
            self.next_bomb_throw = self.play_time + config.ARREMESSO_INTERVALO
        still = []
        for b in self.flying_bombs:
            if not self.landed(b):
                still.append(b)
                continue
            b = self._settle(b)
            if b is None:                               # caiu em cima da cobra com a arena cheia: joga de novo
                self.bomb_queue.appendleft('')
            else:                                       # fica no mapa até a cobra pegar
                self.bonus_apples.append(BonusApple(b.cell, 'bomba', b.cell, self.play_time, self.play_time, None))
        self.flying_bombs = still

    def _bombs_to_apples(self, count):
        """Campo lotado e chegou um presente: até `count` bombas paradas no campo viram maçãs (sorteadas pelo elo).
        Devolve quantas viraram (0 se não havia bomba)."""
        bombs = [b for b in self.bonus_apples if b.kind == 'bomba' and self.landed(b)]
        self.rng.shuffle(bombs)
        weights = apple_weights(self.apple_tier, self.food_to_theme)
        for b in bombs[:count]:
            kind = self.rng.choices(list(weights), list(weights.values()))[0]
            self.bonus_apples.remove(b)
            self.vanished.append((b.cell, 'bomba', self.time))              # a bomba some (efeito) e vira maçã
            self.bonus_apples.append(BonusApple(b.cell, kind, b.cell, self.play_time, self.play_time, None))
            self.bursts.append((b.cell, self.time))
        return min(count, len(bombs))

    def _apple_to_bomb(self):
        """Campo lotado: uma maçã do campo vira bomba (das espalhadas pelos presentes ou das automáticas; a principal
        fica, para a cobra sempre ter o que comer). Devolve False se não houver maçã para transformar."""
        apples = [b for b in self.bonus_apples if b.kind != 'bomba' and self.landed(b)]
        if apples:
            b = self.rng.choice(apples)
            self.bonus_apples.remove(b)
            cell, kind = b.cell, b.kind
        elif self.extra_food:
            cell, kind = self.extra_food.pop(self.rng.randrange(len(self.extra_food)))
        else:
            return False
        self.vanished.append((cell, kind, self.time))                     # a maçã some (efeito) e vira bomba
        self.bonus_apples.append(BonusApple(cell, 'bomba', cell, self.play_time, self.play_time, None))
        self.bursts.append((cell, self.time))
        return True

    def request_bomb(self, label=''):
        """Pede uma bomba ao duende do mal (presente da bomba na live): ela entra na fila e vem logo (vários
        duendes jogam ao mesmo tempo). O agradecimento sai na hora. label: quem pediu, para a placa do mal."""
        if self.bomb_theme is not None:
            self.bomb_queue.append(label)
            if label:
                self.last_bomb_sender = label
                self._thank('mal', label)

    @property
    def bomb_requests(self):
        return len(self.bomb_queue)

    def bomb_landed(self):
        """A bomba já caiu na arena (antes disso está na mão do duende do mal ou voando: não explode)."""
        return self.landed(self.bomb)

    def _explode(self, cell, from_box=False):
        """A cobra pegou a bomba: perde 10 x o tamanho, 1 de tamanho, as maçãs em volta dela somem (a até BOMBA_RAIO
        casas, em toda direção) e ela fica queimada e lenta.
        from_box: bomba que saiu da caixa de presente (a do duende do mal continua onde está)."""
        self.events.append(('bomba',))

        def near(c):
            return max(abs(c[0] - cell[0]), abs(c[1] - cell[1])) <= config.BOMBA_RAIO
        gone = [b for b in self.bonus_apples if b.kind != 'bomba' and self.landed(b) and near(b.cell)]
        self.vanished += [(b.cell, b.kind, self.time) for b in gone]                 # as bombas da caixa ficam
        self.bonus_apples = [b for b in self.bonus_apples if b not in gone]
        gone_extra = [f for f in self.extra_food if near(f[0])]
        self.vanished += [(c, k, self.time) for c, k in gone_extra]
        self.extra_food = [f for f in self.extra_food if f not in gone_extra]
        if self.food is not None and near(self.food):                    # a maçã principal aparece em outro lugar
            self.vanished.append((self.food, self.food_kind, self.time))
            self.food = None
            self.spawn_food(avoid={(cell[0] + dx, cell[1] + dy) for dx in range(-config.BOMBA_RAIO, config.BOMBA_RAIO + 1)
                                   for dy in range(-config.BOMBA_RAIO, config.BOMBA_RAIO + 1)})
        penalty = config.BOMBA_PENALIDADE * len(self.snake)
        self.score = max(0, self.score - penalty)
        self.bombs += 1
        self.shrink = True                      # a cauda sai no fim do passo
        self.popups.append(PointsPopup(cell, -penalty, self.time, 'bomba'))
        self.old_theme, self.theme = self.theme, self.bomb_theme
        self.slow_apples = 0                    # queimada: devagar de novo, e as 10 maçãs para desqueimar recomeçam
        self.wave_origin, self.wave_t = cell, 0.0
        if not from_box:
            self.bomb = None
            self._schedule_bomb()

    def bomb_blinking(self):
        """A bomba está nos últimos segundos (deve piscar)."""
        return self.blinking(self.bomb)

    def queue_turn(self, d):
        if len(self.queue) < config.MAX_QUEUED_TURNS:
            self.queue.append(d)

    def update(self, dt):
        self.time += dt
        self.popups = [p for p in self.popups if self.time - p.born < config.POPUP_SEGUNDOS]
        self.wave_t += dt
        if self.over:
            return
        self.play_time += dt
        self._update_bomb()
        self._update_gifts()
        self._update_extra_food()
        if self.food is None:                   # arena estava lotada: tenta pôr a maçã de novo
            self.spawn_food()
        self.acc += dt
        while not self.over and self.acc >= self.step_time:
            self.acc -= self.step_time
            self.step()

    def step(self):
        if self.controller is not None:         # robô jogando: decide antes de cada passo
            self.queue = [self.controller(self)]
            self.practice = not self.ranked_robot   # tecla B: treino; modo robô (a build com robô): vale
        if self.queue:
            nd = self.queue.pop(0)
            if nd != OPP[self.dir]:
                self.dir = nd
        dx, dy = DIRS[self.dir]
        hx, hy = self.snake[0]
        nh = (hx + dx, hy + dy)
        self.prev = list(self.snake)
        ate_gift = next((g for g in self.gifts_on_board if self.landed(g) and g.cell == nh), None)
        ate_bonus = next((b for b in self.bonus_apples if self.landed(b) and b.cell == nh), None)
        box_bomb = ate_bonus if ate_bonus is not None and ate_bonus.kind == 'bomba' else None
        if box_bomb is not None:                # bomba da caixa: explode (não faz crescer)
            ate_bonus = None
        ate_extra = next((f for f in self.extra_food if f[0] == nh), None)
        grow = nh == self.food or ate_gift is not None or ate_bonus is not None or ate_extra is not None
        body = self.snake if grow else self.snake[:-1]
        if not (0 <= nh[0] < self.n and 0 <= nh[1] < self.n) or nh in body:
            self.dead = True
            self.events.append(('morreu',))
            return
        self.snake.insert(0, nh)
        self.shrink = False
        if self.bomb_landed() and nh == self.bomb.cell:
            self._explode(nh)
        if box_bomb is not None:
            self.bonus_apples.remove(box_bomb)
            self._explode(nh, from_box=True)
        if grow:
            self.prev.append(self.prev[-1])
            burnt = self.theme == self.bomb_theme       # queimada: as maçãs não dão pontos
            if ate_gift is not None:            # presente: pontos, estoura em maçãs e troca o tema
                kind = ate_gift.kind
                points = self.gift_points(kind, ate_gift.value) * len(self.snake)
                new_theme = self.food_to_theme.get(kind)
                if kind == CAIXA:                               # a caixa: o tema dela (caixinhas de presente)
                    new_theme = config.CAIXA_TEMA
                self.eaten += 1
                self.apples_streak = 0          # presente: a contagem para voltar ao normal recomeça
                self.gifts_on_board.remove(ate_gift)
                self._burst(nh, ate_gift)
            elif ate_bonus is not None:         # maçã espalhada por um presente: como a maçã comum
                kind = ate_bonus.kind
                points = 0 if burnt else points_for(kind) * len(self.snake)
                new_theme = self._apple_theme(kind)
                self.bonus_apples.remove(ate_bonus)
            elif ate_extra is not None:         # maçã automática a mais: como a principal
                kind = ate_extra[1]
                points = 0 if burnt else points_for(kind) * len(self.snake)
                new_theme = self._apple_theme(kind)
                self.extra_food.remove(ate_extra)
            else:                               # maçã: valor x tamanho (já com o segmento novo)
                kind = self.food_kind
                points = 0 if burnt else points_for(kind) * len(self.snake)
                new_theme = self._apple_theme(kind)
            self.score += points
            if points:
                self.popups.append(PointsPopup(nh, points, self.time, kind))
            self.events.append(('comeu', kind))
            if new_theme is not None and new_theme != self.theme:
                self.events.append(('tema', new_theme))
                self.old_theme, self.theme = self.theme, new_theme
                self.wave_origin, self.wave_t = nh, 0.0
                if new_theme in config.TEMAS_LENTOS:   # ficou lenta: a contagem para acelerar recomeça
                    self.slow_apples = 0
            if ate_gift is None and ate_bonus is None and ate_extra is None:
                self.spawn_food()
        else:
            self.snake.pop()
        if self.shrink and len(self.snake) > config.BOMBA_TAMANHO_MINIMO:   # bomba: perde o último segmento
            self.snake.pop()
            self.prev = self.prev[:len(self.snake)]

    def _burst(self, cell, gift):
        """O presente comido estoura e espalha maçãs (sorteadas pelo elo) em casas livres aleatórias. A caixa de
        presente abre e espalha também bombas (CAIXA_FRACAO_BOMBAS dos itens), que somem com o tempo."""
        free = self._free_cells(avoid_bomb=True, avoid_food=True, avoid_gift=True)
        free = [c for c in free if c != cell]
        count = min(self.gift_apples(gift.kind, gift.value), len(free))     # sem limite: até lotar a arena
        weights = apple_weights(self.apple_tier, self.food_to_theme)
        self.bursts.append((cell, self.time))
        gap = min(0.04, config.MACA_BONUS_ESPALHAR / max(count, 1))
        bombs = round(count * config.CAIXA_FRACAO_BOMBAS) if gift.kind == CAIXA and self.bomb_theme else 0
        is_bomb = [True] * bombs + [False] * (count - bombs)
        self.rng.shuffle(is_bomb)
        for i, c in enumerate(self.rng.sample(free, max(0, count))):
            lands = self.play_time + config.MACA_BONUS_VOO + gap * i
            if is_bomb[i]:
                self.bonus_apples.append(BonusApple(c, 'bomba', cell, self.play_time + gap * i, lands, None))
            else:
                kind = self.rng.choices(list(weights), list(weights.values()))[0]
                self.bonus_apples.append(BonusApple(c, kind, cell, self.play_time + gap * i, lands, None))   # não somem

    # ------------------------------------------------------------ troca de tema
    def _apple_theme(self, kind):
        """Conta a maçã comida (de qualquer elo). Depois de MACAS_PARA_VOLTAR seguidas, sem presente no meio, a
        cobra volta ao tema padrão. Queimada pela bomba, volta na MACAS_PARA_DESQUEIMAR-ésima maçã (ou comendo um
        presente). Lenta (caracol, queimada), cada maçã a deixa mais rápida (step_time)."""
        self.apples_streak += 1
        if self.theme in config.TEMAS_LENTOS:
            self.slow_apples += 1
        default = self.food_to_theme.get(config.ALIMENTO_PADRAO, config.START_THEME)
        if self.theme == self.bomb_theme:
            return default if self.slow_apples >= config.MACAS_PARA_DESQUEIMAR else None
        if self.apples_streak >= config.MACAS_PARA_VOLTAR:
            return default
        return None

    @property
    def apples_to_reset(self):
        """Quantas maçãs faltam para a cobra voltar ao normal (0 se ela já está no tema padrão)."""
        if self.theme == self.bomb_theme:
            return max(0, config.MACAS_PARA_DESQUEIMAR - self.slow_apples)
        if self.theme == config.START_THEME:
            return 0
        return max(0, config.MACAS_PARA_VOLTAR - self.apples_streak)

    @property
    def apples_to_reset_total(self):
        """De quantas maçãs é a contagem de apples_to_reset (para a barrinha de progresso)."""
        return config.MACAS_PARA_DESQUEIMAR if self.theme == self.bomb_theme else config.MACAS_PARA_VOLTAR

    def theme_at(self, cell):
        """Tema do cenário naquela célula (onda saindo de onde a cobra comeu).

        O 2º valor é o "pulo" (0..1) do tile recém trocado.
        """
        dist = abs(cell[0] - self.wave_origin[0]) + abs(cell[1] - self.wave_origin[1])
        r = self.wave_t * config.WAVE_SPEED
        if dist < r:
            return self.theme, max(0.0, 1 - (r - dist) / 3)
        return self.old_theme, 0.0

    def segment_theme(self, i):
        """Tema do segmento i da cobra: a troca vai da cabeça para a cauda."""
        return self.theme if i <= int(self.wave_t * config.SNAKE_WAVE_SPEED) else self.old_theme

    def wave_passed(self, dist):
        """A onda de troca de cenário já passou da distância `dist` (e os tiles de lá pararam de pular)."""
        return self.wave_t * config.WAVE_SPEED > dist + 3

    def background_mix(self):
        """Quanto (0..1) a cor de fundo já passou do tema antigo para o novo."""
        return min(1.0, self.wave_t * config.WAVE_SPEED / (2 * self.n))
