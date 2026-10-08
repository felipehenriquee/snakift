"""Sons do jogo: efeitos e trilha da pasta assets/audio (config.AUDIO_DIR).

Usa o pygame.mixer. Sem placa de som (ou sem os arquivos), tudo vira silêncio, sem erro.
Os eventos da partida (logic.GameState.events) viram efeitos em play_events(); a trilha toca em loop.
"""
import os

import pygame

from . import config, settings
from .logic import is_apple

SFX = ('comer_maca', 'comer_rosa', 'comer_rosquinha', 'comer_esquilo', 'comer_caracol', 'comer_coracao', 'transformar',
       'contagem_321_vai', 'game_over', 'subir_nivel', 'subir_elo', 'explosao')
EAT = {'rosa': 'comer_rosa', 'rosquinha': 'comer_rosquinha', 'esquilo': 'comer_esquilo', 'caracol': 'comer_caracol',
       'coracao': 'comer_coracao', 'caixa': 'comer_coracao'}     # a caixa de presente da live usa o do coração


class Audio:
    def __init__(self, prefs):
        """prefs: as configurações (volume geral, da música e dos efeitos, de 0 a settings.VOLUME_MAX)."""
        self.prefs = prefs
        self.sfx_volume = None              # volume aplicado nos efeitos (muda quando o jogador mexe)
        self.sounds = {}
        self.ok = False
        self.music_on = False
        self.music_failed = False           # a trilha não abriu: não tenta de novo a cada quadro
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(44100, -16, 2, 512)
            self.ok = True
        except pygame.error:                # sem placa de som: jogo em silêncio
            return
        folder = os.path.join(config.AUDIO_DIR, 'sfx')
        for name in SFX:
            path = os.path.join(folder, name + '.wav')
            if os.path.exists(path):
                try:
                    self.sounds[name] = pygame.mixer.Sound(path)
                except pygame.error:
                    pass
        pygame.mixer.set_num_channels(16)

    def _level(self, key):
        """Volume de 0 a 1 de uma parte: o geral vezes o dela."""
        k = settings.VOLUME_MAX
        return self.prefs.get('volume', k) / k * self.prefs.get(key, k) / k

    def play(self, name):
        vol = config.VOLUME_EFEITOS * self._level('volume_efeitos')
        if not (self.ok and vol > 0 and name in self.sounds):
            return
        if vol != self.sfx_volume:          # o jogador mudou o volume: aplica em todos os efeitos
            for sound in self.sounds.values():
                sound.set_volume(vol)
            self.sfx_volume = vol
        self.sounds[name].play()

    def play_events(self, events):
        """Efeitos dos eventos da partida. Comer um presente já tem o seu som (que inclui a troca de tema);
        a transformação toca sozinha quando o tema muda sem presente (a cobra volta ao normal). A bomba explode."""
        ate_gift = any(e[0] == 'comeu' and e[1] in EAT for e in events) or any(e[0] == 'bomba' for e in events)
        for ev in events:
            if ev[0] == 'comeu' and ev[1] in EAT:
                self.play(EAT[ev[1]])
            elif ev[0] == 'comeu' and is_apple(ev[1]):     # mordida na maçã (de qualquer elo)
                self.play('comer_maca')
            elif ev[0] == 'tema' and not ate_gift:
                self.play('transformar')
            elif ev[0] == 'bomba':                      # a bomba explode (e a troca para o queimado fica sem som)
                self.play('explosao')
            elif ev[0] == 'morreu':
                self.play('game_over')

    def update_music(self):
        """Liga ou desliga a trilha (em loop) e acompanha o volume da configuração."""
        if not self.ok or self.music_failed:
            return
        vol = config.VOLUME_MUSICA * self._level('volume_musica')
        want = vol > 0
        if want and self.music_on:
            pygame.mixer.music.set_volume(vol)
        elif want and not self.music_on:
            path = os.path.join(config.AUDIO_DIR, 'musica', 'trilha_loop.ogg')
            try:
                pygame.mixer.music.load(path)
                pygame.mixer.music.set_volume(vol)
                pygame.mixer.music.play(-1, fade_ms=800)
                self.music_on = True
            except pygame.error:
                self.music_failed = True
        elif not want and self.music_on:
            pygame.mixer.music.fadeout(400)
            self.music_on = False
