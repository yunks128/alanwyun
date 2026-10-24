# Castle Keys

Words are falling out of the sky onto your castle! Type them and the wizard on
the castle zaps them with a magic bolt. A typing game for learning the keyboard.

**Play in the browser:** https://alanwyun.com/castle-keys/

## Controls

| Key | Action |
| --- | --- |
| a - z | type the letters of a falling word |
| Backspace | let go of the word you started and pick another |
| Esc | pause (press Enter while paused to end the game) |

The first letter you type picks the word - no two falling words ever start
with the same letter. The word you are on gets a gold border, the letters you
have typed turn green, and the next letter to press is underlined.

## How it goes

- **Type a word before it lands.** Any word that reaches the castle knocks
  part of it down. Each of the six pieces of the castle takes two hits (the
  first one cracks it), so you can miss 12 words. When the whole castle is
  rubble the game is over.
- **Wrong letter?** The word shakes and flashes red, and you just keep going
  with the right key. The word is still remembered for the practice list.
- **Levels** get harder as you go:

| Level | Words |
| --- | --- |
| 1 | three letters: cat, sun, dog |
| 2 | four letters: frog, kite, moon |
| 3 | five letters: apple, horse, pizza |
| 4 | six and seven letters: castle, dragon, rainbow |
| 5 | longer words: elephant, butterfly, chocolate |
| 6 and up | tricky words: rhythm, necessary, encyclopedia |

  Every level has more words and they fall faster. Finishing a level sends the
  builders out to fix one broken piece of the castle.

- **Points:** 10 for every letter, plus 5 more per letter when a word is typed
  with no wrong letters ("perfect"), plus 50 x the level for finishing a level.

## Words to practice

When the castle falls you see every word you missed or typed a wrong letter
in, with what the word means and which key you pressed by mistake. Press W on
the leaderboard screen to see the list again.

The words and their meanings are the `WORDS` list near the top of
`castle_keys.py` - add your own there.

## Rankings

When a game ends you type a name and the score joins a ranking shared by every
player (the same online database the other games use). Each name only appears
once - its best game. The database rules are in `firebase-rules.json` in the
top folder, and the `castle-keys-scores` section of them has to be live before
scores can be posted.

## Run on your computer

```
pip install -r requirements.txt
python castle_keys.py
```

Your own top twenty are kept in `castle_keys_scores.json` next to the game (in
the browser they go to the page's own storage instead).

## How the website is built

Every push to `main` runs `.github/workflows/pages.yml` in the top folder, which
uses [pygbag](https://pygame-web.github.io/) to turn `castle_keys.py` into a web
page and publishes it to GitHub Pages. Just change `castle_keys.py` and push.
