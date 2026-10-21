"""Tree Jumper - a monkey bouncing up the jungle, with tigers waiting below.

Controls
    Left / Right arrows   move
    P or Esc              pause

The monkey never stops jumping. Steer it onto the branches above to climb, and
keep climbing - the view keeps creeping upwards, and if you drop out of the
bottom of it the tigers on the jungle floor will have you.

Low in the canopy birds fly across. Higher up hawks dive at you, and at the
very top comets come falling out of the sky. One touch from any of them knocks
you out of the trees. Grab bananas on the way for extra points.

When a run ends you type a name, and your score joins the ranking shared by every player.
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

W, H = 600, 800
FPS = 60
HUD_H = 56

# The world: y grows downwards and the jungle floor is at y = 0, so the sky is negative.
PX_PER_M = 10          # pixels of climbing per metre of height
START_Y = -150         # top of the first branch
FLOOR_ON_SCREEN = H - 70   # where the floor sits on screen when a run starts

MW, MH = 30, 38        # monkey size
GRAVITY = 1500
JUMP_V = 900           # every landing bounces you this fast - about 270 px up
MOVE_SPEED = 360
FOLLOW_AT = 0.42       # the view scrolls up to keep the monkey above this much of the screen

TREES = (100, 300, 500)    # trunk centres
TRUNK_W = 30
BRANCH_H = 12
GAP_MIN = 62               # vertical gap between one branch and the next...
GAP_START, GAP_MOST = 112, 196   # ...grows from this to this as you climb (a jump reaches 270)
GAP_GROWS_TO_M = 500
REACH = 210                # the next branch is never further sideways than this
EXTRA_BRANCH = (0.5, 0.08)     # chance of a spare branch on another tree, low down / high up
BRANCH_W_START = (96, 130)
BRANCH_W_END = (62, 90)
BANANA_CHANCE = 0.22
BANANA_POINTS = 10

# The view creeps upwards on its own, so sitting on one branch is never safe.
CREEP_FROM_M = 25
CREEP_BASE = 14            # pixels a second
CREEP_PER_M = 0.07
CREEP_MOST = 70

# What lives at each height
HAZARDS_FROM_M = 15
ZONE_HAWKS = 150
ZONE_COMETS = 350
ZONES = ("Treetops", "Hawk Heights", "Comet Sky")
BIRD_SPEED = (120, 190)
HAWK_SPEED = 170
HAWK_DIVE = 430            # straight at you once it is close
COMET_WARN = 1.0           # seconds of warning before a comet comes down
COMET_SPEED = (430, 560)

FALL_RISE = 0.5            # how long the floor takes to come up after you are knocked out
FLOOR_STRIP = 130          # how much of the floor shows when it comes up
AFTER_CHOMP = 1.1

SCORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tree_jumper_scores.json")
SCORE_KEY = "tree-jumper-scores"   # browser localStorage key used instead of the file
MAX_RANKINGS = 20
VISIBLE_RANKINGS = 5   # rows shown at once on the game-over screen; the rest scroll
RANKING_POOL = 100     # rows pulled from the database before keeping one per name
MAX_NAME_LEN = 16
NAME_KEY_DELAY = 0.5   # keys mashed while dying are ignored this long on the name screen
# Shared online ranking (the same Firebase database the other games use).
# Leave the address empty to keep rankings on this device only.
LEADERBOARD_URL = "https://alien-boom-boom-default-rtdb.firebaseio.com"
LEADERBOARD_PATH = "/tree-jumper-scores.json"
LEADERBOARD_TIMEOUT_S = 5
FUN_NAMES = [
    "Banana Bandit", "Captain Swing", "Vine Rider", "Cheeky Chimp", "Tiger Teaser",
    "Branch Manager", "Coco Nutty", "Sir Bounce", "Treetop Tom", "Monkey Business",
]

BARK = (112, 74, 42)
BARK_DARK = (78, 50, 30)
LEAF = (64, 150, 66)
LEAF_DARK = (40, 112, 50)
FUR = (128, 80, 42)
FUR_LIGHT = (222, 178, 128)
TIGER = (236, 138, 42)
CREAM = (250, 234, 204)
INK = (36, 26, 22)
WHITE = (250, 248, 240)
GOLD = (255, 214, 90)

# sky colours (top, bottom) by height in metres
SKY = [
    (0, (120, 200, 238), (196, 236, 206)),
    (ZONE_HAWKS, (238, 152, 98), (255, 210, 150)),
    (ZONE_COMETS, (30, 28, 74), (78, 52, 110)),
    (ZONE_COMETS + 200, (4, 4, 18), (18, 12, 42)),
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

    Names are matched ignoring case and spacing, and rows are (score, height, name),
    so the plain tuple comparison keeps the highest score.
    """
    best = {}
    for row in rankings:
        key = " ".join(row[2].split()).lower()
        if key not in best or row > best[key]:
            best[key] = row
    return sorted(best.values(), reverse=True)


def fetch_online_rankings():
    """Top (score, height, name) rows from the shared ranking, best first, or None if it can't be reached."""
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


def make_glow(radius, color, strength):
    """A soft round light. The colour itself fades out, because the add-blend
    that paints it on ignores alpha and would leave a hard-edged disc."""
    s = pygame.Surface((radius * 2, radius * 2))
    for i in range(radius, 0, -2):
        t = i / radius
        k = (1 - t) ** 2.2 * strength
        pygame.draw.circle(s, (int(color[0] * k), int(color[1] * k), int(color[2] * k)),
                           (radius, radius), i)
    return s


def make_far_jungle():
    """Rounded tree tops in the distance, seen only near the ground."""
    rng = random.Random(3)
    s = pygame.Surface((W, 300), pygame.SRCALPHA)
    for color, base, size in (((92, 160, 110), 120, 70), ((60, 124, 80), 180, 80)):
        x = -30
        while x < W + 30:
            r = rng.randint(size // 2, size)
            pygame.draw.circle(s, color, (x, base + rng.randint(-20, 20)), r)
            x += rng.randint(r // 2, r)
        pygame.draw.rect(s, color, (0, base, W, 300 - base))
    return s


def make_bird_frames(w, h, body, wing, belly, beak, head=None):
    """Two wing positions of a bird facing left, flipped when it flies right."""
    frames = []
    for up in (True, False):
        s = pygame.Surface((w, h + 20), pygame.SRCALPHA)
        cy = h // 2 + 10
        tail = [(w * 0.7, cy - 2), (w - 1, cy - h * 0.3), (w - 1, cy + h * 0.2), (w * 0.7, cy + 4)]
        pygame.draw.polygon(s, wing, tail)
        pygame.draw.ellipse(s, body, (w * 0.18, cy - h * 0.3, w * 0.62, h * 0.6))
        pygame.draw.ellipse(s, belly, (w * 0.26, cy, w * 0.4, h * 0.28))
        hx, hr = int(w * 0.2), max(5, int(h * 0.3))
        pygame.draw.circle(s, head or body, (hx, cy - hr // 2), hr)
        pygame.draw.polygon(s, beak, [(hx - hr + 2, cy - hr // 2 - 3), (hx - hr - 7, cy - hr // 2 + 1),
                                      (hx - hr + 2, cy - hr // 2 + 4)])
        pygame.draw.circle(s, INK, (hx - 2, cy - hr // 2 - 2), 2)
        wx = w * 0.42
        wing_pts = ([(wx - 6, cy - 2), (wx + 4, cy - h * 0.5 - 8), (wx + 12, cy - 2)] if up
                    else [(wx - 6, cy + 1), (wx + 4, cy + h * 0.5 + 6), (wx + 12, cy + 1)])
        pygame.draw.polygon(s, wing, wing_pts)
        frames.append(s)
    return frames


class Branch:
    def __init__(self, x, y, w, trunk, side):
        self.x, self.y, self.w = x, y, w
        self.trunk, self.side = trunk, side    # side: -1 sticks out left, 1 right, 0 both
        self.banana = False
        self.bounce = 0.0
        self.vine = random.random() < 0.3
        self.vine_at = random.uniform(0.3, 0.8)
        self.vine_len = random.randint(26, 60)

    @property
    def rect(self):
        return pygame.Rect(round(self.x), round(self.y), self.w, BRANCH_H)

    @property
    def banana_rect(self):
        return pygame.Rect(round(self.x + self.w / 2) - 10, round(self.y) - 22, 20, 20)


class Hazard:
    def __init__(self, kind, x, y, vx=0.0, vy=0.0):
        self.kind = kind           # bird, hawk or comet
        self.x, self.y = float(x), float(y)    # centre, in the world
        self.base_y = self.y
        self.vx, self.vy = vx, vy
        self.t = random.uniform(0, math.tau)
        self.diving = False
        self.warn = COMET_WARN if kind == "comet" else 0.0

    @property
    def rect(self):
        w, h = {"bird": (26, 16), "hawk": (34, 20), "comet": (20, 20)}[self.kind]
        return pygame.Rect(round(self.x - w / 2), round(self.y - h / 2), w, h)


class Monkey:
    def __init__(self):
        self.x = float(W // 2 - MW // 2)
        self.y = float(START_Y - MH)
        self.vy = -JUMP_V
        self.face = 1
        self.spin = 0.0

    @property
    def rect(self):
        return pygame.Rect(round(self.x), round(self.y), MW, MH)


# ------------------------------------------------------------------ the game


class Game:
    def __init__(self, screen):
        self.screen = screen
        self.far_jungle = make_far_jungle()
        self.bird_art = make_bird_frames(34, 22, (66, 140, 220), (36, 92, 176), GOLD, (250, 150, 40))
        self.hawk_art = make_bird_frames(52, 30, (122, 80, 46), (86, 56, 32), (214, 190, 160),
                                         (250, 200, 60), head=(240, 236, 226))
        self.comet_glow = make_glow(70, (255, 150, 70), 1.0)
        self.monkey_surf = pygame.Surface((72, 72), pygame.SRCALPHA)
        rng = random.Random(9)
        self.stars = [(rng.randint(0, W), rng.randint(0, H), rng.choice((1, 1, 2))) for _ in range(110)]
        self.clouds = [(rng.randint(-60, W), rng.randint(0, H + 200), rng.randint(30, 60)) for _ in range(7)]
        self.fonts = {}
        self.time = 0.0
        self.state = "title"           # title, play, falling, name, dead
        self.scroll = 0                # first leaderboard row shown
        self.scroll_follow = True      # keep your own row in view until you scroll yourself
        self.name = ""
        self.name_fresh = False
        self.name_time = 0.0
        self.mine = None
        self.online = None
        self.scores = self.load_scores()
        self.new_run()
        self.refresh_online()

    # ---------------------------------------------------------------- set up

    def new_run(self):
        self.monkey = Monkey()
        self.cam = float(-FLOOR_ON_SCREEN)     # world y at the top of the screen
        self.top = 0                           # best height this run, in metres
        self.bananas = 0
        self.zone = 0
        self.branches = []
        start = Branch(W // 2 - 90, START_Y, 180, TREES[1], 0)
        self.branches.append(start)
        self.next_y = START_Y
        self.hazards = []
        self.hazard_timer = 1.5
        self.particles = []
        self.popups = []
        self.tigers = [[150.0, 1, 50.0, 0.0], [430.0, -1, 64.0, 0.0]]   # x, facing, speed, jaw
        self.banner = ""
        self.banner_t = 0.0
        self.shake = 0.0
        self.paused = False
        self.new_best = False
        self.cause = ""
        self.fall_t = 0.0
        self.chomp_t = None
        self.grow_branches()

    def say(self, msg):
        self.banner, self.banner_t = msg, 2.2

    @property
    def score(self):
        return self.top + self.bananas * BANANA_POINTS

    def height_of(self, y):
        """Metres climbed when the monkey's feet are at world y."""
        return max(0, int((START_Y - y) / PX_PER_M))

    def grow_branches(self):
        """Add branches above the view and drop the ones that have fallen below it."""
        while self.next_y > self.cam - 140:
            climbed = (START_Y - self.next_y) / PX_PER_M / GAP_GROWS_TO_M
            gap = random.uniform(GAP_MIN, lerp(GAP_START, GAP_MOST, climbed))
            self.next_y -= gap
            lo = round(lerp(BRANCH_W_START[0], BRANCH_W_END[0], climbed))
            hi = round(lerp(BRANCH_W_START[1], BRANCH_W_END[1], climbed))
            main = self.place_branch(self.next_y, lo, hi, self.branches[-1])
            main.banana = random.random() < BANANA_CHANCE
            self.branches.append(main)
            if random.random() < lerp(*EXTRA_BRANCH, climbed):
                spare = self.place_branch(self.next_y + random.uniform(-24, 24), lo, hi,
                                          avoid=main.trunk)
                self.branches.insert(-1, spare)
        bottom = self.cam + H + 60
        self.branches = [b for b in self.branches if b.y < bottom]

    def place_branch(self, y, lo, hi, prev=None, avoid=None):
        """A branch on one of the trees, close enough sideways to `prev` to jump to."""
        for _ in range(40):
            trunk = random.choice([t for t in TREES if t != avoid])
            side = random.choice((-1, 1))
            w = random.randint(lo, hi)
            x = trunk - 6 if side > 0 else trunk + 6 - w
            x = clamp(x, 0, W - w)
            if prev is None or max(0, x - (prev.x + prev.w), prev.x - (x + w)) <= REACH:
                break
        return Branch(x, y, w, trunk, side)

    # ------------------------------------------------------------ the scores

    @property
    def best(self):
        return max((row[0] for row in self.scores), default=0)

    def load_scores(self):
        """This device's top scores as (score, height, name), plus the last name used."""
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
        """Add this run to this device's top scores and to the shared ranking."""
        self.name = self.name.strip() or random.choice(FUN_NAMES)
        height = clamp(self.top, 1, 999)       # the database keeps this between 1 and 999
        self.mine = (self.score, height, self.name)
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
        self.refresh_online({"name": self.name, "score": self.score, "level": height})
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
        if self.state == "title":
            if confirm:
                self.state = "play"
        elif self.state == "play":
            if key in (pygame.K_p, pygame.K_ESCAPE):
                self.paused = not self.paused
        elif self.state == "name":
            if self.time - self.name_time < NAME_KEY_DELAY:
                return                  # ignore whatever was being mashed as you fell
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
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
            elif confirm:
                self.new_run()
                self.state = "play"
            elif key in (pygame.K_ESCAPE, pygame.K_q):
                if WEB:                 # a browser tab can't be closed, so go back to the title
                    self.new_run()
                    self.state = "title"
                else:
                    pygame.event.post(pygame.event.Event(pygame.QUIT))

    def scroll_rankings(self, rows):
        if self.state != "dead":
            return
        most = max(0, len(self.rankings()[:MAX_RANKINGS]) - VISIBLE_RANKINGS)
        self.scroll = clamp(self.scroll + rows, 0, most)
        self.scroll_follow = False

    # ---------------------------------------------------------------- update

    def update(self, dt, keys):
        self.time += dt
        self.banner_t = max(0, self.banner_t - dt)
        self.shake = max(0, self.shake - dt * 2.5)
        if self.state == "falling":
            self.update_falling(dt)
            return
        if self.state != "play" or self.paused:
            if self.state == "title":
                self.pace_tigers(dt)
            return
        m = self.monkey

        # --- steering
        direction = ((1 if keys[pygame.K_RIGHT] or keys[pygame.K_d] else 0)
                     - (1 if keys[pygame.K_LEFT] or keys[pygame.K_a] else 0))
        if direction:
            m.x = clamp(m.x + direction * MOVE_SPEED * dt, 0, W - MW)
            m.face = direction

        # --- always bouncing: land on a branch on the way down and you spring straight back up
        old_feet = m.y + MH
        m.vy += GRAVITY * dt
        m.y += m.vy * dt
        if m.vy > 0:
            for b in self.branches:
                if old_feet <= b.y <= m.y + MH and m.x + MW - 6 > b.x and m.x + 6 < b.x + b.w:
                    m.y = b.y - MH
                    m.vy = -JUMP_V
                    b.bounce = 1.0
                    self.burst(m.x + MW / 2, b.y, LEAF, 5)
                    break
        for b in self.branches:
            b.bounce = max(0, b.bounce - dt * 4)
            if b.banana and b.banana_rect.colliderect(m.rect):
                b.banana = False
                self.bananas += 1
                self.burst(b.banana_rect.centerx, b.banana_rect.centery, GOLD, 10)
                self.popups.append([b.banana_rect.centerx, b.y - 30, f"+{BANANA_POINTS}", 0.8])

        self.top = max(self.top, self.height_of(m.y + MH))
        zone = 2 if self.top >= ZONE_COMETS else 1 if self.top >= ZONE_HAWKS else 0
        if zone > self.zone:
            self.zone = zone
            self.say("HAWK HEIGHTS!" if zone == 1 else "COMET SKY!")
            self.hazards = [hz for hz in self.hazards if hz.kind != "bird" or zone != 2]

        # --- the view follows you up, and creeps up on its own too
        self.cam = min(self.cam, m.y - H * FOLLOW_AT)
        if self.top >= CREEP_FROM_M:
            self.cam -= min(CREEP_BASE + self.top * CREEP_PER_M, CREEP_MOST) * dt
        self.grow_branches()

        self.spawn_hazards(dt)
        self.move_hazards(dt)
        self.pace_tigers(dt)
        self.fade_effects(dt)

        if self.state != "play":
            return
        if m.y + MH >= 0:
            self.knock_out("tigers")            # right down onto the jungle floor
        elif m.y > self.cam + H:
            self.knock_out("fall")

    def spawn_hazards(self, dt):
        if self.top < HAZARDS_FROM_M:
            return
        self.hazard_timer -= dt
        if self.hazard_timer > 0:
            return
        h = self.top
        faster = 1 + min(h / 600, 0.8)
        if h < ZONE_HAWKS:
            self.hazard_timer = lerp(3.0, 1.6, h / ZONE_HAWKS)
            side = random.choice((-1, 1))
            y = self.cam + random.uniform(HUD_H + 60, H * 0.5)
            self.hazards.append(Hazard("bird", -30 if side > 0 else W + 30, y,
                                       vx=side * random.uniform(*BIRD_SPEED) * faster))
        elif h < ZONE_COMETS:
            self.hazard_timer = lerp(2.4, 1.4, (h - ZONE_HAWKS) / (ZONE_COMETS - ZONE_HAWKS))
            side = random.choice((-1, 1))
            y = self.cam + random.uniform(HUD_H + 40, H * 0.35)
            self.hazards.append(Hazard("hawk", -40 if side > 0 else W + 40, y,
                                       vx=side * HAWK_SPEED * faster))
        else:
            self.hazard_timer = max(0.75, 1.6 - (h - ZONE_COMETS) * 0.003)
            x = clamp(self.monkey.x + MW / 2 + random.uniform(-110, 110), 20, W - 20)
            self.hazards.append(Hazard("comet", x, 0))

    def move_hazards(self, dt):
        m = self.monkey
        mx, my = m.rect.center
        body = m.rect.inflate(-8, -8)
        for hz in self.hazards[:]:
            hz.t += dt
            if hz.kind == "bird":
                hz.x += hz.vx * dt
                hz.y = hz.base_y + math.sin(hz.t * 3) * 14
            elif hz.kind == "hawk":
                if not hz.diving and abs(hz.x - mx) < 150 and hz.y < my - 40:
                    # close enough: fold the wings and go straight for the monkey
                    hz.diving = True
                    d = math.hypot(mx - hz.x, my - hz.y)
                    hz.vx, hz.vy = (mx - hz.x) / d * HAWK_DIVE, (my - hz.y) / d * HAWK_DIVE
                hz.x += hz.vx * dt
                hz.y += hz.vy * dt
            else:
                if hz.warn > 0:
                    hz.warn -= dt
                    if hz.warn <= 0:      # here it comes, out of the top of the sky
                        hz.y = self.cam + HUD_H - 40
                        hz.vx = random.uniform(-90, 90)
                        hz.vy = random.uniform(*COMET_SPEED)
                    continue
                hz.x += hz.vx * dt
                hz.y += hz.vy * dt
                if random.random() < 0.7:
                    self.particles.append([hz.x, hz.y, random.uniform(-30, 30), random.uniform(-60, 0),
                                           random.uniform(0.2, 0.5), random.choice(((255, 200, 90), (255, 130, 60)))])
            if hz.x < -90 or hz.x > W + 90 or hz.y > self.cam + H + 90:
                self.hazards.remove(hz)
                continue
            if self.state == "play" and (hz.kind != "comet" or hz.warn <= 0) and hz.rect.colliderect(body):
                self.knock_out(hz.kind)

    def pace_tigers(self, dt):
        for tiger in self.tigers:
            tiger[0] += tiger[1] * tiger[2] * dt
            if tiger[0] < 60 or tiger[0] > W - 60:
                tiger[1] = -tiger[1]
                tiger[0] = clamp(tiger[0], 60, W - 60)
            tiger[3] = max(0, tiger[3] - dt * 3)

    def knock_out(self, cause):
        """Something got the monkey: down it goes, and the tigers are waiting."""
        m = self.monkey
        self.cause = cause
        self.state = "falling"
        self.fall_t = 0.0
        self.chomp_t = None
        self.shake = 0.7
        if cause == "fall":
            # pop back up at the bottom edge for one last hop, so you see the end
            m.y = self.cam + H - 10 - MH
            m.vy = -260
        elif cause != "tigers":
            m.vy = -380
            self.burst(*m.rect.center, WHITE, 18)
            self.burst(*m.rect.center, FUR, 10)

    def floor_top(self):
        """Where the jungle floor is on screen. Once you are knocked out it comes up to meet you."""
        real = -self.cam
        if self.state not in ("falling", "name", "dead") or real < H:
            return real
        return lerp(H + 10, H - FLOOR_STRIP, self.fall_t / FALL_RISE)

    def update_falling(self, dt):
        m = self.monkey
        self.fall_t += dt
        self.move_hazards(dt)
        self.fade_effects(dt)
        if self.chomp_t is None:
            m.vy += GRAVITY * dt
            m.y += m.vy * dt
            if self.cause != "tigers" and self.cause != "fall":
                m.spin += dt * 9
            floor = self.floor_top()
            mx = m.x + MW / 2
            for tiger in self.tigers:          # the tigers run to where you will land
                tiger[1] = 1 if mx > tiger[0] else -1
                tiger[0] += clamp(mx - tiger[0], -300 * dt, 300 * dt)
                tiger[3] = clamp(1.2 - abs(mx - tiger[0]) / 120, tiger[3], 1)
            risen = self.cause == "tigers" or self.fall_t >= FALL_RISE
            if risen and m.y + MH - self.cam >= floor + 20:
                self.chomp_t = self.fall_t
                self.shake = 1.0
                self.burst(mx, self.cam + floor, FUR, 26)
                self.popups.append([mx, self.cam + floor - 60, "CHOMP!", 1.2])
        elif self.fall_t - self.chomp_t > AFTER_CHOMP:
            self.popups.clear()
            self.ask_name()

    # --------------------------------------------------------------- effects

    def burst(self, x, y, color, n):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = random.uniform(50, 250)
            self.particles.append([x, y, math.cos(a) * v, math.sin(a) * v - 40,
                                   random.uniform(0.25, 0.7), color])

    def fade_effects(self, dt):
        for part in self.particles[:]:
            part[0] += part[2] * dt
            part[1] += part[3] * dt
            part[3] += 360 * dt
            part[4] -= dt
            if part[4] <= 0:
                self.particles.remove(part)
        for pop in self.popups[:]:
            pop[1] -= 34 * dt
            pop[3] -= dt
            if pop[3] <= 0:
                self.popups.remove(pop)

    # ------------------------------------------------------------------ draw

    def font(self, size):
        if size not in self.fonts:
            self.fonts[size] = pygame.font.Font(None, size)
        return self.fonts[size]

    def text(self, msg, size, color, pos, anchor="topleft"):
        surf = self.font(size).render(str(msg), True, color)
        self.screen.blit(surf, surf.get_rect(**{anchor: pos}))

    def sy(self, y):
        """World y to screen y."""
        return round(y - self.cam)

    def draw(self):
        self.draw_sky()
        floor = self.floor_top()
        self.draw_trunks(floor)
        for b in self.branches:
            self.draw_branch(b)
        for hz in self.hazards:
            self.draw_hazard(hz)
        if self.state in ("play", "title") or (self.state == "falling" and self.chomp_t is None):
            self.draw_monkey()
        if floor < H:
            self.draw_floor(floor)
        else:
            self.draw_eyes()
        self.draw_particles()
        for pop in self.popups:
            self.text(pop[2], 30, WHITE, (pop[0], self.sy(pop[1])), "center")
        if self.state != "title":
            self.draw_hud()
        if self.banner_t > 0 and self.state == "play":
            self.text(self.banner, 58, WHITE, (W // 2, HUD_H + 70), "center")
        if self.state == "title":
            self.draw_title()
        elif self.state == "name":
            self.draw_name()
        elif self.state == "dead":
            self.draw_over()
        elif self.paused:
            self.dim()
            self.text("PAUSED", 72, WHITE, (W // 2, H // 2 - 24), "center")
            self.text("P to carry on", 28, (200, 200, 200), (W // 2, H // 2 + 34), "center")
        if self.shake > 0:
            dx, dy = random.randint(-5, 5) * self.shake, random.randint(-4, 4) * self.shake
            self.screen.scroll(int(dx), int(dy))

    def draw_sky(self):
        scr = self.screen
        h = self.top
        top, bottom = SKY[0][1], SKY[0][2]
        for (h1, t1, b1), (h2, t2, b2) in zip(SKY, SKY[1:]):
            if h >= h1:
                k = (h - h1) / (h2 - h1)
                top, bottom = mix(t1, t2, k), mix(b1, b2, k)
        bands = 40
        for i in range(bands):
            scr.fill(mix(top, bottom, i / (bands - 1)), (0, i * H // bands, W, H // bands + 1))

        stars = clamp((h - 250) / 200, 0, 1)
        if stars > 0:
            for i, (x, y, size) in enumerate(self.stars):
                twinkle = 0.7 + 0.3 * math.sin(self.time * 2 + i)
                pygame.draw.circle(scr, mix(top, WHITE, stars * twinkle),
                                   (x, round(y - self.cam * 0.05) % H), size)
        clouds = 1 - clamp((h - 250) / 120, 0, 1)
        if clouds > 0:
            for x, y, r in self.clouds:
                cy = round(y - self.cam * 0.3) % (H + 200) - 100
                color = mix(top, WHITE, 0.75 * clouds)
                for dx, dy, k in ((0, 0, 1), (r * 0.8, 6, 0.75), (-r * 0.8, 8, 0.7)):
                    pygame.draw.circle(scr, color, (round(x + dx), cy + dy), round(r * k))
        far = round(FLOOR_ON_SCREEN - 230 + (-FLOOR_ON_SCREEN - self.cam) * 0.45)
        if far < H:
            scr.blit(self.far_jungle, (0, far))
            if far + self.far_jungle.get_height() < H:
                scr.fill((60, 124, 80), (0, far + self.far_jungle.get_height(), W, H))

    def draw_trunks(self, floor):
        scr = self.screen
        bottom = min(H, round(floor) + 10)
        for x in TREES:
            left = x - TRUNK_W // 2
            pygame.draw.rect(scr, BARK, (left, 0, TRUNK_W, bottom))
            pygame.draw.rect(scr, BARK_DARK, (left, 0, 4, bottom))
            pygame.draw.rect(scr, (140, 98, 60), (left + TRUNK_W - 8, 0, 3, bottom))
            first = int(-self.cam) % 44
            for y in range(-first, bottom, 44):       # bark marks that scroll with the tree
                k = int((y + self.cam) // 44) % 3
                pygame.draw.arc(scr, BARK_DARK, (left + 5 + k * 5, y, 10, 16), 0.5, 2.6, 2)

    def draw_branch(self, b):
        scr = self.screen
        y = self.sy(b.y) + round(math.sin(b.bounce * 9) * b.bounce * 4)
        if y < -40 or y > H + 40:
            return
        rect = pygame.Rect(round(b.x), y, b.w, BRANCH_H)
        if b.vine:
            vx = rect.x + round(rect.w * b.vine_at)
            pygame.draw.line(scr, LEAF_DARK, (vx, y + BRANCH_H), (vx, y + BRANCH_H + b.vine_len), 3)
            for k in range(1, b.vine_len // 14 + 1):
                side = -1 if k % 2 else 1
                pygame.draw.ellipse(scr, LEAF, (vx + side * 5 - 4, y + BRANCH_H + k * 14 - 3, 8, 6))
        pygame.draw.rect(scr, BARK, rect, border_radius=6)
        pygame.draw.rect(scr, (150, 104, 62), (rect.x + 3, rect.y + 2, rect.w - 6, 3), border_radius=2)
        pygame.draw.rect(scr, BARK_DARK, rect, 2, border_radius=6)
        ends = [rect.left, rect.right] if b.side == 0 else [rect.left if b.side < 0 else rect.right]
        for ex in ends:     # a clump of leaves on the end of the branch
            for dx, dy, r, color in ((-8, -6, 12, LEAF_DARK), (8, -4, 11, LEAF_DARK),
                                     (0, -12, 12, LEAF), (-4, 2, 9, LEAF), (6, 0, 9, (90, 176, 80))):
                pygame.draw.circle(scr, color, (ex + dx, y + dy), r)
        if b.banana:
            br = b.banana_rect.move(0, -self.cam)
            br.y = y - 22 + round(math.sin(self.time * 4 + b.x) * 2)
            pygame.draw.arc(scr, GOLD, br, math.pi * 1.05, math.pi * 1.95, 6)
            pygame.draw.circle(scr, (110, 80, 30), (br.left + 2, br.centery + 1), 2)

    def draw_floor(self, top):
        scr = self.screen
        top = round(top)
        pygame.draw.rect(scr, (52, 92, 44), (0, top, W, H - top))
        pygame.draw.rect(scr, (90, 160, 70), (0, top, W, 8))
        for i in range(0, W, 22):            # grass tufts
            pygame.draw.polygon(scr, (70, 136, 60), [(i, top + 2), (i + 6, top - 9), (i + 12, top + 2)])
        for x, face, _, jaw in self.tigers:
            self.draw_tiger(round(x), top + 26, face, jaw)

    def draw_eyes(self):
        """Out of sight below, but the tigers are watching - brighter the lower you get."""
        if self.state != "play":
            return
        low = clamp(((self.monkey.y - self.cam) / H - 0.6) / 0.3, 0, 1)
        if low <= 0:
            return
        blink = math.sin(self.time * 1.7) > -0.95
        for x, _, _, _ in self.tigers:
            if blink:
                for dx in (-9, 9):
                    pygame.draw.ellipse(self.screen, mix((40, 40, 20), (255, 220, 60), low),
                                        (round(x) + dx - 5, H - 16, 10, 7))

    def draw_tiger(self, x, gy, face, jaw):
        scr = self.screen
        tx = x - face * 34
        pygame.draw.lines(scr, TIGER, False, [(tx, gy - 34), (tx - face * 16, gy - 46),
                                              (tx - face * 12, gy - 62)], 6)
        pygame.draw.circle(scr, INK, (tx - face * 12, gy - 62), 4)
        for lx in (x - 24, x - 12, x + 10, x + 22):
            pygame.draw.rect(scr, TIGER, (lx - 4, gy - 22, 9, 22), border_radius=3)
            pygame.draw.ellipse(scr, CREAM, (lx - 5, gy - 4, 11, 6))
        pygame.draw.ellipse(scr, TIGER, (x - 38, gy - 48, 76, 34))
        pygame.draw.ellipse(scr, CREAM, (x - 24, gy - 26, 48, 12))
        for k in (-22, -10, 2, 14):
            pygame.draw.line(scr, INK, (x + k, gy - 47), (x + k - face * 5, gy - 32), 4)
        hx, hy = x + face * 38, gy - 50
        for ex in (hx - 11, hx + 11):
            pygame.draw.circle(scr, TIGER, (ex, hy - 14), 7)
            pygame.draw.circle(scr, (240, 160, 150), (ex, hy - 14), 3)
        pygame.draw.circle(scr, TIGER, (hx, hy), 18)
        for k in (-6, 0, 6):
            pygame.draw.line(scr, INK, (hx + k, hy - 17), (hx + k, hy - 10), 3)
        mouth = jaw > 0.05
        pygame.draw.ellipse(scr, CREAM, (hx + face * 7 - 11, hy - 1, 22, 15 if mouth else 13))
        for ex in (hx + face * 3 - 6, hx + face * 3 + 6):
            pygame.draw.circle(scr, (250, 220, 70), (ex, hy - 5), 4)
            pygame.draw.circle(scr, INK, (ex + face, hy - 5), 2)
        nx = hx + face * 9
        pygame.draw.polygon(scr, INK, [(nx - 4, hy + 1), (nx + 4, hy + 1), (nx, hy + 5)])
        if mouth:
            open_h = round(4 + 16 * jaw)
            m = pygame.Rect(nx - 10, hy + 7, 20, open_h)
            pygame.draw.ellipse(scr, (130, 30, 40), m)
            for k in (-6, 0, 6):
                pygame.draw.polygon(scr, WHITE, [(m.centerx + k - 3, m.top + 1), (m.centerx + k + 3, m.top + 1),
                                                 (m.centerx + k, m.top + 6)])

    def draw_monkey(self):
        m = self.monkey
        s = self.monkey_surf
        s.fill((0, 0, 0, 0))
        f = m.face
        cx, cy = 36, 36
        up = m.vy < 0
        pygame.draw.lines(s, FUR, False, [(cx - f * 9, cy + 10), (cx - f * 20, cy + 9),
                                          (cx - f * 24, cy - 1), (cx - f * 19, cy - 8)], 3)
        legs = 4 if up else 0
        for lx in (cx - 7, cx + 3):
            pygame.draw.rect(s, FUR, (lx, cy + 8 - legs, 5, 12), border_radius=2)
        pygame.draw.ellipse(s, FUR, (cx - 11, cy - 5, 22, 22))
        pygame.draw.ellipse(s, FUR_LIGHT, (cx - 7, cy, 14, 14))
        for side in (-1, 1):
            hand = (cx + side * 15, cy - 17) if up else (cx + side * 18, cy + 3)
            pygame.draw.line(s, FUR, (cx + side * 8, cy), hand, 5)
            pygame.draw.circle(s, FUR_LIGHT, hand, 3)
        hx, hy = cx + f, cy - 12
        for side in (-1, 1):
            pygame.draw.circle(s, FUR, (hx + side * 12, hy - 1), 6)
            pygame.draw.circle(s, FUR_LIGHT, (hx + side * 12, hy - 1), 3)
        pygame.draw.circle(s, FUR, (hx, hy), 11)
        pygame.draw.ellipse(s, FUR_LIGHT, (hx + f * 2 - 8, hy - 6, 16, 14))
        knocked = self.state == "falling"
        for side in (-1, 1):
            ex = hx + f * 2 + side * 4
            if knocked:      # X eyes
                pygame.draw.line(s, INK, (ex - 2, hy - 4), (ex + 2, hy), 2)
                pygame.draw.line(s, INK, (ex - 2, hy), (ex + 2, hy - 4), 2)
            else:
                pygame.draw.circle(s, INK, (ex, hy - 2), 2)
        pygame.draw.arc(s, INK, (hx + f * 2 - 4, hy, 8, 6), math.pi * 1.1, math.pi * 1.9, 2)
        art = pygame.transform.rotate(s, math.degrees(m.spin)) if m.spin else s
        r = m.rect
        self.screen.blit(art, art.get_rect(center=(r.centerx, self.sy(r.centery) - 2)))

    def draw_hazard(self, hz):
        scr = self.screen
        x, y = round(hz.x), self.sy(hz.y)
        if hz.kind == "comet":
            if hz.warn > 0:
                if math.sin(hz.warn * 22) > -0.3:       # flashing warning where it will come down
                    pts = [(x, HUD_H + 8), (x - 14, HUD_H + 34), (x + 14, HUD_H + 34)]
                    pygame.draw.polygon(scr, (240, 60, 60), pts)
                    self.text("!", 28, WHITE, (x, HUD_H + 24), "center")
                return
            speed = math.hypot(hz.vx, hz.vy)
            dx, dy = -hz.vx / speed, -hz.vy / speed
            px, py = -dy, dx
            for length, width, color in ((110, 13, (255, 120, 50)), (70, 8, (255, 210, 110))):
                pygame.draw.polygon(scr, color, [(x + px * width, y + py * width),
                                                 (x + dx * length, y + dy * length),
                                                 (x - px * width, y - py * width)])
            scr.blit(self.comet_glow, (x - 70, y - 70), special_flags=pygame.BLEND_RGB_ADD)
            pygame.draw.circle(scr, (255, 248, 220), (x, y), 11)
            pygame.draw.circle(scr, (200, 120, 80), (x - 3, y + 2), 3)
            return
        frames = self.bird_art if hz.kind == "bird" else self.hawk_art
        frame = frames[0 if math.sin(hz.t * (14 if hz.kind == "bird" else 9)) > 0 else 1]
        if hz.diving:
            frame = frames[1]       # wings folded for the dive
        right = hz.vx > 0
        if right:
            frame = pygame.transform.flip(frame, True, False)
        if hz.diving:
            heading = math.degrees(math.atan2(-hz.vy, hz.vx))
            frame = pygame.transform.rotate(frame, heading if right else heading - 180)
        scr.blit(frame, frame.get_rect(center=(x, y)))

    def draw_particles(self):
        for x, y, _, _, life, color in self.particles:
            size = max(1, int(life * 7))
            pygame.draw.rect(self.screen, color, (x, self.sy(y), size, size))

    def draw_hud(self):
        scr = self.screen
        pygame.draw.rect(scr, (24, 44, 28), (0, 0, W, HUD_H))
        pygame.draw.rect(scr, (70, 130, 64), (0, HUD_H - 4, W, 4))
        label = (150, 190, 150)
        self.text("SCORE", 18, label, (16, 8))
        self.text(self.score, 32, WHITE, (16, 22))
        self.text("HEIGHT", 18, label, (120, 8))
        self.text(f"{self.top} m", 32, (170, 230, 255), (120, 22))
        self.text("BEST", 18, label, (240, 8))
        self.text(max(self.best, self.score), 32, GOLD, (240, 22))
        pygame.draw.arc(scr, GOLD, (340, 14, 22, 22), math.pi * 1.05, math.pi * 1.95, 6)
        self.text(f"x {self.bananas}", 30, GOLD, (366, 22))
        self.text(ZONES[self.zone], 26, (220, 230, 210), (W - 16, 18), "topright")

    def dim(self):
        shade = pygame.Surface((W, H))
        shade.fill((8, 16, 10))
        shade.set_alpha(190)
        self.screen.blit(shade, (0, 0))

    def draw_title(self):
        self.dim()
        self.text("TREE", 110, (130, 220, 110), (W // 2, 96), "center")
        self.text("JUMPER", 110, GOLD, (W // 2, 176), "center")
        self.text("You are a monkey who never stops bouncing.", 28, (220, 226, 214), (W // 2, 240), "center")
        lines = [
            ("Left / Right", "steer onto the branches"),
            ("Keep climbing", "the view creeps up on you"),
            ("Fall?", "the tigers below are hungry"),
            ("Low down", "dodge the birds"),
            ("Higher", "hawks dive at you"),
            ("Highest", "comets fall from the sky"),
            ("Bananas", f"+{BANANA_POINTS} points each"),
            ("P", "pause"),
        ]
        for i, (key, what) in enumerate(lines):
            y = 286 + i * 34
            self.text(key, 30, GOLD, (W // 2 - 18, y), "topright")
            self.text(what, 27, (224, 230, 220), (W // 2 + 4, y + 3))
        if self.rankings():
            score, height, name = self.rankings()[0]
            self.text(f"Best so far: {score} by {name or '?'} ({height} m)",
                      26, GOLD, (W // 2, 590), "center")
        glow = 150 + int(80 * (0.5 + 0.5 * math.sin(self.time * 3)))
        self.text("Press SPACE to begin", 42, (glow, 255, glow // 2), (W // 2, 650), "center")

    def death_message(self):
        return {
            "bird": "A BIRD KNOCKED YOU OFF",
            "hawk": "A HAWK GOT YOU",
            "comet": "HIT BY A COMET",
        }.get(self.cause, "YOU FELL")

    def draw_name(self):
        self.dim()
        self.text(self.death_message(), 56, (255, 150, 90), (W // 2, 150), "center")
        self.text("...and the tigers were waiting.", 30, (220, 226, 214), (W // 2, 200), "center")
        self.text(f"Score  {self.score}", 52, WHITE, (W // 2, 262), "center")
        self.text(f"{self.top} m high, {self.bananas} bananas", 28, (190, 210, 190), (W // 2, 302), "center")
        self.text("Your name for the leaderboard:", 28, (170, 190, 170), (W // 2, 370), "center")
        box = pygame.Rect(W // 2 - 190, 394, 380, 56)
        pygame.draw.rect(self.screen, (20, 36, 22), box, border_radius=8)
        pygame.draw.rect(self.screen, GOLD, box, 2, border_radius=8)
        cursor = "|" if int(self.time * 2) % 2 == 0 else ""
        self.text(self.name + cursor, 40, GOLD if self.name_fresh else WHITE,
                  (box.x + 16, box.centery), "midleft")
        self.text("Type to change it", 26, (190, 200, 190), (W // 2, 482), "center")
        self.text("Down arrow: another silly name", 26, (190, 200, 190), (W // 2, 510), "center")
        self.text("Enter: save my score", 36, WHITE, (W // 2, 570), "center")

    def draw_over(self):
        self.dim()
        self.text(self.death_message(), 56, (255, 150, 90), (W // 2, 110), "center")
        self.text(f"{self.top} m   -   {self.score} points", 34, (220, 226, 214), (W // 2, 166), "center")
        if self.new_best:
            self.text("A NEW BEST!", 34, (150, 240, 140), (W // 2, 208), "center")
        shared = self.online is not None
        self.text("Leaderboard shared with every player" if shared
                  else "Scores saved on this device", 24, (170, 190, 170), (W // 2, 250), "center")
        rows = self.rankings()[:MAX_RANKINGS]
        top = 290
        if not rows:
            self.text("No scores yet. You are the first!", 28, GOLD, (W // 2, top + 20), "center")
        most = max(0, len(rows) - VISIBLE_RANKINGS)
        if self.scroll_follow and self.mine in rows:
            # the shared ranking can arrive late, so keep re-centring on your row
            self.scroll = rows.index(self.mine) - VISIBLE_RANKINGS // 2
        self.scroll = clamp(self.scroll, 0, most)
        mine_at = rows.index(self.mine) if self.mine in rows else -1
        for i in range(self.scroll, min(len(rows), self.scroll + VISIBLE_RANKINGS)):
            score, height, name = rows[i]
            self.text(f"{i + 1}.   {name or '?'}   {score} points   ({height} m)", 27,
                      GOLD if i == mine_at else (214, 222, 210),
                      (W // 2, top + (i - self.scroll) * 30), "center")
        if most:
            # a scroll bar beside the list, and a hint for how to move it
            track = pygame.Rect(W - 34, top - 12, 6, VISIBLE_RANKINGS * 30 - 4)
            pygame.draw.rect(self.screen, (40, 60, 42), track, border_radius=3)
            thumb_h = max(14, track.h * VISIBLE_RANKINGS // len(rows))
            thumb_y = track.y + (track.h - thumb_h) * self.scroll // most
            pygame.draw.rect(self.screen, GOLD, (track.x, thumb_y, track.w, thumb_h), border_radius=3)
            self.text("Up / Down or mouse wheel to scroll", 22, (150, 170, 150),
                      (W // 2, top + VISIBLE_RANKINGS * 30 - 4), "center")
        glow = 150 + int(80 * (0.5 + 0.5 * math.sin(self.time * 3)))
        self.text("Press SPACE to go again", 38, (glow, 255, glow // 2), (W // 2, 520), "center")
        self.text("Esc to leave" if not WEB else "Esc for the title",
                  26, (170, 190, 170), (W // 2, 566), "center")


async def main():
    pygame.init()
    pygame.display.set_caption("Tree Jumper")
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
                game.scroll_rankings(-event.y)
        game.update(dt, pygame.key.get_pressed())
        game.draw()
        pygame.display.flip()
        await asyncio.sleep(0)      # hands control back to the browser each frame


if __name__ == "__main__":
    asyncio.run(main())
