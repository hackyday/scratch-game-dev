# -*- coding: utf-8 -*-
"""
assets.py — Generatori procedurali di asset per giochi Scratch.

Tutti i generatori restituiscono dati pronti per Target.costume() /
Target.sound() di sb3_builder:
    player.costume(A.ship("#ffcc00"), name="player", rotation_center=(32,32))
    player.sound(A.sfx_jump(), name="jump")

SVG = coordinate 64x64 (sprite) o 480x360 (backdrop). Il rotation center
corrisponde al centro dell'immagine, così la rotazione di Scratch è corretta.
"""

import math
import struct
import io
import wave

# ================================================================ SVG

_SVGNS = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h}'>"


def _wrap(w, h, body):
    return f"{_SVGNS.format(w=w, h=h)}{body}</svg>"


def _hex(c):
    if not (isinstance(c, str) and c.startswith("#") and len(c) == 7):
        raise ValueError(f"colore non valido: {c!r}")
    return c


def _shade(c, factor):
    """Ritorna il colore scurito/schiarito (factor <1 scurisce, >1 schiarisce)."""
    r = int(c[1:3], 16); g = int(c[3:5], 16); b = int(c[5:7], 16)
    r = min(255, max(0, int(r * factor)))
    g = min(255, max(0, int(g * factor)))
    b = min(255, max(0, int(b * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


def _star_points(cx, cy, outer, inner, n=5, rot=-math.pi / 2):
    pts = []
    for i in range(n * 2):
        r = outer if i % 2 == 0 else inner
        a = rot + i * math.pi / n
        pts.append(f"{cx + r * math.cos(a):.1f},{cy + r * math.sin(a):.1f}")
    return " ".join(pts)


# ---- sprite 64x64 ---------------------------------------------------

def circle(fill, stroke="#222222", size=64):
    r = size / 2 - 4
    return _wrap(size, size,
                 f"<circle cx='{size/2}' cy='{size/2}' r='{r}' fill='{fill}' "
                 f"stroke='{stroke}' stroke-width='3'/>"
                 f"<circle cx='{size/2-r/3}' cy='{size/2-r/3}' r='{r/4}' fill='{_shade(fill,1.6)}'/>")


def square(fill, stroke="#222222", size=64, rx=8):
    m = 6
    return _wrap(size, size,
                 f"<rect x='{m}' y='{m}' width='{size-2*m}' height='{size-2*m}' rx='{rx}' "
                 f"fill='{fill}' stroke='{stroke}' stroke-width='3'/>")


def triangle(fill, stroke="#222222", size=64):
    """Triangolo orientato verso destra (già in direzione Scratch 90°)."""
    m = 6
    pts = f"{size-m},{size/2} {m},{m} {m},{size-m}"
    return _wrap(size, size,
                 f"<polygon points='{pts}' fill='{fill}' stroke='{stroke}' stroke-width='3'/>")


def star(fill="#ffdd33", stroke="#b8860b", size=64):
    return _wrap(size, size,
                 f"<polygon points='{_star_points(32, 34, 28, 12)}' fill='{fill}' "
                 f"stroke='{stroke}' stroke-width='2'/>"
                 f"<circle cx='32' cy='34' r='4' fill='#ffffff'/>")


def heart(fill="#ff3355", size=64):
    return _wrap(size, size,
                 f"<path d='M32 56 C 10 40 6 24 16 14 C 24 6 32 12 32 20 "
                 f"C 32 12 40 6 48 14 C 58 24 54 40 32 56 Z' fill='{fill}'/>")


def ship(fill="#00ccff", size=64):
    """Navicella spaziale punta a destra (rotation center 32,32, dir 90)."""
    d = _shade(fill, 0.6)
    return _wrap(size, size,
                 f"<path d='M58 32 L 18 8 L 26 32 L 18 56 Z' fill='{fill}' stroke='{d}' stroke-width='2'/>"
                 f"<circle cx='36' cy='32' r='6' fill='#ffffff'/>"
                 f"<path d='M18 8 L 4 14 L 14 22 Z M18 56 L 4 50 L 14 42 Z' fill='{d}'/>")


def rocket(fill="#eeeeee", accent="#ff4444", size=64):
    """Razzo punta a destra."""
    body = f"M8 32 C 20 10 40 10 52 32 C 40 54 20 54 8 32 Z"
    return _wrap(size, size,
                 f"<path d='{body}' fill='{fill}' stroke='#555' stroke-width='2'/>"
                 f"<path d='M52 32 L 62 24 L 58 32 L 62 40 Z' fill='{accent}'/>"
                 f"<circle cx='34' cy='32' r='7' fill='#66ccff' stroke='#333' stroke-width='2'/>")


def enemy(fill="#aa33ff", size=64):
    d = _shade(fill, 0.55)
    return _wrap(size, size,
                 f"<rect x='10' y='20' width='44' height='24' rx='10' fill='{fill}'/>"
                 f"<path d='M10 22 L 2 32 L 10 42 Z M54 22 L 62 32 L 54 42 Z' fill='{d}'/>"
                 f"<circle cx='26' cy='32' r='5' fill='#ff2222'/>"
                 f"<circle cx='38' cy='32' r='5' fill='#ff2222'/>")


def character(fill="#44cc44", skin="#ffcc88", size=64):
    """Semplissimo personaggio vista frontale (punta su: usa rotation -90 o dir 0)."""
    return _wrap(size, size,
                 f"<circle cx='32' cy='18' r='11' fill='{skin}' stroke='#333' stroke-width='2'/>"
                 f"<circle cx='28' cy='16' r='2' fill='#222'/><circle cx='36' cy='16' r='2' fill='#222'/>"
                 f"<path d='M28 22 Q 32 25 36 22' stroke='#222' stroke-width='1.5' fill='none'/>"
                 f"<rect x='22' y='29' width='20' height='22' rx='6' fill='{fill}' stroke='#333' stroke-width='2'/>"
                 f"<rect x='24' y='50' width='6' height='9' rx='3' fill='#3355ff'/>"
                 f"<rect x='34' y='50' width='6' height='9' rx='3' fill='#3355ff'/>")


def coin(fill="#ffcc00", size=64):
    return _wrap(size, size,
                 f"<circle cx='32' cy='32' r='24' fill='{fill}' stroke='#b8860b' stroke-width='3'/>"
                 f"<circle cx='32' cy='32' r='15' fill='{_shade(fill, 1.25)}'/>"
                 f"<text x='32' y='41' font-size='22' text-anchor='middle' fill='#b8860b' font-family='sans-serif'>$</text>")


def platform(fill="#8855ff", size=64):
    return _wrap(size, size,
                 f"<rect x='0' y='20' width='64' height='24' fill='{fill}'/>"
                 f"<rect x='0' y='20' width='64' height='6' fill='{_shade(fill,1.4)}'/>"
                 f"<rect x='0' y='38' width='64' height='6' fill='{_shade(fill,0.6)}'/>")


def ball(fill="#ff8800", size=64):
    r = 26
    return _wrap(size, size,
                 f"<circle cx='32' cy='32' r='{r}' fill='{fill}'/>"
                 f"<path d='M 6 32 A 26 26 0 0 1 58 32' fill='{_shade(fill,1.3)}'/>"
                 f"<circle cx='24' cy='24' r='5' fill='#ffffff' opacity='0.7'/>")


def bullet(fill="#ffee00", size=32):
    return _wrap(size, size,
                 f"<ellipse cx='16' cy='16' rx='12' ry='5' fill='{fill}'/>"
                 f"<circle cx='26' cy='16' r='4' fill='{_shade(fill,1.4)}'/>")


# ---- backdrop 480x360 -----------------------------------------------

def backdrop(c1="#0f2d5c", c2="#1a4a8a", style="gradient", w=480, h=360):
    """backdrop 480x360. style: gradient | stars | grid | sky | night | plain"""
    if style == "plain":
        body = f"<rect width='{w}' height='{h}' fill='{c1}'/>"
    elif style == "sky":
        body = (
            f"<rect width='{w}' height='{h}' fill='{c1}'/>"
            f"<ellipse cx='{w/2}' cy='{h}' rx='{w}' ry='{h*0.4}' fill='{c2}'/>"
            f"<circle cx='{w*0.8}' cy='{h*0.18}' r='26' fill='#ffee88'/>"
            f"<ellipse cx='{w*0.25}' cy='{h*0.3}' rx='70' ry='24' fill='#ffffff' opacity='0.85'/>"
            f"<ellipse cx='{w*0.4}' cy='{h*0.22}' rx='55' ry='19' fill='#ffffff' opacity='0.75'/>"
        )
    elif style == "night":
        stars = "".join(
            f"<circle cx='{(i*97)%w}' cy='{(i*61)%int(h*0.8)}' r='{1.5+(i%2)}' fill='#fff'/>"
            for i in range(60)
        )
        body = (f"<rect width='{w}' height='{h}' fill='{c1}'/>{stars}"
                f"<circle cx='{w*0.82}' cy='{h*0.15}' r='22' fill='#f4f4d0'/>"
                f"<rect y='{h*0.75}' width='{w}' height='{h*0.25}' fill='{c2}'/>")
    elif style == "grid":
        lines = "".join(
            f"<line x1='{i*40}' y1='0' x2='{i*40}' y2='{h}' stroke='#ffffff22' stroke-width='1'/>"
            for i in range(w // 40))
        lines += "".join(
            f"<line x1='0' y1='{i*40}' x2='{w}' y2='{i*40}' stroke='#ffffff22' stroke-width='1'/>"
            for i in range(h // 40))
        body = f"<rect width='{w}' height='{h}' fill='{c1}'/>{lines}"
    elif style == "stars":
        stars = "".join(
            f"<circle cx='{(i*97)%w}' cy='{(i*61)%h}' r='{1+(i%2)*1.5}' fill='#ffffff' opacity='0.{5+(i%3)}'/>"
            for i in range(80))
        body = f"<rect width='{w}' height='{h}' fill='{c1}'/>{stars}"
    else:  # gradient
        body = (
            f"<defs><linearGradient id='g' x1='0' y1='0' x2='0' y2='1'>"
            f"<stop offset='0' stop-color='{c1}'/><stop offset='1' stop-color='{c2}'/>"
            f"</linearGradient></defs>"
            f"<rect width='{w}' height='{h}' fill='url(#g)'/>"
        )
    return _wrap(w, h, body)


# ================================================================ WAV (SFX)

_SR = 44100


def _wav_bytes(samples):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(_SR)
        frames = bytearray()
        for s in samples:
            frames += struct.pack("<h", max(-32767, min(32767, int(s * 32767))))
        w.writeframes(bytes(frames))
    return buf.getvalue()


def _env(i, n, attack=0.01):
    t = i / n
    a = min(1.0, t / attack) if attack > 0 else 1.0
    release = (1 - t) ** 1.5
    return a * release


def tone(freq_start, freq_end, duration, wave_type="square", volume=0.5):
    n = int(_SR * duration)
    samples = []
    for i in range(n):
        t = i / n
        f = freq_start + (freq_end - freq_start) * t
        ph = i * f / _SR
        if wave_type == "sine":
            val = math.sin(2 * math.pi * ph)
        elif wave_type == "square":
            val = 1.0 if math.sin(2 * math.pi * ph) > 0 else -1.0
        elif wave_type == "saw":
            val = 2 * (ph % 1.0) - 1
        elif wave_type == "noise":
            val = math.sin(2 * math.pi * ph) * (2 * (i * 7919 % 1000) / 1000 - 1)
        else:
            raise ValueError(f"wave_type non valido: {wave_type}")
        samples.append(val * volume * _env(i, n))
    return _wav_bytes(samples)


def noise_burst(duration=0.3, volume=0.5, sweep=True):
    n = int(_SR * duration)
    samples = []
    seed = 12345
    for i in range(n):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        val = (seed / 0x3FFFFFFF) - 1
        if sweep:
            val *= (1 - i / n)
        samples.append(val * volume * _env(i, n, 0.002))
    return _wav_bytes(samples)


def melody(notes, note_dur=0.12, wave_type="square", volume=0.4):
    """notes: lista di frequenze (0 = pausa). Ritorna un unico WAV."""
    samples = []
    for f in notes:
        if f <= 0:
            samples.extend([0.0] * int(_SR * note_dur))
            continue
        n = int(_SR * note_dur)
        for i in range(n):
            val = math.sin(2 * math.pi * i * f / _SR)
            if wave_type == "square":
                val = 1.0 if val > 0 else -1.0
            samples.append(val * volume * _env(i, n, 0.02))
    return _wav_bytes(samples)


_NOTE = {"C4": 261.6, "D4": 293.7, "E4": 329.6, "F4": 349.2, "G4": 392.0,
         "A4": 440.0, "B4": 493.9, "C5": 523.3, "D5": 587.3, "E5": 659.3,
         "G5": 784.0, "A5": 880.0, "C6": 1046.5, "R": 0}


def melody_names(names, note_dur=0.15, wave_type="square", volume=0.4):
    """melody con nomi di nota: melody_names(['C4','E4','G4','C5','R','G4'])"""
    return melody([_NOTE[n] for n in names], note_dur, wave_type, volume)


# ---- preset SFX pronti ----------------------------------------------

def sfx_jump():
    return tone(300, 700, 0.18, "square", 0.5)


def sfx_coin():
    return melody([988, 1319], 0.09, "square", 0.4)


def sfx_hit():
    return tone(400, 80, 0.25, "saw", 0.6)


def sfx_explosion():
    return noise_burst(0.45, 0.8)


def sfx_laser():
    return tone(1200, 300, 0.15, "saw", 0.4)


def sfx_powerup():
    return melody([523, 659, 784, 1047], 0.08, "square", 0.45)


def sfx_gameover():
    return melody([392, 330, 262, 196], 0.22, "saw", 0.4)


def sfx_win():
    return melody_names(["C5", "E5", "G5", "C6"], 0.14, "square", 0.45)


def sfx_blip():
    return tone(800, 800, 0.06, "square", 0.3)


def sfx_menu_select():
    return melody([660, 880], 0.07, "square", 0.35)
