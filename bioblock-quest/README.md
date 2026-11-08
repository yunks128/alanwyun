# BioBlock Quest

Team French Cat's FIRST LEGO League Challenge BIOGLOW Innovation Project page:
how the Palos Verdes blue butterfly depends on a few native plants, and what we
can build to help it come back.

**Open it:** https://alanwyun.com/bioblock-quest/

It is one web page (`index.html`), no build step. Every picture is block art
drawn with code. It is our science project, with a game in it:

1. **Did you know?** Five quiz cards. Tap one to flip it and see the answer.
2. **What is BioBlock Quest?** Says what the page is and links to the parts below.
3. **The game:** plant a field and bring the butterflies back.
4. **Our project:** the problem and our question, what we learned, our idea
   (the Habitat Starter Kit) and how we tested it, and who we told.
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

Each Next season, the weedy grass spreads. A plant touching 2 other plants or
rocks is strong and can't be taken over. The best score and the number of games
played are kept in the browser, and the home page shows the best score.

## Try it on your computer

From the top folder:

```
python3 -m http.server 8765
```

then open http://localhost:8765/bioblock-quest/
