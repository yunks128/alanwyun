"""Alien Boom Boom - quick prototype.

Arrow keys: move    Space: shoot    B: fire a bomb    Esc: back to menu
Touch / mouse: tap or hold to shoot, swipe left and right to move.
Coins, shop upgrades and rankings are saved in alien_boom_boom_save.json.
"""
import asyncio
import json
import random
import sys
import threading
import urllib.request
from pathlib import Path

import pygame

# True when running in a web browser (built with pygbag for GitHub Pages)
IS_WEB = sys.platform == "emscripten"

WIDTH, HEIGHT = 600, 800
FPS = 60

PLAYER_SPEED = 6
LASER_SPEED = 11
SHOT_COOLDOWN_MS = 220
START_LIVES = 3
INVINCIBLE_MS = 1500  # grace period after getting hit
SWIPE_SPEED = 1.3  # how far the rocket moves compared with your finger
DOUBLE_TAP_MS = 300  # two taps this close together (in time and place) fire a bomb
DOUBLE_TAP_PX = 60

# Level tuning: level 1 is slow and easy, each level adds speed and spawns.
ALIEN_BASE_MIN_SPEED, ALIEN_BASE_MAX_SPEED = 1.6, 2.6
ALIEN_SPEED_PER_LEVEL = 0.35
ALIEN_SPEED_CAP = 7.0

# Aliens fly in, park somewhere in this band near the top, and shoot down at you.
HOVER_MIN_Y, HOVER_MAX_Y = 70, 300
MAX_ALIENS_BASE = 4  # most aliens parked on screen at once on level 1...
MAX_ALIENS_CAP = 12  # ...growing by one per level up to this
ALIEN_SHOT_MIN_MS, ALIEN_SHOT_MAX_MS = 1500, 3000  # gap between one alien's shots on level 1
ALIEN_SHOT_STEP_MS = 120  # the gap shrinks by this much each level...
ALIEN_SHOT_FLOOR_MS = 600  # ...but never below this
ALIEN_LASER_SPEED = 3.0  # alien laser speed on level 1
ALIEN_LASER_SPEED_STEP = 0.3
ALIEN_LASER_SPEED_CAP = 8.0
TOUGH_FROM_LEVEL = 10  # from this level some aliens take two shots
TOUGH_CHANCE = 0.4
SPAWN_BASE_MS = 1300  # time between alien spawns on level 1
SPAWN_STEP_MS = 100  # spawns get this much quicker each level
SPAWN_MIN_MS = 280
KILLS_BASE = 8  # kills needed to clear level 1
KILLS_PER_LEVEL = 4  # extra kills needed for each later level
LEVEL_BANNER_MS = 2000

BOSS_EVERY = 3  # a boss shows up on every 3rd level
BOSS_BASE_HP = 12  # hits the first boss takes
BOSS_HP_STEP = 6  # extra hits for each later boss
BOSS_HOVER_Y = 80
BOSS_BOMB_DAMAGE = 5  # a bomb hurts the boss instead of destroying it
COIN_VALUE = 10  # what each coin a boss drops is worth
COIN_SPREAD_X = 150  # coins land within this far left/right of the boss
COIN_GAP_Y = 100  # coins fall one after another, this far apart
BOSS_COINS_PER_LEVEL = 10  # a boss drops 30 coins on level 3, 60 on level 6...
START_COINS = 100  # coins a brand new save starts with
MINI_SPEED_BONUS = 0.5  # little ships from a boss fall a bit faster

ITEM_SPEED = 2.5
ITEM_MIN_GAP_MS, ITEM_MAX_GAP_MS = 12000, 20000
ITEM_TYPES = ("double", "big", "bomb")
BOMB_FLASH_MS = 350

# Shop upgrades: key -> (name, description, max level, base cost).
# The price of the next level is base cost x (current level + 1).
SHOP = {
    "speed": ("Speed Boost", "Your rocket flies faster", 3, 100),
    "fire": ("Rapid Laser", "Shoot lasers faster", 3, 150),
    "bomb": ("Bomb Pack", "Start every game with +1 bomb", 3, 120),
}
SPEED_PER_UPGRADE = 1.5
COOLDOWN_PER_UPGRADE_MS = 45

SAVE_PATH = Path(__file__).with_name("alien_boom_boom_save.json")
MAX_RANKINGS = 10
RANKING_POOL = 100  # rows pulled from the database before keeping one per name
# Shared online ranking (Firebase Realtime Database). Paste the database address here, e.g.
# "https://alien-boom-boom-default-rtdb.firebaseio.com". Leave it empty to keep rankings
# on each device only.
LEADERBOARD_URL = "https://alien-boom-boom-default-rtdb.firebaseio.com"
LEADERBOARD_TIMEOUT_S = 5
MAX_NAME_LEN = 16
GAME_OVER_PAUSE_MS = 1500  # how long GAME OVER shows before the name screen
FUN_NAMES = [
    "Captain Kaboom", "Laser Llama", "Sir Booms-a-Lot", "Cosmic Pickle",
    "Zappy McZapface", "Space Taco", "Major Meteor", "Boom Boom Bandit",
    "Galaxy Goose", "Pew Pew Panda", "Nacho Astronaut", "Turbo Noodle",
    "Star Sneeze", "Disco Comet", "Wobble Rocket", "Admiral Giggles",
    "Moon Muffin", "Blasty Banana", "Sergeant Sparkle", "Astro Waffle",
]

BLACK = (8, 8, 20)
WHITE = (240, 240, 240)
GREEN = (80, 230, 110)
RED = (240, 70, 70)
YELLOW = (250, 220, 70)
CYAN = (90, 220, 250)
ORANGE = (250, 150, 50)
PURPLE = (190, 110, 250)
GRAY = (110, 110, 130)
NAVY = (30, 34, 70)

ITEM_STYLE = {
    "double": ("x2", CYAN),
    "big": ("BIG", ORANGE),
    "bomb": ("BOMB", PURPLE),
}


def make_rocket():
    surf = pygame.Surface((44, 56), pygame.SRCALPHA)
    pygame.draw.polygon(surf, WHITE, [(22, 0), (34, 22), (34, 44), (10, 44), (10, 22)])
    pygame.draw.polygon(surf, RED, [(10, 28), (0, 48), (10, 44)])
    pygame.draw.polygon(surf, RED, [(34, 28), (44, 48), (34, 44)])
    pygame.draw.circle(surf, CYAN, (22, 22), 6)
    pygame.draw.polygon(surf, ORANGE, [(14, 44), (22, 56), (30, 44)])
    return surf


def make_alien(body=GREEN):
    surf = pygame.Surface((48, 32), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, body, (0, 10, 48, 20))
    pygame.draw.ellipse(surf, CYAN, (14, 0, 20, 20))
    for x in (10, 24, 38):
        pygame.draw.circle(surf, YELLOW, (x, 21), 3)
    return surf


def make_boss():
    surf = pygame.Surface((160, 100), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, PURPLE, (0, 32, 160, 60))
    pygame.draw.ellipse(surf, RED, (44, 0, 72, 64))
    pygame.draw.ellipse(surf, BLACK, (62, 18, 14, 20))
    pygame.draw.ellipse(surf, BLACK, (84, 18, 14, 20))
    for x in (24, 52, 80, 108, 136):
        pygame.draw.circle(surf, YELLOW, (x, 66), 6)
    return surf


def make_coin():
    surf = pygame.Surface((26, 26), pygame.SRCALPHA)
    pygame.draw.circle(surf, YELLOW, (13, 13), 13)
    pygame.draw.circle(surf, ORANGE, (13, 13), 13, 3)
    text = pygame.font.Font(None, 22).render("$", True, BLACK)
    surf.blit(text, text.get_rect(center=(13, 13)))
    return surf


def make_item(kind):
    label, color = ITEM_STYLE[kind]
    surf = pygame.Surface((52, 30), pygame.SRCALPHA)
    pygame.draw.rect(surf, color, surf.get_rect(), border_radius=8)
    pygame.draw.rect(surf, WHITE, surf.get_rect(), 2, border_radius=8)
    text = pygame.font.Font(None, 22).render(label, True, BLACK)
    surf.blit(text, text.get_rect(center=surf.get_rect().center))
    return surf


def read_save_text():
    if IS_WEB:
        # a browser has no save file, so progress lives in the browser's own storage
        from platform import window
        return window.localStorage.getItem(SAVE_PATH.stem) or ""
    return SAVE_PATH.read_text()


def load_save():
    save = {"coins": START_COINS, "upgrades": {}, "rankings": [], "last_name": ""}
    try:
        data = json.loads(read_save_text())
        if isinstance(data, dict):
            save.update({k: data[k] for k in save if isinstance(data.get(k), type(save[k]))})
    except (OSError, ValueError):
        pass  # no save yet, or an unreadable one: start fresh
    return save


def write_save(save):
    try:
        if IS_WEB:
            from platform import window
            window.localStorage.setItem(SAVE_PATH.stem, json.dumps(save))
        else:
            SAVE_PATH.write_text(json.dumps(save, indent=2))
    except OSError as err:
        print(f"Could not save progress: {err}")


def http(method, url, body=None):
    """Send one web request and return the reply text, or None if it failed."""
    if IS_WEB:
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
    """One entry per player, their best, so nobody can fill the whole ranking.

    Names are matched ignoring case and spacing.
    """
    best = {}
    for entry in rankings:
        key = " ".join(str(entry["name"]).split()).lower()
        rank = (entry["score"], entry["level"])
        if key not in best or rank > (best[key]["score"], best[key]["level"]):
            best[key] = entry
    return sorted(best.values(), key=lambda entry: (entry["score"], entry["level"]), reverse=True)


def fetch_online_rankings():
    """Top scores from the shared ranking, best first, or None if it can't be reached."""
    query = f"/scores.json?orderBy=%22score%22&limitToLast={RANKING_POOL}"
    try:
        rows = json.loads(http("GET", LEADERBOARD_URL + query) or "")
    except ValueError:
        return None
    if rows is None:
        return []  # reachable, but nobody has a score yet
    if not isinstance(rows, dict):
        return None
    rankings = []
    for row in rows.values():
        if isinstance(row, dict) and isinstance(row.get("score"), int) and isinstance(row.get("level"), int):
            rankings.append({"name": str(row.get("name", "?"))[:MAX_NAME_LEN], "score": row["score"], "level": row["level"]})
    return best_per_name(rankings)[:MAX_RANKINGS]


class Game:
    def __init__(self, upgrades=None):
        self.upgrades = upgrades if upgrades is not None else {}
        self.rocket_img = make_rocket()
        self.alien_img = make_alien()
        self.tough_img = make_alien(ORANGE)  # takes two shots
        self.mini_img = pygame.transform.smoothscale(self.alien_img, (32, 21))
        self.boss_img = make_boss()
        self.item_imgs = {kind: make_item(kind) for kind in ITEM_TYPES}
        self.item_imgs["coin"] = make_coin()
        self.stars = [
            [random.randrange(WIDTH), random.randrange(HEIGHT), random.choice((1, 2, 3))]
            for _ in range(70)
        ]
        self.reset()

    def reset(self):
        self.player = self.rocket_img.get_rect(midbottom=(WIDTH // 2, HEIGHT - 20))
        self.lasers = []
        self.aliens = []  # see new_alien() for what each alien holds
        self.alien_lasers = []  # each: {"rect": Rect, "y": float, "speed": float}
        self.boss = None  # {"rect": Rect, "hp": int, "max_hp": int, "dx": float}
        self.items = []  # each item: {"rect": Rect, "kind": str}
        self.booms = []  # each boom: [x, y, age]
        self.lives = START_LIVES
        self.score = 0
        self.coins = 0  # coins picked up this game
        self.level = 1
        self.level_kills = 0
        self.double_laser = False
        self.big_laser = False
        self.bombs = self.upgrades.get("bomb", 0)
        self.speed = round(PLAYER_SPEED + SPEED_PER_UPGRADE * self.upgrades.get("speed", 0))
        self.cooldown = SHOT_COOLDOWN_MS - COOLDOWN_PER_UPGRADE_MS * self.upgrades.get("fire", 0)
        self.over_time = None  # when the game ended
        self.last_shot = 0
        self.last_spawn = 0
        self.next_item = None  # set on the first update
        self.banner_start = None  # set on the first update
        self.flash_start = -BOMB_FLASH_MS
        self.hit_time = -INVINCIBLE_MS
        self.game_over = False
        self.touching = False  # a finger (or the mouse button) is held down

    def kills_needed(self):
        return KILLS_BASE + KILLS_PER_LEVEL * (self.level - 1)

    def shoot(self, now):
        if now - self.last_shot < self.cooldown:
            return
        width, height = (12, 30) if self.big_laser else (4, 16)
        offsets = (-14, 14) if self.double_laser else (0,)
        for dx in offsets:
            laser = pygame.Rect(0, 0, width, height)
            laser.midbottom = (self.player.centerx + dx, self.player.top + 4)
            self.lasers.append(laser)
        self.last_shot = now

    def use_bomb(self, now):
        """Blow up every alien on screen."""
        if self.game_over or self.bombs <= 0:
            return
        self.bombs -= 1
        self.flash_start = now
        for alien in self.aliens:
            self.kill_alien(alien, now)
        self.aliens = []
        self.alien_lasers = []
        if self.boss:
            self.hurt_boss(BOSS_BOMB_DAMAGE, now)

    def kill_alien(self, alien, now):
        rect = alien["rect"]
        self.booms.append([rect.centerx, rect.centery, 0])
        self.score += 10
        self.level_kills += 1
        # a boss level only ends when the boss is destroyed
        if not self.is_boss_level() and self.level_kills >= self.kills_needed():
            self.next_level(now)

    def is_boss_level(self):
        return self.level % BOSS_EVERY == 0

    def next_level(self, now):
        self.level += 1
        self.level_kills = 0
        self.banner_start = now
        if self.is_boss_level():
            self.spawn_boss()

    def spawn_boss(self):
        number = self.level // BOSS_EVERY
        rect = self.boss_img.get_rect(midbottom=(WIDTH // 2, 0))
        hp = BOSS_BASE_HP + BOSS_HP_STEP * (number - 1)
        self.boss = {"rect": rect, "hp": hp, "max_hp": hp, "dx": 1.5 + 0.5 * number}

    def hurt_boss(self, damage, now):
        self.boss["hp"] -= damage
        if self.boss["hp"] > 0:
            return
        # the boss breaks apart into one little ship per level (3 on level 3, 6 on level 6...)
        center = self.boss["rect"].center
        count = self.level
        gap = min(56, (WIDTH - 40) // count)
        speed = min(self.alien_speed() + MINI_SPEED_BONUS, ALIEN_SPEED_CAP)
        for i in range(count):
            rect = self.mini_img.get_rect()
            rect.centerx = center[0] + int((i - (count - 1) / 2) * gap)
            rect.centery = center[1] + (i % 2) * 24
            rect.clamp_ip(pygame.Rect(0, 0, WIDTH, HEIGHT))
            self.aliens.append(self.new_alien(rect, speed, self.mini_img))
        # ...and drops coins to catch: 30 coins' worth on level 3, 60 on level 6...
        coins = self.level * BOSS_COINS_PER_LEVEL // COIN_VALUE
        # They come down one at a time at random spots so each can be caught.
        for i in range(coins):
            rect = self.item_imgs["coin"].get_rect()
            rect.centerx = center[0] + random.randint(-COIN_SPREAD_X, COIN_SPREAD_X)
            rect.clamp_ip(pygame.Rect(0, 0, WIDTH, HEIGHT))
            rect.centery = center[1] - i * COIN_GAP_Y + random.randint(-20, 20)
            self.items.append({"rect": rect, "kind": "coin"})
        for dx in (-50, 0, 50):
            self.booms.append([center[0] + dx, center[1], 0])
        self.boss = None
        self.score += 100
        self.next_level(now)

    def alien_speed(self):
        bonus = ALIEN_SPEED_PER_LEVEL * (self.level - 1)
        speed = random.uniform(ALIEN_BASE_MIN_SPEED, ALIEN_BASE_MAX_SPEED) + bonus
        return min(speed, ALIEN_SPEED_CAP)

    def new_alien(self, rect, speed, img, hover_y=None, hp=1):
        """hover_y is where the alien parks to shoot; None means it dives straight down."""
        return {
            "rect": rect, "x": float(rect.x), "y": float(rect.y), "speed": speed, "img": img,
            "hp": hp, "hover_y": hover_y, "dx": random.choice((-1, 1)) * speed * 0.9,
            "next_shot": None,
        }

    def spawn_alien(self):
        tough = self.level >= TOUGH_FROM_LEVEL and random.random() < TOUGH_CHANCE
        img = self.tough_img if tough else self.alien_img
        rect = img.get_rect()
        rect.x = random.randint(0, WIDTH - rect.width)
        rect.bottom = 0
        hover_y = random.randint(HOVER_MIN_Y, HOVER_MAX_Y)
        self.aliens.append(self.new_alien(rect, self.alien_speed(), img, hover_y, 2 if tough else 1))

    def max_aliens(self):
        return min(MAX_ALIENS_BASE + self.level - 1, MAX_ALIENS_CAP)

    def alien_shot_gap(self):
        cut = ALIEN_SHOT_STEP_MS * (self.level - 1)
        low = max(ALIEN_SHOT_FLOOR_MS, ALIEN_SHOT_MIN_MS - cut)
        high = max(ALIEN_SHOT_FLOOR_MS * 2, ALIEN_SHOT_MAX_MS - cut)
        return random.randint(low, high)

    def alien_shoot(self, alien):
        rect = pygame.Rect(0, 0, 8, 26)
        rect.midtop = alien["rect"].midbottom
        speed = min(ALIEN_LASER_SPEED + ALIEN_LASER_SPEED_STEP * (self.level - 1), ALIEN_LASER_SPEED_CAP)
        self.alien_lasers.append({"rect": rect, "y": float(rect.y), "speed": speed})

    def spawn_item(self):
        kind = random.choice(ITEM_TYPES)
        rect = self.item_imgs[kind].get_rect()
        rect.x = random.randint(0, WIDTH - rect.width)
        rect.bottom = 0
        self.items.append({"rect": rect, "kind": kind})

    def collect(self, kind):
        if kind == "double":
            self.double_laser = True
        elif kind == "big":
            self.big_laser = True
        elif kind == "bomb":
            self.bombs += 1
        elif kind == "coin":
            self.coins += COIN_VALUE
        self.score += 5

    def lose_life(self, now):
        self.lives -= 1
        self.hit_time = now
        # getting hit knocks out your laser upgrades (bombs are kept)
        self.double_laser = False
        self.big_laser = False
        self.booms.append([self.player.centerx, self.player.centery, 0])
        if self.lives <= 0:
            self.game_over = True
            self.over_time = now

    def scroll_stars(self):
        for star in self.stars:
            star[1] += star[2]
            if star[1] > HEIGHT:
                star[0], star[1] = random.randrange(WIDTH), 0

    def draw_stars(self, screen):
        screen.fill(BLACK)
        for x, y, size in self.stars:
            pygame.draw.circle(screen, WHITE, (x, y), size // 2 + 1)

    def update(self, now):
        self.scroll_stars()

        for boom in self.booms:
            boom[2] += 1
        self.booms = [b for b in self.booms if b[2] < 18]

        if self.game_over:
            return

        if self.banner_start is None:
            self.banner_start = now
        if self.next_item is None:
            self.next_item = now + random.randint(ITEM_MIN_GAP_MS, ITEM_MAX_GAP_MS)

        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            self.player.x -= self.speed
        if keys[pygame.K_RIGHT]:
            self.player.x += self.speed
        if keys[pygame.K_UP]:
            self.player.y -= self.speed
        if keys[pygame.K_DOWN]:
            self.player.y += self.speed
        self.player.clamp_ip(pygame.Rect(0, 0, WIDTH, HEIGHT))
        if keys[pygame.K_SPACE] or self.touching:
            self.shoot(now)

        spawn_gap = max(SPAWN_MIN_MS, SPAWN_BASE_MS - SPAWN_STEP_MS * (self.level - 1))
        parked = sum(1 for alien in self.aliens if alien["hover_y"] is not None)
        if now - self.last_spawn >= spawn_gap and parked < self.max_aliens():
            self.spawn_alien()
            self.last_spawn = now

        if now >= self.next_item:
            self.spawn_item()
            self.next_item = now + random.randint(ITEM_MIN_GAP_MS, ITEM_MAX_GAP_MS)

        for laser in self.lasers:
            laser.y -= LASER_SPEED
        self.lasers = [l for l in self.lasers if l.bottom > 0]

        falling = []
        for item in self.items:
            item["rect"].y += ITEM_SPEED
            if item["rect"].colliderect(self.player):
                self.collect(item["kind"])
            elif item["rect"].top <= HEIGHT:
                falling.append(item)
        self.items = falling

        invincible = now - self.hit_time < INVINCIBLE_MS

        if self.boss:
            rect = self.boss["rect"]
            if rect.top < BOSS_HOVER_Y:
                rect.y += 2  # flying in from the top
            else:
                rect.x += self.boss["dx"]
                if rect.left <= 0 or rect.right >= WIDTH:
                    self.boss["dx"] = -self.boss["dx"]
            if rect.colliderect(self.player.inflate(-12, -12)) and not invincible:
                self.lose_life(now)
                invincible = True
            hits = rect.collidelistall(self.lasers)
            if hits:
                damage = sum(2 if self.lasers[i].width > 4 else 1 for i in hits)
                self.lasers = [l for i, l in enumerate(self.lasers) if i not in hits]
                self.booms.append([rect.centerx, rect.bottom - 10, 8])
                self.hurt_boss(damage, now)

        hurtbox = self.player.inflate(-12, -12)
        survivors = []
        for alien in self.aliens:
            rect = alien["rect"]
            if alien["hover_y"] is None or alien["y"] < alien["hover_y"]:
                alien["y"] += alien["speed"]
                rect.y = int(alien["y"])
            else:
                # parked: drift side to side and shoot
                alien["x"] += alien["dx"]
                rect.x = int(alien["x"])
                if rect.left <= 0 or rect.right >= WIDTH:
                    alien["dx"] = -alien["dx"]
                    rect.clamp_ip(pygame.Rect(0, 0, WIDTH, HEIGHT))
                    alien["x"] = float(rect.x)
                if alien["next_shot"] is None:
                    alien["next_shot"] = now + self.alien_shot_gap() // 2
                elif now >= alien["next_shot"]:
                    self.alien_shoot(alien)
                    alien["next_shot"] = now + self.alien_shot_gap()

            hit = rect.collidelist(self.lasers)
            if hit != -1:
                alien["hp"] -= 2 if self.lasers[hit].width > 4 else 1
                del self.lasers[hit]
                if alien["hp"] <= 0:
                    self.kill_alien(alien, now)
                    continue
                self.booms.append([rect.centerx, rect.centery, 10])  # small spark: hurt, not dead

            if rect.colliderect(hurtbox) and not invincible:
                self.booms.append([rect.centerx, rect.centery, 0])
                self.lose_life(now)
                invincible = True
                continue

            # an alien that gets past you also costs a life
            if rect.top > HEIGHT:
                if not invincible:
                    self.lose_life(now)
                    invincible = True
                continue

            survivors.append(alien)
        self.aliens = survivors

        flying = []
        for laser in self.alien_lasers:
            laser["y"] += laser["speed"]
            laser["rect"].y = int(laser["y"])
            if laser["rect"].colliderect(hurtbox) and not invincible:
                self.lose_life(now)
                invincible = True
            elif laser["rect"].top <= HEIGHT:
                flying.append(laser)
        self.alien_lasers = flying

    def draw(self, screen, font, big_font, now):
        self.draw_stars(screen)

        for laser in self.lasers:
            pygame.draw.rect(screen, YELLOW if laser.width > 4 else CYAN, laser, border_radius=3)
        for laser in self.alien_lasers:
            pygame.draw.rect(screen, RED, laser["rect"], border_radius=4)
        for alien in self.aliens:
            screen.blit(alien["img"], alien["rect"])
        if self.boss:
            rect = self.boss["rect"]
            screen.blit(self.boss_img, rect)
            bar = pygame.Rect(rect.left, rect.top - 12, rect.width, 8)
            pygame.draw.rect(screen, WHITE, bar, 1)
            bar.width = int(rect.width * self.boss["hp"] / self.boss["max_hp"])
            pygame.draw.rect(screen, RED, bar)
        for item in self.items:
            screen.blit(self.item_imgs[item["kind"]], item["rect"])

        # blink the rocket while invincible
        blinking = now - self.hit_time < INVINCIBLE_MS and (now // 100) % 2 == 0
        if not self.game_over and not blinking:
            screen.blit(self.rocket_img, self.player)

        for x, y, age in self.booms:
            pygame.draw.circle(screen, YELLOW, (x, y), 6 + age * 2, 3)
            pygame.draw.circle(screen, ORANGE, (x, y), 3 + age, 2)

        flash_age = now - self.flash_start
        if flash_age < BOMB_FLASH_MS:
            flash = pygame.Surface((WIDTH, HEIGHT))
            flash.fill(WHITE)
            flash.set_alpha(int(220 * (1 - flash_age / BOMB_FLASH_MS)))
            screen.blit(flash, (0, 0))

        screen.blit(font.render(f"Score: {self.score}", True, WHITE), (12, 10))
        level_text = font.render(f"Level {self.level}", True, YELLOW)
        screen.blit(level_text, level_text.get_rect(midtop=(WIDTH // 2, 10)))
        lives_text = font.render(f"Lives: {self.lives}", True, WHITE)
        screen.blit(lives_text, (WIDTH - lives_text.get_width() - 12, 10))

        upgrades = [name for name, on in (("x2", self.double_laser), ("BIG", self.big_laser)) if on]
        status = f"Coins: {self.coins}   Bombs: {self.bombs} (B)"
        if upgrades:
            status += "   Laser: " + " + ".join(upgrades)
        screen.blit(font.render(status, True, CYAN), (12, 40))

        if self.game_over:
            over = big_font.render("GAME OVER", True, RED)
            screen.blit(over, over.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 30)))
        elif self.banner_start is not None and now - self.banner_start < LEVEL_BANNER_MS:
            banner = big_font.render(f"LEVEL {self.level}", True, YELLOW)
            screen.blit(banner, banner.get_rect(center=(WIDTH // 2, HEIGHT // 3)))
            if self.boss:
                warning = big_font.render("BOSS!", True, RED)
                screen.blit(warning, warning.get_rect(center=(WIDTH // 2, HEIGHT // 3 + 70)))


class App:
    """Menu, shop, name entry and rankings screens wrapped around the Game."""

    def __init__(self, screen):
        self.screen = screen
        self.font = pygame.font.Font(None, 32)
        self.small_font = pygame.font.Font(None, 24)
        self.big_font = pygame.font.Font(None, 84)
        # the built-in font has no Korean letters, so names typed in Korean need a system font
        korean = None
        if not IS_WEB:  # browsers have no system fonts to search
            korean = pygame.font.match_font("applesdgothicneo,applegothic,malgungothic,nanumgothic,notosanscjkkr")
        self.korean_font = pygame.font.Font(korean, 22) if korean else self.font
        self.save = load_save()
        self.game = Game(self.save["upgrades"])
        self.state = "menu"  # menu, shop, help, play, name, rankings
        self.buttons = []  # (rect, action) pairs drawn this frame
        self.name = ""
        self.name_fresh = False  # True while the name is an untouched suggestion
        self.earned = 0
        self.my_entry = None  # the ranking row from the game just played
        self.online_rankings = None  # shared ranking once it has been downloaded
        self.refresh_online()
        self.running = True
        self.touch_x = 0  # where the finger was last, to measure swipes
        self.last_tap = (-DOUBLE_TAP_MS, 0, 0)  # (time, x, y) of the last tap, to spot double taps

    # ----- actions -----

    def leave_game(self):
        self.bank_coins()  # quitting early still keeps your coins
        self.state = "menu"

    def type_name(self):
        """Phones have no keyboard for the game, so ask with the browser's own text box."""
        from platform import window
        name = window.prompt("Your pilot name:", self.name)
        if name:
            self.name = str(name).strip()[:MAX_NAME_LEN]
            self.name_fresh = False

    def start_game(self):
        self.game.reset()
        self.state = "play"

    def go(self, state):
        self.state = state
        if state == "menu":
            self.refresh_online()

    def refresh_online(self, new_entry=None):
        """Upload new_entry (if any) and download the shared ranking."""
        if not LEADERBOARD_URL:
            return

        def work():
            if new_entry:
                http("POST", LEADERBOARD_URL + "/scores.json", json.dumps(new_entry))
            rankings = fetch_online_rankings()
            if rankings is not None:
                self.online_rankings = rankings
            print("online ranking:", "unavailable" if rankings is None else f"{len(rankings)} scores")

        if IS_WEB:
            work()  # browsers have no threads here; the request is quick
        else:
            threading.Thread(target=work, daemon=True).start()  # don't freeze the game while waiting

    def rankings(self):
        """The shared ranking when it is available, otherwise this device's own."""
        return self.save["rankings"] if self.online_rankings is None else self.online_rankings

    def quit(self):
        self.running = False

    def buy(self, key):
        _, _, max_level, base = SHOP[key]
        level = self.save["upgrades"].get(key, 0)
        cost = base * (level + 1)
        if level < max_level and self.save["coins"] >= cost:
            self.save["coins"] -= cost
            self.save["upgrades"][key] = level + 1
            write_save(self.save)

    def bank_coins(self):
        """Move the coins picked up this game into the saved total."""
        self.earned = self.game.coins
        self.save["coins"] += self.earned
        self.game.coins = 0
        write_save(self.save)

    def suggest_name(self):
        self.name = random.choice([n for n in FUN_NAMES if n != self.name])
        self.name_fresh = True

    def finish_game(self):
        """Game over: bank the coins and ask for a name."""
        self.bank_coins()
        if self.save["last_name"]:
            self.name, self.name_fresh = self.save["last_name"], True
        else:
            self.suggest_name()
        self.state = "name"

    def save_ranking(self):
        name = self.name.strip() or random.choice(FUN_NAMES)
        self.my_entry = {"name": name, "score": self.game.score, "level": self.game.level}
        self.save["rankings"] = best_per_name(self.save["rankings"] + [self.my_entry])[:MAX_RANKINGS]
        self.save["last_name"] = name
        write_save(self.save)
        self.refresh_online(self.my_entry)
        self.state = "rankings"

    # ----- input -----

    def handle_event(self, event, now):
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, action in self.buttons:
                if rect.collidepoint(event.pos):
                    action()
                    break
            else:
                if self.state == "play":
                    # a tap shoots (hold to keep shooting); swiping moves the rocket
                    self.game.touching = True
                    self.touch_x = event.pos[0]
                    near = abs(event.pos[0] - self.last_tap[1]) < DOUBLE_TAP_PX and \
                        abs(event.pos[1] - self.last_tap[2]) < DOUBLE_TAP_PX
                    if now - self.last_tap[0] <= DOUBLE_TAP_MS and near:
                        self.game.use_bomb(now)
                        self.last_tap = (-DOUBLE_TAP_MS, 0, 0)  # a third tap starts over
                    else:
                        self.last_tap = (now, *event.pos)
        elif event.type == pygame.MOUSEMOTION:
            if self.state == "play" and self.game.touching and not self.game.game_over:
                self.game.player.x += round((event.pos[0] - self.touch_x) * SWIPE_SPEED)
                self.game.player.clamp_ip(pygame.Rect(0, 0, WIDTH, HEIGHT))
                self.touch_x = event.pos[0]
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.game.touching = False
        elif event.type == pygame.KEYDOWN:
            self.handle_key(event, now)

    def handle_key(self, event, now):
        key = event.key
        if self.state == "menu":
            if key in (pygame.K_RETURN, pygame.K_SPACE):
                self.start_game()
            elif key == pygame.K_s:
                self.state = "shop"
            elif key == pygame.K_h:
                self.state = "help"
            elif key == pygame.K_ESCAPE and not IS_WEB:  # a web page can't be quit
                self.running = False
        elif self.state in ("shop", "help"):
            if key == pygame.K_ESCAPE:
                self.state = "menu"
        elif self.state == "play":
            if key == pygame.K_ESCAPE:
                self.leave_game()
            elif key == pygame.K_b:
                self.game.use_bomb(now)
        elif self.state == "name":
            if key == pygame.K_RETURN:
                self.save_ranking()
            elif key == pygame.K_TAB:
                self.suggest_name()
            elif key == pygame.K_BACKSPACE:
                # the first edit wipes a suggested name so you can just start typing
                self.name = "" if self.name_fresh else self.name[:-1]
                self.name_fresh = False
            elif event.unicode and event.unicode.isprintable():
                if self.name_fresh:
                    self.name = ""
                    self.name_fresh = False
                self.name = (self.name + event.unicode)[:MAX_NAME_LEN]
        elif self.state == "rankings":
            if key in (pygame.K_RETURN, pygame.K_SPACE):
                self.start_game()
            elif key == pygame.K_ESCAPE:
                self.state = "menu"

    # ----- drawing helpers -----

    def name_font(self, name):
        return self.font if name.isascii() else self.korean_font

    def text(self, label, center, font=None, color=WHITE):
        surf = (font or self.font).render(label, True, color)
        self.screen.blit(surf, surf.get_rect(center=center))

    def button(self, label, rect, action, color=GREEN, enabled=True):
        hover = enabled and rect.collidepoint(pygame.mouse.get_pos())
        fill = GRAY if not enabled else WHITE if hover else color
        pygame.draw.rect(self.screen, fill, rect, border_radius=12)
        pygame.draw.rect(self.screen, WHITE, rect, 2, border_radius=12)
        self.text(label, rect.center, color=BLACK)
        if enabled:
            self.buttons.append((rect, action))

    def draw_rankings(self, top, limit):
        rankings = self.rankings()[:limit]
        if not rankings:
            self.text("No scores yet - be the first!", (WIDTH // 2, top + 20), self.small_font, GRAY)
        for i, entry in enumerate(rankings):
            y = top + i * 34
            mine = entry == self.my_entry
            color = YELLOW if mine else WHITE
            if mine:
                pygame.draw.rect(self.screen, NAVY, (70, y - 4, WIDTH - 140, 32), border_radius=6)
            place = self.font.render(f"{i + 1}.", True, color)
            self.screen.blit(place, (90, y))
            name = self.name_font(entry["name"]).render(entry["name"], True, color)
            self.screen.blit(name, name.get_rect(midleft=(121, y + place.get_height() // 2)))
            score = self.font.render(f"{entry['score']}   Lv {entry['level']}", True, color)
            self.screen.blit(score, (WIDTH - 90 - score.get_width(), y))

    # ----- screens -----

    def draw_menu(self):
        self.text("ALIEN", (WIDTH // 2, 100), self.big_font, GREEN)
        self.text("BOOM BOOM", (WIDTH // 2, 165), self.big_font, YELLOW)
        self.screen.blit(self.game.rocket_img, self.game.rocket_img.get_rect(center=(WIDTH // 2, 240)))
        self.button("PLAY NOW", pygame.Rect(180, 285, 240, 52), self.start_game)
        self.button("SHOP", pygame.Rect(180, 347, 240, 52), lambda: self.go("shop"), CYAN)
        self.button("HOW TO PLAY", pygame.Rect(180, 409, 240, 52), lambda: self.go("help"), ORANGE)
        self.text(f"Coins: {self.save['coins']}", (WIDTH // 2, 490), color=YELLOW)
        self.text("TOP PILOTS", (WIDTH // 2, 535), color=CYAN)
        self.draw_rankings(560, 5)
        self.text("Arrows or swipe to move   Space or tap to shoot", (WIDTH // 2, HEIGHT - 30), self.small_font, GRAY)

    def draw_help(self):
        game = self.game
        self.text("HOW TO PLAY", (WIDTH // 2, 60), self.big_font, ORANGE)
        y = 120
        for heading, rows in (
            ("CONTROLS", [
                ("Arrows", "Move your rocket"),
                ("Space", "Shoot lasers (hold it down to keep firing)"),
                ("B", "Fire a bomb - blows up every alien on screen"),
                ("Esc", "Go back to the menu"),
                ("Touch", "Hold to shoot, swipe to move, double tap for a bomb"),
            ]),
            ("ALIENS", [
                (game.alien_img, "Parks at the top and shoots red lasers. Dodge!"),
                (game.tough_img, "From level 10: takes two shots"),
                (game.boss_img, "Boss every 3rd level. Drops coins when it dies"),
                (game.mini_img, "Little ships dive at you. Don't let them past!"),
            ]),
            ("PICK UP", [
                (game.item_imgs["double"], "Two lasers at a time"),
                (game.item_imgs["big"], "Bigger laser, hits twice as hard"),
                (game.item_imgs["bomb"], "One more bomb"),
                (game.item_imgs["coin"], "Coins to spend in the SHOP"),
            ]),
        ):
            self.screen.blit(self.font.render(heading, True, CYAN), (40, y))
            y += 34
            for icon, label in rows:
                if isinstance(icon, str):
                    key = self.small_font.render(icon, True, YELLOW)
                    self.screen.blit(key, key.get_rect(center=(85, y + 10)))
                else:
                    scale = min(1, 56 / icon.get_width(), 26 / icon.get_height())
                    size = (int(icon.get_width() * scale), int(icon.get_height() * scale))
                    small = pygame.transform.smoothscale(icon, size)
                    self.screen.blit(small, small.get_rect(center=(85, y + 10)))
                self.screen.blit(self.small_font.render(label, True, WHITE), (135, y + 2))
                y += 32
            y += 12
        self.text("You have 3 lives. Getting hit also removes x2 and BIG.", (WIDTH // 2, y + 8), self.small_font, YELLOW)
        self.button("BACK", pygame.Rect(200, HEIGHT - 80, 200, 54), lambda: self.go("menu"))

    def draw_shop(self):
        self.text("SHOP", (WIDTH // 2, 70), self.big_font, CYAN)
        self.text(f"Coins: {self.save['coins']}", (WIDTH // 2, 130), color=YELLOW)
        self.text("Bosses drop coins - catch them to spend here", (WIDTH // 2, 160), self.small_font, GRAY)
        for i, (key, (name, desc, max_level, base)) in enumerate(SHOP.items()):
            top = 195 + i * 120
            pygame.draw.rect(self.screen, NAVY, (30, top, WIDTH - 60, 104), border_radius=12)
            level = self.save["upgrades"].get(key, 0)
            self.screen.blit(self.font.render(name, True, WHITE), (50, top + 14))
            self.screen.blit(self.small_font.render(desc, True, GRAY), (50, top + 44))
            for n in range(max_level):
                pygame.draw.circle(self.screen, YELLOW if n < level else GRAY, (60 + n * 26, top + 82), 9)
            rect = pygame.Rect(WIDTH - 200, top + 26, 150, 52)
            if level >= max_level:
                self.button("MAX", rect, None, enabled=False)
            else:
                cost = base * (level + 1)
                can_buy = self.save["coins"] >= cost
                self.button(f"Buy {cost}", rect, lambda key=key: self.buy(key), YELLOW, can_buy)
        self.button("BACK", pygame.Rect(200, HEIGHT - 90, 200, 54), lambda: self.go("menu"))

    def draw_name(self, now):
        self.text("GAME OVER", (WIDTH // 2, 120), self.big_font, RED)
        self.text(f"Score: {self.game.score}     Level: {self.game.level}", (WIDTH // 2, 200))
        self.text(f"+{self.earned} coins", (WIDTH // 2, 240), color=YELLOW)
        self.text("Your pilot name:", (WIDTH // 2, 320))
        box = pygame.Rect(110, 345, 380, 56)
        pygame.draw.rect(self.screen, NAVY, box, border_radius=10)
        pygame.draw.rect(self.screen, CYAN, box, 2, border_radius=10)
        cursor = "|" if (now // 400) % 2 == 0 else " "
        self.text(self.name + cursor, box.center, self.name_font(self.name), YELLOW if self.name_fresh else WHITE)
        self.text("Type to change it", (WIDTH // 2, 425), self.small_font, GRAY)
        self.button("ANOTHER NAME", pygame.Rect(165, 465, 270, 54), self.suggest_name, CYAN)
        self.button("SAVE", pygame.Rect(165, 535, 270, 54), self.save_ranking)
        if IS_WEB:
            self.button("TYPE MY OWN", pygame.Rect(165, 605, 270, 54), self.type_name, ORANGE)

    def draw_rankings_screen(self):
        self.text("RANKINGS", (WIDTH // 2, 80), self.big_font, YELLOW)
        where = "Saved on this device" if self.online_rankings is None else "Shared with every player"
        self.text(where, (WIDTH // 2, 128), self.small_font, GRAY)
        self.draw_rankings(150, MAX_RANKINGS)
        self.button("PLAY AGAIN", pygame.Rect(70, HEIGHT - 190, 220, 60), self.start_game)
        self.button("SHOP", pygame.Rect(310, HEIGHT - 190, 220, 60), lambda: self.go("shop"), CYAN)
        self.button("MENU", pygame.Rect(190, HEIGHT - 110, 220, 54), lambda: self.go("menu"), ORANGE)

    def frame(self, now):
        self.buttons = []
        if self.state == "play":
            self.game.update(now)
            self.game.draw(self.screen, self.font, self.big_font, now)
            if self.game.game_over:
                if now - self.game.over_time >= GAME_OVER_PAUSE_MS:
                    self.finish_game()
                return
            # on-screen buttons so the game can be played without a keyboard
            self.button("MENU", pygame.Rect(10, HEIGHT - 56, 92, 46), self.leave_game, GRAY)
            self.button(f"BOMB {self.game.bombs}", pygame.Rect(WIDTH - 122, HEIGHT - 56, 112, 46),
                        lambda: self.game.use_bomb(now), PURPLE, self.game.bombs > 0)
            return
        self.game.scroll_stars()
        self.game.draw_stars(self.screen)
        if self.state == "menu":
            self.draw_menu()
        elif self.state == "shop":
            self.draw_shop()
        elif self.state == "help":
            self.draw_help()
        elif self.state == "name":
            self.draw_name(now)
        elif self.state == "rankings":
            self.draw_rankings_screen()


async def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Alien Boom Boom")
    clock = pygame.time.Clock()
    app = App(screen)

    while app.running:
        now = pygame.time.get_ticks()
        for event in pygame.event.get():
            app.handle_event(event, now)
        app.frame(now)
        pygame.display.flip()
        clock.tick(FPS)
        await asyncio.sleep(0)  # lets the browser draw the frame; harmless on desktop

    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())
