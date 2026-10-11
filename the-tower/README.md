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

## Run on your computer

```
pip install -r requirements.txt
python tower.py
```

## How the website is built

Every push to `main` runs `.github/workflows/pages.yml` in the top folder, which uses
[pygbag](https://pygame-web.github.io/) to turn `tower.py` into a web page and
publishes it to GitHub Pages. Just change `tower.py` and push.
