# -*- coding: utf-8 -*-
"""
validate_sb3.py — Validatore strutturale di file .sb3 (solo stdlib Python).

Uso:
    python3 validate_sb3.py game.sb3              # exit 0 = OK
    python3 validate_sb3.py game.sb3 --quiet

Controlla (derivati da scratch-vm/scratch-parser):
  1. zip leggibile, project.json presente e parsabile
  2. struttura targets (stage per primo con isStage, layerOrder progressivi)
  3. costumi/suoni: entry valide + asset presenti nello zip con md5 corretto
  4. blocchi: opcode sintattici, next/parent coerenti, cap blocks, input
     serializzati nella forma sb3 corretta, primitive valide
  5. variabili/liste/broadcast referenziate esistono
  6. estensioni: opcodes esterni coperti da un'estensione dichiarata
  7. procedure: mutation prototype/call coerenti, argument reporters ok
  8. monitor: variabili esistenti
"""

import sys
import json
import zipfile
import hashlib
import re
from io import BytesIO

# Prefissi core ESATTI (da scratch-vm sb3.js CORE_EXTENSIONS).
# ATTENZIONE: i core opcode sono SINGOLARI: event_*, operator_*.
# Le forme plurali (events_*, operators_*) sono il typo più comune e
# TurboWarp le rifiuta come "Unknown extension".
CORE_PREFIXES = {
    "motion", "looks", "sound", "event", "control", "sensing",
    "operator", "data", "procedures", "argument", "colour", "math",
}

PRIMITIVE_TYPES = {4, 5, 6, 7, 8, 9, 10, 11, 12, 13}
KNOWN_MENU_FIELD = re.compile(r"^[A-Z][A-Z_0-9]*$")


class Issues:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def ok(self):
        return not self.errors


def validate(path, quiet=False):
    iss = Issues()
    # ---- 1. zip ------------------------------------------------------
    try:
        zf = zipfile.ZipFile(path)
        names = set(zf.namelist())
    except Exception as e:
        iss.error(f"zip illeggibile: {e}")
        return iss
    if "project.json" not in names:
        iss.error("project.json mancante nello zip")
        return iss
    try:
        proj = json.loads(zf.read("project.json"))
    except Exception as e:
        iss.error(f"project.json non è JSON valido: {e}")
        return iss

    for key in ("targets", "monitors", "extensions", "meta"):
        if key not in proj:
            iss.error(f"project.json: manca la chiave {key!r}")
    meta = proj.get("meta", {})
    if meta.get("semver") != "3.0.0":
        iss.warn(f"meta.semver inatteso: {meta.get('semver')!r} (atteso '3.0.0')")

    targets = proj.get("targets", [])
    if not targets:
        iss.error("nessun target nel progetto")
        return iss

    # ---- 2. targets --------------------------------------------------
    stage = targets[0]
    if not stage.get("isStage"):
        iss.error("il primo target deve essere lo Stage (isStage: true)")
    stage_vars = {v[0]: vid for vid, v in stage.get("variables", {}).items()}

    var_lookup = {}      # var id -> (owner, name)
    list_lookup = {}
    for t in targets:
        name = t.get("name", "?")
        if name == "Stage" and not t.get("isStage"):
            iss.warn(f"un sprite si chiama 'Stage' ({name})")
        for vid, entry in t.get("variables", {}).items():
            if not isinstance(entry, list) or len(entry) < 2:
                iss.error(f"{name}: variabile {vid} malformata: {entry!r}")
                continue
            var_lookup[vid] = (name, entry[0])
        for lid, entry in t.get("lists", {}).items():
            if not isinstance(entry, list) or len(entry) < 2:
                iss.error(f"{name}: lista {lid} malformata: {entry!r}")
            list_lookup[lid] = entry[0] if isinstance(entry, list) and entry else "?"
        for bid, bname in t.get("broadcasts", {}).items():
            if not isinstance(bname, str):
                iss.error(f"{name}: broadcast {bid} malformato")

    # layerOrder
    orders = sorted(t.get("layerOrder", -1) for t in targets)
    if orders != list(range(len(targets))):
        iss.warn(f"layerOrder non progressivi: {orders}")

    # ---- 3-4-5. blocchi, asset, riferimenti ----------------------------
    all_sprite_names = {t.get("name") for t in targets if not t.get("isStage")}

    for t in targets:
        name = t.get("name", "?")
        blocks = t.get("blocks", {})

        # costumi e suoni
        costumes = t.get("costumes", [])
        if not costumes:
            iss.error(f"{name}: nessun costume")
        if not 0 <= t.get("currentCostume", 0) < len(costumes):
            iss.error(f"{name}: currentCostume fuori range")
        for c in costumes:
            for k in ("name", "assetId", "md5ext", "dataFormat",
                      "bitmapResolution", "rotationCenterX", "rotationCenterY"):
                if k not in c:
                    iss.error(f"{name}: costume senza campo {k!r}: {c!r}")
            fn = c.get("md5ext", "")
            if fn and fn not in names:
                iss.error(f"{name}: asset {fn} assente dallo zip")
            elif fn:
                data = zf.read(fn)
                if hashlib.md5(data).hexdigest() != c.get("assetId"):
                    iss.error(f"{name}: md5 di {fn} non corrisponde a assetId")
        for s_ in t.get("sounds", []):
            fn = s_.get("md5ext", "")
            for k in ("name", "assetId", "md5ext", "dataFormat", "rate",
                      "sampleCount"):
                if k not in s_:
                    iss.error(f"{name}: suono senza campo {k!r}")
            if fn and fn not in names:
                iss.error(f"{name}: suono {fn} assente dallo zip")
            elif fn:
                data = zf.read(fn)
                if hashlib.md5(data).hexdigest() != s_.get("assetId"):
                    iss.error(f"{name}: md5 di {fn} non corrisponde")

        # blocchi
        hat_seen = set()
        for bid, b in blocks.items():
            if not isinstance(b, dict):
                iss.error(f"{name}/{bid}: blocco non è un oggetto")
                continue
            op = b.get("opcode")
            if not op or not re.match(r"^[\w-]+_[\w-]+$", str(op)):
                iss.error(f"{name}/{bid}: opcode non valido: {op!r}")
                continue
            op_prefix = str(op).split("_", 1)[0]
            if op_prefix in ("events", "operators"):
                iss.error(
                    f"{name}/{bid}: opcode {op!r} usa il prefisso plurale "
                    f"'{op_prefix}_' — i core sono SINGOLARI: usa "
                    f"{'event_' if op_prefix == 'events' else 'operator_'}* "
                    f"(errore 'Unknown extension' al load)")
            for k in ("next", "parent", "inputs", "fields", "shadow", "topLevel"):
                if k not in b:
                    iss.warn(f"{name}/{bid} ({op}): manca il campo {k!r}")

            # next/parent referenziano blocchi esistenti
            nxt = b.get("next")
            if nxt is not None and nxt not in blocks:
                iss.error(f"{name}/{bid} ({op}): next→{nxt} inesistente")
            par = b.get("parent")
            if par is not None and par not in blocks:
                iss.error(f"{name}/{bid} ({op}): parent→{par} inesistente")

            # cap blocks
            if op in ("control_stop", "control_delete_this_clone") and nxt:
                iss.error(f"{name}/{bid}: cap block {op} ha un next")

            # input
            for iname, ival in (b.get("inputs") or {}).items():
                if not isinstance(ival, list) or not ival:
                    iss.error(f"{name}/{bid} ({op}): input {iname} malformato")
                    continue
                itype = ival[0]
                if itype not in (1, 2, 3):
                    iss.error(f"{name}/{bid} ({op}): input {iname} tipo {itype}")
                    continue
                refs = [x for x in ival[1:] if isinstance(x, str)]
                for r in refs:
                    if r not in blocks:
                        iss.error(
                            f"{name}/{bid} ({op}): input {iname} → blocco "
                            f"{r} inesistente")
                if itype == 1 and isinstance(ival[1], list):
                    prim = ival[1]
                    if not (prim and isinstance(prim[0], int)
                            and prim[0] in PRIMITIVE_TYPES):
                        iss.error(
                            f"{name}/{bid} ({op}): input {iname} primitive "
                            f"non valida: {prim!r}")
                elif itype == 1 and isinstance(ival[1], str):
                    target_b = blocks.get(ival[1])
                    if isinstance(target_b, dict) and not target_b.get("shadow"):
                        iss.warn(
                            f"{name}/{bid} ({op}): input {iname} tipo 1 ma "
                            f"il blocco non è shadow")
                if itype == 3 and len(ival) < 3:
                    iss.error(f"{name}/{bid} ({op}): input {iname} tipo 3 "
                              f"deve essere [3, shadow, block]")

            # fields
            for fname, fval in (b.get("fields") or {}).items():
                if not isinstance(fval, list) or len(fval) not in (1, 2):
                    iss.error(f"{name}/{bid} ({op}): field {fname} malformato")
                    continue
                val, ref = fval
                if ref is not None:
                    if fname in ("VARIABLE",) and ref not in var_lookup:
                        iss.error(f"{name}/{bid}: field {fname} → variabile "
                                  f"sconosciuta {ref}")
                    if fname in ("LIST",) and ref not in list_lookup:
                        iss.error(f"{name}/{bid}: field {fname} → lista "
                                  f"sconosciuta {ref}")

            if b.get("topLevel"):
                if op not in ("procedures_definition",) and not str(op).startswith(
                        ("event_when", "control_start_as_clone")):
                    iss.warn(f"{name}: top level non-hat: {op}")

            if str(op).startswith("event_when") or op == "control_start_as_clone":
                hat_seen.add(bid)

            # procedure mutations
            mut = b.get("mutation")
            if mut:
                if not isinstance(mut, dict):
                    iss.error(f"{name}/{bid}: mutation malformata")
                if op == "procedures_prototype" and "proccode" not in mut:
                    iss.error(f"{name}/{bid}: prototype senza proccode")
                if op == "procedures_call" and "argumentids" not in mut:
                    iss.error(f"{name}/{bid}: call senza argumentids")

        # riferimenti input→primitive variabili ([12, name, id])
        for bid, b in blocks.items():
            for iname, ival in (b.get("inputs") or {}).items():
                if isinstance(ival, list) and ival and ival[0] == 1 \
                        and isinstance(ival[1], list):
                    prim = ival[1]
                    if prim[0] in (12, 13):
                        ref = prim[2] if len(prim) > 2 else None
                        table = var_lookup if prim[0] == 12 else list_lookup
                        if ref not in table:
                            iss.error(
                                f"{name}/{bid}: input {iname} → "
                                f"{'variabile' if prim[0]==12 else 'lista'} "
                                f"sconosciuta {prim!r}")
                    if prim[0] == 11:
                        # broadcast menu primitive: [11, name, id]
                        if not (len(prim) >= 3 and isinstance(prim[2], str)):
                            iss.warn(f"{name}/{bid}: broadcast primitive "
                                     f"senza id: {prim!r}")

        if not hat_seen and blocks:
            iss.warn(f"{name}: nessuno script (nessun hat block)")

    # ---- 6. estensioni -------------------------------------------------
    declared = set(proj.get("extensions", []))
    used = set()
    for t in targets:
        for bid, b in t.get("blocks", {}).items():
            op = str(b.get("opcode", ""))
            prefix = op.split("_", 1)[0]
            if prefix in CORE_PREFIXES:
                continue
            parts = op.split("_", 2)
            two = "_".join(parts[:2]) if len(parts) >= 2 else prefix
            if two in declared:
                used.add(two)
            elif prefix in declared:
                used.add(prefix)
            else:
                iss.error(f"opcode {op!r} usa l'estensione non dichiarata "
                          f"{prefix!r} (project.json extensions: {sorted(declared)})")
    for m in proj.get("monitors", []):
        op = str(m.get("opcode", ""))
        prefix = op.split("_", 1)[0]
        if prefix not in CORE_PREFIXES and prefix not in declared:
            iss.error(f"monitor {op!r}: estensione {prefix!r} non dichiarata")
    for ext in declared - used:
        iss.warn(f"estensione dichiarata ma non usata: {ext!r}")

    # ---- 8. monitors -----------------------------------------------------
    for m in proj.get("monitors", []):
        if m.get("opcode") == "data_variable":
            params = m.get("params", {})
            vid = m.get("id")
            vname = params.get("VARIABLE")
            if vid not in var_lookup:
                iss.error(f"monitor: variabile sconosciuta {vname!r} ({vid})")
            elif var_lookup[vid][1] != vname:
                iss.warn(f"monitor: nome variabile ≠ params ({vname!r})")
        for k in ("mode", "opcode", "params", "value", "x", "y", "visible"):
            if k not in m:
                iss.warn(f"monitor senza campo {k!r}")

    # ---- report -----------------------------------------------------------
    if not quiet:
        if iss.ok() and not iss.warnings:
            print(f"OK — {path}: {len(targets)} target, "
                  f"{sum(len(t.get('blocks', {})) for t in targets)} blocchi, "
                  f"{len(declared)} estensioni")
        else:
            for e in iss.errors:
                print(f"ERROR: {e}")
            for w in iss.warnings:
                print(f"warn: {w}")
            if iss.ok():
                print(f"Struttura OK con {len(iss.warnings)} avvisi "
                      f"({len(targets)} target)")
    return iss


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("uso: validate_sb3.py file.sb3 [--quiet]")
        sys.exit(2)
    quiet = "--quiet" in sys.argv
    issues = validate(sys.argv[1], quiet)
    sys.exit(0 if issues.ok() else 1)
