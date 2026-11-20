# The Tower

Climb 100 stories of ghosts, lava pools, flamethrowers, turrets and falling platforms.
One touch and the run is over - unless you bought a shield.

## The higher stories

| Stories | What's waiting |
| --- | --- |
| 50-60 | 5 ghosts (85% of the time) or 4 ghosts (15%) |
| 61-80 | the same ghosts, plus a 65% chance of a **turret** on the left wall that shoots an arrow across the room every 7 seconds - jump over it |
| 81-100 | 8 ghosts, an 80% chance of a turret, and a 60% chance of **two flamethrowers** |
| 85-100 | a 20% chance of **falling platforms** hovering over a lava pool - each one drops 1.5 seconds after you step on it, and floats back up a little later |

A story never has both a lava pool and a turret.

## Shop

The shop opens every time you clear a story. Alongside the sword upgrades and laser guns
there is a **shield for 20 coins**: it soaks up one hit, so it takes two to end your run.
You can only carry one at a time, and the price never goes up however high you climb.

**Play in the browser:** https://alanwyun.com/the-tower/

## Controls

| Key | Action |
| --- | --- |
| Left / Right | move |
| Up | jump |
| Space | swing the sword or fire the laser gun |
| Q | swap weapons |
| P | pause |

## Rankings

When a run ends you type a name and the score joins a ranking shared by every player
(the same online database Alien Boom Boom uses). The top five also show on
https://alanwyun.com. The database rules are in `firebase-rules.json` in the top folder.

The game-over screen shows the top 20, four at a time - scroll with Up / Down,
Page Up / Page Down or the mouse wheel. It starts on your own row.

## Run on your computer

```
pip install -r requirements.txt
python tower.py
```

## How the website is built

Every push to `main` runs `.github/workflows/pages.yml` in the top folder, which uses
[pygbag](https://pygame-web.github.io/) to turn `tower.py` into a web page and
publishes it to GitHub Pages. Just change `tower.py` and push.
