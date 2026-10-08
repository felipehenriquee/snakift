# Snakift (Cobra dos Presentes): sprites 3D em visão 3/4

## Como rodar
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```
Com o robô (build "com robô"): `python main_robo.py`. É o mesmo jogo, mas o robô joga todas as partidas, e elas
contam de verdade (ranque, perfil, recordes e presenteadores). Menu, configurações, skins e a live funcionam
normalmente; o robô só começa ao apertar Jogar, e Esc pausa (dá para sair para o menu). No fim, a partida segue
sozinha: tela de PDL (`ROBO_ESPERA_PDL`, 8 s) -> pódio da live (`ROBO_ESPERA_TOP`, 10 s) -> recorde salvo -> partida
nova na mesma arena. As duas builds saem de `main.py` (sem robô) e `main_robo.py` (com robô).

Testes: `python -m unittest` (não precisa de pygame).
Screenshots sem abrir janela: `python tools/screenshots.py` (salva em `_nao_usados/screenshots/`).

## Executáveis (.exe)

- No Windows: copie a pasta do projeto para o PC e dê dois cliques em `build_windows.bat`. Ele instala o que
  precisa (Python 3.10+ tem que estar instalado, de python.org), gera `dist\Snakift.exe` (jogo normal) e
  `dist\Snakift Robo.exe` (o robô joga) e cria os dois atalhos na Área de Trabalho, com os ícones
- Em qualquer sistema: `python tools/build_exe.py` (ou `normal` / `robo` para gerar só um). Precisa do
  `pyinstaller` e do `requirements-live.txt` instalados; sem o TikTokLive o executável não conecta na live.
  O PyInstaller só gera executável para o sistema em que roda (no Linux saem `dist/Snakift` e `dist/Snakift Robo`)
- Cada executável é um arquivo só, com os assets dentro. Os dados do jogador (recordes, elo, perfil,
  configurações e o ranque de presenteadores) ficam na pasta de dados do usuário (`%APPDATA%\cobra-presentes`),
  a mesma para as duas versões; trocar o .exe por um novo não apaga nada
- Ícones: `assets/icones/snakift.ico` e `snakift_robo.ico` (a cobra clássica; a do robô tem antena e fone), também
  usados na janela do jogo. Para refazer: `python tools/icones.py`
- O Windows pode avisar "O Windows protegeu o computador" na primeira vez (o .exe não é assinado): clique em
  "Mais informações" e "Executar assim mesmo"

## Pastas
- `cobra/`: o jogo (só depende do pygame). `main.py` abre o jogo.
- `assets/`: tudo que o jogo carrega
  - `sprites/`: temas, skins, avatares, comidas, duendes, sombra e `manifest.json` (gerados por `tools/build.py`)
  - `ui/`: interface chapada (capa, botões, escudos) · `fonts/`: Poppins · `audio/`: efeitos (`sfx/`) e trilha (`musica/`)
- `tools/`: geradores (não vão no jogo): `build.py` e modelos 3D dos sprites, `ui/` (interface e escudos chapados),
  `audio/som.py` (sons), `robo.py`, `screenshots.py`
- `tests/`: testes
- `_nao_usados/`: arquivo morto, fora do jogo (demo e sprites antigos, isométricos, zips, menus antigos, escudos 3D,
  pacote original do tema coração, mp3 original da mordida, screenshots). Pode apagar se não quiser guardar.

## Modo live do TikTok
Ao apertar JOGAR, escolha **Offline** (presentes aparecem de tempos em tempos) ou **Live do TikTok** (digite o @
de quem está ao vivo). No modo live o duende joga os presentes que chegam na live e eles não somem:
- presentes que existem no jogo (`LIVE_PRESENTES` no `config.py`: Rosa = rosa (a "Rose" de 1 moeda fica de fora), Donut = rosquinha, Squirrel =
  esquilo, Slow Motion = caracol, Hand Heart = mãos em coração) viram um arremesso por unidade ("5 rosas" = 5 rosas); os outros, se
  o jogador ligar, viram uma **caixa de presente** que vale (maçã mais cara do elo + moedas enviadas) x tamanho. Presentes fora da lista aparecem no terminal com o nome
  e as moedas, para completar a lista
- no modo live, presentes e bombas só vêm dos espectadores (nada aparece por tempo). A bomba é um presente da
  live: por padrão o "TikTok" (1 moeda; `LIVE_BOMBA_PADRAO`). Na tela do modo, **Presentes da live** abre a grade
  de presentes. Aparecem ligados os que têm visual no jogo (Rosa, Donut, Squirrel, Slow Motion e Hand Heart /
  Mãos em coração): esses viram eles mesmos. Todos os outros (sem visual, ou desligados com um clique) viram a caixa
  de presente, que solta tantos itens quanto as moedas enviadas: nenhum presente é ignorado. A bombinha
  no canto faz de qualquer presente a bomba (fica salvo em `configuracoes.json`: `live_bomba` e `live_ligados`). A lista vem da live ao conectar
  (`presentes_live.json` na pasta de dados, com os ícones em `live_imagens/`); antes disso, uma lista inicial
- no fim da partida, o resumo mostra o top 3 de quem mais mandou presentes (pelo total de moedas), com a foto
  do espectador (baixada da live) ou a inicial.
- no modo live, presentes e bombas vêm **só** dos presentes dos espectadores (nada aparece por tempo, e comentários
  no chat não fazem nada); a caixa de presente solta tantos itens (maçãs e bombas) quanto as moedas enviadas
- vários duendes jogam ao mesmo tempo: um arremesso a cada `ARREMESSO_INTERVALO` (0,15 s), cada item saindo do
  duende livre mais perto de onde ele cai (10 bombas chegam todas em ~3 s)
- campo lotado: o agradecimento sai na hora mesmo assim, cada bomba da live transforma uma maçã do campo em bomba
  (das espalhadas ou das automáticas; a principal fica) e cada presente transforma bombas do campo em maçãs (tantas
  quanto o valor dele); sem o que transformar, eles esperam na fila
- as bombas mandadas pela live e as da caixa de presente não somem: ficam no mapa até a cobra pegar (só a que
  aparece sozinha no modo offline some com o tempo)
- agradecimento: a cada presente (ou bomba) da live, um duende atravessa a faixa embaixo da cerca segurando a placa
  "Obrigado, @fulano" com o ícone do presente embaixo (e "x5" se foram vários) (o do bem da esquerda para a direita, o do mal ao contrário). Vários
  seguidos saem em fila (`AGRADECIMENTO_CAMINHADA`, `AGRADECIMENTO_INTERVALO`, `AGRADECIMENTO_FILA`)
- a fila de arremessos não tem limite: o duende joga mais rápido quando ela cresce e espera abrir espaço se a
  arena lotar; o que cai em cima da cobra escorrega para a casa livre mais perto
- precisa da biblioteca TikTokLive: `pip install -r requirements-live.txt` (o jogo funciona sem ela, só não
  conecta). Chave opcional do Euler Stream (aumenta o limite de conexões): variável de ambiente `SIGN_API_KEY`.
  Se a live cai ou ainda não começou, o jogo tenta de novo em 5, 10, 30 e 60 s (`LIVE_ESPERAS`)
- **B** durante a partida: o robô assume o controle (B de novo devolve) e continua ligado nas próximas partidas.
  Partidas em que o robô jogou são **treino**: não contam para ranque,
  perfil nem recordes. O robô fica em `cobra/robot.py`

## Sons
Efeitos e trilha em `assets/audio` (`AUDIO_DIR` no `config.py`; gerados por `tools/audio/som.py`):
- trilha `musica/trilha_loop.ogg` em loop no menu e na partida (`VOLUME_MUSICA`)
- `comer_maca` ao comer qualquer maçã (convertido de `_nao_usados/audio_original/carrot_crunch.mp3`: cortado e em WAV); `comer_<presente>` ao comer rosa, rosquinha, esquilo, caracol e mãos em coração (a caixa da live usa o do
  coração); `transformar` quando a cobra volta ao normal (50 maçãs seguidas); `explosao` ao pegar a bomba; `contagem_321_vai` na
  aproximação da câmera antes da partida; `game_over` ao morrer; `subir_elo` quando a barra do ranque sobe de
  elo; `subir_nivel` quando sobe de nível (`VOLUME_EFEITOS`)
- volume (Configurações e pausa): Som geral, Música e Efeitos, de 0 a 100% com os botões − e +; o volume de cada parte é o geral vezes o dela. Sem placa de som, o jogo fica em silêncio
- `cobra/audio.py`; a partida avisa o que aconteceu em `GameState.events`

## Código
- `main.py`: ponto de entrada
- `cobra/config.py`: constantes (tabuleiro, câmera, janela, velocidades por tema)
- `cobra/logic.py`: regras do jogo (`GameState`). Não usa pygame, por isso dá para testar
- `cobra/scenery.py`: cerca e decoração em volta do tabuleiro (a partida acontece só dentro da cerca)
- `cobra/projection.py`: grid -> tela, com a perspectiva falsa
- `cobra/manifest.py`: leitura do `manifest.json` dos sprites
- `cobra/assets.py`: carregamento dos sprites
- `cobra/render.py`: desenho (`Renderer`): cenário, cobra e a interface da partida no estilo chapado (placar,
  pausa, ranque, nome do recorde, resumo e tabela), com os escudos de `assets/ui/escudos`
- `cobra/intro.py`: abertura (a câmera começa longe e se aproxima do tabuleiro)
- `cobra/robot.py`: o robô que joga sozinho (tecla B, `main_robo.py` e `tools/robo.py`). Segue um ciclo fixo
  que passa por todas as casas, cortando caminho até o item mais perto enquanto é seguro: nunca se tranca e enche
  a arena inteira (nas arenas ímpares o canto (0, 0) fica fora do ciclo e é pego com um desvio)
- `cobra/live.py`: conexão com a live do TikTok (thread), conversão dos presentes da live em presentes do jogo
- `cobra/records.py`: os 5 melhores de cada arena em cada elo (o elo da arena no começo da partida), salvos em JSON
  (no Linux, `~/.local/share/cobra-presentes/recordes.json`). Recordes de antes da separação por elo vão para o Ferro
- `cobra/result.py`: o que o quadro de fim de jogo mostra (ranque, digitar o nome do recorde, resumo, tabela)
- `cobra/skins.py`: skins liberadas pelo elo (`SKIN_ELO` no config: ferro, bronze, prata, ouro). Ao chegar na
  liga de uma skin em qualquer arena, ela é liberada e equipada; as bloqueadas aparecem com cadeado no menu
- `cobra/rank.py`: ranque (elo) por arena: ligas, divisões, PDL, metas; salvo em `ranque.json` na pasta de dados
- `cobra/profile.py`: perfil do jogador (partidas, vitórias, presentes, tempo, recorde e maior elo por arena; nível por XP)
- `cobra/app.py`: janela, teclado, mouse e laço principal (modos: menu, abertura, jogo)
- `cobra/menu.py`: capa e perfil (lobby) da interface chapada (`assets/ui`), desenhados em
  1280x720 e escalados para a janela com faixas pretas. Caminhos no dicionário `ASSETS` e posições em
  constantes no topo do arquivo. O perfil tem um card por arena com o elo e o JOGAR dela; o lápis da foto
  abre as skins; os ícones do topo abrem configurações, recordes e voltar. Em Configurações, **RESETAR CONTA**
  (com confirmação) apaga tudo o que foi jogado: elo e PDL das arenas, nível, XP, estatísticas e recordes de
  pontos (as skins de elo voltam a ficar bloqueadas). O ranque de presenteadores, o nome e as configurações
  ficam (`cobra/account.py`)
- `cobra/widgets.py`: `Botao` (normal/hover/pressionado, clique ao soltar, tecla de atalho), cache de imagens
  e fontes (Poppins, em `assets/fonts`), `rounded_rect` (cantos suaves), `card`, `bar`,
  `flat_button` e a paleta de cores, usados pelo menu e pela partida
- `cobra/i18n.py`: textos em português e inglês (`t('chave')`); para um texto novo, acrescente a chave nos dois idiomas
- `cobra/settings.py`, `cobra/storage.py`: configurações do jogador (idioma) e gravação dos arquivos na pasta de dados
- `tests/`: testes da lógica e da projeção

Fluxo de cada frame: `app` lê o teclado, depois `GameState.update(dt)` e por fim `Renderer.draw(state)`.

### Constantes que dá para ajustar (`cobra/config.py`)
- `PERSPECTIVA`: 0 desliga; 0.15 deixa a linha do fundo com 85% do tamanho da linha da frente
- `ARENAS`: tamanhos que o jogador escolhe depois de clicar em Jogar (11, 15, 18); a câmera afasta (zoom) para a arena caber
- `CERCA_NA_BORDA`: cerca encostada no tabuleiro (True) ou no centro das células de fora (False)
- `DENSIDADE_PROPS`: fração das células de fora da cerca que ganha decoração (0.2)
- `ESCURECER_FORA`: quanto o chão de fora da cerca fica mais escuro (0.12; 0 = igual ao de dentro)
- `FOLGA_CERCA`: anéis de células sem decoração em volta da cerca (1)
- `SPRITES`: pasta dos sprites que o jogo usa (`assets/sprites`)
- `WIN_W`, `WIN_H`: tamanho inicial da janela (encolhe para caber no monitor). O jogo desenha no tamanho da janela
- `MIN_W`, `MIN_H`: abaixo disso o jogo desenha maior e escala para a janela (para o quadro de fim de jogo caber)
- `SCALE_STEP`, `BOARD_SLICE`: qualidade e cache da perspectiva
- `INTRO_SEGUNDOS`: duração da abertura ao abrir o jogo (2.8; 0 desliga). Qualquer tecla pula
- `INTRO_ZOOM`: de onde a câmera parte (0.4 = começa vendo uma área 2,5x maior que a tela)
- Comida da arena: sempre uma maçã. `MACAS`, `MACA_PESO_ANTERIOR`: uma maçã por elo (Ferro 1, Bronze 5, Prata 10
  ... Mestre 35, em `PONTOS`), sorteada entre a do elo da arena e as dos elos anteriores, cada elo para trás com
  metade do peso (no Mestre: 50% Mestre, 25% Diamante, 12,5% Esmeralda...). A cobra só volta ao clássico depois
  de comer `MACAS_PARA_VOLTAR` (50) maçãs seguidas, de qualquer elo; comer um presente zera a contagem (o placar
  mostra quantas faltam). Queimada pela bomba, a cobra só volta ao normal no primeiro presente que comer ou na
  `MACAS_PARA_DESQUEIMAR`ª (10ª) maçã, e as maçãs não dão pontos enquanto ela está queimada. No caracol e no
  queimado (`TEMAS_LENTOS`) a cobra fica um pouco mais rápida a cada maçã e volta à velocidade normal na
  `MACAS_PARA_ACELERAR`ª (10ª). Fora isso, a maçã vale o valor dela
  x o tamanho da cobra ao comer (já com o segmento novo). `TAMANHO_INICIAL`: 3. Sprites: `comidas/maca_<elo>.png`
  (`python build.py --partes macas`)
- Presentes (rosa, rosquinha, esquilo, caracol e mãos em coração): aparecem como a bomba (`PRESENTE_INTERVALO`, `PRESENTE_DURACAO`,
  `PRESENTE_PISCA`), somem se a cobra não pegar a tempo, fazem crescer e trocam o tema. Valem (maçã mais cara
  do elo + valor do presente) x tamanho da cobra; o valor (10, rosquinha 30, mãos em coração 50, caixa = moedas
  enviadas) é também quantas maçãs eles espalham ao estourar
- Maçãs do jogo na arena ao mesmo tempo (`MACAS_AUTOMATICAS`): 5 na 11x11, 7 na 15x15 e 10 na 18x18. A partida já
  começa assim e, quando a cobra come uma, outra aparece na hora
- Ao comer um presente, ele estoura e espalha maçãs (sorteadas pelo elo) em casas livres aleatórias: tantas
  quanto o valor do presente (rosa 10, rosquinha 30, coração 50, caixa = moedas), sem limite. Elas voam
  do presente até a casa, valem como maçãs comuns (fazem crescer) e não somem. A explosão da bomba apaga só as
  maçãs em volta dela, a até `BOMBA_RAIO` (1) casa em toda direção, diagonais incluídas (a maçã principal reaparece
  em outro lugar; presentes e bombas da caixa ficam)
- Caixa de presente (presente da live que não existe no jogo; no modo offline aparece com `CAIXA_CHANCE_OFFLINE`,
  20%): ao ser comida abre e espalha maçãs e bombas (`CAIXA_FRACAO_BOMBAS`, 20%), tantas quanto as moedas
  enviadas (offline: `CAIXA_ITENS_OFFLINE`, 10). As bombas da caixa ficam no mapa até a cobra pegar, como as maçãs
  Comer a caixa transforma a cobra (e o cenário) no tema dela, `caixa` (`CAIXA_TEMA`): cobra de caixinhas de
  presente embrulhadas (papel roxo e verde-água com bolinhas, fita dourada) com um laço na cabeça, chão de festa
  com confete, pilha de presentes e balões. Cada skin de presente só aparece com o presente dela; as 50 maçãs
  seguidas (ou uma bomba) voltam ao normal. Modelos em `tools/tema_caixa.py`
- Duende que joga os presentes: fica do lado de fora da cerca, no meio da lateral esquerda. Cada presente surge
  na mão dele (`PRESENTE_SURGE`), ele puxa o braço (`PRESENTE_PREPARA`) e arremessa; o presente voa em arco
  (`PRESENTE_VOO`) e só dá para pegar depois de cair. Sprites: `personagem/<pose>.png` (parado, segura, prepara,
  joga; o manifest traz a âncora e onde fica a mão em cada pose): `python build.py --partes personagem`
- Duende do mal: do outro lado (no meio da lateral direita) joga as bombas do mesmo jeito (surge na mão com uma
  fumacinha, arremessa, e a bomba só explode se a cobra pegar depois de cair). Sprites: `personagem/mal_<pose>.png`
  (`personagem_mal` no manifest), gerados junto com o duende bom
- `POPUP_SEGUNDOS`: quanto tempo o "+10" fica subindo depois de comer
- `RECORDES_ARQUIVO`, `CONFIGURACOES_ARQUIVO`, `RANQUE_ARQUIVO`, `PERFIL_ARQUIVO`: onde salvar recordes, idioma, elo e perfil (None = pasta de dados)
- `ALIMENTO_PADRAO`: a maçã de ferro (a comum); maçãs dão pontos mas não contam como presente (nem no contador, nem no PDL)
- `RANQUE_LIGAS`: comidas que a meta pede (na 11x11) e PDL base de cada liga (Ferro 12/25 ... Mestre 67/10)
- `RANQUE_ARENA`: multiplicador das comidas da meta por arena (11: 1.0, 15: 1.6, 18: 2.1)
- meta em pontos (`rank.target`): valor médio de uma comida no elo x (k x 3 + k(k+1)/2) para k comidas. O valor
  médio mistura as maçãs do elo (pelos pesos) com os presentes (`RANQUE_PRESENTES_POR_COMIDA`: 13% / 16% / 18%
  do que se come, medido com o robô, `tools/robo.py`). Ferro: 340 / 860 / 1500 (11x11 / 15x15 / 18x18) ...
  Mestre: 81150 / 204050 / 350500
- Cálculo do PDL (`cobra/rank.py`):
  - vitória: base + % acima da meta ((pontos - meta) / meta x 100; meta 4950 e 12573 pontos = +154) + minutos x presentes
  - derrota: -(base + % que faltou para a meta ((meta - pontos) / meta x 100; meta 1400 e 1120 pontos = -20))
    + minutos x presentes; se o total der positivo, o jogador ganha esses PDL mesmo sem bater a meta
  - nos dois: -`RANQUE_PDL_POR_BOMBA` por bomba e `RANQUE_BONUS_RECORDE` (+10 no #1, +8, +6, +4, +2 no #5)
  - `RANQUE_TEMPO_X_PRESENTES`: peso do minutos x presentes (1.0)
  - com PDL > 0 a derrota para no 0; só cai de divisão quem perde estando no 0; ninguém cai de liga
- XP do nível do perfil (`rank.match_xp`): o mesmo cálculo, com os pontos inteiros no lugar dos pontos acima
  da meta: base + pontos / meta x 100 + minutos x presentes (- bombas + recorde); ganhando ou perdendo.
  `XP_PER_LEVEL` (500, em `cobra/profile.py`) é o XP de cada nível
- `RANQUE_DIVISOES`, `RANQUE_PDL_DIVISAO`: 4 divisões, 100 PDL por divisão
- Botões JOGAR sem texto (`jogar_*_vazio_*.png`, usados fora do português): `python tools/menu_buttons.py`
- `BOMBA_INTERVALO`, `BOMBA_DURACAO`, `BOMBA_PISCA`, `BOMBA_PENALIDADE`: de quanto em quanto tempo a bomba aparece,
  quanto tempo fica, quando começa a piscar e quantos pontos tira. A bomba também tira 1 de tamanho da cobra
  (nunca abaixo de `BOMBA_TAMANHO_MINIMO`, 2). Pegar a bomba troca para o tema `queimado`
  (cobra e cenário queimados, velocidade do caracol) até a cobra comer um presente ou 10 maçãs (sem pontos
  pelas maçãs enquanto queimada; a velocidade volta aos poucos, a cada maçã)

## Sprites
Gere com `cd tools && python build.py --camera 34` (grava em `assets/sprites/`, ~15 min com 12 núcleos).
Para refazer só uma parte: `--partes sprites` (sprites do jogo, ~6 min) ou `--partes ui` (painéis da interface, ~9 min).
Escudos 3D antigos: `--partes escudos` (`assets/sprites/ranque/`; o jogo hoje usa os chapados de `assets/ui/escudos`).
Só alguns painéis: `--partes ui --paineis placar_aberto` (painéis: `placar`, `placar_aberto` — o placar estendido
com quanto vale cada presente — e `fim`).
Câmeras em `tools/sdf.py` (`CAMERAS`): `34` (visão 3/4, tile 96x68), `iso` (isométrica antiga, 96x48), `giro20`.
- `assets/sprites/<tema>/`: temas `classico`, `rosa`, `rosquinha`, `esquilo` (floresta de outono), `caracol`,
  `coracao` (mãos em coração: holográfico), `caixa` (caixa de presente da live) e `queimado` (depois da bomba)
  - `cabeca_{E,S,W,N}.png` e `cauda_{E,S,W,N}.png` (direção em que a cobra anda)
  - `corpo_0.png` e `corpo_1.png` (alterne entre eles para dar variedade)
  - `tile_0.png` e `tile_1.png` (para montar o xadrez do chão)
  - `prop_0.png` e `prop_1.png` (decoração do cenário)
  - `cerca_{reta_x,reta_y,canto_ES,canto_WS,canto_EN,canto_WN,poste}.png` (modelos em `tools/fences.py`)
  - skins da cobra (tema padrão) em `assets/sprites/skins/<skin>/` (`cabeca_*`, `cauda_*`, `corpo_*`); hoje: `ferro`, `bronze`, `prata`, `ouro`, `platina`, `esmeralda`, `diamante` e `mestre` (esmeralda e mestre têm também `corpo_<v>_<dir>`, com barbatanas viradas para a direção).
    Para uma skin de metal nova: cores em `PAL` e `METAL_SKINS` e o nome em `SKINS` (`tools/models.py`), o nome
    traduzido em `cobra/i18n.py` (`skin.<nome>`), a liga que a libera em `SKIN_ELO` (`cobra/config.py`) e
    `python build.py --partes skins avatares`
  - retratos das skins em alta resolução em `assets/sprites/avatares/<skin>.png` (`classico` = a clássica), usados no
    perfil, na tela de skins e na pausa: `python build.py --partes avatares`
  - `ui_placar.png`, `ui_placar_aberto.png` e `ui_fim.png`: painéis 3D antigos do placar e do fim de jogo (modelos em
    `tools/ui.py`). Não são mais usados: a interface da partida é desenhada no estilo chapado
- `assets/sprites/comidas/`: rosa, rosquinha, esquilo, caracol, coracao e maca (cada uma troca para o tema de mesmo nome; a maçã volta para o `classico`)
  e bomba (não é comida: o manifest a descreve em `bomba`, com o tema que ela ativa)
- `assets/sprites/sombra.png`: sombra suave. Desenhe antes dos objetos.
- `assets/sprites/manifest.json`: projeção, tamanhos, âncoras, peças de cerca, direções e cor de fundo de cada tema

## Como posicionar
Visão 3/4: grid alinhado à tela, câmera inclinada 45° para a frente. Face de cima do tile: 96x68.
```
proj = manifest['projecao']                                  # gx = [96, 0], gy = [0, 68]
tela  = origem + gx * proj['gx'] + gy * proj['gy']           # centro do tile, no chão
tile:   blit em tela - manifest['tile']['ancora']
objeto: blit em tela - manifest['objeto']['ancora']          # cobra, comida, props, cercas, sombra
```
Ordem: tiles, depois sombras, depois objetos por `gy` (e `gx` no empate).
Com perspectiva, cada ponto é escalado por `s(gy) = 1 - PERSPECTIVA * (1 - gy / (N - 1))` em direção ao centro da tela.

Direções: E = +gx (direita), S = +gy (baixo), W = -gx (esquerda), N = -gy (cima).
