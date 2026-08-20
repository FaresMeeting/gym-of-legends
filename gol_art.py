# -*- coding: utf-8 -*-
"""
GYM OF LEGENDS - couche artistique
==================================

TOUT ce qui est affiche par le jeu est GENERE PAR LE CODE : polygones,
degrades, particules, lumieres. Aucune image, aucun asset telecharge,
aucun calque ni trace d'une oeuvre existante.

=> l'integralite du visuel (Cerbere compris) est une creation originale,
   libre de droits, exploitable commercialement sans autorisation tierce.

Cerbere n'est pas une marque : c'est une figure de la mythologie grecque,
donc du domaine public. Ce sont les *representations* particulieres
(illustrations d'artistes, personnages de jeux) qui sont protegees - et
nous n'en reproduisons aucune. Les attributs utilises ici (trois tetes,
queue de serpent, chien massif, portail des Enfers) sont des elements
mythologiques generiques, non appropriables.

Direction artistique :
  - eclairage a deux sources : cle chaude (braseros, bas-gauche)
    + contre-jour froid spectral (portail, haut-droite)
  - silhouettes lisibles, aplats sculptes, liseres marques
  - grain, vignettage, brumes : rendu "peint" plutot que "vectoriel"
"""

import math
import random

import pygame
import pygame.gfxdraw

# ============================================================== PALETTE =====
VOID        = (8, 6, 11)
NIGHT       = (17, 13, 21)
NIGHT_WARM  = (32, 21, 22)
# La pierre reste sombre : un decor plus clair que les personnages leur
# vole la lecture et casse le contre-jour.
STONE_DARK  = (22, 19, 26)
STONE       = (38, 33, 42)
STONE_LIT   = (58, 49, 52)
STONE_WARM  = (78, 55, 44)

BEAST_DARK  = (16, 12, 15)
BEAST       = (34, 25, 27)
BEAST_MID   = (55, 40, 39)
BEAST_WARM  = (96, 58, 40)
FUR_TIP     = (128, 82, 52)

# Liseres de contre-jour : volontairement sourds. Un lisere trop clair
# transforme le personnage en autocollant fluo au lieu de suggerer une
# source lumineuse derriere lui.
RIM_COLD    = (72, 124, 114)
RIM_SOFT    = (42, 72, 70)
SPECTRE     = (156, 228, 194)
SPECTRE_DIM = (70, 122, 104)

FIRE_LOW    = (176, 46, 22)
FIRE_MID    = (255, 132, 40)
FIRE_HOT    = (255, 226, 158)
EMBER       = (255, 150, 58)

EYE_HOT     = (255, 96, 58)
EYE_CORE    = (255, 226, 198)
BLOOD       = (198, 40, 34)
MAW         = (74, 18, 22)
TOOTH       = (226, 218, 200)

PELT        = (170, 114, 50)
BRONZE      = (146, 104, 56)

GOLD        = (238, 192, 106)
GOLD_DIM    = (150, 118, 62)
WHITE       = (245, 242, 235)
GREY        = (126, 120, 132)
GREY_DARK   = (54, 50, 60)
GREEN       = (94, 206, 136)
RED         = (216, 58, 48)
INK         = (7, 6, 9)


# ================================================================ FONTS =====
_FONT_CACHE = {}

# Familles cherchees par ordre de preference. Toutes presentes par defaut
# sur Windows ; repli automatique sur la police systeme si absentes.
FAM_DISPLAY = ["Bahnschrift SemiBold Condensed", "Bahnschrift", "Impact",
               "Haettenschweiler", "Arial Narrow"]
FAM_TITLE   = ["Constantia", "Georgia", "Palatino Linotype", "Book Antiqua"]
FAM_BODY    = ["Segoe UI Semibold", "Segoe UI", "Calibri", "Tahoma"]


def font(family, size, bold=False, italic=False):
    """Charge une police en essayant plusieurs familles, avec cache."""
    key = (tuple(family), size, bold, italic)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    f = None
    for name in family:
        try:
            path = pygame.font.match_font(name, bold=bold, italic=italic)
        except Exception:
            path = None
        if path:
            try:
                f = pygame.font.Font(path, size)
                break
            except Exception:
                f = None
    if f is None:
        f = pygame.font.SysFont(None, int(size * 1.25), bold=bold, italic=italic)
    _FONT_CACHE[key] = f
    return f


def text(surf, s, f, color, x, y, anchor="left", shadow=True, glow=None):
    """Texte avec ombre portee (lisibilite sur fond charge) et halo optionnel."""
    img = f.render(s, True, color)
    r = img.get_rect()
    setattr(r, {"left": "midleft", "center": "center",
                "right": "midright", "top": "midtop"}[anchor], (x, y))
    if glow:
        g = f.render(s, True, glow)
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            gg = g.copy()
            gg.set_alpha(70)
            surf.blit(gg, r.move(dx, dy))
    if shadow:
        sh = f.render(s, True, (0, 0, 0))
        sh.set_alpha(190)
        surf.blit(sh, r.move(2, 3))
    surf.blit(img, r)
    return r


# ============================================================== HELPERS =====
def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return (int(lerp(c1[0], c2[0], t)),
            int(lerp(c1[1], c2[1], t)),
            int(lerp(c1[2], c2[2], t)))


def shade(c, k):
    """Assombrit (k<1) ou eclaircit (k>1) une couleur."""
    return (max(0, min(255, int(c[0] * k))),
            max(0, min(255, int(c[1] * k))),
            max(0, min(255, int(c[2] * k))))


def tform(pts, ox, oy, ang=0.0, s=1.0, sy=None, flip=False):
    """Translation + rotation + echelle d'une liste de points locaux."""
    sy = s if sy is None else sy
    ca, sa = math.cos(ang), math.sin(ang)
    out = []
    for x, y in pts:
        x = -x * s if flip else x * s
        y = y * sy
        out.append((ox + x * ca - y * sa, oy + x * sa + y * ca))
    return out


def smooth(pts, steps=6, closed=True):
    """
    Catmull-Rom : transforme un polygone anguleux en contour organique.

    En mode ouvert on duplique les extremites, sinon le premier et le
    dernier segment ne sont jamais generes (la spline a besoin d'un point
    de controle de chaque cote).
    """
    pts = list(pts)
    n = len(pts)
    if n < 3:
        return pts
    if not closed:
        pts = [pts[0]] + pts + [pts[-1]]
        n = len(pts)

    out = []
    last = n if closed else n - 3
    for i in range(last):
        p0 = pts[(i - 1) % n] if closed else pts[i]
        p1 = pts[(i + 1) % n] if not closed else pts[i % n]
        p2 = pts[(i + 2) % n] if not closed else pts[(i + 1) % n]
        p3 = pts[(i + 3) % n] if not closed else pts[(i + 2) % n]
        for k in range(steps):
            t = k / steps
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    if not closed:
        out.append(pts[-1])
    return out


def tapered(joints, widths, steps=5):
    """
    Membre / cou / queue : tube qui suit une polyligne avec largeur variable.
    Beaucoup plus controlable qu'une liste de points dessinee a la main.
    """
    path = smooth(joints, steps=steps, closed=False)
    if len(path) < 2:
        path = list(joints)
    # largeur interpolee le long du chemin lisse
    n = len(path)
    ws = []
    for i in range(n):
        u = i / max(1, n - 1) * (len(widths) - 1)
        i0 = int(u)
        i1 = min(len(widths) - 1, i0 + 1)
        ws.append(lerp(widths[i0], widths[i1], u - i0))

    left, right = [], []
    for i, (x, y) in enumerate(path):
        if i == 0:
            dx, dy = path[1][0] - x, path[1][1] - y
        elif i == n - 1:
            dx, dy = x - path[-2][0], y - path[-2][1]
        else:
            dx, dy = path[i + 1][0] - path[i - 1][0], path[i + 1][1] - path[i - 1][1]
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        left.append((x + nx * ws[i], y + ny * ws[i]))
        right.append((x - nx * ws[i], y - ny * ws[i]))
    return left + right[::-1]


def poly(surf, pts, color, aa=True):
    if len(pts) < 3:
        return
    ip = [(int(x), int(y)) for x, y in pts]
    pygame.draw.polygon(surf, color, ip)
    if aa:
        try:
            pygame.gfxdraw.aapolygon(surf, ip, color)
        except Exception:
            pass


def sculpt(surf, pts, base, rim=None, under=None,
           rim_off=(4, -5), under_off=(-4, 4), edge=None, ew=2):
    """
    Volume en 3 passes : contre-jour froid decale en haut-droite,
    rebond chaud decale en bas-gauche, puis l'aplat de base par-dessus.
    C'est ce qui donne l'impression de masse sculptee.
    """
    if under:
        poly(surf, [(x + under_off[0], y + under_off[1]) for x, y in pts], under)
    if rim:
        poly(surf, [(x + rim_off[0], y + rim_off[1]) for x, y in pts], rim)
    poly(surf, pts, base)
    if edge:
        ip = [(int(x), int(y)) for x, y in pts]
        pygame.draw.polygon(surf, edge, ip, ew)


_GLOW = {}


def _quant(c, step=10):
    return (c[0] // step * step, c[1] // step * step, c[2] // step * step)


def glow(surf, x, y, radius, color, alpha=255):
    """
    Halo radial ADDITIF.

    Attention : pygame.BLEND_ADD ignore le canal alpha de la source. Il faut
    donc pre-multiplier l'intensite DANS les composantes RGB, sinon on obtient
    un disque plat sature au lieu d'un degrade. C'est ce qui est fait ici.
    """
    # Quantification AGRESSIVE du rayon et de l'intensite.
    # Sans elle, des valeurs continues (une braise qui s'eteint, une veine
    # qui pulse) produisent une cle de cache differente a chaque image :
    # on reconstruit alors un degrade complet 60 fois par seconde et par
    # particule, ce qui ecroule le framerate. Le pas est invisible a l'oeil.
    if alpha <= 4:
        return
    radius = max(4, (int(radius) + 3) // 6 * 6)
    alpha = min(255, (int(alpha) + 8) // 20 * 20)
    col = _quant(shade(color, alpha / 255.0), 14)
    if col == (0, 0, 0):
        return
    key = (radius, col)
    g = _GLOW.get(key)
    if g is None:
        g = pygame.Surface((radius * 2, radius * 2))
        g.fill((0, 0, 0))
        steps = max(10, min(40, radius // 2))
        for i in range(steps, 0, -1):
            k = i / steps
            f = (1.0 - k) ** 2.1
            pygame.draw.circle(g, (int(col[0] * f), int(col[1] * f), int(col[2] * f)),
                               (radius, radius), max(1, int(radius * k)))
        _GLOW[key] = g
    surf.blit(g, (int(x - radius), int(y - radius)),
              special_flags=pygame.BLEND_ADD)


_SOFT = {}


def soft_blob(surf, x, y, rx, ry, color, alpha, ang=0.0):
    """Tache douce en alpha classique (masse musculaire, brume, reflet)."""
    # meme logique de quantification que glow() : on borne le nombre de
    # variantes pour que le cache serve reellement a quelque chose
    rx = max(3, (int(rx) + 2) // 5 * 5)
    ry = max(3, (int(ry) + 2) // 5 * 5)
    alpha = max(0, min(255, int(alpha)))
    if alpha <= 3:
        return
    key = (rx, ry, _quant(color, 12), alpha // 16 * 16)
    s = _SOFT.get(key)
    if s is None:
        s = pygame.Surface((rx * 2, ry * 2), pygame.SRCALPHA)
        steps = 16
        for i in range(steps, 0, -1):
            k = i / steps
            a = int(alpha * (1.0 - k) ** 1.5)
            pygame.draw.ellipse(s, (color[0], color[1], color[2], a),
                                (rx * (1 - k), ry * (1 - k),
                                 max(2, rx * 2 * k), max(2, ry * 2 * k)))
        _SOFT[key] = s
    if ang:
        s = pygame.transform.rotate(s, math.degrees(ang))
    surf.blit(s, s.get_rect(center=(int(x), int(y))))


_SHADE_BLOB = {}


def soft_shade(surf, x, y, rx, ry, strength):
    """
    Ombre douce posee en MULTIPLICATION.

    BLEND_MULT ne modifie que les composantes RGB et laisse le canal alpha
    de la destination intact : l'ombre n'apparait donc QUE la ou il y a
    deja de la matiere, et disparait d'elle-meme sur le vide autour du
    personnage. Cela remplace un masque explicite (copie du calque +
    fusion RGBA_MIN), qui etait le poste de rendu le plus couteux.
    """
    rx = max(3, (int(rx) + 4) // 10 * 10)
    ry = max(3, (int(ry) + 4) // 10 * 10)
    s10 = max(1, min(10, int(strength * 10)))
    key = (rx, ry, s10)
    b = _SHADE_BLOB.get(key)
    if b is None:
        b = pygame.Surface((rx * 2, ry * 2))
        b.fill((255, 255, 255))
        steps = 14
        for i in range(steps, 0, -1):
            k = i / steps
            v = int(255 * (1.0 - (s10 / 10.0) * (1.0 - k) ** 1.5))
            pygame.draw.ellipse(b, (v, v, v),
                                (rx * (1 - k), ry * (1 - k),
                                 max(2, rx * 2 * k), max(2, ry * 2 * k)))
        _SHADE_BLOB[key] = b
    surf.blit(b, (int(x - rx), int(y - ry)), special_flags=pygame.BLEND_MULT)


def vgradient(surf, rect, top, bottom, steps=64):
    x, y, w, h = rect
    for i in range(steps):
        c = mix(top, bottom, i / (steps - 1.0))
        pygame.draw.rect(surf, c, (x, y + h * i // steps, w, h // steps + 2))


# ============================================================ PARTICULES ====
class Ember:
    """Braise montante."""
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "r", "col")

    def __init__(self, x, y, spread=30.0):
        self.reset(x, y, spread)

    def reset(self, x, y, spread):
        self.x = x + random.uniform(-spread, spread)
        self.y = y + random.uniform(-8, 8)
        self.vx = random.uniform(-14, 14)
        self.vy = random.uniform(-58, -22)
        self.max_life = random.uniform(1.1, 2.8)
        self.life = self.max_life
        self.r = random.uniform(1.3, 3.2)
        self.col = random.choice((EMBER, FIRE_MID, FIRE_HOT))

    def update(self, dt, t):
        self.life -= dt
        self.x += (self.vx + math.sin(t * 1.7 + self.y * 0.02) * 16) * dt
        self.y += self.vy * dt
        self.vy *= (1.0 - 0.25 * dt)

    def draw(self, surf, halo=False):
        # Un halo par braise coutait ~150 collages additifs par image pour
        # un gain visuel nul a cette taille : seules quelques-unes en ont un.
        k = max(0.0, self.life / self.max_life)
        if halo:
            glow(surf, self.x, self.y, self.r * 6, self.col, int(150 * k))
        pygame.draw.circle(surf, self.col, (int(self.x), int(self.y)),
                           max(1, int(self.r * k)))


class Wisp:
    """
    Ame errante : ruban translucide qui derive vers le haut.

    Le ruban est pre-calcule une fois pour toutes dans un petit sprite
    partage : le dessiner a coups de taches degradees a chaque image
    representait a lui seul une trentaine de gros collages par frame.
    """

    _SPRITES = {}

    @classmethod
    def sprite(cls, size):
        spr = cls._SPRITES.get(size)
        if spr is None:
            w, h = int(size * 1.5), int(size * 4)
            spr = pygame.Surface((w, h), pygame.SRCALPHA)
            for i in range(5):
                k = i / 4.0
                bx = w / 2 + math.sin(k * 2.6) * w * 0.16
                by = h * (0.86 - k * 0.78)
                soft_blob(spr, bx, by, size * 0.52 * (1 - k * 0.55),
                          size * (0.62 + k * 0.42), SPECTRE,
                          int(150 * (1 - k * 0.65)))
            cls._SPRITES[size] = spr
        return spr

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.reset(random.uniform(0, 1))

    def reset(self, prog=0.0):
        self.x = random.uniform(self.w * 0.12, self.w * 0.92)
        self.y = self.h * (0.92 - prog * 0.95)
        self.sp = random.uniform(9, 26)
        self.sz = random.choice((30, 45, 65))    # 3 tailles -> 3 sprites
        self.ph = random.uniform(0, 10)
        self.a = random.uniform(0.30, 0.72)
        self.wob = random.uniform(16, 44)

    def update(self, dt):
        self.y -= self.sp * dt
        if self.y < -self.sz * 4:
            self.reset(0.0)

    def draw(self, surf, t):
        x = self.x + math.sin(t * 0.5 + self.ph) * self.wob
        fade = 1.0
        if self.y > self.h * 0.72:
            fade = max(0.0, (self.h - self.y) / (self.h * 0.28))
        a = int(255 * self.a * fade)
        if a <= 3:
            return
        spr = self.sprite(self.sz)
        spr.set_alpha(a)
        surf.blit(spr, spr.get_rect(midbottom=(int(x), int(self.y))))


class Dust:
    """Poussiere en suspension, tres discrete : donne de la profondeur."""
    __slots__ = ("x", "y", "z", "ph")

    def __init__(self, w, h):
        self.x = random.uniform(0, w)
        self.y = random.uniform(h * 0.25, h)
        self.z = random.uniform(0.3, 1.0)
        self.ph = random.uniform(0, 9)

    def draw(self, surf, t, w, h):
        x = (self.x + math.sin(t * 0.3 + self.ph) * 22 * self.z) % w
        y = self.y - (t * 6 * self.z) % (h * 0.6)
        if y < 0:
            y += h * 0.6
        a = int(50 * self.z)
        pygame.draw.circle(surf, (200, 190, 170, a) if False else
                           mix(NIGHT, WHITE, 0.25 * self.z),
                           (int(x), int(y)), 1)


# ================================================================= FEU ======
def flame(surf, x, y, w, h, t, seed=0.0, intensity=1.0):
    """Flamme procedurale : 3 couches emboitees + halo additif."""
    layers = ((1.00, FIRE_LOW), (0.74, FIRE_MID), (0.42, FIRE_HOT))
    for li, (sc, col) in enumerate(layers):
        pts_l, pts_r = [], []
        n = 11
        for i in range(n + 1):
            v = i / n
            sway = (math.sin(t * 3.1 + seed + v * 4.2) * 0.32
                    + math.sin(t * 6.3 + seed * 1.7 + v * 8.1) * 0.15) * v * w
            hw = (w * 0.5 * sc) * ((1.0 - v) ** 0.62) * \
                 (1.0 + 0.20 * math.sin(t * 9.0 + seed * 3 + v * 12 + li))
            hgt = h * sc * intensity * (1.0 + 0.10 * math.sin(t * 4.4 + seed + li))
            cx = x + sway
            cy = y - v * hgt
            pts_l.append((cx - hw, cy))
            pts_r.append((cx + hw, cy))
        poly(surf, pts_l + pts_r[::-1], col)
    glow(surf, x, y - h * 0.35, w * 2.1 * intensity, FIRE_MID, 130)
    glow(surf, x, y - h * 0.15, w * 1.1 * intensity, FIRE_HOT, 110)


# ============================================================ DECOR =========
class HellGate:
    """
    Le portail des Enfers : mur de pierre, arche a voussoirs, portail
    spectral, braseros, dallage en perspective. La partie fixe est
    pre-calculee une seule fois dans une surface -> cout nul par frame.
    """

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.gx = int(w * 0.635)       # centre du portail
        self.floor_y = int(h * 0.585)  # jonction mur / sol
        self.ground_y = int(h * 0.815) # ligne de sol des personnages
        # Braseros au sol repousses aux extremites : la colonne de gauche
        # est occupee par la jauge de force, on ne la parasite pas.
        self.brazier = [(int(w * -0.005), int(h * 0.775), 1.05),
                        (int(w * 0.985), int(h * 0.720), 0.92)]
        # Torches murales : elles portent l'essentiel de l'eclairage chaud
        # tout en restant hors des zones d'interface.
        self.sconce = [(self.gx - 344, int(h * 0.315)),
                       (self.gx + 344, int(h * 0.315))]
        self.static = None
        self._frame = None
        self._frame_t = -99.0
        self.embers = []
        self.wisps = [Wisp(w, h) for _ in range(9)]
        self.dust = [Dust(w, h) for _ in range(38)]
        self._build()

    # ------------------------------------------------------------ statique --
    def _build(self):
        w, h = self.w, self.h
        s = pygame.Surface((w, h)).convert()
        s.fill(VOID)

        # --- voute / fond : degrade vertical + chaleur au sol ---
        vgradient(s, (0, 0, w, self.floor_y), VOID, NIGHT_WARM)
        # halo froid autour du portail (lueur du passage)
        for r, a in ((520, 26), (380, 30), (250, 34)):
            soft_blob(s, self.gx, int(h * 0.42), r, r * 0.8, SPECTRE_DIM, a)

        self._wall(s)
        self._arch(s)
        self._floor(s)
        for bx, by, sc in self.brazier:
            self._brazier_stone(s, bx, by, sc)
        for sx, sy in self.sconce:
            self._sconce_stone(s, sx, sy)

        # Le vignettage est fixe : on le cuit dans le decor plutot que de
        # recoller un calque plein ecran a chaque image. Bonus : l'interface
        # posee par-dessus n'est plus assombrie sur les bords.
        vignette(s, 0.82)

        self.static = s

    def _sconce_stone(self, s, x, y):
        """Applique murale : console de pierre + coupe, sans le feu."""
        poly(s, [(x - 9, y), (x + 9, y), (x + 16, y + 40), (x - 16, y + 40)],
             mix(STONE, STONE_DARK, 0.3))
        poly(s, [(x - 26, y + 40), (x + 26, y + 40), (x + 20, y + 52),
                 (x - 20, y + 52)], mix(STONE, STONE_DARK, 0.1))
        bowl = [(x - 30, y - 12), (x + 30, y - 12), (x + 20, y + 6),
                (x - 20, y + 6)]
        sculpt(s, bowl, mix(STONE, STONE_WARM, 0.4), edge=shade(STONE_DARK, 0.8))
        pygame.draw.ellipse(s, mix(STONE_WARM, FIRE_LOW, 0.55),
                            (x - 27, y - 17, 54, 11))
        # halo chaud imprime sur le mur, derriere la flamme
        soft_blob(s, x, y - 34, 128, 150, FIRE_LOW, 46)
        soft_blob(s, x, y - 20, 66, 82, FIRE_MID, 34)

    def _wall(self, s):
        """Mur de blocs derriere le portail : appareil irregulier, use."""
        w = self.w
        bh = 52
        y = self.floor_y
        row = 0
        rnd = random.Random(7)
        while y > -bh:
            y -= bh
            off = (row % 2) * 64 + rnd.randint(-10, 10)
            x = -off
            while x < w:
                bw = 124 + rnd.randint(-22, 26)
                # les blocs du haut se perdent dans l'obscurite
                depth = max(0.0, min(1.0, (y + bh) / float(self.floor_y)))
                base = mix(STONE_DARK, STONE, 0.20 + depth * 0.55)
                base = shade(base, 0.68 + rnd.random() * 0.40)
                pygame.draw.rect(s, base, (x + 3, y + 3, bw - 6, bh - 6))
                # arete superieure captant la lumiere, base dans l'ombre
                pygame.draw.line(s, shade(base, 1.45),
                                 (x + 4, y + 4), (x + bw - 7, y + 4), 2)
                pygame.draw.line(s, shade(base, 0.45),
                                 (x + 4, y + bh - 5), (x + bw - 7, y + bh - 5), 3)
                pygame.draw.line(s, shade(base, 0.55),
                                 (x + bw - 6, y + 5), (x + bw - 6, y + bh - 6), 2)
                # usure : eclats et mouchetures
                for _ in range(rnd.randint(1, 4)):
                    ex = rnd.randint(x + 8, max(x + 9, x + bw - 12))
                    ey = rnd.randint(y + 8, y + bh - 12)
                    pygame.draw.circle(s, shade(base, 0.72), (ex, ey),
                                       rnd.randint(2, 6))
                if rnd.random() < 0.22:
                    fx = rnd.randint(x + 10, max(x + 11, x + bw - 14))
                    pygame.draw.line(s, shade(base, 0.6), (fx, y + 6),
                                     (fx + rnd.randint(-10, 10), y + bh - 8), 2)
                x += bw
            row += 1
        # le mur doit rester en retrait : voile sombre degrade vers le haut
        v = pygame.Surface((w, self.floor_y), pygame.SRCALPHA)
        steps = 40
        for i in range(steps):
            a = int(190 * (1.0 - i / (steps - 1.0)) ** 1.4) + 60
            pygame.draw.rect(v, (*VOID, min(235, a)),
                             (0, self.floor_y * i // steps, w,
                              self.floor_y // steps + 2))
        s.blit(v, (0, 0))

    def _arch(self, s):
        """Arche a claveaux + ouverture spectrale."""
        gx = self.gx
        base_y = self.floor_y + 8
        r_in = 152                    # demi-largeur de l'ouverture
        pil_w = 82                    # epaisseur des piliers
        spring = int(self.h * 0.345)  # naissance de l'arc
        r_out = r_in + pil_w

        # --- ouverture : vide + lueur verte profonde ---
        opening = []
        for i in range(41):
            a = math.pi + i * math.pi / 40
            opening.append((gx + math.cos(a) * r_in, spring + math.sin(a) * r_in))
        opening = [(gx - r_in, base_y)] + opening + [(gx + r_in, base_y)]
        poly(s, opening, (5, 8, 8))
        # la lueur du passage reste sourde : un vert franc lit le portail
        # comme un aplat de couleur, pas comme une profondeur
        for k, a in ((1.0, 20), (0.62, 24), (0.32, 30)):
            soft_blob(s, gx, spring + 150, r_in * k, (base_y - spring + 150) * 0.45 * k,
                      shade(SPECTRE_DIM, 0.75), a)
        # rideau de brume verticale dans le passage
        rnd = random.Random(3)
        for i in range(22):
            xx = gx + rnd.uniform(-r_in * 0.92, r_in * 0.92)
            hh = rnd.uniform(90, 300)
            soft_blob(s, xx, base_y - hh * 0.4, 16, hh * 0.5,
                      SPECTRE_DIM, rnd.randint(10, 22))

        # --- piliers en blocs ---
        rnd = random.Random(11)
        for side in (-1, 1):
            # le pilier se pose A L'EXTERIEUR de l'ouverture, jamais dedans
            x0 = gx + side * r_in - (pil_w if side < 0 else 0)
            y = base_y
            while y > spring:
                bh2 = 52
                y -= bh2
                c = mix(STONE, STONE_LIT, rnd.random() * 0.5)
                c = shade(c, 0.62 + rnd.random() * 0.3)
                pygame.draw.rect(s, c, (x0 + 2, y + 2, pil_w - 4, bh2 - 4))
                pygame.draw.line(s, shade(c, 1.4), (x0 + 3, y + 3),
                                 (x0 + pil_w - 5, y + 3), 2)
                # lisere chaud cote brasero
                lx = x0 + 2 if side < 0 else x0 + pil_w - 4
                pygame.draw.line(s, STONE_WARM, (lx, y + 4), (lx, y + bh2 - 6), 3)

        # --- claveaux de l'arc ---
        nvous = 15
        for i in range(nvous):
            a0 = math.pi + i * math.pi / nvous
            a1 = math.pi + (i + 1) * math.pi / nvous
            g = 0.012
            pts = [(gx + math.cos(a0 + g) * r_in, spring + math.sin(a0 + g) * r_in),
                   (gx + math.cos(a1 - g) * r_in, spring + math.sin(a1 - g) * r_in),
                   (gx + math.cos(a1 - g) * r_out, spring + math.sin(a1 - g) * r_out),
                   (gx + math.cos(a0 + g) * r_out, spring + math.sin(a0 + g) * r_out)]
            k = abs(i - (nvous - 1) / 2.0) / (nvous / 2.0)
            c = mix(STONE_LIT, STONE_DARK, 0.25 + k * 0.5)
            c = shade(c, 0.7 + rnd.random() * 0.25)
            poly(s, pts, c)
            pygame.draw.polygon(s, shade(c, 0.5), [(int(a), int(b)) for a, b in pts], 1)

        # --- corniche au sommet ---
        pygame.draw.rect(s, mix(STONE, STONE_DARK, 0.3),
                         (gx - r_out - 22, spring - r_out - 30, (r_out + 22) * 2, 30))
        pygame.draw.rect(s, shade(STONE_LIT, 0.9),
                         (gx - r_out - 22, spring - r_out - 30, (r_out + 22) * 2, 5))

        # --- gravure au fronton (motif geometrique, purement decoratif) ---
        cy = spring - r_out + 2
        for i in range(-3, 4):
            xx = gx + i * 40
            pygame.draw.polygon(s, shade(STONE_LIT, 0.75),
                                [(xx, cy - 44), (xx + 13, cy - 24),
                                 (xx, cy - 6), (xx - 13, cy - 24)], 2)

    def _floor(self, s):
        """Dallage en perspective + flaques reflechissantes."""
        w, h = self.w, self.h
        top, bot = self.floor_y, h
        rows = 9
        rnd = random.Random(23)
        prev = top
        for i in range(rows):
            d0 = (i / rows) ** 1.75
            d1 = ((i + 1) / rows) ** 1.75
            y0 = top + (bot - top) * d0
            y1 = top + (bot - top) * d1
            k = i / (rows - 1.0)
            base = mix(shade(STONE_DARK, 0.75), mix(STONE, STONE_WARM, 0.35), k)
            pygame.draw.rect(s, base, (0, int(y0), w, int(y1 - y0) + 2))
            # joints verticaux, ecartes avec la profondeur
            ncol = max(3, int(14 - i))
            offs = (i % 2) * 0.5
            for c in range(ncol + 1):
                xx = w * ((c + offs) / ncol)
                pygame.draw.line(s, shade(base, 0.62),
                                 (int(xx), int(y0)), (int(xx + (xx - w / 2) * 0.06), int(y1)), 2)
            pygame.draw.line(s, shade(base, 0.55), (0, int(y0)), (w, int(y0)), 2)
            pygame.draw.line(s, shade(base, 1.25), (0, int(y0) + 2), (w, int(y0) + 2), 1)
            # eclats / fissures
            for _ in range(3):
                fx = rnd.randint(0, w)
                pygame.draw.line(s, shade(base, 0.7), (fx, int(y0) + 4),
                                 (fx + rnd.randint(-26, 26), int(y1) - 4), 1)
            prev = y1
        # brume rasante au sol
        for i in range(7):
            soft_blob(s, rnd.randint(0, w), top + rnd.randint(6, 40),
                      rnd.randint(180, 320), rnd.randint(18, 34),
                      SPECTRE_DIM, rnd.randint(8, 16))

    def _brazier_stone(self, s, x, y, sc):
        """Vasque de pierre (partie fixe ; le feu est anime par-dessus)."""
        w = 74 * sc
        # pied
        poly(s, [(x - 16 * sc, y), (x + 16 * sc, y),
                 (x + 26 * sc, y + 56 * sc), (x - 26 * sc, y + 56 * sc)],
             mix(STONE, STONE_DARK, 0.35))
        poly(s, [(x - 34 * sc, y + 56 * sc), (x + 34 * sc, y + 56 * sc),
                 (x + 42 * sc, y + 72 * sc), (x - 42 * sc, y + 72 * sc)],
             mix(STONE, STONE_DARK, 0.15))
        # vasque
        bowl = [(x - w, y - 14 * sc), (x + w, y - 14 * sc),
                (x + w * 0.62, y + 16 * sc), (x - w * 0.62, y + 16 * sc)]
        sculpt(s, bowl, mix(STONE, STONE_WARM, 0.35),
               rim=None, under=None, edge=shade(STONE_DARK, 0.8), ew=2)
        pygame.draw.ellipse(s, shade(STONE_DARK, 0.7),
                            (x - w, y - 22 * sc, w * 2, 18 * sc))
        pygame.draw.ellipse(s, mix(STONE_WARM, FIRE_LOW, 0.5),
                            (x - w * 0.86, y - 19 * sc, w * 1.72, 13 * sc))
        # charbons
        rnd = random.Random(int(x))
        for _ in range(9):
            cx = x + rnd.uniform(-w * 0.7, w * 0.7)
            pygame.draw.circle(s, mix(FIRE_LOW, INK, rnd.random() * 0.6),
                               (int(cx), int(y - 14 * sc)), int(rnd.uniform(3, 7) * sc))

    # ------------------------------------------------------------- anime ----
    def update(self, dt, t):
        for bx, by, sc in self.brazier:
            if random.random() < dt * 26 * sc:
                self.embers.append(Ember(bx, by - 26 * sc, 26 * sc))
        for sx, sy in self.sconce:
            if random.random() < dt * 14:
                self.embers.append(Ember(sx, sy - 18, 14))
        for e in self.embers:
            e.update(dt, t)
        self.embers = [e for e in self.embers if e.life > 0][-80:]
        for wsp in self.wisps:
            wsp.update(dt)

    FRAME_RATE = 1.0 / 30.0

    def draw(self, surf, t, shake=(0, 0)):
        """
        Le decor anime (feu, ames, braises) est compose dans une image
        intermediaire rafraichie a 30 ips, puis simplement recollee. Un
        brasier n'a aucun besoin de 60 images par seconde, et cela divise
        par deux le cout du poste le plus lourd du rendu. Le tremblement
        d'ecran reste fluide : c'est un decalage au collage, pas un redessin.
        """
        if self._frame is None:
            self._frame = pygame.Surface((self.w, self.h)).convert()
            self._frame_t = -99.0
        if abs(t - self._frame_t) >= self.FRAME_RATE:
            self._frame_t = t
            self._paint(self._frame, t)
        surf.blit(self._frame, shake)

    def _paint(self, surf, t):
        shake = (0, 0)
        surf.blit(self.static, shake)
        # portail : pulsation spectrale
        pulse = 0.5 + 0.5 * math.sin(t * 0.9)
        glow(surf, self.gx + shake[0], int(self.h * 0.40) + shake[1],
             int(210 + 30 * pulse), SPECTRE_DIM, int(46 + 18 * pulse))
        # ames
        for wsp in self.wisps:
            wsp.draw(surf, t)
        # feu des torches murales
        for i, (sx, sy) in enumerate(self.sconce):
            inten = 1.0 + 0.12 * math.sin(t * 6.1 + i * 1.7)
            flame(surf, sx + shake[0], sy - 8, 44, 82, t,
                  seed=7.3 + i * 2.9, intensity=inten)

        # feu des braseros
        for i, (bx, by, sc) in enumerate(self.brazier):
            inten = 1.0 + 0.09 * math.sin(t * 5.0 + i * 2.1)
            flame(surf, bx + shake[0], by - 16 * sc, 78 * sc, 128 * sc,
                  t, seed=i * 3.7, intensity=inten * sc)
            # reflet au sol
            soft_blob(surf, bx + shake[0], by + 96 * sc, 92 * sc, 34 * sc,
                      FIRE_MID, int(40 + 14 * math.sin(t * 4 + i)))
        for i, e in enumerate(self.embers):
            e.draw(surf, halo=(i % 4 == 0))
        for d in self.dust:
            d.draw(surf, t, self.w, self.h)


# ============================================================== CERBERE =====
class SpriteCache:
    """
    Cadence d'animation des personnages.

    Un jeu de combat 2D n'anime pas ses persos a 60 images par seconde : les
    poses sont tenues sur plusieurs images et seule la POSITION bouge en
    continu. On reproduit ca ici, et ca resout du meme coup le probleme de
    cout : recomposer un sprite (calque + silhouette + contour) est cher, on
    ne le fait que ~24 fois par seconde, alors que le deplacement, lui,
    reste parfaitement fluide puisque c'est un simple decalage de collage.
    """

    RATE = 1.0 / 18.0

    def __init__(self):
        self.spr = None
        self.margin = 0
        self.t = -99.0
        self.key = None

    def stale(self, t, key):
        return (self.spr is None or key != self.key
                or abs(t - self.t) >= self.RATE)

    def store(self, spr, margin, t, key):
        self.spr, self.margin, self.t, self.key = spr, margin, t, key


class Cerberus:
    """
    Le gardien des Enfers - geometrie entierement originale.

    Construction : un squelette de points nommes, des masses dessinees le
    long de ce squelette, puis un contour unifie. Le personnage est peint
    dans un calque a part pour pouvoir lui appliquer ce contour et un
    eclairage global, comme on le ferait sur un sprite peint.

    Il regarde toujours vers la gauche (Hercule lui fait face).

    Parametres d'animation :
      aggro   0..1  tetes basses, criniere herissee, gueules ouvertes
      strain  0..1  il resiste : muscles bandes, pattes qui derapent
      jaws    0..1  ouverture des machoires
    """

    LW, LH = 800, 580          # dimensions du calque
    OX, OY = 400, 520          # origine locale (sol sous le poitrail)

    # --- tronc ---
    # Le ventre est haut (garde au sol ~40 % de la hauteur au garrot) :
    # un ventre bas transforme le molosse en hippopotame.
    BODY = [(-108, -200), (-92, -232), (-58, -246), (-6, -240), (52, -230),
            (110, -218), (158, -200), (188, -166), (192, -130), (168, -108),
            (122, -104), (56, -100), (-16, -98), (-70, -100), (-108, -120),
            (-126, -160)]
    SHOULDER = [(-130, -124), (-136, -176), (-114, -220), (-66, -234),
                (-28, -208), (-26, -150), (-56, -110), (-104, -102)]
    HAUNCH = [(96, -96), (88, -146), (116, -196), (172, -212), (208, -176),
              (212, -120), (188, -84), (140, -70), (104, -72)]
    CHEST = [(-124, -104), (-132, -152), (-108, -192), (-70, -192),
             (-56, -146), (-70, -100), (-104, -88)]

    # --- tete (museau vers -x, charniere de machoire en (32, 2)) ---
    # Museau long et carre, arcade lourde, oreilles pointues rabattues :
    # on cherche le molosse, pas l'ours.
    SKULL = [(38, -4), (46, -34), (30, -60), (-4, -70), (-40, -66),
             (-74, -56), (-104, -42), (-126, -26), (-116, -8), (-80, -4),
             (-38, -2), (2, -2), (26, 2)]
    LIP_UP = [(-116, -8), (-80, -4), (-38, -2), (2, -2), (26, 2)]
    JAW = [(-112, -6), (-80, 8), (-38, 18), (2, 20), (26, 16),
           (34, 30), (0, 38), (-46, 34), (-88, 22), (-112, 8)]
    JAW_TOP = [(-112, -6), (-80, 8), (-38, 18), (2, 20), (26, 16)]
    EAR = [(18, -54), (38, -96), (72, -88), (68, -46), (34, -34)]
    BROW = [(-6, -66), (-54, -62), (-68, -42), (-14, -48)]
    HINGE = (32, 2)

    def __init__(self):
        self._layer = pygame.Surface((self.LW, self.LH), pygame.SRCALPHA).convert_alpha()
        self._eyes = []      # positions locales des yeux, pour le halo hors calque
        self._cache = SpriteCache()

    # -------------------------------------------------------------- outils --
    @staticmethod
    def _rot(pts, ang, pivot):
        ca, sa = math.cos(ang), math.sin(ang)
        px, py = pivot
        return [(px + (x - px) * ca - (y - py) * sa,
                 py + (x - px) * sa + (y - py) * ca) for x, y in pts]

    def _paw(self, L, x, y, s, base, rim, toes=3):
        pad = [(x - 30 * s, y - 20 * s), (x + 20 * s, y - 24 * s),
               (x + 30 * s, y - 4 * s), (x + 24 * s, y + 8 * s),
               (x - 32 * s, y + 8 * s), (x - 38 * s, y - 6 * s)]
        sculpt(L, smooth(pad, 4), base, rim=rim, rim_off=(2, -3))
        for i in range(toes):
            tx = x + (-22 + i * 20) * s
            pygame.draw.circle(L, shade(base, 1.22), (int(tx), int(y + 2 * s)),
                               max(2, int(9 * s)))
            # griffe courte et recourbee (une griffe longue fait defense)
            poly(L, smooth([(tx - 5 * s, y + 7 * s), (tx + 4 * s, y + 7 * s),
                            (tx - 2 * s, y + 15 * s), (tx - 8 * s, y + 12 * s)], 3),
                 CLAW)

    def _limb(self, L, joints, widths, s, base, rim, dx=0.0):
        j = [(a + dx, b) for a, b in joints]
        pts = tform(tapered(j, widths), self.OX, self.OY, 0.0, s)
        sculpt(L, pts, base, rim=rim, under=shade(base, 1.45),
               rim_off=(3, -3), under_off=(-3, 3))
        return tform([j[-1]], self.OX, self.OY, 0.0, s)[0]

    # ---------------------------------------------------------------- tete --
    def head(self, L, x, y, ang, s, jaw, tone, rim, eye=1.0, detail=1.0):
        def T(pts):
            return tform(pts, x, y, ang, s)

        jang = jaw * 0.62
        jaw_r = self._rot(self.JAW, jang, self.HINGE)
        jaw_top_r = self._rot(self.JAW_TOP, jang, self.HINGE)

        # oreilles pointues rabattues (peu de lissage : elles doivent rester
        # anguleuses, un lissage fort les arrondit en oreilles d'ourson)
        for k, off in ((0.82, (16, -4)), (1.0, (0, 0))):
            ear = [(px * k + off[0], py * k + off[1]) for px, py in self.EAR]
            sculpt(L, T(smooth(ear, 2)), shade(tone, 0.6 if k < 0.9 else 0.76),
                   rim=rim, rim_off=(2, -2))
            # conque : retrecie autour du barycentre pour rester DANS l'oreille
            cx = sum(p[0] for p in ear) / len(ear)
            cy = sum(p[1] for p in ear) / len(ear)
            inner = [(cx + (px - cx) * 0.5, cy + (py - cy) * 0.5) for px, py in ear]
            poly(L, T(smooth(inner, 3)), shade(MAW, 0.38))

        # interieur de la gueule
        if jaw > 0.05:
            maw = self.LIP_UP + jaw_top_r[::-1]
            poly(L, T(maw), MAW)
            tongue = [(-52, 4), (-8, 8), (14, 12)]
            tongue = tongue + self._rot([(12, 14), (-14, 22), (-54, 14)],
                                        jang, self.HINGE)
            poly(L, T(tongue), shade(BLOOD, 0.8))

        # machoire inferieure + crocs du bas
        sculpt(L, T(smooth(jaw_r, 3)), shade(tone, 0.88), rim=rim, rim_off=(2, -2))
        for bx, by, sz in ((-96, 5, 17), (-70, 10, 10), (-46, 14, 9),
                           (-22, 17, 12), (-2, 18, 8)):
            fx, fy = self._rot([(bx, by)], jang, self.HINGE)[0]
            poly(L, T([(fx - sz * 0.42, fy + 3), (fx + sz * 0.42, fy + 3),
                       (fx - sz * 0.1, fy - sz)]), TOOTH)

        # crane
        sculpt(L, T(smooth(self.SKULL, 4)), tone, rim=rim,
               under=shade(tone, 1.5), rim_off=(2, -3), under_off=(-3, 3))
        # chanfrein eclaire (le dessus du museau capte la lumiere)
        soft_blob(L, *T([(-74, -44)])[0], 44 * s, 11 * s, shade(tone, 1.55), 78, ang)
        # arcade sourciliere lourde
        poly(L, T(self.BROW), shade(tone, 1.28))
        poly(L, T([(-6, -66), (-54, -62), (-56, -54), (-10, -58)]),
             shade(tone, 0.62))
        # crocs superieurs : deux canines dominantes + molaires,
        # jamais une rangee reguliere (ca fait peigne)
        for bx, sz in ((-104, 21), (-78, 12), (-56, 10), (-34, 14), (-14, 9)):
            sz *= (0.55 + 0.45 * jaw)
            poly(L, T([(bx - sz * 0.42, -6), (bx + sz * 0.42, -6),
                       (bx - sz * 0.12, sz)]), TOOTH)
            poly(L, T([(bx - sz * 0.42, -6), (bx - sz * 0.08, -6),
                       (bx - sz * 0.12, sz)]), shade(TOOTH, 0.78))
        # truffe
        poly(L, T(smooth([(-130, -30), (-116, -44), (-100, -32), (-114, -20)], 3)),
             shade(tone, 0.42))
        # plis du grognement
        if detail > 0.5:
            for i in range(3):
                pts = T([(-90 + i * 15, -46 - i * 3), (-72 + i * 15, -54 - i * 3),
                         (-52 + i * 15, -52 - i * 3)])
                pygame.draw.aalines(L, shade(tone, 1.5), False,
                                    [(int(a), int(b)) for a, b in pts])

        # oeil : braise
        ex, ey = T([(-46, -46)])[0]
        self._eyes.append((ex, ey, eye))
        er = max(2.0, 7.5 * s)
        glow(L, ex, ey, er * 6 * eye, EYE_HOT, int(200 * eye))
        pygame.draw.circle(L, EYE_HOT, (int(ex), int(ey)), int(er))
        pygame.draw.circle(L, EYE_CORE, (int(ex - er * 0.25), int(ey - er * 0.3)),
                           max(1, int(er * 0.45)))
        # lisere froid sur la ligne de crete du crane
        top = T([(34, -48), (28, -62), (-6, -72), (-44, -68), (-78, -58),
                 (-108, -44), (-128, -26)])
        pygame.draw.lines(L, rim, False, [(int(a), int(b)) for a, b in top],
                          max(1, int(2 * s)))

    # -------------------------------------------------------------- dessin --
    def draw(self, surf, x, y, s=1.0, t=0.0, aggro=0.6, strain=0.0, jaws=0.5):
        """(x, y) = point au sol sous le poitrail ; s = echelle."""
        key = (round(s, 2), round(aggro, 1), round(strain, 1), round(jaws, 1))
        if self._cache.stale(t, key):
            self._bake(t, s, aggro, strain, jaws)
            self._cache.store(self._spr, self._m, t, key)

        soft_blob(surf, x + 24 * s, y + 6 * s, 230 * s, 34 * s, INK, 170)
        spr, m = self._cache.spr, self._cache.margin
        surf.blit(spr, (int(x - self.OX * s - m), int(y - self.OY * s - m)))
        # les yeux debordent dans la scene : halo peint hors du sprite
        for ex, ey, k in self._eyes:
            glow(surf, x + (ex - self.OX) * s, y + (ey - self.OY) * s,
                 46 * s * k, EYE_HOT, int(120 * k))

    def _bake(self, t, s, aggro, strain, jaws):
        L = self._layer
        L.fill((0, 0, 0, 0))
        OX, OY = self.OX, self.OY
        rnd = random.Random(1789)
        self._eyes = []

        breath = math.sin(t * 2.1) * 4.0
        far = shade(BEAST_DARK, 1.15)
        mid = BEAST
        near = BEAST_MID
        rim = RIM_COLD
        rim_far = RIM_SOFT
        slip = strain * 18

        def T(pts, off=(0, 0)):
            return tform([(a + off[0], b + off[1]) for a, b in pts], OX, OY, 0.0, 1.0)

        # ---- queue-serpent (plan le plus lointain) ----
        wig = math.sin(t * 1.9)
        tail_j = [(172, -190), (244, -232), (292, -304), (262, -374), (198, -400)]
        tail_j = [(a + i * wig * 5, b + math.sin(t * 2.3 + i * 0.8) * 6)
                  for i, (a, b) in enumerate(tail_j)]
        tail_w = [36, 28, 21, 15, 11]
        sculpt(L, T(tapered(tail_j, tail_w)), shade(mid, 0.88),
               rim=rim_far, rim_off=(3, -3))
        # ecailles ventrales : arcs suivant la courbe, pas des ronds
        for i in range(16):
            u = (i + 0.5) / 16
            k = u * (len(tail_j) - 1)
            i0 = min(len(tail_j) - 2, int(k))
            f = k - i0
            px = lerp(tail_j[i0][0], tail_j[i0 + 1][0], f)
            py = lerp(tail_j[i0][1], tail_j[i0 + 1][1], f)
            dx = tail_j[i0 + 1][0] - tail_j[i0][0]
            dy = tail_j[i0 + 1][1] - tail_j[i0][1]
            ang = math.atan2(dy, dx)
            wdt = lerp(tail_w[i0], tail_w[i0 + 1], f) * 0.82
            arc = [(px + math.cos(ang + 1.57) * wdt, py + math.sin(ang + 1.57) * wdt),
                   (px + math.cos(ang) * wdt * 0.5, py + math.sin(ang) * wdt * 0.5),
                   (px - math.cos(ang + 1.57) * wdt, py - math.sin(ang + 1.57) * wdt)]
            pygame.draw.lines(L, shade(mid, 1.22), False,
                              [(int(OX + a), int(OY + b)) for a, b in arc], 2)
        thx, thy = OX + tail_j[-1][0], OY + tail_j[-1][1]
        sn = [(10, -8), (-16, -24), (-52, -20), (-64, -4), (-48, 10), (-14, 16),
              (10, 10)]
        sculpt(L, [(thx + a, thy + b) for a, b in smooth(sn, 4)],
               shade(mid, 1.0), rim=rim_far, rim_off=(2, -3))
        glow(L, thx - 34, thy - 10, 16, EYE_HOT, 180)
        pygame.draw.circle(L, EYE_HOT, (int(thx - 34), int(thy - 10)), 4)
        if math.sin(t * 3.3) > 0.2:
            pygame.draw.lines(L, BLOOD, False,
                              [(int(thx - 64), int(thy - 6)),
                               (int(thx - 88), int(thy - 14))], 3)
            pygame.draw.lines(L, BLOOD, False,
                              [(int(thx - 64), int(thy - 6)),
                               (int(thx - 86), int(thy + 2))], 3)

        # ---- pattes du fond (anterieur droit / posterieur en Z) ----
        p = self._limb(L, [(-64, -206), (-88, -140), (-104, -70), (-116, -16)],
                       [30, 20, 14, 12], 1.0, far, rim_far, dx=-slip * 0.5)
        self._paw(L, p[0], p[1], 0.86, far, rim_far)
        p = self._limb(L, [(118, -198), (162, -136), (126, -72), (152, -16)],
                       [34, 23, 15, 13], 1.0, far, rim_far)
        self._paw(L, p[0], p[1], 0.88, far, rim_far)

        # ---- tronc ----
        # Le rebond chaud reste discret : trop marque, il se lit comme un
        # bandeau orange colle sous le ventre au lieu d'une lumiere reflechie.
        bounce = shade(BEAST_WARM, 0.62)
        body = [(a, b + breath * 0.4) for a, b in self.BODY]
        sculpt(L, T(smooth(body, 5)), mid, rim=rim, under=bounce,
               rim_off=(3, -4), under_off=(-3, 4))
        sculpt(L, T(smooth(self.HAUNCH, 5)), shade(mid, 1.10), rim=rim,
               under=shade(bounce, 0.85), rim_off=(3, -4), under_off=(-2, 3))
        sculpt(L, T(smooth(self.SHOULDER, 5)), shade(mid, 1.18), rim=rim,
               under=bounce, rim_off=(3, -4), under_off=(-2, 3))
        sculpt(L, T(smooth(self.CHEST, 5)), shade(mid, 1.04), under=bounce,
               under_off=(-2, 3))

        # ---- volumes musculaires ----
        for lx, ly, rx, ry, k, a in ((-92, -160, 34, 44, 1.55, 110),
                                     (156, -150, 38, 46, 1.5, 110),
                                     (24, -206, 68, 20, 1.35, 100),
                                     (10, -84, 74, 18, 0.68, 130),
                                     (-84, -104, 30, 26, 0.72, 110)):
            soft_blob(L, OX + lx, OY + ly, rx, ry, shade(mid, k), a)
        if strain > 0.15:
            for i in range(4):
                soft_blob(L, OX - 4 + i * 28, OY - 130, 8, 36,
                          shade(mid, 0.6), int(130 * strain))

        # ---- texture de fourrure (graine fixe : stable dans le temps) ----
        # echantillonnage dans une ellipse qui epouse le tronc, sinon les
        # poils debordent sur le vide autour de la silhouette
        ecx, ecy, erx, ery = 34, -168, 172, 74
        for _ in range(220):
            u, v = rnd.uniform(-1, 1), rnd.uniform(-1, 1)
            if u * u + v * v > 1.0:
                continue
            fx, fy = ecx + u * erx, ecy + v * ery
            ln = rnd.uniform(8, 22)
            # les poils suivent la retombee du flanc : plus obliques en bas
            ang = -0.45 + v * 0.55 + rnd.uniform(-0.18, 0.18)
            c = shade(mid, 1.45 if rnd.random() < 0.4 else 0.66)
            pygame.draw.line(L, c, (int(OX + fx), int(OY + fy)),
                             (int(OX + fx + math.cos(ang) * ln),
                              int(OY + fy + math.sin(ang) * ln)), 2)

        # ---- veines de braise sous le pelage ----
        # Signature du personnage : la creature n'est pas seulement sombre,
        # elle couve. Les veines pulsent avec l'agressivite.
        pulse = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(t * 2.6)) * (0.4 + 0.6 * aggro)
        veins = [[(-96, -206), (-64, -190), (-30, -184), (6, -190)],
                 [(-70, -160), (-34, -150), (4, -152)],
                 [(60, -206), (96, -196), (130, -186)],
                 [(96, -140), (132, -132), (162, -138)]]
        for vpath in veins:
            pts = [(int(OX + a), int(OY + b)) for a, b in smooth(vpath, 5, False)]
            # la braise couve SOUS le poil : elle reste sourde, seul un
            # coeur tres fin est franchement chaud
            pygame.draw.lines(L, mix(BEAST, FIRE_LOW, 0.42 * pulse), False, pts, 4)
            pygame.draw.lines(L, mix(BEAST, FIRE_LOW, 0.85 * pulse), False, pts, 2)
            for px, py in pts[::7]:
                glow(L, px, py, 13, FIRE_LOW, int(60 * pulse))

        # ---- crete de poils herisses le long de l'echine ----
        # Un seul contour ondule irregulier, pas une file de triangles :
        # des pics reguliers donnent immanquablement un dos de stegosaure.
        spine = [(-74, -248), (-52, -250), (-30, -246), (-6, -242), (18, -238),
                 (44, -234), (72, -228), (100, -220), (128, -212), (152, -202)]
        crest = random.Random(4242)
        top = []
        for i, (px, py) in enumerate(spine):
            fade = (1.0 - i / (len(spine) - 1.0)) ** 0.9
            hgt = (8 + 26 * fade) * (0.55 + 0.65 * aggro) * crest.uniform(0.6, 1.35)
            top.append((px - hgt * 0.22, py - hgt))
        ridge = smooth(top + spine[::-1], 4)
        poly(L, T(ridge), shade(mid, 0.72))
        pygame.draw.lines(L, rim_far, False,
                          [(int(a), int(b)) for a, b in T(smooth(top, 4))], 2)

        # ---- pattes du premier plan ----
        p = self._limb(L, [(152, -206), (200, -140), (158, -72), (190, -12)],
                       [38, 26, 17, 15], 1.0, near, rim)
        self._paw(L, p[0], p[1], 1.0, near, rim)
        p = self._limb(L, [(-98, -218), (-130, -150), (-152, -78), (-168, -12)],
                       [36, 24, 16, 14], 1.0, near, rim, dx=-slip)
        self._paw(L, p[0], p[1], 0.96, near, rim)
        if strain > 0.25:
            for i in range(3):
                sx = p[0] + 34 + i * 26
                pygame.draw.line(L, shade(STONE_DARK, 1.6),
                                 (int(sx), int(p[1] + 8)),
                                 (int(sx + 42), int(p[1] + 11)), 3)

        # ---- collier de fer ----
        col = T([(-118, -196), (-72, -222), (-44, -206), (-92, -178)])
        sculpt(L, col, shade(BRONZE, 0.45), rim=BRONZE, rim_off=(2, -3))
        for i in range(3):
            cx2, cy2 = OX - 106 + i * 26, OY - 196 - i * 9
            poly(L, [(cx2, cy2 - 10), (cx2 + 8, cy2), (cx2, cy2 + 10),
                     (cx2 - 8, cy2)], BRONZE)

        # ---- COUS + TETES : du plan lointain au plan proche ----
        # Convention d'angle : POSITIF = museau vers le haut (le museau est
        # sur -x, donc y' = x*sin(a) devient negatif quand a est positif).
        hs = 0.92
        heads = [
            # cou, largeurs, angle tete, teinte, mult. ouverture, plan
            # 1) tete du fond, dressee, hurlant vers le ciel
            ([(-62, -234), (-48, -304), (-14, -356)], [40, 30, 22],
             0.98 + math.sin(t * 2.0 + 1.9) * 0.05, shade(far, 1.35), 0.6, 0.5),
            # 2) tete centrale, la plus haute et la plus large
            ([(-94, -230), (-142, -286), (-186, -306)], [48, 38, 28],
             0.30 + math.sin(t * 2.4) * 0.05 + aggro * 0.10, mid, 1.0, 1.0),
            # 3) tete proche, basse, projetee en avant : celle qui mord
            ([(-106, -214), (-160, -234), (-216, -242)], [44, 35, 25],
             -0.24 + math.sin(t * 2.7 + 3.4) * 0.05 - aggro * 0.16,
             shade(near, 1.05), 0.9, 1.0),
        ]
        for joints, widths, hang, tone, jk, det in heads:
            npts = T(tapered(joints, widths))
            sculpt(L, npts, tone, rim=rim if det > 0.8 else rim_far,
                   under=shade(BEAST_WARM, 0.95 if det > 0.8 else 0.5),
                   rim_off=(3, -4), under_off=(-3, 4))
            # criniere : lobes arrondis superposes plutot que des pics
            # (des triangles reguliers donnent une lame de scie)
            mane = random.Random(int(joints[0][1]))
            for i in range(9):
                u = (i + 0.35) / 9
                k = u * (len(joints) - 1)
                i0 = min(len(joints) - 2, int(k))
                mx = lerp(joints[i0][0], joints[i0 + 1][0], k - i0)
                my = lerp(joints[i0][1], joints[i0 + 1][1], k - i0)
                sp = (16 + 11 * aggro) * (1.05 - abs(u - 0.4)) * mane.uniform(0.6, 1.4)
                wd = mane.uniform(13, 22)
                tip = mane.uniform(-9, 7)
                lobe = smooth([(mx - wd, my + 11), (mx - wd * 0.5, my - sp * 0.55),
                               (mx + tip, my - sp), (mx + wd * 0.8, my - sp * 0.4),
                               (mx + wd, my + 9)], 3)
                poly(L, T(lobe), shade(tone, mane.uniform(0.52, 0.78)))
            hx2, hy2 = OX + joints[-1][0], OY + joints[-1][1]
            self.head(L, hx2, hy2, hang, hs, jaws * jk, tone,
                      rim if det > 0.8 else rim_far, eye=det, detail=det)

        # ---- souffle brulant ----
        for joints, widths, hang, tone, jk, det in heads:
            if jaws * jk < 0.35:
                continue
            hx2, hy2 = OX + joints[-1][0], OY + joints[-1][1]
            for i in range(3):
                k = (t * 0.85 + i * 0.33) % 1.0
                soft_blob(L, hx2 - 100 - k * 90, hy2 - 10 - k * 30,
                          18 + k * 34, 13 + k * 26, FIRE_LOW,
                          int(70 * (1 - k) * jaws * jk))

        # ---- passe d'eclairage globale, DECOUPEE sur la silhouette ----
        # C'est elle qui donne le contraste de valeurs : le haut du dos part
        # dans l'ombre, le poitrail et les pattes avant recoivent les braseros.
        # Sans decoupe, ces taches deborderaient en halos flottants autour du
        # personnage ; on les masque donc par l'alpha du calque.
        for bx, by, rx, ry, k in ((40, -252, 240, 96, 0.55), (210, -176, 130, 124, 0.4),
                                  (-60, -300, 150, 80, 0.3)):
            soft_shade(L, OX + bx, OY + by, rx, ry, k)
        for bx, by, r, a in ((-150, -110, 130, 62), (-196, -246, 96, 42)):
            glow(L, OX + bx, OY + by, r, BEAST_WARM, a)

        self._spr, self._m = compose_sprite(L, s, width=max(3, int(5 * s)),
                                            color=INK, ring=5)


CLAW = (214, 204, 184)


# ============================================================= HERCULE ======
PELT_COL = (156, 102, 44)
# Volontairement tres sombre : le heros se lit a contre-jour par ses
# liseres, pas par sa couleur propre. Un ton moyen le rend gris et plat.
SKIN_TONE = (40, 28, 28)


class Hercules:
    """
    Le heros, de trois quarts dos, arc-boute dans un bras de fer contre la
    bete. Il regarde vers +x (Cerbere est a sa droite).

    Rendu a contre-jour : masses sombres, lisere chaud du brasero a sa
    gauche, lisere froid du portail a sa droite. La depouille de lion est
    un attribut mythologique generique (domaine public) ; sa forme ici est
    dessinee de zero.

    draw() renvoie la position des mains : c'est le point d'accroche de la
    chaine.
    """

    LW, LH = 460, 400
    OX, OY = 200, 350       # origine : le sol, entre les deux pieds

    TORSO = [(-44, -150), (8, -156), (18, -202), (6, -244), (-44, -254),
             (-72, -238), (-66, -192), (-54, -156)]
    CAPE = [(-62, -246), (-88, -218), (-94, -176), (-80, -150), (-62, -172),
            (-54, -206), (-52, -236)]

    def __init__(self):
        self._layer = pygame.Surface((self.LW, self.LH), pygame.SRCALPHA).convert_alpha()
        self._cache = SpriteCache()
        self._grip = (0.0, 0.0)

    def draw(self, surf, x, y, s=1.0, t=0.0, pull=0.0):
        # La traction est quantifiee plus finement que le reste : c'est le
        # parametre que le joueur pilote, sa reponse doit rester lisible.
        key = (round(s, 2), round(pull, 2))
        if self._cache.stale(t, key):
            self._bake(t, s, pull)
            self._cache.store(self._spr, self._m, t, key)

        soft_blob(surf, x - 8 * s, y + 4 * s, 118 * s, 22 * s, INK, 165)
        spr, m = self._cache.spr, self._cache.margin
        surf.blit(spr, (int(x - self.OX * s - m), int(y - self.OY * s - m)))
        gx, gy = self._grip
        return (x + (gx - self.OX) * s, y + (gy - self.OY) * s)

    def _bake(self, t, s, pull):
        L = self._layer
        L.fill((0, 0, 0, 0))
        OX, OY = self.OX, self.OY
        breath = math.sin(t * 2.4) * 2.2
        # plus il tire, plus il bascule en arriere et plie la jambe avant
        k = pull
        base = SKIN_TONE
        dark = shade(base, 0.72)
        warm = (222, 126, 56)      # brasero, a sa gauche
        cold = RIM_COLD            # portail, dans son dos a droite

        def T(pts):
            return [(OX + a, OY + b + breath * 0.25) for a, b in pts]

        def LEAN(pts, amount=1.0):
            """Bascule du buste : plus c'est haut, plus c'est recule."""
            return [(a + (-0.16 - k * 0.20) * b * amount, b) for a, b in pts]

        # Hierarchie de valeurs par plan : sans ecart net entre membre
        # arriere et membre avant, tout fusionne en une masse noire unique.
        far_tone = shade(base, 0.58)
        near_tone = shade(base, 1.42)

        # ---------- jambe arriere, tendue loin derriere (l'ancrage) ----------
        rear = [(-30, -152), (-62, -96), (-84, -40), (-92, -12)]
        sculpt(L, T(tapered(rear, [32, 23, 15, 12])), far_tone,
               rim=shade(warm, 0.6), rim_off=(-3, -3))
        poly(L, T(smooth([(-114, -16), (-80, -20), (-72, -2), (-118, 0)], 3)),
             far_tone)

        # ---------- jambe avant, pliee, qui encaisse ----------
        fx = 8 + k * 16
        front = [(6, -154), (44 + k * 10, -96), (46 + k * 14, -34), (58 + fx, -12)]
        sculpt(L, T(tapered(front, [36, 26, 17, 13])), near_tone,
               rim=cold, rim_off=(4, -4), under=shade(base, 1.9), under_off=(-3, 3))
        poly(L, T(smooth([(40 + fx, -16), (78 + fx, -20), (86 + fx, -2),
                          (36 + fx, 0)], 3)), near_tone)
        # cuisse avant : masse eclairee qui detache la jambe du buste
        soft_blob(L, *T([(24 + k * 6, -122)])[0], 30, 40, shade(base, 2.1), 110)

        # ---------- buste ----------
        torso = LEAN(self.TORSO)
        sculpt(L, T(smooth(torso, 5)), base, rim=cold, rim_off=(5, -5),
               under=shade(base, 1.45), under_off=(-4, 4))
        # dorsaux / omoplates suggeres par des masses douces
        for bx, by, rx, ry, kk in ((-30, -226, 26, 18, 1.5), (-6, -216, 20, 14, 1.35),
                                   (-40, -180, 22, 20, 0.72), (0, -172, 18, 14, 1.25)):
            px, py = T(LEAN([(bx, by)]))[0]
            soft_blob(L, px, py, rx, ry, shade(base, kk), 105)
        # colonne
        pts = T(LEAN([(-34, -244), (-30, -206), (-26, -168), (-30, -152)]))
        pygame.draw.lines(L, shade(base, 0.6), False,
                          [(int(a), int(b)) for a, b in pts], 4)

        # ---------- depouille de lion : cape dans le dos ----------
        cape = LEAN(self.CAPE)
        sculpt(L, T(smooth(cape, 4)), shade(PELT_COL, 0.22),
               rim=shade(PELT_COL, 0.7), rim_off=(-3, -3))
        for i in range(5):
            u = i / 4.0
            p0 = T(LEAN([(-62 - u * 22, -238 + u * 78)]))[0]
            p1 = T(LEAN([(-54 - u * 16, -228 + u * 76)]))[0]
            pygame.draw.line(L, shade(PELT_COL, 0.48), (int(p0[0]), int(p0[1])),
                             (int(p1[0]), int(p1[1])), 4)

        # ---------- tete sous la capuche de lion ----------
        hx, hy = T(LEAN([(-48, -282)]))[0]

        # 1) la capuche derriere la tete (cowl), pas une couronne de rayons :
        #    des meches en etoile se lisent comme un soleil, pas comme un lion
        hood = smooth([(-2, -34), (-22, -44), (-44, -38), (-54, -14),
                       (-50, 12), (-30, 26), (-8, 20), (2, 0)], 5)
        # La capuche est le ton CLAIR, le visage le ton SOMBRE : sans cet
        # ecart de valeur, tete et capuche fusionnent en une boule brune.
        poly(L, [(hx + a, hy + b) for a, b in hood], shade(PELT_COL, 0.62))
        for i in range(8):
            a = 1.3 + i * 0.48
            r0, r1 = 34, 34 + 12 + 6 * math.sin(i * 2.3)
            cxh, cyh = hx - 24, hy - 6
            poly(L, [(cxh + math.cos(a - 0.14) * r0, cyh + math.sin(a - 0.14) * r0),
                     (cxh + math.cos(a) * r1, cyh + math.sin(a) * r1),
                     (cxh + math.cos(a + 0.14) * r0, cyh + math.sin(a + 0.14) * r0)],
                 shade(PELT_COL, 0.34 + 0.14 * (i % 2)))

        # 2) le visage, dans l'ombre de la capuche
        pygame.draw.circle(L, shade(base, 0.5), (int(hx), int(hy)), 24)
        poly(L, smooth([(hx - 14, hy + 8), (hx + 17, hy + 11), (hx + 9, hy + 34),
                        (hx - 11, hy + 28)], 3), shade(base, 0.4))
        # profil accroche par la lumiere du brasero
        pygame.draw.arc(L, warm, (hx - 22, hy - 24, 46, 48), -0.9, 1.0, 3)

        # 3) le mufle du lion rabattu sur le front (attribut d'Heracles).
        #    Sans crocs : deux triangles blancs a hauteur d'yeux se lisent
        #    immanquablement comme une paire de lunettes.
        muzzle = smooth([(-30, -38), (-2, -44), (14, -34), (8, -22), (-18, -18),
                         (-32, -26)], 4)
        sculpt(L, [(hx + a, hy + b) for a, b in muzzle], shade(PELT_COL, 0.5),
               rim=shade(PELT_COL, 1.05), rim_off=(2, -3))
        pygame.draw.arc(L, shade(PELT_COL, 0.24), (hx - 26, hy - 40, 38, 26),
                        3.4, 6.0, 3)

        # liseres : chaud a gauche, froid a droite
        pygame.draw.arc(L, warm, (hx - 26, hy - 28, 52, 52), 2.2, 4.4, 4)
        pygame.draw.arc(L, cold, (hx - 26, hy - 28, 52, 52), -1.2, 0.7, 4)

        # ---------- bras : deux mains serrees sur la chaine ----------
        gx, gy = 104 + k * 6, -198 + k * 20
        for dy, w0, tone in ((24, 18, far_tone), (-8, 22, near_tone)):
            sh = T(LEAN([(-16, -244 + dy)]))[0]
            el = T([(44, -226 + dy + k * 14)])[0]
            hd = T([(gx - 6, gy + dy * 0.45)])[0]
            sculpt(L, tapered([sh, el, hd], [w0, w0 * 0.72, w0 * 0.52]),
                   tone, rim=warm, rim_off=(-2, -4),
                   under=shade(base, 1.5), under_off=(3, 3))
        px, py = T([(gx, gy)])[0]
        pygame.draw.circle(L, shade(base, 1.25), (int(px), int(py)), 15)
        pygame.draw.circle(L, shade(base, 0.55), (int(px), int(py)), 15, 3)
        pygame.draw.arc(L, warm, (px - 16, py - 16, 32, 32), 1.9, 4.6, 3)
        if k > 0.45:
            glow(L, px, py, 52, warm, int(130 * (k - 0.45) * 1.8))

        # ---------- eclairage global (MULT/ADD : pas besoin de masque) ------
        soft_shade(L, OX - 10, OY - 250, 130, 90, 0.4)
        glow(L, OX - 110, OY - 130, 100, warm, 40)
        glow(L, OX + 70, OY - 200, 90, cold, 30)

        self._grip = (px, py)
        self._spr, self._m = compose_sprite(L, s, width=max(3, int(4.5 * s)),
                                            color=INK, ring=5)


def chain(surf, p0, p1, tension=0.5, s=1.0, t=0.0):
    """
    Chaine a maillons. La fleche (le ventre de la chainette) se resorbe
    quand la traction monte : c'est le retour visuel principal de l'effort.
    """
    sag = (1.0 - tension) ** 1.4 * 130 * s + 6
    n = 14
    pts = []
    for i in range(n + 1):
        u = i / n
        x = lerp(p0[0], p1[0], u)
        y = lerp(p0[1], p1[1], u) + math.sin(u * math.pi) * sag
        if tension > 0.72:
            y += math.sin(t * 32 + u * 9) * (tension - 0.72) * 9
        pts.append((x, y))

    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        ang = math.atan2(y1 - y0, x1 - x0)
        seg = math.hypot(x1 - x0, y1 - y0)
        rl = seg * 0.62
        # un maillon sur deux vu de profil : presque une barre
        rw = (7.5 if i % 2 == 0 else 3.2) * s
        ring = []
        for j in range(14):
            a = j / 14 * math.tau
            ex, ey = math.cos(a) * rl, math.sin(a) * rw
            ring.append((int(mx + ex * math.cos(ang) - ey * math.sin(ang)),
                         int(my + ex * math.sin(ang) + ey * math.cos(ang))))
        pygame.draw.polygon(surf, shade(BRONZE, 0.35), ring, max(2, int(5 * s)))
        pygame.draw.polygon(surf, BRONZE, ring, max(1, int(2 * s)))
        # eclat sur la face superieure du maillon
        pygame.draw.line(surf, shade(BRONZE, 1.5),
                         ring[10], ring[12], max(1, int(2 * s)))

    if tension > 0.78:
        for _ in range(int((tension - 0.78) * 26)):
            i = random.randint(0, n)
            glow(surf, pts[i][0], pts[i][1], 15 * s, FIRE_HOT, 130)


# ============================================================== POST FX =====
_VIGNETTE = {}


def vignette(surf, strength=1.0):
    """
    Assombrissement des bords.

    Calcule en basse definition puis agrandi : un degre radial pixel par
    pixel en 1280x720 couterait des secondes, alors qu'un 96x54 lisse
    donne exactement le meme resultat visuel pour un cout negligeable.
    """
    w, h = surf.get_size()
    key = (w, h)
    v = _VIGNETTE.get(key)
    if v is None:
        lw, lh = 96, 54
        small = pygame.Surface((lw, lh), pygame.SRCALPHA)
        for j in range(lh):
            dy = (j + 0.5) / lh * 2 - 1
            for i in range(lw):
                dx = (i + 0.5) / lw * 2 - 1
                d = math.sqrt(dx * dx * 0.78 + dy * dy)
                k = max(0.0, min(1.0, (d - 0.40) / 0.82))
                small.set_at((i, j), (0, 0, 0, int(238 * k ** 1.8)))
        v = pygame.transform.smoothscale(small, (w, h))
        _VIGNETTE[key] = v
    if strength >= 0.99:
        surf.blit(v, (0, 0))
    else:
        c = v.copy()
        c.set_alpha(int(255 * strength))
        surf.blit(c, (0, 0))


_GRAIN = None


def grain(surf, amount=16):
    """Grain fixe pre-calcule (4 variantes alternees) - tres bon marche."""
    global _GRAIN
    w, h = surf.get_size()
    if _GRAIN is None or _GRAIN[0].get_size() != (w, h):
        gs = []
        for _ in range(4):
            g = pygame.Surface((w, h), pygame.SRCALPHA)
            px = pygame.PixelArray(g)
            for yy in range(0, h, 2):
                for xx in range(0, w, 2):
                    v = random.randint(0, 255)
                    px[xx, yy] = (v, v, v, 255)
            del px
            g.set_alpha(amount)
            gs.append(g)
        _GRAIN = gs
    idx = (pygame.time.get_ticks() // 60) % 4
    surf.blit(_GRAIN[idx], (0, 0), special_flags=pygame.BLEND_MULT)


def letterbox(surf, k):
    """Bandes cinema. k = 0 (aucune) -> 1 (bandes pleines)."""
    if k <= 0.01:
        return 0
    w, h = surf.get_size()
    bh = int(h * 0.115 * k)
    pygame.draw.rect(surf, (0, 0, 0), (0, 0, w, bh))
    pygame.draw.rect(surf, (0, 0, 0), (0, h - bh, w, bh))
    return bh


def color_grade(surf, tint, amount):
    """Teinte globale : sert aux flashs et aux fondus d'ambiance."""
    if amount <= 0.01:
        return
    ov = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    ov.fill((*tint, int(255 * amount)))
    surf.blit(ov, (0, 0))


def force_gauge(surf, x, y, w, h, force, lo, hi, hold=None, label="FORCE"):
    """
    Jauge de traction verticale : le retour visuel central du jeu.

    Le tutoriel et l'arene appellent CETTE fonction, jamais deux dessins
    separes : le joueur doit reconnaitre exactement la meme jauge quand il
    passe de l'explication au jeu.
    """
    in_band = lo <= force <= hi
    r = w // 2

    # fut
    pygame.draw.rect(surf, (0, 0, 0), (x - 4, y - 4, w + 8, h + 8),
                     border_radius=r + 4)
    pygame.draw.rect(surf, shade(STONE_DARK, 0.8), (x, y, w, h), border_radius=r)
    for i in range(1, 10):
        yy = y + h * i // 10
        pygame.draw.line(surf, shade(STONE_DARK, 1.5), (x + 5, yy),
                         (x + w - 5, yy), 1)

    # zone cible : fond seulement pour l'instant
    zy = int(y + (1 - hi) * h)
    zh = max(4, int((hi - lo) * h))
    zc = GREEN if in_band else (50, 96, 68)
    pygame.draw.rect(surf, shade(zc, 0.35), (x - 7, zy, w + 14, zh),
                     border_radius=8)

    # niveau courant
    fh = int(max(0.0, min(1.0, force)) * h)
    fy = y + h - fh
    if fh > 3:
        col = GREEN if in_band else GOLD
        pygame.draw.rect(surf, shade(col, 0.5), (x, fy, w, fh),
                         border_radius=r)
        pygame.draw.rect(surf, shade(col, 0.8), (x + 3, fy + 2, w - 6,
                                                 max(2, fh - 4)),
                         border_radius=r)

    # ... et le CADRE de la zone par-dessus le remplissage : sinon la barre
    # recouvre la cible et le joueur ne voit plus ou il doit se placer
    if in_band:
        glow(surf, x + w / 2, zy + zh / 2, w * 1.9, GREEN, 90)
    pygame.draw.rect(surf, zc, (x - 7, zy, w + 14, zh), 3, border_radius=8)

    if fh > 3:
        col = GREEN if in_band else GOLD
        # curseur : la ligne que le joueur suit reellement
        pygame.draw.rect(surf, WHITE, (x - 13, fy - 3, w + 26, 6),
                         border_radius=3)
        glow(surf, x + w / 2, fy, w * 1.5, col, 130)

    text(surf, label, font(FAM_DISPLAY, 19), GREY, x + w // 2, y - 20,
         anchor="center")

    # anneau de tenue
    if hold is not None:
        cx, cy, rr = x + w // 2, y + h + 52, 30
        pygame.draw.circle(surf, shade(STONE_DARK, 1.2), (cx, cy), rr, 7)
        if hold > 0:
            pygame.draw.arc(surf, GREEN, (cx - rr, cy - rr, rr * 2, rr * 2),
                            math.pi / 2, math.pi / 2 + min(1.0, hold) * math.tau, 7)
        if hold >= 1.0:
            glow(surf, cx, cy, 54, GREEN, 130)
        text(surf, "TENUE", font(FAM_DISPLAY, 15), GREY, cx, cy + rr + 18,
             anchor="center")


def compose_sprite(layer, scale=1.0, width=5, color=INK, ring=4):
    """
    Cuit un calque de personnage en un sprite fini, contour compris.

    Le contour est obtenu en tamponnant une silhouette pleine tout autour
    (multiplication par du noir : les RGB tombent a 0, l'alpha est conserve),
    puis en reposant le calque par-dessus. C'est ce contour continu qui
    donne la lisibilite "dessin anime" plutot qu'un empilement de formes.

    Renvoie (sprite, marge). La marge est le decalage a retrancher a la
    position d'ancrage au moment de l'affichage.
    """
    lay = layer
    if abs(scale - 1.0) > 0.01:
        lay = pygame.transform.smoothscale(
            layer, (max(1, int(layer.get_width() * scale)),
                    max(1, int(layer.get_height() * scale))))
    m = int(width) + 2
    spr = pygame.Surface((lay.get_width() + m * 2, lay.get_height() + m * 2),
                         pygame.SRCALPHA)
    # Silhouette pleine : une seule fusion suffit. On garde le contour noir
    # pur plutot que de reteinter (une passe RGBA_ADD de plus sur toute la
    # surface pour un ecart de couleur invisible).
    sil = lay.copy()
    sil.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
    for i in range(ring):
        a = i / ring * math.tau
        spr.blit(sil, (int(m + math.cos(a) * width),
                       int(m + math.sin(a) * width)))
    spr.blit(lay, (m, m))
    return spr, m


def speed_lines(surf, cx, cy, k, color=WHITE, n=30):
    """Lignes de vitesse facon anime, pour ponctuer un temps fort."""
    if k <= 0.01:
        return
    w, h = surf.get_size()
    for i in range(n):
        a = (i / n) * math.tau + random.random() * 0.2
        r0 = 250 + random.random() * 120
        r1 = r0 + 160 * k
        pygame.draw.line(surf, color,
                         (cx + math.cos(a) * r0, cy + math.sin(a) * r0),
                         (cx + math.cos(a) * r1, cy + math.sin(a) * r1),
                         random.choice((1, 2, 3)))


def impact_ring(surf, x, y, k, color=FIRE_HOT):
    """Onde de choc circulaire (k = 0 -> 1)."""
    if k <= 0 or k >= 1:
        return
    r = int(40 + k * 260)
    f = (1 - k) ** 1.6
    col = (int(color[0] * f), int(color[1] * f), int(color[2] * f))
    ring = pygame.Surface((r * 2 + 8, r * 2 + 8))
    ring.fill((0, 0, 0))
    pygame.draw.circle(ring, col, (r + 4, r + 4), r, max(2, int(11 * (1 - k))))
    surf.blit(ring, (x - r - 4, y - r - 4), special_flags=pygame.BLEND_ADD)
