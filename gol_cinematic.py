# -*- coding: utf-8 -*-
"""
GYM OF LEGENDS - cinematique d'ouverture
========================================

Une cinematique courte, entierement mise en scene par le code : la camera
se deplace dans le decor des Enfers, le texte s'ecrit au fur et a mesure,
puis un plan-tutoriel explique le geste avant que le combat commence.

Principe technique : la scene est toujours peinte a taille reelle dans une
surface "plateau" (stage), et la camera n'est qu'un recadrage + agrandissement
de ce plateau. On obtient de vrais mouvements d'appareil (travelling, zoom)
sans avoir a transformer chaque forme dessinee.
"""

import math

import pygame

import gol_art as A


class Shot:
    """
    Un plan.

    cam      (x, y, zoom) vise au debut du plan, en coordonnees plateau
    cam_end  meme chose a la fin : la camera interpole entre les deux
    lines    repliques : (locuteur, texte). None = pas de cartouche
    hold     duree du plan en secondes
    setup    fonction optionnelle qui peint les acteurs sur le plateau
    """

    def __init__(self, cam, cam_end, lines, hold, setup=None, flash=0.0):
        self.cam = cam
        self.cam_end = cam_end
        self.lines = lines or []
        self.hold = hold
        self.setup = setup
        self.flash = flash


class Cinematic:
    """Enchaine les plans, gere la camera, le texte et le fondu."""

    CPS = 42.0          # caracteres par seconde a l'ecriture

    def __init__(self, w, h, gate, cerberus, hercules):
        self.w, self.h = w, h
        self.gate = gate
        self.cerb = cerberus
        self.herc = hercules
        self.stage = pygame.Surface((w, h)).convert()

        self.f_name = A.font(A.FAM_DISPLAY, 24)
        self.f_line = A.font(A.FAM_TITLE, 31)
        self.f_hint = A.font(A.FAM_BODY, 19)
        self.f_title = A.font(A.FAM_DISPLAY, 92)
        self.f_sub = A.font(A.FAM_TITLE, 26, italic=True)

        self.shots = self._build()
        self.i = 0
        self.t = 0.0            # temps ecoule dans le plan courant
        self.total = 0.0        # temps absolu (animations du decor)
        self.line_i = 0
        self.line_t = 0.0
        self.done = False
        self.fade = 1.0         # fondu au noir en ouverture
        self._band = None

    # ------------------------------------------------------------ plans ----
    def _build(self):
        w, h = self.w, self.h
        g = self.gate
        gx, gy = g.gx, g.ground_y

        def wide(surf, k):
            pass

        # Echelle 1.0 partout : elle evite un redimensionnement lisse du
        # calque a chaque recomposition (voir compose_sprite).
        CX, HX = 880, 252

        def beast_only(surf, k):
            self.cerb.draw(surf, CX, gy, 1.0, self.total,
                           aggro=0.25 + k * 0.55, strain=0.0,
                           jaws=0.15 + k * 0.55)

        def hero_enters(surf, k):
            self.herc.draw(surf, HX - 60 + k * 60, gy - 12, 1.0, self.total,
                           pull=0.05)
            self.cerb.draw(surf, CX, gy, 1.0, self.total,
                           aggro=0.7, strain=0.05, jaws=0.5)

        def faceoff(surf, k):
            grip = self.herc.draw(surf, HX, gy - 12, 1.0, self.total,
                                  pull=0.25 + k * 0.5)
            self.cerb.draw(surf, CX, gy, 1.0, self.total,
                           aggro=0.9, strain=0.2 + k * 0.5, jaws=0.8)
            A.chain(surf, grip, (CX - 72, gy - 172), tension=0.35 + k * 0.5,
                    s=1.0, t=self.total)

        cx = w * 0.5
        return [
            # 1. large sur le portail, camera qui recule lentement
            Shot((gx, h * 0.44, 1.55), (gx, h * 0.48, 1.18),
                 [("", "Aux portes des Enfers, la ou les ames entrent"),
                  ("", "et d'ou aucune ne ressort.")],
                 6.4, wide),

            # 2. plan serre sur la bete, les yeux s'allument
            Shot((gx + 90, h * 0.38, 1.72), (gx + 130, h * 0.48, 1.30),
                 [("", "Un seul gardien. Trois gueules."),
                  ("LE NARRATEUR", "Cerbere ne dort jamais tout entier.")],
                 6.6, beast_only),

            # 3. Hercule entre dans le champ
            Shot((320, h * 0.52, 1.65), (430, h * 0.56, 1.28),
                 [("LE NARRATEUR", "Douzieme travail d'Hercule : le ramener"),
                  ("LE NARRATEUR", "vivant. Sans arme. Sans blessure.")],
                 6.4, hero_enters),

            # 4. face a face, la chaine se tend
            Shot((cx + 40, h * 0.58, 1.30), (cx + 20, h * 0.56, 1.06),
                 [("HERCULE", "Une seule prise me reste : la traction."),
                  ("HERCULE", "Tirer. Tenir. Relacher. Encore.")],
                 6.8, faceoff, flash=0.0),
        ]

    # ----------------------------------------------------------- avance ----
    def skip_line(self):
        """Entree : termine la replique en cours, ou passe au plan suivant."""
        sh = self.shots[self.i]
        if self.line_i < len(sh.lines):
            full = len(sh.lines[self.line_i][1]) / self.CPS
            if self.line_t < full:
                self.line_t = full
                return
            self.line_i += 1
            self.line_t = 0.0
            if self.line_i < len(sh.lines):
                return
        self._next_shot()

    def skip_all(self):
        self.done = True

    def _next_shot(self):
        self.i += 1
        self.t = 0.0
        self.line_i = 0
        self.line_t = 0.0
        if self.i >= len(self.shots):
            self.done = True
            self.i = len(self.shots) - 1

    def update(self, dt):
        if self.done:
            return
        self.total += dt
        self.t += dt
        self.fade = max(0.0, self.fade - dt * 1.1)
        self.gate.update(dt, self.total)

        sh = self.shots[self.i]
        if self.line_i < len(sh.lines):
            self.line_t += dt
            full = len(sh.lines[self.line_i][1]) / self.CPS
            # une fois la replique ecrite, on la laisse respirer
            if self.line_t > full + 1.7:
                self.line_i += 1
                self.line_t = 0.0
        elif self.t >= sh.hold:
            self._next_shot()

    # ------------------------------------------------------------ rendu ----
    def draw(self, surf):
        sh = self.shots[self.i]
        k = min(1.0, self.t / max(0.1, sh.hold))
        ease = k * k * (3 - 2 * k)          # demarrage et arret adoucis

        # --- le plateau, peint a taille reelle ---
        st = self.stage
        self.gate.draw(st, self.total)
        if sh.setup:
            sh.setup(st, ease)

        # --- la camera : recadrage + agrandissement du plateau ---
        cx = A.lerp(sh.cam[0], sh.cam_end[0], ease)
        cy = A.lerp(sh.cam[1], sh.cam_end[1], ease)
        z = A.lerp(sh.cam[2], sh.cam_end[2], ease)
        vw, vh = int(self.w / z), int(self.h / z)
        vx = int(max(0, min(self.w - vw, cx - vw / 2)))
        vy = int(max(0, min(self.h - vh, cy - vh / 2)))
        view = st.subsurface(pygame.Rect(vx, vy, vw, vh))
        pygame.transform.smoothscale(view, (self.w, self.h), surf)

        A.vignette(surf, 1.0)

        # --- bandes cinema + cartouche de dialogue ---
        bh = A.letterbox(surf, 1.0)
        self._caption(surf, sh, bh)

        if self.fade > 0.01:
            A.color_grade(surf, (0, 0, 0), self.fade)

    def _caption(self, surf, sh, bh):
        if self.line_i >= len(sh.lines):
            self._hint(surf, bh)
            return
        who, txt = sh.lines[self.line_i]
        n = int(self.line_t * self.CPS)
        shown = txt[:n]

        y = self.h - bh - 74
        # bandeau sombre derriere le texte, pour la lisibilite
        if self._band is None:
            self._band = pygame.Surface((self.w, 108), pygame.SRCALPHA)
            self._band.fill((0, 0, 0, 150))
        surf.blit(self._band, (0, y - 26))

        if who:
            A.text(surf, who, self.f_name, A.GOLD, 92, y - 4, glow=A.GOLD_DIM)
            pygame.draw.line(surf, A.GOLD_DIM, (92, y + 12),
                             (92 + self.f_name.size(who)[0], y + 12), 2)
        A.text(surf, shown, self.f_line, A.WHITE, 92, y + 44)

        # curseur clignotant tant que la ligne s'ecrit
        if n < len(txt) and int(self.total * 6) % 2 == 0:
            wpx = self.f_line.size(shown)[0]
            pygame.draw.rect(surf, A.GOLD, (92 + wpx + 4, y + 30, 11, 26))
        self._hint(surf, bh)

    def _hint(self, surf, bh):
        A.text(surf, "[ENTREE] suite      [ECHAP] passer la cinematique",
               self.f_hint, A.GREY, self.w - 60, self.h - bh - 20,
               anchor="right", shadow=True)


class Tutorial:
    """
    Le plan-explication.

    Plutot qu'un mur de texte, on montre : une jauge identique a celle du
    jeu execute en boucle une repetition parfaite, et les trois etapes
    s'allument au moment ou la demonstration les traverse.
    """

    CYCLE = 6.0          # duree d'une demonstration complete

    STEPS = [
        ("TIRER", "Monte la traction progressivement,",
         "sans a-coup, jusqu'a la zone verte."),
        ("TENIR", "Stabilise-toi DANS la zone",
         "le temps que l'anneau se remplisse."),
        ("RELACHER", "Relache doucement.",
         "Cerbere recule d'un pas. Recommence."),
    ]

    def __init__(self, w, h, cfg):
        self.w, self.h = w, h
        self.cfg = cfg
        self.t = 0.0
        self.f_title = A.font(A.FAM_DISPLAY, 62)
        self.f_step = A.font(A.FAM_DISPLAY, 30)
        self.f_body = A.font(A.FAM_BODY, 20)
        self.f_num = A.font(A.FAM_DISPLAY, 46)
        self.f_hint = A.font(A.FAM_BODY, 20)
        self.f_note = A.font(A.FAM_TITLE, 19, italic=True)

    def update(self, dt):
        self.t += dt

    # --- profil de la repetition demontree : montee / tenue / descente ---
    def _demo(self, lo, hi):
        u = (self.t % self.CYCLE) / self.CYCLE
        mid = (lo + hi) / 2.0
        if u < 0.06:
            return 0.0, 0.0, 0
        if u < 0.34:                      # montee reguliere
            k = (u - 0.06) / 0.28
            return mid * (k * k * (3 - 2 * k)), 0.0, 0
        if u < 0.74:                      # tenue dans la zone
            k = (u - 0.34) / 0.40
            wob = math.sin(self.t * 5.0) * (hi - lo) * 0.10
            return mid + wob, k, 1
        if u < 0.92:                      # relachement
            k = (u - 0.74) / 0.18
            return mid * (1 - k), 1.0, 2
        return 0.0, 0.0, 2

    def draw(self, surf, gate, total):
        w, h = self.w, self.h
        gate.draw(surf, total)
        A.color_grade(surf, (6, 5, 9), 0.62)

        lo, hi = self.cfg.band()
        force, hold, active = self._demo(lo, hi)

        A.text(surf, "LE GESTE", self.f_title, A.GOLD, 96, 96, glow=A.GOLD_DIM)
        A.text(surf, "Face-Pull  -  la meme jauge t'attend dans l'arene",
               self.f_note, A.GREY, 100, 146)
        pygame.draw.line(surf, A.GOLD_DIM, (96, 170), (620, 170), 2)

        # --- demonstration vivante ---
        # hauteur calee pour que l'anneau de tenue reste au-dessus du
        # cartouche du bas, sinon il disparait derriere
        A.force_gauge(surf, 168, 228, 52, 266, force, lo, hi, hold=hold)

        # --- les trois etapes, celle en cours mise en avant ---
        y = 236
        for i, (title, l1, l2) in enumerate(self.STEPS):
            on = (i == active)
            col = A.GOLD if on else A.GREY_DARK
            tc = A.WHITE if on else A.GREY
            pygame.draw.circle(surf, col, (392, y + 14), 22, 0 if on else 3)
            A.text(surf, str(i + 1), self.f_num,
                   A.INK if on else A.GREY, 392, y + 15, anchor="center",
                   shadow=False)
            A.text(surf, title, self.f_step, col, 436, y + 6)
            A.text(surf, l1, self.f_body, tc, 436, y + 40)
            A.text(surf, l2, self.f_body, tc, 436, y + 66)
            if on:
                pygame.draw.line(surf, A.GOLD, (436, y + 22),
                                 (436 + self.f_step.size(title)[0], y + 22), 2)
            y += 116

        # --- rappel de la consigne clinique ---
        box = pygame.Rect(96, h - 152, w - 192, 62)
        pygame.draw.rect(surf, (0, 0, 0), box, border_radius=8)
        pygame.draw.rect(surf, A.GREY_DARK, box, 2, border_radius=8)
        A.text(surf, "Ce n'est pas un jeu de force : c'est un jeu de CONTROLE.",
               self.f_body, A.WHITE, box.x + 24, box.y + 22)
        A.text(surf, "Regulier et stable rapporte plus que fort et brusque.",
               self.f_body, A.GREEN, box.x + 24, box.y + 44)

        A.text(surf, "[ENTREE]  AFFRONTER CERBERE", self.f_hint, A.GOLD,
               w // 2, h - 56, anchor="center", glow=A.GOLD_DIM)
