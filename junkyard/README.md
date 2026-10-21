# Junkyard Nights

The gate is locked and something purple is moving out there. Survive the blobs
with three lives, a sword, and whatever the junk coughs up.

## Controls

| Key | Action |
| --- | --- |
| Arrow keys | walk (you can't pass through the wrecks) |
| Space | swing your sword |
| B | set off a bomb you are carrying |
| P or Esc | pause |

Your sword swings in the direction you are walking, so step towards a blob to
hit it. A swing keeps the direction you started it in, so you can back away
mid-cut without the blade whipping round behind you.

## The yard

- **Blobs** crawl out of the dark and chase you. Touch one and you lose a life;
  you get three, and a few seconds of blinking safety after each hit.
- Bigger blobs take more than one hit. The pale pips under a blob show how much
  is left in it.
- A blob that has just appeared is see-through and harmless until it solidifies.
- Clear every blob in a wave and the next one starts, bigger than the last.

## Things to pick up

Walk over them. They land where a blob died, or get shaken loose when you clear
a wave, and each sits in its own little pool of light so you can spot it.

| | |
| --- | --- |
| 💣 **Bomb** | goes in your pocket; press **B** to blow up every blob in the yard |
| 🗡 **Longer sword** | more reach, up to three times |
| ⚡ **Faster sword** | shorter cooldown between swings, up to four times |

Bombs stack, and the HUD shows how many you are carrying. Once your sword is
fully upgraded, only bombs turn up.

## Rankings

When a run ends you type a name and the score joins a ranking shared by every
player (the same online database the other two games use). The database rules
are in `firebase-rules.json` in the top folder, and the `junkyard-scores`
section of them has to be live before scores can be posted.

The game-over screen shows the top 20, five at a time - scroll with Up / Down,
Page Up / Page Down or the mouse wheel. It starts on your own row.

## Run on your computer

```
pip install -r requirements.txt
python junkyard.py
```

Your own top twenty are kept in `junkyard_scores.json` next to the game (in the
browser they go to the page's own storage instead).
