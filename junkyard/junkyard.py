"""Junkyard Nights - trapped in an eerie junkyard with the purple blobs.

Controls
    Left / Right / Up / Down   move
    Space                      swing your sword
    B                          set off a bomb you picked up
    P or Esc                   pause

Blobs ooze out of the dark and take a life if they touch you, and you only have
three. Cut them down before they reach you, and grab what the junk coughs up:
bombs that clear the whole yard, and upgrades that make your sword longer or
quicker.

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

W, H = 960, 600
FPS = 60
HUD_H = 64             # the strip along the top; the yard is everything below it
EDGE = 18              # how close to the fence you can get

PW, PH = 26, 30        # player size
SPEED = 232
HIT_GRACE = 1.6        # seconds of blinking safety after a blob gets you
LIVES = 3

SCORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "junkyard_scores.json")
SCORE_KEY = "junkyard-scores"      # browser localStorage key used instead of the file
MAX_RANKINGS = 5
MAX_NAME_LEN = 16
NAME_KEY_DELAY = 0.5   # keys mashed while dying are ignored this long on the name screen
# Shared online ranking (the same Firebase database the other two games use).
# Leave the address empty to keep rankings on this device only.
LEADERBOARD_URL = "https://alien-boom-boom-default-rtdb.firebaseio.com"
LEADERBOARD_PATH = "/junkyard-scores.json"
LEADERBOARD_TIMEOUT_S = 5
FUN_NAMES = [
    "Scrap Goblin", "Blob Masher", "Rust Bucket", "Sir Clangs-a-Lot", "Tyre Fire",
    "Midnight Welder", "Fridge Wrangler", "Oil Slick", "Crane Dancer", "Bin Raider",
]

# Sword levels. Picking up an upgrade moves you one step along one of these.
SWORD_REACH = [60, 76, 92, 108]
SWORD_COOLDOWN = [0.55, 0.44, 0.35, 0.28, 0.22]
SWING_TIME = 0.17
ARC_HALF = math.radians(58)    # the swing covers this much either side of where you face

BLOB_POINTS = 10
WAVE_BONUS = 40
SPAWN_FADE = 0.9       # a blob is see-through and harmless this long after it appears
SPAWN_CLEAR = 230      # ...and never appears closer to you than this
ITEM_CAP = 4           # at most this many items lying around at once
DROP_CHANCE = 0.12     # chance a dead blob leaves something behind
LAMP_R = 190           # how far a floodlight throws its light
GLOW_STEPS = 7         # brightnesses kept ready for the flicker

JUNK_SIZES = {
    "car": (120, 56), "fridge": (40, 62), "barrel": (34, 34),
    "tyres": (46, 46), "crate": (52, 44),
}

DARK = (12, 16, 18)
RUST = (150, 86, 48)
BLOB_SKIN = (158, 86, 214)
BLOB_DARK = (96, 44, 148)
STEEL = (206, 212, 224)
BONE = (236, 240, 245)
GHOST_GREEN = (150, 220, 180)


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


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


def fetch_online_rankings():
    """Top (score, wave, name) rows from the shared ranking, best first, or None if it can't be reached."""
    query = f"?orderBy=%22score%22&limitToLast={MAX_RANKINGS}"
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
    return sorted(rankings, reverse=True)


def angle_gap(a, b):
    """How far apart two angles are, in radians, never more than pi."""
    return abs((a - b + math.pi) % math.tau - math.pi)


# --------------------------------------------------------------- pretty bits


def make_ground():
    """The junkyard floor: packed dirt, oil stains and old tyre tracks."""
    rng = random.Random(11)
    s = pygame.Surface((W, H - HUD_H))
    s.fill((26, 30, 30))
    for _ in range(90):           # patches of lighter dirt
        x, y = rng.randint(0, W), rng.randint(0, H - HUD_H)
        r = rng.randint(30, 90)
        pygame.draw.ellipse(s, (30, 34, 33), (x - r, y - r // 2, r * 2, r))
    for _ in range(26):           # oil stains
        x, y = rng.randint(0, W), rng.randint(0, H - HUD_H)
        r = rng.randint(12, 34)
        pygame.draw.ellipse(s, (20, 22, 24), (x - r, y - r // 2, r * 2, r))
    for _ in range(7):            # tyre tracks wandering across the yard
        y = rng.randint(20, H - HUD_H - 20)
        step = rng.choice((-1, 1))
        for x in range(0, W, 16):
            y = clamp(y + rng.randint(-3, 3) * step, 10, H - HUD_H - 10)
            pygame.draw.rect(s, (22, 25, 26), (x, y, 9, 4))
            pygame.draw.rect(s, (22, 25, 26), (x, y + 16, 9, 4))
    for _ in range(1400):         # grit
        x, y = rng.randint(0, W - 1), rng.randint(0, H - HUD_H - 1)
        d = rng.randint(-6, 8)
        s.set_at((x, y), (26 + d, 30 + d, 30 + d))
    return s


def make_vignette():
    """Darkness closing in around the edges of the yard."""
    s = pygame.Surface((W, H - HUD_H), pygame.SRCALPHA)
    s.fill((3, 6, 8, 205))
    base = s.get_rect().inflate(260, 200)
    steps = 56
    for i in range(steps):
        t = i / (steps - 1)
        alpha = int(205 * (1 - t) ** 1.7)
        rect = base.inflate(-base.w * 0.99 * t, -base.h * 0.99 * t)
        rect.center = base.center
        pygame.draw.ellipse(s, (3, 6, 8, alpha), rect)
    return s


def make_fog():
    """One drifting bank of mist, blitted a few times at different spots."""
    s = pygame.Surface((320, 190), pygame.SRCALPHA)
    base = s.get_rect()
    steps = 22
    for i in range(steps):
        t = i / (steps - 1)
        alpha = int(3 + 20 * t)
        rect = base.inflate(-base.w * 0.95 * t, -base.h * 0.95 * t)
        rect.center = base.center
        pygame.draw.ellipse(s, (150, 172, 168, alpha), rect)
    return s


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


def make_junk(rng, safe):
    """Scatter wrecks around the yard, leaving room to walk and a clear start."""
    junk = []
    kinds = list(JUNK_SIZES)
    for _ in range(500):
        if len(junk) >= 11:
            break
        kind = rng.choice(kinds)
        w, h = JUNK_SIZES[kind]
        rect = pygame.Rect(rng.randint(EDGE + 12, W - EDGE - 12 - w),
                           rng.randint(HUD_H + EDGE + 12, H - EDGE - 12 - h), w, h)
        if rect.inflate(90, 90).colliderect(safe):
            continue
        # a 60px gap everywhere means there is always a way through
        if any(rect.inflate(60, 60).colliderect(other.rect) for other in junk):
            continue
        junk.append(Junk(rect, kind, rng))
    return junk


class Junk:
    def __init__(self, rect, kind, rng):
        self.rect = rect
        self.kind = kind
        self.tint = rng.randint(-14, 14)
        self.flip = rng.random() < 0.5

    def draw(self, scr):
        r, d = self.rect, self.tint
        shadow = pygame.Rect(r.left - 4, r.bottom - 8, r.w + 8, 14)
        pygame.draw.ellipse(scr, (14, 17, 18), shadow)
        if self.kind == "car":
            body = (74 + d, 60 + d, 66 + d)
            pygame.draw.rect(scr, body, r, border_radius=8)
            cab = pygame.Rect(r.left + (14 if self.flip else 30), r.top - 16, r.w - 44, 22)
            pygame.draw.rect(scr, (60 + d, 50 + d, 56 + d), cab, border_radius=6)
            pygame.draw.rect(scr, (28, 36, 40), cab.inflate(-10, -10), border_radius=3)
            pygame.draw.rect(scr, (RUST[0] + d, RUST[1] + d, RUST[2] + d),
                             (r.left + 10, r.centery, r.w - 20, 7), border_radius=3)
            for wx in (r.left + 16, r.right - 26):
                pygame.draw.circle(scr, (24, 26, 28), (wx, r.bottom - 4), 10)
        elif self.kind == "fridge":
            pygame.draw.rect(scr, (178 + d, 182 + d, 176 + d), r, border_radius=5)
            pygame.draw.rect(scr, (120 + d, 126 + d, 122 + d), r, 3, border_radius=5)
            pygame.draw.line(scr, (120 + d, 126 + d, 122 + d),
                             (r.left + 4, r.centery - 6), (r.right - 4, r.centery - 6), 3)
            pygame.draw.rect(scr, (90 + d, 96 + d, 94 + d), (r.right - 11, r.top + 10, 5, 14), border_radius=2)
        elif self.kind == "barrel":
            pygame.draw.rect(scr, (68 + d, 92 + d, 72 + d), r, border_radius=6)
            pygame.draw.rect(scr, (46 + d, 66 + d, 52 + d), r, 3, border_radius=6)
            pygame.draw.line(scr, (46 + d, 66 + d, 52 + d), (r.left, r.centery), (r.right, r.centery), 3)
            pygame.draw.circle(scr, (120, 190, 130), (r.centerx, r.top + 8), 4)
        elif self.kind == "tyres":
            for i, ry in enumerate((r.bottom - 14, r.bottom - 26, r.bottom - 36)):
                pygame.draw.ellipse(scr, (30 + d, 32 + d, 34 + d), (r.left + i * 3, ry, r.w - i * 6, 18))
                pygame.draw.ellipse(scr, (18, 20, 22), (r.centerx - 7, ry + 4, 14, 10))
        else:  # crate
            pygame.draw.rect(scr, (122 + d, 88 + d, 54 + d), r, border_radius=3)
            pygame.draw.rect(scr, (84 + d, 58 + d, 34 + d), r, 3, border_radius=3)
            pygame.draw.line(scr, (84 + d, 58 + d, 34 + d), r.topleft, r.bottomright, 3)
            pygame.draw.line(scr, (84 + d, 58 + d, 34 + d), r.topright, r.bottomleft, 3)


# ------------------------------------------------------------------ the cast


class Mover:
    """Anything that walks around the yard and bumps into the junk."""

    def slide(self, dx, dy, junk, w, h):
        self.x += dx
        r = pygame.Rect(round(self.x), round(self.y), w, h)
        for piece in junk:
            if r.colliderect(piece.rect):
                self.x = piece.rect.left - w if dx > 0 else piece.rect.right
                r.x = round(self.x)
        self.y += dy
        r = pygame.Rect(round(self.x), round(self.y), w, h)
        for piece in junk:
            if r.colliderect(piece.rect):
                self.y = piece.rect.top - h if dy > 0 else piece.rect.bottom
                r.y = round(self.y)
        self.x = clamp(self.x, EDGE, W - EDGE - w)
        self.y = clamp(self.y, HUD_H + EDGE, H - EDGE - h)


class Player(Mover):
    def __init__(self):
        self.len_lvl = 0
        self.cd_lvl = 0
        self.lives = LIVES
        self.place(W // 2 - PW // 2, (H + HUD_H) // 2)

    def place(self, x, y):
        self.x, self.y = float(x), float(y)
        self.facing = -math.pi / 2     # looking up the yard
        self.cooldown = 0.0
        self.swing = 0.0
        self.swing_hits = []
        self.grace = 0.0
        self.step = 0.0

    @property
    def rect(self):
        return pygame.Rect(round(self.x), round(self.y), PW, PH)

    @property
    def reach(self):
        return SWORD_REACH[self.len_lvl]

    @property
    def cool(self):
        return SWORD_COOLDOWN[self.cd_lvl]

    def swing_angle(self):
        """Where the blade is pointing right now, part way through the swing."""
        done = 1 - self.swing / SWING_TIME
        return self.facing - ARC_HALF + 2 * ARC_HALF * done


class Blob(Mover):
    def __init__(self, x, y, size, wave):
        self.x, self.y = float(x), float(y)
        self.size = size               # 1 small, 2 middling, 3 big
        self.hp = size
        self.r = 11 + 4 * size
        self.speed = (78 - 9 * size) + min(wave * 3.5, 46)
        self.phase = random.uniform(0, math.tau)
        self.spawn = SPAWN_FADE
        self.flash = 0.0
        self.kbx = self.kby = 0.0
        self.detour = 0.0          # >0 while squeezing around a piece of junk
        self.detour_dir = 1

    @property
    def rect(self):
        return pygame.Rect(round(self.x), round(self.y), self.r * 2, self.r * 2)

    @property
    def center(self):
        return self.x + self.r, self.y + self.r

    def wobble(self, time):
        return math.sin(time * 4 + self.phase) * 0.14


class Item:
    SIZE = 24

    def __init__(self, x, y, kind):
        self.rect = pygame.Rect(round(x), round(y), self.SIZE, self.SIZE)
        self.kind = kind
        self.born = 0.0


# ------------------------------------------------------------------ the game


class Game:
    def __init__(self, screen):
        self.screen = screen
        self.ground = make_ground()
        self.vignette = make_vignette()
        self.fog = make_fog()
        # the lamps flicker, so keep a few brightnesses ready rather than
        # building a new glow every frame
        self.glows = [make_glow(LAMP_R, (214, 192, 120), 0.3 + 0.7 * i / (GLOW_STEPS - 1))
                      for i in range(GLOW_STEPS)]
        # a dropped item sits in its own little pool of light, or you would
        # never spot it out in the dark
        self.item_glow = {"bomb": make_glow(34, (255, 160, 80), 0.5),
                          "longer": make_glow(34, (120, 210, 255), 0.5),
                          "faster": make_glow(34, (255, 215, 110), 0.5)}
        self.fonts = {}
        self.time = 0.0
        self.state = "title"           # title, play, name, dead
        self.name = ""
        self.name_fresh = False        # True while the name is an untouched suggestion
        self.name_time = 0.0
        self.mine = None               # the ranking row from the run just played
        self.online = None             # shared ranking once it has been downloaded
        self.scores = self.load_scores()
        self.new_run()
        self.refresh_online()

    # ---------------------------------------------------------------- set up

    def new_run(self):
        self.player = Player()
        self.score = 0
        self.wave = 0
        self.blobs = []
        self.items = []
        self.particles = []
        self.popups = []
        self.bombs = 0
        self.to_spawn = 0
        self.spawn_timer = 0.0
        self.banner = ""
        self.banner_t = 0.0
        self.flash = 0.0
        self.paused = False
        self.new_best = False
        self.junk = make_junk(random, self.player.rect.inflate(150, 150))
        self.lamps = [(W * 0.22, HUD_H + 70), (W * 0.78, H - 90)]
        self.start_wave()

    def start_wave(self):
        self.wave += 1
        self.to_spawn = 3 + self.wave * 2
        self.spawn_timer = 0.5
        self.say(f"WAVE {self.wave}")

    def say(self, msg):
        self.banner, self.banner_t = msg, 1.7

    @property
    def best(self):
        return max((row[0] for row in self.scores), default=0)

    def load_scores(self):
        """This device's top scores as (score, wave, name), plus the last name used."""
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
        """The run is over: ask for a name before saving the score."""
        self.mine = None
        if not self.name:
            self.name = random.choice(FUN_NAMES)
        self.name_fresh = True
        self.name_time = self.time
        self.state = "name"

    def save_score(self):
        """Add this run to this device's top scores and to the shared ranking."""
        self.name = self.name.strip() or random.choice(FUN_NAMES)
        self.mine = (self.score, self.wave, self.name)
        self.new_best = self.score > self.best
        self.scores = sorted(self.scores + [self.mine], reverse=True)[:MAX_RANKINGS]
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
        self.refresh_online({"name": self.name, "score": self.score, "level": self.wave})
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
            # if the score could not be uploaded, fall back to this device's own list
            self.online = rankings
            print("online ranking:", "unavailable" if rankings is None else f"{len(rankings)} scores")

        if WEB:
            work()  # browsers have no threads here; the request is quick
        else:
            threading.Thread(target=work, daemon=True).start()  # don't freeze the game while waiting

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
            elif key == pygame.K_b:
                self.use_bomb()
        elif self.state == "name":
            if self.time - self.name_time < NAME_KEY_DELAY:
                return                  # ignore whatever was being mashed as you died
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.save_score()
            elif key == pygame.K_DOWN:  # (Tab would move the keyboard away from the game in a browser)
                self.name = random.choice([n for n in FUN_NAMES if n != self.name])
                self.name_fresh = True
            elif key == pygame.K_BACKSPACE:
                # the first edit wipes a suggested name so you can just start typing
                self.name = "" if self.name_fresh else self.name[:-1]
                self.name_fresh = False
            elif char and char.isprintable() and (char != " " or (self.name and not self.name_fresh)):
                if self.name_fresh:
                    self.name = ""
                    self.name_fresh = False
                self.name = (self.name + char)[:MAX_NAME_LEN]
        elif self.state == "dead":
            if confirm:
                self.new_run()
                self.state = "play"
            elif key in (pygame.K_ESCAPE, pygame.K_q):
                if WEB:                 # a browser tab can't be closed, so go back to the title
                    self.new_run()
                    self.state = "title"
                else:
                    pygame.event.post(pygame.event.Event(pygame.QUIT))

    # ---------------------------------------------------------------- update

    def update(self, dt, keys):
        self.time += dt
        self.banner_t = max(0, self.banner_t - dt)
        self.flash = max(0, self.flash - dt * 2.4)
        if self.state != "play" or self.paused:
            return
        p = self.player

        # --- walking
        dx = (1 if keys[pygame.K_RIGHT] else 0) - (1 if keys[pygame.K_LEFT] else 0)
        dy = (1 if keys[pygame.K_DOWN] else 0) - (1 if keys[pygame.K_UP] else 0)
        if dx or dy:
            length = math.hypot(dx, dy)
            p.slide(dx / length * SPEED * dt, dy / length * SPEED * dt, self.junk, PW, PH)
            if p.swing <= 0:
                # a swing commits to the way you were facing, so backing off
                # mid-cut doesn't whip the blade around behind you
                p.facing = math.atan2(dy, dx)
            p.step += dt
        p.cooldown = max(0, p.cooldown - dt)
        p.swing = max(0, p.swing - dt)
        p.grace = max(0, p.grace - dt)

        # --- swinging
        if keys[pygame.K_SPACE] and p.cooldown <= 0:
            p.swing = SWING_TIME
            p.cooldown = p.cool
            p.swing_hits = []
        if p.swing > 0:
            self.cut(p)

        # --- blobs crawling in
        if self.to_spawn:
            self.spawn_timer -= dt
            if self.spawn_timer <= 0:
                self.spawn_blob()
                self.spawn_timer = max(0.22, 0.8 - self.wave * 0.03)

        self.move_blobs(dt)
        self.pick_up()
        self.fade_effects(dt)

        if not self.to_spawn and not self.blobs:
            self.score += WAVE_BONUS
            self.drop_reward()
            self.start_wave()

    def cut(self, p):
        """Anything inside the sword's arc that has not been hit this swing takes a chop."""
        cx, cy = p.rect.center
        angle = p.swing_angle()
        for blob in self.blobs[:]:
            if blob.spawn > 0 or blob in p.swing_hits:
                continue
            bx, by = blob.center
            if math.hypot(bx - cx, by - cy) > p.reach + blob.r:
                continue
            if angle_gap(math.atan2(by - cy, bx - cx), angle) > ARC_HALF:
                continue
            p.swing_hits.append(blob)
            self.wound(blob, math.atan2(by - cy, bx - cx))

    def wound(self, blob, away):
        blob.hp -= 1
        blob.flash = 0.12
        blob.kbx += math.cos(away) * 260
        blob.kby += math.sin(away) * 260
        bx, by = blob.center
        self.burst(bx, by, BLOB_SKIN, 7)
        if blob.hp <= 0:
            self.kill(blob, drops=True)

    def kill(self, blob, drops):
        if blob not in self.blobs:
            return
        self.blobs.remove(blob)
        bx, by = blob.center
        points = BLOB_POINTS * blob.size
        self.score += points
        self.burst(bx, by, BLOB_SKIN, 20)
        self.popups.append([bx, by - 16, f"+{points}", 0.8])
        if drops and len(self.items) < ITEM_CAP and random.random() < DROP_CHANCE:
            self.drop(bx, by)

    def spawn_blob(self):
        """Put a blob somewhere in the yard that is clear of junk and well away from you."""
        px, py = self.player.rect.center
        size = self.pick_size()
        r = 11 + 4 * size
        for _ in range(60):
            x = random.randint(EDGE, W - EDGE - r * 2)
            y = random.randint(HUD_H + EDGE, H - EDGE - r * 2)
            if math.hypot(x + r - px, y + r - py) < SPAWN_CLEAR:
                continue
            spot = pygame.Rect(x, y, r * 2, r * 2)
            if any(spot.colliderect(piece.rect) for piece in self.junk):
                continue
            self.blobs.append(Blob(x, y, size, self.wave))
            self.to_spawn -= 1
            return
        self.to_spawn -= 1     # the yard is crowded tonight; skip this one

    def pick_size(self):
        roll = random.random()
        if self.wave >= 6 and roll < 0.2:
            return 3
        if self.wave >= 3 and roll < 0.38:
            return 2
        return 1

    def move_blobs(self, dt):
        p = self.player
        px, py = p.rect.center
        for blob in self.blobs[:]:
            blob.flash = max(0, blob.flash - dt)
            if blob.spawn > 0:
                blob.spawn -= dt
                continue
            bx, by = blob.center
            dx, dy = px - bx, py - by
            dist = math.hypot(dx, dy) or 1
            for other in self.blobs:        # don't pile up on top of each other
                if other is blob:
                    continue
                ox, oy = other.center
                gap = math.hypot(ox - bx, oy - by)
                if 0 < gap < blob.r + other.r:
                    dx -= (ox - bx) / gap * 40
                    dy -= (oy - by) / gap * 40
            step = blob.speed * dt
            length = math.hypot(dx, dy) or 1
            ux, uy = dx / length, dy / length
            if blob.detour > 0:
                # slide along whatever is in the way, still leaning towards you,
                # otherwise a blob pinned against a wreck would never get round it
                blob.detour -= dt
                ux, uy = -uy * blob.detour_dir + ux * 0.35, ux * blob.detour_dir + uy * 0.35
                side = math.hypot(ux, uy) or 1
                ux, uy = ux / side, uy / side
            was = (blob.x, blob.y)
            blob.slide(ux * step + blob.kbx * dt, uy * step + blob.kby * dt,
                       self.junk, blob.r * 2, blob.r * 2)
            if blob.detour <= 0 and math.hypot(blob.x - was[0], blob.y - was[1]) < step * 0.4:
                blob.detour = 0.75          # jammed: try going round the other way
                blob.detour_dir = random.choice((-1, 1))
            blob.kbx *= max(0, 1 - 6 * dt)
            blob.kby *= max(0, 1 - 6 * dt)
            if p.grace <= 0 and blob.rect.inflate(-6, -6).colliderect(p.rect):
                self.hurt()
                return

    def hurt(self):
        p = self.player
        p.lives -= 1
        p.grace = HIT_GRACE
        cx, cy = p.rect.center
        self.burst(cx, cy, (255, 120, 120), 24)
        self.flash = 0.6
        # shove everything back so you are not caught again the instant the grace ends
        for blob in self.blobs:
            bx, by = blob.center
            away = math.atan2(by - cy, bx - cx)
            blob.kbx += math.cos(away) * 420
            blob.kby += math.sin(away) * 420
        if p.lives <= 0:
            self.ask_name()
        else:
            self.say(f"{p.lives} {'LIFE' if p.lives == 1 else 'LIVES'} LEFT")

    # ----------------------------------------------------------------- items

    def kinds_worth_dropping(self):
        p = self.player
        kinds = ["bomb"]
        if p.len_lvl < len(SWORD_REACH) - 1:
            kinds.append("longer")
        if p.cd_lvl < len(SWORD_COOLDOWN) - 1:
            kinds.append("faster")
        return kinds

    def drop(self, x, y):
        kind = random.choice(self.kinds_worth_dropping())
        x = clamp(x - Item.SIZE / 2, EDGE, W - EDGE - Item.SIZE)
        y = clamp(y - Item.SIZE / 2, HUD_H + EDGE, H - EDGE - Item.SIZE)
        item = Item(x, y, kind)
        if any(item.rect.colliderect(piece.rect) for piece in self.junk):
            return
        item.born = self.time
        self.items.append(item)

    def drop_reward(self):
        """Clearing a wave shakes something loose from the junk."""
        for _ in range(2 if random.random() < 0.35 else 1):
            for _ in range(40):
                x = random.randint(EDGE, W - EDGE - Item.SIZE)
                y = random.randint(HUD_H + EDGE, H - EDGE - Item.SIZE)
                spot = pygame.Rect(x, y, Item.SIZE, Item.SIZE)
                if any(spot.colliderect(piece.rect) for piece in self.junk):
                    continue
                if any(spot.colliderect(other.rect) for other in self.items):
                    continue
                self.drop(x + Item.SIZE / 2, y + Item.SIZE / 2)
                break

    def pick_up(self):
        p = self.player
        for item in self.items[:]:
            if not item.rect.colliderect(p.rect):
                continue
            self.items.remove(item)
            if item.kind == "bomb":
                self.bombs += 1
                self.say("BOMB  -  PRESS B")
            elif item.kind == "longer":
                p.len_lvl = min(p.len_lvl + 1, len(SWORD_REACH) - 1)
                self.say("LONGER SWORD")
            else:
                p.cd_lvl = min(p.cd_lvl + 1, len(SWORD_COOLDOWN) - 1)
                self.say("FASTER SWORD")

    def use_bomb(self):
        """B sets off one of the bombs you are carrying."""
        if self.state != "play" or self.paused or self.bombs <= 0:
            return
        self.bombs -= 1
        self.blow_up()

    def blow_up(self):
        """A bomb takes out every blob in the yard at once."""
        caught = len(self.blobs)
        for blob in self.blobs[:]:
            self.kill(blob, drops=False)
        self.flash = 1.0
        cx, cy = self.player.rect.center
        self.burst(cx, cy, (255, 210, 130), 40)
        self.say(f"BOOM!  {caught} blob{'' if caught == 1 else 's'}" if caught else "BOOM!")

    # --------------------------------------------------------------- effects

    def burst(self, x, y, color, n):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = random.uniform(50, 260)
            self.particles.append([x, y, math.cos(a) * v, math.sin(a) * v,
                                   random.uniform(0.25, 0.65), color])

    def fade_effects(self, dt):
        for part in self.particles[:]:
            part[0] += part[2] * dt
            part[1] += part[3] * dt
            part[2] *= max(0, 1 - 2.5 * dt)
            part[3] *= max(0, 1 - 2.5 * dt)
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

    def draw(self):
        scr = self.screen
        scr.blit(self.ground, (0, HUD_H))
        self.draw_lamps()
        for piece in sorted(self.junk, key=lambda j: j.rect.bottom):
            piece.draw(scr)
        self.draw_items()
        for blob in sorted(self.blobs, key=lambda b: b.y):
            self.draw_blob(blob)
        if self.state not in ("name", "dead"):
            self.draw_player()
        self.draw_particles()
        scr.blit(self.vignette, (0, HUD_H))
        self.draw_fog()
        for pop in self.popups:
            self.text(pop[2], 26, (255, 236, 160), (pop[0], pop[1]), "center")
        if self.flash > 0:
            glare = pygame.Surface((W, H - HUD_H))
            glare.fill((255, 235, 190))
            glare.set_alpha(int(150 * min(1, self.flash)))
            scr.blit(glare, (0, HUD_H))
        if self.state != "title":       # nothing to count before you go in
            self.draw_hud()
        if self.banner_t > 0 and self.state == "play":
            self.text(self.banner, 60, (236, 226, 255), (W // 2, HUD_H + 70), "center")
        if self.state == "title":
            self.draw_title()
        elif self.state == "name":
            self.draw_name()
        elif self.state == "dead":
            self.draw_over()
        elif self.paused:
            self.dim()
            self.text("PAUSED", 72, BONE, (W // 2, H // 2 - 24), "center")
            self.text("P to carry on", 28, (176, 180, 196), (W // 2, H // 2 + 34), "center")

    def draw_lamps(self):
        """Two tired floodlights, buzzing and flickering over the yard."""
        for i, (lx, ly) in enumerate(self.lamps):
            flicker = 0.74 + 0.26 * math.sin(self.time * (7 + i * 3)) * math.sin(self.time * 2.3 + i)
            if random.random() < 0.015:
                flicker *= 0.4
            level = int(clamp(flicker, 0, 1) * (GLOW_STEPS - 1))
            self.screen.blit(self.glows[level], (lx - LAMP_R, ly - LAMP_R),
                             special_flags=pygame.BLEND_RGB_ADD)
            pygame.draw.rect(self.screen, (52, 56, 60), (lx - 4, ly - 34, 8, 34))
            bulb = int(150 + 80 * flicker)
            pygame.draw.circle(self.screen, (bulb, bulb - 14, bulb - 70), (int(lx), int(ly - 36)), 7)

    def draw_fog(self):
        for i in range(5):
            drift = (self.time * (9 + i * 4) + i * 260) % (W + 340) - 340
            y = HUD_H + 60 + i * 102 + math.sin(self.time * 0.5 + i) * 18
            self.screen.blit(self.fog, (drift, y))

    def draw_items(self):
        for item in self.items:
            r = item.rect
            bob = math.sin((self.time - item.born) * 3.4) * 3
            spot = r.move(0, bob)
            self.screen.blit(self.item_glow[item.kind], (r.centerx - 34, r.centery - 34),
                             special_flags=pygame.BLEND_RGB_ADD)
            pygame.draw.ellipse(self.screen, (16, 19, 20), (r.left, r.bottom - 5, r.w, 9))
            if item.kind == "bomb":
                pygame.draw.circle(self.screen, (58, 60, 70), spot.center, 11)
                pygame.draw.circle(self.screen, (118, 122, 136), spot.center, 11, 2)
                pygame.draw.circle(self.screen, (176, 182, 196),
                                   (spot.centerx - 4, spot.centery - 4), 3)
                tip = (spot.centerx + 6, spot.top - 2)
                pygame.draw.line(self.screen, (160, 130, 86), (spot.centerx + 3, spot.top + 3), tip, 3)
                spark = 3 + int(math.sin(self.time * 18) * 1.5)
                pygame.draw.circle(self.screen, (255, 210, 110), tip, spark)
            elif item.kind == "longer":
                pygame.draw.line(self.screen, (150, 230, 255),
                                 (spot.centerx, spot.bottom - 2), (spot.centerx, spot.top + 1), 4)
                pygame.draw.line(self.screen, (120, 90, 50),
                                 (spot.left + 4, spot.bottom - 5), (spot.right - 4, spot.bottom - 5), 3)
                pygame.draw.polygon(self.screen, (150, 230, 255),
                                    [(spot.centerx, spot.top - 5), (spot.centerx - 5, spot.top + 2),
                                     (spot.centerx + 5, spot.top + 2)])
            else:
                pygame.draw.polygon(self.screen, (255, 226, 110),
                                    [(spot.centerx + 3, spot.top), (spot.left + 4, spot.centery + 3),
                                     (spot.centerx, spot.centery + 3), (spot.centerx - 3, spot.bottom),
                                     (spot.right - 4, spot.centery - 3), (spot.centerx, spot.centery - 3)])

    def draw_blob(self, blob):
        bx, by = blob.center
        squash = blob.wobble(self.time)
        rx, ry = blob.r * (1 + squash), blob.r * (1 - squash)
        body = pygame.Rect(0, 0, rx * 2, ry * 2)
        body.center = (bx, by)
        skin, dark = (BONE, (190, 190, 200)) if blob.flash > 0 else (BLOB_SKIN, BLOB_DARK)
        surf = self.screen
        if blob.spawn > 0:                # fading in, still harmless
            ghost = pygame.Surface((blob.r * 3, blob.r * 3), pygame.SRCALPHA)
            local = body.move(-body.left + blob.r // 2, -body.top + blob.r // 2)
            alpha = int(200 * (1 - blob.spawn / SPAWN_FADE))
            pygame.draw.ellipse(ghost, (*skin, alpha), local)
            surf.blit(ghost, (bx - blob.r * 1.5, by - blob.r * 1.5))
            return
        pygame.draw.ellipse(surf, (14, 17, 18), (bx - rx, by + ry - 5, rx * 2, 9))
        pygame.draw.ellipse(surf, dark, body.inflate(4, 4))
        pygame.draw.ellipse(surf, skin, body)
        pygame.draw.ellipse(surf, (210, 170, 250), body.inflate(-rx, -ry).move(-rx * 0.2, -ry * 0.3))
        eye = max(2, blob.r // 4)
        for side in (-1, 1):
            ex = bx + side * rx * 0.38
            pygame.draw.circle(surf, (24, 12, 34), (int(ex), int(by - ry * 0.1)), eye)
            pygame.draw.circle(surf, (255, 255, 255), (int(ex + 1), int(by - ry * 0.1 - 1)), max(1, eye // 3))
        for i in range(blob.hp - 1):      # pips showing a tougher blob
            pygame.draw.circle(surf, (255, 235, 255), (int(bx - 5 + i * 10), int(by + ry * 0.45)), 2)

    def draw_player(self):
        p, scr = self.player, self.screen
        r = p.rect
        if p.grace > 0 and math.sin(self.time * 26) < 0:
            return                        # blink while the blobs can't touch you
        pygame.draw.ellipse(scr, (14, 17, 18), (r.left - 2, r.bottom - 6, r.w + 4, 10))
        swayy = math.sin(p.step * 13) * 2
        pygame.draw.rect(scr, (56, 66, 86), (r.left + 3, r.centery + 2, 8, r.h // 2 - 2 + swayy))
        pygame.draw.rect(scr, (56, 66, 86), (r.right - 11, r.centery + 2, 8, r.h // 2 - 2 - swayy))
        pygame.draw.rect(scr, (92, 120, 150), (r.left, r.top + 8, r.w, r.h - 14), border_radius=6)
        pygame.draw.circle(scr, (240, 206, 172), (r.centerx, r.top + 7), 8)
        look = (r.centerx + math.cos(p.facing) * 3, r.top + 6 + math.sin(p.facing) * 3)
        pygame.draw.circle(scr, (40, 34, 40), (int(look[0]), int(look[1])), 2)

        angle = p.swing_angle() if p.swing > 0 else p.facing - ARC_HALF * 0.55
        hand = (r.centerx + math.cos(angle) * 10, r.centery + math.sin(angle) * 10)
        tip = (r.centerx + math.cos(angle) * p.reach, r.centery + math.sin(angle) * p.reach)
        if p.swing > 0:                   # a pale sweep showing what the blade covered
            wedge = pygame.Surface((p.reach * 2 + 8, p.reach * 2 + 8), pygame.SRCALPHA)
            mid = (p.reach + 4, p.reach + 4)
            pts = [mid]
            start = p.facing - ARC_HALF
            steps = 14
            for i in range(steps + 1):
                a = start + (angle - start) * i / steps
                pts.append((mid[0] + math.cos(a) * p.reach, mid[1] + math.sin(a) * p.reach))
            if len(pts) > 2:
                pygame.draw.polygon(wedge, (220, 240, 255, 52), pts)
            scr.blit(wedge, (r.centerx - mid[0], r.centery - mid[1]))
        ready = p.cooldown <= 0
        blade = STEEL if ready else (120, 126, 140)
        pygame.draw.line(scr, (118, 84, 48), (r.centerx, r.centery), hand, 5)
        pygame.draw.line(scr, blade, hand, tip, 4)
        pygame.draw.circle(scr, (150, 110, 60), (int(hand[0]), int(hand[1])), 4)

    def draw_particles(self):
        for x, y, _, _, life, color in self.particles:
            size = max(1, int(life * 7))
            pygame.draw.rect(self.screen, color, (x, y, size, size))

    def draw_hud(self):
        p, scr = self.player, self.screen
        pygame.draw.rect(scr, (18, 22, 24), (0, 0, W, HUD_H))
        pygame.draw.rect(scr, (56, 62, 66), (0, HUD_H - 4, W, 4))

        for i in range(LIVES):
            self.heart(26 + i * 30, 24, i < p.lives)
        self.text("LIVES", 20, (140, 146, 156), (26, 40))

        self.text("SCORE", 20, (140, 146, 156), (160, 10))
        self.text(self.score, 34, BONE, (160, 26))

        self.text("WAVE", 20, (140, 146, 156), (320, 10))
        self.text(self.wave, 34, GHOST_GREEN, (320, 26))

        self.text("BEST", 20, (140, 146, 156), (430, 10))
        self.text(max(self.best, self.score), 34, (255, 226, 130), (430, 26))

        self.text("SWORD", 20, (140, 146, 156), (600, 8))
        self.pips("reach", p.len_lvl, len(SWORD_REACH) - 1, 600, 30, (150, 230, 255))
        self.pips("speed", p.cd_lvl, len(SWORD_COOLDOWN) - 1, 740, 30, (255, 226, 110))

        left = len(self.blobs) + self.to_spawn
        self.text(f"Blobs left: {left}", 26, (206, 170, 240), (W - 20, 10), "topright")
        self.text(f"Bombs: {self.bombs} (B)", 24,
                  (255, 190, 110) if self.bombs else (108, 114, 122), (W - 20, 38), "topright")

    def pips(self, label, level, top, x, y, color):
        self.text(label, 18, (140, 146, 156), (x, y + 1))
        for i in range(top):
            spot = (x + 48 + i * 13, y + 7)
            if i < level:
                pygame.draw.circle(self.screen, color, spot, 5)
            else:
                pygame.draw.circle(self.screen, (72, 78, 84), spot, 5, 2)

    def heart(self, x, y, full):
        color = (236, 72, 96) if full else (62, 50, 56)
        pygame.draw.circle(self.screen, color, (x - 5, y - 3), 6)
        pygame.draw.circle(self.screen, color, (x + 5, y - 3), 6)
        pygame.draw.polygon(self.screen, color, [(x - 11, y), (x + 11, y), (x, y + 12)])

    def dim(self):
        shade = pygame.Surface((W, H))
        shade.fill((6, 8, 10))
        shade.set_alpha(185)
        self.screen.blit(shade, (0, 0))

    def draw_title(self):
        self.dim()
        self.text("JUNKYARD NIGHTS", 86, (206, 170, 240), (W // 2, 108), "center")
        self.text("The gate is locked and something purple is moving out there.",
                  28, (196, 200, 210), (W // 2, 178), "center")
        lines = [
            ("Arrow keys", "walk through the junk"),
            ("Space", "swing your sword (watch the cooldown)"),
            ("B", "set off a bomb - blows up every blob in the yard"),
            ("Upgrades", "a longer sword, or a quicker one"),
            ("P", "pause"),
        ]
        for i, (key, what) in enumerate(lines):
            y = 240 + i * 42
            self.text(key, 32, (255, 226, 130), (W // 2 - 30, y), "topright")
            self.text(what, 28, (214, 218, 228), (W // 2 - 4, y + 4))
        self.text("Three lives. That is all the junkyard gives you.",
                  26, (160, 166, 176), (W // 2, 462), "center")
        if self.rankings():
            score, wave, name = self.rankings()[0]
            self.text(f"Best so far: {score} by {name or '?'} (wave {wave})",
                      26, (255, 226, 130), (W // 2, 492), "center")
        glow = 150 + int(80 * (0.5 + 0.5 * math.sin(self.time * 3)))
        self.text("Press SPACE to go in", 40, (glow, glow, 255 - glow // 3), (W // 2, 530), "center")

    def draw_name(self):
        self.dim()
        self.text("THE BLOBS GOT YOU", 74, (236, 92, 112), (W // 2, 116), "center")
        self.text(f"You lasted to wave {self.wave}", 30, (214, 218, 228), (W // 2, 172), "center")
        self.text(f"Score  {self.score}", 48, BONE, (W // 2, 224), "center")
        self.text("Your name for the leaderboard:", 28, (160, 166, 176), (W // 2, 288), "center")
        box = pygame.Rect(W // 2 - 190, 312, 380, 56)
        pygame.draw.rect(self.screen, (24, 28, 32), box, border_radius=8)
        pygame.draw.rect(self.screen, (255, 226, 130), box, 2, border_radius=8)
        cursor = "|" if int(self.time * 2) % 2 == 0 else ""
        self.text(self.name + cursor, 40, (255, 226, 130) if self.name_fresh else BONE,
                  (box.x + 16, box.centery), "midleft")
        self.text("Type to change it        Down arrow: another silly name",
                  26, (176, 182, 196), (W // 2, 400), "center")
        self.text("Enter: save my score", 34, BONE, (W // 2, 456), "center")

    def draw_over(self):
        self.dim()
        self.text("THE BLOBS GOT YOU", 74, (236, 92, 112), (W // 2, 92), "center")
        self.text(f"Wave {self.wave}   -   {self.score} points", 34, (214, 218, 228),
                  (W // 2, 150), "center")
        if self.new_best:
            self.text("A NEW BEST!", 34, (150, 230, 160), (W // 2, 192), "center")
        shared = self.online is not None
        self.text("Leaderboard shared with every player" if shared
                  else "Scores saved on this device", 24, (150, 156, 166), (W // 2, 230), "center")
        rows = self.rankings()[:MAX_RANKINGS]
        if not rows:
            self.text("No scores yet. You are the first!", 28, (206, 170, 240),
                      (W // 2, 286), "center")
        marked = False
        for i, row in enumerate(rows):
            score, wave, name = row
            mine = not marked and row == self.mine
            marked = marked or mine
            self.text(f"{i + 1}.   {name or '?'}   {score} points   (wave {wave})", 27,
                      (255, 226, 130) if mine else (204, 208, 222),
                      (W // 2, 272 + i * 29), "center")
        glow = 150 + int(80 * (0.5 + 0.5 * math.sin(self.time * 3)))
        self.text("Press SPACE to go back in", 36, (glow, glow, 255 - glow // 3),
                  (W // 2, 452), "center")
        self.text("Esc to leave" if not WEB else "Esc for the title",
                  26, (150, 156, 166), (W // 2, 500), "center")


async def main():
    pygame.init()
    pygame.display.set_caption("Junkyard Nights")
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
        game.update(dt, pygame.key.get_pressed())
        game.draw()
        pygame.display.flip()
        await asyncio.sleep(0)      # hands control back to the browser each frame


if __name__ == "__main__":
    asyncio.run(main())
