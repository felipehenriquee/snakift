"""Efeitos sonoros e trilha do Snakift, sintetizados do zero (numpy/scipy).

python som.py           -> gera assets/audio/sfx/*.wav e assets/audio/musica/trilha_loop.ogg (+ .wav)
Tudo é original e gerado por código: pode usar à vontade, inclusive comercialmente.
"""
import os, subprocess
import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', '..', 'assets', 'audio')
rng = np.random.default_rng(7)


# ================================================================ básicos
def t_(dur):
    return np.arange(int(dur * SR)) / SR


def note_hz(n):
    """n = nome ('C5', 'F#4') ou número MIDI."""
    if isinstance(n, str):
        names = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
        k = names[n[0]] + (1 if '#' in n else -1 if 'b' in n[1:] else 0)
        o = int(n[-1])
        n = 12 * (o + 1) + k
    return 440.0 * 2 ** ((n - 69) / 12)


def env(n, a=0.005, d=0.1, s=0.0, r=0.05, sus_time=None):
    """ADSR com n amostras."""
    a_, d_, r_ = int(a * SR), int(d * SR), int(r * SR)
    hold = max(0, n - a_ - d_ - r_) if sus_time is None else int(sus_time * SR)
    e = np.concatenate([np.linspace(0, 1, max(a_, 1)), 1 - (1 - s) * (1 - np.exp(-5 * np.linspace(0, 1, max(d_, 1)))),
                        np.full(hold, s), s * np.exp(-5 * np.linspace(0, 1, max(r_, 1)))])
    if len(e) < n:
        e = np.concatenate([e, np.zeros(n - len(e))])
    return e[:n]


def expdec(n, tau):
    return np.exp(-np.arange(n) / (tau * SR))


def osc(freq, dur, kind='sine', phase=0.0):
    """freq pode ser número ou array (varredura)."""
    n = int(dur * SR)
    f = np.broadcast_to(np.asarray(freq, float), (n,)) if np.ndim(freq) == 0 else np.asarray(freq, float)[:n]
    ph = 2 * np.pi * np.cumsum(f) / SR + phase
    if kind == 'sine':
        return np.sin(ph)
    if kind == 'tri':
        return 2 / np.pi * np.arcsin(np.sin(ph))
    if kind == 'square':      # quadrada suave (aditiva até a 9ª harmônica)
        return sum(np.sin(ph * k) / k for k in (1, 3, 5, 7, 9)) * 4 / np.pi * 0.8
    if kind == 'saw':
        return sum(np.sin(ph * k) / k * (-1) ** (k + 1) for k in range(1, 12)) * 0.6


def fm_bell(freq, dur, ratio=3.5, index=2.5, tau=0.5):
    n = int(dur * SR); t = np.arange(n) / SR
    mod_env = expdec(n, tau * 0.4)
    return np.sin(2 * np.pi * freq * t + index * mod_env * np.sin(2 * np.pi * freq * ratio * t)) * expdec(n, tau)


def noise(dur):
    return rng.uniform(-1, 1, int(dur * SR))


def lp(x, fc, order=2):
    b, a = signal.butter(order, min(fc, SR / 2 - 100) / (SR / 2), 'low')
    return signal.lfilter(b, a, x)


def hp(x, fc, order=2):
    b, a = signal.butter(order, fc / (SR / 2), 'high')
    return signal.lfilter(b, a, x)


def bp(x, lo, hi, order=2):
    b, a = signal.butter(order, [lo / (SR / 2), min(hi, SR / 2 - 100) / (SR / 2)], 'band')
    return signal.lfilter(b, a, x)


def sweep_bp(x, f0, f1, q=4.0):
    """Filtro passa-banda com frequência variando (para 'whoosh'), em blocos."""
    out = np.zeros_like(x); blk = 512
    zi = None
    for i in range(0, len(x), blk):
        f = f0 * (f1 / f0) ** (i / len(x))
        bw = f / q
        b, a = signal.butter(2, [max(30, f - bw) / (SR / 2), min(SR / 2 - 200, f + bw) / (SR / 2)], 'band')
        if zi is None or len(zi) != max(len(a), len(b)) - 1:
            zi = signal.lfilter_zi(b, a) * 0
        out[i:i + blk], zi = signal.lfilter(b, a, x[i:i + blk], zi=zi)
    return out


def reverb(x, size=1.2, wet=0.25, damp=6000, seed=1, pre=0.012):
    """Reverb por convolução com resposta ao impulso sintética (estéreo)."""
    g = np.random.default_rng(seed)
    n = int(size * SR)
    outs = []
    for ch in range(2):
        ir = g.normal(0, 1, n) * np.exp(-np.arange(n) / (size * SR / 6.5))
        ir = lp(ir, damp)
        ir = np.concatenate([np.zeros(int(pre * SR)), ir]); ir /= np.sqrt((ir ** 2).sum())
        outs.append(signal.fftconvolve(x if x.ndim == 1 else x[:, ch], ir))
    L = max(len(o) for o in outs)
    wetsig = np.stack([np.pad(o, (0, L - len(o))) for o in outs], 1)
    dry = x if x.ndim == 2 else np.stack([x, x], 1)
    dry = np.pad(dry, ((0, L - len(dry)), (0, 0)))
    return dry * (1 - wet * 0.5) + wetsig * wet


def place(buf, x, at):
    i = int(at * SR)
    x = np.array(x, float)
    nf = min(len(x) // 4, int(0.012 * SR))      # rampa no fim: evita estalo quando o som é cortado
    if nf > 1:
        ramp = np.linspace(1, 0, nf)
        x[-nf:] *= ramp[:, None] if x.ndim == 2 else ramp
    if x.ndim == 1 and buf.ndim == 2:
        x = np.stack([x, x], 1)
    end = min(len(buf), i + len(x))
    buf[i:end] += x[:end - i]


def pan(x, p):
    """p em [-1, 1]."""
    l, r = np.cos((p + 1) * np.pi / 4), np.sin((p + 1) * np.pi / 4)
    return np.stack([x * l, x * r], 1)


def finish(x, peak=0.89, fade=0.01):
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    x = x - x.mean(0)
    # corta silêncio do fim
    a = np.abs(x).max(1)
    last = np.nonzero(a > a.max() * 0.004)[0]
    if len(last):
        x = x[:last[-1] + 1]
    nf = int(fade * SR)
    x[-nf:] *= np.linspace(1, 0, nf)[:, None]
    x[:64] *= np.linspace(0, 1, 64)[:, None]
    return x / (np.abs(x).max() + 1e-9) * peak


def save_wav(name, x):
    path = os.path.join(OUT, 'sfx', name + '.wav')
    wavfile.write(path, SR, (np.clip(x, -1, 1) * 32767).astype(np.int16))
    return path


def buf(dur):
    return np.zeros((int(dur * SR), 2))


# ================================================================ EFEITOS
def comer_rosa():
    """Plim suave de sininho + farfalhar de pétalas."""
    b = buf(1.4)
    for i, (nn, p) in enumerate([('E6', -0.3), ('B6', 0.3), ('E7', 0.0)]):
        place(b, pan(fm_bell(note_hz(nn), 1.2, ratio=2.0, index=1.2, tau=0.35) * [0.5, 0.4, 0.22][i], p), 0.04 * i)
    pet = bp(noise(0.25), 3000, 9000) * env(int(0.25 * SR), 0.01, 0.2, 0, 0.03) * 0.18
    place(b, pan(pet, 0.2), 0.0)
    return finish(reverb(b, 1.0, 0.3, seed=2))


def comer_maca():
    """(Não é mais gerado: o comer_maca.wav agora vem do carrot_crunch.mp3 do jogador.)
    Mordida curta na maçã: dois crocs (casca), um 'tump' grave e um chiadinho de suco. Bem curto, porque
    a maçã é comida o tempo todo."""
    b = buf(0.45)
    for i, at in enumerate((0.0, 0.045)):
        n = int(0.06 * SR)
        cr = bp(noise(0.06), 1800, 8500) * expdec(n, 0.009) * (1.0 - 0.35 * i)
        cr += bp(noise(0.06), 250, 700) * expdec(n, 0.016) * 0.55
        place(b, pan(cr, -0.08 + 0.16 * i), at)
    f = np.linspace(210, 120, int(0.07 * SR))
    place(b, osc(f, 0.07) * env(len(f), 0.002, 0.06, 0, 0.01) * 0.35, 0.005)
    juice = bp(noise(0.16), 2500, 6000) * env(int(0.16 * SR), 0.02, 0.12, 0, 0.03) * 0.12
    place(b, pan(juice, 0.15), 0.06)
    return finish(reverb(b, 0.35, 0.08, seed=12), peak=0.7)


def comer_rosquinha():
    """Mordida crocante (3 crocs) + 'pop' fofinho + granulado tilintando."""
    b = buf(1.0)
    for i, at in enumerate((0.0, 0.055, 0.12)):
        n = int(0.07 * SR)
        cr = bp(noise(0.07), 1200, 7000) * expdec(n, 0.012) * (0.9 - 0.2 * i)
        cr += bp(noise(0.07), 300, 900) * expdec(n, 0.02) * 0.5
        place(b, pan(cr, -0.1 + 0.1 * i), at)
    f = np.linspace(620, 240, int(0.16 * SR))
    place(b, osc(f, 0.16) * env(len(f), 0.002, 0.13, 0, 0.02) * 0.6, 0.02)
    for i in range(6):
        fr = note_hz(rng.choice([96, 98, 100, 103, 105]))
        place(b, pan(fm_bell(fr, 0.25, 4.0, 0.8, 0.06) * 0.18, rng.uniform(-0.7, 0.7)), 0.16 + i * 0.035)
    return finish(reverb(b, 0.6, 0.15, seed=3))


def comer_esquilo():
    """Quebra da noz + dois 'chirps' agudos de esquilo."""
    b = buf(0.9)
    n = int(0.05 * SR)
    crack = bp(noise(0.05), 1500, 8000) * expdec(n, 0.006) + osc(950, 0.05, 'tri') * expdec(n, 0.012) * 0.6
    place(b, crack * 0.9, 0.0)
    place(b, osc(620, 0.08, 'tri') * expdec(int(0.08 * SR), 0.02) * 0.4, 0.03)        # 'toc' de madeira
    for i, at in enumerate((0.13, 0.27)):
        d = 0.09
        tt = t_(d)
        f = 2600 + 1400 * np.sin(np.pi * tt / d) + 300 * np.sin(2 * np.pi * 38 * tt)   # sobe e desce com vibrato
        ch = osc(f, d) * env(len(tt), 0.006, 0.06, 0.3, 0.02) * 0.45
        ch += osc(f * 2, d) * env(len(tt), 0.006, 0.05, 0.1, 0.02) * 0.1
        place(b, pan(ch, 0.25 * (-1) ** i), at)
    return finish(reverb(b, 0.5, 0.12, seed=4))


def comer_caracol():
    """Gulp lento e borbulhante (câmera lenta)."""
    b = buf(1.7)
    f = 220 * np.exp(-t_(0.5) * 1.6) + 90
    gulp = osc(f, 0.5, 'sine') * env(len(f), 0.03, 0.45, 0, 0.05)
    place(b, lp(gulp, 900) * 0.6, 0.0)
    for i in range(7):
        d = 0.12
        fr = rng.uniform(300, 700)
        bub = osc(fr * (1 + 2.5 * t_(d) / d) ** 1.2, d) * env(int(d * SR), 0.004, 0.09, 0, 0.02)
        place(b, pan(bub * 0.35, rng.uniform(-0.6, 0.6)), 0.2 + i * rng.uniform(0.12, 0.2))
    # 'whoosh' descendo, efeito câmera lenta
    w = sweep_bp(noise(0.9), 2500, 300, 3) * env(int(0.9 * SR), 0.2, 0.6, 0, 0.1) * 0.35
    place(b, pan(w, -0.2), 0.05)
    return finish(reverb(b, 1.4, 0.3, seed=5))


def comer_coracao():
    """Presente caro: arpejo de cristal + cintilância + acorde doce que abre."""
    b = buf(3.2)
    arp = ['C6', 'E6', 'G6', 'B6', 'D7', 'E7', 'G7']
    for i, nn in enumerate(arp):
        x = fm_bell(note_hz(nn), 1.8, ratio=3.0, index=1.6, tau=0.55) * (0.32 - 0.02 * i)
        place(b, pan(x, -0.6 + 1.2 * i / (len(arp) - 1)), 0.055 * i)
    # acorde de 'pad' (Cmaj9) crescendo e sumindo
    pad = np.zeros(int(2.6 * SR))
    for nn in ('C4', 'G4', 'B4', 'D5', 'E5'):
        for det in (-0.004, 0.004):
            pad += osc(note_hz(nn) * (1 + det), 2.6, 'saw') * 0.05
    pad = lp(pad, 2500) * env(len(pad), 0.5, 1.2, 0.4, 0.9)
    place(b, pad, 0.15)
    # cintilância: muitos pontinhos agudos
    for i in range(40):
        fr = rng.uniform(4000, 9000)
        sp = osc(fr, 0.08) * expdec(int(0.08 * SR), 0.015) * rng.uniform(0.03, 0.08)
        place(b, pan(sp, rng.uniform(-1, 1)), 0.1 + rng.uniform(0, 1.8))
    return finish(reverb(b, 2.4, 0.42, damp=9000, seed=6))


def transformar():
    """Troca de tema: whoosh subindo + escala mágica + brilho."""
    b = buf(1.8)
    w = sweep_bp(noise(0.9), 250, 6000, 2.5) * env(int(0.9 * SR), 0.5, 0.35, 0, 0.05)
    place(b, pan(w * 0.55, -0.3), 0.0)
    scale = ['C5', 'D5', 'E5', 'G5', 'A5', 'C6', 'E6', 'G6', 'C7']
    for i, nn in enumerate(scale):
        x = fm_bell(note_hz(nn), 0.6, 2.0, 1.0, 0.18) * 0.22
        place(b, pan(x, -0.8 + 1.6 * i / 8), 0.35 + 0.045 * i)
    place(b, fm_bell(note_hz('C7'), 1.2, 3.0, 2.0, 0.5) * 0.3, 0.78)
    return finish(reverb(b, 1.6, 0.35, seed=7))


def explosao():
    """Bomba: BOOM grave que despenca + estouro abafado + estalinhos de destroços + 'uóóón' descendo (deu ruim)."""
    b = buf(2.0)
    n = int(1.2 * SR)
    f = 38 + 120 * np.exp(-t_(1.2) * 7)                                    # tranco grave caindo de ~160 a 40 Hz
    boom = osc(f, 1.2) * expdec(n, 0.35) * 0.9
    boom += osc(f * 0.5, 1.2) * expdec(n, 0.5) * 0.5
    place(b, boom, 0.0)
    m = int(0.9 * SR)
    blast = lp(noise(0.9), 900) * env(m, 0.003, 0.25, 0.25, 0.4) * 1.1     # estouro abafado
    blast += bp(noise(0.9), 900, 3500) * expdec(m, 0.06) * 0.5              # o "tch" do começo
    place(b, pan(blast, -0.05), 0.0)
    for i in range(18):                                                      # destroços caindo
        at = 0.08 + rng.uniform(0, 0.7) ** 1.6
        k = int(0.03 * SR)
        cr = bp(noise(0.03), 1500, 6000) * expdec(k, 0.006) * rng.uniform(0.08, 0.22)
        place(b, pan(cr, rng.uniform(-0.8, 0.8)), at)
    d = 0.75                                                                  # 'uóóón' triste, descendo
    tt = t_(d)
    fw = note_hz('D4') * (1 - 0.35 * tt / d) * (1 + 0.015 * np.sin(2 * np.pi * 5.5 * tt))
    wah = lp(osc(fw, d, 'square') * 0.5 + osc(fw, d, 'tri') * 0.5, 1400) * env(len(tt), 0.04, 0.2, 0.6, 0.3) * 0.22
    place(b, pan(wah, 0.1), 0.45)
    return finish(reverb(b, 1.4, 0.22, seed=13))


def bip(nn='A5', dur=0.22, vol=0.6):
    x = osc(note_hz(nn), dur, 'square') * env(int(dur * SR), 0.003, 0.08, 0.35, 0.06) * vol
    return lp(x, 5000)


def contagem():
    """3, 2, 1, VAI!"""
    b = buf(3.9)
    for i in range(3):
        place(b, bip('A5'), i * 0.8)
    go = np.zeros(int(0.9 * SR))
    for nn in ('A5', 'C#6', 'E6', 'A6'):
        go += osc(note_hz(nn), 0.9, 'square') * env(len(go), 0.004, 0.3, 0.35, 0.4) * 0.22
    place(b, lp(go, 6000), 2.4)
    return finish(reverb(b, 0.8, 0.2, seed=8))


def game_over():
    """'Uóóóm uóm' fofo descendo + baque macio."""
    b = buf(2.4)
    notes = [('G4', 0.32), ('F#4', 0.32), ('F4', 0.32), ('E4', 1.0)]
    at = 0
    for i, (nn, d) in enumerate(notes):
        f0 = note_hz(nn)
        tt = t_(d)
        bend = 1 - (0.06 * tt / d if i == 3 else 0)
        vib = 1 + (0.012 * np.sin(2 * np.pi * 6 * tt) * (tt / d) if i == 3 else 0)
        f = f0 * bend * vib
        x = osc(f, d, 'square') * 0.5 + osc(f, d, 'tri') * 0.5
        x = lp(x, 1800) * env(len(tt), 0.01, 0.1, 0.7, 0.12 if i < 3 else 0.6) * 0.5
        place(b, x, at)
        at += d + 0.02
    th = osc(110 * np.exp(-t_(0.4) * 4) + 45, 0.4) * expdec(int(0.4 * SR), 0.12) * 0.7
    place(b, th, at - 0.95)
    return finish(reverb(b, 1.2, 0.25, seed=9))


def subir_nivel():
    b = buf(1.3)
    for i, nn in enumerate(['C5', 'E5', 'G5', 'C6']):
        x = osc(note_hz(nn), 0.35, 'square') * env(int(0.35 * SR), 0.003, 0.12, 0.25, 0.15) * 0.3
        place(b, pan(lp(x, 6000), -0.4 + 0.27 * i), 0.07 * i)
    place(b, fm_bell(note_hz('C7'), 0.9, 3.0, 1.5, 0.3) * 0.28, 0.3)
    for i in range(10):
        place(b, pan(osc(rng.uniform(5000, 9000), 0.06) * expdec(int(0.06 * SR), 0.012) * 0.06, rng.uniform(-1, 1)), 0.3 + rng.uniform(0, 0.5))
    return finish(reverb(b, 1.0, 0.25, seed=10))


def brass(freq, dur):
    n = int(dur * SR)
    x = sum(osc(freq * (1 + d), dur, 'saw') for d in (-0.003, 0.0, 0.003)) / 3
    # brilho que abre no ataque e fecha depois = cara de metal (mistura de dois filtros, sem estalos)
    tt = np.arange(n) / SR
    k = (1 - np.exp(-tt / 0.05)) * np.exp(-tt / 0.6)
    out = lp(x, 1100, 1) * (1 - k) + lp(x, 5000, 1) * k
    return out * env(n, 0.03, 0.2, 0.7, 0.25)


def subir_elo():
    """Fanfarra: mais pomposa que o 'subir nível'."""
    b = buf(3.4)
    seq = [(['G4', 'B4', 'D5'], 0.0, 0.16), (['G4', 'B4', 'D5'], 0.18, 0.16), (['G4', 'B4', 'D5'], 0.36, 0.16),
           (['C5', 'E5', 'G5'], 0.56, 0.5), (['D5', 'F#5', 'A5'], 1.1, 0.3), (['G5', 'B5', 'D6', 'G4'], 1.42, 1.4)]
    for chord, at, d in seq:
        for j, nn in enumerate(chord):
            place(b, pan(brass(note_hz(nn), d + 0.1) * 0.22, -0.4 + 0.4 * j), at)
    # tímpano + prato
    for at in (0.56, 1.42):
        tim = osc(note_hz('G2') * (1 + 0.15 * np.exp(-t_(0.8) * 20)), 0.8) * expdec(int(0.8 * SR), 0.25) * 0.6
        place(b, tim, at)
    cym = hp(noise(2.0), 5000) * expdec(int(2.0 * SR), 0.6) * 0.18
    place(b, pan(cym, 0.3), 1.42)
    for i in range(16):
        place(b, pan(osc(rng.uniform(5000, 10000), 0.07) * expdec(int(0.07 * SR), 0.015) * 0.07, rng.uniform(-1, 1)), 1.45 + rng.uniform(0, 1.2))
    return finish(reverb(b, 1.8, 0.3, seed=11))


SFX = {
    'comer_rosa': comer_rosa, 'comer_rosquinha': comer_rosquinha, 'comer_esquilo': comer_esquilo,
    'comer_caracol': comer_caracol, 'comer_coracao': comer_coracao, 'transformar': transformar,
    'contagem_321_vai': contagem, 'explosao': explosao, 'game_over': game_over, 'subir_nivel': subir_nivel, 'subir_elo': subir_elo,
}


# ================================================================ TRILHA (loop)
BPM = 112
BEAT = 60 / BPM
BAR = BEAT * 4


def ep(freq, dur, vel=1.0):
    """Piano elétrico fofinho (FM suave)."""
    n = int(dur * SR); t = np.arange(n) / SR
    m = np.exp(-t / 0.25) * 1.2
    x = np.sin(2 * np.pi * freq * t + m * np.sin(2 * np.pi * freq * t)) * np.exp(-t / 0.9)
    x += 0.25 * np.sin(2 * np.pi * freq * 2 * t) * np.exp(-t / 0.3)
    return x * env(n, 0.004, 0.2, 1.0, 0.08) * vel


def marimba(freq, dur, vel=1.0):
    n = int(dur * SR); t = np.arange(n) / SR
    x = np.sin(2 * np.pi * freq * t) * np.exp(-t / 0.22) + 0.35 * np.sin(2 * np.pi * freq * 4 * t) * np.exp(-t / 0.05)
    x[:40] *= np.linspace(0, 1, 40)
    return x * vel


def pluck_bass(freq, dur, vel=1.0):
    n = int(dur * SR)
    x = osc(freq, dur, 'tri') * 0.8 + osc(freq * 2, dur, 'sine') * 0.15
    x = lp(x, 900) * env(n, 0.004, 0.18, 0.55, 0.06)
    return x * vel


def kick():
    d = 0.35
    f = 50 + 120 * np.exp(-t_(d) * 35)
    return osc(f, d) * expdec(int(d * SR), 0.12)


def snare():
    d = 0.22
    n = int(d * SR)
    return (bp(noise(d), 1200, 8000) * expdec(n, 0.05) * 0.6 + osc(190, d, 'tri') * expdec(n, 0.04) * 0.4)


def hat(open_=False):
    d = 0.25 if open_ else 0.05
    return hp(noise(d), 7000) * expdec(int(d * SR), 0.08 if open_ else 0.012)


def shaker():
    d = 0.08
    return bp(noise(d), 5000, 11000) * env(int(d * SR), 0.02, 0.05, 0, 0.01)


CHORDS = {   # (baixo, notas do acorde)
    'C': ('C3', ['E4', 'G4', 'C5']), 'Am': ('A2', ['E4', 'A4', 'C5']), 'F': ('F2', ['F4', 'A4', 'C5']),
    'G': ('G2', ['D4', 'G4', 'B4']), 'Em': ('E3', ['E4', 'G4', 'B4']), 'Dm': ('D3', ['D4', 'F4', 'A4']),
}
PROG = ['C', 'Am', 'F', 'G', 'C', 'Am', 'F', 'G', 'F', 'G', 'Em', 'Am', 'Dm', 'G', 'C', 'G']

# melodia: (compasso, tempo em batidas, nota, duração em batidas)
MELODY_A = [  # 4 compassos
    (0, 0, 'E5', 0.5), (0, 0.5, 'G5', 0.5), (0, 1, 'C6', 1), (0, 2.5, 'B5', 0.5), (0, 3, 'G5', 1),
    (1, 0, 'A5', 0.5), (1, 0.5, 'G5', 0.5), (1, 1, 'E5', 1), (1, 2.5, 'C5', 0.5), (1, 3, 'E5', 1),
    (2, 0, 'F5', 0.5), (2, 0.5, 'A5', 0.5), (2, 1, 'C6', 1), (2, 2.5, 'A5', 0.5), (2, 3, 'F5', 1),
    (3, 0, 'G5', 0.5), (3, 0.5, 'B5', 0.5), (3, 1, 'D6', 1.5), (3, 3, 'B5', 0.5), (3, 3.5, 'G5', 0.5),
]
MELODY_B = [
    (0, 0, 'E5', 0.5), (0, 0.5, 'G5', 0.5), (0, 1, 'C6', 1), (0, 2.5, 'D6', 0.5), (0, 3, 'E6', 1),
    (1, 0, 'C6', 0.5), (1, 0.5, 'A5', 0.5), (1, 1, 'E5', 1), (1, 2.5, 'G5', 0.5), (1, 3, 'A5', 1),
    (2, 0, 'A5', 0.5), (2, 0.5, 'C6', 0.5), (2, 1, 'F6', 1), (2, 2.5, 'E6', 0.5), (2, 3, 'C6', 1),
    (3, 0, 'D6', 1), (3, 1, 'B5', 0.5), (3, 1.5, 'G5', 0.5), (3, 2, 'D5', 2),
]
MELODY_C = [  # ponte
    (0, 0, 'A5', 1), (0, 1, 'C6', 0.5), (0, 1.5, 'A5', 0.5), (0, 2, 'F5', 2),
    (1, 0, 'G5', 1), (1, 1, 'B5', 0.5), (1, 1.5, 'D6', 0.5), (1, 2, 'B5', 2),
    (2, 0, 'G5', 0.5), (2, 0.5, 'B5', 0.5), (2, 1, 'E6', 1.5), (2, 3, 'D6', 1),
    (3, 0, 'C6', 0.5), (3, 0.5, 'E6', 0.5), (3, 1, 'A5', 2), (3, 3, 'C6', 0.5), (3, 3.5, 'B5', 0.5),
    (4, 0, 'A5', 1), (4, 1, 'F5', 0.5), (4, 1.5, 'A5', 0.5), (4, 2, 'D6', 2),
    (5, 0, 'B5', 1), (5, 1, 'D6', 1), (5, 2, 'G5', 2),
    (6, 0, 'C6', 0.5), (6, 0.5, 'E6', 0.5), (6, 1, 'G6', 1), (6, 2, 'E6', 0.5), (6, 2.5, 'C6', 0.5), (6, 3, 'G5', 1),
    (7, 0, 'D6', 0.5), (7, 0.5, 'B5', 0.5), (7, 1, 'G5', 1), (7, 2, 'B5', 0.5), (7, 2.5, 'C6', 0.5), (7, 3, 'D6', 1),
]


def musica():
    bars = len(PROG)
    total = bars * BAR
    tail = 3.0
    mix = {k: np.zeros((int((total + tail) * SR), 2)) for k in ('drums', 'bass', 'keys', 'lead', 'sparkle')}
    swing = 0.06 * BEAT

    def at(bar, beat):
        b = beat + (swing / BEAT if (beat * 2) % 2 == 1 else 0)
        return bar * BAR + b * BEAT

    for bi, ch in enumerate(PROG):
        bass, notes = CHORDS[ch]
        # bateria
        for beat in (0, 2):
            place(mix['drums'], kick() * 0.9, at(bi, beat))
        place(mix['drums'], kick() * 0.5, at(bi, 2.5 if bi % 2 else 3.5))
        for beat in (1, 3):
            place(mix['drums'], pan(snare() * 0.45, 0.05), at(bi, beat))
        for e in range(8):
            place(mix['drums'], pan(hat(open_=(e == 7 and bi % 4 == 3)) * (0.18 if e % 2 else 0.26), 0.35), at(bi, e / 2))
        for s16 in range(16):
            if s16 % 2:
                place(mix['drums'], pan(shaker() * 0.08, -0.4), at(bi, s16 / 4))
        # baixo saltitante
        bpat = [(0, 1.0, 1), (1.5, 0.5, 1), (2, 1.0, 1), (3, 0.5, 2), (3.5, 0.5, 1)]
        for beat, dur, octv in bpat:
            place(mix['bass'], pluck_bass(note_hz(bass) * octv, dur * BEAT * 0.95) * 0.75, at(bi, beat))
        # acordes em contratempo (piano elétrico)
        for beat in (0.5, 1.5, 2.5, 3.5):
            for j, nn in enumerate(notes):
                place(mix['keys'], pan(ep(note_hz(nn), BEAT * 0.45, 0.16), -0.3 + 0.3 * j), at(bi, beat))
        # brilhinho a cada 2 compassos
        if bi % 2 == 0:
            for k, nn in enumerate(['C7', 'G6', 'E7']):
                place(mix['sparkle'], pan(fm_bell(note_hz(nn), 0.6, 3.0, 1.0, 0.2) * 0.05, 0.6 - 0.6 * k), at(bi, 3 + k * 0.33))

    def put_melody(mel, start_bar, vol=0.32):
        for b, beat, nn, d in mel:
            place(mix['lead'], pan(marimba(note_hz(nn), d * BEAT + 0.4, vol), 0.1), at(start_bar + b, beat))
            place(mix['lead'], pan(ep(note_hz(nn), d * BEAT * 0.9, vol * 0.25), 0.1), at(start_bar + b, beat))
    put_melody(MELODY_A, 0)
    put_melody(MELODY_B, 4)
    put_melody(MELODY_C, 8)

    # efeitos por trilha
    mix['keys'] = reverb_st(mix['keys'], 1.4, 0.35, 21)
    mix['lead'] = reverb_st(mix['lead'], 1.6, 0.3, 22)
    mix['sparkle'] = reverb_st(mix['sparkle'], 2.0, 0.5, 23)
    out = mix['drums'] * 0.85 + mix['bass'] * 0.9 + mix['keys'] * 0.8 + mix['lead'] * 1.0 + mix['sparkle']
    # loop sem emenda: o que passa do fim volta para o começo
    n = int(total * SR)
    loop = out[:n].copy()
    rest = out[n:]
    loop[:len(rest)] += rest[:n]
    # compressão leve + normalização
    loop = np.tanh(loop / (np.abs(loop).max() + 1e-9) * 1.6) / np.tanh(1.6)
    return loop * 0.62


def reverb_st(x, size, wet, seed):
    L = reverb(x[:, 0], size, wet, seed=seed)
    R = reverb(x[:, 1], size, wet, seed=seed + 50)
    n = len(x)
    return np.stack([L[:n, 0], R[:n, 1]], 1)


if __name__ == '__main__':
    os.makedirs(os.path.join(OUT, 'sfx'), exist_ok=True)
    os.makedirs(os.path.join(OUT, 'musica'), exist_ok=True)
    for name, fn in SFX.items():
        x = fn()
        save_wav(name, x)
        print(f'{name}: {len(x) / SR:.2f}s')
    m = musica()
    wpath = os.path.join(OUT, 'musica', 'trilha_loop.wav')
    wavfile.write(wpath, SR, (np.clip(m, -1, 1) * 32767).astype(np.int16))
    opath = os.path.join(OUT, 'musica', 'trilha_loop.ogg')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wpath, '-c:a', 'libvorbis', '-q:a', '6', opath], check=True)
    print(f'trilha: {len(m) / SR:.2f}s ({len(PROG)} compassos a {BPM} BPM)')
