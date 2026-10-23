# Track of Doom

You are a race car on a track floating high over the void. The track never
ends - and it doesn't have any barriers either.

**Play in the browser:** https://alanwyun.com/track-of-doom/

## Controls

| Key | Action |
| --- | --- |
| Up | speed up |
| Down | brake, then back up |
| Left / Right | steer |
| Space | jump |
| P or Esc | pause (press E while paused to end the race) |

## How it goes

- **Don't fall off.** Drive (or land) off the edge of the track and you fall
  into the void. You have as many cars as you like: a new one is put at the
  start of the level you were on.
- **The track is endless.** It is made of straight pieces joined by sharp
  90 degree turns, and it gets narrower level by level. A chequered gate marks
  the start of each level.
- **Watch the clock.** You start with 45 seconds and every new level you reach
  puts more time back on (22 seconds at first, down to 12 later on). When the
  clock runs out the race is over - so falling off costs you time, not lives.

| Thing | What it does |
| --- | --- |
| Sharp turns | brake and steer, or fly off the edge |
| Ramps | throw you over the spike pit right after them - but only if you hit them fast enough |
| Spikes | a pit after every ramp, and shorter rows across half the track to steer round or hop |
| Smashers | heavy blocks that slam down on the track every 2 seconds - they shake just before |
| Spiky balls | scattered somewhere new on every level - steer round them or hop over with Space |
| Coins | 10 points each (some hang over the spike pits) |
| Blue pads | a speed boost for a couple of seconds |

Your score is how far you drove in metres plus 10 for every coin.

## Rankings

When the time runs out you type a name and the score joins a ranking shared by
every player (the same online database the other games use). Each name only
appears once - its best run - so there can never be two Bobs on the board
(names are matched ignoring capitals and spaces). The database rules are in
`firebase-rules.json` in the top folder, and the `track-of-doom-scores` section
of them has to be live before scores can be posted.

The game-over screen shows the top 20, five at a time - scroll with Up / Down,
Page Up / Page Down or the mouse wheel. It starts on your own row.

## Run on your computer

```
pip install -r requirements.txt
python track_of_doom.py
```

Your own top twenty are kept in `track_of_doom_scores.json` next to the game
(in the browser they go to the page's own storage instead).

## How the website is built

Every push to `main` runs `.github/workflows/pages.yml` in the top folder, which
uses [pygbag](https://pygame-web.github.io/) to turn `track_of_doom.py` into a
web page and publishes it to GitHub Pages. Just change `track_of_doom.py` and push.
