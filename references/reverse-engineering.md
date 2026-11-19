# Reverse engineering di .sb3 con `sb3_inspect.py`

Obiettivo: capire, copiare o modificare un `.sb3` esistente **senza far leggere
`project.json` all'AI** (un progetto reale sono 5k–100k+ token). Lo script legge lo
ZIP, interpreta il JSON e stampa solo ciò che serve. Solo stdlib Python, nessuna
installazione. Accetta anche `.sprite3` (singolo sprite).

## Comandi

| Comando | Cosa stampa | Costo tipico |
|---|---|---|
| `info f.sb3` | target, n. script/blocchi, variabili (globali/locali), liste, messaggi, estensioni, custom block, monitor, opcode più usati, stima token, **HINT** sul genere/meccaniche (cloni, collisioni, platformer…) | ~20 righe |
| `tree f.sb3 [target]` | ogni script numerato `#N` con hat, n. blocchi e fatti utili (invia/scrive/chiama/clona) | 1 riga/script |
| `flow f.sb3` | mappa globale: broadcast (mittenti → riceventi), variabili (scritte da / lette da), liste, custom block e chi li chiama, cloni | ~1 riga/elemento |
| `show f.sb3 [target] [-s 0,2,4-6] [--max-lines N]` | pseudo-codice degli script scelti | proporzionale agli script |
| `find f.sb3 "testo" [--regex] [--limit N]` | blocchi che contengono opcode / testo / nome variabile / messaggio / proccode | 1 riga/hit |
| `assets f.sb3 [-o dir]` | costumi e suoni (nome, formato, dimensione, centro di rotazione); con `-o` li estrae | 1 riga/asset |
| `to-python f.sb3 -o rebuild.py [--build] [--keep-loose]` | genera uno script `sb3_builder` equivalente + cartella `rebuild_assets/` | ~1 riga/blocco |
| `diff a.sb3 b.sb3 [--json] [--scripts]` | confronto strutturale; con `--scripts` mostra pseudo-codice degli script diversi | ~10–80 righe |
| `import f.sb3 Sprite [-o out.py] [-s N] [--extract-assets]` | estrae uno sprite come frammento `sb3_builder` pronto da incollare | ~1 riga/blocco |
| `explain f.sb3` | riassunto euristico: scene, controlli, score/vite, win/lose (guess) | ~15 righe |

`target` accetta il nome esatto, senza distinzione maiuscole, o una sottostringa unica.

## Flusso di lavoro

1. **Capire il gioco**: `info` → `tree` → `flow`. Spesso basta questo per spiegare le
   scene (messaggi), lo stato (variabili) e chi fa cosa.
2. **Approfondire**: `show <sprite> -s N` solo sugli script rilevanti; `find` per
   trovare dove viene usata una variabile o un blocco.
3. **Copiare/modificare**: `to-python ... --build`, poi edita `rebuild.py`
   (stesso stile di `examples/coin_dash/build_game.py`) e rilancialo.
   `rebuild.py` importa `sb3_builder` con il percorso assoluto della cartella `scripts/`
   usata alla generazione: se sposti la skill, aggiorna la riga `sys.path.insert`.
   Dopo una modifica usa `diff originale.sb3 nuovo.sb3` per verificare che non
   siano spariti sprite, costumi o variabili.
4. **Imparare**: riscrivi la logica nei tuoi script con `sb3_builder` invece di
   incollare interi sprite; riusa i pattern di `game-recipes.md`.

## Sintassi del pseudo-codice (`show`)

Sintassi scratchblocks, con **indentazione al posto di `end`**:

```
when I receive [hurt v]            # hat; [x v] = dropdown/menu/campo
define jump (HEIGHT) and say (my text)   # custom block (argomenti tra parentesi)
repeat (3)                         # (n) = numero, [testo] = stringa, (var) = variabile
  jump ((score) + (hp)) and say [yo]     # chiamata custom block; ((a) + (b)) = reporter annidato
  if <(hp) > (2)> then             # <...> = booleano
    next costume
  else
    broadcast [dead v] and wait
add [sword] to [inventory v]       # campo lista/variabile come dropdown
(inventory :: list)                # reporter di lista
_                                  # slot vuoto
looks_foo X:(1) [mode v]           # opcode senza template: "opcode INPUT:valore [campo v]"
```

Opcode non presenti nei template (estensioni, blocchi rari) escono in forma generica
`opcode INPUT:valore [CAMPO v]`: per la firma esatta guarda `opcode-catalog.md` o
`extensions.md`.

## Cosa fa `to-python` (e cosa no)

Rigenera: stage + sprite (posizione, size, direzione, rotationStyle, visibilità, layer),
costumi (SVG/PNG/altri formati), suoni (con rate/sampleCount originali), variabili
globali e locali (anche cloud), liste, messaggi, custom block (argomenti, default, warp,
return), tutti gli script con hat, estensioni dichiarate, monitor di variabili globali.

Con `--build` esegue lo script, lancia `validate_sb3` e confronta per ogni target
opcode, variabili, liste, costumi e suoni con l'originale. Se tutto coincide stampa
`blocchi/variabili/asset identici ✔`.

Non riprodotto (segnalato in output o come commento `# [saltato]` nello script):

- stack di blocchi **senza hat** (blocchi sciolti nell'editor): `--keep-loose` li include;
- commenti dell'editor;
- monitor di liste, di variabili locali e di reporter non-variabile;
- `mutation` con nodi figli (rari, solo alcune estensioni);
- `tempo` dello stage (il builder usa 60).

Particolarità del builder rispettate nel codice generato: variabili/liste referenziate
con `p.var(nome[, scope])` e `p.listref(...)`, campi variabile via `VID()/LID()/BID()`,
broadcast con `p.broadcast_receive/send`, custom block dichiarati prima degli script
che li chiamano, hat non standard (estensioni) aggiunti a `S.HAT_BLOCKS`.

## Errori frequenti

- `ERRORE: ... non è uno zip valido`: il file non è un sb3 (forse sb2 o corrotto).
- `project.json senza 'targets'`: formato sb2/sb vecchio, converti prima con Scratch/TurboWarp.
- Target non trovato: l'errore elenca i nomi disponibili.
- `BUILD FALLITO` in `--build`: l'output mostra la coda dell'errore del builder; di solito
  indica un blocco con struttura insolita: segnalalo e tratta quello script a mano
  (`show` per leggerlo, poi riscrivilo).
