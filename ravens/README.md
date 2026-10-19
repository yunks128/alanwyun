# Ravens from the Underworld

They are climbing out of the burning hole at the bottom right, and all you have
is a rocket launcher that fires straight up.

**Play in the browser:** https://alanwyun.com/ravens/

## Controls

| Key | Action |
| --- | --- |
| Left / Right | run along the ground |
| Space | fire a rocket straight up |
| P or Esc | pause |

## How it goes

- Ravens climb out of the hole, settle into the sky and fly back and forth.
- A raven loads a pellet and waits until it is **right above you** before
  dropping it, so standing still is never safe. Three pellets and you are done.
- Your rocket only goes straight up, so you have to get under a raven to hit
  it - which is exactly where it wants you. Fire, then move.
- The blast kills every raven near it, and wipes out any pellets in the air, so
  a well-placed rocket can save you as well as score.
- Clear every raven in a wave and the next one starts. **Every wave they fly a
  little faster**, up to a cap so it stays playable.

## Rankings

When a run ends you type a name and the score joins a ranking shared by every
player (the same online database the other games use). The database rules are
in `firebase-rules.json` in the top folder, and the `ravens-scores` section of
them has to be live before scores can be posted.

## Run on your computer

```
pip install -r requirements.txt
python ravens.py
```

Your own top five are kept in `ravens_scores.json` next to the game (in the
browser they go to the page's own storage instead).

## How the website is built

Every push to `main` runs `.github/workflows/pages.yml` in the top folder, which
uses [pygbag](https://pygame-web.github.io/) to turn `ravens.py` into a web page
and publishes it to GitHub Pages. Just change `ravens.py` and push.
