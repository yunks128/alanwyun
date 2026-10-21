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
- **Don't touch the ravens.** Bumping into one - say, standing by the hole as
  they climb out - hurts just as much as a pellet.
- Your rocket only goes straight up, so you have to get under a raven to hit
  it - which is exactly where it wants you. Fire, then move.
- The blast kills every raven near it, and wipes out any pellets in the air, so
  a well-placed rocket can save you as well as score.
- Clear every raven in a wave and the next one starts. **Every wave they fly a
  little faster**, up to a cap so it stays playable.

## Upgrades

After every wave you are offered three upgrades and pick one (press 1, 2 or 3,
or Left / Right and Space):

| Upgrade | What it does | Most |
| --- | --- | --- |
| Quick Reload | shoot faster (20% shorter reload each time) | 6 |
| Bigger Boom | wider explosions | 4 |
| Fast Rockets | rockets fly 25% quicker | 4 |
| Double Shot | one more rocket per shot, side by side | 2 |
| Fast Feet | run 12% quicker | 4 |
| Patch Up | get a life back (only offered when you have lost one) | - |

## Rankings

When a run ends you type a name and the score joins a ranking shared by every
player (the same online database the other games use). The database rules are
in `firebase-rules.json` in the top folder, and the `ravens-scores` section of
them has to be live before scores can be posted.

The game-over screen shows the top 20, five at a time - scroll with Up / Down,
Page Up / Page Down or the mouse wheel. It starts on your own row.

## Run on your computer

```
pip install -r requirements.txt
python ravens.py
```

Your own top twenty are kept in `ravens_scores.json` next to the game (in the
browser they go to the page's own storage instead).

## How the website is built

Every push to `main` runs `.github/workflows/pages.yml` in the top folder, which
uses [pygbag](https://pygame-web.github.io/) to turn `ravens.py` into a web page
and publishes it to GitHub Pages. Just change `ravens.py` and push.
