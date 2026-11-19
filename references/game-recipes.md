# Ricette di gioco — pattern già strutturati per il builder

Tutte le ricette sono pseudocodice con la DSL di `sb3_builder.py`. Copiale,
adattale, incollale nel tuo `build_game.py`. Coordinate stage: x ∈ [-240, 240],
y ∈ [-180, 180].

## 1. Platformer (fisica base)

Variabili globali: `yvel` (velocità verticale). Sprite Player con
`rotationStyle="don't rotate"`.

```python
p = S.Project()
stage = p.stage
stage.costume(A.backdrop("#1b2f4b", "#335f9e", style="gradient"), name="bg",
              rotation_center=(240, 180))
player = p.sprite("Player", rotationStyle="don't rotate")
player.costume(A.character("#44cc44"), name="player", rotation_center=(32, 32))
player.sound(A.sfx_jump(), name="jump")
yvel = p.variable("yvel", 0)

GROUND = "#8855ff"  # colore delle piattaforme

def play(name):  # helper: suona un suono per nome
    return S.blk("sound_play", SOUND_MENU=S.menu("sound_sounds_menu",
                                                 {"SOUND_MENU": name}))

# loop fisica: gravità + salto + movimento
player.script(
    S.when_flag(),
    S.blk("motion_gotoxy", X=S.v(-180), Y=S.v(100)),
    S.blk("data_setvariableto", fields={"VARIABLE": ["yvel", yvel]}, VALUE=S.v(0)),
    S.blk("control_forever", SUBSTACK=S.seq(
        # gravità
        S.blk("data_changevariableby", fields={"VARIABLE": ["yvel", yvel]}, VALUE=S.v(-1)),
        S.blk("motion_changeyby", DY=p.var("yvel")),
        # salto: solo se a terra (tocca il colore del suolo)
        S.blk("control_if", CONDITION=S.touching_color(GROUND), SUBSTACK=S.seq(
            S.blk("data_setvariableto", fields={"VARIABLE": ["yvel", yvel]}, VALUE=S.v(0)),
            S.blk("control_if", CONDITION=S.key_pressed("space"), SUBSTACK=S.seq(
                S.blk("data_setvariableto", fields={"VARIABLE": ["yvel", yvel]}, VALUE=S.v(14)),
                play("jump"),
            )),
        )),
        # movimento orizzontale
        S.blk("control_if", CONDITION=S.key_pressed("right arrow"), SUBSTACK=S.seq(
            S.blk("motion_changexby", DX=S.v(4)),
        )),
        S.blk("control_if", CONDITION=S.key_pressed("left arrow"), SUBSTACK=S.seq(
            S.blk("motion_changexby", DX=S.v(-4)),
        )),
    )),
)
```

Piattaforme: sprite quadrati statici; il terreno si gestisce o con
`S.touching_color("#hex")` sul colore delle piattaforme, o con la posizione
(`motion_yposition < soglia`). Nelle piattaforme multiple usa cloni.

Terreno solido in 3 blocchi (dopo il movimento): se tocchi il colore del suolo,
risali finché non lo tocchi più:

```python
S.blk("control_repeat_until", CONDITION=S.blk("operator_not", OPERAND=S.touching_color("#8855ff")), SUBSTACK=S.seq(
    S.blk("motion_changeyby", DY=S.v(1)),
))
```

## 2. Spari con cloni (shooter)

Sprite `Bullet`, costume piccolo (`A.bullet()`), nascosto (`sprite.visible=False`,
`sprite.hide()` iniziale).

```python
bullet = p.sprite("Bullet", visible=False)
bullet.costume(A.bullet(), name="bullet", rotation_center=(16, 16))

player.script(S.when_key("space"), S.blk("control_create_clone_of",
              CLONE_OPTION=S.menu("control_create_clone_of_menu",
                                  {"CLONE_OPTION": "Bullet"})))

bullet.script(S.blk("control_start_as_clone"),      # cap: nessun flag clicco
              S.blk("motion_goto", GO_TO=S.menu("motion_goto_menu", {"TO": "Player"})),
              S.blk("motion_pointtowards", TOWARDS=S.menu("motion_pointtowards_menu", {"TOWARDS": "_mouse_"})),
              S.blk("looks_show"),
              S.blk("control_forever", SUBSTACK=S.seq(
                  S.blk("motion_movesteps", STEPS=S.v(12)),
                  S.blk("control_if", CONDITION=S.touching("_edge_"), SUBSTACK=S.seq(
                      S.blk("control_delete_this_clone"))),
              )))
```

Attenzione: `control_start_as_clone` è un hat; NON mettere blocchi sopra.
Ritmo di fuoco: invece di `when_key`, usa un loop che spara ogni 0.2s
(`control_wait DURATION S.v(0.2)` + create clone).

## 3. Nemici che inseguono / spawn casuale

```python
enemy.script(S.blk("control_start_as_clone"),
    S.blk("motion_gotoxy", X=S.random(-200, 200), Y=S.v(180)),
    S.blk("looks_show"),
    S.blk("control_forever", SUBSTACK=S.seq(
        S.blk("motion_pointtowards", TOWARDS=S.menu("motion_pointtowards_menu", {"TOWARDS": "Player"})),
        S.blk("motion_movesteps", STEPS=S.v(2)),
        S.blk("control_if", CONDITION=S.touching("Player"), SUBSTACK=S.seq(
            S.blk("data_changevariableby", fields={"VARIABLE": ["lives", lives]}, VALUE=S.v(-1)),
            S.blk("control_delete_this_clone"),
        )),
    )),
)
```

Spawn: hat `when_flag` → `control_forever [ wait 2s; create clone of Enemy ]`.

## 4. Menu / scene (stato globale con backdrop)

Uno script sullo Stage gestisce le scene; i giochi controllano `p.var("scene")`.

```python
p.variable("scene", "menu")
stage.script(S.when_flag(),
    S.blk("data_setvariableto", fields={"VARIABLE": ["scene", scene]}, VALUE=S.s("menu")),
    S.blk("looks_switchbackdropto", BACKDROP=S.menu("looks_backdrops", {"BACKDROP": "Menu"})),
)
# bottone gioca: sprite Button
btn.script(S.blk("event_whenthisspriteclicked"),
    S.blk("data_setvariableto", fields={"VARIABLE": ["scene", scene]}, VALUE=S.s("game")),
    S.blk("looks_switchbackdropto", BACKDROP=S.menu("looks_backdrops", {"BACKDROP": "Level1"})),
    p.broadcast_send("start game"))
# i gameplay partono con: pl.script(p.broadcast_receive("start game"), ...)
```

## 5. Punti, vita, game over

```python
score = p.variable("score", 0); lives = p.variable("lives", 3)
p.monitor("score", x=5, y=5); p.monitor("lives", x=5, y=40)

# game over broadcast dal momento in cui lives = 0 (dove perdi la vita):
S.blk("control_if", CONDITION=S.lt(p.var("lives"), S.v(1)), SUBSTACK=S.seq(
    S.blk("sound_play", SOUND_MENU=S.menu("sound_sounds_menu", {"SOUND_MENU": "gameover"})),
    S.blk("looks_switchbackdropto", BACKDROP=S.menu("looks_backdrops", {"BACKDROP": "GameOver"})),
    S.stop("all"),
))
```

Vittoria: `S.equals(p.var("score"), S.v(20))` → broadcast "win" → cambio
backdrop + `A.sfx_win()`.

## 6. Effetto ghost per morte/danno (lampeggio)

```python
S.blk("looks_seteffectto", fields={"EFFECT": ["GHOST", None]}, VALUE=S.v(50)),
S.blk("control_wait", DURATION=S.v(0.3)),
S.blk("looks_seteffectto", fields={"EFFECT": ["GHOST", None]}, VALUE=S.v(0)),
```

Alla fine del gioco sempre `looks_cleargraphiceffects`.

## 7. Scrolling (camera segue il player)

Variabile globale `scrollx`. Ogni sprite di scena:
`motion_setx X = (mia_x) - scrollx`. Player fermo al centro? No: player si muove
e `scrollx` cresce:

```python
player.script(S.when_flag(), S.blk("control_forever", SUBSTACK=S.seq(
    S.blk("control_if", CONDITION=S.key_pressed("right arrow"), SUBSTACK=S.seq(
        S.blk("data_changevariableby", fields={"VARIABLE": ["scrollx", scrollx]}, VALUE=S.v(4)),
    )),
)))
# oggetti di sfondo:
S.blk("motion_setx", X=S.blk("operator_add",
       OPERAND1=object_world_x, OPERAND2=S.blk("operator_subtract",
       OPERAND1=S.v(0), OPERAND2=p.var("scrollx"))))
```

## 8. Salvataggio (TurboWarp) — estensione local-storage

```python
p.use_extension("local-storage")
# salva: ls_setValue VALUE=(stringa con operatore join dei valori) KEY=S.s("save1")
S.blk("ls_setValue", KEY=S.s("save1"), VALUE=S.blk("operator_join",
    STRING1=p.var("score"), STRING2=S.s("|")))
# carica:
S.blk("ls_getValue", KEY=S.s("save1"))   # reporter, input KEY
```

Vanilla: lista `data_addtolist` + codifica manuale — evitalo, preferisci TurboWarp.

## 9. Cooldown / timer di gioco

Timer built-in: `sensing_timer` + `sensing_resettimer`. Countdown:

```python
p.variable("timeleft", 60)
stage.script(S.when_flag(), S.blk("sensing_resettimer"),
    S.blk("control_forever", SUBSTACK=S.seq(
        S.blk("control_wait_until", CONDITION=S.gt(S.blk("sensing_timer"), S.v(1))),
        S.blk("sensing_resettimer"),
        S.blk("data_changevariableby", fields={"VARIABLE": ["timeleft", timeleft]}, VALUE=S.v(-1)),
        S.blk("control_if", CONDITION=S.lt(p.var("timeleft"), S.v(1)), SUBSTACK=S.seq(
            p.broadcast_send("game over")),
        ),
    )))
```

## 10. Checklist qualità finale (prima di consegnare)

- [ ] Ogni sprite ha costume + (dove serve) suono, `rotationStyle` adeguato
- [ ] All'avvio: reset variabili, posizioni, effetti, visibilità (script "reset" sul flag)
- [ ] I cloni vengono eliminati (edge/enemy/bullet) — nessun clone infinito
- [ ] Vittoria E sconfitta implementate (backdrop + suono + stop)
- [ ] Punteggio monitorato (`p.monitor`)
- [ ] Il gioco è giocabile con 3 tasti max (flag + frecce + space)
- [ ] validate_sb3.py: 0 error; package_html.js: parte senza eccezioni
