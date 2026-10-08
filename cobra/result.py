"""O que o quadro de fim de jogo está mostrando. Não depende do pygame.

Fases:
  'ranque'  elo da arena: meta, PDL ganhos ou perdidos, barra de progresso (Enter continua)
  'top'     partida da live: pódio de quem mais mandou presentes (Enter continua)
  'nome'    a pontuação entrou nos recordes: o jogador digita o nome (Enter salva)
  'resumo'  pontos, presentes e tempo; se entrou nos recordes, oferece ver a tabela
  'tabela'  os 10 melhores da arena jogada, com a partida que acabou destacada
"""
from . import rank, records


class Result:
    def __init__(self, state, path, rank_outcome=None, live_name=None):
        """Os recordes são os da arena no elo em que a partida começou (rank_outcome.before). Partida de treino
        (state.practice: o robô jogou) vai direto para o resumo, sem ranque nem recordes."""
        self.path = path
        self.score, self.eaten, self.play_time = state.score, state.eaten, state.play_time
        self.won = state.won
        self.arena = state.n
        self.league = rank.tier_id(rank_outcome.before) if rank_outcome is not None else records.FIRST_LEAGUE
        self.data = records.load(path)
        self.records = records.table(self.data, self.arena, self.league)     # só a tabela desta arena e elo
        self.live_name = live_name          # modo live: o recorde sai com o @ (e não troca o nome do offline)
        self.name = live_name or self.data['ultimo_nome']
        self.rank = None                    # posição na tabela (0 = 1º), depois de salvar
        self.save_error = None              # mensagem, se não deu para gravar o arquivo
        self.rank_outcome = rank_outcome    # cobra.rank.Outcome desta partida (None = sem ranque)
        self.xp_info = None                 # (XP ganho, nível antes, (nível, XP no nível, XP por nível) depois)
        self.new_skin = None                # skin liberada (e equipada) nesta partida
        self.supporters = []                # modo live: quem mais mandou presentes (live.Tribute), no pódio
        self.started = state.time           # para animar a tela do ranque
        self.practice = bool(getattr(state, 'practice', False))
        self.live_top = bool(getattr(state, 'live', False))     # partida da live: tem o pódio depois do ranque
        if rank_outcome is not None:
            self.phase = 'ranque'
        else:
            self.phase = 'top' if self.live_top else self._after_rank()

    def _after_rank(self):
        if self.practice:
            return 'resumo'
        return 'nome' if records.qualifies(self.records, self.score) else 'resumo'

    def continue_rank(self):
        """Continuar: do ranque para o pódio da live (se for partida da live) e de lá para o recorde (ou o resumo)."""
        if self.phase == 'ranque' and self.live_top:
            self.phase = 'top'
        elif self.phase in ('ranque', 'top'):
            self.phase = self._after_rank()

    @property
    def is_best(self):
        """A partida é (ou vai ser, ao salvar o nome) o 1º lugar."""
        if self.rank is not None:
            return self.rank == 0
        return self.phase == 'nome' and (not self.records or self.score > self.records[0]['pontos'])

    @property
    def can_show_table(self):
        return self.rank is not None

    def type_char(self, ch):
        if self.phase == 'nome' and ch.isprintable() and len(self.name) < records.MAX_NAME:
            self.name += ch

    def backspace(self):
        if self.phase == 'nome':
            self.name = self.name[:-1]

    def confirm(self):
        """Enter na fase do nome: salva o recorde (e o nome, para a próxima vez)."""
        if self.phase in ('ranque', 'top'):
            self.continue_rank()
        if self.phase != 'nome':
            return
        self.records, self.rank = records.add(self.records, self.name, self.score, self.play_time, self.arena,
                                              self.league)
        self.name = self.records[self.rank]['nome']
        self.data['tabelas'][self.arena, self.league] = self.records
        if not self.live_name:
            self.data['ultimo_nome'] = self.name
        try:
            records.save(self.path, self.data)
        except OSError as e:                # sem permissão, disco cheio...: o recorde fica só nesta sessão
            self.save_error = str(e)
        self.phase = 'resumo'

    def toggle_table(self):
        if self.can_show_table:
            self.phase = 'tabela' if self.phase == 'resumo' else 'resumo'
