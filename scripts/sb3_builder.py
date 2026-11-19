# -*- coding: utf-8 -*-
"""
sb3_builder.py — Build valid Scratch 3 (.sb3) projects entirely from Python.

The .sb3 format is a ZIP containing project.json + asset files (md5ext names).
Format constants are derived from scratch-vm source:
  https://github.com/scratchfoundation/scratch-vm/blob/develop/src/serialization/sb3.js

Quick usage:
    import sys; sys.path.insert(0, "<skill>/scripts")
    import sb3_builder as S

    p = S.Project()
    stage = p.stage
    stage.costume(S.svg_backdrop("#0f2d5c", "#1a4a8a"), name="bg")
    player = p.sprite("Player")
    player.costume(S.svg_ship("#ffcc00"), name="player")
    player.script(
        S.blk("event_whenflagclicked"),
        S.blk("control_forever", SUBSTACK=S.seq(
            S.blk("motion_movesteps", STEPS=S.v(4)),
            S.blk("motion_ifonedgebounce"),
        )),
    )
    p.build("game.sb3")

Rules encoded by this builder (from sb3.js):
  INPUT_SAME_BLOCK_SHADOW = 1  -> [1, primitive] or [1, menuId]
  INPUT_BLOCK_NO_SHADOW   = 2  -> [2, blockId]  (boolean/reporter/substack)
  INPUT_DIFF_BLOCK_SHADOW = 3  -> [3, shadowId, blockId]
  Primitives: 4=math_number 5=positive 6=whole 7=integer 8=angle 9=colour
              10=text 11=broadcast_menu 12=variable 13=list
"""

import json
import zipfile
import hashlib
import io
import uuid
import os
import re

# ---------------------------------------------------------------- constants

# Exact set from scratch-vm sb3.js CORE_EXTENSIONS. NOTE: opcode prefixes
# are SINGULAR (event_whenflagclicked, operator_add). The plural forms
# (events_*, operators_*) are typos that TurboWarp rejects as unknown extensions.
CORE_EXTENSIONS = {
    "argument", "colour", "control", "data", "event", "looks",
    "math", "motion", "operator", "procedures", "sensing", "sound",
}

# Extension ids known to exist in Scratch / TurboWarp / PenguinMod runtimes.
# Any other prefix found in opcodes is added as an explicit extension id
# (needed for TurboWarp/PenguinMod community extensions).
KNOWN_EXTENSIONS = {
    "pen", "music", "videoSensing", "text2speech", "translate", "makeymakey",
    "microbit", "ev3", "boost", "wedo2", "gdxfor", "speech2text",
    "tw", "tw_files", "procedures_enable_return",
    # TurboWarp gallery
    "box2d", "gamepad", "pointerlock", "runtime-options", "stretch", "text",
    "utilities", "bitwise", "clipboard", "cursor", "encoding", "fetch",
    "files", "iframe", "itchio", "local-storage", "navigator", "penplus",
    "sound", "battery", "clouddata-ping", "cloudlink", "gamejolt",
    "steamworks", "numerical-encoding-2", "ar",
    # PenguinMod built-ins (game-relevant subset; full list in references/extensions.md)
    "pm_camera", "pm_controlsExpansion", "pm_eventsExpansion",
    "pm_inlineblocks", "pm_motionExpansion", "pm_operatorsExpansion",
    "pm_sensingExpansion", "jg_3d", "jg_animation", "jg_audio",
    "jg_clones", "jg_debugging", "jg_easySave", "jg_files", "jg_json",
    "jg_pathfinding", "jg_runtime", "jg_scripts", "jg_storage", "jg_timers",
    "jg_tween", "gameutils", "gsa_canvas", "gsa_colorUtilBlocks",
    "gsa_objectVars", "gsa_tempVars", "jwArray", "jwColor", "jwDate",
    "jwLambda", "jwNum", "jwPointer", "jwStorage", "jwTargets", "jwVector",
    "jwXML", "iyg_perlin_noise", "lily_tempVars2",
    "xeltalliv_clippingblending", "theshovel_canvasEffects",
    "theshovel_colorPicker", "theshovel_customStyles", "theshovel_lzString",
    "sp_javascriptV2", "dt_cameracontrols", "fr_3d",
}

# Blocks that terminate a script (no `next` allowed).
CAP_BLOCKS = {"control_stop", "control_delete_this_clone"}

# Hat blocks start scripts.
HAT_BLOCKS = {
    "event_whenflagclicked", "event_whenkeypressed",
    "event_whenbroadcastreceived", "event_whenstageclicked",
    "event_whenthisspriteclicked", "event_whenbackdropswitchesto",
    "event_whengreaterthan", "event_whentouchingobject",
    "control_start_as_clone", "procedures_definition",
}

VALID_ROTATION_STYLES = {"all around", "left-right", "don't rotate"}


class BuilderError(Exception):
    pass


def _uid():
    return uuid.uuid4().hex[:20]


# ---------------------------------------------------------------- primitives

def v(x):
    """math_number primitive (float/any number)."""
    return [4, str(x)]


def pos(x):
    """math_positive_number primitive."""
    return [5, str(x)]


def whole(x):
    """math_whole_number primitive (integer >= 0)."""
    return [6, str(int(x))]


def integer(x):
    """math_integer primitive."""
    return [7, str(int(x))]


def angle(x):
    """math_angle primitive (0-360)."""
    return [8, str(x)]


def color(hexstr):
    """colour_picker primitive ('#aabbcc')."""
    if not re.match(r"^#[0-9a-fA-F]{6}$", hexstr):
        raise BuilderError(f"colore non valido: {hexstr!r} (usa '#rrggbb')")
    return [9, hexstr]


def s(text):
    """text primitive."""
    return [10, str(text)]


# ---------------------------------------------------------------- blocks

class Block:
    def __init__(self, opcode, inputs=None, fields=None, mutation=None,
                 shadow=False):
        self.opcode = opcode
        self.inputs = dict(inputs or {})
        self.fields = dict(fields or {})
        self.mutation = dict(mutation) if mutation else None
        self.shadow = shadow
        self.id = _uid()
        self.next = None
        self._next_obj = None
        self.parent = None
        self.topLevel = False
        self.x = None
        self.y = None
        self._used = False

    def serialize(self):
        obj = {
            "opcode": self.opcode,
            "next": self.next,
            "parent": self.parent,
            "inputs": self.inputs,
            "fields": self.fields,
            "shadow": self.shadow,
            "topLevel": self.topLevel,
        }
        if self.topLevel:
            obj["x"] = self.x if self.x is not None else 48
            obj["y"] = self.y if self.y is not None else 48
        if self.mutation is not None:
            mut = {"tagName": "mutation", "children": []}
            mut.update(self.mutation)
            obj["mutation"] = mut
        return obj


class Seq:
    """A chain of blocks used as a stack input (SUBSTACK / SUBSTACK2)."""
    def __init__(self, *blocks):
        self.blocks = []
        for b in blocks:
            if isinstance(b, Seq):
                self.blocks.extend(b.blocks)
            elif isinstance(b, Block):
                self.blocks.append(b)
            elif b is None:
                continue
            else:
                raise BuilderError(f"Seq accetta solo Block/Seq, trovato {b!r}")
        if not self.blocks:
            raise BuilderError("Seq vuota: metti almeno un blocco dentro S.seq(...)")
        for i, b in enumerate(self.blocks):
            if i + 1 < len(self.blocks):
                b.next = self.blocks[i + 1].id
                b._next_obj = self.blocks[i + 1]
                self.blocks[i + 1].parent = b.id
            else:
                b.next = None
                b._next_obj = None


class CustomBlock:
    """Handle for a user-defined custom block (procedures)."""
    def __init__(self, sprite, proccode, args, returns, warp):
        self.sprite = sprite
        self.proccode = proccode
        self.returns = returns
        self.argids = [str(_uid()) for _ in args]
        self.argnames = [a[0] for a in args]
        self.argdefaults = [a[1] for a in args]
        self.warp = "true" if warp else "false"
        self.hat = sprite._add_custom_definition(self)

    def mutation(self):
        mut = {
            "proccode": self.proccode,
            "argumentids": json.dumps(self.argids),
            "argumentnames": json.dumps(self.argnames),
            "argumentdefaults": json.dumps(self.argdefaults),
            "warp": self.warp,
        }
        if self.returns:
            mut["return"] = "true"
        return mut


def blk(opcode, **kwargs):
    """Create a block.

    Named kwargs are treated as INPUTS when their value is a primitive
    ([4,'10'], [10,'hi']...), a Block, or a Seq — e.g.
        S.blk('motion_sety', Y=S.v(100))
    FIELD values (dropdowns, variable refs like ['score', vid]) must be
    passed explicitly via fields={...}.
    """
    inputs = kwargs.pop("inputs", None) or {}
    fields = kwargs.pop("fields", None) or {}
    mutation = kwargs.pop("mutation", None)
    shadow = kwargs.pop("shadow", False)
    for name, val in kwargs.items():
        is_primitive = (isinstance(val, (list, tuple)) and val
                        and isinstance(val[0], int))
        if not (is_primitive or isinstance(val, (Block, Seq))):
            raise BuilderError(
                f"{opcode}: il kwarg {name}={val!r} non è un input valido. "
                f"I campi (menu/variabili) vanno passati via fields={{...}}"
            )
        inputs[name] = val
    return Block(opcode, inputs, fields, mutation, shadow)


def menu(opcode, fields):
    """Create a menu shadow block.
    Plain field values are wrapped as [value, None] (sb3 field form), e.g.
    S.menu('sensing_keyoptions', {'KEY_OPTION': 'space'})."""
    if not opcode.endswith("menu") and opcode not in (
        "looks_costume", "looks_backdrops", "sound_sounds_menu",
        "sensing_keyoptions", "music_menu_DRUM", "music_menu_INSTRUMENT",
        "videoSensing_menu_VIDEO_STATE", "sensing_of_object_menu",
        "event_touchingobjectmenu",
    ):
        raise BuilderError(
            f"{opcode!r} non sembra un menu (opcode di menu finiscono per 'menu' "
            f"o sono noti). Controlla il catalogo opcodes."
        )
    norm = {}
    for k, val in fields.items():
        norm[k] = [val, None] if not isinstance(val, (list, tuple)) else list(val)
    return Block(opcode, {}, norm, None, shadow=True)


def seq(*blocks):
    return Seq(*blocks)


def stop(option="all"):
    """control_stop with proper mutation (cap block)."""
    if option not in ("all", "this script", "other scripts in sprite"):
        raise BuilderError(f"stop option non valida: {option!r}")
    hasnext = "true" if option == "other scripts in sprite" else "false"
    return blk("control_stop",
               fields={"STOP_OPTION": [option, None]},
               mutation={"hasnext": hasnext})


def set_effect(effect, value):
    """looks_seteffectto (EFFECT field): ghost/color/brightness/fisheye/mosaic."""
    return blk("looks_seteffectto", fields={"EFFECT": [effect, None]},
               VALUE=value)


def change_effect(effect, change):
    return blk("looks_changeeffectby", fields={"EFFECT": [effect, None]},
               CHANGE=change)


def play_sound(name):
    """sound_play with the sound menu shadow."""
    return blk("sound_play", SOUND_MENU=menu("sound_sounds_menu",
                                             {"SOUND_MENU": name}))


# ---------------------------------------------------------------- target

class Target:
    def __init__(self, project, name, is_stage=False):
        self.project = project
        self.name = name
        self.is_stage = is_stage
        self.variables = {}   # id -> [name, value] (+ True cloud)
        self.lists = {}       # id -> [name, [items]]
        self.broadcasts = {}  # id -> name
        self.blocks = {}      # id -> Block
        self.comments = {}
        self.currentCostume = 0
        self.costumes = []
        self.sounds = []
        self.volume = 100
        self.layerOrder = 0 if is_stage else None
        # sprite-only
        self.visible = True
        self.x = 0
        self.y = 0
        self.size = 100
        self.direction = 90
        self.draggable = False
        self.rotationStyle = "all around"

    # ---- assets -------------------------------------------------
    def costume(self, data, name=None, rotation_center=(0, 0),
                bitmap_resolution=1):
        """Add a costume. data = SVG string, PNG bytes, or a path to a file."""
        if isinstance(data, (str, bytes)) and os.path.exists(str(data)):
            with open(str(data), "rb") as f:
                data = f.read()
        if isinstance(data, str):
            data = data.encode("utf-8")
            fmt = "svg"
        elif isinstance(data, bytes):
            fmt = "png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "svg"
        else:
            raise BuilderError("costume: passa una stringa SVG, PNG bytes o un path")
        if fmt == "svg":
            ext, res = "svg", bitmap_resolution
        else:
            ext, res = "png", bitmap_resolution
        md5 = hashlib.md5(data).hexdigest()
        entry = {
            "name": name or f"{self.name}{len(self.costumes) + 1}",
            "assetId": md5,
            "md5ext": f"{md5}.{ext}",
            "dataFormat": fmt,
            "bitmapResolution": res,
            "rotationCenterX": rotation_center[0],
            "rotationCenterY": rotation_center[1],
        }
        self.costumes.append((entry, data))
        return len(self.costumes) - 1

    def sound(self, data, name=None, rate=44100):
        """Add a sound from WAV bytes or a file path."""
        if isinstance(data, str) and os.path.exists(data):
            with open(data, "rb") as f:
                data = f.read()
        if not isinstance(data, bytes):
            raise BuilderError("sound: passa bytes WAV o un path")
        md5 = hashlib.md5(data).hexdigest()
        # parse wav header for sampleCount
        sample_count = 0
        if data[:4] == b"RIFF":
            i = 12
            while i + 8 <= len(data):
                cid = data[i:i + 4]
                csize = int.from_bytes(data[i + 4:i + 8], "little")
                if cid == b"data":
                    sample_count = csize // 2  # 16-bit mono
                    break
                i += 8 + csize + (csize % 2)
        entry = {
            "name": name or f"sound{len(self.sounds) + 1}",
            "assetId": md5,
            "md5ext": f"{md5}.wav",
            "dataFormat": "wav",
            "format": "",
            "rate": rate,
            "sampleCount": sample_count,
        }
        self.sounds.append((entry, data))
        return len(self.sounds) - 1

    # ---- variables / broadcasts ---------------------------------
    def variable(self, name, value=0, cloud=False):
        """Declare a sprite-local variable (use p.variable for global)."""
        vid = self.project._var_id(self, name)
        extra = [value] + ([True] if cloud else [])
        self.variables[vid] = [name] + list(extra)
        return vid

    def list(self, name, items=None):
        lid = self.project._list_id(self, name)
        self.lists[lid] = [name, list(items or [])]
        return lid

    def broadcast(self, name):
        return self.project._broadcast_id(name)

    # ---- scripts -------------------------------------------------
    def script(self, *blocks, x=48, y=None):
        """Add a script (a hat block followed by stacked blocks)."""
        if not blocks:
            raise BuilderError(f"script vuoto in {self.name}")
        y = y if y is not None else self.project._next_script_y()
        chain = self._chain(blocks, "script")
        head = chain[0]
        if head.opcode not in HAT_BLOCKS and head.opcode != "procedures_definition":
            raise BuilderError(
                f"il primo blocco di uno script deve essere un hat block "
                f"(events_whenflagclicked, events_whenkeypressed, "
                f"events_whenbroadcastreceived, control_start_as_clone, "
                f"events_whenthisspriteclicked, ...), non {head.opcode!r}"
            )
        head.topLevel = True
        head.x, head.y = x, y
        self._register(head)
        return head

    def script_at(self, block_or_seq):
        """Register an already-built top-level block (advanced)."""
        head = block_or_seq
        head.topLevel = True
        self._register(head)
        return head

    # ---- custom blocks -------------------------------------------
    def custom_block(self, proccode, args=(), returns=False, warp=True):
        """args: list of (NAME, default) tuples. returns=True = TurboWarp reporter."""
        return CustomBlock(self, proccode, list(args), returns, warp)

    def call(self, custom_block, **arg_values):
        """Create a procedures_call block (delegates to Project.call)."""
        return self.project.call(custom_block, **arg_values)

    def _add_custom_definition(self, cb):
        mutation = {
            "proccode": cb.proccode,
            "argumentids": json.dumps(cb.argids),
            "argumentnames": json.dumps(cb.argnames),
            "argumentdefaults": json.dumps(cb.argdefaults),
            "warp": cb.warp,
        }
        if cb.returns:
            mutation["return"] = "true"
        proto = Block("procedures_prototype", {}, {}, mutation, shadow=True)
        definition = blk("procedures_definition",
                         inputs={"custom_block": [1, proto]})
        cb.definition = definition
        return definition

    # ---- internal --------------------------------------------------
    def _chain(self, blocks, ctx):
        chain = []
        for b in blocks:
            if isinstance(b, Seq):
                chain.extend(b.blocks)
            elif isinstance(b, Block):
                chain.append(b)
            else:
                raise BuilderError(f"{ctx}: elemento non valido {b!r}")
        if not chain:
            raise BuilderError(f"{ctx}: nessun blocco")
        for i, b in enumerate(chain):
            if i + 1 < len(chain):
                b.next = chain[i + 1].id
                b._next_obj = chain[i + 1]
                chain[i + 1].parent = b.id
            else:
                b.next = None
                b._next_obj = None
            if b.opcode in CAP_BLOCKS and b.next:
                raise BuilderError(
                    f"{b.opcode} è un cap block (non può avere blocchi sotto di sé)"
                )
        return chain

    def _register(self, block):
        """Register a block + convert its inputs to serialized sb3 form."""
        if block.id in self.blocks:
            return
        self.blocks[block.id] = block
        for name in list(block.inputs.keys()):
            val = block.inputs[name]
            block.inputs[name] = self._serialize_input(block, val)
        if getattr(block, "_next_obj", None) is not None:
            self._register(block._next_obj)

    def _serialize_input(self, owner, val):
        """Convert a Python-side input value into sb3 serialized form.

        primitive [4,'10']      -> [1, [4,'10']]
        menu Block (shadow)     -> [1, menuId]
        reporter Block          -> [2, blockId]
        Seq (substack)          -> [2, firstBlockId]
        already-serialized list -> passthrough
        """
        if isinstance(val, (list, tuple)):
            if len(val) >= 2 and isinstance(val[0], int):
                if val[0] in (1, 2, 3):
                    # già nella forma sb3 [type, ...]
                    if val[0] == 1 and isinstance(val[1], Block):
                        m = val[1]
                        if not m.shadow:
                            raise BuilderError(
                                f"input [1, block] richiede un menu shadow, "
                                f"trovato {m.opcode}"
                            )
                        m.parent = owner.id
                        self.blocks[m.id] = m
                        return [1, m.id]
                    return list(val)
                # primitive compresse (4..13) → wrap [1, primitive]
                return [1, list(val)]
            raise BuilderError(f"input non riconosciuto: {val!r}")
        if isinstance(val, Block):
            self._check_reuse(val)
            val.parent = owner.id
            if val.shadow:
                self.blocks[val.id] = val
                return [1, val.id]
            self._register(val)
            return [2, val.id]
        if isinstance(val, Seq):
            first = val.blocks[0]
            self._check_reuse(first)
            first.parent = owner.id
            self._register(first)
            return [2, first.id]
        raise BuilderError(
            f"input non riconosciuto: {val!r}. Usa S.v(), S.s(), S.var(), "
            f"un Block, o S.seq(...) per gli input SUBSTACK."
        )

    def _check_reuse(self, b):
        if getattr(b, "_used", False):
            raise BuilderError(
                f"il blocco {b.opcode} è usato in più input: creane una "
                f"copia per ogni uso"
            )
        b._used = True


# ---------------------------------------------------------------- project

class Project:
    def __init__(self):
        self.stage = Target(self, "Stage", is_stage=True)
        self.sprites = []
        self.monitors = []
        self.extensions = set()
        self._script_count = 0
        self._var_ids = {}     # (owner_name, name) -> id
        self._list_ids = {}
        self._broadcast_ids = {}

    # ---- targets -------------------------------------------------
    def sprite(self, name, x=0, y=0, size=100, direction=90, visible=True,
               rotationStyle="all around", draggable=False):
        if name in (t.name for t in [self.stage] + self.sprites):
            raise BuilderError(f"target duplicato: {name}")
        if not name or name == "Stage":
            raise BuilderError("nome sprite non valido")
        if rotationStyle not in VALID_ROTATION_STYLES:
            raise BuilderError(
                f"rotationStyle non valido: {rotationStyle!r} "
                f"(valori: {sorted(VALID_ROTATION_STYLES)})")
        t = Target(self, name)
        t.x, t.y, t.size, t.direction, t.visible = x, y, size, direction, visible
        t.rotationStyle, t.draggable = rotationStyle, draggable
        t.layerOrder = len(self.sprites) + 1
        self.sprites.append(t)
        return t

    # ---- global data ----------------------------------------------
    def variable(self, name, value=0, cloud=False):
        vid = self._var_id(self.stage, name)
        entry = [name, value] + ([True] if cloud else [])
        self.stage.variables[vid] = entry
        return vid

    def list(self, name, items=None):
        lid = self._list_id(self.stage, name)
        self.stage.lists[lid] = [name, list(items or [])]
        return lid

    def broadcast(self, name):
        return self._broadcast_id(name)

    def monitor(self, name, mode="default", x=5, y=5, visible=True):
        """Show a monitor for a variable. mode: default/large/slider."""
        vid = self._var_id(self.stage, name)
        self.monitors.append({
            "id": vid, "mode": mode, "opcode": "data_variable",
            "params": {"VARIABLE": name}, "spriteName": None, "value": 0,
            "width": 0, "height": 0, "x": x, "y": y, "visible": visible,
            "sliderMin": 0, "sliderMax": 100, "isDiscrete": True,
        })

    def use_extension(self, ext_id):
        self.extensions.add(ext_id)

    # ---- lookups used by helpers -----------------------------------
    def var(self, name, scope=None):
        """Return a data_variable primitive [12, name, id].
        scope: Target for sprite-local variables, None = global."""
        owner = scope if scope is not None else self.stage
        key = (owner.name, name)
        if key not in self._var_ids:
            owner.variable(name, 0)
        vid = self._var_ids[key]
        return [12, name, vid]

    def listref(self, name, scope=None):
        owner = scope if scope is not None else self.stage
        key = (owner.name, name)
        if key not in self._list_ids:
            owner.list(name)
        lid = self._list_ids[key]
        return [13, name, lid]

    def broadcast_ref(self, name):
        bid = self._broadcast_id(name)
        return [11, name, bid]

    # ---- internal ---------------------------------------------------
    def _next_script_y(self):
        y = 48 + self._script_count * 300
        self._script_count += 1
        return y

    def _var_id(self, owner, name):
        key = (owner.name, name)
        if key not in self._var_ids:
            self._var_ids[key] = str(_uid())
        return self._var_ids[key]

    def _list_id(self, owner, name):
        key = (owner.name, name)
        if key not in self._list_ids:
            self._list_ids[key] = str(_uid())
        return self._list_ids[key]

    def _broadcast_id(self, name):
        if name not in self._broadcast_ids:
            bid = str(_uid())
            self._broadcast_ids[name] = bid
            # i broadcast DEVONO essere dichiarati nello Stage, altrimenti i
            # ricevitori non partono (verificato nel runtime TurboWarp)
            self.stage.broadcasts[bid] = name
        return self._broadcast_ids[name]

    def _add_custom_definition(self, cb):
        mutation = {
            "proccode": cb.proccode,
            "argumentids": json.dumps(cb.argids),
            "argumentnames": json.dumps(cb.argnames),
            "argumentdefaults": json.dumps(cb.argdefaults),
            "warp": cb.warp,
        }
        if cb.returns:
            mutation["return"] = "true"
        proto = Block("procedures_prototype", {}, {}, mutation, shadow=True)
        definition = blk("procedures_definition",
                         inputs={"custom_block": [1, proto]})
        cb.definition = definition
        return definition

    def call(self, custom_block, **arg_values):
        """Create a procedures_call block for a CustomBlock handle.
        NOTE (from TurboWarp scratch3_procedures.js): call input keys are the
        ARGUMENT IDS, not the names, and reporter-calls need mutation.return."""
        inputs = {}
        for i, argname in enumerate(custom_block.argnames):
            if argname not in arg_values:
                raise BuilderError(
                    f"call {custom_block.proccode!r}: manca l'argomento {argname!r}"
                )
            inputs[custom_block.argids[i]] = arg_values[argname]
            del arg_values[argname]
        if arg_values:
            raise BuilderError(
                f"call {custom_block.proccode!r}: argomenti inattesi "
                f"{list(arg_values)}"
            )
        mut = {
            "proccode": custom_block.proccode,
            "argumentids": json.dumps(custom_block.argids),
            "warp": custom_block.warp,
        }
        if custom_block.returns:
            mut["return"] = "true"
        return blk("procedures_call", inputs=inputs, mutation=mut)

    def broadcast_receive(self, name):
        """Hat block: when I receive <name>."""
        bid = self._broadcast_id(name)
        return blk("event_whenbroadcastreceived",
                   fields={"BROADCAST_OPTION": [name, bid]})

    def broadcast_send(self, name, and_wait=False):
        """event_broadcast / event_broadcastandwait block."""
        opcode = "event_broadcastandwait" if and_wait else "event_broadcast"
        ref = self.broadcast_ref(name)
        return blk(opcode, inputs={"BROADCAST_INPUT": [1, ref]})

    # ---- helpers that live on Project for discoverability ------------
    def touching_menu(self, what):
        """Menu input for sensing_touchingobject ('_edge_', '_mouse_' or sprite)."""
        return menu("sensing_touchingobjectmenu", {"TOUCHINGOBJECTMENU": what})

    def build(self, path):
        """Serialize and write the .sb3 zip. Returns project.json dict."""
        # ---- serialize all targets
        for t in [self.stage] + self.sprites:
            if not t.costumes:
                raise BuilderError(
                    f"target {t.name!r} non ha costume: usa .costume(...) "
                    f"(asset.py ha generatori pronti)"
                )
        if self.stage.layerOrder != 0:
            self.stage.layerOrder = 0
        for i, sp in enumerate(self.sprites):
            sp.layerOrder = i + 1

        serialized = []
        for t in [self.stage] + self.sprites:
            for b in t.blocks.values():
                if b.parent is None and not b.topLevel and not b.shadow:
                    raise BuilderError(
                        f"blocco orfano {b.opcode} ({b.id}) in {t.name}: "
                        f"non è collegato a nessuno script"
                    )
            blocks_out = {bid: b.serialize() for bid, b in t.blocks.items()}
            base = {
                "isStage": t.is_stage,
                "name": t.name,
                "variables": t.variables,
                "lists": t.lists,
                "broadcasts": t.broadcasts,
                "blocks": blocks_out,
                "comments": t.comments,
                "currentCostume": t.currentCostume,
                "costumes": [e for e, _ in t.costumes],
                "sounds": [e for e, _ in t.sounds],
                "volume": t.volume,
                "layerOrder": t.layerOrder,
            }
            if t.is_stage:
                base.update({
                    "tempo": 60, "videoTransparency": 50,
                    "videoState": "on", "textToSpeechLanguage": None,
                })
            else:
                base.update({
                    "visible": t.visible, "x": t.x, "y": t.y, "size": t.size,
                    "direction": t.direction, "draggable": t.draggable,
                    "rotationStyle": t.rotationStyle,
                })
            serialized.append(base)

        project = {
            "targets": serialized,
            "monitors": self.monitors,
            "extensions": sorted(self.extensions),
            "meta": {
                "semver": "3.0.0",
                "vm": "2.3.4",
                "agent": "ZCode sb3_builder",
            },
        }

        # ---- detect extensions from opcodes (same rule as scratch-vm sb3.js)
        for t in [self.stage] + self.sprites:
            for b in t.blocks.values():
                prefix = b.opcode.split("_", 1)[0]
                if prefix in CORE_EXTENSIONS:
                    continue
                if prefix in KNOWN_EXTENSIONS:
                    self.extensions.add(prefix)
                else:
                    # try 2-segment prefix (ids like jg_3d, pm_motionExpansion)
                    parts = b.opcode.split("_", 2)
                    two = "_".join(parts[:2]) if len(parts) >= 2 else prefix
                    if two in KNOWN_EXTENSIONS:
                        self.extensions.add(two)
                    else:
                        self.extensions.add(prefix)
        for m in self.monitors:
            if m["opcode"] == "data_variable":
                continue
            prefix = m["opcode"].split("_", 1)[0]
            if prefix not in CORE_EXTENSIONS:
                self.extensions.add(prefix)

        project["extensions"] = sorted(self.extensions)

        # ---- write zip
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("project.json", json.dumps(project, ensure_ascii=False))
            for t in [self.stage] + self.sprites:
                for entry, data in t.costumes:
                    zf.writestr(entry["md5ext"], data)
                for entry, data in t.sounds:
                    zf.writestr(entry["md5ext"], data)
        return project


# ---------------------------------------------------------------- helpers
# Frequent composite inputs (kept tiny so games stay readable).

def key_pressed(key_name):
    """sensing_keypressed boolean block; menu shadow sensing_keyoptions."""
    return blk("sensing_keypressed",
               inputs={"KEY_OPTION": menu("sensing_keyoptions",
                                          {"KEY_OPTION": key_name})})


def mouse_down():
    return blk("sensing_mousedown")


def touching(what):
    return blk("sensing_touchingobject",
               inputs={"TOUCHINGOBJECTMENU": menu(
                   "sensing_touchingobjectmenu", {"TOUCHINGOBJECTMENU": what})})


def touching_color(hexstr):
    return blk("sensing_touchingcolor", inputs={"COLOR": color(hexstr)})


def random(a, b):
    return blk("operator_random", inputs={"FROM": v(a), "TO": v(b)})


def gt(a, b):
    return blk("operator_gt", inputs={"OPERAND1": a, "OPERAND2": b})


def lt(a, b):
    return blk("operator_lt", inputs={"OPERAND1": a, "OPERAND2": b})


def equals(a, b):
    return blk("operator_equals", inputs={"OPERAND1": a, "OPERAND2": b})


def when_flag():
    return blk("event_whenflagclicked")


def when_key(key_name):
    # event_whenkeypressed's KEY_OPTION is a FIELD (no menu shadow),
    # verified from scratch-blocks field_dropdown + real sb3 fixtures
    return blk("event_whenkeypressed", fields={"KEY_OPTION": [key_name, None]})


def start_as_clone():
    return blk("control_start_as_clone")


def arg(name):
    """argument_reporter_string_number: use inside a custom block body."""
    return blk("argument_reporter_string_number", fields={"VALUE": [name, None]})


def arg_bool(name):
    """argument_reporter_boolean: use inside a custom block body."""
    return blk("argument_reporter_boolean", fields={"VALUE": [name, None]})
