"""Track of Doom - a race car on an endless track floating over the void.

Controls
    Up / Down arrows      speed up / brake (and back up)
    Left / Right arrows   steer
    Space                 jump
    P or Esc              pause

The track floats in the sky and never ends. Drive off the edge and you fall
into the void - but you have as many cars as you like, so you are put straight
back at the start of the level you are on.

Every level is longer and nastier than the last: sharp turns, ramps to jump
spike pits with, smashers that slam down every 2 seconds, and spiky balls
scattered somewhere new on every level. Grab coins for points and drive over
the blue pads for a speed boost.

The clock is what ends a race. Every level you reach puts time back on it; when
it runs out you type a name, and your score joins the ranking shared by every player.
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
PX_PER_M = 10          # pixels of track per metre

# The car. Its heading is in radians, 0 = up the screen, turning clockwise.
CAR_W, CAR_L = 26, 44
ACCEL = 560
BRAKE = 950
COAST = 240            # slowing down with nothing pressed
MAX_SPEED = 420
REVERSE_MAX = 160
TURN_RATE = 3.6
AIR_STEER = 0.35       # how much you can steer while in the air
GRAVITY = 1300
JUMP_V = 360           # a hop: about 0.55 s in the air, enough to clear a spiky ball
JUMP_BUFFER = 0.12     # Space pressed this long before landing still jumps
RAMP_V = 700           # the most a ramp can throw you up...
RAMP_LAND = 380        # ...aiming to land this far on, safely past the spike pit (too slow and you won't)
BOOST_SPEED = 680
BOOST_KICK = 600
BOOST_TIME = 2.2
HIT_R = 12             # the car's hit box, around its middle

# The track: straight pieces joined by sharp 90 degree turns, always heading up overall.
UP, LEFT, RIGHT = (0, -1), (-1, 0), (1, 0)
TRACK_W_START, TRACK_W_END = 190, 140    # the track gets narrower...
NARROWS_BY_LEVEL = 12                    # ...until this level
SEGMENTS_PER_LEVEL = 8                   # up, across, up, across...
DRIFT = 450                              # turn back towards the middle past this far sideways
SLAB = 22                                # how thick the floating track looks
GATE_IN = 110                            # each level's start gate, this far into its first piece
CLEAR_AFTER_GATE = 260                   # no obstacles this close after a start gate
GENERATE_AHEAD = 4000

# Obstacles
RAMP_LEN = 56
RAMP_GAP = 24
BED_LEN = 200          # the spike pit after a ramp - too long to hop, so use the ramp
STRIP_LEN = 46         # a short row of spikes across half the track
SMASH_LEN = 96
SMASH_EVERY = 2.0      # a smasher comes down every 2 seconds
SMASH_DROP_AT = 1.2    # ...this far through its cycle...
SMASH_FALL = 0.12
SMASH_HOLD = 0.3       # ...and stays down this long
SMASH_HIGH = 150
SMASH_WARN = 0.4       # it shakes this long before it drops
BALL_R = 15
COIN_R = 10
COIN_POINTS = 10
BALLS_FIRST, BALLS_MOST = 3, 14
FEATURE_LEN = {"coins": 200, "boost": 100, "ramp": RAMP_LEN + RAMP_GAP + BED_LEN + 200,
               "smasher": SMASH_LEN + 20, "spikes": STRIP_LEN + 30, "none": 80}

START_TIME = 45.0
LEVEL_TIME = (22, 12)  # seconds a new level puts back on the clock, at first / at most down to
RESPAWN_AFTER = 1.1
TIME_UP_FOR = 1.6

SCORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "track_of_doom_scores.json")
SCORE_KEY = "track-of-doom-scores"   # browser localStorage key used instead of the file
MAX_RANKINGS = 20
VISIBLE_RANKINGS = 5   # rows shown at once on the game-over screen; the rest scroll
RANKING_POOL = 100     # rows pulled from the database before keeping one per name
MAX_NAME_LEN = 16
NAME_KEY_DELAY = 0.5   # keys mashed as time ran out are ignored this long on the name screen
# Shared online ranking (the same Firebase database the other games use).
# Leave the address empty to keep rankings on this device only.
LEADERBOARD_URL = "https://alien-boom-boom-default-rtdb.firebaseio.com"
LEADERBOARD_PATH = "/track-of-doom-scores.json"
LEADERBOARD_TIMEOUT_S = 5
FUN_NAMES = [
    "Turbo Toast", "Captain Skid", "Doom Driver", "Sir Vroom", "Ramp Champ",
    "Lord Burnout", "Spike Dodger", "Nitro Noodle", "Edge Lord", "Wheelie Willy",
]

ASPHALT = (60, 58, 74)
ASPHALT_LINE = (210, 206, 220)
EDGE = (214, 44, 56)
EDGE_DARK = (120, 20, 34)
SLAB_SIDE = (46, 30, 54)
VOID_TOP = (16, 6, 26)
VOID_BOTTOM = (70, 10, 30)
CAR_RED = (232, 52, 46)
INK = (20, 16, 26)
WHITE = (250, 248, 240)
GOLD = (255, 214, 70)
BOOST = (60, 210, 255)
METAL = (128, 128, 146)


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


def along(rect, d, f0, f1):
    """The part of rect from f0 to f1 of the way along it, driving in direction d."""
    dx, dy = d
    if dx == 0:
        h = rect.h
        top = rect.bottom - h * f1 if dy < 0 else rect.top + h * f0
        return pygame.Rect(rect.x, round(top), rect.w, max(1, round(h * (f1 - f0))))
    w = rect.w
    left = rect.right - w * f1 if dx < 0 else rect.left + w * f0
    return pygame.Rect(round(left), rect.y, max(1, round(w * (f1 - f0))), rect.h)


# --------------------------------------------------------------- pretty bits


def make_car():
    """The race car seen from above, nose pointing up the screen."""
    s = pygame.Surface((CAR_W + 10, CAR_L + 6), pygame.SRCALPHA)
    cx = s.get_width() // 2
    for wy in (8, CAR_L - 12):           # four fat tyres
        for side in (-1, 1):
            pygame.draw.rect(s, INK, (cx + side * (CAR_W // 2) - 5, wy, 10, 13), border_radius=3)
    body = pygame.Rect(cx - CAR_W // 2, 3, CAR_W, CAR_L)
    pygame.draw.rect(s, CAR_RED, body, border_radius=9)
    pygame.draw.rect(s, (160, 26, 30), body, 2, border_radius=9)
    pygame.draw.rect(s, WHITE, (cx - 3, 4, 6, CAR_L - 2))                       # racing stripe
    pygame.draw.rect(s, (90, 180, 230), (cx - 9, 14, 18, 10), border_radius=3)   # windscreen
    pygame.draw.rect(s, (40, 70, 110), (cx - 8, 26, 16, 9), border_radius=3)     # roof
    pygame.draw.rect(s, INK, (cx - CAR_W // 2 - 2, CAR_L - 1, CAR_W + 4, 6), border_radius=2)  # spoiler
    for side in (-1, 1):
        pygame.draw.circle(s, (255, 244, 170), (cx + side * 8, 6), 3)           # headlights
    return s


def make_spikes(w, h):
    """A bed of little metal spikes, seen from above."""
    s = pygame.Surface((w, h))
    s.fill((40, 34, 46))
    step = 15
    for gy in range(step // 2, h, step):
        for gx in range(step // 2 + (gy // step % 2) * 7, w, step):
            pts = [(gx, gy - 7), (gx + 6, gy), (gx, gy + 7), (gx - 6, gy)]
            pygame.draw.polygon(s, (110, 108, 124), pts)
            pygame.draw.polygon(s, (220, 220, 232), [pts[0], (gx, gy), pts[3]])
            pygame.draw.polygon(s, (70, 68, 82), [pts[1], (gx, gy), pts[2]])
    pygame.draw.rect(s, (150, 40, 50), s.get_rect(), 2)
    return s


def make_glow(radius, color, strength):
    """A soft round light, painted on with an add-blend."""
    s = pygame.Surface((radius * 2, radius * 2))
    for i in range(radius, 0, -2):
        k = (1 - i / radius) ** 2.2 * strength
        pygame.draw.circle(s, (int(color[0] * k), int(color[1] * k), int(color[2] * k)),
                           (radius, radius), i)
    return s


class Segment:
    """One straight piece of track, from point a for `length` pixels in direction d."""

    def __init__(self, a, d, length, w, s0, level):
        self.ax, self.ay = a
        self.d = d
        self.length, self.w = length, w
        self.s0, self.level = s0, level        # s0: how far along the whole track it starts
        dx, dy = d
        self.end = (self.ax + dx * length, self.ay + dy * length)
        # the piece reaches half a track width past both of its ends, which fills in the corners
        x0, x1 = sorted((self.ax, self.end[0]))
        y0, y1 = sorted((self.ay, self.end[1]))
        self.rect = pygame.Rect(round(x0 - w / 2), round(y0 - w / 2),
                                round(x1 - x0 + w), round(y1 - y0 + w))
        self.used = []      # (from, to) stretches along it that already have something on them

    def point(self, s, across=0.0):
        """The point s along this piece, `across` to the right of its middle."""
        dx, dy = self.d
        return self.ax + dx * s - dy * across, self.ay + dy * s + dx * across

    def box(self, s, length, width, across=0.0):
        """A rectangle centred s along the piece, `length` long and `width` wide."""
        cx, cy = self.point(s, across)
        if self.d[0] == 0:
            return pygame.Rect(round(cx - width / 2), round(cy - length / 2), round(width), round(length))
        return pygame.Rect(round(cx - length / 2), round(cy - width / 2), round(length), round(width))

    def progress(self, x, y):
        dx, dy = self.d
        return self.s0 + clamp((x - self.ax) * dx + (y - self.ay) * dy, 0, self.length)

    def is_free(self, s0, s1):
        return all(s1 <= a or s0 >= b for a, b in self.used)


class Level:
    def __init__(self, number, first):
        self.number = number
        self.first = first                   # the piece the level starts on
        self.start_s = first.s0 + GATE_IN    # where its gate is, along the whole track
        self.spawn = first.point(GATE_IN + 45)


class Thing:
    """Something on the track: coin, boost pad, ramp, spikes, smasher or spiky ball."""

    def __init__(self, kind, level, rect, d=UP):
        self.kind, self.level, self.rect, self.d = kind, level, rect, d
        self.alive = True
        self.phase = random.uniform(0, SMASH_EVERY)    # smashers don't all come down together
        self.spin = random.uniform(0, math.tau)
        self.slammed = False


class Car:
    def __init__(self, x, y, a=0.0):
        self.x, self.y, self.a = float(x), float(y), a
        self.speed = 0.0
        self.z, self.vz = 0.0, 0.0     # height above the track
        self.boost = 0.0

    @property
    def airborne(self):
        return self.z > 0 or self.vz > 0

    @property
    def hitbox(self):
        return pygame.Rect(round(self.x - HIT_R), round(self.y - HIT_R), HIT_R * 2, HIT_R * 2)


# ------------------------------------------------------------------ the game


class Game:
    def __init__(self, screen):
        self.screen = screen
        self.car_art = make_car()
        self.boost_glow = make_glow(40, BOOST, 0.8)
        self.spike_art = {}
        rng = random.Random(7)
        self.stars = [(rng.randint(0, W), rng.randint(0, H), rng.choice((1, 1, 2)),
                       rng.choice((0.08, 0.15, 0.25))) for _ in range(140)]
        self.rocks = [(rng.randint(0, W), rng.randint(0, H), rng.randint(10, 34)) for _ in range(9)]
        self.fonts = {}
        self.time = 0.0
        self.state = "title"           # title, play, timeup, name, dead
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
        self.segments = []
        self.things = []
        self.levels = []
        self.track_end = (0.0, 0.0)
        self.track_len = 0.0
        self.far = 0.0                 # furthest along the track you have driven
        self.level = 1
        self.coins = 0
        self.crashes = 0
        self.time_left = START_TIME
        self.race_t = 0.0              # drives the smashers; stops while paused
        self.grow_track()
        self.car = Car(*self.levels[0].spawn)
        self.cam_x = self.car.x - W / 2
        self.cam_y = self.car.y - H * 0.58
        self.crash = None              # what got you, while the wreck is shown
        self.crash_t = 0.0
        self.jump_buffer = 0.0
        self.particles = []
        self.popups = []
        self.banner = ""
        self.banner_t = 0.0
        self.shake = 0.0
        self.paused = False
        self.new_best = False
        self.timeup_t = 0.0

    def say(self, msg):
        self.banner, self.banner_t = msg, 2.2

    @property
    def score(self):
        return int(self.far / PX_PER_M) + self.coins * COIN_POINTS

    def grow_track(self):
        """Lay down whole levels until the track reaches well past the car."""
        while self.track_len < self.far + GENERATE_AHEAD:
            self.add_level()

    def add_level(self):
        n = len(self.levels) + 1
        w = round(lerp(TRACK_W_START, TRACK_W_END, (n - 1) / NARROWS_BY_LEVEL))
        new = []
        ramp_on = random.randrange(2, SEGMENTS_PER_LEVEL, 2)     # every level gets at least one ramp
        for i in range(SEGMENTS_PER_LEVEL):
            if i % 2 == 0:
                d = UP
                length = random.uniform(650, 950) if i == 0 else random.uniform(420, 1000)
                if i == ramp_on:
                    length = max(length, w * 1.5 + FEATURE_LEN["ramp"] + random.uniform(100, 320))
            else:
                # left or right, but drifting back towards the middle if it has wandered off
                x = self.track_end[0]
                d = LEFT if x > DRIFT else RIGHT if x < -DRIFT else random.choice((LEFT, RIGHT))
                length = random.uniform(w + 60, 520)
            seg = Segment(self.track_end, d, length, w, self.track_len, n)
            self.track_end = seg.end
            self.track_len += length
            new.append(seg)
        self.segments += new
        level = Level(n, new[0])
        self.levels.append(level)
        for i, seg in enumerate(new):
            self.dress(seg, n, first=i == 0, ramp=i == ramp_on)
        self.scatter_balls(level, new)

    def dress(self, seg, n, first, ramp=False):
        """Put obstacles and goodies along one piece, keeping clear of the corners."""
        kinds = ["coins", "boost", "ramp", "smasher", "spikes", "none"]
        weights = [3, 1.5, 2 if seg.d == UP else 0, min(1 + 0.3 * n, 3.5), min(1 + 0.25 * n, 3), 1.5]
        s = seg.w * 0.75 + (GATE_IN + CLEAR_AFTER_GATE if first else 0) + random.uniform(0, 80)
        end = seg.length - seg.w * 0.75
        while True:
            kind = "ramp" if ramp else random.choices(kinds, weights)[0]
            ramp = False
            need = FEATURE_LEN[kind]
            if s + need > end:
                break
            self.place(kind, seg, s, n)
            seg.used.append((s, s + need))
            s += need + random.uniform(60, 180)

    def place(self, kind, seg, s, n):
        w = seg.w
        add = self.things.append
        if kind == "coins":
            across = random.choice((0, -w / 4, w / 4))
            for i in range(5):
                x, y = seg.point(s + 20 + i * 40, across)
                add(Thing("coin", n, pygame.Rect(round(x) - COIN_R, round(y) - COIN_R, COIN_R * 2, COIN_R * 2)))
        elif kind == "boost":
            across = random.uniform(-(w / 2 - 50), w / 2 - 50)
            add(Thing("boost", n, seg.box(s + 50, 70, 64, across), seg.d))
        elif kind == "ramp":
            add(Thing("ramp", n, seg.box(s + RAMP_LEN / 2, RAMP_LEN, w), seg.d))
            bed_mid = s + RAMP_LEN + RAMP_GAP + BED_LEN / 2
            add(Thing("spikes", n, seg.box(bed_mid, BED_LEN, w)))
            for k in (-1, 0, 1):        # coins hanging over the pit, for the brave
                x, y = seg.point(bed_mid + k * 55)
                add(Thing("coin", n, pygame.Rect(round(x) - COIN_R, round(y) - COIN_R, COIN_R * 2, COIN_R * 2)))
        elif kind == "smasher":
            add(Thing("smasher", n, seg.box(s + SMASH_LEN / 2, SMASH_LEN, w + 8), seg.d))
        elif kind == "spikes":
            width = w * 0.55
            side = random.choice((-1, 1))
            add(Thing("spikes", n, seg.box(s + STRIP_LEN / 2, STRIP_LEN, width, side * (w - width) / 2)))

    def scatter_balls(self, level, segs):
        """Spiky balls go somewhere new on every level."""
        count = min(BALLS_FIRST + level.number - 1, BALLS_MOST)
        placed = 0
        for _ in range(count * 30):
            if placed == count:
                break
            i = random.randrange(len(segs))
            seg = segs[i]
            lo = seg.w * 0.55 + (GATE_IN + CLEAR_AFTER_GATE if i == 0 else 0)
            hi = seg.length - seg.w * 0.55
            if hi <= lo:
                continue
            s = random.uniform(lo, hi)
            if not seg.is_free(s - 50, s + 50):
                continue
            x, y = seg.point(s, random.uniform(-(seg.w / 2 - BALL_R - 8), seg.w / 2 - BALL_R - 8))
            self.things.append(Thing("ball", level.number,
                                     pygame.Rect(round(x) - BALL_R, round(y) - BALL_R, BALL_R * 2, BALL_R * 2)))
            seg.used.append((s - 30, s + 30))
            placed += 1

    def on_track(self, x, y):
        return any(seg.rect.collidepoint(x, y) for seg in self.segments)

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
        """Add this run to this device's top scores and to the shared ranking."""
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
                self.say("LEVEL 1")
        elif self.state == "play":
            if key in (pygame.K_p, pygame.K_ESCAPE):
                self.paused = not self.paused
            elif self.paused and key == pygame.K_e:
                self.paused = False
                self.time_left = 0          # finish the race here
            elif key == pygame.K_SPACE and not self.paused:
                self.jump_buffer = JUMP_BUFFER
        elif self.state == "name":
            if self.time - self.name_time < NAME_KEY_DELAY:
                return                  # ignore whatever was being mashed as time ran out
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
                self.say("LEVEL 1")
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
        if self.state == "title":
            self.race_t += dt
            return
        if self.state == "timeup":
            self.timeup_t += dt
            self.race_t += dt
            self.fade_effects(dt)
            if self.timeup_t > TIME_UP_FOR:
                self.ask_name()
            return
        if self.state != "play" or self.paused:
            return
        self.race_t += dt
        self.time_left -= dt
        if self.time_left <= 0:
            self.time_left = 0
            self.state = "timeup"
            self.timeup_t = 0.0
            return

        if self.crash:
            self.update_crash(dt)
        else:
            self.drive(dt, keys)
        self.slam_smashers()
        self.follow_car(dt)
        self.fade_effects(dt)

    def drive(self, dt, keys):
        c = self.car
        gas = (1 if keys[pygame.K_UP] or keys[pygame.K_w] else 0) - (1 if keys[pygame.K_DOWN] or keys[pygame.K_s] else 0)
        steer = (1 if keys[pygame.K_RIGHT] or keys[pygame.K_d] else 0) - (1 if keys[pygame.K_LEFT] or keys[pygame.K_a] else 0)

        # --- jump, if Space was pressed just now (or just before you landed)
        self.jump_buffer = max(0, self.jump_buffer - dt)
        if self.jump_buffer > 0 and not c.airborne:
            c.vz = JUMP_V
            self.jump_buffer = 0

        # --- speed: only the wheels on the track can speed you up or slow you down
        top = BOOST_SPEED if c.boost > 0 else MAX_SPEED
        c.boost = max(0, c.boost - dt)
        if not c.airborne:
            if gas > 0:
                c.speed += (ACCEL if c.speed >= 0 else BRAKE) * dt
            elif gas < 0:
                c.speed -= (BRAKE if c.speed > 0 else ACCEL * 0.6) * dt
            else:
                c.speed -= math.copysign(min(abs(c.speed), COAST * dt), c.speed)
            if c.speed > top:          # a boost wearing off slows you back down gently
                c.speed = max(top, c.speed - 500 * dt)
            c.speed = max(c.speed, -REVERSE_MAX)

        # --- steering needs some speed, and works much less in the air
        grip = clamp(abs(c.speed) / 160, 0, 1) * (AIR_STEER if c.airborne else 1)
        c.a += steer * TURN_RATE * grip * dt * (1 if c.speed >= 0 else -1)
        c.x += math.sin(c.a) * c.speed * dt
        c.y -= math.cos(c.a) * c.speed * dt

        if c.airborne:
            c.vz -= GRAVITY * dt
            c.z += c.vz * dt
            if c.z <= 0:
                c.z, c.vz = 0.0, 0.0
                if self.on_track(c.x, c.y):
                    self.burst(c.x, c.y, (150, 140, 160), 8)
        if not c.airborne and not self.on_track(c.x, c.y):
            self.wreck("fall")
            return

        # --- how far along the track you have got
        for seg in self.segments:
            if seg.rect.collidepoint(c.x, c.y):
                self.far = max(self.far, seg.progress(c.x, c.y))
        while self.level < len(self.levels) and self.far >= self.levels[self.level].start_s:
            self.level += 1
            bonus = max(LEVEL_TIME[1], LEVEL_TIME[0] - (self.level - 2))
            self.time_left += bonus
            self.say(f"LEVEL {self.level}")
            self.popups.append([c.x, c.y - 50, f"+{bonus} s", 1.2, (140, 255, 160)])
            keep = self.level - 1      # forget the track two levels back
            self.segments = [s for s in self.segments if s.level >= keep]
            self.things = [t for t in self.things if t.level >= keep]
        self.grow_track()

        # --- whatever is on the track under you
        box = c.hitbox
        near = box.inflate(160, 160)
        for t in self.things:
            if not t.alive or not near.colliderect(t.rect):
                continue
            if t.kind == "coin":
                if math.hypot(t.rect.centerx - c.x, t.rect.centery - c.y) < COIN_R + HIT_R + 6:
                    t.alive = False
                    self.coins += 1
                    self.burst(*t.rect.center, GOLD, 10)
                    self.popups.append([t.rect.centerx, t.rect.centery - 20, f"+{COIN_POINTS}", 0.7, GOLD])
            elif t.kind == "boost":
                if not c.airborne and t.rect.collidepoint(c.x, c.y):
                    if c.boost <= 0:
                        self.popups.append([c.x, c.y - 40, "BOOST!", 0.8, BOOST])
                    c.boost = BOOST_TIME
                    c.speed = max(c.speed, BOOST_KICK)
            elif t.kind == "ramp":
                # thrown off the lip: about the same landing spot at any speed, if you are quick enough
                if not c.airborne and along(t.rect, t.d, 0.5, 1).collidepoint(c.x, c.y) and c.speed > 40:
                    c.vz = min(RAMP_V, RAMP_LAND * GRAVITY / (2 * c.speed))
            elif t.kind == "spikes":
                if c.z < 8 and box.colliderect(t.rect):
                    self.wreck("spikes")
                    return
            elif t.kind == "smasher":
                if self.smasher_height(t) < 30 and box.colliderect(t.rect):
                    self.wreck("smasher")
                    return
            elif t.kind == "ball":
                if c.z < 18 and math.hypot(t.rect.centerx - c.x, t.rect.centery - c.y) < BALL_R + HIT_R:
                    self.wreck("ball")
                    return

    def wreck(self, cause):
        """Off the edge or smashed up: show it, then put a new car at the start of this level."""
        c = self.car
        self.crash = cause
        self.crash_t = 0.0
        self.crashes += 1
        self.shake = 0.5 if cause == "fall" else 0.9
        if cause != "fall":
            self.burst(c.x, c.y, (255, 170, 60), 22)
            self.burst(c.x, c.y, CAR_RED, 14)
            self.burst(c.x, c.y, INK, 10)
        text = {"fall": "OFF THE EDGE!", "spikes": "SPIKED!", "smasher": "SMASHED!",
                "ball": "SPIKY BALL!"}[cause]
        self.popups.append([c.x, c.y - 30, text, 1.1, (255, 120, 90)])

    def update_crash(self, dt):
        c = self.car
        self.crash_t += dt
        if self.crash == "fall":        # tumbling away into the void
            c.x += math.sin(c.a) * c.speed * dt
            c.y -= math.cos(c.a) * c.speed * dt
            c.speed *= 0.97
            c.a += dt * 5
        if self.crash_t >= RESPAWN_AFTER:
            self.crash = None
            self.car = Car(*self.levels[self.level - 1].spawn)
            self.jump_buffer = 0
            self.cam_x = self.car.x - W / 2          # jump the view straight there
            self.cam_y = self.car.y - H * 0.58

    def smasher_height(self, t):
        """How high a smasher's block is right now: 0 means slammed down on the track."""
        p = (self.race_t + t.phase) % SMASH_EVERY
        if p < SMASH_DROP_AT:
            return SMASH_HIGH
        p -= SMASH_DROP_AT
        if p < SMASH_FALL:
            k = p / SMASH_FALL
            return SMASH_HIGH * (1 - k * k)
        p -= SMASH_FALL
        if p < SMASH_HOLD:
            return 0
        p -= SMASH_HOLD
        return SMASH_HIGH * p / (SMASH_EVERY - SMASH_DROP_AT - SMASH_FALL - SMASH_HOLD)

    def slam_smashers(self):
        """A puff of dust and a little shake when a smasher you can see hits the track."""
        view = pygame.Rect(round(self.cam_x), round(self.cam_y), W, H)
        for t in self.things:
            if t.kind != "smasher":
                continue
            down = self.smasher_height(t) == 0
            if down and not t.slammed and view.colliderect(t.rect):
                self.shake = max(self.shake, 0.22)
                for x in (t.rect.left, t.rect.right):
                    self.burst(x, t.rect.centery, (170, 160, 170), 6)
            t.slammed = down

    def follow_car(self, dt):
        c = self.car
        look = 0.0 if self.crash else 0.32
        tx = c.x + math.sin(c.a) * c.speed * look - W / 2
        ty = c.y - math.cos(c.a) * c.speed * look - H * 0.58
        k = 1 - math.exp(-5 * dt)
        self.cam_x += (tx - self.cam_x) * k
        self.cam_y += (ty - self.cam_y) * k

    # --------------------------------------------------------------- effects

    def burst(self, x, y, color, n):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = random.uniform(40, 260)
            self.particles.append([x, y, math.cos(a) * v, math.sin(a) * v, random.uniform(0.25, 0.75), color])

    def fade_effects(self, dt):
        drag = math.exp(-3 * dt)
        for part in self.particles[:]:
            part[0] += part[2] * dt
            part[1] += part[3] * dt
            part[2] *= drag
            part[3] *= drag
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

    def to_screen(self, rect):
        return rect.move(-round(self.cam_x), -round(self.cam_y))

    def draw(self):
        self.draw_void()
        if self.crash == "fall":
            self.draw_car()             # falling past the edge, so under the track
        self.draw_track()
        view = pygame.Rect(round(self.cam_x) - 40, round(self.cam_y) - 40, W + 80, H + 80 + SMASH_HIGH)
        on_screen = [t for t in self.things if t.alive and view.colliderect(t.rect)]
        for t in on_screen:
            if t.kind != "smasher":
                self.draw_thing(t)
        for t in on_screen:
            if t.kind == "smasher":
                self.draw_smasher_shadow(t)
        if self.crash is None:
            self.draw_car()
        for t in on_screen:
            if t.kind == "smasher":
                self.draw_smasher(t)
        self.draw_particles()
        for x, y, msg, life, color in self.popups:
            self.text(msg, 32, color, (round(x - self.cam_x), round(y - self.cam_y)), "center")
        if self.state != "title":
            self.draw_hud()
        if self.banner_t > 0 and self.state == "play":
            self.text(self.banner, 64, WHITE, (W // 2, HUD_H + 80), "center")
        if self.state == "title":
            self.draw_title()
        elif self.state == "timeup":
            self.text("TIME'S UP!", 84, (255, 90, 80), (W // 2, H // 2 - 40), "center")
        elif self.state == "name":
            self.draw_name()
        elif self.state == "dead":
            self.draw_over()
        elif self.paused:
            self.dim()
            self.text("PAUSED", 72, WHITE, (W // 2, H // 2 - 40), "center")
            self.text("P to carry on", 30, (210, 200, 220), (W // 2, H // 2 + 20), "center")
            self.text("E to end the race here", 26, (170, 160, 190), (W // 2, H // 2 + 56), "center")
        if self.shake > 0:
            dx, dy = random.randint(-5, 5) * self.shake, random.randint(-4, 4) * self.shake
            self.screen.scroll(int(dx), int(dy))

    def draw_void(self):
        scr = self.screen
        bands = 32
        for i in range(bands):
            scr.fill(mix(VOID_TOP, VOID_BOTTOM, i / (bands - 1)), (0, i * H // bands, W, H // bands + 1))
        for i, (x, y, size, depth) in enumerate(self.stars):
            twinkle = 0.6 + 0.4 * math.sin(self.time * 2 + i)
            pos = (round(x - self.cam_x * depth) % W, round(y - self.cam_y * depth) % H)
            pygame.draw.circle(scr, mix(VOID_TOP, WHITE, twinkle * depth * 3.5), pos, size)
        for x, y, r in self.rocks:        # lumps of rock drifting far below the track
            pos = (round(x - self.cam_x * 0.4) % (W + 80) - 40, round(y - self.cam_y * 0.4) % (H + 80) - 40)
            pygame.draw.circle(scr, (40, 22, 44), pos, r)
            pygame.draw.circle(scr, (58, 34, 60), (pos[0] - r // 4, pos[1] - r // 4), r * 2 // 3)

    def draw_track(self):
        scr = self.screen
        view = pygame.Rect(round(self.cam_x), round(self.cam_y) - SLAB, W, H + SLAB)
        visible = [s for s in self.segments if s.rect.colliderect(view)]
        rects = [self.to_screen(s.rect) for s in visible]
        # underneath first, then the red edges, then the road, so the corners join up
        for r in rects:
            pygame.draw.rect(scr, SLAB_SIDE, r.move(0, SLAB))
            pygame.draw.rect(scr, (28, 18, 34), (r.x, r.bottom + SLAB - 6, r.w, 6))
        for r in rects:
            pygame.draw.rect(scr, EDGE_DARK, r.move(0, 4))
            pygame.draw.rect(scr, EDGE, r)
        for r in rects:
            pygame.draw.rect(scr, ASPHALT, r.inflate(-14, -14))
        ox, oy = round(self.cam_x), round(self.cam_y)
        for seg in visible:                # dashes down the middle
            s = seg.w * 0.6 + (-seg.s0) % 80
            while s < seg.length - seg.w * 0.6:
                pygame.draw.rect(scr, ASPHALT_LINE, seg.box(s, 30, 5).move(-ox, -oy))
                s += 80
        for level in self.levels:          # chequered start gate at the start of every level
            seg = level.first
            if seg not in visible:
                continue
            gate = seg.box(GATE_IN, 28, seg.w - 14).move(-ox, -oy)
            sq = 14
            for row in range(2):
                for col in range(0, gate.w, sq):
                    color = WHITE if (col // sq + row) % 2 == 0 else INK
                    pygame.draw.rect(scr, color, (gate.x + col, gate.y + row * sq, min(sq, gate.w - col), sq))
            x, y = seg.point(GATE_IN + 70)
            label = self.font(46).render(f"LEVEL {level.number}", True, (90, 86, 106))
            scr.blit(label, label.get_rect(center=(round(x) - ox, round(y) - oy)))

    def draw_thing(self, t):
        scr = self.screen
        r = self.to_screen(t.rect)
        dx, dy = t.d
        if t.kind == "coin":
            wobble = abs(math.cos(self.time * 4 + t.spin))
            face = pygame.Rect(0, 0, max(4, round(COIN_R * 2 * wobble)), COIN_R * 2)
            face.center = r.center
            pygame.draw.ellipse(scr, (190, 130, 20), face.move(0, 2))
            pygame.draw.ellipse(scr, GOLD, face)
            if face.w > 8:
                pygame.draw.ellipse(scr, (255, 240, 160), face.inflate(-face.w // 2, -8))
        elif t.kind == "boost":
            pygame.draw.rect(scr, (20, 60, 90), r, border_radius=8)
            pygame.draw.rect(scr, BOOST, r, 3, border_radius=8)
            for k in range(3):
                glow = 0.5 + 0.5 * math.sin(self.time * 8 - k * 1.4)
                self.chevron(along(r, t.d, k / 3, (k + 1) / 3).center, t.d, 22, mix((30, 90, 130), (190, 250, 255), glow))
        elif t.kind == "ramp":
            bands = 6
            for k in range(bands):         # darker at the bottom, bright at the lip
                pygame.draw.rect(scr, mix((150, 90, 20), (255, 210, 70), k / (bands - 1)),
                                 along(r, t.d, k / bands, (k + 1) / bands))
            pygame.draw.rect(scr, WHITE, along(r, t.d, 0.94, 1))
            self.chevron(r.center, t.d, 30, INK)
            pygame.draw.rect(scr, (110, 60, 10), r, 2)
        elif t.kind == "spikes":
            key = (r.w, r.h)
            if key not in self.spike_art:
                self.spike_art[key] = make_spikes(*key)
            scr.blit(self.spike_art[key], r)
        elif t.kind == "ball":
            cx, cy = r.center
            spin = self.time * 3 + t.spin
            for k in range(8):
                a = spin + k * math.tau / 8
                tip = (cx + math.cos(a) * (BALL_R + 9), cy + math.sin(a) * (BALL_R + 9))
                b1 = (cx + math.cos(a - 0.3) * BALL_R, cy + math.sin(a - 0.3) * BALL_R)
                b2 = (cx + math.cos(a + 0.3) * BALL_R, cy + math.sin(a + 0.3) * BALL_R)
                pygame.draw.polygon(scr, (200, 200, 214), (b1, tip, b2))
            pygame.draw.circle(scr, INK, (cx + 3, cy + 4), BALL_R)
            pygame.draw.circle(scr, (84, 80, 96), (cx, cy), BALL_R)
            pygame.draw.circle(scr, (150, 146, 166), (cx - 4, cy - 5), 5)

    def chevron(self, center, d, size, color):
        dx, dy = d
        nx, ny = -dy, dx
        cx, cy = center
        tip = (cx + dx * size * 0.35, cy + dy * size * 0.35)
        wings = [(cx - dx * size * 0.3 + nx * side * size * 0.55, cy - dy * size * 0.3 + ny * side * size * 0.55)
                 for side in (-1, 1)]
        pygame.draw.lines(self.screen, color, False, [wings[0], tip, wings[1]], 6)

    def draw_smasher_shadow(self, t):
        h = self.smasher_height(t)
        r = self.to_screen(t.rect)
        shade = pygame.Surface(r.size, pygame.SRCALPHA)
        shade.fill((0, 0, 0, round(60 + 120 * (1 - h / SMASH_HIGH))))
        self.screen.blit(shade, r)
        # the posts the block slides up and down between, either side of the track
        dx, dy = t.d
        nx, ny = -dy, dx
        half = (t.rect.w if dx == 0 else t.rect.h) / 2 + 12
        for side in (-1, 1):
            px, py = r.centerx + nx * side * half, r.centery + ny * side * half
            pygame.draw.circle(self.screen, (50, 48, 60), (round(px), round(py) + 6), 13)
            pygame.draw.circle(self.screen, METAL, (round(px), round(py)), 13)
            pygame.draw.circle(self.screen, GOLD, (round(px), round(py)), 6)

    def draw_smasher(self, t):
        scr = self.screen
        h = self.smasher_height(t)
        p = (self.race_t + t.phase) % SMASH_EVERY
        warn = SMASH_DROP_AT - SMASH_WARN <= p < SMASH_DROP_AT
        jiggle = random.randint(-2, 2) if warn else 0
        r = self.to_screen(t.rect).inflate(-6, -6)
        grow = round(h * 0.15)       # higher up looks bigger, and a little further up the screen
        block = r.inflate(grow, grow).move(jiggle, -round(h * 0.25))
        pygame.draw.rect(scr, (52, 50, 64), block.move(0, 12), border_radius=6)        # its side
        pygame.draw.rect(scr, METAL, block, border_radius=6)
        stripes = block.inflate(-10, -10)
        pygame.draw.rect(scr, GOLD, stripes, border_radius=4)
        inner = stripes.inflate(-12, -12)
        scr.set_clip(stripes)
        for x in range(stripes.left - stripes.h, stripes.right, 16):       # yellow and black stripes
            pygame.draw.line(scr, INK, (x, stripes.bottom), (x + stripes.h, stripes.top), 6)
        scr.set_clip(None)
        pygame.draw.rect(scr, (98, 98, 116), inner, border_radius=3)
        pygame.draw.rect(scr, (156, 156, 176), (inner.x, inner.y, inner.w, 4))
        if warn and int(self.time * 16) % 2 == 0:
            pygame.draw.rect(scr, (255, 60, 60), block, 4, border_radius=6)

    def draw_car(self):
        c = self.car
        x, y = round(c.x - self.cam_x), round(c.y - self.cam_y)
        if self.crash == "fall":
            k = clamp(self.crash_t / RESPAWN_AFTER, 0, 1)
            art = pygame.transform.rotozoom(self.car_art, -math.degrees(c.a), lerp(1, 0.15, k))
            art.set_alpha(round(255 * (1 - k * 0.8)))
            self.screen.blit(art, art.get_rect(center=(x, y + round(SLAB * k * 3))))
            return
        if c.boost > 0:
            behind = (x - math.sin(c.a) * 26, y + math.cos(c.a) * 26 - c.z * 0.5)
            self.screen.blit(self.boost_glow, (round(behind[0]) - 40, round(behind[1]) - 40),
                             special_flags=pygame.BLEND_RGB_ADD)
            if random.random() < 0.8:
                self.particles.append([c.x - math.sin(c.a) * 24, c.y + math.cos(c.a) * 24,
                                       random.uniform(-40, 40), random.uniform(-40, 40), 0.3,
                                       random.choice((BOOST, WHITE))])
        # the shadow stays on the track while the car goes up in the air
        shadow = pygame.Surface((CAR_W + 10, CAR_L + 6), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 110), shadow.get_rect().inflate(-6, -2), border_radius=10)
        shadow = pygame.transform.rotozoom(shadow, -math.degrees(c.a), max(0.6, 1 - c.z / 300))
        self.screen.blit(shadow, shadow.get_rect(center=(x + round(c.z * 0.35), y + 4 + round(c.z * 0.5))))
        art = pygame.transform.rotozoom(self.car_art, -math.degrees(c.a), 1 + c.z / 260)
        self.screen.blit(art, art.get_rect(center=(x, y - round(c.z * 0.25))))

    def draw_particles(self):
        for x, y, _, _, life, color in self.particles:
            size = max(1, int(life * 8))
            pygame.draw.rect(self.screen, color, (round(x - self.cam_x), round(y - self.cam_y), size, size))

    def draw_hud(self):
        scr = self.screen
        pygame.draw.rect(scr, (24, 12, 30), (0, 0, W, HUD_H))
        pygame.draw.rect(scr, EDGE, (0, HUD_H - 4, W, 4))
        label = (170, 140, 180)
        self.text("SCORE", 18, label, (16, 8))
        self.text(self.score, 32, WHITE, (16, 22))
        self.text("LEVEL", 18, label, (120, 8))
        self.text(self.level, 32, (170, 230, 255), (120, 22))
        self.text("TIME", 18, label, (196, 8))
        low = self.time_left < 10
        color = (255, 80, 70) if low and int(self.time * 4) % 2 == 0 else (255, 160, 150) if low else WHITE
        self.text(f"{math.ceil(self.time_left)}", 32, color, (196, 22))
        self.text("BEST", 18, label, (272, 8))
        self.text(max(self.best, self.score), 32, GOLD, (272, 22))
        pygame.draw.circle(scr, GOLD, (382, 32), 10)
        pygame.draw.circle(scr, (255, 240, 160), (382, 32), 5)
        self.text(f"x {self.coins}", 30, GOLD, (398, 22))
        self.text("SPEED", 18, label, (W - 120, 8))
        bar = pygame.Rect(W - 120, 26, 100, 14)
        pygame.draw.rect(scr, (50, 34, 60), bar, border_radius=4)
        fill = clamp(abs(self.car.speed) / BOOST_SPEED, 0, 1)
        pygame.draw.rect(scr, BOOST if self.car.boost > 0 else (250, 120, 90),
                         (bar.x, bar.y, round(bar.w * fill), bar.h), border_radius=4)
        pygame.draw.line(scr, WHITE, (bar.x + bar.w * MAX_SPEED // BOOST_SPEED, bar.y - 2),
                         (bar.x + bar.w * MAX_SPEED // BOOST_SPEED, bar.bottom + 1), 2)

    def dim(self):
        shade = pygame.Surface((W, H))
        shade.fill((14, 6, 20))
        shade.set_alpha(195)
        self.screen.blit(shade, (0, 0))

    def draw_title(self):
        self.dim()
        self.text("TRACK OF", 86, WHITE, (W // 2, 92), "center")
        for dx, dy, color in ((4, 5, EDGE_DARK), (0, 0, (255, 70, 60))):
            self.text("DOOM", 150, color, (W // 2 + dx, 176 + dy), "center")
        self.text("A race car on a track floating over the void.", 28, (226, 214, 230), (W // 2, 250), "center")
        lines = [
            ("Up / Down", "speed up / brake"),
            ("Left / Right", "steer round the sharp turns"),
            ("Space", "jump"),
            ("Ramps", "fly over the spike pits"),
            ("Smashers", "slam down every 2 seconds"),
            ("Spiky balls", "somewhere new every level"),
            ("Blue pads", "speed boost"),
            ("Off the edge?", "back to the start of the level"),
            ("The clock", "each level adds time - don't run out"),
        ]
        for i, (key, what) in enumerate(lines):
            y = 290 + i * 33
            self.text(key, 30, GOLD, (W // 2 - 60, y), "topright")
            self.text(what, 26, (230, 224, 236), (W // 2 - 44, y + 3))
        if self.rankings():
            score, level, name = self.rankings()[0]
            self.text(f"Best so far: {score} by {name or '?'} (level {level})",
                      26, GOLD, (W // 2, 618), "center")
        glow = 150 + int(80 * (0.5 + 0.5 * math.sin(self.time * 3)))
        self.text("Press SPACE to race", 44, (255, glow, glow // 2), (W // 2, 672), "center")

    def draw_name(self):
        self.dim()
        self.text("TIME'S UP!", 64, (255, 100, 80), (W // 2, 150), "center")
        self.text(f"Score  {self.score}", 52, WHITE, (W // 2, 230), "center")
        self.text(f"level {self.level},  {int(self.far / PX_PER_M)} m,  {self.coins} coins,  {self.crashes} crashes",
                  27, (200, 190, 210), (W // 2, 272), "center")
        self.text("Your name for the leaderboard:", 28, (180, 170, 190), (W // 2, 370), "center")
        box = pygame.Rect(W // 2 - 190, 394, 380, 56)
        pygame.draw.rect(self.screen, (30, 16, 38), box, border_radius=8)
        pygame.draw.rect(self.screen, GOLD, box, 2, border_radius=8)
        cursor = "|" if int(self.time * 2) % 2 == 0 else ""
        self.text(self.name + cursor, 40, GOLD if self.name_fresh else WHITE,
                  (box.x + 16, box.centery), "midleft")
        self.text("Type to change it", 26, (200, 190, 210), (W // 2, 482), "center")
        self.text("Down arrow: another silly name", 26, (200, 190, 210), (W // 2, 510), "center")
        self.text("Enter: save my score", 36, WHITE, (W // 2, 570), "center")

    def draw_over(self):
        self.dim()
        self.text("TIME'S UP!", 60, (255, 100, 80), (W // 2, 110), "center")
        self.text(f"Level {self.level}   -   {self.score} points", 34, (230, 220, 236), (W // 2, 166), "center")
        if self.new_best:
            self.text("A NEW BEST!", 34, (150, 240, 140), (W // 2, 208), "center")
        shared = self.online is not None
        self.text("Leaderboard shared with every player" if shared
                  else "Scores saved on this device", 24, (180, 170, 190), (W // 2, 250), "center")
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
            score, level, name = rows[i]
            self.text(f"{i + 1}.   {name or '?'}   {score} points   (level {level})", 27,
                      GOLD if i == mine_at else (226, 218, 232),
                      (W // 2, top + (i - self.scroll) * 30), "center")
        if most:
            # a scroll bar beside the list, and a hint for how to move it
            track = pygame.Rect(W - 34, top - 12, 6, VISIBLE_RANKINGS * 30 - 4)
            pygame.draw.rect(self.screen, (60, 40, 70), track, border_radius=3)
            thumb_h = max(14, track.h * VISIBLE_RANKINGS // len(rows))
            thumb_y = track.y + (track.h - thumb_h) * self.scroll // most
            pygame.draw.rect(self.screen, GOLD, (track.x, thumb_y, track.w, thumb_h), border_radius=3)
            self.text("Up / Down or mouse wheel to scroll", 22, (170, 160, 180),
                      (W // 2, top + VISIBLE_RANKINGS * 30 - 4), "center")
        glow = 150 + int(80 * (0.5 + 0.5 * math.sin(self.time * 3)))
        self.text("Press SPACE to race again", 38, (255, glow, glow // 2), (W // 2, 520), "center")
        self.text("Esc to leave" if not WEB else "Esc for the title",
                  26, (180, 170, 190), (W // 2, 566), "center")


async def main():
    pygame.init()
    pygame.display.set_caption("Track of Doom")
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
