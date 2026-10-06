import os
import sys
import math
import random
import pygame
from pygame import mixer

ANDROID = hasattr(sys, "getandroidapilevel") or "ANDROID_ARGUMENT" in os.environ
TOUCH_UI = ANDROID or os.environ.get("TOUCH_UI") == "1"

def resource_path(rel_path: str) -> str:
    """
    Works for dev + PyInstaller onefile.
    """
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel_path)

def asset_path(filename: str) -> str:
    return resource_path(os.path.join("assets", filename))

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

pygame.init()
mixer.init()

WIDTH, HEIGHT = 800, 600
if ANDROID:
    pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
else:
    pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("Space Invader")
# Virtual 800x600 canvas; present() scales it to whatever the real screen is.
screen = pygame.Surface((WIDTH, HEIGHT)).convert()

clock = pygame.time.Clock()
FPS = 60

# -------------------- Assets --------------------

# Images
ICON = pygame.image.load(asset_path("ufo.png")).convert_alpha()
pygame.display.set_icon(ICON)

BG_GAME = pygame.image.load(asset_path("back.jpg")).convert()
# Optional menu background (you listed background.png)
BG_MENU = pygame.image.load(asset_path("background.png")).convert()

PLAYER_IMG = pygame.image.load(asset_path("player.png")).convert_alpha()
ENEMY_IMG = pygame.image.load(asset_path("enemy.png")).convert_alpha()
BULLET_IMG = pygame.image.load(asset_path("bullet.png")).convert_alpha()

# Image tint helper (returns a new surface tinted by color)
def tint_image(img, color):
    surf = img.copy().convert_alpha()
    # create an overlay the same size and fill with color, then multiply
    overlay = pygame.Surface(img.get_size(), flags=pygame.SRCALPHA)
    overlay.fill((*color, 0))
    surf.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    return surf

# Simple ship sprite builder to create distinct variants from one base
def make_ship_sprite(base_img, main_color, accent_color):
    surf = tint_image(base_img, main_color)
    # add a bright cockpit stripe + side fins
    w, h = surf.get_size()
    pygame.draw.rect(surf, accent_color, (w//2 - 3, 6, 6, h - 10))
    pygame.draw.polygon(surf, accent_color, [(2, h-6), (10, h-2), (2, h-2)])
    pygame.draw.polygon(surf, accent_color, [(w-2, h-6), (w-10, h-2), (w-2, h-2)])
    return surf

# Power-up sprite builder
def make_powerup_sprite(bg_color, fg_color):
    surf = pygame.Surface((32, 32), pygame.SRCALPHA)
    pygame.draw.circle(surf, bg_color, (16, 16), 14)
    pygame.draw.circle(surf, (255, 255, 255), (16, 16), 14, 2)
    pygame.draw.rect(surf, fg_color, (10, 10, 12, 12), border_radius=3)
    return surf

# Enemy type presets (small scout, gunner, heavy)
ENEMY_TYPES = {
    "scout": {"hp": 1, "speed_mul": 1.2, "shoots": False, "color": (180, 220, 255), "score": 1},
    "gunner": {"hp": 2, "speed_mul": 0.9, "shoots": True,  "color": (255, 200, 150), "score": 2},
    "heavy": {"hp": 4, "speed_mul": 0.6, "shoots": False, "color": (255, 120, 120), "score": 4},
}

# Boss preset
BOSS_CONFIG = {"hp_base": 10, "speed": 2.2, "shoot_cooldown": 38, "score": 12}

# Sounds
SND_LASER = mixer.Sound(asset_path("laser.wav"))
SND_EXPLODE = mixer.Sound(asset_path("explosion.wav"))

MUSIC_GAME = asset_path("background.ogg")
MUSIC_MENU = asset_path("soso.ogg")

# Fonts (no external font file)
font_score = pygame.font.Font(None, 32)
font_menu = pygame.font.Font(None, 40)
font_title = pygame.font.Font(None, 70)
font_over = pygame.font.Font(None, 72)

# -------------------- Ships / Powerups --------------------

SHIPS = {
    "Falcon": {
        "speed": 6.0,
        "bullet_speed": 11,
        "base_cooldown": 14,
        "img": make_ship_sprite(PLAYER_IMG, (120, 200, 255), (255, 255, 255)),
        "glow": (120, 200, 255),
        "weapon": "normal",
    },
    "Wasp": {
        "speed": 7.2,
        "bullet_speed": 10,
        "base_cooldown": 12,
        "img": make_ship_sprite(PLAYER_IMG, (255, 220, 90), (255, 120, 60)),
        "glow": (255, 220, 90),
        "weapon": "rapid",
    },
    "Titan": {
        "speed": 5.2,
        "bullet_speed": 12,
        "base_cooldown": 16,
        "img": make_ship_sprite(PLAYER_IMG, (200, 120, 255), (120, 255, 200)),
        "glow": (200, 120, 255),
        "weapon": "burst",
    },
    "Raven": {
        "speed": 6.4,
        "bullet_speed": 15,
        "base_cooldown": 18,
        "img": make_ship_sprite(PLAYER_IMG, (180, 180, 180), (255, 80, 80)),
        "glow": (200, 200, 200),
        "weapon": "laser",
    },
    "Piranha": {
        "speed": 6.0,
        "bullet_speed": 11,
        "base_cooldown": 15,
        "img": make_ship_sprite(PLAYER_IMG, (120, 255, 200), (60, 120, 255)),
        "glow": (120, 255, 200),
        "weapon": "spread",
    },
    "Comet": {
        "speed": 7.0,
        "bullet_speed": 12,
        "base_cooldown": 13,
        "img": make_ship_sprite(PLAYER_IMG, (255, 160, 90), (255, 255, 255)),
        "glow": (255, 160, 90),
        "weapon": "triple",
    },
    "Viper": {
        "speed": 7.6,
        "bullet_speed": 10,
        "base_cooldown": 11,
        "img": make_ship_sprite(PLAYER_IMG, (120, 255, 140), (255, 255, 80)),
        "glow": (120, 255, 140),
        "weapon": "rapid",
    },
}

POWERUP_SPRITES = {
    "TRI": make_powerup_sprite((40, 240, 120), (0, 80, 0)),
    "RAP": make_powerup_sprite((255, 120, 255), (70, 0, 70)),
    "SHD": make_powerup_sprite((80, 200, 255), (0, 50, 120)),
    "BONUS": make_powerup_sprite((255, 215, 0), (120, 80, 0)),
    "SPRD": make_powerup_sprite((120, 255, 200), (0, 80, 60)),
    "LASR": make_powerup_sprite((255, 80, 80), (80, 0, 0)),
    "BURST": make_powerup_sprite((180, 120, 255), (60, 0, 120)),
}

# -------------------- Game State --------------------

# Level configs
LEVELS = {
    "Easy":   {"enemy_speed": 0.55, "enemy_drop": 38, "num_enemies": 6},
    "Medium": {"enemy_speed": 0.75, "enemy_drop": 46, "num_enemies": 7},
    "Hard":   {"enemy_speed": 1.05, "enemy_drop": 54, "num_enemies": 9},
    "Insane": {"enemy_speed": 1.35, "enemy_drop": 62, "num_enemies": 11},
}

# Per-level tuning for boss + ship feel
LEVEL_TUNING = {
    "Easy":   {"speed_bonus": 1.0, "boss_spawn": 16, "boss_cd": 55, "boss_speed_mul": 0.8,
               "spread": (-1.6, 0, 1.6), "burst": 4, "wave": (-1.6, 1.6), "dy": 2.6},
    "Medium": {"speed_bonus": 0.6, "boss_spawn": 14, "boss_cd": 46, "boss_speed_mul": 0.9,
               "spread": (-1.9, -0.6, 0, 0.6, 1.9), "burst": 5, "wave": (-1.8, 0, 1.8), "dy": 3.0},
    "Hard":   {"speed_bonus": 0.2, "boss_spawn": 12, "boss_cd": 40, "boss_speed_mul": 1.0,
               "spread": (-2.2, -1.1, 0, 1.1, 2.2), "burst": 6, "wave": (-2.0, 0, 2.0), "dy": 3.4},
    "Insane": {"speed_bonus": 0.0, "boss_spawn": 10, "boss_cd": 34, "boss_speed_mul": 1.1,
               "spread": (-2.5, -1.6, -0.8, 0, 0.8, 1.6, 2.5), "burst": 7, "wave": (-2.4, 0, 2.4), "dy": 3.8},
}

# Persistent run state for "Continue"
saved_run = None  # will store dict when you start a game
selected_ship = "Falcon"

def new_run_state(level_name="Easy"):
    cfg = LEVELS[level_name]
    ship_cfg = SHIPS[selected_ship]
    tuning = LEVEL_TUNING[level_name]
    state = {
        "level": level_name,
        "score": 0,
        "player_x": 370,
        "player_y": 480,
        "player_dx": 0,
        "bullets": [],  # list of {'x','y','dy'}
        "bullet_speed": ship_cfg["bullet_speed"],
        "fire_cooldown": 0,  # frames until next shot
        "fire_mode": ship_cfg["weapon"],  # 'normal','triple','rapid','spread','laser','burst'
        "fire_mode_timer": 0,  # frames remaining for powerup
        "base_weapon": ship_cfg["weapon"],
        "powerups": [],  # falling powerups
        "shield": False,
        "shield_timer": 0,
        "enemies": [],
        "enemy_bullets": [],  # bullets fired by enemies/boss
        "boss": None,  # boss dict when active
        "last_boss_score": -1,
        "enemy_speed": cfg["enemy_speed"],
        "enemy_drop": cfg["enemy_drop"],
        "num_enemies": cfg["num_enemies"],
        "game_over": False,
        "ship_name": selected_ship,
        "ship_speed": ship_cfg["speed"] + tuning["speed_bonus"],
        "ship_cooldown": ship_cfg["base_cooldown"],
        "explosions": [],
        "revive_tokens": 0,
        "revive_next_score": 15,
        "revive_max": 4,
        "revive_invuln": 0,
        "boss_spawn_score": tuning["boss_spawn"],
        "boss_cd": tuning["boss_cd"],
        "boss_speed_mul": tuning["boss_speed_mul"],
        "boss_spread": tuning["spread"],
        "boss_burst": tuning["burst"],
        "boss_wave": tuning["wave"],
        "boss_dy": tuning["dy"],
        "tutorial_timer": FPS * 8,
        "show_tips": True,
    }

    for _ in range(state["num_enemies"]):
        etype = random.choices(list(ENEMY_TYPES.keys()), weights=[60, 25, 15])[0]
        cfg_e = ENEMY_TYPES[etype]
        ex = random.randint(0, 736)
        ey = random.randint(50, 150)
        dx = state["enemy_speed"] * cfg_e["speed_mul"]
        state["enemies"].append({
            "x": ex,
            "y": ey,
            "dx": dx,  # direction+speed
            "type": etype,
            "hp": cfg_e["hp"],
            "shoot_cooldown": random.randint(30, 120) if cfg_e["shoots"] else None,
            "score": cfg_e["score"],
            "color": cfg_e["color"],
            "img": tint_image(ENEMY_IMG, cfg_e["color"]),
        })
    return state

def draw_text(text, font, color, x, y, center=False):
    surf = font.render(text, True, color)
    rect = surf.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    screen.blit(surf, rect)
    return rect

def is_collision(ex, ey, bx, by):
    dist = math.sqrt((ex - bx) ** 2 + (ey - by) ** 2)
    return dist < 27

def trigger_player_explosion(state, x, y):
    state["explosions"].append({
        "x": x,
        "y": y,
        "radius": 6,
        "dr": 3,
        "life": 22,
        "max_life": 22,
    })

def play_menu_music():
    try:
        mixer.music.load(MUSIC_MENU)
        mixer.music.play(-1)
    except Exception:
        # If mp3 decode fails on some setups, just ignore.
        pass

def play_game_music():
    try:
        mixer.music.load(MUSIC_GAME)
        mixer.music.play(-1)
    except Exception:
        pass

def stop_music():
    try:
        mixer.music.stop()
    except Exception:
        pass

# -------------------- Screen scaling + touch input --------------------

_scaled = None

def _layout():
    ww, wh = pygame.display.get_surface().get_size()
    scale = min(ww / WIDTH, wh / HEIGHT)
    sw, sh = max(1, int(WIDTH * scale)), max(1, int(HEIGHT * scale))
    return ww, wh, scale, (ww - sw) // 2, (wh - sh) // 2, sw, sh

def present():
    """Scale the virtual canvas to the real window (letterboxed) and flip."""
    global _scaled
    win = pygame.display.get_surface()
    ww, wh, scale, ox, oy, sw, sh = _layout()
    if (sw, sh) == (ww, wh):
        if (sw, sh) == (WIDTH, HEIGHT):
            win.blit(screen, (0, 0))
        else:
            if _scaled is None or _scaled.get_size() != (sw, sh):
                _scaled = pygame.Surface((sw, sh)).convert()
            pygame.transform.scale(screen, (sw, sh), _scaled)
            win.blit(_scaled, (0, 0))
    else:
        if _scaled is None or _scaled.get_size() != (sw, sh):
            _scaled = pygame.Surface((sw, sh)).convert()
        pygame.transform.scale(screen, (sw, sh), _scaled)
        win.fill((0, 0, 0))
        win.blit(_scaled, (ox, oy))
    pygame.display.flip()

def to_virtual(px, py):
    """Window pixels -> 800x600 game coordinates."""
    ww, wh, scale, ox, oy, sw, sh = _layout()
    return ((px - ox) / scale, (py - oy) / scale)

def finger_to_virtual(fx, fy):
    """Normalised touch coords (0..1) -> 800x600 game coordinates."""
    ww, wh = pygame.display.get_surface().get_size()
    return to_virtual(fx * ww, fy * wh)

def mouse_virtual():
    return to_virtual(*pygame.mouse.get_pos())

BACK_KEYS = (pygame.K_ESCAPE, getattr(pygame, "K_AC_BACK", pygame.K_ESCAPE))

_BG_EVENT = getattr(pygame, "APP_WILLENTERBACKGROUND", None)
_FG_EVENT = getattr(pygame, "APP_DIDENTERFOREGROUND", None)

pointers = {}  # active touches (or the mouse on desktop) -> (x, y) in game coords

def get_events():
    """pygame.event.get() plus Android pause/resume handling."""
    events = pygame.event.get()
    if ANDROID and _BG_EVENT is not None and _FG_EVENT is not None:
        for ev in events:
            if ev.type == _BG_EVENT:
                pointers.clear()
                try:
                    mixer.music.pause()
                except Exception:
                    pass
                while True:
                    ev2 = pygame.event.wait()
                    if ev2.type == pygame.QUIT:
                        pygame.quit()
                        raise SystemExit
                    if ev2.type == _FG_EVENT:
                        break
                try:
                    mixer.music.unpause()
                except Exception:
                    pass
                break
    return events

def track_pointer(event):
    """Keep `pointers` up to date. Returns the (x, y) of a brand-new press, else None."""
    t = event.type
    if t == pygame.FINGERDOWN:
        pos = finger_to_virtual(event.x, event.y)
        pointers[("f", event.finger_id)] = pos
        return pos
    if t == pygame.FINGERMOTION:
        pointers[("f", event.finger_id)] = finger_to_virtual(event.x, event.y)
    elif t == pygame.FINGERUP:
        pointers.pop(("f", event.finger_id), None)
    elif not ANDROID:  # desktop testing: mouse acts as one finger
        if t == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = to_virtual(*event.pos)
            pointers["mouse"] = pos
            return pos
        if t == pygame.MOUSEMOTION and "mouse" in pointers:
            pointers["mouse"] = to_virtual(*event.pos)
        elif t == pygame.MOUSEBUTTONUP and event.button == 1:
            pointers.pop("mouse", None)
    return None

def pointer_in(rect):
    return any(rect.collidepoint(int(p[0]), int(p[1])) for p in pointers.values())

# On-screen buttons (game coordinates)
BTN_LEFT = pygame.Rect(16, 488, 104, 92)
BTN_RIGHT = pygame.Rect(132, 488, 104, 92)
BTN_FIRE = pygame.Rect(664, 488, 120, 92)
BTN_MENU = pygame.Rect(10, 76, 84, 36)
BTN_REVIVE = pygame.Rect(300, 400, 200, 60)

def draw_button(rect, label, font, active=False):
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(s, (255, 255, 255, 110 if active else 55), s.get_rect(), border_radius=16)
    pygame.draw.rect(s, (255, 255, 255, 170), s.get_rect(), 2, border_radius=16)
    screen.blit(s, rect.topleft)
    draw_text(label, font, (255, 255, 255), rect.centerx, rect.centery, center=True)

_boss_img = None

def get_boss_img():
    global _boss_img
    if _boss_img is None:
        big = pygame.transform.scale(ENEMY_IMG, (ENEMY_IMG.get_width() * 2, ENEMY_IMG.get_height() * 2))
        _boss_img = tint_image(big, (255, 100, 200))
    return _boss_img

# -------------------- Menus with Selector --------------------

def menu_screen(title, options, selected_index=0):
    """
    Generic menu:
    - Up/Down to move selector
    - Enter to choose
    - Mouse hover highlights; click chooses
    Returns selected option index.
    """
    while True:
        clock.tick(FPS)

        # Background
        screen.blit(BG_MENU, (0, 0))

        # Title
        draw_text(title, font_title, (255, 255, 255), WIDTH // 2, 140, center=True)

        # Options rendering
        option_rects = []
        start_y = 260
        line_h = 55

        mx, my = mouse_virtual()
        hovered = None

        for i, label in enumerate(options):
            y = start_y + i * line_h

            # Highlight if selected/hovered
            is_sel = (i == selected_index)

            # Render text to get rect
            color = (255, 255, 255)
            rect = draw_text(label, font_menu, color, WIDTH // 2, y, center=True)
            option_rects.append(rect)

            # Hover detection
            if rect.collidepoint(mx, my):
                hovered = i

            # Draw selector + highlight box
            if is_sel:
                pad_x, pad_y = 18, 10
                box = pygame.Rect(rect.left - pad_x, rect.top - pad_y,
                                  rect.width + pad_x * 2, rect.height + pad_y * 2)
                pygame.draw.rect(screen, (255, 255, 255), box, 2, border_radius=10)

                # Little arrow ">"
                draw_text(">", font_menu, (255, 255, 255), box.left - 30, rect.centery - rect.height // 2, center=False)

        # If hovering, move selection (feels nice)
        if hovered is not None and not ANDROID:
            selected_index = hovered

        present()

        # Events
        for event in get_events():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit

            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    selected_index = (selected_index - 1) % len(options)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    selected_index = (selected_index + 1) % len(options)
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    return selected_index
                elif event.key in BACK_KEYS:
                    return None  # back/cancel

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Tap / click selects whatever is under the pointer
                pos = to_virtual(*event.pos)
                for i, r in enumerate(option_rects):
                    if r.inflate(60, 24).collidepoint(int(pos[0]), int(pos[1])):
                        return i

def main_menu():
    global saved_run

    stop_music()
    play_menu_music()

    options = ["New Game", "Continue", "Tutorial", "Ship Select", "Levels", "Quit"]
    selected = 0

    while True:
        choice = menu_screen("SPACE INVADER", options, selected_index=selected)
        if choice is None:
            # Escape does nothing here, keep menu
            continue

        selected = choice

        if options[choice] == "New Game":
            saved_run = new_run_state("Easy")
            stop_music()
            play_game_music()
            run_game(saved_run)

            # back to menu after game ends
            stop_music()
            play_menu_music()

        elif options[choice] == "Continue":
            if saved_run is None:
                # if nothing to continue, start new
                saved_run = new_run_state("Easy")
            stop_music()
            play_game_music()
            run_game(saved_run)
            stop_music()
            play_menu_music()

        elif options[choice] == "Tutorial":
            tutorial_screen()

        elif options[choice] == "Ship Select":
            ship_select_menu()

        elif options[choice] == "Levels":
            level_menu()

        elif options[choice] == "Quit":
            pygame.quit()
            raise SystemExit

def level_menu():
    global saved_run

    options = ["Easy", "Medium", "Hard", "Insane", "Back"]
    selected = 0

    while True:
        choice = menu_screen("SELECT LEVEL", options, selected_index=selected)
        if choice is None:
            return  # ESC back

        selected = choice

        if options[choice] == "Back":
            return

        # Start a new run at chosen level
        saved_run = new_run_state(options[choice])
        stop_music()
        play_game_music()
        run_game(saved_run)
        stop_music()
        play_menu_music()

# -------------------- Tutorial --------------------

def tutorial_screen():
    if TOUCH_UI:
        tips = [
            "Move: < and > buttons",
            "Shoot: hold FIRE",
            "Revive: REVIVE button (when available)",
            "Powerups: TRI, RAP, SPRD, LASR, BURST, SHD",
            "Boss: dodge patterns, keep moving",
            "Tip: hold FIRE for Laser beam",
        ]
    else:
        tips = [
            "Move: A/D or Left/Right",
            "Shoot: Space",
            "Revive: R (when available)",
            "Powerups: TRI, RAP, SPRD, LASR, BURST, SHD",
            "Boss: dodge patterns, keep moving",
            "Tip: hold Space for Laser beam",
        ]

    while True:
        clock.tick(FPS)
        screen.blit(BG_MENU, (0, 0))
        draw_text("HOW TO PLAY", font_title, (255, 255, 255), WIDTH // 2, 110, center=True)

        y = 220
        for t in tips:
            draw_text(t, font_menu, (255, 255, 255), WIDTH // 2, y, center=True)
            y += 45

        draw_text(("Tap anywhere to go back" if TOUCH_UI else "Press Enter to start or ESC to go back"), font_score, (255, 255, 255), WIDTH // 2, HEIGHT - 60, center=True)
        present()

        for event in get_events():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    return
                if event.key in BACK_KEYS:
                    return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                return

# -------------------- Ship Select --------------------

def ship_select_menu():
    global selected_ship

    ship_names = list(SHIPS.keys())
    selected = ship_names.index(selected_ship) if selected_ship in ship_names else 0

    while True:
        clock.tick(FPS)
        screen.blit(BG_MENU, (0, 0))
        draw_text("SELECT SHIP", font_title, (255, 255, 255), WIDTH // 2, 110, center=True)

        # Draw ships in a grid
        cols = 4
        start_x = 120
        start_y = 230
        gap_x = 170
        gap_y = 170
        mx, my = mouse_virtual()

        hover_idx = None
        rects = []
        for i, name in enumerate(ship_names):
            row = i // cols
            col = i % cols
            x = start_x + col * gap_x
            y = start_y + row * gap_y
            img = SHIPS[name]["img"]
            rect = img.get_rect(center=(x, y))
            screen.blit(img, rect.topleft)
            draw_text(name, font_menu, (255, 255, 255), x, y + 70, center=True)
            rects.append(rect)
            if rect.collidepoint(mx, my):
                hover_idx = i

            if i == selected:
                pad = 10
                box = pygame.Rect(rect.left - pad, rect.top - pad, rect.width + pad * 2, rect.height + pad * 2)
                pygame.draw.rect(screen, (255, 255, 255), box, 2, border_radius=8)

        draw_text(("Tap a ship to select  |  Back button: return" if TOUCH_UI else "Enter: Select  |  ESC: Back"), font_score, (255, 255, 255), WIDTH // 2, HEIGHT - 60, center=True)

        if hover_idx is not None and not ANDROID:
            selected = hover_idx

        present()

        for event in get_events():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_LEFT, pygame.K_a):
                    selected = (selected - 1) % len(ship_names)
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    selected = (selected + 1) % len(ship_names)
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    selected_ship = ship_names[selected]
                    return
                elif event.key in BACK_KEYS:
                    return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = to_virtual(*event.pos)
                for i, r in enumerate(rects):
                    if r.inflate(40, 70).collidepoint(int(pos[0]), int(pos[1])):
                        selected_ship = ship_names[i]
                        return

# -------------------- Game Loop --------------------

def try_fire(state, auto=False):
    """Fire the current weapon if off cooldown. auto=True is used for hold-to-fire."""
    if state["game_over"] or state["fire_cooldown"] > 0:
        return
    mode = state["fire_mode"]
    if not (auto and mode == "laser"):
        SND_LASER.play()
    px = state["player_x"]
    if mode == "triple":
        for ox in (-20, 0, 20):
            state["bullets"].append({"x": px + ox, "y": 480, "dy": -state["bullet_speed"], "dx": 0, "damage": 1, "type": "bullet"})
    elif mode == "spread":
        for dx in (-2.4, -1.2, 0, 1.2, 2.4):
            state["bullets"].append({"x": px, "y": 480, "dy": -state["bullet_speed"] + 1, "dx": dx, "damage": 1, "type": "bullet"})
    elif mode == "laser":
        pass  # sustained beam, handled in the game loop while FIRE/Space is held
    elif mode == "burst":
        for oy in (0, 8, 16):
            state["bullets"].append({"x": px, "y": 480 - oy, "dy": -state["bullet_speed"], "dx": 0, "damage": 1, "type": "bullet"})
    else:
        state["bullets"].append({"x": px, "y": 480, "dy": -state["bullet_speed"], "dx": 0, "damage": 1, "type": "bullet"})

    base_cd = state.get("ship_cooldown", 14)
    if mode == "rapid":
        state["fire_cooldown"] = 5
    elif mode == "laser":
        state["fire_cooldown"] = 6
    elif mode == "burst":
        state["fire_cooldown"] = base_cd + 2
    else:
        state["fire_cooldown"] = base_cd

def do_revive(state):
    state["game_over"] = False
    state["revive_tokens"] -= 1
    state["revive_invuln"] = FPS * 2
    state["enemy_bullets"] = []
    state["player_x"] = 370
    SND_LASER.play()

def run_game(state):
    """
    Runs the actual game using the provided state dict.
    Updates state in-place so "Continue" works.
    """
    # Short aliases
    player_y = state["player_y"]
    bullet_speed = state.get("bullet_speed", 10)
    ship_speed = state.get("ship_speed", 6.0)
    ship_cfg = SHIPS[state.get("ship_name", "Falcon")]
    ship_img = ship_cfg["img"]
    ship_glow = ship_cfg.get("glow", (120, 200, 255))
    pygame.event.clear()  # drop the tap that started the game
    pointers.clear()

    while True:
        clock.tick(FPS)

        # Events
        for event in get_events():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit

            # Touch / mouse presses on the on-screen buttons
            press = track_pointer(event)
            if press is not None and TOUCH_UI:
                tx, ty = int(press[0]), int(press[1])
                if BTN_MENU.collidepoint(tx, ty):
                    return
                if state["game_over"] and state["revive_tokens"] > 0 and BTN_REVIVE.collidepoint(tx, ty):
                    do_revive(state)

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    try_fire(state)
                elif event.key in BACK_KEYS:
                    # Back to menu
                    return
                elif event.key == pygame.K_r:
                    # Revive if ready
                    if state["game_over"] and state["revive_tokens"] > 0:
                        do_revive(state)

            if event.type == pygame.KEYUP:
                if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    state["player_dx"] = 0
                if event.key == pygame.K_h:
                    state["show_tips"] = not state.get("show_tips", True)

        # Smooth input every frame (keyboard + on-screen buttons)
        keys = pygame.key.get_pressed()
        left_btn = TOUCH_UI and pointer_in(BTN_LEFT)
        right_btn = TOUCH_UI and pointer_in(BTN_RIGHT)
        fire_btn = TOUCH_UI and pointer_in(BTN_FIRE)
        dx = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a] or left_btn:
            dx -= ship_speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d] or right_btn:
            dx += ship_speed
        state["player_dx"] = dx
        if fire_btn:
            try_fire(state, auto=True)
        laser_active = ((keys[pygame.K_SPACE] or fire_btn) and state["fire_mode"] == "laser" and not state["game_over"])

        # Update player
        state["player_x"] += state["player_dx"]
        state["player_x"] = clamp(state["player_x"], 0, 736)

        # Draw background
        screen.blit(BG_GAME, (0, 0))

        # Enemy movement (types + optional shooting)
        if not state["game_over"]:
            for e in state["enemies"]:
                e["x"] += e["dx"]

                # bounce on edges using current enemy_speed magnitude
                if e["x"] <= 0:
                    e["dx"] = abs(e["dx"])
                    e["y"] += state["enemy_drop"]
                elif e["x"] >= 736:
                    e["dx"] = -abs(e["dx"])
                    e["y"] += state["enemy_drop"]

                # Shooting enemies fire downward occasionally
                if e.get("shoot_cooldown") is not None:
                    e["shoot_cooldown"] -= 1
                    if e["shoot_cooldown"] <= 0:
                        # fire a bullet from enemy
                        state["enemy_bullets"].append({"x": e["x"] + ENEMY_IMG.get_width()//2, "y": e["y"] + ENEMY_IMG.get_height(), "dy": 4, "owner": "enemy"})
                        e["shoot_cooldown"] = random.randint(50, 140)

                # Game over check (shield protects once)
                if e["y"] > 440:
                    if state["shield"]:
                        state["shield"] = False
                        state["shield_timer"] = 0
                        e["y"] = 100
                    else:
                        if not state["game_over"]:
                            trigger_player_explosion(state, state["player_x"] + PLAYER_IMG.get_width()//2, player_y + PLAYER_IMG.get_height()//2)
                        state["game_over"] = True

        # Boss spawn: every N points spawn a boss once
        boss_spawn = state.get("boss_spawn_score", 12)
        if state["boss"] is None and state["score"] > 0 and state["score"] % boss_spawn == 0 and state["last_boss_score"] != state["score"]:
            # spawn boss with entry animation
            hp = BOSS_CONFIG["hp_base"] + (state["score"] // boss_spawn) * 4
            state["boss"] = {
                "x": 100,
                "y": -120,
                "target_y": 40,
                "dx": BOSS_CONFIG["speed"] * state.get("boss_speed_mul", 1.0),
                "hp": hp,
                "cooldown": state.get("boss_cd", BOSS_CONFIG["shoot_cooldown"]),
                "score": BOSS_CONFIG["score"],
                "phase": 0,
                "phase_timer": FPS * 3,
                "entering": True,
            }
            state["last_boss_score"] = state["score"]

        # Boss movement and shooting
        if state["boss"] is not None and not state["game_over"]:
            b = state["boss"]
            if b.get("entering"):
                b["y"] += 3
                if b["y"] >= b["target_y"]:
                    b["y"] = b["target_y"]
                    b["entering"] = False
            else:
                b["x"] += b["dx"]
                if b["x"] <= 0 or b["x"] >= 736:
                    b["dx"] = -b["dx"]

                # phase switching
                b["phase_timer"] -= 1
                if b["phase_timer"] <= 0:
                    b["phase"] = (b["phase"] + 1) % 3
                    b["phase_timer"] = FPS * 3

                b["cooldown"] -= 1
                if b["cooldown"] <= 0:
                    cx = b["x"] + ENEMY_IMG.get_width()//2
                    cy = b["y"] + ENEMY_IMG.get_height()
                    if b["phase"] == 0:
                        # spread shot
                        for dx in state.get("boss_spread", (-2.2, -1.1, 0, 1.1, 2.2)):
                            state["enemy_bullets"].append({"x": cx, "y": cy, "dx": dx, "dy": state.get("boss_dy", 3.2), "owner": "boss"})
                    elif b["phase"] == 1:
                        # burst downward
                        for _ in range(state.get("boss_burst", 6)):
                            state["enemy_bullets"].append({"x": cx + random.randint(-20, 20), "y": cy, "dx": 0, "dy": state.get("boss_dy", 4.2) + 0.6, "owner": "boss"})
                    else:
                        # sweeping wave
                        for dx in state.get("boss_wave", (-2.0, 0, 2.0)):
                            state["enemy_bullets"].append({"x": cx, "y": cy, "dx": dx, "dy": state.get("boss_dy", 3.5) + 0.4, "owner": "boss"})
                    base_cd = state.get("boss_cd", BOSS_CONFIG["shoot_cooldown"])
                    b["cooldown"] = max(28, base_cd - state["score"] // 8)

        # Bullets: movement, draw and collisions
        if not state["game_over"]:
            new_bullets = []
            for b in state["bullets"]:
                b["x"] += b.get("dx", 0)
                b["y"] += b["dy"]
                # draw bullet
                screen.blit(BULLET_IMG, (b["x"] + 16, b["y"] + 10))
                if b["y"] > 0:
                    hit = False
                    # boss collision
                    if state["boss"] is not None:
                        boss_rect = pygame.Rect(state["boss"]["x"], state["boss"]["y"],
                                                ENEMY_IMG.get_width()*2, ENEMY_IMG.get_height()*2)
                        if boss_rect.collidepoint(b["x"], b["y"]):
                            SND_EXPLODE.play()
                            state["boss"]["hp"] -= b.get("damage", 1)
                            if state["boss"]["hp"] <= 0:
                                trigger_player_explosion(state, state["boss"]["x"] + ENEMY_IMG.get_width(), state["boss"]["y"] + ENEMY_IMG.get_height())
                                state["score"] += state["boss"].get("score", 10)
                                state["boss"] = None
                            hit = True

                    for e in state["enemies"]:
                        if not hit and is_collision(e["x"], e["y"], b["x"], b["y"]):
                            SND_EXPLODE.play()
                            e["hp"] -= b.get("damage", 1)
                            if e["hp"] <= 0:
                                state["score"] += e.get("score", 1)
                                # chance to drop powerup
                                if random.random() < 0.28:
                                    ptype = random.choice(["TRI", "RAP", "SHD", "BONUS", "SPRD", "LASR", "BURST"])
                                    state["powerups"].append({"x": e["x"], "y": e["y"], "type": ptype, "dy": 2})
                                # respawn enemy
                                etype = e["type"]
                                cfg_e = ENEMY_TYPES[etype]
                                e["x"] = random.randint(0, 736)
                                e["y"] = random.randint(50, 150)
                                e["dx"] = abs(state["enemy_speed"]) if e["dx"] >= 0 else -abs(state["enemy_speed"])
                                e["hp"] = cfg_e["hp"]
                                e["score"] = cfg_e["score"]
                                # speed up world a bit
                                state["enemy_speed"] *= 1.015
                                for en in state["enemies"]:
                                    en["dx"] = abs(state["enemy_speed"]) if en["dx"] >= 0 else -abs(state["enemy_speed"])
                            hit = True
                            break
                    if not hit:
                        new_bullets.append(b)
            state["bullets"] = new_bullets

        # Sustained laser beam (thicker like mobile space invader)
        if laser_active:
            beam_w = 12
            beam_x = int(state["player_x"] + 16 - beam_w // 2)
            # extend beam to the top of the screen
            beam_y = 0
            beam_len = int(player_y + PLAYER_IMG.get_height() // 2)
            beam_rect = pygame.Rect(beam_x, beam_y, beam_w, beam_len)
            pygame.draw.rect(screen, (255, 60, 60), beam_rect)
            pygame.draw.rect(screen, (255, 210, 210), beam_rect, 2)

            # damage boss/enemies while beam touches them
            if state["boss"] is not None:
                boss_rect = pygame.Rect(state["boss"]["x"], state["boss"]["y"],
                                        ENEMY_IMG.get_width()*2, ENEMY_IMG.get_height()*2)
                if boss_rect.colliderect(beam_rect):
                    state["boss"]["hp"] -= 0.2
                    if state["boss"]["hp"] <= 0:
                        trigger_player_explosion(state, state["boss"]["x"] + ENEMY_IMG.get_width(), state["boss"]["y"] + ENEMY_IMG.get_height())
                        state["score"] += state["boss"].get("score", 10)
                        state["boss"] = None

            for e in state["enemies"]:
                e_rect = pygame.Rect(e["x"], e["y"], ENEMY_IMG.get_width(), ENEMY_IMG.get_height())
                if e_rect.colliderect(beam_rect):
                    e["hp"] -= 0.2
                    if e["hp"] <= 0:
                        state["score"] += e.get("score", 1)
                        if random.random() < 0.28:
                            ptype = random.choice(["TRI", "RAP", "SHD", "BONUS", "SPRD", "LASR", "BURST"])
                            state["powerups"].append({"x": e["x"], "y": e["y"], "type": ptype, "dy": 2})
                        etype = e["type"]
                        cfg_e = ENEMY_TYPES[etype]
                        e["x"] = random.randint(0, 736)
                        e["y"] = random.randint(50, 150)
                        e["dx"] = abs(state["enemy_speed"]) if e["dx"] >= 0 else -abs(state["enemy_speed"])
                        e["hp"] = cfg_e["hp"]
                        e["score"] = cfg_e["score"]
                        state["enemy_speed"] *= 1.015
                        for en in state["enemies"]:
                            en["dx"] = abs(state["enemy_speed"]) if en["dx"] >= 0 else -abs(state["enemy_speed"])

        # Powerups falling and pickup
        new_pu = []
        for p in state["powerups"]:
            p["y"] += p["dy"]
            # draw powerup sprite
            pu_img = POWERUP_SPRITES.get(p["type"])
            if pu_img:
                screen.blit(pu_img, (p["x"], p["y"]))
            draw_text(p["type"], font_score, (0, 0, 0), int(p["x"]+8), int(p["y"]+6))

            player_rect = pygame.Rect(state["player_x"], player_y, PLAYER_IMG.get_width(), PLAYER_IMG.get_height())
            if player_rect.collidepoint(p["x"]+16, p["y"]+16):
                # apply effect
                if p["type"] == "TRI":
                    state["fire_mode"] = "triple"
                    state["fire_mode_timer"] = FPS * 6
                elif p["type"] == "RAP":
                    state["fire_mode"] = "rapid"
                    state["fire_mode_timer"] = FPS * 6
                elif p["type"] == "SPRD":
                    state["fire_mode"] = "spread"
                    state["fire_mode_timer"] = FPS * 6
                elif p["type"] == "LASR":
                    state["fire_mode"] = "laser"
                    state["fire_mode_timer"] = FPS * 6
                elif p["type"] == "BURST":
                    state["fire_mode"] = "burst"
                    state["fire_mode_timer"] = FPS * 6
                elif p["type"] == "SHD":
                    state["shield"] = True
                    state["shield_timer"] = FPS * 8
                elif p["type"] == "BONUS":
                    state["score"] += 5
                SND_LASER.play()
            else:
                if p["y"] < HEIGHT:
                    new_pu.append(p)
        state["powerups"] = new_pu

        # Cooldowns / timers
        if state["fire_cooldown"] > 0:
            state["fire_cooldown"] -= 1
        if state["fire_mode_timer"] > 0:
            state["fire_mode_timer"] -= 1
            if state["fire_mode_timer"] == 0:
                state["fire_mode"] = state.get("base_weapon", "normal")
        if state["shield_timer"] > 0:
            state["shield_timer"] -= 1
            if state["shield_timer"] == 0:
                state["shield"] = False
        # draw player
        if not state["game_over"]:
            # subtle glow to keep ship visible
            glow = pygame.Surface((80, 80), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*ship_glow, 70), (40, 40), 28)
            screen.blit(glow, (state["player_x"] - 8, player_y - 8))
            screen.blit(ship_img, (state["player_x"], player_y))

        # Draw enemies (colored/tinted)
        for e in state["enemies"]:
            img = e.get("img") if e.get("img") is not None else tint_image(ENEMY_IMG, e.get("color", (200,200,200)))
            screen.blit(img, (e["x"], e["y"]))
            # optional hp indicator for heavy types
            if e.get("hp", 0) > 1:
                draw_text(str(e.get("hp", 0)), font_score, (255,255,255), e["x"]+10, e["y"]-6)

        # Score + level
        draw_text(f"Score: {state['score']}", font_score, (255, 255, 255), 10, 10)
        draw_text(f"Level: {state['level']}", font_score, (255, 255, 255), 10, 42)

        # Draw enemy bullets
        new_eb = []
        prect = pygame.Rect(state["player_x"], player_y, PLAYER_IMG.get_width(), PLAYER_IMG.get_height())
        for eb in state["enemy_bullets"]:
            # update
            eb["x"] += eb.get("dx", 0)
            eb["y"] += eb.get("dy", 4)
            # draw
            pygame.draw.circle(screen, (255, 80, 80), (int(eb["x"]), int(eb["y"])), 6)
            # collision with player
            if prect.collidepoint(int(eb["x"]), int(eb["y"])):
                if state["revive_invuln"] > 0:
                    continue
                if state["shield"]:
                    state["shield"] = False
                    state["shield_timer"] = 0
                else:
                    if not state["game_over"]:
                        trigger_player_explosion(state, state["player_x"] + PLAYER_IMG.get_width()//2, player_y + PLAYER_IMG.get_height()//2)
                    state["game_over"] = True
            elif 0 <= eb["y"] < HEIGHT:
                new_eb.append(eb)
        state["enemy_bullets"] = new_eb

        # Boss drawing and HP
        if state["boss"] is not None:
            b = state["boss"]
            # big tinted boss image
            boss_img = get_boss_img()
            screen.blit(boss_img, (b["x"], b["y"]))
            # boss HP bar
            bar_w = 200
            boss_spawn = state.get("boss_spawn_score", 12)
            hp_ratio = max(0.0, b["hp"]) / (BOSS_CONFIG["hp_base"] + (state["score"]//boss_spawn)*4)
            pygame.draw.rect(screen, (255,0,0), (WIDTH//2 - bar_w//2, 12, int(bar_w*hp_ratio), 10))
            pygame.draw.rect(screen, (255,255,255), (WIDTH//2 - bar_w//2, 12, bar_w, 10), 2)

        # Power-up HUD
        hud_x = WIDTH - 200
        draw_text(f"Power: {state['fire_mode']}", font_score, (255,255,255), hud_x, 10)
        if state["fire_mode_timer"] > 0:
            draw_text(f"{state['fire_mode_timer']//FPS}s", font_score, (255,255,255), hud_x, 42)
        if state['shield']:
            draw_text("Shield: ON", font_score, (0,255,255), hud_x, 74)
            pygame.draw.circle(screen, (0,255,255), (int(state['player_x']+PLAYER_IMG.get_width()/2), int(player_y+PLAYER_IMG.get_height()/2)), 40, 2)
        if state.get("show_tips", True) and state.get("tutorial_timer", 0) > 0:
            draw_text(("Tips: < > to move, FIRE to shoot" if TOUCH_UI else "Tips: Move A/D, Shoot Space, Revive R"), font_score, (255,255,200), WIDTH // 2, 90, center=True)
            draw_text(("Hold FIRE for the Laser beam" if TOUCH_UI else "Hold Space for Laser beam. Press H to hide tips"), font_score, (255,255,200), WIDTH // 2, 118, center=True)

        # Revive HUD
        if state["score"] >= state["revive_next_score"] and state["revive_tokens"] < state["revive_max"]:
            state["revive_tokens"] += 1
            state["revive_next_score"] *= 2
        if state["revive_tokens"] > 0 and not state["game_over"]:
            draw_text(f"Revive: {state['revive_tokens']}/{state['revive_max']}", font_score, (255, 255, 100), hud_x, 106)
        if state["revive_invuln"] > 0:
            state["revive_invuln"] -= 1
        if state.get("tutorial_timer", 0) > 0:
            state["tutorial_timer"] -= 1

        # Explosions animation
        new_explosions = []
        for ex in state["explosions"]:
            ex["radius"] += ex["dr"]
            ex["life"] -= 1
            if ex["life"] > 0:
                new_explosions.append(ex)
            # draw
            alpha = int(255 * (ex["life"] / ex["max_life"]))
            boom = pygame.Surface((ex["radius"]*2, ex["radius"]*2), pygame.SRCALPHA)
            pygame.draw.circle(boom, (255, 180, 60, alpha), (ex["radius"], ex["radius"]), ex["radius"])
            screen.blit(boom, (ex["x"] - ex["radius"], ex["y"] - ex["radius"]))
        state["explosions"] = new_explosions

        # Game over overlay
        if state["game_over"]:
            draw_text("GAME OVER", font_over, (255, 255, 255), WIDTH // 2, HEIGHT // 2 - 30, center=True)
            if TOUCH_UI:
                if state["revive_tokens"] > 0:
                    draw_button(BTN_REVIVE, "REVIVE", font_menu, pointer_in(BTN_REVIVE))
                draw_text("Tap MENU to go back", font_score, (255, 255, 255), WIDTH // 2, HEIGHT // 2 + 20, center=True)
            elif state["revive_tokens"] > 0:
                draw_text("Press R to revive", font_score, (255, 255, 255), WIDTH // 2, HEIGHT // 2 + 20, center=True)
                draw_text("Press ESC to go back", font_score, (255, 255, 255), WIDTH // 2, HEIGHT // 2 + 60, center=True)
            else:
                draw_text("Press ESC to go back", font_score, (255, 255, 255), WIDTH // 2, HEIGHT // 2 + 40, center=True)

        # On-screen controls
        if TOUCH_UI:
            draw_button(BTN_LEFT, "<", font_title, pointer_in(BTN_LEFT))
            draw_button(BTN_RIGHT, ">", font_title, pointer_in(BTN_RIGHT))
            draw_button(BTN_FIRE, "FIRE", font_menu, pointer_in(BTN_FIRE))
            draw_button(BTN_MENU, "MENU", font_score, False)

        present()


if __name__ == "__main__":
    main_menu()
