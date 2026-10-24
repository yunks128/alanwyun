"""Castle Keys - type the words falling from the sky before they smash your castle.

Controls
    a - z                 type the letters of a falling word
    Backspace             let go of the word you started
    Esc                   pause

Words come falling out of the sky towards your castle. Type a word and the
wizard on the castle zaps it with a magic bolt. Any word that reaches the
castle knocks a piece of it down, and when the whole castle is rubble the game
is over.

Level 1 has short, easy words. Every level the words get longer and harder
and fall faster - but finishing a level sends the builders out to fix one
broken piece of the castle.

When the game ends you see every word you missed or typed a wrong letter in,
with what it means, so you can practice it for next time. Then you type a name
and your score joins the ranking shared by every player.
"""
import asyncio
import json
import math
import os
import random
import sys
import threading
import urllib.request

import pygame

WEB = sys.platform == "emscripten"     # running in a browser through pygbag

W, H = 960, 600
FPS = 60
HUD_H = 56
GROUND_Y = H - 26

# The castle is a row of pieces along the bottom; each takes two hits to knock down.
SECTION_W = 160
SECTIONS = ("tower", "wall", "keep", "keep", "wall", "tower")
SECTION_TALL = {"tower": 170, "wall": 104, "keep": 136}
SECTION_HP = 2
ROOF_H = 44                # the pointy roof on an unbroken tower
RUBBLE_H = 22

# Words and how they fall
PLAQUE_H = 44
WORD_FONT = 36
WORDS_FIRST_LEVEL = 10
WORDS_MORE_PER_LEVEL = 2
WORDS_MOST_PER_LEVEL = 24
FALL_SPEED = 26            # pixels a second on level 1 ...
FALL_FASTER = 1.13         # ... times this every level ...
FALL_MOST = 120            # ... up to this
SPAWN_GAP = 3.6            # seconds between words on level 1, shrinking every level
SPAWN_GAP_LEAST = 1.1
LEVEL_BREAK = 3.0          # seconds of calm between levels
LETTER_POINTS = 10
PERFECT_BONUS = 5          # per letter, for a word typed with no wrong letters
LEVEL_BONUS = 50           # times the level just cleared
STUCK_HINT = 3             # wrong letters in a row before the Backspace hint shows

SCORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "castle_keys_scores.json")
SCORE_KEY = "castle-keys-scores"   # browser localStorage key used instead of the file
MAX_RANKINGS = 20
VISIBLE_RANKINGS = 5   # rows shown at once on the game-over screen; the rest scroll
VISIBLE_WORDS = 4      # practice words shown at once on the review screen
RANKING_POOL = 100     # rows pulled from the database before keeping one per name
MAX_NAME_LEN = 16
NAME_KEY_DELAY = 0.8   # keys mashed while the castle falls are ignored this long
# Shared online ranking (the same Firebase database the other games use).
# Leave the address empty to keep rankings on this device only.
LEADERBOARD_URL = "https://alien-boom-boom-default-rtdb.firebaseio.com"
LEADERBOARD_PATH = "/castle-keys-scores.json"
LEADERBOARD_TIMEOUT_S = 5
FUN_NAMES = [
    "Speedy Fingers", "Keyboard Knight", "Captain Caps", "Letter Wizard", "Space Bar Star",
    "Typo Tamer", "Word Wizard", "Sir Types-a-Lot", "Castle Keeper", "Lady Letters",
]

# The words, easiest first. Each level mostly uses its own list, with some from the one before.
WORDS = [
    [   # level 1: three letters
        ("cat", "a small furry pet that says meow"),
        ("dog", "a furry pet that barks and wags its tail"),
        ("sun", "the bright star that gives us daylight"),
        ("hat", "something you wear on your head"),
        ("bed", "the soft place where you sleep at night"),
        ("cup", "a small bowl with a handle that you drink from"),
        ("pig", "a pink farm animal that says oink"),
        ("red", "the color of strawberries and fire trucks"),
        ("run", "to move very fast on your feet"),
        ("big", "large, not small"),
        ("box", "a container with flat sides to keep things in"),
        ("fox", "a wild animal like a dog, with a bushy orange tail"),
        ("hen", "a grown-up girl chicken that lays eggs"),
        ("map", "a drawing that shows where places are"),
        ("jam", "a sweet spread made from fruit"),
        ("egg", "a shell that a baby bird hatches out of"),
        ("bus", "a long vehicle that carries lots of people"),
        ("ant", "a tiny insect that lives in a big group"),
        ("owl", "a bird with big eyes that hoots at night"),
        ("cow", "a farm animal that gives us milk"),
        ("bat", "a furry flying animal that comes out at night"),
        ("net", "strings tied together to catch things"),
        ("pen", "a tool for writing with ink"),
        ("fan", "a machine that blows air to keep you cool"),
        ("mud", "wet, sticky dirt"),
        ("zip", "to close a coat or a bag with a zipper"),
        ("yes", "the word you say when you agree"),
        ("toy", "something children play with"),
        ("sky", "the space above us where the clouds float"),
        ("ice", "water that is frozen hard and cold"),
    ],
    [   # level 2: four letters
        ("fish", "an animal that lives and swims in water"),
        ("frog", "a small green animal that hops and croaks"),
        ("cake", "a sweet baked treat, yummy on birthdays"),
        ("tree", "a tall plant with a trunk, branches and leaves"),
        ("star", "a tiny bright light in the night sky"),
        ("moon", "the big round light we see in the night sky"),
        ("ship", "a very big boat that sails on the sea"),
        ("bird", "an animal with feathers and wings"),
        ("milk", "a white drink that comes from cows"),
        ("rain", "drops of water falling from the clouds"),
        ("snow", "soft white flakes of frozen water"),
        ("kite", "a toy that flies in the wind on a long string"),
        ("ball", "a round toy you can throw, kick or bounce"),
        ("book", "pages of words or pictures that you read"),
        ("door", "you open it to go in or out of a room"),
        ("hand", "the part of your arm with five fingers"),
        ("jump", "to push off the ground up into the air"),
        ("play", "to have fun with games or toys"),
        ("sing", "to make music with your voice"),
        ("blue", "the color of a clear sky"),
        ("gold", "a shiny yellow metal that is worth a lot"),
        ("king", "a man who rules a country"),
        ("duck", "a bird that swims and says quack"),
        ("nest", "a home that birds build for their eggs"),
        ("rock", "a hard piece of stone"),
        ("leaf", "a flat green part that grows on a plant"),
        ("wind", "air that moves and blows things around"),
        ("drum", "an instrument you hit to make a beat"),
        ("bell", "a metal thing that rings"),
        ("lion", "a big wild cat with a fluffy mane"),
    ],
    [   # level 3: five letters
        ("apple", "a round crunchy fruit, red or green"),
        ("house", "a building where a family lives"),
        ("horse", "a big animal that people can ride"),
        ("water", "the clear liquid we drink, found in rivers and seas"),
        ("smile", "the happy shape your mouth makes"),
        ("happy", "feeling glad and good"),
        ("green", "the color of grass and leaves"),
        ("light", "what lets us see, like from the sun or a lamp"),
        ("cloud", "a white fluffy shape floating in the sky"),
        ("beach", "sandy land next to the sea"),
        ("chair", "a seat with a back, for one person"),
        ("brave", "not afraid to do something hard or scary"),
        ("dream", "pictures and stories in your head while you sleep"),
        ("juice", "a drink squeezed out of fruit"),
        ("mouse", "a tiny animal with a long tail and a squeak"),
        ("pizza", "flat bread baked with cheese and toppings"),
        ("plant", "a living thing that grows in the soil"),
        ("river", "a long stream of water flowing to the sea"),
        ("sheep", "a farm animal covered in soft wool"),
        ("tiger", "a big orange wild cat with black stripes"),
        ("train", "a line of cars that runs on tracks"),
        ("whale", "the biggest animal in the sea"),
        ("queen", "a woman who rules a country"),
        ("magic", "tricks that seem impossible"),
        ("candy", "a sweet treat made with sugar"),
        ("clock", "a machine that shows what time it is"),
        ("bread", "food baked from flour, used for sandwiches"),
        ("earth", "the planet we all live on"),
        ("shell", "the hard cover of a snail, a turtle or an egg"),
        ("storm", "strong wind and rain, sometimes with thunder"),
    ],
    [   # level 4: six and seven letters
        ("castle", "a big strong building with towers and walls"),
        ("dragon", "a make-believe monster with wings that breathes fire"),
        ("rabbit", "a small furry animal with long ears that hops"),
        ("banana", "a long yellow fruit that monkeys love"),
        ("garden", "a place where flowers or vegetables grow"),
        ("planet", "a huge round world that travels around a star"),
        ("rocket", "a machine that blasts up into space"),
        ("pencil", "a wooden stick with lead inside, for writing"),
        ("friend", "someone you like, who likes you too"),
        ("school", "the place where children go to learn"),
        ("monkey", "a clever animal that climbs trees"),
        ("turtle", "an animal with a hard shell on its back"),
        ("jungle", "a hot, thick forest full of plants and animals"),
        ("winter", "the coldest season of the year"),
        ("summer", "the hottest season of the year"),
        ("wizard", "a person in stories who can do magic"),
        ("knight", "a soldier in armor who rides a horse"),
        ("silver", "a shiny gray metal"),
        ("bridge", "something built to cross over a river or a road"),
        ("forest", "a big area covered with lots of trees"),
        ("island", "land with water all around it"),
        ("puzzle", "a game or a problem you have to figure out"),
        ("rainbow", "a curve of colors in the sky after rain"),
        ("giraffe", "a tall animal with a very long neck"),
        ("penguin", "a black and white bird that swims but cannot fly"),
        ("dolphin", "a clever sea animal that loves to jump"),
        ("thunder", "the loud boom you hear in a storm"),
        ("kitchen", "the room where food is cooked"),
        ("blanket", "a big soft cover that keeps you warm"),
        ("library", "a place full of books that you can borrow"),
    ],
    [   # level 5: longer words
        ("elephant", "a huge gray animal with a long trunk"),
        ("dinosaur", "a giant animal that lived long, long ago"),
        ("mountain", "a very, very tall hill of rock"),
        ("sandwich", "food between two slices of bread"),
        ("treasure", "gold, jewels and other precious things"),
        ("princess", "the daughter of a king or a queen"),
        ("butterfly", "an insect with big, colorful wings"),
        ("beautiful", "very pretty to look at"),
        ("adventure", "an exciting trip or experience"),
        ("chocolate", "a sweet brown treat made from cocoa beans"),
        ("umbrella", "a cover you hold over your head in the rain"),
        ("kangaroo", "an Australian animal that hops and has a pouch"),
        ("volcano", "a mountain that can blow out hot melted rock"),
        ("alphabet", "all the letters from A to Z, in order"),
        ("hospital", "a place where doctors and nurses help sick people"),
        ("computer", "a machine that stores information and runs games"),
        ("birthday", "the day of the year when you were born"),
        ("together", "with each other"),
        ("question", "something you ask to find out an answer"),
        ("favorite", "the one you like the best"),
        ("surprise", "something you did not expect"),
        ("scientist", "a person who studies how the world works"),
        ("astronaut", "a person who travels into space"),
        ("telescope", "a tube that makes faraway things look close"),
        ("crocodile", "a big reptile with sharp teeth and a long tail"),
        ("invisible", "impossible to see"),
        ("celebrate", "to do something fun for a special day"),
        ("important", "something that matters a lot"),
        ("different", "not the same"),
        ("vegetable", "a plant that we eat, like a carrot or peas"),
    ],
    [   # level 6 and up: tricky words
        ("imagination", "making up pictures and ideas in your mind"),
        ("temperature", "how hot or cold something is"),
        ("mysterious", "strange and hard to explain"),
        ("necessary", "something that you really need"),
        ("rhythm", "a beat in music that repeats"),
        ("knowledge", "the things you know and have learned"),
        ("avalanche", "a huge amount of snow sliding down a mountain"),
        ("carnivore", "an animal that eats meat"),
        ("dangerous", "something that could hurt you"),
        ("gymnastics", "a sport with flips, jumps and balancing"),
        ("hurricane", "a giant storm with very strong winds"),
        ("microscope", "a tool that makes tiny things look big"),
        ("nocturnal", "awake at night and asleep during the day"),
        ("orchestra", "a big group of musicians playing together"),
        ("photograph", "a picture taken with a camera"),
        ("restaurant", "a place where you pay to eat a meal"),
        ("skeleton", "all the bones inside your body"),
        ("vocabulary", "all the words that you know"),
        ("calendar", "a chart of the days, weeks and months"),
        ("separate", "to pull things apart"),
        ("enormous", "very, very big"),
        ("delicious", "tastes really good"),
        ("courageous", "very brave"),
        ("peculiar", "strange or unusual"),
        ("magnificent", "wonderful and grand"),
        ("exhausted", "very, very tired"),
        ("environment", "the land, water and air all around us"),
        ("experiment", "a test to find out something new"),
        ("caterpillar", "a crawly bug that turns into a butterfly"),
        ("encyclopedia", "a book full of facts about everything"),
    ],
]
OLDER_WORD_CHANCE = 0.25   # how often a level borrows a word from the list before

STONE = (196, 190, 210)
STONE_DARK = (138, 130, 160)
STONE_LIGHT = (224, 220, 236)
ROOF = (214, 64, 84)
WOOD = (120, 72, 40)
GRASS = (88, 168, 76)
INK = (30, 24, 54)
WHITE = (250, 248, 240)
GOLD = (255, 214, 90)
TYPED = (130, 236, 120)
ROBE = (66, 96, 220)
HAT = (128, 64, 200)

# sky colours (top, bottom) by level
SKY = [
    (1, (110, 186, 240), (200, 234, 250)),
    (3, (238, 150, 110), (255, 214, 160)),
    (5, (74, 52, 130), (190, 110, 140)),
    (7, (14, 14, 46), (50, 36, 90)),
]


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * clamp(t, 0, 1)


def mix(c1, c2, t):
    return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))


def http(method, url, body=None):
    """Send one web request and return the reply text, or None if it failed."""
    if WEB:
        # in a browser, ask the page's own JavaScript to make the request
        from platform import window
        script = (
            "(function(){try{var x=new XMLHttpRequest();"
            f"x.open({json.dumps(method)},{json.dumps(url)},false);"
            f"x.send({json.dumps(body) if body is not None else 'null'});"
            "return x.status+'\\n'+x.responseText;}catch(e){return '0\\n';}})()"
        )
        status, _, text = str(window.eval(script)).partition("\n")
        return text if status == "200" else None
    try:
        data = body.encode() if body is not None else None
        request = urllib.request.Request(url, data=data, method=method)
        with urllib.request.urlopen(request, timeout=LEADERBOARD_TIMEOUT_S) as reply:
            return reply.read().decode()
    except (OSError, ValueError):
        return None


def best_per_name(rankings):
    """One row per player, their best, so there can never be two Bobs on the board.

    Names are matched ignoring case and spacing, and rows are (score, level, name),
    so the plain tuple comparison keeps the highest score.
    """
    best = {}
    for row in rankings:
        key = " ".join(row[2].split()).lower()
        if key not in best or row > best[key]:
            best[key] = row
    return sorted(best.values(), reverse=True)


def fetch_online_rankings():
    """Top (score, level, name) rows from the shared ranking, best first, or None if it can't be reached."""
    query = f"?orderBy=%22score%22&limitToLast={RANKING_POOL}"
    try:
        rows = json.loads(http("GET", LEADERBOARD_URL + LEADERBOARD_PATH + query) or "")
    except ValueError:
        return None
    if rows is None:
        return []  # reachable, but nobody has a score yet
    if not isinstance(rows, dict):
        return None
    rankings = []
    for row in rows.values():
        if isinstance(row, dict) and isinstance(row.get("score"), int) and isinstance(row.get("level"), int):
            rankings.append((row["score"], row["level"], str(row.get("name", "?"))[:MAX_NAME_LEN]))
    return best_per_name(rankings)[:MAX_RANKINGS]


# --------------------------------------------------------------- pretty bits


def make_hills():
    """Two rows of rolling hills behind the castle."""
    rng = random.Random(5)
    s = pygame.Surface((W, 220), pygame.SRCALPHA)
    for color, base, size in (((130, 196, 120), 90, 110), ((98, 176, 92), 150, 90)):
        x = -40
        while x < W + 40:
            r = rng.randint(size // 2, size)
            pygame.draw.circle(s, color, (x, base + rng.randint(0, 30)), r)
            x += rng.randint(r // 2, r)
        pygame.draw.rect(s, color, (0, base + 20, W, 220 - base))
    return s


def make_glow(radius, color):
    """A soft round light for the add-blend, fading out to black at the edge."""
    s = pygame.Surface((radius * 2, radius * 2))
    for i in range(radius, 0, -2):
        k = (1 - i / radius) ** 2
        pygame.draw.circle(s, (int(color[0] * k), int(color[1] * k), int(color[2] * k)), (radius, radius), i)
    return s


def wrap(font, text, width):
    """Split text into lines no wider than width."""
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and font.size(trial)[0] > width:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line] if line else lines


class Word:
    def __init__(self, text, meaning, x, speed, width):
        self.text, self.meaning = text, meaning
        self.x = float(x)              # centre
        self.y = float(HUD_H - PLAQUE_H)   # top, sliding in from under the HUD
        self.speed = speed
        self.w = width
        self.typed = 0                 # letters typed so far
        self.mistakes = 0
        self.wrong_t = 0.0             # flashes red after a wrong letter
        self.t = random.uniform(0, math.tau)

    @property
    def rect(self):
        return pygame.Rect(round(self.x - self.w / 2), round(self.y), self.w, PLAQUE_H)


# ------------------------------------------------------------------ the game


class Game:
    def __init__(self, screen):
        self.screen = screen
        self.hills = make_hills()
        self.glow = make_glow(46, (255, 150, 60))
        self.wand_glow = make_glow(30, (160, 200, 255))
        rng = random.Random(9)
        self.stars = [(rng.randint(0, W), rng.randint(HUD_H, H - 160), rng.choice((1, 1, 2))) for _ in range(90)]
        self.clouds = [[rng.uniform(0, W), rng.randint(HUD_H + 30, 300), rng.randint(26, 46)] for _ in range(6)]
        self.fonts = {}
        self.time = 0.0
        self.state = "title"           # title, play, ending, review, name, dead
        self.scroll = 0                # first leaderboard row shown
        self.scroll_follow = True      # keep your own row in view until you scroll yourself
        self.review_scroll = 0
        self.saved = False             # the name has been typed and the score saved
        self.name = ""
        self.name_fresh = False
        self.name_time = 0.0
        self.mine = None
        self.online = None
        self.scores = self.load_scores()
        self.new_game()
        self.refresh_online()

    # ---------------------------------------------------------------- set up

    def new_game(self):
        self.hp = [SECTION_HP] * len(SECTIONS)
        self.words = []
        self.target = None
        self.score = 0
        self.level = 1
        self.to_spawn = WORDS_FIRST_LEVEL
        self.spawn_t = 1.0
        self.break_t = 0.0
        self.streak = 0
        self.best_streak = 0
        self.zapped = 0
        self.keys_right = 0
        self.keys_wrong = 0
        self.wrong_in_a_row = 0
        self.trouble = {}              # word -> what went wrong with it, for the review
        self.recent = []               # words used lately, so they don't come round again too soon
        self.particles = []
        self.popups = []
        self.bolts = []
        self.zap_t = 0.0
        self.miss_t = 0.0
        self.banner = ""
        self.sub_banner = ""
        self.banner_t = 0.0
        self.shake = 0.0
        self.paused = False
        self.new_best = False
        self.end_t = 0.0
        self.saved = False
        self.review_scroll = 0
        self.say(f"LEVEL {self.level}", "Type the words before they land!")

    def say(self, msg, sub=""):
        self.banner, self.sub_banner, self.banner_t = msg, sub, 2.6

    def section_x(self, i):
        return i * SECTION_W

    def section_at(self, x):
        return clamp(int(x // SECTION_W), 0, len(SECTIONS) - 1)

    def section_height(self, i):
        """How tall piece i of the castle stands right now."""
        if self.hp[i] <= 0:
            return RUBBLE_H
        tall = SECTION_TALL[SECTIONS[i]]
        return tall if self.hp[i] >= SECTION_HP else round(tall * 0.62)

    def section_top(self, i):
        """Where a falling word hits piece i, roof included."""
        top = GROUND_Y - self.section_height(i)
        if SECTIONS[i] == "tower" and self.hp[i] >= SECTION_HP:
            top -= ROOF_H
        return top

    @property
    def fall_speed(self):
        return min(FALL_SPEED * FALL_FASTER ** (self.level - 1), FALL_MOST)

    def pick_word(self):
        """A word for this level whose first letter isn't on any word already falling,
        so the first key you press always says which word you mean."""
        taken = {w.text[0] for w in self.words}
        tier = min(self.level, len(WORDS)) - 1
        lists = [WORDS[tier]]
        if tier > 0 and random.random() < OLDER_WORD_CHANCE:
            lists = [WORDS[tier - 1]]
        lists.append(WORDS[tier])      # fall back on this level's own words
        for words in lists:
            choices = [w for w in words if w[0][0] not in taken and w[0] not in self.recent]
            if choices:
                return random.choice(choices)
        return None

    def spawn_word(self):
        picked = self.pick_word()
        standing = [i for i, hp in enumerate(self.hp) if hp > 0]
        if not picked or not standing:
            return False
        text, meaning = picked
        width = self.font(WORD_FONT).size(text)[0] + 28
        # aim it at a piece of the castle that is still standing, away from the
        # words that only just started falling
        for _ in range(20):
            i = random.choice(standing)
            x = self.section_x(i) + SECTION_W / 2 + random.uniform(-50, 50)
            x = clamp(x, width / 2 + 8, W - width / 2 - 8)
            if all(abs(x - w.x) > (width + w.w) / 2 + 10 or w.y > HUD_H + 110 for w in self.words):
                break
        else:
            return False
        speed = self.fall_speed * random.uniform(0.9, 1.1)
        self.words.append(Word(text, meaning, x, speed, width))
        self.recent = (self.recent + [text])[-12:]
        return True

    # ------------------------------------------------------------ the scores

    @property
    def best(self):
        return max((row[0] for row in self.scores), default=0)

    def load_scores(self):
        """This device's top scores as (score, level, name), plus the last name used."""
        try:
            if WEB:
                from platform import window
                data = json.loads(window.localStorage.getItem(SCORE_KEY) or "[]")
            else:
                with open(SCORE_FILE) as f:
                    data = json.load(f)
            if isinstance(data, dict):
                self.name = str(data.get("name", ""))[:MAX_NAME_LEN]
                data = data["scores"]
            return [(int(row[0]), int(row[1]), str(row[2]) if len(row) > 2 else "") for row in data]
        except Exception:
            return []

    def ask_name(self):
        self.mine = None
        if not self.name:
            self.name = random.choice(FUN_NAMES)
        self.name_fresh = True
        self.name_time = self.time
        self.state = "name"

    def save_score(self):
        """Add this game to this device's top scores and to the shared ranking."""
        self.name = self.name.strip() or random.choice(FUN_NAMES)
        level = clamp(self.level, 1, 999)       # the database keeps this between 1 and 999
        self.mine = (self.score, level, self.name)
        self.new_best = self.score > self.best
        self.scores = best_per_name(self.scores + [self.mine])[:MAX_RANKINGS]
        try:
            save = json.dumps({"scores": self.scores, "name": self.name})
            if WEB:
                from platform import window
                window.localStorage.setItem(SCORE_KEY, save)
            else:
                with open(SCORE_FILE, "w") as f:
                    f.write(save)
        except Exception:
            pass       # a high score is never worth crashing over
        self.refresh_online({"name": self.name, "score": self.score, "level": level})
        self.saved = True
        self.scroll = 0
        self.scroll_follow = True
        self.state = "dead"

    def refresh_online(self, new_entry=None):
        """Upload new_entry (if any) and download the shared ranking."""
        if not LEADERBOARD_URL:
            return

        def work():
            rankings = None
            if not new_entry or http("POST", LEADERBOARD_URL + LEADERBOARD_PATH,
                                     json.dumps(new_entry)) is not None:
                rankings = fetch_online_rankings()
            self.online = rankings
            print("online ranking:", "unavailable" if rankings is None else f"{len(rankings)} scores")

        if WEB:
            work()  # browsers have no threads here; the request is quick
        else:
            threading.Thread(target=work, daemon=True).start()

    def rankings(self):
        """The shared ranking when it is available, otherwise this device's own."""
        return self.scores if self.online is None else self.online

    # ----------------------------------------------------------------- input

    def on_key(self, key, char=""):
        confirm = key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
        enter = key in (pygame.K_RETURN, pygame.K_KP_ENTER)
        if self.state == "title":
            if confirm:
                self.state = "play"
        elif self.state == "play":
            if key == pygame.K_ESCAPE:
                self.paused = not self.paused
            elif self.paused:
                if enter:
                    self.paused = False
                    self.castle_falls()
            elif pygame.K_a <= key <= pygame.K_z:
                self.type_letter(chr(key))
            elif key == pygame.K_BACKSPACE and self.target:
                self.target.typed = 0
                self.target = None
                self.wrong_in_a_row = 0
        elif self.state == "review":
            if key in (pygame.K_UP, pygame.K_DOWN, pygame.K_PAGEUP, pygame.K_PAGEDOWN):
                step = {pygame.K_UP: -1, pygame.K_DOWN: 1,
                        pygame.K_PAGEUP: -VISIBLE_WORDS, pygame.K_PAGEDOWN: VISIBLE_WORDS}[key]
                self.scroll_review(step)
            elif enter and self.time - self.name_time >= NAME_KEY_DELAY:
                if self.saved:
                    self.state = "dead"
                else:
                    self.ask_name()
        elif self.state == "name":
            if self.time - self.name_time < NAME_KEY_DELAY:
                return                  # ignore whatever was still being typed
            if enter:
                self.save_score()
            elif key == pygame.K_DOWN:
                self.name = random.choice([n for n in FUN_NAMES if n != self.name])
                self.name_fresh = True
            elif key == pygame.K_BACKSPACE:
                self.name = "" if self.name_fresh else self.name[:-1]
                self.name_fresh = False
            elif char and char.isprintable() and (char != " " or (self.name and not self.name_fresh)):
                if self.name_fresh:
                    self.name = ""
                    self.name_fresh = False
                self.name = (self.name + char)[:MAX_NAME_LEN]
        elif self.state == "dead":
            if key == pygame.K_UP:
                self.scroll_rankings(-1)
            elif key == pygame.K_DOWN:
                self.scroll_rankings(1)
            elif key == pygame.K_PAGEUP:
                self.scroll_rankings(-VISIBLE_RANKINGS)
            elif key == pygame.K_PAGEDOWN:
                self.scroll_rankings(VISIBLE_RANKINGS)
            elif key == pygame.K_w:
                self.review_scroll = 0
                self.name_time = self.time
                self.state = "review"
            elif confirm:
                self.new_game()
                self.state = "play"
            elif key in (pygame.K_ESCAPE, pygame.K_q):
                if WEB:                 # a browser tab can't be closed, so go back to the title
                    self.new_game()
                    self.state = "title"
                else:
                    pygame.event.post(pygame.event.Event(pygame.QUIT))

    def on_wheel(self, rows):
        if self.state == "review":
            self.scroll_review(rows)
        else:
            self.scroll_rankings(rows)

    def scroll_rankings(self, rows):
        if self.state != "dead":
            return
        most = max(0, len(self.rankings()[:MAX_RANKINGS]) - VISIBLE_RANKINGS)
        self.scroll = clamp(self.scroll + rows, 0, most)
        self.scroll_follow = False

    def scroll_review(self, rows):
        most = max(0, len(self.trouble) - VISIBLE_WORDS)
        self.review_scroll = clamp(self.review_scroll + rows, 0, most)

    def type_letter(self, letter):
        if self.target not in self.words:
            self.target = None
        if self.target is None:
            # the first letter picks the word (no two falling words start the same way)
            starts = [w for w in self.words if w.text[0] == letter]
            if not starts:
                self.keys_wrong += 1
                self.miss_t = 0.35
                return
            self.target = max(starts, key=lambda w: w.y)
        word = self.target
        need = word.text[word.typed]
        if letter != need:
            self.keys_wrong += 1
            self.wrong_in_a_row += 1
            word.mistakes += 1
            word.wrong_t = 0.35
            self.streak = 0
            if word.text not in self.trouble:
                self.trouble[word.text] = {"meaning": word.meaning, "missed": False,
                                           "slip": f"you pressed {letter.upper()} instead of {need.upper()}"}
            return
        self.keys_right += 1
        self.wrong_in_a_row = 0
        word.typed += 1
        if word.typed == len(word.text):
            self.zap(word)

    def zap(self, word):
        """The wizard blasts a finished word out of the sky."""
        self.words.remove(word)
        self.target = None
        self.zapped += 1
        n = len(word.text)
        points = n * LETTER_POINTS + (n * PERFECT_BONUS if word.mistakes == 0 else 0)
        if word.mistakes == 0:
            self.streak += 1
            self.best_streak = max(self.best_streak, self.streak)
        self.score += points
        cx, cy = word.rect.center
        wx, wy = self.wand_tip()
        self.bolts.append([wx, wy, cx, cy, 0.22])
        self.zap_t = 0.3
        self.burst(cx, cy, GOLD, 22)
        self.burst(cx, cy, (160, 210, 255), 14)
        label = f"+{points}"
        if word.mistakes == 0 and self.streak and self.streak % 5 == 0:
            label = f"{self.streak} PERFECT IN A ROW!"
        elif word.mistakes == 0:
            label += "  PERFECT!"
        self.popups.append([cx, cy - 10, label, 1.0])

    # ---------------------------------------------------------------- update

    def update(self, dt, keys):
        self.time += dt
        self.banner_t = max(0, self.banner_t - dt)
        self.shake = max(0, self.shake - dt * 2.5)
        self.miss_t = max(0, self.miss_t - dt)
        self.zap_t = max(0, self.zap_t - dt)
        for cloud in self.clouds:
            cloud[0] = (cloud[0] + 80 + dt * 8) % (W + 160) - 80   # drift right, wrap round off-screen
        if self.state not in ("play", "ending") or self.paused:
            return
        self.move_words(dt)
        self.fade_effects(dt)
        if self.state == "ending":
            self.end_t += dt
            if self.end_t > 2.6:
                self.words.clear()
                self.review_scroll = 0
                self.name_time = self.time
                self.state = "review"
            return

        # --- the level: drop its words one by one, then have a breather and fix the castle
        if self.break_t > 0:
            self.break_t -= dt
            if self.break_t <= 0:
                self.level += 1
                self.to_spawn = min(WORDS_FIRST_LEVEL + WORDS_MORE_PER_LEVEL * (self.level - 1),
                                    WORDS_MOST_PER_LEVEL)
                self.spawn_t = 0.5
                self.say(f"LEVEL {self.level}", "Longer words, falling faster!")
            return
        if self.to_spawn > 0:
            self.spawn_t -= dt
            room = len(self.words) < 3 + self.level // 2
            if self.spawn_t <= 0 and room:
                if self.spawn_word():
                    self.to_spawn -= 1
                    self.spawn_t = max(SPAWN_GAP_LEAST, SPAWN_GAP * 0.9 ** (self.level - 1))
                else:
                    self.spawn_t = 0.3      # no room up there just now; try again in a moment
        elif not self.words:
            self.level_cleared()

    def level_cleared(self):
        bonus = LEVEL_BONUS * self.level
        self.score += bonus
        self.break_t = LEVEL_BREAK
        broken = [i for i, hp in enumerate(self.hp) if hp < SECTION_HP]
        if broken:
            i = min(broken, key=lambda k: self.hp[k])
            self.hp[i] += 1
            x = self.section_x(i) + SECTION_W / 2
            self.burst(x, self.section_top(i), GOLD, 26)
            self.say(f"LEVEL {self.level} DONE!  +{bonus}", "The builders fixed part of your castle")
        else:
            self.say(f"LEVEL {self.level} DONE!  +{bonus}", "Your castle is as good as new")

    def move_words(self, dt):
        for word in self.words[:]:
            word.t += dt
            word.wrong_t = max(0, word.wrong_t - dt)
            word.y += word.speed * dt
            if random.random() < 0.5:    # sparks off the fireball it rides on
                self.particles.append([word.x + random.uniform(-10, 10), word.y - 6,
                                       random.uniform(-20, 20), random.uniform(-70, -30),
                                       random.uniform(0.2, 0.45), random.choice(((255, 200, 90), (255, 130, 60)))])
            i = self.section_at(word.x)
            if word.y + PLAQUE_H >= self.section_top(i):
                self.crash(word, i)

    def crash(self, word, i):
        """A word nobody typed lands on the castle."""
        self.words.remove(word)
        if self.target is word:
            self.target = None
        self.streak = 0
        entry = self.trouble.setdefault(word.text, {"meaning": word.meaning, "slip": None})
        entry["missed"] = True
        x, y = word.x, self.section_top(i)
        if self.state != "play":
            self.burst(x, y, STONE_DARK, 10)
            return
        if self.hp[i] > 0:
            self.hp[i] -= 1
            self.shake = 0.8
            self.burst(x, y, STONE, 26)
            self.burst(x, y, (255, 150, 60), 16)
            self.popups.append([x, y - 30, "CRASH!" if self.hp[i] else "BOOM!", 1.0])
        else:
            self.burst(x, y, STONE_DARK, 12)  # only rubble left there to land on
        if not any(self.hp):
            self.castle_falls()

    def castle_falls(self):
        self.state = "ending"
        self.end_t = 0.0
        self.target = None
        self.shake = 1.2
        for i in range(len(SECTIONS)):
            self.hp[i] = 0
            self.burst(self.section_x(i) + SECTION_W / 2, GROUND_Y - 40, STONE, 20)
        for word in self.words:      # whatever was still falling counts as missed too
            entry = self.trouble.setdefault(word.text, {"meaning": word.meaning, "slip": None})
            entry["missed"] = True
            word.speed = max(word.speed, 220)

    # --------------------------------------------------------------- effects

    def burst(self, x, y, color, n):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = random.uniform(50, 260)
            self.particles.append([x, y, math.cos(a) * v, math.sin(a) * v - 60,
                                   random.uniform(0.3, 0.8), color])

    def fade_effects(self, dt):
        for part in self.particles[:]:
            part[0] += part[2] * dt
            part[1] += part[3] * dt
            part[3] += 360 * dt
            part[4] -= dt
            if part[4] <= 0:
                self.particles.remove(part)
        for pop in self.popups[:]:
            pop[1] -= 36 * dt
            pop[3] -= dt
            if pop[3] <= 0:
                self.popups.remove(pop)
        for bolt in self.bolts[:]:
            bolt[4] -= dt
            if bolt[4] <= 0:
                self.bolts.remove(bolt)

    # ------------------------------------------------------------------ draw

    def font(self, size):
        if size not in self.fonts:
            self.fonts[size] = pygame.font.Font(None, size)
        return self.fonts[size]

    def text(self, msg, size, color, pos, anchor="topleft"):
        surf = self.font(size).render(str(msg), True, color)
        self.screen.blit(surf, surf.get_rect(**{anchor: pos}))

    def draw(self):
        self.draw_sky()
        self.screen.blit(self.hills, (0, GROUND_Y - 200))
        self.draw_castle()
        self.draw_wizard()
        pygame.draw.rect(self.screen, GRASS, (0, GROUND_Y, W, H - GROUND_Y))
        pygame.draw.rect(self.screen, (120, 196, 96), (0, GROUND_Y, W, 5))
        for word in self.words:
            self.draw_word(word)
        self.draw_bolts()
        self.draw_particles()
        for pop in self.popups:
            self.text(pop[2], 32, WHITE, (pop[0], round(pop[1])), "center")
        if self.state != "title":
            self.draw_hud()
        if self.state == "play" and not self.paused:
            if self.banner_t > 0:
                self.text(self.banner, 72, WHITE, (W // 2, HUD_H + 110), "center")
                self.text(self.sub_banner, 32, GOLD, (W // 2, HUD_H + 160), "center")
            if self.wrong_in_a_row >= STUCK_HINT and self.target:
                self.text("Stuck? Press Backspace to pick another word", 28, WHITE,
                          (W // 2, GROUND_Y + 13), "center")
        if self.state == "ending" and self.end_t > 0.5:
            self.text("THE CASTLE HAS FALLEN!", 72, WHITE, (W // 2, HUD_H + 120), "center")
        if self.state == "title":
            self.draw_title()
        elif self.state == "review":
            self.draw_review()
        elif self.state == "name":
            self.draw_name()
        elif self.state == "dead":
            self.draw_over()
        elif self.paused:
            self.dim()
            self.text("PAUSED", 80, WHITE, (W // 2, H // 2 - 40), "center")
            self.text("Esc to carry on", 32, (210, 210, 220), (W // 2, H // 2 + 24), "center")
            self.text("Enter to end the game", 28, (170, 170, 190), (W // 2, H // 2 + 62), "center")
        if self.shake > 0:
            dx, dy = random.randint(-6, 6) * self.shake, random.randint(-4, 4) * self.shake
            self.screen.scroll(int(dx), int(dy))

    def draw_sky(self):
        scr = self.screen
        level = self.level if self.state != "title" else 1
        top, bottom = SKY[-1][1], SKY[-1][2]
        for (l1, t1, b1), (l2, t2, b2) in zip(SKY, SKY[1:]):
            if l1 <= level < l2:
                k = (level - l1) / (l2 - l1)
                top, bottom = mix(t1, t2, k), mix(b1, b2, k)
                break
        bands = 30
        for i in range(bands):
            scr.fill(mix(top, bottom, i / (bands - 1)), (0, i * H // bands, W, H // bands + 1))
        night = clamp((level - 4) / 3, 0, 1)
        if night > 0:
            for i, (x, y, size) in enumerate(self.stars):
                twinkle = 0.7 + 0.3 * math.sin(self.time * 2 + i)
                pygame.draw.circle(scr, mix(top, WHITE, night * twinkle), (x, y), size)
            pygame.draw.circle(scr, mix(top, (250, 246, 220), night), (820, 120), 34)
            pygame.draw.circle(scr, mix(top, (226, 222, 196), night), (808, 112), 7)
        if night < 1:
            pygame.draw.circle(scr, mix((255, 230, 120), top, night), (140, 130), 40)
        for x, y, r in self.clouds:
            color = mix(top, WHITE, 0.8 * (1 - night * 0.7))
            for dx, dy, k in ((0, 0, 1), (r * 0.9, 6, 0.75), (-r * 0.9, 8, 0.7)):
                pygame.draw.circle(scr, color, (round(x + dx), y + dy), round(r * k))

    def draw_castle(self):
        scr = self.screen
        for i, kind in enumerate(SECTIONS):
            hp = self.hp[i]
            left = self.section_x(i)
            area = pygame.Rect(left, 0, SECTION_W, GROUND_Y)
            if hp <= 0:
                self.draw_rubble(left, i)
                continue
            tall = self.section_height(i)
            top = GROUND_Y - tall
            inset = 18 if kind == "tower" else 0
            body = pygame.Rect(left + inset, top, SECTION_W - inset * 2, tall)
            scr.set_clip(area)
            if hp >= SECTION_HP:
                pygame.draw.rect(scr, STONE, body)
                for mx in range(body.left, body.right, 26):     # battlements along the top
                    pygame.draw.rect(scr, STONE, (mx + 2, top - 16, 14, 17))
                    pygame.draw.rect(scr, STONE_DARK, (mx + 2, top - 16, 14, 17), 2)
            else:
                # broken off: a jagged top instead of battlements
                rng = random.Random(i * 7 + 1)
                pts = [(body.left, GROUND_Y), (body.left, top + rng.randint(0, 14))]
                for x in range(body.left + 20, body.right, 20):
                    pts.append((x, top + rng.randint(-6, 18)))
                pts += [(body.right, top + rng.randint(0, 14)), (body.right, GROUND_Y)]
                pygame.draw.polygon(scr, STONE, pts)
            self.draw_bricks(body, i)
            pygame.draw.line(scr, STONE_LIGHT, (body.left + 3, top + 4), (body.left + 3, GROUND_Y), 3)
            pygame.draw.line(scr, STONE_DARK, (body.right - 2, top), (body.right - 2, GROUND_Y), 3)
            if kind == "tower":
                slit = pygame.Rect(body.centerx - 6, top + 34, 12, 34)
                pygame.draw.rect(scr, INK, slit, border_radius=6)
                if hp >= SECTION_HP:
                    roof = [(body.left - 10, top - 14), (body.centerx, top - 14 - ROOF_H), (body.right + 10, top - 14)]
                    pygame.draw.polygon(scr, ROOF, roof)
                    pygame.draw.polygon(scr, (170, 40, 64), roof, 3)
                    pole = (body.centerx, top - 14 - ROOF_H)
                    pygame.draw.line(scr, INK, pole, (pole[0], pole[1] - 26), 3)
                    wave = math.sin(self.time * 5 + i) * 4
                    flag = [(pole[0], pole[1] - 26), (pole[0] + 26, pole[1] - 20 + wave), (pole[0], pole[1] - 13)]
                    pygame.draw.polygon(scr, GOLD, flag)
            elif kind == "keep":
                # half of the gate sits in each of the two middle pieces
                gate = pygame.Rect(W // 2 - 40, GROUND_Y - 66, 80, 66)
                pygame.draw.rect(scr, WOOD, gate.inflate(0, -20).move(0, 10))
                pygame.draw.ellipse(scr, WOOD, (gate.x, gate.y, gate.w, 40))
                for gx in range(gate.left + 12, gate.right, 16):
                    pygame.draw.line(scr, (86, 50, 28), (gx, gate.y + 6), (gx, GROUND_Y), 3)
                if tall > 100:
                    win = pygame.Rect(body.centerx - 10 + (18 if i == 2 else -18), top + 26, 20, 28)
                    pygame.draw.rect(scr, (255, 220, 120) if self.level >= 4 else INK, win, border_radius=10)
            if hp < SECTION_HP:          # cracks
                rng = random.Random(i * 13 + 3)
                for _ in range(3):
                    x, y = body.left + rng.randint(16, body.w - 16), top + rng.randint(20, max(21, tall - 30))
                    pts = [(x, y)]
                    for _ in range(4):
                        x += rng.randint(-10, 10)
                        y += rng.randint(6, 12)
                        pts.append((x, y))
                    pygame.draw.lines(scr, INK, False, pts, 2)
            scr.set_clip(None)

    def draw_bricks(self, body, seed):
        scr = self.screen
        row = 0
        for y in range(GROUND_Y - 18, body.top, -18):
            pygame.draw.line(scr, STONE_DARK, (body.left, y), (body.right, y), 1)
            shift = 18 if row % 2 else 0
            for x in range(body.left + shift, body.right, 36):
                pygame.draw.line(scr, STONE_DARK, (x, y), (x, y + 18), 1)
            row += 1

    def draw_rubble(self, left, i):
        rng = random.Random(i * 5 + 11)
        for _ in range(14):
            r = rng.randint(7, 15)
            x = left + rng.randint(14, SECTION_W - 14)
            y = GROUND_Y - rng.randint(0, RUBBLE_H - 4)
            pygame.draw.circle(self.screen, rng.choice((STONE, STONE_DARK, (170, 164, 186))), (x, y), r)
        if self.state == "ending" or rng.random() < 0.7:
            # a wisp of smoke curling up from the rubble
            k = (self.time * 0.6 + i * 0.37) % 1
            pygame.draw.circle(self.screen, (120, 116, 130), (left + 80 + round(math.sin(k * 6) * 10),
                                                              round(GROUND_Y - 20 - k * 60)), round(6 + k * 10))

    def wand_tip(self):
        x, feet = self.wizard_spot()
        raised = self.zap_t > 0
        return (x + 22, feet - (66 if raised else 44))

    def wizard_spot(self):
        """The wizard stands on the taller of the two middle pieces of the castle."""
        feet = min(GROUND_Y - self.section_height(2), GROUND_Y - self.section_height(3)) - 2
        return W // 2, feet

    def draw_wizard(self):
        scr = self.screen
        x, feet = self.wizard_spot()
        pygame.draw.polygon(scr, ROBE, [(x - 16, feet), (x, feet - 40), (x + 16, feet)])
        pygame.draw.polygon(scr, (255, 214, 90), [(x - 3, feet - 20), (x + 3, feet - 20), (x, feet - 14)])
        pygame.draw.circle(scr, (250, 214, 180), (x, feet - 44), 10)
        pygame.draw.polygon(scr, WHITE, [(x - 8, feet - 41), (x + 8, feet - 41), (x, feet - 26)])   # beard
        pygame.draw.circle(scr, INK, (x - 3, feet - 46), 2)
        pygame.draw.circle(scr, INK, (x + 4, feet - 46), 2)
        hat = [(x - 15, feet - 50), (x + 2, feet - 86), (x + 15, feet - 50)]
        pygame.draw.polygon(scr, HAT, hat)
        pygame.draw.rect(scr, (98, 44, 160), (x - 16, feet - 53, 32, 5), border_radius=2)
        pygame.draw.circle(scr, GOLD, (x + 1, feet - 66), 3)
        tip = self.wand_tip()
        pygame.draw.line(scr, WOOD, (x + 10, feet - 28), tip, 4)
        if self.state in ("play", "title"):
            scr.blit(self.wand_glow, (tip[0] - 30, tip[1] - 30), special_flags=pygame.BLEND_RGB_ADD)
            pygame.draw.circle(scr, WHITE, tip, 4)

    def draw_word(self, word):
        scr = self.screen
        rect = word.rect
        if word.wrong_t > 0:
            rect.x += round(math.sin(word.wrong_t * 60) * 5)
        # the fireball the word rides down on
        flick = math.sin(word.t * 18) * 3
        tail = [(rect.centerx - 18, rect.top + 6), (rect.centerx + flick, rect.top - 46), (rect.centerx + 18, rect.top + 6)]
        pygame.draw.polygon(scr, (255, 130, 50), tail)
        inner = [(rect.centerx - 9, rect.top + 4), (rect.centerx - flick, rect.top - 26), (rect.centerx + 9, rect.top + 4)]
        pygame.draw.polygon(scr, (255, 220, 120), inner)
        scr.blit(self.glow, (rect.centerx - 46, rect.top - 40), special_flags=pygame.BLEND_RGB_ADD)
        locked = word is self.target
        danger = clamp((word.y + PLAQUE_H - (GROUND_Y - 260)) / 160, 0, 1)
        fill = mix((44, 34, 92), (130, 30, 50), danger)
        if word.wrong_t > 0:
            fill = (190, 40, 50)
        pygame.draw.rect(scr, fill, rect, border_radius=14)
        border = (255, 90, 90) if word.wrong_t > 0 else GOLD if locked else WHITE
        pygame.draw.rect(scr, border, rect, 4 if locked else 2, border_radius=14)
        font = self.font(WORD_FONT)
        done, rest = word.text[:word.typed], word.text[word.typed:]
        x = rect.x + 14
        y = rect.centery
        if done:
            surf = font.render(done, True, TYPED)
            scr.blit(surf, surf.get_rect(midleft=(x, y)))
            x += surf.get_width()
        if rest:
            surf = font.render(rest, True, WHITE)
            scr.blit(surf, surf.get_rect(midleft=(x, y)))
            if locked:     # underline the next letter to press
                nw = font.size(rest[0])[0]
                pygame.draw.rect(scr, GOLD, (x, y + 13, nw, 4), border_radius=2)

    def draw_bolts(self):
        for x0, y0, x1, y1, life in self.bolts:
            pts = [(x0, y0)]
            for k in range(1, 8):
                t = k / 8
                pts.append((lerp(x0, x1, t) + random.uniform(-10, 10), lerp(y0, y1, t) + random.uniform(-10, 10)))
            pts.append((x1, y1))
            pygame.draw.lines(self.screen, (160, 200, 255), False, pts, 7)
            pygame.draw.lines(self.screen, WHITE, False, pts, 3)

    def draw_particles(self):
        for x, y, _, _, life, color in self.particles:
            size = max(1, int(life * 8))
            pygame.draw.rect(self.screen, color, (x, y, size, size))

    def draw_hud(self):
        scr = self.screen
        pygame.draw.rect(scr, (30, 24, 70), (0, 0, W, HUD_H))
        pygame.draw.rect(scr, (110, 90, 200), (0, HUD_H - 4, W, 4))
        label = (170, 160, 220)
        self.text("SCORE", 18, label, (16, 8))
        self.text(self.score, 32, WHITE, (16, 22))
        self.text("LEVEL", 18, label, (140, 8))
        self.text(self.level, 32, (170, 230, 255), (140, 22))
        self.text("BEST", 18, label, (230, 8))
        self.text(max(self.best, self.score), 32, GOLD, (230, 22))
        self.text("PERFECT IN A ROW", 18, label, (350, 8))
        self.text(self.streak, 32, TYPED, (350, 22))
        self.text("CASTLE", 18, label, (W - 250, 8))
        for i in range(len(SECTIONS)):
            for k in range(SECTION_HP):
                full = self.hp[i] > k
                box = pygame.Rect(W - 250 + i * 40 + k * 18, 28, 14, 18)
                pygame.draw.rect(scr, STONE if full else (60, 50, 100), box, border_radius=3)
        if self.miss_t > 0:
            self.text("No word starts with that letter!", 28, (255, 150, 150), (W // 2, HUD_H + 22), "center")

    def dim(self, alpha=200):
        shade = pygame.Surface((W, H))
        shade.fill((16, 12, 40))
        shade.set_alpha(alpha)
        self.screen.blit(shade, (0, 0))

    def glowing(self, msg, size, y):
        glow = 150 + int(80 * (0.5 + 0.5 * math.sin(self.time * 3)))
        self.text(msg, size, (glow, 255, glow // 2), (W // 2, y), "center")

    def draw_title(self):
        self.dim(170)
        self.text("CASTLE", 120, (190, 200, 255), (W // 2 - 140, 104), "center")
        self.text("KEYS", 120, GOLD, (W // 2 + 190, 104), "center")
        self.text("Words are falling on your castle! Type them and the wizard zaps them.",
                  30, (226, 222, 240), (W // 2, 168), "center")
        lines = [
            ("Type a word", "the wizard zaps it before it lands"),
            ("Wrong letter?", "keep going - look for the right key"),
            ("Backspace", "let go of a word and pick another"),
            ("Missed a word?", "it knocks down part of your castle"),
            ("Every level", "longer words that fall faster"),
            ("Level done", "the builders fix part of the castle"),
            ("Esc", "pause"),
        ]
        for i, (key, what) in enumerate(lines):
            y = 204 + i * 32
            self.text(key, 30, GOLD, (W // 2 - 20, y), "topright")
            self.text(what, 28, (226, 222, 240), (W // 2, y + 2))
        if self.rankings():
            score, level, name = self.rankings()[0]
            self.text(f"Best so far: {score} by {name or '?'} (level {level})",
                      26, GOLD, (W // 2, 446), "center")
        self.glowing("Press SPACE to begin", 44, 490)

    def accuracy(self):
        typed = self.keys_right + self.keys_wrong
        return round(100 * self.keys_right / typed) if typed else 100

    def draw_review(self):
        self.dim(225)
        scr = self.screen
        self.text("WORDS TO PRACTICE", 60, GOLD, (W // 2, 46), "center")
        self.text(f"Level {self.level}   -   {self.zapped} words zapped   -   "
                  f"{self.accuracy()}% of keys right   -   {self.best_streak} perfect words in a row",
                  26, (210, 206, 236), (W // 2, 90), "center")
        entries = list(self.trouble.items())
        top = 124
        if not entries:
            self.text("WOW! You didn't miss a single word!", 48, TYPED, (W // 2, 240), "center")
            self.text("You are a true Castle Keeper.", 32, WHITE, (W // 2, 290), "center")
        most = max(0, len(entries) - VISIBLE_WORDS)
        self.review_scroll = clamp(self.review_scroll, 0, most)
        row_h = 92
        meaning_font = self.font(28)
        for n, (word, info) in enumerate(entries[self.review_scroll:self.review_scroll + VISIBLE_WORDS]):
            y = top + n * row_h
            card = pygame.Rect(70, y, W - 140, row_h - 10)
            pygame.draw.rect(scr, (44, 36, 96), card, border_radius=14)
            pygame.draw.rect(scr, (110, 96, 190), card, 2, border_radius=14)
            self.text(word, 44, GOLD, (card.x + 20, card.y + 12))
            if info["missed"]:
                tag, color = "it hit the castle", (255, 140, 140)
            else:
                tag, color = "typed with a slip", (255, 196, 120)
            self.text(tag, 24, color, (card.right - 18, card.y + 12), "topright")
            if info["slip"]:
                self.text(info["slip"], 24, (210, 206, 236), (card.right - 18, card.y + 34), "topright")
            for k, line in enumerate(wrap(meaning_font, "means: " + info["meaning"], card.w - 40)[:2]):
                self.text(line, 28, WHITE, (card.x + 20, card.y + 46 + k * 22))
        if most:
            track = pygame.Rect(W - 50, top, 6, VISIBLE_WORDS * row_h - 10)
            pygame.draw.rect(scr, (50, 44, 100), track, border_radius=3)
            thumb_h = max(14, track.h * VISIBLE_WORDS // len(entries))
            thumb_y = track.y + (track.h - thumb_h) * self.review_scroll // most
            pygame.draw.rect(scr, GOLD, (track.x, thumb_y, track.w, thumb_h), border_radius=3)
            self.text(f"{len(entries)} words  -  Up / Down or mouse wheel to see them all", 24,
                      (170, 160, 220), (W // 2, top + VISIBLE_WORDS * row_h + 2), "center")
        if self.time - self.name_time >= NAME_KEY_DELAY:
            self.glowing("Press ENTER to carry on", 38, H - 40)

    def draw_name(self):
        self.dim(225)
        self.text("THE CASTLE HAS FALLEN!", 64, (255, 150, 120), (W // 2, 110), "center")
        self.text(f"Score  {self.score}", 56, WHITE, (W // 2, 180), "center")
        self.text(f"Level {self.level}, {self.zapped} words zapped", 30, (210, 206, 236), (W // 2, 222), "center")
        self.text("Your name for the leaderboard:", 30, (190, 184, 230), (W // 2, 290), "center")
        box = pygame.Rect(W // 2 - 200, 314, 400, 58)
        pygame.draw.rect(self.screen, (26, 20, 60), box, border_radius=8)
        pygame.draw.rect(self.screen, GOLD, box, 2, border_radius=8)
        cursor = "|" if int(self.time * 2) % 2 == 0 else ""
        self.text(self.name + cursor, 42, GOLD if self.name_fresh else WHITE,
                  (box.x + 16, box.centery), "midleft")
        self.text("Type to change it", 26, (200, 196, 226), (W // 2, 404), "center")
        self.text("Down arrow: another silly name", 26, (200, 196, 226), (W // 2, 432), "center")
        self.text("Enter: save my score", 38, WHITE, (W // 2, 490), "center")

    def draw_over(self):
        self.dim(225)
        self.text("THE CASTLE HAS FALLEN!", 60, (255, 150, 120), (W // 2, 70), "center")
        self.text(f"Level {self.level}   -   {self.score} points", 34, (226, 222, 240), (W // 2, 120), "center")
        if self.new_best:
            self.text("A NEW BEST!", 34, TYPED, (W // 2, 156), "center")
        shared = self.online is not None
        self.text("Leaderboard shared with every player" if shared
                  else "Scores saved on this device", 24, (190, 184, 230), (W // 2, 190), "center")
        rows = self.rankings()[:MAX_RANKINGS]
        top = 226
        if not rows:
            self.text("No scores yet. You are the first!", 28, GOLD, (W // 2, top + 20), "center")
        most = max(0, len(rows) - VISIBLE_RANKINGS)
        if self.scroll_follow and self.mine in rows:
            # the shared ranking can arrive late, so keep re-centring on your row
            self.scroll = rows.index(self.mine) - VISIBLE_RANKINGS // 2
        self.scroll = clamp(self.scroll, 0, most)
        mine_at = rows.index(self.mine) if self.mine in rows else -1
        for i in range(self.scroll, min(len(rows), self.scroll + VISIBLE_RANKINGS)):
            score, level, name = rows[i]
            self.text(f"{i + 1}.   {name or '?'}   {score} points   (level {level})", 28,
                      GOLD if i == mine_at else (220, 216, 236),
                      (W // 2, top + (i - self.scroll) * 32), "center")
        if most:
            # a scroll bar beside the list, and a hint for how to move it
            track = pygame.Rect(W // 2 + 260, top - 12, 6, VISIBLE_RANKINGS * 32 - 4)
            pygame.draw.rect(self.screen, (50, 44, 100), track, border_radius=3)
            thumb_h = max(14, track.h * VISIBLE_RANKINGS // len(rows))
            thumb_y = track.y + (track.h - thumb_h) * self.scroll // most
            pygame.draw.rect(self.screen, GOLD, (track.x, thumb_y, track.w, thumb_h), border_radius=3)
            self.text("Up / Down or mouse wheel to scroll", 22, (170, 160, 220),
                      (W // 2, top + VISIBLE_RANKINGS * 32 - 4), "center")
        self.glowing("Press SPACE to play again", 40, 440)
        self.text("W to see your practice words again", 28, (226, 222, 240), (W // 2, 488), "center")
        self.text("Esc to leave" if not WEB else "Esc for the title",
                  26, (190, 184, 230), (W // 2, 524), "center")


async def main():
    pygame.init()
    pygame.display.set_caption("Castle Keys")
    screen = pygame.display.set_mode((W, H), 0 if WEB else pygame.SCALED)
    clock = pygame.time.Clock()
    game = Game(screen)
    while True:
        dt = min(clock.tick(FPS) / 1000, 1 / 30)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                game.on_key(event.key, event.unicode)
            if event.type == pygame.MOUSEWHEEL:
                game.on_wheel(-event.y)
        game.update(dt, pygame.key.get_pressed())
        game.draw()
        pygame.display.flip()
        await asyncio.sleep(0)      # hands control back to the browser each frame


if __name__ == "__main__":
    asyncio.run(main())
