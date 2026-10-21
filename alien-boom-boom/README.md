# Alien Boom Boom

A rocket-versus-aliens arcade game made with Python and pygame.

**Play in your browser:** https://alanwyun.com/alien-boom-boom/

## How to play

- **Arrow keys** move your rocket, **Space** shoots, **B** fires a bomb, **Esc** goes back to the menu.
- Aliens park at the top and shoot red lasers. You have three lives.
- Every third level has a boss. It drops coins when it dies; spend them in the shop.
- The rankings screen holds the top 20, ten at a time - drag the list, use the mouse
  wheel or Up / Down to scroll. It starts on your own row.

A keyboard is needed, so it does not work on phones.

## Run it on your computer

```
python3 -m venv .venv
.venv/bin/pip install pygame
.venv/bin/python alien_boom_boom.py
```

## How the website is built

Every push to `main` runs `.github/workflows/pages.yml` in the top folder, which uses
[pygbag](https://pygame-web.github.io/) to turn the game into a web page and
publishes it to GitHub Pages. In the browser, coins, upgrades and rankings are
saved in that browser only.
