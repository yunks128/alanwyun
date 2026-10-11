# The Tower

Climb 50 stories of ghosts, lava pools and flamethrowers. One touch and the run is over.

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

## Run on your computer

```
pip install -r requirements.txt
python tower.py
```

## How the website is built

Every push to `main` runs `.github/workflows/pages.yml` in the top folder, which uses
[pygbag](https://pygame-web.github.io/) to turn `tower.py` into a web page and
publishes it to GitHub Pages. Just change `tower.py` and push.
