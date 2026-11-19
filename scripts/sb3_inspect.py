# -*- coding: utf-8 -*-
"""
sb3_inspect.py — Reverse engineering di file .sb3 esistenti SENZA leggere project.json.

Un project.json reale pesa spesso centinaia di KB (decine di migliaia di token).
Questo tool lo legge al posto tuo (stdlib pura) e restituisce viste COMPATTE:

    python3 sb3_inspect.py info      game.sb3               # panoramica + stima token + hint genere
    python3 sb3_inspect.py tree      game.sb3               # sprite -> script numerati (1 riga ciascuno)
    python3 sb3_inspect.py show      game.sb3 Player        # pseudo-codice (sintassi scratchblocks)
    python3 sb3_inspect.py show      game.sb3 Player -s 0,2 # solo gli script #0 e #2
    python3 sb3_inspect.py flow      game.sb3               # broadcast, variabili, custom block, cloni
    python3 sb3_inspect.py find      game.sb3 "score"       # cerca opcode/testo/variabili/messaggi
    python3 sb3_inspect.py assets    game.sb3 -o assets/    # elenca (e con -o estrae) costumi e suoni
    python3 sb3_inspect.py diff      a.sb3 b.sb3 [--scripts] # confronto strutturale (+ pseudo-codice)
    python3 sb3_inspect.py import    game.sb3 Enemy -o x.py  # estrae uno sprite come frammento builder
    python3 sb3_inspect.py explain   game.sb3               # riassunto euristico (scene/score/win)
    python3 sb3_inspect.py to-python game.sb3 -o rebuild.py --build
                                                              # rigenera il progetto come script
                                                              # sb3_builder (copiare/imparare/modificare)

Accetta anche file .sprite3 (singolo sprite condiviso).

Percorso consigliato per l'AI:  info|explain -> tree -> flow -> show <sprite> -s N -> (find)
-> import <sprite> per copiare un pezzo; to-python per l'intero gioco
-> diff dopo rebuild per verificare la struttura.
"""

import argparse
import hashlib
import json
import keyword
import os
import re
import subprocess
import sys
import zipfile
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))

CORE = {
    "argument", "colour", "control", "data", "event", "looks",
    "math", "motion", "operator", "procedures", "sensing", "sound",
}

HATS = {
    "event_whenflagclicked", "event_whenkeypressed",
    "event_whenbroadcastreceived", "event_whenstageclicked",
    "event_whenthisspriteclicked", "event_whenbackdropswitchesto",
    "event_whengreaterthan", "event_whentouchingobject",
    "control_start_as_clone", "procedures_definition",
}

BOOLEAN_OPS = {
    "operator_and", "operator_or", "operator_not", "operator_gt",
    "operator_lt", "operator_equals", "operator_contains",
    "sensing_touchingobject", "sensing_touchingcolor",
    "sensing_coloristouchingcolor", "sensing_keypressed",
    "sensing_mousedown", "data_listcontainsitem",
    "argument_reporter_boolean",
}

# Template in sintassi scratchblocks. {NOME} = input (reporter/primitiva) oppure field (dropdown).
TEMPLATES = {
    # motion
    "motion_movesteps": "move {STEPS} steps",
    "motion_turnright": "turn right {DEGREES} degrees",
    "motion_turnleft": "turn left {DEGREES} degrees",
    "motion_goto": "go to {TO}",
    "motion_gotoxy": "go to x: {X} y: {Y}",
    "motion_glideto": "glide {SECS} secs to {TO}",
    "motion_glidesecstoxy": "glide {SECS} secs to x: {X} y: {Y}",
    "motion_pointindirection": "point in direction {DIRECTION}",
    "motion_pointtowards": "point towards {TOWARDS}",
    "motion_changexby": "change x by {DX}",
    "motion_setx": "set x to {X}",
    "motion_changeyby": "change y by {DY}",
    "motion_sety": "set y to {Y}",
    "motion_ifonedgebounce": "if on edge, bounce",
    "motion_setrotationstyle": "set rotation style {STYLE}",
    "motion_xposition": "x position",
    "motion_yposition": "y position",
    "motion_direction": "direction",
    # looks
    "looks_sayforsecs": "say {MESSAGE} for {SECS} seconds",
    "looks_say": "say {MESSAGE}",
    "looks_thinkforsecs": "think {MESSAGE} for {SECS} seconds",
    "looks_think": "think {MESSAGE}",
    "looks_switchcostumeto": "switch costume to {COSTUME}",
    "looks_nextcostume": "next costume",
    "looks_switchbackdropto": "switch backdrop to {BACKDROP}",
    "looks_switchbackdroptoandwait": "switch backdrop to {BACKDROP} and wait",
    "looks_nextbackdrop": "next backdrop",
    "looks_changesizeby": "change size by {CHANGE}",
    "looks_setsizeto": "set size to {SIZE} %",
    "looks_changeeffectby": "change {EFFECT} effect by {CHANGE}",
    "looks_seteffectto": "set {EFFECT} effect to {VALUE}",
    "looks_cleargraphiceffects": "clear graphic effects",
    "looks_show": "show",
    "looks_hide": "hide",
    "looks_gotofrontback": "go to {FRONT_BACK} layer",
    "looks_goforwardbackwardlayers": "go {FORWARD_BACKWARD} {NUM} layers",
    "looks_costumenumbername": "costume {NUMBER_NAME}",
    "looks_backdropnumbername": "backdrop {NUMBER_NAME}",
    "looks_size": "size",
    # sound
    "sound_playuntildone": "play sound {SOUND_MENU} until done",
    "sound_play": "start sound {SOUND_MENU}",
    "sound_stopallsounds": "stop all sounds",
    "sound_changeeffectby": "change {EFFECT} effect by {VALUE}",
    "sound_seteffectto": "set {EFFECT} effect to {VALUE}",
    "sound_cleareffects": "clear sound effects",
    "sound_changevolumeby": "change volume by {VOLUME}",
    "sound_setvolumeto": "set volume to {VOLUME} %",
    "sound_volume": "volume",
    # events
    "event_whenflagclicked": "when green flag clicked",
    "event_whenkeypressed": "when {KEY_OPTION} key pressed",
    "event_whenthisspriteclicked": "when this sprite clicked",
    "event_whenstageclicked": "when stage clicked",
    "event_whenbackdropswitchesto": "when backdrop switches to {BACKDROP}",
    "event_whengreaterthan": "when {WHENGREATERTHANMENU} > {VALUE}",
    "event_whenbroadcastreceived": "when I receive {BROADCAST_OPTION}",
    "event_whentouchingobject": "when this sprite touches {TOUCHINGOBJECTMENU}",
    "event_broadcast": "broadcast {BROADCAST_INPUT}",
    "event_broadcastandwait": "broadcast {BROADCAST_INPUT} and wait",
    # control
    "control_wait": "wait {DURATION} seconds",
    "control_repeat": "repeat {TIMES}",
    "control_forever": "forever",
    "control_if": "if {CONDITION} then",
    "control_if_else": "if {CONDITION} then",
    "control_wait_until": "wait until {CONDITION}",
    "control_repeat_until": "repeat until {CONDITION}",
    "control_while": "while {CONDITION}",
    "control_for_each": "for each {VARIABLE} in {VALUE}",
    "control_stop": "stop {STOP_OPTION}",
    "control_start_as_clone": "when I start as a clone",
    "control_create_clone_of": "create clone of {CLONE_OPTION}",
    "control_delete_this_clone": "delete this clone",
    # sensing
    "sensing_touchingobject": "touching {TOUCHINGOBJECTMENU} ?",
    "sensing_touchingcolor": "touching color {COLOR} ?",
    "sensing_coloristouchingcolor": "color {COLOR} is touching {COLOR2} ?",
    "sensing_distanceto": "distance to {DISTANCETOMENU}",
    "sensing_askandwait": "ask {QUESTION} and wait",
    "sensing_answer": "answer",
    "sensing_keypressed": "key {KEY_OPTION} pressed?",
    "sensing_mousedown": "mouse down?",
    "sensing_mousex": "mouse x",
    "sensing_mousey": "mouse y",
    "sensing_setdragmode": "set drag mode {DRAG_MODE}",
    "sensing_loudness": "loudness",
    "sensing_timer": "timer",
    "sensing_resettimer": "reset timer",
    "sensing_of": "{PROPERTY} of {OBJECT}",
    "sensing_current": "current {CURRENTMENU}",
    "sensing_dayssince2000": "days since 2000",
    "sensing_username": "username",
    # operators
    "operator_add": "{NUM1} + {NUM2}",
    "operator_subtract": "{NUM1} - {NUM2}",
    "operator_multiply": "{NUM1} * {NUM2}",
    "operator_divide": "{NUM1} / {NUM2}",
    "operator_random": "pick random {FROM} to {TO}",
    "operator_gt": "{OPERAND1} > {OPERAND2}",
    "operator_lt": "{OPERAND1} < {OPERAND2}",
    "operator_equals": "{OPERAND1} = {OPERAND2}",
    "operator_and": "{OPERAND1} and {OPERAND2}",
    "operator_or": "{OPERAND1} or {OPERAND2}",
    "operator_not": "not {OPERAND}",
    "operator_join": "join {STRING1} {STRING2}",
    "operator_letter_of": "letter {LETTER} of {STRING}",
    "operator_length": "length of {STRING}",
    "operator_contains": "{STRING1} contains {STRING2} ?",
    "operator_mod": "{NUM1} mod {NUM2}",
    "operator_round": "round {NUM}",
    "operator_mathop": "{OPERATOR} of {NUM}",
    # data
    "data_setvariableto": "set {VARIABLE} to {VALUE}",
    "data_changevariableby": "change {VARIABLE} by {VALUE}",
    "data_showvariable": "show variable {VARIABLE}",
    "data_hidevariable": "hide variable {VARIABLE}",
    "data_addtolist": "add {ITEM} to {LIST}",
    "data_deleteoflist": "delete {INDEX} of {LIST}",
    "data_deletealloflist": "delete all of {LIST}",
    "data_insertatlist": "insert {ITEM} at {INDEX} of {LIST}",
    "data_replaceitemoflist": "replace item {INDEX} of {LIST} with {ITEM}",
    "data_itemoflist": "item {INDEX} of {LIST}",
    "data_itemnumoflist": "item # of {ITEM} in {LIST}",
    "data_lengthoflist": "length of {LIST}",
    "data_listcontainsitem": "{LIST} contains {ITEM} ?",
    "data_showlist": "show list {LIST}",
    "data_hidelist": "hide list {LIST}",
    # pen
    "pen_clear": "erase all",
    "pen_stamp": "stamp",
    "pen_penDown": "pen down",
    "pen_penUp": "pen up",
    "pen_setPenColorToColor": "set pen color to {COLOR}",
    "pen_changePenColorParamBy": "change pen {COLOR_PARAM} by {VALUE}",
    "pen_setPenColorParamTo": "set pen {COLOR_PARAM} to {VALUE}",
    "pen_changePenSizeBy": "change pen size by {SIZE}",
    "pen_setPenSizeTo": "set pen size to {SIZE}",
    # music
    "music_playDrumForBeats": "play drum {DRUM} for {BEATS} beats",
    "music_restForBeats": "rest for {BEATS} beats",
    "music_playNoteForBeats": "play note {NOTE} for {BEATS} beats",
    "music_setInstrument": "set instrument to {INSTRUMENT}",
    "music_setTempo": "set tempo to {TEMPO}",
    "music_changeTempo": "change tempo by {TEMPO}",
    "music_getTempo": "tempo",
    # --- estensioni comuni (TurboWarp / music / pen / video) ---
    "music_playDrumForBeats": "play drum {DRUM} for {BEATS} beats",
    "music_restForBeats": "rest for {BEATS} beats",
    "music_playNoteForBeats": "play note {NOTE} for {BEATS} beats",
    "music_setInstrument": "set instrument to {INSTRUMENT}",
    "music_setTempo": "set tempo to {TEMPO}",
    "music_changeTempo": "change tempo by {TEMPO}",
    "music_getTempo": "tempo",
    "pen_clear": "erase all",
    "pen_stamp": "stamp",
    "pen_penDown": "pen down",
    "pen_penUp": "pen up",
    "pen_setPenColorToColor": "set pen color to {COLOR}",
    "pen_changePenColorParamBy": "change pen {COLOR_PARAM} by {VALUE}",
    "pen_setPenColorParamTo": "set pen {COLOR_PARAM} to {VALUE}",
    "pen_changePenSizeBy": "change pen size by {SIZE}",
    "pen_setPenSizeTo": "set pen size to {SIZE}",
    "videoSensing_whenMotionGreaterThan": "when video motion > {REFERENCE}",
    "videoSensing_videoOn": "video {ATTRIBUTE} on {SUBJECT}",
    "videoSensing_videoToggle": "turn video {VIDEO_STATE}",
    "videoSensing_setVideoTransparency": "set video transparency to {TRANSPARENCY}",
    "text2speech_speakAndWait": "speak {WORDS}",
    "text2speech_setVoice": "set voice to {VOICE}",
    "text2speech_setLanguage": "set language to {LANGUAGE}",
    "translate_getTranslate": "translate {WORDS} to {LANGUAGE}",
    "translate_getViewerLanguage": "language",
    # TurboWarp / runtime
    "tw_getLastKeyPressed": "last key pressed",
    "tw_getMouseX": "mouse x",
    "tw_getMouseY": "mouse y",

}

LIST_WRITE_OPS = {
    "data_addtolist", "data_deleteoflist", "data_deletealloflist",
    "data_insertatlist", "data_replaceitemoflist",
}
VAR_WRITE_OPS = {"data_setvariableto", "data_changevariableby"}


def die(msg):
    print(f"ERRORE: {msg}", file=sys.stderr)
    sys.exit(1)


# ====================================================================
# Caricamento
# ====================================================================

class Target:
    def __init__(self, sb, d):
        self.sb = sb
        self.d = d
        self.name = d.get("name", "?")
        self.is_stage = bool(d.get("isStage"))
        self.blocks = d.get("blocks", {}) or {}
        self._scripts = None

    def block(self, bid):
        b = self.blocks.get(bid) if isinstance(bid, str) else None
        return b if isinstance(b, dict) else None

    def scripts(self):
        """Id dei blocchi top-level (ordinati per y, x)."""
        if self._scripts is None:
            tops = [i for i, b in self.blocks.items()
                    if isinstance(b, dict) and b.get("topLevel")]
            tops.sort(key=lambda i: (self.blocks[i].get("y", 0) or 0,
                                     self.blocks[i].get("x", 0) or 0))
            self._scripts = tops
        return self._scripts

    def chain(self, first):
        out, seen, cur = [], set(), first
        while cur and cur not in seen and self.block(cur):
            seen.add(cur)
            out.append(cur)
            cur = self.blocks[cur].get("next")
        return out

    def subtree(self, first):
        """Tutti gli id raggiungibili da first (next + input)."""
        acc, stack = set(), [first]
        while stack:
            bid = stack.pop()
            b = self.block(bid)
            if b is None or bid in acc:
                continue
            acc.add(bid)
            if b.get("next"):
                stack.append(b["next"])
            for inp in (b.get("inputs") or {}).values():
                stack.extend(input_refs(inp))
        return acc

    def real_count(self, ids):
        return sum(1 for i in ids if not self.blocks[i].get("shadow"))

    def definitions(self):
        """proccode -> dict(argnames, argids, argdefaults, warp, returns, def_id)."""
        out = {}
        for bid, b in self.blocks.items():
            if not isinstance(b, dict) or b.get("opcode") != "procedures_definition":
                continue
            ref = (b.get("inputs") or {}).get("custom_block")
            kind, val = input_parts(ref)
            proto = self.block(val) if kind == "block" else None
            if not proto or not proto.get("mutation"):
                continue
            m = proto["mutation"]
            out[m.get("proccode", "")] = {
                "argnames": _jl(m.get("argumentnames")),
                "argids": _jl(m.get("argumentids")),
                "argdefaults": _jl(m.get("argumentdefaults")),
                "warp": str(m.get("warp", "false")).lower() == "true",
                "returns": str(m.get("return", "false")).lower() == "true",
                "def_id": bid,
            }
        return out


def _jl(x):
    if isinstance(x, list):
        return x
    try:
        v = json.loads(x) if isinstance(x, str) else []
        return v if isinstance(v, list) else []
    except ValueError:
        return []


class Sb3:
    def __init__(self, path):
        self.path = path
        self.zf = None
        self.file_size = os.path.getsize(path) if os.path.exists(path) else 0
        if not os.path.exists(path):
            die(f"file non trovato: {path}")
        if path.lower().endswith(".json"):
            with open(path, "rb") as f:
                raw = f.read()
        else:
            try:
                self.zf = zipfile.ZipFile(path)
            except zipfile.BadZipFile:
                die(f"{path} non è uno zip valido (un .sb3/.sprite3 è uno ZIP)")
            names = self.zf.namelist()
            # .sb3 → project.json ; .sprite3 → sprite.json
            if "project.json" in names:
                pj = "project.json"
            elif "sprite.json" in names:
                pj = "sprite.json"
            else:
                pj = next((n for n in names if n.endswith(("project.json", "sprite.json"))), None)
            if not pj:
                die("project.json / sprite.json non trovato nello zip")
            raw = self.zf.read(pj)
        self.raw_size = len(raw)
        try:
            self.data = json.loads(raw.decode("utf-8-sig"))
        except ValueError as e:
            die(f"project.json non valido: {e}")
        # .sprite3: root is a single target object, not {targets:[...]}
        self.is_sprite3 = False
        if "targets" not in self.data:
            if "blocks" in self.data or "costumes" in self.data:
                self.data = {
                    "targets": [self.data],
                    "monitors": [],
                    "extensions": [],
                    "meta": {"semver": "3.0.0", "agent": "sprite3"},
                }
                self.is_sprite3 = True
            else:
                die("project.json senza 'targets' (è un file sb2/sb? serve sb3)")
        self.targets = [Target(self, t) for t in self.data["targets"]]
        self.monitors = self.data.get("monitors", []) or []
        self.extensions = self.data.get("extensions", []) or []

    @property
    def stage(self):
        return next((t for t in self.targets if t.is_stage), self.targets[0])

    def find_target(self, name):
        for t in self.targets:
            if t.name == name:
                return t
        low = name.lower()
        for t in self.targets:
            if t.name.lower() == low:
                return t
        cands = [t for t in self.targets if low in t.name.lower()]
        if len(cands) == 1:
            return cands[0]
        names = ", ".join(t.name for t in self.targets)
        die(f"target '{name}' non trovato. Disponibili: {names}")


def input_parts(inp):
    """(kind, value): ('prim', [..]) | ('block', id) | ('none', None)."""
    if not isinstance(inp, list) or len(inp) < 2:
        return ("none", None)
    a = inp[1]
    if a is None and len(inp) >= 3:
        a = inp[2]
    if isinstance(a, list):
        return ("prim", a)
    if isinstance(a, str):
        return ("block", a)
    return ("none", None)


def input_refs(inp):
    out = []
    if isinstance(inp, list):
        for x in inp[1:]:
            if isinstance(x, str):
                out.append(x)
    return out


def field_val(b, name, default=None):
    f = (b.get("fields") or {}).get(name)
    if isinstance(f, list) and f:
        return f[0]
    return default


def is_hat(op):
    if not op or not isinstance(op, str):
        return False
    if op in HATS:
        return True
    # core non-hat
    prefix = op.split("_", 1)[0]
    if prefix in CORE:
        return False
    # extension hats: common patterns
    return bool(re.search(
        r"(?:^|_)(?:when|hat|on[A-Z]|start|receive|broadcast)",
        op, re.I))


# ====================================================================
# Pseudo-codice (sintassi scratchblocks)
# ====================================================================

def num_text(v):
    return "_" if v is None or v == "" else str(v)


class Pseudo:
    def __init__(self, tgt):
        self.t = tgt
        self.defs = tgt.definitions()

    def prim(self, p):
        t = p[0]
        if t in (4, 5, 6, 7, 8):
            return f"({num_text(p[1])})"
        if t == 9:
            return f"[{p[1]}]"
        if t == 10:
            return f"[{p[1]}]"
        if t == 11:
            return f"[{p[1]} v]"
        if t == 12:
            return f"({p[1]})"
        if t == 13:
            return f"({p[1]} :: list)"
        return f"[{p}]"

    def inp(self, b, name):
        raw = (b.get("inputs") or {}).get(name)
        kind, val = input_parts(raw)
        if kind == "prim":
            return self.prim(val)
        if kind == "block":
            blk = self.t.block(val)
            if blk is None:
                rawp = self.t.blocks.get(val)
                return self.prim(rawp) if isinstance(rawp, list) else None
            if blk.get("shadow") and not blk.get("inputs"):
                flds = blk.get("fields") or {}
                if flds:
                    fv = next(iter(flds.values()))
                    return f"[{fv[0] if isinstance(fv, list) and fv else fv} v]"
            return self.inline(val)
        return None

    def fill(self, tpl, b):
        def rep(m):
            n = m.group(1)
            if n in (b.get("inputs") or {}):
                s = self.inp(b, n)
                return s if s is not None else "_"
            fv = field_val(b, n)
            if fv is not None:
                return f"[{fv} v]"
            return "_"
        return re.sub(r"\{(\w+)\}", rep, tpl)

    def generic(self, b):
        parts = [b["opcode"]]
        for k, v in (b.get("fields") or {}).items():
            parts.append(f"[{v[0] if isinstance(v, list) and v else v} v]")
        for k in (b.get("inputs") or {}):
            if k.startswith("SUBSTACK"):
                continue
            s = self.inp(b, k)
            if s is not None:
                parts.append(f"{k}:{s}")
        return " ".join(parts)

    def proc_label(self, proccode, argvals):
        it = iter(argvals)
        return re.sub(r"%[snb]", lambda m: next(it, "_"), proccode)

    def head(self, bid):
        b = self.t.block(bid)
        op = b["opcode"]
        if op == "procedures_definition":
            kind, val = input_parts((b.get("inputs") or {}).get("custom_block"))
            proto = self.t.block(val) if kind == "block" else None
            if proto and proto.get("mutation"):
                m = proto["mutation"]
                names = _jl(m.get("argumentnames"))
                return "define " + self.proc_label(
                    m.get("proccode", "?"), [f"({n})" for n in names])
            return "define ?"
        if op == "procedures_call":
            m = b.get("mutation") or {}
            ids = _jl(m.get("argumentids"))
            vals = []
            for aid in ids:
                s = self.inp(b, aid)
                vals.append(s if s is not None else "_")
            return self.proc_label(m.get("proccode", "?"), vals)
        tpl = TEMPLATES.get(op)
        return self.fill(tpl, b) if tpl else self.generic(b)

    def inline(self, bid):
        b = self.t.block(bid)
        op = b["opcode"]
        if op == "data_variable":
            return f"({field_val(b, 'VARIABLE', '?')})"
        if op == "data_listcontents":
            return f"({field_val(b, 'LIST', '?')} :: list)"
        if op == "argument_reporter_string_number":
            return f"({field_val(b, 'VALUE', '?')})"
        if op == "argument_reporter_boolean":
            return f"<{field_val(b, 'VALUE', '?')}>"
        txt = self.head(bid)
        return f"<{txt}>" if op in BOOLEAN_OPS else f"({txt})"

    def stack(self, first, ind, out, limit):
        pad = "  " * ind
        for bid in self.t.chain(first):
            if len(out) >= limit:
                return
            b = self.t.block(bid)
            out.append(pad + self.head(bid))
            subs = sorted(k for k in (b.get("inputs") or {})
                          if k.startswith("SUBSTACK"))
            for k in subs:
                if k == "SUBSTACK2" and b["opcode"] == "control_if_else":
                    out.append(pad + "else")
                kind, val = input_parts(b["inputs"][k])
                if kind == "block":
                    blk = self.t.block(val)
                    if blk and not blk.get("shadow"):
                        self.stack(val, ind + 1, out, limit)

    def script_lines(self, top, limit=10 ** 9):
        out = []
        self.stack(top, 0, out, limit)
        return out


# ====================================================================
# Analisi (fatti per script)
# ====================================================================

def script_facts(t, top):
    ids = t.subtree(top)
    f = {"sends": set(), "recvs": set(), "var_w": set(), "var_r": set(),
         "list_w": set(), "list_r": set(), "calls": set(), "clones": set(),
         "blocks": t.real_count(ids)}
    for bid in ids:
        b = t.blocks[bid]
        op = b.get("opcode", "")
        if op in ("event_broadcast", "event_broadcastandwait"):
            kind, val = input_parts((b.get("inputs") or {}).get("BROADCAST_INPUT"))
            if kind == "prim" and val and val[0] == 11:
                f["sends"].add(val[1])
            elif kind == "block" and t.block(val) and t.block(val).get("shadow"):
                f["sends"].add(field_val(t.block(val), "BROADCAST_OPTION", "?"))
            else:
                f["sends"].add("<dinamico>")
        elif op == "event_whenbroadcastreceived":
            f["recvs"].add(field_val(b, "BROADCAST_OPTION", "?"))
        elif op in VAR_WRITE_OPS:
            f["var_w"].add(field_val(b, "VARIABLE", "?"))
        elif op in LIST_WRITE_OPS:
            f["list_w"].add(field_val(b, "LIST", "?"))
        elif op == "procedures_call":
            f["calls"].add((b.get("mutation") or {}).get("proccode", "?"))
        elif op == "control_create_clone_of":
            kind, val = input_parts((b.get("inputs") or {}).get("CLONE_OPTION"))
            mb = t.block(val) if kind == "block" else None
            f["clones"].add(field_val(mb, "CLONE_OPTION", "?") if mb else "?")
        elif op == "data_variable":
            f["var_r"].add(field_val(b, "VARIABLE", "?"))
        elif op == "data_listcontents":
            f["list_r"].add(field_val(b, "LIST", "?"))
        elif op in ("data_itemoflist", "data_lengthoflist",
                    "data_listcontainsitem", "data_itemnumoflist"):
            f["list_r"].add(field_val(b, "LIST", "?"))
        for inp in (b.get("inputs") or {}).values():
            kind, val = input_parts(inp)
            if kind == "prim" and val and val[0] == 12:
                f["var_r"].add(val[1])
            elif kind == "prim" and val and val[0] == 13:
                f["list_r"].add(val[1])
    return f


# ====================================================================
# Comandi: info / tree / show / flow / find / assets
# ====================================================================

def short(s, n=78):
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[:n - 1] + "…"


def cmd_info(sb, a):
    kb = sb.raw_size / 1024
    tok = sb.raw_size // 4
    print(f"FILE     {os.path.basename(sb.path)}  ({sb.file_size/1024:.0f} KB)")
    print(f"JSON     project.json {kb:.1f} KB ≈ {tok:,} token  →  NON leggerlo: usa questi comandi")
    meta = sb.data.get("meta", {})
    if meta:
        print(f"META     agent={meta.get('agent', '?')}  vm={meta.get('vm', '?')}")
    print(f"EXT      {', '.join(sb.extensions) if sb.extensions else '(nessuna: vanilla)'}")
    total_ops = Counter()
    for t in sb.targets:
        ids = [i for i, b in t.blocks.items() if isinstance(b, dict)]
        real = [i for i in ids if not t.blocks[i].get("shadow")]
        for i in real:
            total_ops[t.blocks[i].get("opcode", "?")] += 1
        kind = "stage" if t.is_stage else "sprite"
        extra = ""
        if not t.is_stage:
            extra = (f"  x={t.d.get('x')} y={t.d.get('y')} size={t.d.get('size')}"
                     f"{'' if t.d.get('visible', True) else ' (nascosto)'}")
        print(f"TARGET   {t.name} [{kind}]  {len(t.scripts())} script, {len(real)} blocchi, "
              f"{len(t.d.get('costumes', []))} costumi, {len(t.d.get('sounds', []))} suoni{extra}")
        lv = t.d.get("variables", {})
        if lv and not t.is_stage:
            print("           var locali: " + ", ".join(f"{v[0]}={v[1]}" for v in lv.values()))
        ll = t.d.get("lists", {})
        if ll and not t.is_stage:
            print("           liste locali: " + ", ".join(f"{v[0]}[{len(v[1])}]" for v in ll.values()))
    st = sb.stage
    gv = st.d.get("variables", {})
    if gv:
        print("VAR GLOB " + ", ".join(
            f"{v[0]}={json.dumps(v[1], ensure_ascii=False)}{' ☁' if len(v) > 2 else ''}"
            for v in gv.values()))
    gl = st.d.get("lists", {})
    if gl:
        print("LISTE    " + ", ".join(f"{v[0]}[{len(v[1])} elementi]" for v in gl.values()))
    bc = st.d.get("broadcasts", {})
    if bc:
        print("MESSAGGI " + ", ".join(bc.values()))
    procs = []
    for t in sb.targets:
        for code, d in t.definitions().items():
            procs.append(f"{t.name}: {code}{' (warp)' if d['warp'] else ''}"
                         f"{' →return' if d['returns'] else ''}")
    if procs:
        print("CUSTOM   " + " | ".join(procs))
    vis = [m for m in sb.monitors if m.get("visible")]
    if vis:
        print("MONITOR  " + ", ".join(
            f"{(m.get('params') or {}).get('VARIABLE') or m.get('opcode')}"
            f"{'@' + m['spriteName'] if m.get('spriteName') else ''}" for m in vis))
    print("TOP OP   " + ", ".join(f"{o}×{n}" for o, n in total_ops.most_common(12)))
    hints = _genre_hints(sb)
    if hints:
        print("HINT     " + " | ".join(hints))
    print("\nPROSSIMI PASSI: tree | flow | show <target> [-s N] | find <testo> | assets | diff | to-python")


def cmd_tree(sb, a):
    for t in sb.targets:
        if a.target and t is not sb.find_target(a.target):
            continue
        ps = Pseudo(t)
        tops = t.scripts()
        kind = "stage" if t.is_stage else "sprite"
        print(f"[{t.name}] ({kind}, {len(tops)} script)")
        for i, top in enumerate(tops):
            f = script_facts(t, top)
            head = short(ps.head(top), 60)
            op = t.blocks[top].get("opcode", "")
            tag = "" if is_hat(op) else "  (stack senza hat)"
            bits = []
            if f["sends"]:
                bits.append("invia " + ",".join(sorted(f["sends"])))
            if f["var_w"]:
                bits.append("scrive " + ",".join(sorted(f["var_w"])))
            if f["calls"]:
                bits.append("chiama " + ",".join(sorted(f["calls"])))
            if f["clones"]:
                bits.append("clona " + ",".join(sorted(f["clones"])))
            print(f"  #{i}  {head}  — {f['blocks']} blocchi{tag}"
                  + (f"  [{'; '.join(bits)}]" if bits else ""))
        print()


def parse_sel(sel, n):
    if not sel:
        return None
    out = set()
    for part in sel.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.update(range(int(lo), int(hi) + 1))
        elif part:
            out.add(int(part))
    return {i for i in out if 0 <= i < n}


def cmd_show(sb, a):
    targets = [sb.find_target(a.target)] if a.target else sb.targets
    limit = a.max_lines
    printed = 0
    for t in targets:
        ps = Pseudo(t)
        tops = t.scripts()
        sel = parse_sel(a.script, len(tops))
        if not tops:
            continue
        print(f"=== {t.name} ===")
        printed += 1
        for i, top in enumerate(tops):
            if sel is not None and i not in sel:
                continue
            remaining = limit - printed
            if remaining <= 0:
                print(f"... (troncato a {limit} righe: usa -s N o --max-lines)")
                return
            lines = ps.script_lines(top, remaining)
            op = t.blocks[top].get("opcode", "")
            print(f"# #{i}" + ("" if is_hat(op) else " (stack senza hat)"))
            for ln in lines:
                print(ln)
            printed += len(lines) + 1
            print()
            printed += 1


def cmd_flow(sb, a):
    senders, receivers = defaultdict(list), defaultdict(list)
    var_w, var_r = defaultdict(set), defaultdict(set)
    list_w, list_r = defaultdict(set), defaultdict(set)
    clones, calls = [], defaultdict(set)
    gvars = {v[0] for v in sb.stage.d.get("variables", {}).values()}
    for t in sb.targets:
        for i, top in enumerate(t.scripts()):
            f = script_facts(t, top)
            ref = f"{t.name}#{i}"
            for m in f["sends"]:
                senders[m].append(ref)
            for m in f["recvs"]:
                receivers[m].append(ref)
            for v in f["var_w"]:
                var_w[v].add(ref)
            for v in f["var_r"]:
                var_r[v].add(ref)
            for v in f["list_w"]:
                list_w[v].add(ref)
            for v in f["list_r"]:
                list_r[v].add(ref)
            for c in f["clones"]:
                clones.append(f"{ref} clona {c}")
            for c in f["calls"]:
                calls[(t.name, c)].add(ref)
            if t.blocks[top].get("opcode") == "control_start_as_clone":
                clones.append(f"{ref} = comportamento del clone")
    print("## MESSAGGI (broadcast)")
    names = sorted(set(senders) | set(receivers) | set(sb.stage.d.get("broadcasts", {}).values()))
    for m in names:
        print(f"  {m}: inviato da [{', '.join(senders.get(m, [])) or '—'}]"
              f" → ricevuto da [{', '.join(receivers.get(m, [])) or '—'}]")
    print("\n## VARIABILI (W=scritta da, R=letta da)")
    for v in sorted(set(var_w) | set(var_r)):
        scope = "glob" if v in gvars else "loc"
        print(f"  {v} ({scope}): W[{', '.join(sorted(var_w.get(v, []))) or '—'}]"
              f" R[{', '.join(sorted(var_r.get(v, []))) or '—'}]")
    if list_w or list_r:
        print("\n## LISTE")
        for v in sorted(set(list_w) | set(list_r)):
            print(f"  {v}: W[{', '.join(sorted(list_w.get(v, []))) or '—'}]"
                  f" R[{', '.join(sorted(list_r.get(v, []))) or '—'}]")
    printed_proc = False
    for t in sb.targets:
        for code, d in t.definitions().items():
            if not printed_proc:
                print("\n## CUSTOM BLOCK")
                printed_proc = True
            who = sorted(calls.get((t.name, code), []))
            print(f"  {t.name}: {code}  args={d['argnames']}  chiamato da [{', '.join(who) or '—'}]")
    if clones:
        print("\n## CLONI")
        for c in clones:
            print("  " + c)


def block_haystack(t, b):
    parts = [b.get("opcode", "")]
    for k, v in (b.get("fields") or {}).items():
        if isinstance(v, list) and v:
            parts.append(str(v[0]))
    for inp in (b.get("inputs") or {}).values():
        kind, val = input_parts(inp)
        if kind == "prim" and val and len(val) > 1:
            parts.append(str(val[1]))
        elif kind == "block":
            mb = t.block(val)
            if mb and mb.get("shadow"):
                for v in (mb.get("fields") or {}).values():
                    if isinstance(v, list) and v:
                        parts.append(str(v[0]))
    m = b.get("mutation") or {}
    if m.get("proccode"):
        parts.append(m["proccode"])
    return " ".join(parts)


def cmd_find(sb, a):
    pat = re.compile(a.query if a.regex else re.escape(a.query), re.I)
    hits = 0
    for t in sb.targets:
        ps = Pseudo(t)
        owner = {}
        tops = t.scripts()
        for i, top in enumerate(tops):
            for bid in t.subtree(top):
                owner.setdefault(bid, i)
        for bid, b in t.blocks.items():
            if not isinstance(b, dict) or b.get("shadow"):
                continue
            if pat.search(block_haystack(t, b)):
                try:
                    line = ps.head(bid)
                except Exception:  # noqa: BLE001
                    line = b.get("opcode", "?")
                idx = owner.get(bid)
                print(f"{t.name}#{idx if idx is not None else '?'}: {short(line, 100)}")
                hits += 1
                if hits >= a.limit:
                    print(f"... (limite {a.limit}: usa --limit)")
                    return
    if not hits:
        print("nessun risultato")


def asset_files(sb):
    """Genera (target, kind, index, entry)."""
    for t in sb.targets:
        for i, c in enumerate(t.d.get("costumes", [])):
            yield t, "costume", i, c
        for i, s in enumerate(t.d.get("sounds", [])):
            yield t, "sound", i, s


def slug(s, default="x"):
    s = re.sub(r"[^\w\-]+", "_", str(s), flags=re.U).strip("_")
    return s or default


def asset_relpath(t, kind, i, entry):
    ext = entry.get("dataFormat") or os.path.splitext(entry.get("md5ext", ""))[1].lstrip(".") or "bin"
    return os.path.join(slug(t.name), f"{kind[0]}{i:02d}_{slug(entry.get('name', kind))}.{ext}")


def read_asset(sb, entry):
    if not sb.zf:
        return None
    for key in (entry.get("md5ext"),
                f"{entry.get('assetId')}.{entry.get('dataFormat')}"):
        if key and key in sb.zf.namelist():
            return sb.zf.read(key)
    return None


def cmd_assets(sb, a):
    n = 0
    for t, kind, i, e in asset_files(sb):
        rel = asset_relpath(t, kind, i, e)
        data = read_asset(sb, e)
        size = f"{len(data)/1024:.1f} KB" if data is not None else "MANCANTE"
        extra = (f"centro=({e.get('rotationCenterX')},{e.get('rotationCenterY')}) res={e.get('bitmapResolution', 1)}"
                 if kind == "costume" else f"rate={e.get('rate')} campioni={e.get('sampleCount')}")
        print(f"{t.name:<14} {kind:<8} {e.get('name')!r:<24} {e.get('dataFormat'):<4} {size:>10}  {extra}")
        if a.out and data is not None:
            dst = os.path.join(a.out, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as f:
                f.write(data)
            n += 1
    if a.out:
        print(f"\nestratti {n} file in {a.out}/")


# ====================================================================
# to-python: rigenera il progetto come script sb3_builder
# ====================================================================

class Raw:
    def __init__(self, code):
        self.code = code


class Call:
    def __init__(self, func, args=(), kwargs=()):
        self.func, self.args, self.kwargs = func, list(args), list(kwargs)
        self._one = None


class Dict:
    def __init__(self, items):
        self.items = list(items)
        self._one = None


def one(n):
    if isinstance(n, Raw):
        return n.code
    if n._one is not None:
        return n._one
    if isinstance(n, Dict):
        s = "{" + ", ".join(f"{k}: {one(v)}" for k, v in n.items) + "}"
    else:
        parts = [one(x) for x in n.args]
        parts += [(f"**{one(v)}" if k == "**" else f"{k}={one(v)}") for k, v in n.kwargs]
        s = f"{n.func}({', '.join(parts)})"
    n._one = s
    return s


def render(n, ind=0, width=100):
    if isinstance(n, Raw):
        return n.code
    s = one(n)
    if len(s) + ind <= width:
        return s
    pad = " " * (ind + 4)
    if isinstance(n, Dict):
        body = ",\n".join(f"{pad}{k}: {render(v, ind + 4, width)}" for k, v in n.items)
        return "{\n" + body + ",\n" + " " * ind + "}"
    parts = [render(x, ind + 4, width) for x in n.args]
    parts += [(f"**{render(v, ind + 4, width)}" if k == "**" else f"{k}={render(v, ind + 4, width)}")
              for k, v in n.kwargs]
    body = ",\n".join(pad + p for p in parts)
    return f"{n.func}(\n{body},\n{' ' * ind})"


def pylit(x):
    if x is None or isinstance(x, bool):
        return repr(x)
    if isinstance(x, (int, float)):
        return repr(x)
    if isinstance(x, str):
        return json.dumps(x, ensure_ascii=False)
    if isinstance(x, (list, tuple)):
        return "[" + ", ".join(pylit(i) for i in x) + "]"
    if isinstance(x, dict):
        return "{" + ", ".join(f"{pylit(k)}: {pylit(v)}" for k, v in x.items()) + "}"
    return repr(x)


def num_literal(s):
    s = str(s)
    if re.fullmatch(r"-?\d+", s) and str(int(s)) == s:
        return s
    try:
        f = float(s)
        if repr(f) == s and "e" not in s.lower() and f == f and abs(f) != float("inf"):
            return s
    except ValueError:
        pass
    return None


def py_ident(name, used):
    base = re.sub(r"\W+", "_", name, flags=re.U).strip("_").lower() or "x"
    if base[0].isdigit():
        base = "_" + base
    if keyword.iskeyword(base):
        base += "_"
    cand, n = base, 2
    while cand in used:
        cand = f"{base}_{n}"
        n += 1
    used.add(cand)
    return cand


RESERVED_KW = {"inputs", "fields", "mutation", "shadow"}


class PyGen:
    def __init__(self, sb, out_py, keep_loose=False):
        self.sb = sb
        self.out_py = out_py
        self.keep_loose = keep_loose
        stem = os.path.splitext(os.path.basename(out_py))[0]
        self.stem = stem
        self.assets_dirname = stem + "_assets"
        self.assets_dir = os.path.join(os.path.dirname(os.path.abspath(out_py)), self.assets_dirname)
        self.warnings, self.skipped = [], []
        self.extra_hats = set()
        self.used = {"p", "stage", "S", "os", "sys", "hashlib", "HERE"}
        self.py = {}
        self.cbvars = {}
        self.n_assets = 0
        sys.path.insert(0, HERE)
        try:
            import sb3_builder as _S
            self.builder_hats = set(_S.HAT_BLOCKS)
        except Exception:  # noqa: BLE001
            self.builder_hats = set(HATS)

    # ---- helpers ------------------------------------------------------
    def warn(self, msg):
        if msg not in self.warnings:
            self.warnings.append(msg)

    def scope_arg(self, t, kind, ident, name):
        key = "variables" if kind == "var" else "lists"
        if t.is_stage:
            return ""
        if ident in t.d.get(key, {}):
            return ", " + self.py[t.name]
        if ident in self.sb.stage.d.get(key, {}):
            return ""
        if any(v[0] == name for v in t.d.get(key, {}).values()):
            return ", " + self.py[t.name]
        return ""

    def prim_node(self, t, p):
        ty = p[0]
        if ty == 4:
            lit = num_literal(p[1])
            return Call("S.v", [Raw(lit if lit is not None else pylit(str(p[1])))])
        if ty == 10:
            return Call("S.s", [Raw(pylit(str(p[1])))])
        if ty == 9:
            if re.fullmatch(r"#[0-9a-fA-F]{6}", str(p[1])):
                return Call("S.color", [Raw(pylit(p[1]))])
            return Raw(f"[9, {pylit(str(p[1]))}]")
        if ty in (5, 6, 7, 8):
            return Raw(f"[{ty}, {pylit(str(p[1]))}]")
        if ty == 11:
            return Raw(f"p.broadcast_ref({pylit(p[1])})")
        if ty == 12:
            ident = p[2] if len(p) > 2 else None
            return Raw(f"p.var({pylit(p[1])}{self.scope_arg(t, 'var', ident, p[1])})")
        if ty == 13:
            ident = p[2] if len(p) > 2 else None
            return Raw(f"p.listref({pylit(p[1])}{self.scope_arg(t, 'list', ident, p[1])})")
        self.warn(f"primitiva sconosciuta {p!r}")
        return Raw(f"[4, {pylit(str(p[1]) if len(p) > 1 else '')}]")

    def menu_node(self, b):
        flds = {}
        for k, v in (b.get("fields") or {}).items():
            flds[k] = v[0] if isinstance(v, list) and v else v
        op = b["opcode"]
        ok = op.endswith("menu") or op in (
            "looks_costume", "looks_backdrops", "sound_sounds_menu",
            "sensing_keyoptions", "music_menu_DRUM", "music_menu_INSTRUMENT",
            "videoSensing_menu_VIDEO_STATE", "sensing_of_object_menu",
            "event_touchingobjectmenu")
        if ok:
            return Call("S.menu", [Raw(pylit(op)), Raw(pylit(flds))])
        norm = {k: [v, None] for k, v in flds.items()}
        return Call("S.Block", [Raw(pylit(op)), Raw("{}"), Raw(pylit(norm)),
                                Raw("None"), Raw("True")])

    def seq_node(self, t, first):
        ids = [i for i in t.chain(first) if not t.blocks[i].get("shadow")]
        if not ids:
            return None
        return Call("S.seq", [self.block_node(t, i) for i in ids])

    def input_node(self, t, name, inp):
        kind, val = input_parts(inp)
        if kind == "prim":
            return self.prim_node(t, val)
        if kind != "block":
            return None
        raw = t.blocks.get(val)
        if isinstance(raw, list):
            return self.prim_node(t, raw)
        b = t.block(val)
        if b is None:
            return None
        if b.get("shadow"):
            return self.menu_node(b)
        if name.startswith("SUBSTACK") or b.get("next"):
            return self.seq_node(t, val)
        return self.block_node(t, val)

    def field_code(self, t, name, v):
        v0 = v[0] if isinstance(v, list) and v else v
        vid = v[1] if isinstance(v, list) and len(v) > 1 else None
        if name == "VARIABLE":
            return f"[{pylit(v0)}, VID({pylit(v0)}{self.scope_arg(t, 'var', vid, v0)})]"
        if name == "LIST":
            return f"[{pylit(v0)}, LID({pylit(v0)}{self.scope_arg(t, 'list', vid, v0)})]"
        if name == "BROADCAST_OPTION":
            return f"[{pylit(v0)}, BID({pylit(v0)})]"
        if vid is None:
            return f"[{pylit(v0)}, None]"
        return pylit(list(v))

    # ---- un blocco ------------------------------------------------------
    def block_node(self, t, bid):
        b = t.block(bid)
        op = b["opcode"]
        fields = b.get("fields") or {}
        inputs = b.get("inputs") or {}
        py = self.py[t.name]

        if op == "event_whenflagclicked":
            return Call("S.when_flag")
        if op == "control_start_as_clone":
            return Call("S.start_as_clone")
        if op == "event_whenbroadcastreceived" and "BROADCAST_OPTION" in fields:
            return Call("p.broadcast_receive", [Raw(pylit(field_val(b, "BROADCAST_OPTION")))])
        if op in ("event_broadcast", "event_broadcastandwait"):
            kind, val = input_parts(inputs.get("BROADCAST_INPUT"))
            name = None
            if kind == "prim" and val and val[0] == 11:
                name = val[1]
            elif kind == "block" and t.block(val) and t.block(val).get("shadow"):
                name = field_val(t.block(val), "BROADCAST_OPTION")
            if name is not None:
                kw = [("and_wait", Raw("True"))] if op.endswith("andwait") else []
                return Call("p.broadcast_send", [Raw(pylit(name))], kw)
        if op == "data_variable":
            n = field_val(b, "VARIABLE", "?")
            vid = (fields.get("VARIABLE") or [None, None])[1]
            return Raw(f"p.var({pylit(n)}{self.scope_arg(t, 'var', vid, n)})")
        if op == "data_listcontents":
            n = field_val(b, "LIST", "?")
            vid = (fields.get("LIST") or [None, None])[1]
            return Raw(f"p.listref({pylit(n)}{self.scope_arg(t, 'list', vid, n)})")
        if op == "argument_reporter_string_number":
            return Call("S.arg", [Raw(pylit(field_val(b, "VALUE", "?")))])
        if op == "argument_reporter_boolean":
            return Call("S.arg_bool", [Raw(pylit(field_val(b, "VALUE", "?")))])
        if op == "control_stop":
            opt = field_val(b, "STOP_OPTION")
            if opt in ("all", "this script", "other scripts in sprite"):
                return Call("S.stop", [Raw(pylit(opt))])
        if op == "procedures_definition":
            kind, val = input_parts(inputs.get("custom_block"))
            proto = t.block(val) if kind == "block" else None
            code = (proto or {}).get("mutation", {}).get("proccode")
            cb = self.cbvars.get((t.name, code))
            if cb:
                return Raw(f"{cb}.hat")
        if op == "procedures_call":
            m = b.get("mutation") or {}
            code = m.get("proccode")
            cb = self.cbvars.get((t.name, code))
            d = t.definitions().get(code)
            if cb and d:
                call_ids = _jl(m.get("argumentids")) or d["argids"]
                items = []
                for idx, aname in enumerate(d["argnames"]):
                    aid = call_ids[idx] if idx < len(call_ids) else None
                    node = self.input_node(t, aid, inputs.get(aid)) if aid in inputs else None
                    items.append((aname, node if node is not None else Call("S.s", [Raw('""')])))
                plain = all(n.isidentifier() and not keyword.iskeyword(n)
                            and n not in ("self", "custom_block") for n, _ in items)
                if plain:
                    return Call(f"{py}.call", [Raw(cb)], items)
                return Call(f"{py}.call", [Raw(cb)],
                            [("**", Dict([(pylit(n), nd) for n, nd in items]))])
            self.warn(f"{t.name}: chiamata a custom block non definito {code!r}")

        # ---- generico: S.blk(opcode, INPUT=..., fields={...}, mutation={...})
        kwargs, extra = [], []
        for name, inp in inputs.items():
            node = self.input_node(t, name, inp)
            if node is None:
                continue
            if name.isidentifier() and not keyword.iskeyword(name) and name not in RESERVED_KW:
                kwargs.append((name, node))
            else:
                extra.append((pylit(name), node))
        if extra:
            kwargs.append(("inputs", Dict(extra)))
        if fields:
            kwargs.append(("fields", Dict([(pylit(k), Raw(self.field_code(t, k, v)))
                                           for k, v in fields.items()])))
        mut = b.get("mutation")
        if mut:
            mm = {k: v for k, v in mut.items() if k not in ("tagName", "children")}
            if mut.get("children"):
                self.warn(f"{t.name}: mutation con children ignorati in {op}")
            if mm:
                kwargs.append(("mutation", Raw(pylit(mm))))
        return Call("S.blk", [Raw(pylit(op))], kwargs)

    # ---- generazione ------------------------------------------------------
    def costume_line(self, t, i, c, rel):
        py = self.py[t.name]
        path = f"os.path.join(ASSETS, {pylit(rel.replace(os.sep, '/'))})"
        fmt = (c.get("dataFormat") or "").lower()
        cx, cy = c.get("rotationCenterX", 0), c.get("rotationCenterY", 0)
        res = c.get("bitmapResolution", 1)
        if fmt in ("svg", "png"):
            return (f"{py}.costume({path}, name={pylit(c.get('name'))}, "
                    f"rotation_center=({pylit(cx)}, {pylit(cy)}), bitmap_resolution={pylit(res)})")
        return (f"raw_costume({py}, {path}, {pylit(c.get('name'))}, ({pylit(cx)}, {pylit(cy)}), "
                f"{pylit(res)}, {pylit(fmt)})")

    def sound_line(self, t, s, rel):
        py = self.py[t.name]
        path = f"os.path.join(ASSETS, {pylit(rel.replace(os.sep, '/'))})"
        return (f"raw_sound({py}, {path}, {pylit(s.get('name'))}, {pylit(s.get('dataFormat') or 'wav')}, "
                f"{pylit(s.get('rate', 44100))}, {pylit(s.get('sampleCount', 0))}, "
                f"{pylit(s.get('format', ''))})")

    def gen_assets(self, t, lines):
        py = self.py[t.name]
        for i, c in enumerate(t.d.get("costumes", [])):
            rel = asset_relpath(t, "costume", i, c)
            data = read_asset(self.sb, c)
            if data is None:
                self.warn(f"{t.name}: costume {c.get('name')!r} mancante nello zip (saltato)")
                continue
            dst = os.path.join(self.assets_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as f:
                f.write(data)
            self.n_assets += 1
            lines.append(self.costume_line(t, i, c, rel))
        for i, s in enumerate(t.d.get("sounds", [])):
            rel = asset_relpath(t, "sound", i, s)
            data = read_asset(self.sb, s)
            if data is None:
                self.warn(f"{t.name}: suono {s.get('name')!r} mancante nello zip (saltato)")
                continue
            dst = os.path.join(self.assets_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as f:
                f.write(data)
            self.n_assets += 1
            lines.append(self.sound_line(t, s, rel))
        cur = t.d.get("currentCostume", 0)
        if cur:
            lines.append(f"{py}.currentCostume = {pylit(cur)}")
        vol = t.d.get("volume", 100)
        if vol != 100:
            lines.append(f"{py}.volume = {pylit(vol)}")

    def gen_scripts(self, t, lines):
        py = self.py[t.name]
        for idx, top in enumerate(t.scripts()):
            head = t.blocks[top]
            op = head.get("opcode", "")
            chain = [i for i in t.chain(top) if not t.blocks[i].get("shadow")]
            hat = is_hat(op)
            if not hat and not self.keep_loose:
                self.skipped.append(f"{t.name}#{idx}: stack senza hat ({op}, {len(chain)} blocchi)")
                lines.append(f"# [saltato] {t.name}#{idx}: stack senza hat ({op}, {len(chain)} blocchi)"
                             f" — usa --keep-loose per includerlo")
                continue
            if op not in self.builder_hats:
                self.extra_hats.add(op)
            nodes = [self.block_node(t, i) for i in chain]
            kw = [("x", Raw(pylit(head.get("x", 48)))), ("y", Raw(pylit(head.get("y", 48))))]
            lines.append(f"# --- {t.name}#{idx}")
            lines.append(render(Call(f"{py}.script", nodes, kw)))
            lines.append("")

    def gen(self):
        sb = self.sb
        stage = sb.stage
        for t in sb.targets:
            self.py[t.name] = "stage" if t.is_stage else py_ident("sp_" + t.name, self.used)
        body = []

        # ---- dati globali
        body.append("# ---------------- dati globali (Stage) ----------------")
        for vid, v in stage.d.get("variables", {}).items():
            cloud = ", cloud=True" if len(v) > 2 and v[2] else ""
            body.append(f"p.variable({pylit(v[0])}, {pylit(v[1])}{cloud})")
        for lid, l in stage.d.get("lists", {}).items():
            body.append(f"p.list({pylit(l[0])}, {pylit(l[1])})")
        for name in stage.d.get("broadcasts", {}).values():
            body.append(f"p.broadcast({pylit(name)})")
        body.append("")
        body.append("def VID(name, scope=None): return p.var(name, scope)[2]")
        body.append("def LID(name, scope=None): return p.listref(name, scope)[2]")
        body.append("def BID(name): return p.broadcast_ref(name)[2]")
        body.append("")

        # ---- target: stage prima, sprite per layerOrder
        order = [stage] + sorted([t for t in sb.targets if not t.is_stage],
                                 key=lambda x: x.d.get("layerOrder", 0))
        for t in order:
            py = self.py[t.name]
            body.append(f"# ================ {t.name} ================")
            if not t.is_stage:
                rs = t.d.get("rotationStyle", "all around")
                if rs not in ("all around", "left-right", "don't rotate"):
                    rs = "all around"
                body.append(
                    f"{py} = p.sprite({pylit(t.name)}, x={pylit(t.d.get('x', 0))}, "
                    f"y={pylit(t.d.get('y', 0))}, size={pylit(t.d.get('size', 100))}, "
                    f"direction={pylit(t.d.get('direction', 90))}, visible={pylit(t.d.get('visible', True))}, "
                    f"rotationStyle={pylit(rs)}, draggable={pylit(t.d.get('draggable', False))})")
                for vid, v in t.d.get("variables", {}).items():
                    cloud = ", cloud=True" if len(v) > 2 and v[2] else ""
                    body.append(f"{py}.variable({pylit(v[0])}, {pylit(v[1])}{cloud})")
                for lid, l in t.d.get("lists", {}).items():
                    body.append(f"{py}.list({pylit(l[0])}, {pylit(l[1])})")
            self.gen_assets(t, body)
            for code, d in t.definitions().items():
                cb = py_ident(f"cb_{self.py[t.name]}_{code}", self.used)
                self.cbvars[(t.name, code)] = cb
                args = [(n, d["argdefaults"][i] if i < len(d["argdefaults"]) else "")
                        for i, n in enumerate(d["argnames"])]
                body.append(f"{cb} = {py}.custom_block({pylit(code)}, {pylit([list(a) for a in args])}, "
                            f"returns={pylit(d['returns'])}, warp={pylit(d['warp'])})")
            body.append("")
            self.gen_scripts(t, body)

        # ---- monitor
        for m in sb.monitors:
            params = m.get("params") or {}
            if m.get("opcode") == "data_variable" and not m.get("spriteName") and params.get("VARIABLE"):
                body.append(f"p.monitor({pylit(params['VARIABLE'])}, mode={pylit(m.get('mode', 'default'))}, "
                            f"x={pylit(m.get('x', 5))}, y={pylit(m.get('y', 5))}, "
                            f"visible={pylit(bool(m.get('visible', True)))})")
            else:
                body.append(f"# [monitor non supportato dal builder] {m.get('opcode')} "
                            f"{params} sprite={m.get('spriteName')}")

        # ---- header
        head = [
            "# -*- coding: utf-8 -*-",
            f'"""Rebuild di {os.path.basename(sb.path)} generato da sb3_inspect.py to-python.',
            "",
            "Script nel formato della skill scratch-game-dev (sb3_builder). Modificalo e rilancialo:",
            "i costumi/suoni originali sono nella cartella *_assets accanto a questo file.",
            '"""',
            "import hashlib",
            "import os",
            "import sys",
            f"sys.path.insert(0, {pylit(HERE)})",
            "import sb3_builder as S",
            "",
            "HERE = os.path.dirname(os.path.abspath(__file__))",
            f"ASSETS = os.path.join(HERE, {pylit(self.assets_dirname)})",
            f"OUT = os.path.join(HERE, {pylit(self.stem + '.sb3')})",
            "",
            "",
            "def raw_costume(t, path, name, center, res, ext):",
            "    with open(path, 'rb') as f:",
            "        data = f.read()",
            "    md5 = hashlib.md5(data).hexdigest()",
            "    t.costumes.append(({'name': name, 'assetId': md5, 'md5ext': f'{md5}.{ext}',",
            "                        'dataFormat': ext, 'bitmapResolution': res,",
            "                        'rotationCenterX': center[0], 'rotationCenterY': center[1]}, data))",
            "",
            "",
            "def raw_sound(t, path, name, ext, rate, count, fmt):",
            "    with open(path, 'rb') as f:",
            "        data = f.read()",
            "    md5 = hashlib.md5(data).hexdigest()",
            "    t.sounds.append(({'name': name, 'assetId': md5, 'md5ext': f'{md5}.{ext}',",
            "                      'dataFormat': ext, 'format': fmt, 'rate': rate,",
            "                      'sampleCount': count}, data))",
            "",
            "",
            "p = S.Project()",
            "stage = p.stage",
        ]
        for ext in sb.extensions:
            if ext not in CORE:
                head.append(f"p.use_extension({pylit(ext)})")
        if self.extra_hats:
            head.append(f"S.HAT_BLOCKS.update({pylit(sorted(self.extra_hats))})  # hat non standard")
        head.append("")
        tail = ["", "p.build(OUT)", 'print("creato", OUT)', ""]
        return "\n".join(head + body + tail)


def fingerprint(path):
    sb = Sb3(path)
    fp = {}
    for t in sb.targets:
        ops = Counter(b.get("opcode") for b in t.blocks.values()
                      if isinstance(b, dict) and not b.get("shadow"))
        fp[t.name] = {
            "ops": ops,
            "vars": sorted(v[0] for v in t.d.get("variables", {}).values()),
            "lists": sorted(v[0] for v in t.d.get("lists", {}).values()),
            "costumes": [c.get("name") for c in t.d.get("costumes", [])],
            "sounds": [s.get("name") for s in t.d.get("sounds", [])],
        }
    return fp


def compare(orig, rebuilt):
    a, b = fingerprint(orig), fingerprint(rebuilt)
    diffs = []
    for name in a:
        if name not in b:
            diffs.append(f"target mancante: {name}")
            continue
        for key in ("vars", "lists", "costumes", "sounds"):
            if a[name][key] != b[name][key]:
                diffs.append(f"{name}: {key} diversi")
        d = a[name]["ops"] - b[name]["ops"]
        e = b[name]["ops"] - a[name]["ops"]
        if d:
            diffs.append(f"{name}: opcode persi {dict(d)}")
        if e:
            diffs.append(f"{name}: opcode in più {dict(e)}")
    return diffs


def cmd_to_python(sb, a):
    out = a.out or (os.path.splitext(os.path.basename(sb.path))[0] + "_rebuild.py")
    g = PyGen(sb, out, keep_loose=a.keep_loose)
    code = g.gen()
    with open(out, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"scritto {out}  ({len(code.splitlines())} righe) + {g.n_assets} asset in {g.assets_dirname}/")
    for s in g.skipped:
        print("  [saltato]", s)
    for w in g.warnings:
        print("  [warn]", w)
    if not a.build:
        print(f"\nper ricostruire:  python3 {out}")
        return
    r = subprocess.run([sys.executable, out], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(out)))
    if r.returncode != 0:
        print("BUILD FALLITO:\n" + (r.stderr or r.stdout)[-1500:])
        sys.exit(2)
    rebuilt = os.path.join(os.path.dirname(os.path.abspath(out)), g.stem + ".sb3")
    print(f"build OK → {rebuilt}")
    try:
        import validate_sb3
        iss = validate_sb3.validate(rebuilt, True)
        print(f"validate_sb3: {len(iss.errors)} errori, {len(iss.warnings)} warning")
        for e in iss.errors[:10]:
            print("  ERROR", e)
    except Exception as e:  # noqa: BLE001
        print(f"(validate_sb3 non eseguito: {e})")
    diffs = compare(sb.path, rebuilt)
    if diffs:
        print("DIFFERENZE rispetto all'originale:")
        for d in diffs[:20]:
            print("  -", d)
    else:
        print("confronto con l'originale: blocchi/variabili/asset identici ✔")


# ====================================================================

def _target_sig(t):
    """Compact signature of a target for structural diff."""
    tops = t.scripts()
    ops = Counter()
    for top in tops:
        for bid in t.subtree(top):
            b = t.block(bid)
            if b and not b.get("shadow"):
                ops[b.get("opcode", "?")] += 1
    costumes = [c.get("name", "?") for c in (t.d.get("costumes") or [])]
    sounds = [s.get("name", "?") for s in (t.d.get("sounds") or [])]
    # variables stored as {id: [name, value, cloud?]}
    var_list = []
    for vid, v in (t.d.get("variables") or {}).items():
        if isinstance(v, list) and len(v) >= 2:
            var_list.append((str(v[0]), v[1], bool(v[2]) if len(v) > 2 else False))
    lists = []
    for lid, L in (t.d.get("lists") or {}).items():
        if isinstance(L, list) and len(L) >= 1:
            lists.append(L[0])
    return {
        "name": t.name,
        "is_stage": t.is_stage,
        "scripts": len(tops),
        "blocks": sum(1 for b in t.blocks.values() if isinstance(b, dict) and not b.get("shadow")),
        "costumes": costumes,
        "sounds": sounds,
        "variables": sorted(var_list),
        "lists": sorted(lists),
        "top_ops": ops.most_common(8),
        "rotationStyle": t.d.get("rotationStyle"),
        "size": t.d.get("size"),
        "visible": t.d.get("visible"),
    }


def cmd_diff(sb_a, a):
    """Structural comparison between two .sb3 (or the same file twice for self-check)."""
    path_b = a.other
    sb_b = Sb3(path_b)
    as_json = getattr(a, "json", False)

    sig_a = {t.name: _target_sig(t) for t in sb_a.targets}
    sig_b = {t.name: _target_sig(t) for t in sb_b.targets}

    only_a = sorted(set(sig_a) - set(sig_b))
    only_b = sorted(set(sig_b) - set(sig_a))
    common = sorted(set(sig_a) & set(sig_b))

    diffs = []
    if only_a:
        diffs.append(f"solo in A: {', '.join(only_a)}")
    if only_b:
        diffs.append(f"solo in B: {', '.join(only_b)}")

    for name in common:
        sa, sb_ = sig_a[name], sig_b[name]
        for key in ("scripts", "blocks", "rotationStyle", "size", "visible"):
            if sa.get(key) != sb_.get(key):
                diffs.append(f"{name}.{key}: {sa.get(key)} → {sb_.get(key)}")
        if sa["costumes"] != sb_["costumes"]:
            diffs.append(f"{name}.costumes: {sa['costumes']} → {sb_['costumes']}")
        if sa["sounds"] != sb_["sounds"]:
            diffs.append(f"{name}.sounds: {sa['sounds']} → {sb_['sounds']}")
        if sa["variables"] != sb_["variables"]:
            diffs.append(f"{name}.variables differ ({len(sa['variables'])} vs {len(sb_['variables'])})")
        if sa["lists"] != sb_["lists"]:
            diffs.append(f"{name}.lists: {sa['lists']} → {sb_['lists']}")
        # opcode multiset

    # extensions
    ext_a = sorted(sb_a.extensions or [])
    ext_b = sorted(sb_b.extensions or [])
    if ext_a != ext_b:
        diffs.append(f"extensions: {ext_a} → {ext_b}")

    if as_json:
        import json as _json
        print(_json.dumps({
            "only_a": only_a, "only_b": only_b, "common": common,
            "diffs": diffs, "identical": not diffs and not only_a and not only_b,
        }, ensure_ascii=False, indent=2))
        return

    print(f"A: {sb_a.path}  ({len(sb_a.targets)} target)")
    print(f"B: {sb_b.path}  ({len(sb_b.targets)} target)")
    if not diffs and not only_a and not only_b:
        print("struttura identica ✔ (target, costumi, suoni, variabili, liste, estensioni)")
        if not getattr(a, "scripts", False):
            return
        # still may want script-level even if structure matches
    for d in diffs:
        print("  ≠", d)
    if only_a or only_b:
        print(f"  target solo A: {only_a or '—'}  |  solo B: {only_b or '—'}")

    if getattr(a, "scripts", False):
        print("\n--- script diff (pseudo-codice) ---")
        for name in common:
            ta = next(t for t in sb_a.targets if t.name == name)
            tb = next(t for t in sb_b.targets if t.name == name)
            sa = [Pseudo(ta).script_lines(top) for top in ta.scripts()]
            sb_lines = [Pseudo(tb).script_lines(top) for top in tb.scripts()]
            # normalize to text
            ta_txt = ["\n".join(x) for x in sa]
            tb_txt = ["\n".join(x) for x in sb_lines]
            if ta_txt == tb_txt:
                continue
            print(f"[{name}]")
            # simple LCS-ish: show scripts only in A / only in B / changed by index
            n = max(len(ta_txt), len(tb_txt))
            for i in range(n):
                a_s = ta_txt[i] if i < len(ta_txt) else None
                b_s = tb_txt[i] if i < len(tb_txt) else None
                if a_s == b_s:
                    continue
                if a_s and not b_s:
                    print(f"  #{i} solo in A:")
                    for ln in a_s.splitlines()[:30]:
                        print("    -", ln)
                elif b_s and not a_s:
                    print(f"  #{i} solo in B:")
                    for ln in b_s.splitlines()[:30]:
                        print("    +", ln)
                else:
                    print(f"  #{i} modificato:")
                    for ln in (a_s or "").splitlines()[:15]:
                        print("    -", ln)
                    for ln in (b_s or "").splitlines()[:15]:
                        print("    +", ln)


def _genre_hints(sb):
    """Heuristic genre / mechanics from opcodes and messages."""
    ops = Counter()
    msgs = set()
    for t in sb.targets:
        for b in t.blocks.values():
            if not isinstance(b, dict) or b.get("shadow"):
                continue
            op = b.get("opcode") or ""
            ops[op] += 1
            if op == "event_whenbroadcastreceived":
                f = (b.get("fields") or {}).get("BROADCAST_OPTION")
                if f:
                    msgs.add(str(f[0]).lower())
            if op in ("event_broadcast", "event_broadcastandwait"):
                # input may hold message
                pass
    hints = []
    if ops.get("control_create_clone_of") or ops.get("control_start_as_clone"):
        hints.append("cloni")
    if ops.get("sensing_touchingobject") or ops.get("sensing_touchingcolor"):
        hints.append("collisioni")
    if ops.get("motion_changeyby") and (ops.get("event_whenkeypressed") or ops.get("sensing_keypressed")):
        if ops.get("motion_changeyby", 0) > 5:
            hints.append("platformer/fisica-y")
    if ops.get("sensing_mousedown") or ops.get("sensing_mousex"):
        hints.append("mouse/point-and-click")
    if any(k in ops for k in ("pen_penDown", "pen_stamp")):
        hints.append("pen drawing")
    if any("music_" in k for k in ops):
        hints.append("music")
    scene_msgs = [m for m in msgs if any(x in m for x in ("start", "menu", "game", "win", "over", "level", "next", "die", "hurt", "play"))]
    if scene_msgs:
        hints.append("scene/broadcast: " + ", ".join(sorted(scene_msgs)[:6]))
    if ops.get("data_changevariableby") or ops.get("data_setvariableto"):
        hints.append("variabili di stato")
    return hints




# ====================================================================
# import — estrae uno sprite (o script) come frammento sb3_builder
# ====================================================================

def cmd_import(sb, a):
    """Emette codice Python sb3_builder per uno sprite (o script) da incollare."""
    t = sb.find_target(a.target)
    out = a.out or f"import_{slug(t.name)}.py"
    script_sel = parse_sel(a.script, len(t.scripts())) if a.script else None

    g = PyGen(sb, out, keep_loose=getattr(a, "keep_loose", False))
    # registra nomi python per TUTTI i target (scope vars) e per questo sprite
    for tt in sb.targets:
        if tt.name not in g.py:
            g.py[tt.name] = "stage" if tt.is_stage else py_ident("sp_" + tt.name, g.used)
    lines = []
    lines.append("# -*- coding: utf-8 -*-")
    lines.append(f'"""Frammento importato da {sb.path} — sprite {t.name!r}.')
    lines.append("Incolla in un build_game.py esistente (dopo p = S.Project()...).")
    lines.append('Rinomina variabili/messaggi se collidono col progetto destinazione."""')
    lines.append("import os, sys")
    lines.append("# sys.path.insert(0, '/path/to/scratch-game-dev/scripts')")
    lines.append("# import sb3_builder as S")
    lines.append("# import assets as A")
    lines.append("")
    lines.append("# --- asset di questo sprite (SVG/WAV già estratti se --extract-assets) ---")

    assets_dir = None
    if a.extract_assets:
        assets_dir = os.path.splitext(out)[0] + "_assets"
        os.makedirs(assets_dir, exist_ok=True)
        for i, c in enumerate(t.d.get("costumes") or []):
            rel = asset_relpath(t, "costume", i, c)
            data = read_asset(sb, c)
            if data is None:
                lines.append(f"# costume {c.get('name')!r}: asset non trovato nello zip")
                continue
            dest = os.path.join(assets_dir, os.path.basename(rel) if rel else f"c{i}.{c.get('dataFormat','svg')}")
            with open(dest, "wb") as f:
                f.write(data)
            lines.append(f"# costume estratto: {dest}")
        for i, s_ in enumerate(t.d.get("sounds") or []):
            rel = asset_relpath(t, "sound", i, s_)
            data = read_asset(sb, s_)
            if data is None:
                continue
            dest = os.path.join(assets_dir, os.path.basename(rel) if rel else f"s{i}.{s_.get('dataFormat','wav')}")
            with open(dest, "wb") as f:
                f.write(data)
            lines.append(f"# sound estratto: {dest}")

    lines.append("")
    pyname = g.py[t.name]
    lines.append(f"# --- sprite {t.name!r} ---")
    lines.append(f"# ASSICURATI di avere:  {pyname} = p.sprite({t.name!r})")
    lines.append(f"# e ASSETS = percorso alla cartella asset (o usa --extract-assets)")
    rot = t.d.get("rotationStyle") or "all around"
    if rot != "all around":
        lines.append(f"{pyname}.rotationStyle = {rot!r}")
    # local vars / lists
    for vid, v in (t.d.get("variables") or {}).items():
        if isinstance(v, list) and len(v) >= 2:
            cloud = ", cloud=True" if (len(v) > 2 and v[2]) else ""
            lines.append(f'# locale: p.variable({v[0]!r}, {pylit(v[1])}{cloud}, scope={t.name!r})')
    for lid, L in (t.d.get("lists") or {}).items():
        if isinstance(L, list) and L:
            lines.append(f'# lista locale: {L[0]!r}')

    # Use PyGen helpers for the sprite body
    body = []
    g.gen_assets(t, body)
    # scripts filter
    all_scripts = t.scripts()
    if script_sel is not None:
        # monkey-patch scripts temporarily
        orig = t._scripts
        t._scripts = [all_scripts[i] for i in sorted(script_sel) if i < len(all_scripts)]
        g.gen_scripts(t, body)
        t._scripts = orig
    else:
        g.gen_scripts(t, body)

    for ln in body:
        lines.append(ln if isinstance(ln, str) else render(ln))

    lines.append("")
    lines.append(f"# fine import di {t.name!r}")
    code = "\n".join(lines) + "\n"
    with open(out, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"scritto {out}  ({len(lines)} righe) — sprite {t.name!r}"
          + (f", script {sorted(script_sel)}" if script_sel is not None else " (tutti gli script)"))
    if assets_dir:
        print(f"  asset in {assets_dir}/")
    for w in g.warnings:
        print("  [warn]", w)


# ====================================================================
# explain — riassunto euristico one-screen
# ====================================================================

def cmd_explain(sb, a):
    """Riassunto automatico (guess): scene, controlli, score/lives, win/lose."""
    as_json = getattr(a, "json", False)
    ops = Counter()
    msgs_recv = defaultdict(list)  # msg -> [target]
    msgs_send = defaultdict(list)
    keys = set()
    var_writes = defaultdict(set)  # var -> {target}
    var_reads = defaultdict(set)
    backdrops = []
    for t in sb.targets:
        if t.is_stage:
            backdrops = [c.get("name", "?") for c in (t.d.get("costumes") or [])]
        for bid, b in t.blocks.items():
            if not isinstance(b, dict) or b.get("shadow"):
                continue
            op = b.get("opcode") or ""
            ops[op] += 1
            if op == "event_whenkeypressed":
                f = (b.get("fields") or {}).get("KEY_OPTION")
                if f:
                    keys.add(str(f[0]))
            if op == "sensing_keypressed":
                # KEY_OPTION is usually a menu shadow block
                inp = (b.get("inputs") or {}).get("KEY_OPTION")
                if isinstance(inp, list) and len(inp) > 1:
                    ref = inp[1] if isinstance(inp[1], str) else None
                    if ref and ref in t.blocks:
                        fld = (t.blocks[ref].get("fields") or {}).get("KEY_OPTION")
                        if fld:
                            keys.add(str(fld[0]))
            if op == "event_whenbroadcastreceived":
                f = (b.get("fields") or {}).get("BROADCAST_OPTION")
                if f:
                    msgs_recv[str(f[0])].append(t.name)
            if op in ("event_broadcast", "event_broadcastandwait"):
                # try field/input
                for iname, ival in (b.get("inputs") or {}).items():
                    if isinstance(ival, list) and len(ival) > 1 and isinstance(ival[1], list):
                        prim = ival[1]
                        if prim and prim[0] == 11:
                            msgs_send[str(prim[1])].append(t.name)
            if op in ("data_setvariableto", "data_changevariableby"):
                f = (b.get("fields") or {}).get("VARIABLE")
                if f:
                    var_writes[str(f[0])].add(t.name)
            # reads via primitive 12
            for ival in (b.get("inputs") or {}).values():
                if isinstance(ival, list) and ival and ival[0] == 1 and isinstance(ival[1], list):
                    prim = ival[1]
                    if prim and prim[0] == 12 and len(prim) > 1:
                        var_reads[str(prim[1])].add(t.name)

    # heuristic labels
    score_vars = [v for v in var_writes if re.search(r"score|punti|point", v, re.I)]
    life_vars = [v for v in var_writes if re.search(r"liv|life|hp|heart|vite", v, re.I)]
    win_msgs = [m for m in list(msgs_recv) + list(msgs_send)
                if re.search(r"win|vittoria|victory|you.?win", m, re.I)]
    lose_msgs = [m for m in list(msgs_recv) + list(msgs_send)
                 if re.search(r"lose|game.?over|morte|dead|die|sconfitta", m, re.I)]
    start_msgs = [m for m in list(msgs_recv) + list(msgs_send)
                  if re.search(r"start|play|inizio|menu|go", m, re.I)]

    genre = _genre_hints(sb)

    summary = {
        "file": sb.path,
        "targets": [t.name for t in sb.targets],
        "backdrops_as_scenes": backdrops,
        "keys": sorted(keys),
        "score_vars_guess": score_vars,
        "lives_vars_guess": life_vars,
        "win_messages_guess": sorted(set(win_msgs)),
        "lose_messages_guess": sorted(set(lose_msgs)),
        "start_messages_guess": sorted(set(start_msgs)),
        "broadcasts": sorted(set(list(msgs_recv) + list(msgs_send))),
        "mechanics_guess": genre,
        "extensions": list(sb.extensions or []),
        "note": "tutto euristico — verifica con tree/flow/show",
    }

    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    print(f"EXPLAIN  {sb.path}  (guess — non affidarti ciecamente)")
    print(f"TARGET   {', '.join(summary['targets'])}")
    if backdrops:
        print(f"SCENE    backdrop: {', '.join(backdrops)}")
    if keys:
        print(f"CONTROLLI tasti: {', '.join(sorted(keys))}")
    else:
        # mouse?
        if ops.get("sensing_mousedown") or ops.get("sensing_mousex"):
            print("CONTROLLI mouse (mousedown/x/y rilevati)")
        else:
            print("CONTROLLI (nessun event_whenkeypressed — guarda sensing_keypressed o click)")
    if score_vars:
        print(f"SCORE    variabili candidate: {', '.join(score_vars)}")
    if life_vars:
        print(f"VITE     variabili candidate: {', '.join(life_vars)}")
    if start_msgs:
        print(f"START    messaggi: {', '.join(sorted(set(start_msgs)))}")
    if win_msgs:
        print(f"WIN      messaggi: {', '.join(sorted(set(win_msgs)))}")
    if lose_msgs:
        print(f"LOSE     messaggi: {', '.join(sorted(set(lose_msgs)))}")
    if genre:
        print(f"MECCANICHE {' | '.join(genre)}")
    if sb.extensions:
        print(f"EXT      {', '.join(sb.extensions)}")
    print("\nVerifica con: tree | flow | show <sprite> -s N")



def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(
        description="Reverse engineering di .sb3 senza leggere project.json",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("info", help="panoramica compatta")
    p.add_argument("file")
    p = sub.add_parser("tree", help="script numerati per target")
    p.add_argument("file")
    p.add_argument("target", nargs="?")
    p = sub.add_parser("show", help="pseudo-codice")
    p.add_argument("file")
    p.add_argument("target", nargs="?")
    p.add_argument("-s", "--script", help="indici script, es. 0,2,4-6")
    p.add_argument("--max-lines", type=int, default=200)
    p = sub.add_parser("flow", help="broadcast / variabili / custom block / cloni")
    p.add_argument("file")
    p = sub.add_parser("find", help="cerca testo/opcode/variabile/messaggio")
    p.add_argument("file")
    p.add_argument("query")
    p.add_argument("--regex", action="store_true")
    p.add_argument("--limit", type=int, default=40)
    p = sub.add_parser("assets", help="elenca/estrae costumi e suoni")
    p.add_argument("file")
    p.add_argument("-o", "--out")
    p = sub.add_parser("to-python", help="genera uno script sb3_builder equivalente")
    p.add_argument("file")
    p.add_argument("-o", "--out")
    p.add_argument("--build", action="store_true", help="esegue, valida e confronta")
    p.add_argument("--keep-loose", action="store_true", help="includi stack senza hat")

    p = sub.add_parser("diff", help="confronto strutturale tra due .sb3")
    p.add_argument("file")
    p.add_argument("other")
    p.add_argument("--json", action="store_true")
    p.add_argument("--scripts", action="store_true",
                   help="mostra anche pseudo-codice degli script diversi")

    p = sub.add_parser("import", help="estrae uno sprite come frammento sb3_builder")
    p.add_argument("file")
    p.add_argument("target", help="nome sprite da importare")
    p.add_argument("-o", "--out")
    p.add_argument("-s", "--script", help="solo certi script, es. 0,2,4-6")
    p.add_argument("--extract-assets", action="store_true",
                   help="estrae costumi/suoni in <out>_assets/")
    p.add_argument("--keep-loose", action="store_true")

    p = sub.add_parser("explain", help="riassunto euristico one-screen (guess)")
    p.add_argument("file")
    p.add_argument("--json", action="store_true")

    a = ap.parse_args()

    if a.cmd == "diff":
        sb = Sb3(a.file)
        cmd_diff(sb, a)
        return

    sb = Sb3(a.file)
    dispatch = {
        "info": cmd_info, "tree": cmd_tree, "show": cmd_show, "flow": cmd_flow,
        "find": cmd_find, "assets": cmd_assets, "to-python": cmd_to_python,
        "import": cmd_import, "explain": cmd_explain,
    }
    dispatch[a.cmd](sb, a)


if __name__ == "__main__":
    main()
