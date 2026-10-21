# Tree Jumper

You are a monkey who never stops bouncing. Climb the jungle from branch to
branch - and don't fall, because the tigers on the jungle floor are hungry.

**Play in the browser:** https://alanwyun.com/tree-jumper/

## Controls

| Key | Action |
| --- | --- |
| Left / Right | steer the monkey |
| P or Esc | pause |

The monkey jumps on its own: land on a branch on the way down and it springs
straight back up.

## How it goes

- **Keep climbing.** The view creeps upwards on its own, a little faster the
  higher you get. Drop out of the bottom of it and the tigers get you.
- What tries to knock you out of the trees depends on how high you are:

| Height | Danger |
| --- | --- |
| up to 150 m | **birds** fly across the treetops |
| 150 - 350 m | **hawks** cruise over, then dive straight at you |
| 350 m and up | **comets** fall out of the sky - a red **!** shows where |

- One touch from any of them and you fall - and the tigers are waiting.
- The branches get further apart and shorter the higher you go, but there is
  always one you can reach.
- Bananas on the branches are worth 10 points each. Your score is your height in
  metres plus your bananas.

## Rankings

When a run ends you type a name and the score joins a ranking shared by every
player (the same online database the other games use). Each name only appears
once - its best run - so there can never be two Bobs on the board (names are
matched ignoring capitals and spaces). The database rules are in
`firebase-rules.json` in the top folder, and the `tree-jumper-scores` section of
them has to be live before scores can be posted.

The game-over screen shows the top 20, five at a time - scroll with Up / Down,
Page Up / Page Down or the mouse wheel. It starts on your own row.

## Run on your computer

```
pip install -r requirements.txt
python tree_jumper.py
```

Your own top twenty are kept in `tree_jumper_scores.json` next to the game (in
the browser they go to the page's own storage instead).

## How the website is built

Every push to `main` runs `.github/workflows/pages.yml` in the top folder, which
uses [pygbag](https://pygame-web.github.io/) to turn `tree_jumper.py` into a web
page and publishes it to GitHub Pages. Just change `tree_jumper.py` and push.
