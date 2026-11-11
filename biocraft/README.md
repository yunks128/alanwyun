# Biocraft

Team French Cat's FIRST LEGO League Challenge BIOGLOW Innovation Project page:
how the Palos Verdes blue butterfly depends on a few native plants, and what we
can build to help it come back.

**Open it:** https://alanwyun.com/biocraft/

It is one web page (`index.html`), no build step. Every picture is block art
drawn with code. It is our science project, with a game in it:

1. **Did you know?** Five quiz cards. Tap one to flip it and see the answer.
2. **What is Biocraft?** Says what the page is and links to the parts below.
3. **The game:** plant a field and bring the butterflies back.
4. **Our project:** the problem and our question, what we learned, our idea
   (the Biocraft Starter Kit) and how we tested it, and who we told.
5. **You can help:** what to do at home and the plants in our kit.
6. **Team French Cat**

Boxes with a dashed yellow border (`<span class="edit">`) are spots for the team
to fill in.

## The game

Pick a block (keys 1-6) and tap the field (or use the arrow keys and Enter).
You get 7 blocks a season, for 8 seasons. Flowers bring visiting butterflies;
the right mix of blocks makes animals move in:

| Animal | Needs |
| --- | --- |
| Palos Verdes blue | 4 deerweed blocks all touching |
| Native bees | 3 buckwheat, and bare dirt next to one |
| California gnatcatcher | 4 sagebrush blocks all touching |
| Cactus wren | 2 cactus touching, next to sagebrush |
| Western fence lizard | a rock touching 2 plants |
| Anna's hummingbird | all 4 kinds of plants |

Each Next season, people build one new house or road next to the old ones
(on bare dirt or weeds, or on a lonely plant if there is no room), and the
weedy grass spreads. A plant touching 2 other plants or
rocks is strong and can't be taken over. The best score is kept in the browser, and the home page shows it.

When a game ends, the player can type a name and save it to the **Top habitats**
rankings (`biocraft-scores` in the shared online database). The most animals
wins, and the higher biodiversity score breaks a tie. Each name shows once,
with its best game. The top 20 show under the game and on the home page card.
The rule for it is the `biocraft-scores` section of `firebase-rules.json`, and
like the counter below it has to be published in the Firebase console first.

Every finished game adds 1 to `biocraft-plays` in the shared online database
the other games use, and the page (and the home page card) shows how many games
everyone has played. The rule for it is the `biocraft-plays` section of
`firebase-rules.json` in the top folder, which has to be published in the
Firebase console before the count can go up. Until then the page shows the
games played on that computer.

## Try it on your computer

From the top folder:

```
python3 -m http.server 8765
```

then open http://localhost:8765/biocraft/
