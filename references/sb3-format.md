# Formato .sb3 — specifica (da scratch-vm/src/serialization/sb3.js)

Un `.sb3` è uno ZIP (asset compressi, project.json) contenente:

```
project.json
<md5hex>.svg | <md5hex>.png   (costumi)
<md5hex>.wav | <md5hex>.mp3   (suoni)
```

Il nome di ogni asset è `md5ext = md5(bytes) + estensione`; `assetId` nel JSON
è l'md5 puro. Il builder e il validatore lo gestiscono.

## project.json

```json
{
  "targets": [ stage, sprite1, ... ],
  "monitors": [...],
  "extensions": ["pen", "music"],
  "meta": { "semver": "3.0.0", "vm": "2.3.4", "agent": "..." }
}
```

- `targets[0]` è SEMPRE lo Stage (`isStage: true`, `layerOrder: 0`).
- Prefissi core degli opcode (SINGOLARI, da scratch-vm sb3.js CORE_EXTENSIONS):
  motion, looks, sound, event, control, sensing, operator, data, procedures,
  argument, colour, math. ⚠️ `events_*`/`operators_*` sono TYPO: TurboWarp
  li tratta come estensioni sconosciute e il load fallisce.

## Stage target

```json
{
  "isStage": true, "name": "Stage",
  "variables": { "<id>": ["nome", valore, true?] },   // true = cloud
  "lists":     { "<id>": ["nome", [elementi]] },
  "broadcasts": { "<id>": "nome" },
  "blocks": { ... }, "comments": {},
  "currentCostume": 0,
  "costumes": [ { "name": "backdrop1", "dataFormat": "svg", "assetId": "...",
                  "md5ext": "...svg", "bitmapResolution": 1,
                  "rotationCenterX": 240, "rotationCenterY": 180 } ],
  "sounds": [ { "name": "pop", "assetId": "...", "md5ext": "...wav",
                "dataFormat": "wav", "format": "", "rate": 44100,
                "sampleCount": N } ],
  "volume": 100, "layerOrder": 0,
  "tempo": 60, "videoTransparency": 50, "videoState": "on",
  "textToSpeechLanguage": null
}
```

## Sprite target

Come Stage più, senza tempo/video*:
```json
{ "isStage": false, "name": "Sprite1",
  "visible": true, "x": 0, "y": 0, "size": 100, "direction": 90,
  "draggable": false, "rotationStyle": "all around", "layerOrder": 1 }
```
`rotationStyle`: "all around" | "left-right" | "don't rotate".
Costume sprite: `rotationCenter` = punto di rotazione; per sprite 64x64 centrato
→ (32,32). `bitmapResolution: 2` solo per PNG grandi (retina); SVG → 1.

## Blocchi (la parte crittica)

```json
"<id>": {
  "opcode": "motion_movesteps",
  "next": "<id>|null",
  "parent": "<id>|null",
  "inputs": { "STEPS": [1, [4, "10"]] },
  "fields": {},
  "shadow": false,
  "topLevel": true,
  "x": 48, "y": 48          // solo topLevel
}
```

### Input — costanti da sb3.js

| forma | significato |
|---|---|
| `[1, [primitive]]` | shadow inline (valore letterale) |
| `[1, "<menuId>"]` | shadow menu (blocco shadow separato) |
| `[2, "<blockId>"]` | solo blocco (boolean/reporter/substack) |
| `[3, "<shadowId>", "<blockId>"]` | shadow oscurato da un blocco |

### Primitive compresse (array dentro gli input)

| codice | opcode | uso |
|---|---|---|
| 4 | math_number | qualsiasi numero `S.v()` |
| 5 | math_positive_number | ≥0 |
| 6 | math_whole_number | intero ≥0 |
| 7 | math_integer | intero |
| 8 | math_angle | angolo |
| 9 | colour_picker | `["#rrggbb"]` `S.color()` |
| 10 | text | stringhe `S.s()` |
| 11 | event_broadcast_menu | `[11, "nome", idBroadcast]` |
| 12 | data_variable | `[12, "nome", idVar]` (`p.var()`) |
| 13 | data_listcontents | `[13, "nome", idList]` (`p.listref()`) |

### Menu shadow (dropdown)

```json
"<menuId>": { "opcode": "sensing_keyoptions", "parent": "<parentBlockId>",
              "fields": { "KEY_OPTION": ["space", null] },
              "shadow": true, "topLevel": false }
```
Menu/dropdown che sono FIELD diretti (senza shadow), verificati su
scratch-blocks compilato e fixture reali: `event_whenkeypressed` (KEY_OPTION),
`event_whengreaterthan` (WHENGREATERTHANMENU), `event_whenbackdropswitchesto`
(BACKDROP), `event_whenbroadcastreceived` (BROADCAST_OPTION), `control_stop`
(STOP_OPTION), `motion_setrotationstyle` (STYLE), `sensing_setdragmode`
(DRAG_MODE), `sensing_current` (CURRENTMENU), `sensing_of` (PROPERTY),
`operator_mathop` (OPERATOR), `looks_seteffectto`/`looks_changeeffectby`
(EFFECT), `looks_gotofrontback` (FRONT_BACK),
`looks_goforwardbackwardlayers` (FORWARD_BACKWARD), `data_*` (VARIABLE/LIST).
I menu-shadow reali finiscono per `_menu` o sono: looks_costume,
looks_backdrops, sound_sounds_menu, sensing_keyoptions,
sensing_touchingobjectmenu, sensing_distancetomenu,
sensing_of_object_menu, motion_goto_menu, motion_pointtowards_menu,
motion_glideto_menu, control_create_clone_of_menu, music_menu_DRUM,
music_menu_INSTRUMENT, videoSensing_menu_VIDEO_STATE.

### Mutation (custom blocks + control_stop)

```json
// definition hat (procedures_definition)
"inputs": { "custom_block": [1, "<protoId>"] }
// prototype (shadow)
{ "opcode": "procedures_prototype", "shadow": true, "parent": "<defId>",
  "mutation": { "tagName": "mutation", "children": [],
    "proccode": "jump %n", "argumentids": "[\"a\",\"b\"]",
    "argumentnames": "[\"HEIGHT\"]", "argumentdefaults": "[\"10\"]",
    "warp": "true", "return": "true?" } }
// call — input keys sono gli ARGUMENT IDS (non i nomi)!
{ "opcode": "procedures_call",
  "mutation": { "proccode": "jump %n", "argumentids": "[\"a\"]", "warp": "true", "return": "true?" },
  "inputs": { "<argumentId>": [1, [4, "20"]] } }
// control_stop: mutation { "hasnext": "false" } (o "true" per "other scripts in sprite")
```

### Argument reporter (dentro il corpo della definizione)

```json
{ "opcode": "argument_reporter_string_number", "fields": { "VALUE": ["HEIGHT", null] } }
{ "opcode": "argument_reporter_boolean", "fields": { "VALUE": ["FLAG", null] } }
```

## Monitors

```json
{ "id": "<varId>", "mode": "default|large|slider", "opcode": "data_variable",
  "params": { "VARIABLE": "score" }, "spriteName": null, "value": 0,
  "width": 0, "height": 0, "x": 5, "y": 5, "visible": true,
  "sliderMin": 0, "sliderMax": 100, "isDiscrete": true }
```
`id` per un monitor di variabile = l'id della variabile.

## Coordinate stage

480x360; centro (0,0); x ∈ [-240, 240]; y ∈ [-180, 180]. Suolo visivo tipico:
y = -160. TurboWarp permette stage fino a 1024x960 (opzione packager `--stage`).

## Note di caricamento (perché il formato è rigoroso)

- scratch-vm accetta input `[2, id]` anche dove l'editor metterebbe uno shadow.
- Blocchi con opcode sconosciuti (estensione non caricata) restano nel progetto
  ma non fanno nulla.
- `next`/`parent` rotti NON bloccano il caricamento ma rompono l'editor: il
  validatore li controlla per questo.
- Il campo `meta.vm` non viene validato, ma i parser vecchi leggono `semver`.
