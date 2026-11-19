# Estensioni — Scratch, TurboWarp, PenguinMod

Gli opcode di un'estensione sono `<extId>_<opcode>`. L'ID va nella lista
`project.json.extensions` (il builder lo rileva dai prefissi; per ID con
underscore chiama `p.use_extension(id)`). Compatibilità: **vanilla Scratch
 ignora le estensioni sconosciute** (i blocchi restano inerti); TurboWarp e
PenguinMod caricano le proprie da gallery/URL quando apri il progetto.

## Vanilla Scratch (built-in, sicure ovunque)

| ID | Uso nei giochi |
|---|---|
| pen | minimappe, scie, disegno libero, radar |
| music | melodie con note MIDI senza file audio |
| videoSensing | giochi con webcam |
| text2speech | voci (italiano: `text2speech_setVoice` menu "Italian") |
| translate | localizzazione |
| makeymakey | controlli fisici |

TurboWarp built-in extra: **`tw`** (last key pressed, mouse button down),
**`procedures_enable_return`** (custom block con valore di ritorno).
TurboWarp core ha SEMPRE anche: `control_while`, `control_for_each`,
`looks_hideallsprites`, `operator_contains`, stage fino a 1024x960, fps
configurabile, compilatore. Il monitor "Faster mode" = `turbo`.

## TurboWarp gallery (extensions.turbowarp.org — caricate via URL al load)

| ID | Uso nei giochi |
|---|---|
| gamepad | controlli con joystick (gamepad_getAxis, _buttonIsDown) |
| pointerlock | mouse FPS-style (pointerlock_getMouseMovement) |
| box2d | fisica 2D completa |
| stretch | sprite allungabili (stretch_setStretch) |
| penplus | pen con sprite/curve avanzate |
| runtime-options | optioni runtime da progetto (runtime-options_setInterpreter) |
| local-storage | salvataggi persistenti (`ls_setValue`/`ls_getValue`) |
| files | leggere/scrivere file utente |
| clipboard, navigator, cursor, iframe, fetch | utilità web |
| sound (TW) | mic/audiorecording |
| utilities (TW) | extra di operatori |
| bitwise | operazioni bit (raspberry) |
| cloudlink | multiplayer via WebSocket |
| gamejolt, itchio, steamworks | integrazioni store |

## PenguinMod (penguinmod.com — built-in nel loro VM)

ID esatti (dal sorgente PenguinMod-Vm `src/extensions/`). I più utili per i giochi:

| ID | Uso |
|---|---|
| gameutils | utility game (device?) — suite per giochi |
| jg_runtime | runtime: static offset, render mode, FPS reporting |
| jg_timers | molti timer paralleli (jg_timers_startTimer...) |
| jg_tween | animazioni smooth (tween_moveTo...) |
| jg_pathfinding | A* pathfinding su griglia |
| jg_clones | info/gestione cloni avanzata |
| jg_easySave | salvataggi semplici (easySave_setValue) |
| jg_json | JSON completo (json_set, json_get) |
| jg_files | file system locale |
| jg_animation | animazioni sprite |
| jg_audio | audio 3D/pitch |
| jg_3d / fr_3d | 3D |
| jg_javascript / sp_javascriptV2 | exec JS (attento) |
| pm_motionExpansion / pm_operatorsExpansion / pm_sensingExpansion / pm_eventsExpansion / pm_controlsExpansion | estensioni dei blocchi base PM |
| pm_camera | controllo webcam/camera |
| gsa_canvas / theshovel_canvasEffects | effetti canvas |
| xeltalliv_clippingblending | clipping & blending (anche TW) |
| gsa_tempVars / lily_tempVars2 / gsa_objectVars | variabili temporanee |
| jwArray / jwNum / jwColor / jwVector / jwLambda | utility matematiche |
| iyg_perlin_noise | rumore perlin (terrain gen!) |
| jg_prism / jg_shaders | effetti shader |
| jg_debugging / jg_dev | console |

Lista completa live: https://github.com/PenguinMod/PenguinMod-Vm/tree/develop/src/extensions
Docs blocchi PM: https://docs.penguinmod.com

## Regole per il codice AI

1. **Default vanilla.** Passa a TurboWarp solo se una ricetta lo richiede
   (salvataggi, while, return, stage grande). PenguinMod solo su richiesta esplicita.
2. Non inventare opcode di estensione senza verificare l'ID nel catalogo sopra
   o nella gallery live. Un opcode sbagliato = blocco morto nel progetto.
3. Per estensioni con underscore nell'ID (`jg_3d`, `pm_motionExpansion`,
   `runtime-options`) usa SEMPRE `p.use_extension("jg_3d")` prima del build.
4. Il packager TurboWarp risolve da solo le estensioni gallery/PM? NO: risolve
   solo quelle di extensions.turbowarp.org; le PM richiedono apertura in
   PenguinMod (o fornitura dell'URL dell'estensione).
5. Cloud variables (multiplayer semplice): `p.variable("score", cloud=True)`
   sulla Stage — funzionano solo su Scratch/TurboWarp hostati, non in HTML standalone.
