"""Constantes do jogo: tabuleiro, câmera, janela e velocidades."""
import os

TITLE = 'Snakift'
# modo robô (a build "com robô": python main_robo.py): o robô joga todas as partidas, que contam de verdade (ranque,
# perfil e recordes); menu, configurações e o resto funcionam normalmente. No fim, a partida segue sozinha:
# tela de PDL (ROBO_ESPERA_PDL s) -> pódio da live (ROBO_ESPERA_TOP s) -> recorde salvo -> partida nova
MODO_ROBO = os.environ.get('SNAKIFT_ROBO') == '1'
ROBO_ESPERA_PDL = 8.0
ROBO_ESPERA_TOP = 10.0

# tabuleiro
N = 11                  # células por lado (arena padrão)
ARENAS = (11, 15, 18)   # tamanhos que o jogador escolhe depois de clicar em Jogar
START_THEME = 'classico'
MAX_QUEUED_TURNS = 3    # curvas guardadas antes do próximo passo
CERCA_NA_BORDA = True   # True: cerca encostada na borda do tabuleiro; False: no centro das células de fora

# cenário (tudo o que fica fora da cerca e preenche a tela)
DENSIDADE_PROPS = 0.2   # fração das células de fora que ganha uma decoração
ESCURECER_FORA = 0.12   # o chão de fora da cerca fica 12% mais escuro (0 = igual ao de dentro)
FOLGA_CERCA = 1         # anéis de células sem decoração em volta da cerca

# câmera
SPRITES = os.path.join('assets', 'sprites')  # pasta dos sprites (gerada por tools/build.py)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_DIR = os.path.join(_ROOT, 'assets', 'ui')
AUDIO_DIR = os.path.join(_ROOT, 'assets', 'audio')     # efeitos (sfx/*.wav) e trilha (musica/)
VOLUME_EFEITOS = 0.7
VOLUME_MUSICA = 0.35         # interface chapada: capa, botões, escudos
FONT_DIR = os.path.join(_ROOT, 'assets', 'fonts')     # Poppins
ICON_DIR = os.path.join(_ROOT, 'assets', 'icones')    # ícone da janela e dos executáveis (tools/icones.py)
PERSPECTIVA = 0.15      # 0 = desligada; 0.15 = a linha do fundo fica com 85% do tamanho da da frente
SCALE_STEP = 0.01       # níveis de escala guardados em cache (objetos entre duas linhas usam o nível mais próximo)
BOARD_SLICE = 4         # altura (px) das fatias usadas para encolher o chão com perspectiva

# abertura: ao abrir o jogo, a câmera começa longe e se aproxima (qualquer tecla pula)
INTRO_SEGUNDOS = 2.8    # duração da aproximação (0 = sem abertura)
INTRO_ZOOM = 0.4        # zoom inicial: 0.4 = começa vendo uma área 2,5x maior que a tela

# janela: tamanho inicial (encolhe para caber no monitor) e mínimo. O jogo desenha no tamanho da
# janela (o zoom ajusta o tabuleiro); só abaixo do mínimo ele desenha maior e escala para a janela
WIN_W, WIN_H = 1360, 1080
MIN_W, MIN_H = 1000, 760
HUD_H = 150             # altura reservada para o placar no topo (o tabuleiro fica centralizado abaixo dele)
FPS = 60
MAX_DT = 0.25           # evita que um travamento da janela faça a cobra pular várias casas

# pontuação: cada comida vale o seu valor x o tamanho da cobra (já com o segmento que ela acabou de ganhar)
PONTOS_PADRAO = 10
ALIMENTO_PADRAO = 'maca'  # a maçã é o alimento comum: dá pontos, mas não conta como presente (nem PDL)
PONTOS = {'maca': 1, 'rosquinha': 30, 'coracao': 50,    # outras comidas valem PONTOS_PADRAO (esquilo: 10 x tamanho)
          'maca_bronze': 5, 'maca_prata': 10, 'maca_ouro': 15, 'maca_platina': 20, 'maca_esmeralda': 25,
          'maca_diamante': 30, 'maca_mestre': 35}
# uma maçã para cada elo (liga -> maçã). Na partida aparecem a maçã do elo da arena e as dos elos anteriores,
# cada elo para trás com MACA_PESO_ANTERIOR do peso do seguinte (no Mestre: 50% Mestre, 25% Diamante...)
MACAS = {'ferro': 'maca', 'bronze': 'maca_bronze', 'prata': 'maca_prata', 'ouro': 'maca_ouro',
         'platina': 'maca_platina', 'esmeralda': 'maca_esmeralda', 'diamante': 'maca_diamante', 'mestre': 'maca_mestre'}
MACA_PESO_ANTERIOR = 0.5
TAMANHO_INICIAL = 3     # segmentos da cobra no começo da partida
RECORDES_ARQUIVO = None  # None = pasta de dados do usuário (no Linux, ~/.local/share/cobra-presentes/recordes.json)
CONFIGURACOES_ARQUIVO = None  # idem, configuracoes.json (idioma escolhido no menu)
POPUP_SEGUNDOS = 0.9    # quanto tempo o "+10" fica subindo na tela depois de comer

# ranque (elo): cada arena tem o seu. Uma partida é vitória se os pontos batem a meta da liga atual.
RANQUE_LIGAS = [            # liga, comidas que a meta pede (na arena 11x11), PDL ganhos na vitória
    ('ferro', 12, 25), ('bronze', 16, 25), ('prata', 24, 20), ('ouro', 30, 20),
    ('platina', 36, 15), ('esmeralda', 46, 15), ('diamante', 55, 10), ('mestre', 67, 10),
]
# arenas maiores dão mais espaço, então a meta pede mais comidas (≈ área^0.75 em relação à 11x11)
RANQUE_ARENA = {11: 1.0, 15: 1.6, 18: 2.1}      # arena: multiplicador das comidas da meta
# meta em pontos = pontos esperados comendo essas comidas (rank.target): valor médio de uma comida no elo x
# soma dos tamanhos (a k-ésima comida vale o valor dela x (TAMANHO_INICIAL + k)). Quase tudo que se come são
# maçãs (a comum, as automáticas e as que os presentes espalham); o presente vale a maçã mais cara do elo + o valor
# dele (rank.food_value). Fração do que se come que é
# presente, medida com o robô (tools/robo.py) em cada arena:
RANQUE_PRESENTES_POR_COMIDA = {11: 0.032, 15: 0.037, 18: 0.038}
RANQUE_DIVISOES = 4         # IV, III, II, I (o Mestre não tem divisões)
RANQUE_PDL_DIVISAO = 100    # PDL para subir de divisão
RANQUE_TEMPO_X_PRESENTES = 1.0   # PDL por (minuto jogado x presente); na derrota diminui a perda
RANQUE_PDL_POR_BOMBA = 1    # PDL perdidos por bomba pega na partida (vitória ou derrota)
RANQUE_BONUS_RECORDE = 10   # entrar nos recordes da arena e do elo: +10 PDL no #1, +8 no #2 ... +2 no #5
RANQUE_BONUS_RECORDE_PASSO = 2
RANQUE_ARQUIVO = None       # None = pasta de dados do usuário (ranque.json)
PERFIL_ARQUIVO = None       # None = pasta de dados do usuário (perfil.json: estatísticas do perfil)
# skins liberadas pelo elo: skin -> liga (em qualquer arena). Ao chegar na liga, a skin é liberada e equipada
SKIN_ELO = {'ferro': 'ferro', 'bronze': 'bronze', 'prata': 'prata', 'ouro': 'ouro', 'platina': 'platina', 'esmeralda': 'esmeralda', 'diamante': 'diamante', 'mestre': 'mestre'}
SKINS_LIBERADAS = set()         # para testar: skins liberadas sem precisar do elo (ex.: {'mestre'}; vazio = jogo normal)

# bomba: aparece de vez em quando junto com a comida; se a cobra pegar, perde pontos,
# o cenário e a cobra ficam queimados e ela anda devagar (até comer outra comida)
BOMBA_TEMA = 'queimado'
BOMBA_INTERVALO = (8.0, 16.0)   # segundos de partida entre uma bomba e a próxima (sorteado nessa faixa)
BOMBA_DURACAO = 6.0             # segundos até a bomba sumir, se a cobra não pegar
BOMBA_PISCA = 2.0               # nos últimos segundos ela pisca, avisando que vai sumir
BOMBA_CASAS_LIVRES = 2          # bombas da live só caem se sobrarem tantas casas livres (para as maçãs): com a arena
                                # quase cheia, esperam na fila até abrir espaço (senão a cobra não tem o que comer)
BOMBA_RAIO = 1                  # a explosão apaga as maçãs a até tantas casas da bomba, em toda direção (3 x 3)
BOMBA_PENALIDADE = 10           # pontos perdidos x o tamanho da cobra (o placar não fica negativo); e 1 de tamanho
BOMBA_TAMANHO_MINIMO = 2        # a bomba não encolhe a cobra abaixo disso (cabeça e cauda)
# presentes (rosa, rosquinha, esquilo, caracol, coracao = mãos em coração): aparecem como a bomba, de tempos em
# tempos (no modo offline; na live, quando os espectadores mandam), e somem se a cobra
# não pegar. Valem (maçã mais cara do elo + valor deles) x tamanho, estouram em maçãs (tantas quanto o valor),
# fazem crescer e trocam o tema
PRESENTE_INTERVALO = (8.0, 16.0)
PRESENTE_DURACAO = 6.0
# agradecimento: a cada presente (ou bomba) da live, um duende atravessa a faixa embaixo da cerca com a placa
# "Obrigado, @fulano" (o do bem da esquerda para a direita, o do mal ao contrário). Vários seguidos andam em fila
AGRADECIMENTO_CAMINHADA = 7.0   # segundos para atravessar a faixa
AGRADECIMENTO_INTERVALO = 2.6   # segundos entre um duende e o próximo da fila (do mesmo lado)
AGRADECIMENTO_FILA = 6          # no máximo tantos esperando para sair (de cada lado); os outros não ganham placa
PRESENTE_PISCA = 2.0
# o duende do lado da cerca joga cada presente: ele surge na mão, o duende prepara e arremessa, e o presente
# voa até a casa sorteada; só depois de cair dá para pegar (e o PRESENTE_DURACAO começa a contar)
PRESENTE_SURGE = 0.55           # segundos do presente aparecendo na mão
PRESENTE_PREPARA = 0.3          # braço para trás
PRESENTE_VOO = 0.6              # do arremesso até cair
# ao comer um presente, ele estoura e espalha maçãs (sorteadas pelo elo) pelo mapa: tantas quanto o valor do
# presente (rosa 10, rosquinha 30, coração 50, caixa = moedas), sem limite: podem ocupar todas as casas livres.
# Elas não somem
# caixa de presente (presente da live que não existe no jogo; no modo offline também aparece): ao ser comida,
# abre e espalha maçãs e bombas, tantas quanto as moedas enviadas (offline: CAIXA_ITENS_OFFLINE). As bombas da
# caixa ficam no mapa até a cobra pegar, como as maçãs
CAIXA_ITENS_OFFLINE = 10
CAIXA_FRACAO_BOMBAS = 0.2
CAIXA_CHANCE_OFFLINE = 0.2      # chance de o presente que aparece sozinho (offline) ser a caixa
# a caixa transforma a cobra (e o cenário) no tema dela: cobra de caixinhas de presente e cenário de festa. Cada
# skin de presente só aparece com o presente dela; os presentes sem skin no jogo viram a caixa
CAIXA_TEMA = 'caixa'
# a cobra só volta ao tema padrão depois de comer MACAS_PARA_VOLTAR maçãs (de qualquer elo) sem comer presente
# no meio: comer um presente zera a contagem. Queimada pela bomba, qualquer maçã tira do queimado
MACAS_PARA_VOLTAR = 50
# lentos: no caracol (Slow Motion) e queimada (bomba) a cobra anda devagar, mas cada maçã comida a deixa um pouco mais
# rápida, até a velocidade normal na MACAS_PARA_ACELERAR-ésima. Queimada, as maçãs não dão pontos, e ela só volta ao
# normal comendo um presente ou na MACAS_PARA_DESQUEIMAR-ésima maçã
TEMAS_LENTOS = ('caracol', 'queimado')
MACAS_PARA_ACELERAR = 10
MACAS_PARA_DESQUEIMAR = 10
# maçãs do jogo na arena ao mesmo tempo, por tamanho de arena (a principal + as automáticas): já começa assim e,
# quando a cobra come uma, outra aparece na hora
MACAS_AUTOMATICAS = {11: 5, 15: 7, 18: 10}
MACAS_AUTOMATICAS_PADRAO = 5    # outras arenas
MACA_BONUS_VOO = 0.55           # segundos voando do presente até a casa (cada uma sai um pouquinho depois)
MACA_BONUS_ESPALHAR = 0.8       # todas saem dentro desse tempo (muitas maçãs: saem mais juntas)
PRESENTE_RITMO_FILA = 0.25      # com presentes na fila o duende joga mais rápido: duração / (1 + 0,25 x fila)
PRESENTE_RITMO_MINIMO = 0.35    # ... até 35% da duração normal
ARREMESSO_INTERVALO = 0.15      # s entre um arremesso e o próximo: vários duendes jogam ao mesmo tempo (cada item sai
                                # do duende livre mais perto de onde cai), então 10 bombas chegam quase juntas

# modo live do TikTok (cobra/live.py). Presentes da live com o mesmo nome dos do jogo viram esses presentes (um
# arremesso por unidade); os outros viram a caixa de presente, que vale as moedas enviadas. Os nomes são os do
# TikTok em inglês; os que chegarem e não estiverem aqui aparecem no terminal, para você completar a lista
# a 'Rose' (1 moeda) fica de fora: quem vira a rosa do jogo é o presente 'Rosa'
LIVE_PRESENTES = {'Rosa': 'rosa', 'Donut': 'rosquinha', 'Doughnut': 'rosquinha', 'Rosquinha': 'rosquinha',
                  'Squirrel': 'esquilo', 'Esquilo': 'esquilo', 'Hand Heart': 'coracao', 'Hand Hearts': 'coracao',
                  'Mãos em coração': 'coracao', 'Slow Motion': 'caracol', 'Câmera lenta': 'caracol'}
# só os presentes com visual no jogo (LIVE_PRESENTES) começam ligados; os outros o jogador liga na tela da live
# (e eles viram a caixa de presente). Qualquer presente pode ser escolhido como a bomba
LIVE_BOMBA_PADRAO = 'TikTok'    # presente da live que pede uma bomba ao duende do mal (muda na tela da live)
LIVE_TOP = 3                    # quantos espectadores aparecem no top da partida
LIVE_CATALOGO_ARQUIVO = None    # None = pasta de dados (presentes_live.json: lista salva ao conectar na live)
# lista inicial da tela "Presentes da live", até conectar numa live (aí vem a lista real, com os ícones);
# moedas aproximadas (None = o valor só aparece quando conectar na live)
LIVE_CATALOGO_PADRAO = (('Rosa', None), ('Rose', 1), ('TikTok', 1), ('GG', 1), ('Ice Cream Cone', 1),
                        ('Heart Me', 1), ('Squirrel', 1), ('Finger Heart', 5), ('Perfume', 20), ('Doughnut', 30),
                        ('Hand Heart', 100), ('Slow Motion', None), ('Galaxy', 1000), ('Lion', 29999),
                        ('Universe', 44999))
LIVE_ESPERAS = (5, 10, 30, 60)  # segundos entre as tentativas de reconectar (a última se repete)

# velocidades
STEP = {'classico': 0.15, 'rosa': 0.14, 'rosquinha': 0.13, 'esquilo': 0.11, 'caracol': 0.26, 'coracao': 0.14, 'caixa': 0.14,  # s por passo; caracol = câmera lenta
        'queimado': 0.26}      # queimado (bomba): lento como o caracol
WAVE_SPEED = 18.0       # tiles por segundo da onda de troca de cenário
SNAKE_WAVE_SPEED = 25.0  # segmentos por segundo da troca de tema na cobra
