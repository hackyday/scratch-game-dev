---
name: scratch-game-dev
description: Creare giochi Scratch (.sb3) completi interamente via codice, senza editor. Usa questa skill ogni volta che l'utente vuole creare, generare o modificare un progetto/gioco Scratch, TurboWarp o PenguinMod: "fai un gioco scratch", "crea un .sb3", "platformer in Scratch", "giochi fatti dall'AI con Scratch", oppure quando chiede di convertire sb3 in HTML/EXE giocabile. Copre la generazione di project.json, asset procedurali (SVG/WAV), validazione e packaging TurboWarp. Copre anche il REVERSE ENGINEERING di .sb3 esistenti ("analizza questo sb3", "copia/impara da questo gioco", "come funziona questo progetto Scratch", "modifica questo .sb3") con sb3_inspect.py, SENZA mai leggere project.json.
---

# Scratch Game Dev — giochi Scratch interamente generati dall'AI

Un file `.sb3` è solo uno ZIP: `project.json` + asset nominati col loro md5.
Questa skill genera tutto via codice, poi valida e impacchetta — niente editor
né click. Lo stack è derivato dal codice sorgente reale:

- **scratch-vm** (Scratch Foundation) — formato sb3 (`src/serialization/sb3.js`)
- **TurboWarp** — estensioni built-in + gallery, `@turbowarp/packager` (HTML/EXE)
- **PenguinMod** — 96 estensioni built-in game-oriented (VM fork di TurboWarp)

## Percorso di lavoro (obbligatorio, in quest'ordine)

### 1. Design breve
Prima di scrivere codice definisci: genere (platformer, shooter, arcade, quiz...),
scena di gioco/menu/vittoria, 3-8 sprite max, meccaniche chiave, condizione di
vittoria/sconfitta. Non scrivere GDD lunghi: 10 righe bastano. Se l'utente è
vago, scegli tu e procedi (è un generatore di giochi, non un consulente).

### 2. Scelta runtime

| Target | Quando | Note |
|---|---|---|
| **Vanilla sb3** | default: massima compatibilità, opens in scratch.mit.edu | solo blocchi core + pen/music |
| **TurboWarp** | serve `control_while`, custom block con `return`, stage grande, FPS, gallery ext | aprire in turbowarp.org; packager incluso |
| **PenguinMod** | servono estensioni PM (3D, pathfinding, tween...) | aprire in penguinmod.com/editor |

La regola: **quando non serve, restare vanilla**. Un sb3 vanilla gira anche in
TurboWarp/PenguinMod (che sono superset), il contrario no.

### 3. Scrivi lo script di build (Python)

Crea una directory di lavoro (`/tmp/<gioco>/` o nel workspace) e scrivi un
`build_game.py` che importa la skill. Non reinventare il formato sb3 a mano:
usa il builder che serializza secondo il codice reale di scratch-vm.

```python
import sys
sys.path.insert(0, "/home/catto/.agents/skills/scratch-game-dev/scripts")
import sb3_builder as S
import assets as A   # generatori SVG + SFX WAV

p = S.Project()
stage = p.stage
stage.costume(A.backdrop("#0f2d5c", "#1a4a8a", style="stars"), name="bg",
              rotation_center=(240, 180))

player = p.sprite("Player")
player.costume(A.ship("#ffcc00"), name="player", rotation_center=(32, 32))
player.sound(A.sfx_jump(), name="jump")

score = p.variable("score", 0)
p.monitor("score")

player.script(
    S.when_flag(),
    S.blk("control_forever", SUBSTACK=S.seq(
        S.blk("control_if", CONDITION=S.key_pressed("right arrow"), SUBSTACK=S.seq(
            S.blk("motion_changeyby", DY=S.v(-1)),  # logica di gioco qui
        )),
        S.blk("motion_movesteps", STEPS=S.v(4)),
    )),
)
p.build("game.sb3")
```

**Lessico del builder** (leggi `references/opcode-catalog.md` per gli opcode e
`references/game-recipes.md` per i pattern di gioco già pronti):

- `S.blk(opcode, INPUT=value, fields={FIELD: [val, id|null]})` — un blocco.
  Input numerici/stringa: `S.v(10)`, `S.s("ciao")`, `S.angle(90)`, `S.color("#ff0000")`.
  Input boolean/reporter: passa direttamente un Block (`S.key_pressed("space")`).
  Substack: `SUBSTACK=S.seq(...)`, ramo else: `SUBSTACK2=S.seq(...)`.
- Variabili: `p.var("score")` → primitive `[12,...]` da infilare negli input;
  fields variabile: `fields={"VARIABLE": ["score", vid]}` con `vid = p.variable(...)`.
- Broadcast: hat `p.broadcast_receive("win")`, invio `p.broadcast_send("win")`
  o `p.broadcast_send("win", and_wait=True)`.
- Menu/dropdown: `S.menu("sensing_keyoptions", {"KEY_OPTION": "space"})`;
  helper pronti: `S.key_pressed`, `S.when_key`, `S.touching`, `S.random`, `S.gt/lt/equals`, `S.stop`.
- Custom block: `jump = sprite.custom_block("jump %n", [("HEIGHT", 10)])`;
  definizione `sprite.script(jump.hat, corpo...)` con argomenti via `S.arg("HEIGHT")`;
  chiamata `sprite.call(jump, HEIGHT=S.v(20))`. Reporter-style: `returns=True` (solo TurboWarp, dichiarare estensione `procedures_enable_return`).
- Asset: `A.circle/square/triangle/star/heart/ship/rocket/enemy/character/coin/platform/ball/bullet(color...)`,
  `A.backdrop(c1, c2, style="gradient|stars|grid|sky|night")`,
  SFX: `A.sfx_jump/coin/hit/explosion/laser/powerup/gameover/win/blip/menu_select()`,
  generici: `A.tone(f1, f2, dur, "square|sine|saw|noise")`, `A.melody([...])`, `A.noise_burst()`.
  Costume sprite = SVG 64x64, `rotation_center=(32,32)`; backdrop = 480x360, `(240,180)`.
- Lo stage va SEMPR creato con costume prima di `p.build()`.

Regole hard: gli sprite di gioco girano con `direction=90` e `rotation_style="left-right"`
se non deve ruotare (imposta `sprite.rotationStyle`), gli script hanno sempre un hat block,
i cloni vanno puliti con `control_delete_this_clone`, ogni `control_repeat/forever` ha un body `S.seq(...)` non vuoto.

### 4. Genera + valida (ciclo di fix)

```bash
python3 build_game.py
python3 ~/.agents/skills/scratch-game-dev/scripts/validate_sb3.py game.sb3
```

Il validatore controlla struttura blocchi, asset/md5, estensioni dichiarate,
procedure, monitor. **Fixa ogni ERROR prima di continuare** (i `warn` sono
investigabili ma non bloccanti). Gli errori tipici sono opcode sbagliati o
input/fields invertiti: il catalogo ha le firme esatte.

### 5. Impacchetta in HTML giocabile (e verifica che parta)

```bash
node ~/.agents/skills/scratch-game-dev/scripts/package_html.js game.sb3 game.html
```

Richiede `@turbowarp/packager` già installato nella cartella scripts della skill
(è incluso; se mancante: `cd ~/.agents/skills/scratch-game-dev/scripts && npm install --save-exact @turbowarp/packager`).
`loadProject()` usa scratch-vm vero: **se lo sb3 è rotto, qui fallisce** — è il
secondo test di validità. Opzioni: `--vanilla` (Scratch puro), `--fps 60`,
`--clones 300`, `--stage 960x720`, `--interpolation`.

Se ci sono strumenti browser disponibili nella sessione, apri `game.html`,
clicca la bandiera verde e fai uno screenshot per verificare che il gioco si
veda e parta: è il collaudo finale prima di consegnare.

### 6. Consegna

Dichiara all'utente:
- **game.sb3** — apribile in https://turbowarp.org/editor (o scratch.mit.edu se vanilla)
- **game.html** — standalone, doppio click e si gioca
- comandi di gioco e meccaniche implementate

Per desktop: il packager supporta anche output `.exe`/`.zip` con
`packager.options.target = 'nwjs' | 'electron'` (Node API) — menzionalo solo se
richiesto, scarica binari esterni (~100MB).

## Errori comuni (imparati a memoria)

1. **Sprite senza costume** → `BuilderError`: ogni target ha bisogno di almeno 1 costume.
2. **Script senza hat** → `BuilderError`: il primo blocco di `script()` è un hat.
3. **Cap block con blocchi sotto** (`control_stop`, `control_delete_this_clone`) → errore.
4. **Stesso Block object usato in due input** → errore: crea 2 copie (fai una funzione).
5. **Prefissi singolari**: i core opcode sono `event_*` e `operator_*` (NON
   `events_*`/`operators_*` — TurboWarp dà "Unknown extension" al load).
6. **FIELD vs menu**: `event_whenkeypressed` ha KEY_OPTION come FIELD diretto,
   mentre `sensing_keypressed` usa il menu shadow `sensing_keyoptions`;
   `looks_switchbackdropto` usa menu `looks_backdrops`; `control_stop` ha
   STOP_OPTION come FIELD. Catalogo e sb3-format.md hanno la lista completa.
7. **Variabili**: nei `data_*` la variabile è un FIELD `{"VARIABLE": [nome, id]}`,
   negli altri input è primitive `p.var("nome")`. Non confondere.
8. **Rotazione**: gli sprite di default ruotano (`all around`): per un platformer
   usa `rotationStyle="left-right"` o `"don't rotate"`.
9. **Estensioni**: usa solo opcode con estensione davvero dichiarata in
   `project.json.extensions` — il builder le rileva dai prefissi, ma per ID con
   underscore (`jg_3d`, `pm_motionExpansion`) chiama `p.use_extension("jg_3d")`.

## Esempio completo funzionante

`examples/coin_dash/` contiene un gioco arcade completo (menu, cloni, nemici,
punti/vite, suoni, GameOver/Win) generato e verificato end-to-end nel runtime.
Leggi `examples/coin_dash/build_game.py` come riferimento di stile prima di
scrivere il tuo primo gioco: dimostra TUTTE le API del builder.

## Reverse engineering di .sb3 esistenti (copiare / imparare / modificare)

Quando l'utente fornisce un `.sb3` da capire, copiare o modificare, **NON leggere mai
`project.json`** (né con `cat`, né con `view`, né aprendo lo zip a mano): pesa
decine/centinaia di KB e brucia token. Usa `scripts/sb3_inspect.py`, che lo legge
al posto tuo e restituisce viste compatte (solo stdlib Python):

```bash
S=~/.agents/skills/scratch-game-dev/scripts
python3 $S/sb3_inspect.py info game.sb3            # panoramica: target, variabili, messaggi, estensioni, stima token, HINT sul genere/meccaniche
python3 $S/sb3_inspect.py tree game.sb3            # script numerati: "#2 when I receive [hurt v] — 5 blocchi [scrive inv]"
python3 $S/sb3_inspect.py flow game.sb3            # chi invia/riceve ogni broadcast, chi scrive/legge ogni variabile, cloni, custom block
python3 $S/sb3_inspect.py show game.sb3 Player -s 1   # pseudo-codice (scratchblocks) dello script #1 di Player
python3 $S/sb3_inspect.py find game.sb3 "score"    # dove compare un opcode / testo / variabile / messaggio
python3 $S/sb3_inspect.py assets game.sb3 -o assets/   # elenca ed estrae costumi e suoni
python3 $S/sb3_inspect.py to-python game.sb3 -o rebuild.py --build   # rigenera il gioco come script sb3_builder
python3 $S/sb3_inspect.py diff original.sb3 modified.sb3 [--scripts]  # confronto (+ pseudo-codice)
python3 $S/sb3_inspect.py import game.sb3 Enemy -o enemy.py --extract-assets  # copia uno sprite
python3 $S/sb3_inspect.py explain game.sb3         # riassunto euristico scene/score/win
```

**Ordine consigliato** (dal più economico al più costoso): `info` → `tree` → `flow` →
`show <sprite> -s N` solo sugli script che servono → `find` per cercare un dettaglio.
`show` senza `-s` stampa tutti gli script di quel target (limite `--max-lines`, default 200).
Il pseudo-codice usa la sintassi scratchblocks con l'indentazione al posto di `end`.

**Imparare da un gioco**: `info` + `flow` + `show` sugli script chiave, poi riusa i pattern
(vedi anche `references/game-recipes.md`). Non copiare a occhio interi sprite: spiega all'utente
cosa hai capito e riscrivi con `sb3_builder`.

**Copiare / modificare un gioco**: `to-python game.sb3 -o rebuild.py --build` crea
`rebuild.py` (stesso formato di `examples/coin_dash/build_game.py`) + la cartella
`rebuild_assets/` con costumi e suoni originali. Con `--build` lo esegue, lo valida
(`validate_sb3`) e confronta opcode/variabili/asset con l'originale. Poi **modifica
`rebuild.py`** (cambia un valore, aggiungi uno sprite, riscrivi uno script) e rilancialo:
non serve mai toccare il JSON. Limiti noti: stack di blocchi senza hat saltati (usa
`--keep-loose` per includerli), commenti e monitor di liste/variabili locali non
riprodotti (segnalati nell'output).

Dettagli e sintassi del pseudo-codice: `references/reverse-engineering.md`.

## References — quando leggerle

- `references/opcode-catalog.md` — firma esatta di OGNI blocco core (+ pen/music). Leggilo prima di scrivere la build se non hai gli input a mente.
- `references/game-recipes.md` — pattern completi già testati: platformer fisica, spari con cloni, nemici, menu scene, punti/vita, power-up, salvataggio, scrolling. PARTI DA QUI per la logica di gioco.
- `references/extensions.md` — catalogo estensioni Scratch/TurboWarp/PenguinMod con ID esatti e blocchi utili per i giochi.
- `references/sb3-format.md` — specifica completa del formato sb3 (serve solo per debugging avanzato o feature del builder non coperte).
- `references/reverse-engineering.md` — come leggere l'output di `sb3_inspect.py` (sintassi pseudo-codice, flow, limiti di `to-python`). Leggilo quando analizzi un .sb3 esistente.
