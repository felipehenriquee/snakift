"""Robô que joga sozinho (piloto automático no jogo, tecla B, main_robo.py e tools/robo.py). Não depende do pygame.

No começo (as primeiras HAMILTON_AFTER maçãs): vai direto no item mais perto pelo menor caminho, desde que depois
ainda alcance a cauda; senão segue a cauda (_greedy). Parece natural, mas com a cobra grande ela se tranca.

Para encher a arena inteira: segue um ciclo que passa por todas as casas (ciclo hamiltoniano), sorteado a cada
partida (o contorno de um labirinto aleatório: cycle), para o robô não andar sempre do mesmo jeito.
Primeiro se alinha (_align: anda sempre para a frente no ciclo, por jogadas seguras, até o corpo inteiro ficar em
ordem nele); depois segue o ciclo (_hamilton), cortando caminho até o item mais perto quando o atalho fica entre a
cabeça e a cauda. Com o corpo em ordem no ciclo, as casas à frente da cabeça até a cauda estão sempre livres e ela
nunca se tranca, por maior que fique. Nas arenas ímpares (11, 15) não existe ciclo por todas as casas: o canto
(0, 0) fica de fora, e a maçã que cair nele é pega com um desvio do mesmo tamanho.

Desvia das bombas; só passa por uma se não houver outra jogada segura.
"""
import random
from collections import deque

from . import config
from .logic import DIR_FROM_DELTA, DIRS

GOALS_TRIED = 6         # itens testados por jogada, do mais perto para o mais longe (o resto fica para depois)
HAMILTON_AFTER = 0      # depois de comer tantas maçãs, a cobra passa a seguir o ciclo (antes vai direto no item, que
                        # parece mais natural). Medido nas simulações (presentes e bombas) quantas enchem a arena:
                        # 0 = 100%, 5 = 98%, 10 = ~75%, 15 = ~55% (a cobra já grande não consegue entrar no ciclo)
SHORTCUT_MAX = 0.6      # atalhos no ciclo só até a cobra ocupar essa fração da arena (depois só segue o ciclo)
HUNGER_LAPS = 2         # sem comer nada por tantas voltas na arena (passos = isso x casas): para de evitar as
                        # bombas (muitas bombas da live paradas podem prender a cobra num laço sem fim)
DODGE_MAX = 5           # até esse tamanho, se o ciclo mandar para uma bomba, desvia por uma jogada segura fora dele
                        # (depois volta a se alinhar); maior, sair do ciclo é arriscado (ela não consegue voltar e
                        # empaca): pega a bomba, que só tira um pedaço e alguns pontos
GEOMETRIC = True        # atalhos pela distância de verdade até o item (False: pela ordem do ciclo)


def _nbrs(c, n):
    for d, (dx, dy) in DIRS.items():
        x, y = c[0] + dx, c[1] + dy
        if 0 <= x < n and 0 <= y < n:
            yield d, (x, y)


def _bfs(start, goal, blocked, n):
    """Caminho mais curto (lista de células, sem a de partida) ou None."""
    prev, q = {start: None}, deque([start])
    while q:
        c = q.popleft()
        if c == goal:
            path = []
            while c != start:
                path.append(c)
                c = prev[c]
            return path[::-1]
        for _, m in _nbrs(c, n):
            if m not in prev and (m not in blocked or m == goal):
                prev[m] = c
                q.append(m)
    return None


def _distances(start, blocked, n):
    """Passos do caminho mais curto de `start` até cada casa alcançável (sem passar por `blocked`)."""
    dist, q = {start: 0}, deque([start])
    while q:
        c = q.popleft()
        for _, m in _nbrs(c, n):
            if m not in dist and m not in blocked:
                dist[m] = dist[c] + 1
                q.append(m)
    return dist


def _area(start, blocked, n):
    seen, q = {start}, deque([start])
    while q:
        c = q.popleft()
        for _, m in _nbrs(c, n):
            if m not in seen and m not in blocked:
                seen.add(m)
                q.append(m)
    return len(seen)


# ---------------------------------------------------------------- ciclo hamiltoniano
_CYCLES = {}


def cycle(n, seed=0):
    """(casas do ciclo em ordem, índice de cada casa, casa que fica de fora ou None) da arena n x n.

    O ciclo é o contorno de um labirinto sorteado (seed): a arena é dividida em blocos de 2 x 2 casas, os blocos são
    ligados por uma árvore aleatória e o caminho dá a volta nas paredes dela, passando por todas as casas. Cada
    partida sorteia um labirinto, então o robô não anda sempre do mesmo jeito. Arena ímpar: o labirinto fica nas
    casas 1..n-1 e a linha 0 e a coluna 0 (menos o canto (0, 0), que fica de fora) entram em pares pelas bordas.
    """
    key = (n, seed)
    if key not in _CYCLES:
        if len(_CYCLES) > 64:
            _CYCLES.clear()
        cells = _maze_cycle(n, seed)
        _CYCLES[key] = (cells, {c: i for i, c in enumerate(cells)}, (0, 0) if n % 2 else None)
    return _CYCLES[key]


def _maze_cycle(n, seed):
    rnd = random.Random(seed)
    off = n % 2                                     # ímpar: o labirinto começa na casa 1
    size = (n - off) // 2                           # blocos por lado
    blocks = [(i, j) for i in range(size) for j in range(size)]
    walls = [((i, j), (i + 1, j)) for i in range(size - 1) for j in range(size)]
    walls += [((i, j), (i, j + 1)) for i in range(size) for j in range(size - 1)]
    rnd.shuffle(walls)
    parent = {b: b for b in blocks}

    def root(b):
        while parent[b] != b:
            parent[b] = parent[parent[b]]
            b = parent[b]
        return b
    tree = set()
    for a, b in walls:                              # árvore aleatória (Kruskal): o labirinto
        ra, rb = root(a), root(b)
        if ra != rb:
            parent[ra] = rb
            tree.add((a, b))
    adj = {}

    def link(p, q):
        adj.setdefault(p, set()).add(q)
        adj.setdefault(q, set()).add(p)

    def unlink(p, q):
        adj[p].discard(q)
        adj[q].discard(p)

    def cell(bx, by, dx, dy):
        return off + 2 * bx + dx, off + 2 * by + dy
    for bx, by in blocks:                           # o caminho contorna as paredes do labirinto
        tl, tr, bl, br = cell(bx, by, 0, 0), cell(bx, by, 1, 0), cell(bx, by, 0, 1), cell(bx, by, 1, 1)
        right, down = ((bx, by), (bx + 1, by)) in tree, ((bx, by), (bx, by + 1)) in tree
        if ((bx, by - 1), (bx, by)) not in tree:
            link(tl, tr)
        if not down:
            link(bl, br)
        if ((bx - 1, by), (bx, by)) not in tree:
            link(tl, bl)
        if not right:
            link(tr, br)
        if right:
            link(tr, cell(bx + 1, by, 0, 0))
            link(br, cell(bx + 1, by, 0, 1))
        if down:
            link(bl, cell(bx, by + 1, 0, 0))
            link(br, cell(bx, by + 1, 1, 0))
    if off:                                         # ímpar: linha 0 e coluna 0 encaixadas em pares nas bordas
        for k in range(size):
            a, b = (1 + 2 * k, 1), (2 + 2 * k, 1)   # borda de cima: a -> (a, 0) -> (b, 0) -> b
            unlink(a, b)
            link(a, (a[0], 0))
            link((a[0], 0), (b[0], 0))
            link((b[0], 0), b)
            a, b = (1, 1 + 2 * k), (1, 2 + 2 * k)   # borda da esquerda: a -> (0, a) -> (0, b) -> b
            unlink(a, b)
            link(a, (0, a[1]))
            link((0, a[1]), (0, b[1]))
            link((0, b[1]), b)
    start = (off, off)
    cells, prev, cur = [start], None, start
    while True:                                     # percorre o contorno
        nxt = next(c for c in sorted(adj[cur]) if c != prev)
        if nxt == start:
            break
        cells.append(nxt)
        prev, cur = cur, nxt
    return cells


def _game_cycle(s):
    """O ciclo desta partida (um labirinto sorteado por partida: match_seed, do GameState)."""
    return cycle(s.n, getattr(s, 'match_seed', 0))


def _hamilton(s, bombs):
    """Jogada pelo ciclo (com atalhos seguros) ou None se o corpo não está em ordem no ciclo."""
    n, body, head = s.n, s.snake, s.snake[0]
    cells, order, skip = _game_cycle(s)
    size = len(cells)

    def idx(c):                                     # o canto conta como a casa que o desvio pula, (1, 1)
        return order[(1, 1)] if c == skip else order[c]

    for sign in (1, -1):                            # o ciclo vale nos dois sentidos: o que deixa o corpo em ordem
        def ahead(a, b, sign=sign):
            return (sign * (idx(b) - idx(a))) % size
        steps = [ahead(body[k + 1], body[k]) for k in range(len(body) - 1)]
        if all(st >= 1 for st in steps) and sum(steps) < size:
            break
    else:
        return None
    entry, exit_ = (None, None) if not skip else ((1, 0), (0, 1)) if sign == 1 else ((0, 1), (1, 0))
    if head == skip:                                # no canto: sai pelo outro lado do desvio (livre ou a cauda)
        return None if exit_ in body[:-1] else DIR_FROM_DELTA[(exit_[0] - head[0], exit_[1] - head[1])]
    gap = ahead(head, body[-1]) if len(body) > 1 else size      # casas livres à frente até a cauda (+1)
    items = [g.cell for g in s.gifts_on_board if s.landed(g)]
    items += [b.cell for b in getattr(s, 'bonus_apples', []) if s.landed(b) and b.kind != 'bomba']
    items += list(getattr(s, '_robot_targets', ()))     # travada: as bombas viram alvo (para destravar)
    if s.food is not None:
        items.append(s.food)
    items += [c for c, _ in getattr(s, 'extra_food', [])]
    edible = set(items)                             # tudo que faz crescer (até o que estiver embaixo do corpo)
    items = [c for c in items if c not in body]
    goal = min(items, key=lambda c: ahead(head, c), default=None)   # o item mais perto à frente, pelo ciclo
    occupied = set(body[:-1])
    fills = len(body) + 1 == n * n                  # comer agora enche a arena: venceu
    twin = (1, 1) if skip else None                 # a casa que o desvio do canto pula
    # maçã no canto (ou na casa que o desvio pula): sem atalhos, para os buracos do corpo sumirem e sobrar
    # espaço à frente quando a cabeça passar pela entrada do desvio (senão ela chega sempre com a cauda colada)
    shortcuts = len(body) <= SHORTCUT_MAX * size and (goal is None or goal not in (skip, twin))
    moves = []
    for d, m in _nbrs(head, n):
        if m in occupied:
            continue
        if skip and ((m == twin and skip in occupied) or (m == skip and twin in occupied)):
            continue                                # canto e (1, 1) contam como a mesma casa: um de cada vez
        if fills and m in items:                    # a última casa: come e vence
            moves.append((-2, d, m))
            continue
        if m == twin and body[-1] == skip and m not in edible:  # cauda no canto: passa por (1, 1) em vez de
            moves.append((-1, d, m))                # seguir a cauda pelo canto (senão vira rota fixa e (1, 1) fica
            continue                                # para sempre de fora)
        if m == skip and m == body[-1] and m not in edible:     # a cauda no canto: segue atrás dela (ela anda)
            moves.append((ahead(m, goal) if goal is not None else 1, d, m))
            continue
        if m == skip:                               # entra no canto só pela maçã de lá, com a saída livre
            # a saída tem que estar livre à frente ou ser a própria cauda (que anda no passo seguinte)
            if m in items and head == entry and ahead(head, exit_) <= gap:
                moves.append((-1, d, m))            # antes da casa que o desvio pula (que conta como o canto)
            continue
        step = ahead(head, m)
        if step > 1 and not shortcuts:
            continue
        if 1 <= step < gap or (m == body[-1] and m not in edible):     # só para a frente, antes da cauda
            # (a cauda só anda se a casa dela não tiver comida: senão a cobra cresce e bate nela)
            moves.append((ahead(m, goal) if goal is not None else step, d, m))
    if GEOMETRIC and shortcuts and goal is not None and goal != skip:
        # atalhos pela distância de verdade até o item (como a estratégia antiga), só por casas permitidas: à
        # frente da cabeça no ciclo, antes do item e da cauda. Fica natural com a cobra pequena e continua seguro
        limit = min(ahead(head, goal), gap - 1)
        window = {c for c in order if 0 < ahead(head, c) <= limit and c not in occupied and c not in bombs}
        if goal in window:
            dist, todo = {goal: 0}, deque([goal])
            while todo:
                c = todo.popleft()
                for _, nb in _nbrs(c, n):
                    if nb in window and nb not in dist:
                        dist[nb] = dist[c] + 1
                        todo.append(nb)
            near = [(dist[m], -ahead(head, m), d, m) for key, d, m in moves if m in dist]
            if near:
                return min(near)[2]
    safe = [mv for mv in moves if mv[2] not in bombs]
    if goal is not None:
        # bomba parada no ciclo: as outras jogadas seguras só voltam no ciclo (a cobra roda atrás da cauda num
        # circuito pequeno e nunca chega no item). Se só a bomba chega mais perto, ela trava o caminho: a cobra
        # pequena desvia por fora do ciclo (choose), a grande passa por ela
        here = ahead(head, goal)
        if not any(mv[0] < here for mv in safe) and any(mv[0] < here for mv in moves):
            safe = []
    pick = min(safe or moves, default=None)         # bomba só se não houver outra jogada segura
    return pick[1] if pick else None


def choose(s, avoid_bombs=True):
    """Direção da próxima jogada para o estado `s` (cobra.logic.GameState).

    Nas primeiras HAMILTON_AFTER maçãs, a estratégia antiga (vai direto no item mais perto). Depois, o ciclo (para
    encher a arena): se o corpo ainda não está em ordem nele, primeiro se alinha (_align); depois segue o ciclo.

    avoid_bombs=False (o robô das lives): desvia das bombas como sempre, mas se todas as jogadas sem bomba o deixam
    preso no futuro, pega a bomba como último recurso.
    """
    bombs = {s.bomb.cell} if s.bomb else set()          # desvia também enquanto ela voa (vai cair ali)
    bombs |= {b.cell for b in getattr(s, 'flying_bombs', [])}                        # as da live voando
    bombs |= {b.cell for b in getattr(s, 'bonus_apples', []) if b.kind == 'bomba'}   # e as paradas no mapa
    if len(s.snake) + 1 == s.n * s.n:                   # comer a última casa livre enche a arena: vence
        last = {g.cell for g in s.gifts_on_board if s.landed(g)} | {c for c, _ in getattr(s, 'extra_food', [])}
        last |= {b.cell for b in getattr(s, 'bonus_apples', []) if s.landed(b) and b.kind != 'bomba'}
        if s.food is not None:
            last.add(s.food)
        for d, m in _nbrs(s.snake[0], s.n):
            if m in last:
                return d
    progress = (len(s.snake), s.score)                  # comeu alguma coisa desde a última jogada?
    if progress != getattr(s, '_robot_progress', None):
        s._robot_progress, s._robot_hunger = progress, 0
    s._robot_hunger = getattr(s, '_robot_hunger', 0) + 1
    hungry = s._robot_hunger > HUNGER_LAPS * s.n * s.n  # travada (bombas demais no caminho): vai até elas
    if hungry:
        targets, bombs = set(bombs), set()
    else:
        targets = set()
    s._robot_targets = targets                          # bombas que viram alvo (_hamilton), até no canto
    if getattr(s, '_robot_dodge', None) == progress and len(s.snake) <= DODGE_MAX:
        return _greedy(s, bombs, avoid_bombs)           # desviando de uma bomba no ciclo: vai direto até comer algo
    if len(s.snake) >= config.TAMANHO_INICIAL + HAMILTON_AFTER:      # cada maçã comida = uma bolinha a mais
        move = _hamilton(s, bombs)
        if move is not None:
            s._robot_align = None                   # já está no ciclo
            dx, dy = DIRS[move]
            if (s.snake[0][0] + dx, s.snake[0][1] + dy) in bombs and len(s.snake) <= DODGE_MAX:
                alt, safe = _choose(s, bombs)       # o ciclo manda para a bomba: desvia, se for seguro
                ax, ay = DIRS[alt]
                if safe and (s.snake[0][0] + ax, s.snake[0][1] + ay) not in bombs:
                    s._robot_dodge, s._robot_align = progress, None     # (voltando ao ciclo, ela batia de novo
                    return alt                                          # na bomba e rodava atrás da cauda)
            return move
        move = _align(s, bombs)                     # ainda não: entra no ciclo
        if move is not None:
            return move
    else:
        s._robot_align = None
    return _greedy(s, bombs, avoid_bombs)


def _align(s, bombs):
    """Transição para o ciclo. Ao começar, guarda o sentido do ciclo e a casa de partida; a cada passo anda o
    mínimo para a frente no ciclo a partir dela (sem dar a volta: senão a cobra roda num circuito pequeno e o corpo
    nunca cabe em menos de uma volta), só por jogadas em que ainda alcança a cauda. Depois de andar o próprio
    tamanho assim, o corpo inteiro está em ordem no ciclo e _hamilton assume. Se travar (nenhuma jogada assim),
    devolve None: a estratégia antiga decide e a transição recomeça de onde a cobra estiver."""
    n, body, head = s.n, s.snake, s.snake[0]
    cells, order, skip = _game_cycle(s)
    size = len(cells)
    if head == skip:
        return None
    edible = {g.cell for g in s.gifts_on_board if s.landed(g)}
    edible |= {b.cell for b in getattr(s, 'bonus_apples', []) if s.landed(b) and b.kind != 'bomba'}
    if s.food is not None:
        edible.add(s.food)
    edible |= {c for c, _ in getattr(s, 'extra_food', [])}
    state = getattr(s, '_robot_align', None)
    if state is None:
        def ordered(sign):                          # quantas casas a partir da cabeça já estão em ordem no ciclo
            k = 0
            while k + 1 < len(body) and skip not in (body[k], body[k + 1]) and \
                    (sign * (order[body[k]] - order[body[k + 1]])) % size >= 1:
                k += 1
            return k
        sign = max((1, -1), key=ordered)
        state = s._robot_align = (sign, order[head])
    sign, start = state

    def progress(c):                                # quanto já andou para a frente desde a casa de partida
        return (sign * (order[c] - start)) % size
    best = None
    for d, m in _nbrs(head, n):
        if m == skip or m in body[:-1] or (m == body[-1] and m in edible):
            continue
        if progress(m) <= progress(head):           # só para a frente, sem dar a volta no ciclo
            continue
        virt = ([m] + body) if m in edible else ([m] + body[:-1])     # comendo, a cauda não anda
        if _bfs(m, virt[-1], set(virt[1:-1]) | (bombs - {m}), n) is None:
            continue
        key = (m in bombs, progress(m))             # bomba só se for a única jogada para a frente (senão a
        if best is None or key < best[0]:           # cobra fica solta e, grande, não consegue mais se alinhar)
            best = (key, d)
    if best is None:
        s._robot_align = None
        return None
    return best[1]


def _greedy(s, bombs, avoid_bombs):
    """Estratégia antiga: o item mais perto pelo caminho, se depois ainda alcançar a cauda; senão segue a cauda."""
    move, safe = _choose(s, bombs)
    if safe or avoid_bombs or not bombs:
        return move
    return _choose(s, set())[0]                         # último recurso: passa pela bomba para não se trancar


def _choose(s, bomb):
    """(direção, segura?) evitando as casas `bomb`. Segura = depois dela a cabeça ainda alcança a cauda."""
    n, snake, head = s.n, s.snake, s.snake[0]
    body = set(snake[:-1]) | bomb
    # itens positivos (presentes caídos, maçãs espalhadas e a maçã): vai no mais perto pelo caminho de verdade
    items = [(g.cell, None if g.expires is None else (g.expires - s.play_time) / s.step_time)
             for g in s.gifts_on_board if s.landed(g)]                   # na mão do duende ou voando não dá
    items += [(b.cell, None) for b in getattr(s, 'bonus_apples', []) if s.landed(b) and b.kind != 'bomba']
    if s.food is not None:
        items.append((s.food, None))
    items += [(c, None) for c, _ in getattr(s, 'extra_food', [])]
    dist = _distances(head, body, n)
    goals = sorted(((g, left) for g, left in items if g in dist and g not in snake), key=lambda gl: dist[gl[0]])
    edible = {g for g, _ in goals}                      # passar por cima de outra comida no caminho a faria
    for goal, steps_left in goals[:GOALS_TRIED]:       # crescer antes da hora: desvia delas
        path = _bfs(head, goal, body | (edible - {goal}), n)
        if path and (steps_left is None or len(path) < steps_left):
            virt = (list(reversed(path)) + snake)[:len(snake) + 1]      # simula comer: ainda chega na cauda?
            if len(virt) <= 2 or _bfs(virt[0], virt[-1], set(virt[1:-1]) | bomb, n) is not None:
                return next(d for d, m in _nbrs(head, n) if m == path[0]), True
    best, best_key = None, None                         # segue a cauda, preferindo a jogada que mais enrola
    for d, m in _nbrs(head, n):
        if m in body:
            continue
        virt = [m] + snake[:-1]
        reaches_tail = _bfs(m, virt[-1], set(virt[1:-1]) | bomb, n) is not None
        key = (reaches_tail, _area(m, set(virt[1:]) | bomb, n), abs(m[0] - snake[-1][0]) + abs(m[1] - snake[-1][1]))
        if best_key is None or key > best_key:
            best, best_key = d, key
    return best or s.dir, best_key is not None and best_key[0]
