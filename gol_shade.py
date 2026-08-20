# -*- coding: utf-8 -*-
"""
GYM OF LEGENDS - moteur d'eclairage par pixel
=============================================

Pourquoi ce module existe
-------------------------
Dessiner un personnage en remplissant des polygones donne, quoi qu'on fasse,
un rendu vectoriel plat : il n'y a aucune lumiere dans l'image, seulement des
couleurs posees cote a cote. Deplacer des points ne change rien a ce plafond.

Ici on ajoute l'etape qui manquait, celle d'un rendu peint :

  1. RELIEF   - on dessine, en niveaux de gris, l'epaisseur de chaque masse
                anatomique (le garrot bombe plus que le flanc, le museau plus
                que la joue). C'est une carte de hauteur.
  2. NORMALES - la pente de cette carte donne, en chaque pixel, l'orientation
                de la surface.
  3. LUMIERE  - on eclaire ces normales avec deux sources : une cle chaude
                venue des braseros et un contre-jour froid venu du portail.

Le resultat est un degrade continu qui epouse la forme, la ou l'aplat ne
donnait qu'une teinte uniforme.

Cout
----
Tout est calcule en numpy, une seule fois par pose (12 poses/seconde), et le
flou passe par des sommes cumulees : cout lineaire, pas de convolution. Le
champ de lumiere, qui est par nature tres doux, est calcule en demi-resolution
puis agrandi ; seule la composition finale travaille a pleine resolution.
"""

import numpy as np
import pygame

# ------------------------------------------------------------------ FLOU ----
def box_blur(a, r):
    """
    Flou moyenneur separable, en sommes cumulees : O(n) par axe.

    Une convolution gaussienne classique couterait bien trop cher a cette
    taille, et a l'echelle ou on l'utilise (adoucir un champ de hauteur) la
    difference visuelle est nulle.
    """
    if r < 1:
        return a
    k = 2 * r + 1
    p = np.pad(a, ((r + 1, r), (0, 0)), mode="edge")
    c = np.cumsum(p, axis=0)
    a = (c[k:] - c[:-k]) * (1.0 / k)
    p = np.pad(a, ((0, 0), (r + 1, r)), mode="edge")
    c = np.cumsum(p, axis=1)
    return (c[:, k:] - c[:, :-k]) * (1.0 / k)


def _norm3(x, y, z):
    inv = 1.0 / np.sqrt(x * x + y * y + z * z + 1e-6)
    return x * inv, y * inv, z * inv


# --------------------------------------------------------------- GRAIN ------
_FUR = {}


def fur_noise(w, h, seed=1789, scale=3):
    """
    Bruit fin, calcule une seule fois : sert de micro-relief de pelage.

    Applique en multiplication sur la couleur finale, il casse l'uniformite
    des grandes surfaces sans qu'on ait a dessiner un seul poil.
    """
    key = (w, h, seed, scale)
    n = _FUR.get(key)
    if n is None:
        rng = np.random.default_rng(seed)
        small = rng.random((w // scale + 2, h // scale + 2)).astype(np.float32)
        small = box_blur(small, 1)
        n = np.repeat(np.repeat(small, scale, axis=0), scale, axis=1)[:w, :h]
        n = 0.86 + 0.28 * n
        _FUR[key] = n
    return n


# ------------------------------------------------------------- ECLAIRAGE ----
class Light:
    """Une source : direction (x, y, z), couleur, intensite."""

    __slots__ = ("d", "col", "power")

    def __init__(self, d, col, power=1.0):
        n = np.sqrt(sum(c * c for c in d))
        self.d = tuple(c / n for c in d)
        self.col = np.array(col, dtype=np.float32) / 255.0
        self.power = power


# Ecran : x vers la droite, y vers le BAS. La cle vient donc d'en bas a
# gauche (les braseros poses au sol), le contre-jour d'en haut a droite
# (le portail, derriere la bete).
KEY = Light((-0.58, 0.44, 0.68), (255, 176, 108), 1.0)
RIM = Light((0.62, -0.52, 0.58), (120, 196, 178), 1.0)


AMBIENT_COL = np.array((104, 116, 148), dtype=np.float32) / 255.0

# Facteur de sous-echantillonnage du champ de lumiere. Celui-ci est tres
# basse frequence (le flou qui le produit a un large rayon), donc le calculer
# au quart puis l'agrandir est visuellement indiscernable et quatre fois
# moins cher. Le detail fin vient de la carte de pelage, elle en pleine
# resolution.
STEP = 4

_POOL = {}


def _pool(w, h, tag):
    """
    Surface persistante reutilisee d'une image a l'autre.

    pygame.surfarray.make_surface alloue et convertit a chaque appel : c'etait
    a lui seul la moitie du cout du moteur. Ecrire dans le tampon d'une
    surface deja allouee revient a une simple recopie memoire.
    """
    key = (w, h, tag)
    s = _POOL.get(key)
    if s is None:
        s = pygame.Surface((w, h)).convert()
        _POOL[key] = s
    return s


def _write(surf, data):
    a = pygame.surfarray.pixels3d(surf)
    a[:] = data
    del a
    return surf

_FUR_SURF = {}


def _fur_surface(w, h, strength):
    """Micro-relief de pelage, pre-calcule, applique en multiplication."""
    key = (w, h, round(strength, 2))
    s = _FUR_SURF.get(key)
    if s is None:
        n = fur_noise(w, h)
        n = 1.0 - strength + strength * n
        a = np.clip(n * 255.0, 0, 255).astype(np.uint8)
        s = pygame.surfarray.make_surface(np.repeat(a[:, :, None], 3, axis=2))
        _FUR_SURF[key] = s
    return s


def _raw_height(surf):
    """Repli : carte d'epaisseur fournie comme simple surface grise."""
    f = pygame.surfarray.pixels_red(surf)
    a = np.asarray(f[::STEP, ::STEP], dtype=np.float32) * (1.0 / 255.0)
    del f
    return a


def shade(layer, form, ambient=0.30, relief=2.6, rim_power=3.2,
          rim_gain=1.0, fur=0.0, ao=0.62, counter=0.0):
    """
    Eclaire `layer` (RGBA, couleur de base) d'apres `form` (niveaux de gris,
    carte d'epaisseur). Modifie `layer` sur place.

    Les couleurs de `layer` sont des ALBEDOS : la teinte de l'objet sous
    pleine lumiere. L'eclairage ne fait ensuite que les assombrir (multi-
    plication) puis ajouter le contre-jour (addition).

    relief     amplification de la pente : trop haut, ca tourne au metal
    rim_power  durete du contre-jour : eleve = lisere fin sur les aretes
    fur        0 -> lisse ; 1 -> micro-relief de pelage a pleine force

    Performance : la lumiere, tres basse frequence, est calculee en demi-
    resolution en numpy, puis agrandie et appliquee par des fusions pygame.
    Composer en numpy a pleine resolution coutait dix fois plus cher pour un
    resultat identique.
    """
    w, h = layer.get_size()

    # --- carte d'epaisseur -> champ de hauteur lisse (quart de resolution) ---
    fh = form.height() if isinstance(form, FormBuffer) else _raw_height(form)
    hw, hh = fh.shape

    # Deux echelles de flou, toutes deux COURTES.
    # Le role du flou n'est pas de creer le volume - celui-ci vient deja des
    # bombements declares dans la carte d'epaisseur - mais seulement
    # d'adoucir les marches d'escalier des polygones. Un rayon large fond
    # toutes les masses en une seule bouillie et supprime le relief interne.
    height = (0.5 * box_blur(fh, max(2, hw // 40))
              + 0.5 * box_blur(fh, max(1, hw // 110)))

    # --- normales, par gradient du champ de hauteur ---
    gx = np.zeros_like(height)
    gy = np.zeros_like(height)
    gx[1:-1, :] = (height[2:, :] - height[:-2, :]) * 0.5
    gy[:, 1:-1] = (height[:, 2:] - height[:, :-2]) * 0.5
    amp = relief * hw / 100.0
    nx, ny, nz = _norm3(-gx * amp, -gy * amp, np.ones_like(gx))

    d = KEY.d
    diff = np.clip(nx * d[0] + ny * d[1] + nz * d[2], 0.0, 1.0)
    d = RIM.d
    rim = np.clip(nx * d[0] + ny * d[1] + nz * d[2], 0.0, 1.0) ** rim_power
    # Le contre-jour n'a de sens que sur les bords : au centre d'une masse
    # epaisse, aucune lumiere ne passe par derriere.
    rim *= np.clip(1.0 - height * 1.5, 0.0, 1.0)

    # --- occlusion ambiante ---
    # C'est la piece decisive. Un modele purement diffus donne un objet
    # "gonfle" et uniforme ; ce sont les ombres de contact - la ou deux
    # masses se rejoignent, la ou une patte passe derriere le flanc - qui
    # font lire l'image comme un dessin plutot que comme un ballon. On les
    # obtient gratuitement : le champ de hauteur est bas exactement dans
    # ces creux.
    if ao > 0.0:
        occ = np.clip(height * 2.2, 0.0, 1.0) ** 0.55
        shadowing = (1.0 - ao) + ao * occ
    else:
        shadowing = 1.0

    # --- carte de multiplication : ambiante froide + cle chaude ---
    # Bornee a 1 par construction, donc compatible avec BLEND_MULT.
    mul = (ambient * AMBIENT_COL[None, None, :]
           + (1.0 - ambient) * diff[:, :, None] * KEY.col[None, None, :])
    mul *= shadowing[:, :, None] if ao > 0.0 else 1.0

    # --- contre-ombrage ---
    # Presque tous les animaux sont sombres sur le dos et clairs sous le
    # ventre. Sans cette variation verticale, un pelage d'une seule teinte
    # se lit comme du plastique quelle que soit la qualite de l'eclairage.
    if counter > 0.0:
        ramp = np.linspace(1.0 - counter, 1.0, hh, dtype=np.float32)
        mul *= ramp[None, :, None]
    mul_s = _write(_pool(hw, hh, "mul"),
                   np.clip(mul * 255.0, 0, 255).astype(np.uint8))
    add_s = _write(_pool(hw, hh, "add"),
                   np.clip((rim * rim_gain * 255.0)[:, :, None]
                           * RIM.col[None, None, :], 0, 255).astype(np.uint8))

    mul_s = pygame.transform.smoothscale(mul_s, (w, h))
    add_s = pygame.transform.smoothscale(add_s, (w, h))

    # BLEND_MULT et BLEND_ADD ne touchent pas le canal alpha : la silhouette
    # est preservee sans avoir a manipuler de masque.
    layer.blit(mul_s, (0, 0), special_flags=pygame.BLEND_MULT)
    if fur > 0.0:
        layer.blit(_fur_surface(w, h, fur), (0, 0), special_flags=pygame.BLEND_MULT)
    layer.blit(add_s, (0, 0), special_flags=pygame.BLEND_ADD)


# ------------------------------------------------------------------ FORM ----
class FormBuffer:
    """
    Ou l'on declare l'epaisseur de chaque masse du personnage.

    Convention : 0 = vide, 255 = le point le plus proche du spectateur. On ne
    cherche pas une profondeur exacte, seulement des ecarts credibles - un
    garrot plus bombe que le flanc, un museau plus saillant qu'une joue.

    DEUX CANAUX, pour une bonne raison
    ---------------------------------
    - `mass()` rasterise un polygone : c'est le canal des pieces FINES
      (pattes, cornes, dents, crocs). Etroites, elles sont naturellement
      arrondies par le petit flou applique ensuite.

    - `blob()` accumule un dome LISSE calcule analytiquement en numpy :
      c'est le canal des GROSSES masses (flanc, epaule, cuisse, museau).

    Pourquoi ne pas tout rasteriser ? Parce qu'on derive ensuite ce champ
    pour obtenir les normales. Des ellipses concentriques dessinees en
    escalier ont un gradient en marches : amplifie par l'eclairage, ca ne
    produit pas du volume mais des taches. Un dome analytique, lui, se
    derive proprement.
    """

    def __init__(self, w, h, step=None):
        self.w, self.h = w, h
        self.step = step or STEP
        self.gw = max(1, w // self.step)
        self.gh = max(1, h // self.step)
        self.surf = pygame.Surface((w, h))
        self.surf.fill((0, 0, 0))
        self.dome = np.zeros((self.gw, self.gh), dtype=np.float32)
        ax = np.arange(self.gw, dtype=np.float32) * self.step
        ay = np.arange(self.gh, dtype=np.float32) * self.step
        self._gx = ax[:, None]
        self._gy = ay[None, :]

    def clear(self):
        self.surf.fill((0, 0, 0))
        self.dome[:] = 0.0

    def mass(self, pts, level):
        """Piece fine : polygone plein d'epaisseur uniforme."""
        v = int(max(0, min(255, level)))
        if len(pts) >= 3:
            pygame.draw.polygon(self.surf, (v, v, v),
                                [(int(a), int(b)) for a, b in pts])

    def blob(self, x, y, rx, ry, level):
        """
        Grosse masse : paraboloide lisse, accumule en maximum.

        Le maximum (plutot qu'une somme) fait que deux masses qui se
        chevauchent se rejoignent par une arete nette au lieu de gonfler
        l'une dans l'autre - c'est exactement le pli qu'on veut voir entre
        une epaule et un flanc.
        """
        rx, ry = max(2.0, float(rx)), max(2.0, float(ry))
        st = self.step
        i0 = max(0, int((x - rx) / st))
        i1 = min(self.gw, int((x + rx) / st) + 2)
        j0 = max(0, int((y - ry) / st))
        j1 = min(self.gh, int((y + ry) / st) + 2)
        if i0 >= i1 or j0 >= j1:
            return
        dx = (self._gx[i0:i1] - x) / rx
        dy = (self._gy[:, j0:j1] - y) / ry
        d2 = dx * dx + dy * dy
        v = (1.0 - d2) * float(level)
        np.maximum(self.dome[i0:i1, j0:j1], v, out=self.dome[i0:i1, j0:j1])

    def groove(self, p0, p1, width, level):
        """Un creux (ou une arete) le long d'un segment."""
        v = int(max(0, min(255, level)))
        pygame.draw.line(self.surf, (v, v, v),
                         (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1])),
                         max(1, int(width)))

    def height(self):
        """Champ combine, en quart de resolution, normalise en 0..1."""
        f = pygame.surfarray.pixels_red(self.surf)
        raster = np.asarray(f[::self.step, ::self.step], dtype=np.float32)
        del f
        g = self.dome
        if raster.shape != g.shape:          # arrondis de division
            gw = min(raster.shape[0], g.shape[0])
            gh = min(raster.shape[1], g.shape[1])
            raster = raster[:gw, :gh]
            g = g[:gw, :gh]
        return np.maximum(raster, np.clip(g, 0.0, 255.0)) * (1.0 / 255.0)
