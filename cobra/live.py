"""Modo live do TikTok: recebe os presentes da live e entrega ao jogo. Não depende do pygame.

A conexão usa a biblioteca TikTokLive (opcional: `pip install -r requirements-live.txt`), que só precisa do @
de quem está ao vivo. Ela roda numa thread com o próprio asyncio; o jogo chama poll() e poll_tributes() a cada
quadro, sem nunca travar esperando a rede. Se a live cai ou ainda não começou, tenta de novo espaçando as
tentativas (LIVE_ESPERAS), para não gastar o limite de requests do servidor de assinatura.

No modo live, presentes e bombas só vêm dos espectadores. As opções da live (configuracoes.json) dizem qual
presente é a bomba ('live_bomba', por padrão o "TikTok") e quais presentes aparecem ligados ('live_ligados'; sem a
lista, os que têm visual no jogo). Ligado = o presente vira ele mesmo no jogo; qualquer outro (sem visual ou
desligado) vira a caixa de presente, que solta tantos itens quanto as moedas enviadas. Nenhum presente é ignorado.
Ao conectar, a lista de presentes da live é salva (presentes_live.json) para a tela de configuração, e as fotos
dos espectadores e os ícones dos presentes são baixados para a pasta de dados (live_imagens/).

Chave do Euler Stream (opcional, aumenta o limite): variável de ambiente SIGN_API_KEY.
"""
import asyncio
import hashlib
import os
import queue
import threading
import time
import unicodedata
from collections import namedtuple

from . import config, storage
from .logic import CAIXA, GiftOrder

BOMBA = 'bomba'         # pedido especial: o duende do mal joga uma bomba
# um presente recebido na live, para o top da partida: quem mandou, foto, quantas moedas e quantos presentes
Tribute = namedtuple('Tribute', 'user nickname avatar coins gifts', defaults=(1,))


def live_available():
    """A biblioteca TikTokLive está instalada?"""
    import importlib.util
    return importlib.util.find_spec('TikTokLive') is not None


def _key(name):
    """Nome do presente sem acento, minúsculo e sem espaços nas pontas ("Rosé " -> "rose")."""
    text = unicodedata.normalize('NFKD', str(name or '')).encode('ascii', 'ignore').decode()
    return text.strip().lower()


def default_options():
    return {'live_bomba': config.LIVE_BOMBA_PADRAO, 'live_ligados': None}


def is_enabled(name, options):
    """O presente aparece ligado (vira ele mesmo no jogo)? Sem escolha do jogador, os que têm visual no jogo
    (LIVE_PRESENTES). Os desligados não somem: viram a caixa de presente."""
    chosen = options.get('live_ligados')
    if chosen is None:
        return is_known(name)
    return _key(name) in {_key(n) for n in chosen}


def is_bomb(name, options):
    return bool(options.get('live_bomba')) and _key(name) == _key(options['live_bomba'])


def gift_orders(name, coins, count=1, sender='', options=None):
    """Pedidos para o jogo a partir de um presente da live.

    O presente da bomba pede bombas ao duende do mal; presentes ligados que existem no jogo (LIVE_PRESENTES) viram
    um arremesso por unidade ("5 rosas" = 5 rosas); todos os outros (sem visual no jogo ou desligados) viram uma
    caixa de presente que vale o total de moedas enviado.
    """
    options = options if options is not None else default_options()
    count = max(1, int(count or 1))
    label = f'@{sender}: {name}' + (f' x{count}' if count > 1 else '') if sender else str(name)
    if is_bomb(name, options):
        return [GiftOrder(BOMBA, 0, label)] * count
    kind = {_key(k): v for k, v in config.LIVE_PRESENTES.items()}.get(_key(name))
    if kind is not None and is_enabled(name, options):
        return [GiftOrder(kind, 0, label)] * count
    return [GiftOrder(CAIXA, max(1, int(coins or 0)) * count, label)]


def is_known(name):
    """O presente da live tem correspondente no jogo?"""
    return _key(name) in {_key(k) for k in config.LIVE_PRESENTES}


# ---------------------------------------------------------------- top da partida
class Leaderboard:
    """Quem mais mandou presentes na partida (pelo total de moedas)."""

    def __init__(self):
        self.users = {}

    def add(self, tribute):
        cur = self.users.get(tribute.user)
        coins = (cur.coins if cur else 0) + max(0, int(tribute.coins or 0))
        gifts = (cur.gifts if cur else 0) + max(0, int(tribute.gifts or 0))
        self.users[tribute.user] = Tribute(tribute.user, tribute.nickname or (cur.nickname if cur else ''),
                                           tribute.avatar or (cur.avatar if cur else None), coins, gifts)

    def top(self, n=3):
        """Os n que mais mandaram (moedas, do maior para o menor; empate: quem mandou primeiro)."""
        ranked = sorted(enumerate(self.users.values()), key=lambda iv: (-iv[1].coins, iv[0]))
        return [t for _, t in ranked[:n]]


def apply_orders(state, orders):
    """Entrega os pedidos à partida: presentes para o duende, bombas para o duende do mal."""
    for order in orders:
        if order.kind == BOMBA:
            state.request_bomb(order.label)
        else:
            state.request_gift(order.kind, order.value, order.label)


# ---------------------------------------------------------------- lista de presentes e imagens
def catalog_path():
    return config.LIVE_CATALOGO_ARQUIVO or os.path.join(storage.data_dir(), 'presentes_live.json')


def load_catalog(path=None):
    """[{'nome', 'moedas', 'imagem'}] da última live conectada; sem arquivo, a lista inicial do config."""
    data = storage.read_json(path or catalog_path())
    items = data.get('presentes') if isinstance(data, dict) else None
    if isinstance(items, list):
        out = [i for i in items if isinstance(i, dict) and isinstance(i.get('nome'), str)]
        if out:
            return out
    return [{'nome': n, 'moedas': c, 'imagem': ''} for n, c in config.LIVE_CATALOGO_PADRAO]


def parse_gift_list(info):
    """Lista de presentes devolvida pelo TikTok ao conectar -> [{'nome', 'moedas', 'imagem'}], sem repetidos."""
    gifts = info.get('gifts', []) if isinstance(info, dict) else []
    out, seen = [], set()
    for g in gifts:
        if not isinstance(g, dict) or not g.get('name') or _key(g['name']) in seen:
            continue
        seen.add(_key(g['name']))
        urls = (g.get('image') or g.get('icon') or {}).get('url_list') or []
        out.append({'nome': g['name'], 'moedas': int(g.get('diamond_count') or 0), 'imagem': urls[0] if urls else ''})
    return sorted(out, key=lambda i: (i['moedas'], _key(i['nome'])))


def image_path(url):
    """Onde a imagem (foto de espectador, ícone de presente) fica guardada na pasta de dados."""
    ext = os.path.splitext(url.split('?')[0])[1].lower()
    ext = ext if ext in ('.png', '.jpg', '.jpeg', '.webp', '.gif') else '.img'
    name = hashlib.sha1(url.encode()).hexdigest()[:20] + ext
    return os.path.join(storage.data_dir(), 'live_imagens', name)


def _first_url(image):
    urls = getattr(image, 'url_list', None) or getattr(image, 'm_urls', None) or []
    return urls[0] if urls else None


class LiveConnection:
    """Conexão com a live de `username` numa thread. status: (estado, motivo, segundos até tentar de novo).

    estados: 'conectando', 'conectado', 'offline' (a live não está acontecendo), 'erro', 'sem_biblioteca'.
    motivos: 'fim' (a live terminou), 'nao_ao_vivo', 'nao_encontrado' ou o nome do erro.
    options: função que devolve as opções da live atuais (bomba, desligados); lida a cada presente.
    """

    def __init__(self, username, options=default_options):
        self.username = username.strip().lstrip('@')
        self.options = options
        self._orders = queue.Queue()
        self._tributes = queue.Queue()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._status = ('conectando', '', 0)
        self._loop = None
        self._client = None
        self._downloads = set()
        self._thread = threading.Thread(target=self._run, name='tiktok-live', daemon=True)

    # ---------------------------------------------------------------- lado do jogo
    def start(self):
        self._thread.start()
        return self

    def stop(self):
        """Desliga (e desconecta, se estiver conectado). Não espera a thread terminar."""
        self._stop.set()
        loop, client = self._loop, self._client
        if loop is not None and client is not None and loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(client.disconnect(), loop)
            except RuntimeError:
                pass

    @staticmethod
    def _drain(q):
        out = []
        while True:
            try:
                out.append(q.get_nowait())
            except queue.Empty:
                return out

    def poll(self):
        """Pedidos que chegaram desde a última chamada (lista de GiftOrder)."""
        return self._drain(self._orders)

    def poll_tributes(self):
        """Presentes recebidos desde a última chamada, para o top da partida (lista de Tribute)."""
        return self._drain(self._tributes)

    @property
    def status(self):
        with self._lock:
            return self._status

    def _set_status(self, state, reason='', retry_in=0):
        with self._lock:
            self._status = (state, reason, retry_in)

    # ---------------------------------------------------------------- thread
    def _run(self):
        if not live_available():
            self._set_status('sem_biblioteca')
            return
        asyncio.run(self._main())

    def _download(self, url):
        """Baixa a imagem para a pasta de dados (uma vez só), sem travar quem chamou."""
        if not url or url in self._downloads or os.path.exists(image_path(url)):
            return
        self._downloads.add(url)
        asyncio.get_running_loop().create_task(self._fetch(url))

    @staticmethod
    async def _fetch(url):
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as http:
                resp = await http.get(url)
            if resp.status_code == 200 and resp.content:
                path = image_path(url)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path + '.tmp', 'wb') as f:
                    f.write(resp.content)
                os.replace(path + '.tmp', path)
        except Exception:               # sem rede, imagem fora do ar: fica a bolinha com a inicial
            pass

    def _save_catalog(self, client):
        items = parse_gift_list(getattr(client, 'gift_info', None))
        if not items:
            return
        try:
            storage.write_json(catalog_path(), {'live': self.username, 'presentes': items})
        except OSError:
            return
        for item in items:
            self._download(item['imagem'])

    async def _main(self):
        from TikTokLive import TikTokLiveClient
        from TikTokLive.client.errors import UserNotFoundError, UserOfflineError
        from TikTokLive.events import ConnectEvent, GiftEvent
        self._loop = asyncio.get_running_loop()
        attempt = 0
        while not self._stop.is_set():
            self._set_status('conectando')
            client = TikTokLiveClient(unique_id='@' + self.username)
            self._client = client

            @client.on(ConnectEvent)
            async def on_connect(_event):
                nonlocal attempt
                attempt = 0
                self._set_status('conectado')
                self._save_catalog(client)

            @client.on(GiftEvent)
            async def on_gift(event):
                gift = event.gift
                if gift is None or (gift.type == 1 and event.streaking):     # sequência ainda rolando: espera
                    return
                user = event.user
                sender = getattr(user, 'unique_id', '') or getattr(user, 'nickname', '')
                count = max(1, int(event.repeat_count or 1))
                avatar = _first_url(getattr(user, 'avatar_jpg', None)) or _first_url(getattr(user, 'avatar_thumb', None))
                self._download(avatar)
                self._tributes.put(Tribute(sender, getattr(user, 'nickname', '') or sender, avatar,
                                           int(gift.diamond_count or 0) * count, count))
                options = self.options()
                if not is_known(gift.name) and not is_bomb(gift.name, options):     # para completar LIVE_PRESENTES
                    print(f'[live] presente sem visual no jogo (vira caixa): {gift.name!r}, {gift.diamond_count} moedas')
                for order in gift_orders(gift.name, gift.diamond_count, count, sender, options):
                    self._orders.put(order)

            try:
                await client.connect(fetch_gift_info=True)  # fica aqui enquanto a live estiver conectada
                state, reason = 'offline', 'fim'
            except UserOfflineError:
                state, reason = 'offline', 'nao_ao_vivo'
            except UserNotFoundError:
                state, reason = 'erro', 'nao_encontrado'
            except Exception as e:                          # rede, limite do servidor de assinatura...
                state, reason = 'erro', type(e).__name__
            self._client = None
            if self._stop.is_set():
                break
            wait = config.LIVE_ESPERAS[min(attempt, len(config.LIVE_ESPERAS) - 1)]
            attempt += 1
            deadline = time.monotonic() + wait
            while not self._stop.is_set() and time.monotonic() < deadline:
                self._set_status(state, reason, int(deadline - time.monotonic()) + 1)
                await asyncio.sleep(0.5)
