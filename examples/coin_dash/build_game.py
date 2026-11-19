# -*- coding: utf-8 -*-
"""Coin Dash — gioco arcade completo generato con la skill scratch-game-dev.

Menu → Game → GameOver/Win. Player con frecce, monete con cloni, nemici
che inseguono, invulnerabilità dopo il colpo, score/lives con monitor,
SFX procedurali, broadcast per le scene.
"""
import sys
sys.path.insert(0, "/home/catto/.agents/skills/scratch-game-dev/scripts")
import sb3_builder as S
import assets as A

WIN_SCORE = 15

p = S.Project()
stage = p.stage

# ---------------- stage: 4 backdrops + suoni ----------------
stage.costume(A.backdrop("#0a1630", "#16336b", style="night"), name="Menu",
              rotation_center=(240, 180))
stage.costume(A.backdrop("#1b2f4b", "#335f9e", style="grid"), name="Game",
              rotation_center=(240, 180))
stage.costume(A.backdrop("#330b0b", "#550d0d", style="plain"), name="GameOver",
              rotation_center=(240, 180))
stage.costume(A.backdrop("#0d330b", "#0d551b", style="plain"), name="Win",
              rotation_center=(240, 180))
stage.sound(A.sfx_gameover(), name="gameover")
stage.sound(A.sfx_win(), name="win")

score = p.variable("score", 0)
lives = p.variable("lives", 3)
inv = p.variable("inv", 0)
p.monitor("score", x=8, y=8)
p.monitor("lives", x=8, y=44)

def play(sprite, name):
    return S.blk("sound_play", SOUND_MENU=S.menu("sound_sounds_menu",
                                                 {"SOUND_MENU": name}))

# ---------------- reset iniziale (flag) ----------------
stage.script(
    S.when_flag(),
    S.blk("data_setvariableto", fields={"VARIABLE": ["score", score]}, VALUE=S.v(0)),
    S.blk("data_setvariableto", fields={"VARIABLE": ["lives", lives]}, VALUE=S.v(3)),
    S.blk("data_setvariableto", fields={"VARIABLE": ["inv", inv]}, VALUE=S.v(0)),
    S.blk("looks_switchbackdropto", BACKDROP=S.menu("looks_backdrops",
                                                    {"BACKDROP": "Menu"})),
)

# ---------------- sprite Player ----------------
player = p.sprite("Player", rotationStyle="don't rotate")
player.costume(A.ball("#ff8800"), name="player", rotation_center=(32, 32))

# menu: rimbalza sullo schermo
player.script(
    S.when_flag(),
    S.blk("looks_show"),
    S.blk("looks_cleargraphiceffects"),
    S.blk("looks_setsize", SIZE=S.v(100)),
    S.blk("motion_gotoxy", X=S.v(0), Y=S.v(0)),
    S.blk("control_forever", SUBSTACK=S.seq(
        S.blk("motion_movesteps", STEPS=S.v(4)),
        S.blk("motion_ifonedgebounce"),
    )),
)

# gioco: movimento con le frecce + limiti bordi
player.script(
    p.broadcast_receive("start game"),
    S.blk("control_forever", SUBSTACK=S.seq(
        S.blk("control_if", CONDITION=S.key_pressed("left arrow"), SUBSTACK=S.seq(
            S.blk("motion_changexby", DX=S.v(-5)))),
        S.blk("control_if", CONDITION=S.key_pressed("right arrow"), SUBSTACK=S.seq(
            S.blk("motion_changexby", DX=S.v(5)))),
        S.blk("control_if", CONDITION=S.key_pressed("up arrow"), SUBSTACK=S.seq(
            S.blk("motion_changeyby", DY=S.v(5)))),
        S.blk("control_if", CONDITION=S.key_pressed("down arrow"), SUBSTACK=S.seq(
            S.blk("motion_changeyby", DY=S.v(-5)))),
        S.blk("control_if", CONDITION=S.gt(S.blk("motion_xposition"), S.v(220)),
              SUBSTACK=S.seq(S.blk("motion_setx", X=S.v(220)))),
        S.blk("control_if", CONDITION=S.lt(S.blk("motion_xposition"), S.v(-220)),
              SUBSTACK=S.seq(S.blk("motion_setx", X=S.v(-220)))),
        S.blk("control_if", CONDITION=S.gt(S.blk("motion_yposition"), S.v(160)),
              SUBSTACK=S.seq(S.blk("motion_sety", Y=S.v(160)))),
        S.blk("control_if", CONDITION=S.lt(S.blk("motion_yposition"), S.v(-160)),
              SUBSTACK=S.seq(S.blk("motion_sety", Y=S.v(-160)))),
    )),
)

# danno: lampeggio e invulnerabilità
player.script(
    p.broadcast_receive("hurt"),
    S.blk("looks_seteffectto", fields={"EFFECT": ["GHOST", None]}, VALUE=S.v(60)),
    S.blk("control_wait", DURATION=S.v(0.8)),
    S.blk("looks_seteffectto", fields={"EFFECT": ["GHOST", None]}, VALUE=S.v(0)),
    S.blk("data_setvariableto", fields={"VARIABLE": ["inv", inv]}, VALUE=S.v(0)),
)

# ---------------- sprite Coin ----------------
coin = p.sprite("Coin", visible=False)
coin.costume(A.coin(), name="coin", rotation_center=(32, 32))
coin.sound(A.sfx_coin(), name="coin")

coin.script(S.when_flag(), S.blk("looks_hide"))

# clone: vive 4s, se tocca Player → punto + suono + auto-delete
coin.script(
    S.blk("control_start_as_clone"),
    S.blk("looks_show"),
    S.blk("motion_gotoxy", X=S.random(-210, 210), Y=S.random(-150, 150)),
    S.blk("control_repeat", TIMES=S.v(40), SUBSTACK=S.seq(
        S.blk("control_wait", DURATION=S.v(0.1)),
        S.blk("control_if", CONDITION=S.touching("Player"), SUBSTACK=S.seq(
            S.blk("data_changevariableby", fields={"VARIABLE": ["score", score]},
                  VALUE=S.v(1)),
            play(coin, "coin"),
            S.blk("control_delete_this_clone"),
        )),
    )),
    S.blk("control_delete_this_clone"),
)

# ---------------- sprite Enemy ----------------
enemy = p.sprite("Enemy", visible=False)
enemy.costume(A.enemy("#aa33ff"), name="enemy", rotation_center=(32, 32))
enemy.sound(A.sfx_hit(), name="hit")

enemy.script(S.when_flag(), S.blk("looks_hide"))

enemy.script(
    S.blk("control_start_as_clone"),
    S.blk("looks_show"),
    S.blk("looks_setsize", SIZE=S.v(90)),
    S.blk("motion_gotoxy", X=S.random(-200, 200), Y=S.v(170)),
    S.blk("control_forever", SUBSTACK=S.seq(
        S.blk("motion_pointtowards", TOWARDS=S.menu("motion_pointtowards_menu",
                                                   {"TOWARDS": "Player"})),
        S.blk("motion_movesteps", STEPS=S.v(2.5)),
        S.blk("control_if", CONDITION=S.blk("operator_and",
              OPERAND1=S.touching("Player"),
              OPERAND2=S.equals(p.var("inv"), S.v(0))), SUBSTACK=S.seq(
            S.blk("data_changevariableby", fields={"VARIABLE": ["lives", lives]},
                  VALUE=S.v(-1)),
            S.blk("data_setvariableto", fields={"VARIABLE": ["inv", inv]}, VALUE=S.v(1)),
            play(enemy, "hit"),
            p.broadcast_send("hurt"),
            S.blk("control_delete_this_clone"),
        )),
    )),
)

# ---------------- sprite StartButton ----------------
button = p.sprite("StartButton", rotationStyle="don't rotate")
button.costume(A.square("#00cc66"), name="btn", rotation_center=(32, 32))
button.sound(A.sfx_menu_select(), name="btn")

button.script(
    S.when_flag(),
    S.blk("looks_show"),
    S.blk("looks_setsize", SIZE=S.v(300)),
    S.blk("motion_gotoxy", X=S.v(0), Y=S.v(-120)),
)

button.script(
    S.blk("event_whenthisspriteclicked"),
    play(button, "btn"),
    S.blk("looks_switchbackdropto", BACKDROP=S.menu("looks_backdrops",
                                                    {"BACKDROP": "Game"})),
    p.broadcast_send("start game"),
)

button.script(
    p.broadcast_receive("start game"),
    S.blk("looks_hide"),
)

# ---------------- logica di scena / spawner (Stage) ----------------
# spawner monete
stage.script(
    p.broadcast_receive("start game"),
    S.blk("control_forever", SUBSTACK=S.seq(
        S.blk("control_create_clone_of", CLONE_OPTION=S.menu(
            "control_create_clone_of_menu", {"CLONE_OPTION": "Coin"})),
        S.blk("control_wait", DURATION=S.v(0.55)),
    )),
)

# spawner nemici
stage.script(
    p.broadcast_receive("start game"),
    S.blk("control_forever", SUBSTACK=S.seq(
        S.blk("control_wait", DURATION=S.v(2)),
        S.blk("control_create_clone_of", CLONE_OPTION=S.menu(
            "control_create_clone_of_menu", {"CLONE_OPTION": "Enemy"})),
    )),
)

# controllo vittoria/sconfitta
stage.script(
    p.broadcast_receive("start game"),
    S.blk("control_forever", SUBSTACK=S.seq(
        S.blk("control_wait", DURATION=S.v(0.2)),
        S.blk("control_if", CONDITION=S.lt(p.var("lives"), S.v(1)), SUBSTACK=S.seq(
            p.broadcast_send("game over"))),
        S.blk("control_if", CONDITION=S.gt(p.var("score"), S.v(WIN_SCORE - 1)),
              SUBSTACK=S.seq(p.broadcast_send("win"))),
    )),
)

stage.script(
    p.broadcast_receive("game over"),
    S.blk("looks_switchbackdropto", BACKDROP=S.menu("looks_backdrops",
                                                    {"BACKDROP": "GameOver"})),
    play(stage, "gameover"),
    S.stop("all"),
)

stage.script(
    p.broadcast_receive("win"),
    S.blk("looks_switchbackdropto", BACKDROP=S.menu("looks_backdrops",
                                                    {"BACKDROP": "Win"})),
    play(stage, "win"),
    S.stop("all"),
)

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "coin_dash.sb3"
    proj = p.build(out)
    blocks = sum(len(t["blocks"]) for t in proj["targets"])
    print(f"OK {out}: {len(proj['targets'])} target, {blocks} blocchi, "
          f"estensioni={proj['extensions']}")
