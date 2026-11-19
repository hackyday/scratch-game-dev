# Changelog — features & fixes (2026-11-19)

## validate_sb3.py
- **KNOWN_OPCODES**: tabella di ~170 opcode core/menu/procedures derivata da
  `opcode-catalog.md`. Un typo come `looks_setsize` (corretto: `looks_setsizeto`)
  diventa ERROR con suggerimento automatico.
- Protegge ogni gioco generato dall'AI da opcode inesistenti che passavano
  il solo check sintattico `^\w+_\w+$`.

## examples/coin_dash
- Fix: `looks_setsize` → `looks_setsizeto` (3 occorrenze in build_game.py).
- `coin_dash.sb3` rigenerato e validato OK.
- Path di import in build_game.py reso relativo al file.

## sb3_inspect.py
- **diff** `a.sb3 b.sb3 [--scripts] [--json]`: confronto strutturale; con
  `--scripts` mostra il pseudo-codice degli script diversi.
- **import** `game.sb3 Sprite [-o out.py] [-s N] [--extract-assets]`: estrae
  uno sprite come frammento `sb3_builder` pronto da incollare (il caso d'uso
  più comune di “copia da questo gioco”).
- **explain** `game.sb3`: riassunto euristico one-screen (scene/backdrop,
  tasti, score/vite, messaggi win/lose/start, meccaniche).
- Supporto **.sprite3** (zip con `sprite.json`).
- Template scratchblocks per pen, music, video, tts, translate, alcuni TW.
- `info` stampa HINT di genere (cloni, collisioni, platformer, …).
- `is_hat` più robusto sulle estensioni.

## Non implementato (priorità più bassa)
- `fetch <project id>` via `@turbowarp/sbdl` (richiede node_modules completo).
- Template completi di tutte le estensioni PenguinMod (centinaia di opcode);
  i più usati (pen/music) ci sono; gli altri restano in forma generica.
