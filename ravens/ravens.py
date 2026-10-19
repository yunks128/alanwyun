"""Ravens from the Underworld - they come up out of the hole, and you have a rocket launcher.

Controls
    Left / Right arrows   move
    Space                 fire a rocket straight up
    P or Esc              pause

Ravens climb out of the burning hole at the bottom right, settle into the sky
and drop pellets on you. Three pellets is all it takes. Rockets only go
straight up, so you have to stand under a raven to get it - and the blast
takes out anything else close by, pellets included.

Every wave the ravens fly a little faster.

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
HUD_H = 56
GROUND_Y = 500         # top of the ground
SKY_TOP = HUD_H + 26   # ravens never fly above this
SKY_LOW = 250          # ...nor cruise below this

PW, PH = 26, 44        # player size
SPEED = 268
LIVES = 3
HIT_GRACE = 1.7        # blinking safety after a pellet gets you

HOLE = pygame.Rect(806, GROUND_Y - 16, 128, 48)   # the hole, bottom right

ROCKET_SPEED = 660
ROCKET_COOLDOWN = 0.62
BLAST_R = 76           # an explosion kills ravens within this
BLAST_TIME = 0.34

RAVEN_W, RAVEN_H = 38, 24
RAVEN_BASE_SPEED = 78
WAVE_SPEEDUP = 0.11    # each wave the ravens fly this much faster
MAX_SPEEDUP = 2.6
RISE_SPEED = 150       # how fast they climb out of the hole

PELLET_SPEED = 300
PELLET_R = 5
# A loaded raven fires the moment it enters this window, so the pellet lands at
# the edge of it - keep it inside the player's half-width or every shot misses.
PELLET_AIM = 11

RAVEN_POINTS = 15
WAVE_BONUS = 50

SCORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ravens_scores.json")
SCORE_KEY = "ravens-scores"        # browser localStorage key used instead of the file
MAX_RANKINGS = 5
RANKING_POOL = 100     # rows pulled from the database before keeping one per name
MAX_NAME_LEN = 16
NAME_KEY_DELAY = 0.5   # keys mashed while dying are ignored this long on the name screen
# Shared online ranking (the same Firebase database the other games use).
# Leave the address empty to keep rankings on this device only.
LEADERBOARD_URL = "https://alien-boom-boom-default-rtdb.firebaseio.com"
LEADERBOARD_PATH = "/ravens-scores.json"
LEADERBOARD_TIMEOUT_S = 5
FUN_NAMES = [
    "Beak Breaker", "Rocket Gran", "Feather Duster", "Sir Caw-a-Lot", "Ash Walker",
    "Bird Bother", "Pellet Dodger", "Smoky Pete", "Night Shrieker", "Boom Gardener",
]

EMBER = (255, 146, 62)
BLOOD = (206, 62, 74)
BONE = (238, 232, 226)
ROCK = (48, 40, 46)
RAVEN_BLACK = (28, 24, 32)


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


def best_per_name(rankings):
    """One row per player, their best, so nobody can fill the whole ranking.

    Names are matched ignoring case and spacing, and rows are (score, wave, name),
    so the plain tuple comparison keeps the highest score.
    """
    best = {}
    for row in rankings:
        key = " ".join(row[2].split()).lower()
        if key not in best or row > best[key]:
            best[key] = row
    return sorted(best.values(), reverse=True)


def fetch_online_rankings():
    """Top (score, wave, name) rows from the shared ranking, best first, or None if it can't be reached."""
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


def make_backdrop():
    """A sickly underworld sky over jagged rock."""
    rng = random.Random(5)
    s = pygame.Surface((W, H))
    for y in range(H):
        t = y / H
        s.fill((int(18 + 46 * t), int(12 + 20 * t), int(28 + 16 * t)), (0, y, W, 1))
    for _ in range(90):           # embers hanging in the air
        x, y = rng.randint(0, W), rng.randint(HUD_H, GROUND_Y)
        d = rng.randint(0, 60)
        pygame.draw.circle(s, (120 + d, 60 + d // 2, 50), (x, y), rng.choice((1, 1, 2)))

    # far spires
    for layer, (color, base, tall) in enumerate((((36, 24, 38), 470, 150), ((26, 18, 30), 500, 210))):
        x = -40
        while x < W + 40:
            w = rng.randint(50, 130)
            h = rng.randint(tall // 2, tall)
            pygame.draw.polygon(s, color, [(x, base), (x + w // 2, base - h), (x + w, base)])
            x += rng.randint(w // 2, w)

    pygame.draw.rect(s, ROCK, (0, GROUND_Y, W, H - GROUND_Y))
    pygame.draw.rect(s, (66, 54, 60), (0, GROUND_Y, W, 6))
    for _ in range(170):          # cracks and grit in the rock
        x = rng.randint(0, W)
        y = rng.randint(GROUND_Y + 8, H - 4)
        d = rng.randint(-8, 10)
        pygame.draw.rect(s, (48 + d, 40 + d, 46 + d), (x, y, rng.randint(2, 9), 2))
    return s


RAVEN_CY = 24          # where the body sits inside the drawn frame


def make_raven_frames():
    """Two wing positions, drawn once and flipped as the raven flaps.

    A pure black bird vanishes against this sky, so everything gets a cold rim
    light to keep the silhouette readable.
    """
    rim = (86, 78, 100)
    feather = (56, 50, 70)
    frames = []
    for up in (True, False):
        s = pygame.Surface((RAVEN_W, RAVEN_H + 26), pygame.SRCALPHA)
        cy = RAVEN_CY
        # the far wing sits behind everything, the near one on top, both swept
        far = ([(15, cy - 3), (26, cy - 17), (29, cy - 4)] if up
               else [(15, cy + 1), (26, cy + 13), (29, cy + 2)])
        near = ([(13, cy - 2), (19, cy - 21), (27, cy - 5)] if up
                else [(13, cy + 1), (19, cy + 16), (27, cy + 2)])
        pygame.draw.polygon(s, feather, far)

        pygame.draw.polygon(s, RAVEN_BLACK,                        # tail
                            [(26, cy - 4), (RAVEN_W - 1, cy - 9), (RAVEN_W - 1, cy + 3), (26, cy + 4)])
        pygame.draw.ellipse(s, RAVEN_BLACK, (8, cy - 7, 23, 14))   # body
        pygame.draw.ellipse(s, rim, (8, cy - 7, 23, 14), 1)
        pygame.draw.circle(s, RAVEN_BLACK, (9, cy - 7), 7)         # head
        pygame.draw.circle(s, rim, (9, cy - 7), 7, 1)
        pygame.draw.polygon(s, (232, 182, 72),                     # beak
                            [(4, cy - 9), (-3, cy - 5), (4, cy - 1)])
        pygame.draw.polygon(s, RAVEN_BLACK, near)
        pygame.draw.circle(s, BLOOD, (7, cy - 9), 3)               # eye
        pygame.draw.circle(s, (255, 214, 206), (6, cy - 10), 1)
        frames.append(s)
    return frames


class Rocket:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.trail = 0.0

    @property
    def rect(self):
        return pygame.Rect(round(self.x) - 4, round(self.y) - 12, 8, 24)


class Blast:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.life = BLAST_TIME

    @property
    def radius(self):
        return BLAST_R * (1 - (self.life / BLAST_TIME) ** 2) ** 0.5


class Pellet:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)

    @property
    def rect(self):
        return pygame.Rect(round(self.x) - PELLET_R, round(self.y) - PELLET_R,
                           PELLET_R * 2, PELLET_R * 2)


class Raven:
    def __init__(self, speed):
        self.x = float(HOLE.centerx - RAVEN_W // 2)
        self.y = float(HOLE.centery)
        self.speed = speed
        self.rising = True
        self.roost = random.randint(SKY_TOP, SKY_LOW)   # the height it settles at
        self.dir = -1                                    # out of the hole, head left
        self.bob = random.uniform(0, math.tau)
        self.drop = random.uniform(0.8, 2.4)
        self.flap = random.uniform(0, math.tau)

    @property
    def rect(self):
        return pygame.Rect(round(self.x), round(self.y), RAVEN_W, RAVEN_H)

    @property
    def center(self):
        return self.x + RAVEN_W / 2, self.y + RAVEN_H / 2


class Player:
    def __init__(self):
        self.x = float(W // 2 - PW // 2)
        self.lives = LIVES
        self.cooldown = 0.0
        self.grace = 0.0
        self.step = 0.0
        self.recoil = 0.0

    @property
    def y(self):
        return GROUND_Y - PH

    @property
    def rect(self):
        return pygame.Rect(round(self.x), self.y, PW, PH)

    @property
    def muzzle(self):
        return self.rect.centerx + 4, self.y - 6


# ------------------------------------------------------------------ the game


class Game:
    def __init__(self, screen):
        self.screen = screen
        self.backdrop = make_backdrop()
        self.ravens_art = make_raven_frames()
        self.hole_glow = make_glow(120, (255, 120, 50), 0.85)
        self.blast_glow = make_glow(110, (255, 190, 90), 1.0)
        self.fonts = {}
        self.time = 0.0
        self.state = "title"           # title, play, name, dead
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
        self.player = Player()
        self.score = 0
        self.wave = 0
        self.ravens = []
        self.rockets = []
        self.pellets = []
        self.blasts = []
        self.particles = []
        self.popups = []
        self.to_spawn = 0
        self.spawn_timer = 0.0
        self.banner = ""
        self.banner_t = 0.0
        self.shake = 0.0
        self.paused = False
        self.new_best = False
        self.start_wave()

    def start_wave(self):
        self.wave += 1
        self.to_spawn = 2 + self.wave * 2
        self.spawn_timer = 0.8
        self.say(f"WAVE {self.wave}" if self.wave == 1 else f"WAVE {self.wave}  -  FASTER")

    def say(self, msg):
        self.banner, self.banner_t = msg, 1.8

    @property
    def raven_speed(self):
        """Ravens fly a little faster every wave."""
        return RAVEN_BASE_SPEED * min(1 + WAVE_SPEEDUP * (self.wave - 1), MAX_SPEEDUP)

    # ------------------------------------------------------------ the scores

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
                return                  # ignore whatever was being mashed as you died
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
        self.shake = max(0, self.shake - dt * 2.5)
        if self.state != "play" or self.paused:
            return
        p = self.player

        # --- walking
        direction = (1 if keys[pygame.K_RIGHT] else 0) - (1 if keys[pygame.K_LEFT] else 0)
        if direction:
            p.x = clamp(p.x + direction * SPEED * dt, 8, W - PW - 8)
            p.step += dt
        p.cooldown = max(0, p.cooldown - dt)
        p.grace = max(0, p.grace - dt)
        p.recoil = max(0, p.recoil - dt * 4)

        # --- firing straight up
        if keys[pygame.K_SPACE] and p.cooldown <= 0:
            p.cooldown = ROCKET_COOLDOWN
            p.recoil = 1.0
            self.rockets.append(Rocket(*p.muzzle))

        self.move_rockets(dt)
        self.move_ravens(dt)
        self.move_pellets(dt)
        self.fade_effects(dt)

        if self.to_spawn:
            self.spawn_timer -= dt
            if self.spawn_timer <= 0:
                self.ravens.append(Raven(self.raven_speed))
                self.to_spawn -= 1
                self.spawn_timer = max(0.28, 0.95 - self.wave * 0.04)

        if not self.to_spawn and not self.ravens:
            self.score += WAVE_BONUS
            self.start_wave()

    def move_rockets(self, dt):
        for rocket in self.rockets[:]:
            rocket.y -= ROCKET_SPEED * dt
            rocket.trail += dt
            hit = next((r for r in self.ravens if r.rect.colliderect(rocket.rect)), None)
            if hit or rocket.y <= HUD_H + 6:
                self.rockets.remove(rocket)
                self.explode(rocket.x, rocket.y)

    def explode(self, x, y):
        self.blasts.append(Blast(x, y))
        self.shake = 0.5
        self.burst(x, y, EMBER, 26)
        caught = [r for r in self.ravens
                  if math.hypot(r.center[0] - x, r.center[1] - y) <= BLAST_R + RAVEN_H / 2]
        for raven in caught:
            self.kill(raven)
        # the blast clears pellets too, which is what makes standing your ground worth it
        for pellet in self.pellets[:]:
            if math.hypot(pellet.x - x, pellet.y - y) <= BLAST_R:
                self.pellets.remove(pellet)
                self.burst(pellet.x, pellet.y, (150, 130, 160), 5)
        if len(caught) > 1:
            self.popups.append([x, y - 30, f"{len(caught)} AT ONCE!", 1.1])

    def kill(self, raven):
        if raven not in self.ravens:
            return
        self.ravens.remove(raven)
        cx, cy = raven.center
        self.score += RAVEN_POINTS
        self.burst(cx, cy, RAVEN_BLACK, 16)
        self.burst(cx, cy, (90, 80, 96), 8)
        self.popups.append([cx, cy - 14, f"+{RAVEN_POINTS}", 0.8])

    def move_ravens(self, dt):
        p = self.player
        for raven in self.ravens:
            raven.flap += dt * 11
            if raven.rising:
                # climb out of the hole and drift left into the sky
                raven.y -= RISE_SPEED * dt
                raven.x -= raven.speed * 0.55 * dt
                if raven.y <= raven.roost:
                    raven.y = float(raven.roost)
                    raven.rising = False
                continue
            raven.x += raven.dir * raven.speed * dt
            raven.bob += dt * 2.2
            raven.y = raven.roost + math.sin(raven.bob) * 12
            if raven.x < 6:
                raven.x, raven.dir = 6.0, 1
            elif raven.x > W - RAVEN_W - 6:
                raven.x, raven.dir = float(W - RAVEN_W - 6), -1
            # drop a pellet, but only when roughly overhead so it feels aimed
            # once a raven is loaded it waits until it is actually over you, so
            # standing still is never safe and the pellet is worth dodging
            raven.drop -= dt
            if raven.drop <= 0 and abs(raven.center[0] - p.rect.centerx) < PELLET_AIM:
                self.pellets.append(Pellet(raven.center[0], raven.y + RAVEN_H))
                raven.drop = random.uniform(1.4, 3.0) / clamp(self.wave * 0.3, 1, 3)

    def move_pellets(self, dt):
        p = self.player
        for pellet in self.pellets[:]:
            pellet.y += PELLET_SPEED * dt
            if pellet.y > H:
                self.pellets.remove(pellet)
                continue
            if pellet.y >= GROUND_Y and pellet.y < GROUND_Y + 14:
                self.burst(pellet.x, GROUND_Y, (120, 104, 130), 4)
                self.pellets.remove(pellet)
                continue
            if p.grace <= 0 and pellet.rect.colliderect(p.rect):
                self.pellets.remove(pellet)
                self.hurt()
                return

    def hurt(self):
        p = self.player
        p.lives -= 1
        p.grace = HIT_GRACE
        self.shake = 0.8
        cx, cy = p.rect.center
        self.burst(cx, cy, BLOOD, 24)
        # wipe the pellets in the air so you are not hit again the moment the grace ends
        self.pellets.clear()
        if p.lives <= 0:
            self.ask_name()
        else:
            self.say(f"{p.lives} {'LIFE' if p.lives == 1 else 'LIVES'} LEFT")

    # --------------------------------------------------------------- effects

    def burst(self, x, y, color, n):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = random.uniform(50, 250)
            self.particles.append([x, y, math.cos(a) * v, math.sin(a) * v - 40,
                                   random.uniform(0.25, 0.7), color])

    def fade_effects(self, dt):
        for blast in self.blasts[:]:
            blast.life -= dt
            if blast.life <= 0:
                self.blasts.remove(blast)
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

    def draw(self):
        scr = self.screen
        shake = (0, 0)
        if self.shake > 0:
            shake = (random.randint(-5, 5) * self.shake, random.randint(-4, 4) * self.shake)
        scr.blit(self.backdrop, shake)
        self.draw_hole()
        for pellet in self.pellets:
            self.draw_pellet(pellet)
        for raven in self.ravens:
            self.draw_raven(raven)
        for rocket in self.rockets:
            self.draw_rocket(rocket)
        if self.state not in ("name", "dead"):
            self.draw_player()
        self.draw_particles()
        for blast in self.blasts:
            self.draw_blast(blast)
        for pop in self.popups:
            self.text(pop[2], 26, (255, 224, 150), (pop[0], pop[1]), "center")
        if self.state != "title":
            self.draw_hud()
        if self.banner_t > 0 and self.state == "play":
            self.text(self.banner, 58, (255, 214, 180), (W // 2, HUD_H + 64), "center")
        if self.state == "title":
            self.draw_title()
        elif self.state == "name":
            self.draw_name()
        elif self.state == "dead":
            self.draw_over()
        elif self.paused:
            self.dim()
            self.text("PAUSED", 72, BONE, (W // 2, H // 2 - 24), "center")
            self.text("P to carry on", 28, (186, 172, 180), (W // 2, H // 2 + 34), "center")

    def draw_hole(self):
        scr = self.screen
        glow = 0.8 + 0.2 * math.sin(self.time * 2.4)
        scr.blit(self.hole_glow, (HOLE.centerx - 120, HOLE.centery - 120),
                 special_flags=pygame.BLEND_RGB_ADD)
        pygame.draw.ellipse(scr, (16, 10, 14), HOLE)
        inner = HOLE.inflate(-18, -14)
        pygame.draw.ellipse(scr, (int(120 * glow), int(40 * glow), 30), inner)
        pygame.draw.ellipse(scr, (int(210 * glow), int(90 * glow), 40), inner.inflate(-26, -16))
        pygame.draw.ellipse(scr, (30, 22, 26), HOLE, 4)

    def draw_raven(self, raven):
        frame = self.ravens_art[0 if math.sin(raven.flap) > 0 else 1]
        if raven.dir > 0 and not raven.rising:
            frame = pygame.transform.flip(frame, True, False)
        self.screen.blit(frame, (raven.x, raven.y + RAVEN_H / 2 - RAVEN_CY))

    def draw_pellet(self, pellet):
        pygame.draw.circle(self.screen, (176, 150, 190), (int(pellet.x), int(pellet.y)), PELLET_R)
        pygame.draw.circle(self.screen, (96, 74, 110), (int(pellet.x), int(pellet.y)), PELLET_R, 1)

    def draw_rocket(self, rocket):
        x, y = int(rocket.x), int(rocket.y)
        flame = 10 + int(math.sin(self.time * 40) * 4)
        pygame.draw.polygon(self.screen, (255, 190, 90),
                            [(x - 4, y + 10), (x + 4, y + 10), (x, y + 10 + flame)])
        pygame.draw.rect(self.screen, (206, 212, 224), (x - 4, y - 8, 8, 18), border_radius=2)
        pygame.draw.polygon(self.screen, BLOOD, [(x - 4, y - 8), (x + 4, y - 8), (x, y - 17)])

    def draw_blast(self, blast):
        r = max(1, int(blast.radius))
        t = blast.life / BLAST_TIME
        size = max(2, int(r * 1.4))
        self.screen.blit(pygame.transform.smoothscale(self.blast_glow, (size, size)),
                         (blast.x - size // 2, blast.y - size // 2),
                         special_flags=pygame.BLEND_RGB_ADD)
        pygame.draw.circle(self.screen, (255, int(170 * t + 60), 70), (int(blast.x), int(blast.y)), r, 4)

    def draw_player(self):
        p, scr = self.player, self.screen
        r = p.rect
        if p.grace > 0 and math.sin(self.time * 26) < 0:
            return                        # blink while the pellets can't touch you
        sway = math.sin(p.step * 13) * 2
        pygame.draw.ellipse(scr, (28, 22, 28), (r.left - 3, r.bottom - 5, r.w + 6, 10))
        pygame.draw.rect(scr, (52, 46, 62), (r.left + 3, r.centery + 6, 8, r.h // 2 - 8 + sway))
        pygame.draw.rect(scr, (52, 46, 62), (r.right - 11, r.centery + 6, 8, r.h // 2 - 8 - sway))
        pygame.draw.rect(scr, (92, 108, 140), (r.left, r.top + 12, r.w, r.h - 20), border_radius=6)
        pygame.draw.circle(scr, (240, 206, 172), (r.centerx - 2, r.top + 8), 8)
        pygame.draw.rect(scr, (70, 62, 80), (r.centerx - 11, r.top + 1, 18, 6), border_radius=3)

        # the launcher: a fat tube held up beside the head, kicking as it fires
        kick = p.recoil * 7
        tube = pygame.Rect(r.centerx + 5, r.top - 34 + kick, 14, 42)
        pygame.draw.rect(scr, (58, 64, 74), tube, border_radius=4)
        pygame.draw.rect(scr, (92, 100, 112), tube, 2, border_radius=4)
        muzzle = pygame.Rect(tube.left - 4, tube.top - 4, tube.w + 8, 9)
        pygame.draw.rect(scr, (120, 128, 140), muzzle, border_radius=3)
        pygame.draw.ellipse(scr, (26, 22, 28), (tube.left + 2, tube.top - 2, tube.w - 4, 6))
        pygame.draw.rect(scr, (78, 60, 50), (tube.left - 3, tube.bottom - 14, 6, 11), border_radius=2)
        pygame.draw.line(scr, (240, 206, 172), (r.centerx + 2, r.top + 20), (tube.left, tube.bottom - 10), 5)
        ready = p.cooldown <= 0
        pygame.draw.circle(scr, (120, 255, 150) if ready else (210, 90, 70),
                           (tube.right - 3, tube.bottom - 6), 3)
        if p.recoil > 0.2:      # muzzle flash
            pygame.draw.circle(scr, (255, 220, 140), (tube.centerx, tube.top - 4),
                               int(10 * p.recoil))

    def draw_particles(self):
        for x, y, _, _, life, color in self.particles:
            size = max(1, int(life * 7))
            pygame.draw.rect(self.screen, color, (x, y, size, size))

    def draw_hud(self):
        p, scr = self.player, self.screen
        pygame.draw.rect(scr, (20, 14, 22), (0, 0, W, HUD_H))
        pygame.draw.rect(scr, (70, 46, 54), (0, HUD_H - 4, W, 4))

        for i in range(LIVES):
            self.heart(26 + i * 30, 22, i < p.lives)
        self.text("LIVES", 18, (150, 132, 140), (26, 36))

        self.text("SCORE", 18, (150, 132, 140), (150, 8))
        self.text(self.score, 32, BONE, (150, 22))

        self.text("WAVE", 18, (150, 132, 140), (300, 8))
        self.text(self.wave, 32, EMBER, (300, 22))

        self.text("BEST", 18, (150, 132, 140), (410, 8))
        self.text(max(self.best, self.score), 32, (255, 214, 120), (410, 22))

        self.text("ROCKET", 18, (150, 132, 140), (560, 8))
        bar = pygame.Rect(560, 26, 130, 9)
        pygame.draw.rect(scr, (56, 44, 52), bar, border_radius=4)
        ready = 1 - p.cooldown / ROCKET_COOLDOWN
        pygame.draw.rect(scr, (120, 255, 150) if ready >= 1 else (210, 120, 70),
                         (bar.x, bar.y, bar.w * ready, bar.h), border_radius=4)

        left = len(self.ravens) + self.to_spawn
        self.text(f"Ravens left: {left}", 26, (214, 186, 220), (W - 20, 16), "topright")

    def heart(self, x, y, full):
        color = (236, 72, 96) if full else (62, 48, 54)
        pygame.draw.circle(self.screen, color, (x - 5, y - 3), 6)
        pygame.draw.circle(self.screen, color, (x + 5, y - 3), 6)
        pygame.draw.polygon(self.screen, color, [(x - 11, y), (x + 11, y), (x, y + 12)])

    def dim(self):
        shade = pygame.Surface((W, H))
        shade.fill((10, 6, 12))
        shade.set_alpha(190)
        self.screen.blit(shade, (0, 0))

    def draw_title(self):
        self.dim()
        self.text("RAVENS", 92, (236, 92, 104), (W // 2, 78), "center")
        self.text("FROM THE UNDERWORLD", 54, (255, 170, 90), (W // 2, 142), "center")
        self.text("They are climbing out of the hole. You have a rocket launcher.",
                  28, (214, 200, 206), (W // 2, 198), "center")
        lines = [
            ("Left / Right", "run along the ground"),
            ("Space", "fire a rocket straight up"),
            ("Watch out", "ravens drop pellets - three of them and you are done"),
            ("The blast", "kills every raven near it, and wipes out pellets"),
            ("P", "pause"),
        ]
        for i, (key, what) in enumerate(lines):
            y = 252 + i * 40
            self.text(key, 30, (255, 214, 120), (W // 2 - 30, y), "topright")
            self.text(what, 27, (218, 212, 220), (W // 2 - 4, y + 3))
        self.text("Every wave they fly a little faster.", 26, (176, 160, 172), (W // 2, 462), "center")
        if self.rankings():
            score, wave, name = self.rankings()[0]
            self.text(f"Best so far: {score} by {name or '?'} (wave {wave})",
                      26, (255, 214, 120), (W // 2, 492), "center")
        glow = 150 + int(80 * (0.5 + 0.5 * math.sin(self.time * 3)))
        self.text("Press SPACE to begin", 40, (255, glow, glow // 2), (W // 2, 540), "center")

    def draw_name(self):
        self.dim()
        self.text("THE RAVENS GOT YOU", 72, (236, 92, 104), (W // 2, 116), "center")
        self.text(f"You lasted to wave {self.wave}", 30, (214, 206, 212), (W // 2, 172), "center")
        self.text(f"Score  {self.score}", 48, BONE, (W // 2, 224), "center")
        self.text("Your name for the leaderboard:", 28, (166, 150, 160), (W // 2, 288), "center")
        box = pygame.Rect(W // 2 - 190, 312, 380, 56)
        pygame.draw.rect(self.screen, (28, 20, 26), box, border_radius=8)
        pygame.draw.rect(self.screen, (255, 214, 120), box, 2, border_radius=8)
        cursor = "|" if int(self.time * 2) % 2 == 0 else ""
        self.text(self.name + cursor, 40, (255, 214, 120) if self.name_fresh else BONE,
                  (box.x + 16, box.centery), "midleft")
        self.text("Type to change it        Down arrow: another silly name",
                  26, (186, 174, 184), (W // 2, 400), "center")
        self.text("Enter: save my score", 34, BONE, (W // 2, 456), "center")

    def draw_over(self):
        self.dim()
        self.text("THE RAVENS GOT YOU", 72, (236, 92, 104), (W // 2, 92), "center")
        self.text(f"Wave {self.wave}   -   {self.score} points", 34, (214, 206, 212),
                  (W // 2, 150), "center")
        if self.new_best:
            self.text("A NEW BEST!", 34, (150, 230, 160), (W // 2, 192), "center")
        shared = self.online is not None
        self.text("Leaderboard shared with every player" if shared
                  else "Scores saved on this device", 24, (166, 150, 160), (W // 2, 230), "center")
        rows = self.rankings()[:MAX_RANKINGS]
        if not rows:
            self.text("No scores yet. You are the first!", 28, (255, 170, 90),
                      (W // 2, 286), "center")
        marked = False
        for i, row in enumerate(rows):
            score, wave, name = row
            mine = not marked and row == self.mine
            marked = marked or mine
            self.text(f"{i + 1}.   {name or '?'}   {score} points   (wave {wave})", 27,
                      (255, 214, 120) if mine else (210, 202, 212),
                      (W // 2, 272 + i * 29), "center")
        glow = 150 + int(80 * (0.5 + 0.5 * math.sin(self.time * 3)))
        self.text("Press SPACE to go again", 36, (255, glow, glow // 2), (W // 2, 452), "center")
        self.text("Esc to leave" if not WEB else "Esc for the title",
                  26, (166, 150, 160), (W // 2, 500), "center")


async def main():
    pygame.init()
    pygame.display.set_caption("Ravens from the Underworld")
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
