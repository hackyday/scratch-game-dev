# Catalogo opcodes — firme esatte (verificate su scratch-blocks compilato + fixture sb3 reali di scratch-vm)

Ogni firma qui sotto è derivata da DUE fonti reali:
1. `src/blocks/*.ts` + `dist/main.mjs` di **scratch-blocks** (field_dropdown = FIELD,
   input_value = può contenere blocchi → menu shadow quando è un dropdown)
2. fixture `.sb3` reali del repo **scratch-vm** (serializzazioni prodotte dall'editor)

⚠️ **CONVENZIONE CRITICA**: i prefissi core sono SINGOLARI — `event_*`,
`operator_*`. Le forme plurali `events_*` / `operators_*` sono il typo più
comune e TurboWarp le rifiuta al load con `Unknown extension`.

Forme input:
- `[1, [4,"10"]]` literal → helper `S.v(10)`, `S.s("x")`, `S.color("#hex")`
- `[1, menuId]` menu shadow → `S.menu(opcode, {FIELD: value})`
- `[2, blockId]` boolean/reporter/substack → passa il Block o `S.seq(...)`
- `[3, shadow, block]` shadow oscurato (es. variabile dentro slot numerico)

Notazione: `F(NAME, "val")` = FIELD del blocco, `M(op, NAME, "val")` = menu shadow.

## Motion (prefix `motion_`)

| opcode | inputs | fields |
|---|---|---|
| motion_movesteps | STEPS=[1,[4,"10"]] | |
| motion_turnright / motion_turnleft | DEGREES=[1,[4,"15"]] | |
| motion_gotoxy | X, Y | |
| motion_goto | GO_TO=[1, M("motion_goto_menu","TO","_mouse_"/"_random_"/"_myself_")] | |
| motion_glidesecstoxy | SECS, X, Y | |
| motion_glideto | SECS=[1,[4,"1"]], TO=[1, M("motion_glideto_menu","TO","_random_")] | |
| motion_pointindirection | DIRECTION=[1,[8,"90"]] | |
| motion_pointtowards | TOWARDS=[1, M("motion_pointtowards_menu","TOWARDS","_mouse_")] | |
| motion_changexby | DX | |
| motion_setx | X | |
| motion_changeyby | DY | |
| motion_sety | Y | |
| motion_ifonedgebounce | — | |
| motion_setrotationstyle | — | F(STYLE, "left-right") ⚠️ FIELD, non menu |
| motion_xposition / motion_yposition / motion_direction | reporter | |

## Looks (prefix `looks_`)

| opcode | inputs | fields |
|---|---|---|
| looks_say / looks_sayforsecs | MESSAGE (+ SECS) | |
| looks_think / looks_thinkforsecs | MESSAGE | |
| looks_switchcostumeto | COSTUME=[1, M("looks_costume","COSTUME","nome")] | |
| looks_nextcostume | — | |
| looks_switchbackdropto | BACKDROP=[1, M("looks_backdrops","BACKDROP","nome")] | |
| looks_nextbackdrop | — | |
| looks_changesizeby / looks_setsizeto | CHANGE / SIZE | |
| looks_changeeffectby | CHANGE + F(EFFECT, "GHOST") ⚠️ FIELD | |
| looks_seteffectto | VALUE + F(EFFECT, "GHOST") ⚠️ opcode è seteffect**to** | |
| looks_cleargraphiceffects | — | |
| looks_show / looks_hide | — | |
| looks_gotofrontback | — | F(FRONT_BACK, "front") ⚠️ FIELD |
| looks_goforwardbackwardlayers | NUM | F(FORWARD_BACKWARD, "forward") ⚠️ FIELD |
| looks_backdropnumbername / looks_costumenumbername | — | F(NUMBER_NAME, "number") |
| looks_hideallsprites | — | (TurboWarp) |
| looks_for | STACK=S.seq(...), TIMES | (TurboWarp) |

## Sound (prefix `sound_`)

| opcode | inputs | fields |
|---|---|---|
| sound_play / sound_playuntildone | SOUND_MENU=[1, M("sound_sounds_menu","SOUND_MENU","nome")] | |
| sound_stopallsounds | — | |
| sound_changevolumeby / sound_setvolumeto | VOLUME | |
| sound_volume | reporter | |
| sound_seteffectto / sound_changeeffectby | VALUE/CHANGE + F(EFFECT, "pan/pitch") | (TW) |

## Events (prefix `event_` SINGOLARE!)

| opcode | inputs | fields |
|---|---|---|
| event_whenflagclicked | hat, — | |
| event_whenkeypressed | hat | F(KEY_OPTION, "space") ⚠️ FIELD diretto, NIENTE menu |
| event_whenthisspriteclicked | hat, — | |
| event_whenstageclicked | hat, — (stage) | |
| event_whenbroadcastreceived | hat | F(BROADCAST_OPTION, [nome, idBroadcast]) |
| event_whengreaterthan | VALUE=[1,[4,"10"]] | F(WHENGREATERTHANMENU, "TIMER") |
| event_whenbackdropswitchesto | hat | F(BACKDROP, "nome") |
| event_broadcast | BROADCAST_INPUT=[1,[11,"nome",id]] → `p.broadcast_send()` | |
| event_broadcastandwait | idem | |
| event_whentouchingobject | hat, TOUCHINGOBJECTMENU | (TurboWarp) |

Valori tasti: "space","up arrow","down arrow","left arrow","right arrow","any","a".."z","0".."9".

## Control (prefix `control_`)

| opcode | inputs | fields |
|---|---|---|
| control_wait | DURATION | |
| control_repeat | TIMES=[1,[6,"10"]], SUBSTACK=[2,id] | |
| control_forever | SUBSTACK | |
| control_if | CONDITION=[2,id], SUBSTACK | |
| control_ifelse | CONDITION, SUBSTACK, SUBSTACK2 | |
| control_wait_until / control_repeat_until | CONDITION (+SUBSTACK) | |
| control_while / control_for_each | (TurboWarp) | |
| control_stop | — | F(STOP_OPTION, "all"/"this script"/"other scripts in sprite") + mutation {"hasnext":"false"} ⚠️ FIELD. Usa `S.stop()` |
| control_start_as_clone | hat, — | |
| control_create_clone_of | CLONE_OPTION=[1, M("control_create_clone_of_menu","CLONE_OPTION","_myself_"/"_random_"/"NomeSprite")] | |
| control_delete_this_clone | cap, — | |

## Sensing (prefix `sensing_`)

| opcode | inputs | fields |
|---|---|---|
| sensing_touchingobject | TOUCHINGOBJECTMENU=[1, M("sensing_touchingobjectmenu","TOUCHINGOBJECTMENU","_mouse_"/"_edge_"/"NomeSprite")] | |
| sensing_touchingcolor | COLOR=[1,[9,"#hex"]] | |
| sensing_coloristouchingcolor | COLOR, COLOR2 | |
| sensing_distanceto | DISTANCETOMENU=[1, M("sensing_distancetomenu","DISTANCETOMENU","_mouse_"/"Nome")] | |
| sensing_askandwait | QUESTION=[1,[10,"..."]] | |
| sensing_answer | reporter | |
| sensing_keypressed | KEY_OPTION=[1, M("sensing_keyoptions","KEY_OPTION","space")] ⚠️ QUI il menu esiste | |
| sensing_mousedown / sensing_mousex / sensing_mousey | reporters | |
| sensing_setdragmode | — | F(DRAG_MODE, "draggable") |
| sensing_loudness / sensing_timer / sensing_resettimer | — | |
| sensing_of | OBJECT=[1, M("sensing_of_object_menu","OBJECT","_stage_"/"Nome")] | F(PROPERTY, "x position") |
| sensing_current | — | F(CURRENTMENU, "year") |
| sensing_dayssince2000 / sensing_username | reporters | |

## Operators (prefix `operator_` SINGOLARE!)

| opcode | inputs |
|---|---|
| operator_add / subtract / multiply / divide | NUM1, NUM2 (⚠️ non OPERAND) |
| operator_random | FROM, TO |
| operator_gt / lt / equals | OPERAND1, OPERAND2 |
| operator_and / or | OPERAND1, OPERAND2 |
| operator_not | OPERAND |
| operator_join | STRING1, STRING2 |
| operator_letter_of | LETTER, STRING |
| operator_length | STRING |
| operator_contains | STRING1, STRING2 |
| operator_mod | NUM1, NUM2 |
| operator_round | NUM |
| operator_mathop | NUM + F(OPERATOR, "abs"/"floor"/"ceiling"/"sqrt"/"sin"/...) |

## Data (prefix `data_`)

| opcode | inputs | fields |
|---|---|---|
| data_setvariableto | VALUE=[1,[10,"0"]] | F(VARIABLE, [nome, idVar]) |
| data_changevariableby | VALUE=[1,[4,"1"]] | F(VARIABLE, [nome, idVar]) |
| data_showvariable / data_hidevariable | — | F(VARIABLE, [nome, idVar]) |
| data_variable (reporter) | primitive [12,nome,id] via `p.var()` | F(VARIABLE, [nome, idVar]) |
| data_addtolist | ITEM | F(LIST, [nome, idList]) |
| data_deleteoflist | INDEX | F(LIST, ...) |
| data_deletealloflist | — | F(LIST, ...) |
| data_insertatlist | INDEX, ITEM | F(LIST, ...) |
| data_replaceitemoflist | INDEX, ITEM | F(LIST, ...) |
| data_itemoflist | INDEX | F(LIST, ...) |
| data_itemnumoflist | ITEM | F(LIST, ...) |
| data_lengthoflist / data_listcontainsitem | (ITEM) | F(LIST, ...) |
| data_showlist / data_hidelist | — | F(LIST, ...) |

## Procedures (custom blocks)

`jump = sprite.custom_block("jump %n", [("HEIGHT", 10)])` →
`sprite.script(jump.hat, corpo)` con argomenti `S.arg("HEIGHT")` /
`S.arg_bool("FLAG")`; chiamata `sprite.call(jump, HEIGHT=S.v(20))`.
Formati argomento: `%s` text, `%n` number, `%b` boolean.
Le chiavi degli input di procedures_call sono gli ARGUMENT IDS (da TurboWarp
scratch3_procedures.js). Reporter-call richiede `mutation.return` + estensione
`procedures_enable_return` (TurboWarp).

Serializzazione reference:
```json
procedures_definition  inputs: {"custom_block": [1, "<protoId>"]}
procedures_prototype   shadow, mutation {proccode, argumentids, argumentnames,
                       argumentdefaults, warp, (return per TW)}
procedures_call        mutation {proccode, argumentids, warp}, inputs {"<argId>": [1, prim]}
argument_reporter_string_number / _boolean  F(VALUE, "NOME")
```

## Pen (estensione "pen") — da scratch3_pen source

| opcode | inputs |
|---|---|
| pen_clear / pen_stamp / pen_penDown / pen_penUp | — |
| pen_setPenColorToColor | COLOR=[1,[9,"#hex"]] |
| pen_changePenColorBy / pen_setPenColorParamTo / pen_changePenColorParamBy | COLOR_PARAM (menu pen_menu_COLOR_PARAM) / VALUE |
| pen_setPenSizeTo / pen_changePenSizeBy | SIZE |
| pen_setPenShadeToNumber / pen_changePenShadeBy / pen_setPenHueToNumber / pen_changePenHueBy | HUE/SHADE |

## Music (estensione "music") — da scratch3_music source

| opcode | inputs |
|---|---|
| music_playDrumForBeats | DRUM=[1, M("music_menu_DRUM","DRUM","1")], BEATS=[1,[4,"0.25"]] |
| music_restForBeats | BEATS |
| music_playNoteForBeats | NOTE=[1,[8,"60"]], BEATS |
| music_setInstrument | INSTRUMENT=[1, M("music_menu_INSTRUMENT","INSTRUMENT","1")] |
| music_setTempo / music_changeTempo | TEMPO |
| music_getTempo | reporter |
| music_midiSetInstrument / music_midiPlayDrumForBeats | idem |

MIDI: C4=60, D4=62, E4=64, G4=67, A4=69, C5=72. Menu estensione: opcode
`<extId>_menu_<NOME>` (es. `music_menu_DRUM`).

## Estensioni extra utili nei giochi (vedi extensions.md)

- TurboWarp core: `tw_getLastKeyPressed`, `tw_getMouseButtonIsDown` (menu
  tw_menu_MOUSE_BUTTON "0 primary"/"1 middle"/"2 secondary"),
  `tw_getInterpreterState`... opcode `tw_*`.
- `procedures_enable_return`: abilita procedures_return per custom block
  reporter (TW).
- PenguinMod/TW gallery: catalogo completo in references/extensions.md.
