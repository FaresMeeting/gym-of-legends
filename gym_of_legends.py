# -*- coding: utf-8 -*-
"""
GYM OF LEGENDS (pygame)
=======================
QTE narratif de reeducation : Hercule vs Cerbere - mouvement Face-Pull.

CONTROLE : gachette R2 analogique d'une manette.
  La PRESSION sur R2 = la FORCE de traction du patient.
  -> quand la vraie poulie arrivera, il suffira de remplacer
     InputSource.read() par la lecture du capteur. Le reste ne bouge pas.

Le visuel vit dans gol_art.py (decor, personnages, effets) et
gol_cinematic.py (ouverture narrative + ecran d'explication). Tout y est
genere par le code : aucune image, aucun asset externe, donc aucune
dependance a une oeuvre tierce.

Lancer :  python gym_of_legends.py
"""

import json
import math
import random
from datetime import datetime

import pygame

import gol_art as A
from gol_cinematic import Cinematic, Tutorial

# ---------------------------------------------------------------- CONFIG ----
W, H = 1280, 720
FPS = 60

# La palette de reference vit dans gol_art : on n'en garde ici que des alias,
# pour eviter deux jeux de couleurs qui divergent avec le temps.
INK, WHITE, GREY = A.INK, A.WHITE, A.GREY
GREY_DARK, GOLD, GREEN = A.GREY_DARK, A.GOLD, A.GREEN
ORANGE, RED = A.FIRE_MID, A.BLOOD

DEADZONE = 0.10          # en dessous : on considere R2 relache


# ------------------------------------------------------------ INPUT SOURCE --
class InputSource:
    """
    Renvoie une force normalisee 0.0 -> 1.0.

    Trois modes :
      - "pad"   : gachette analogique (R2), axe auto-detecte a la calibration
      - "mouse" : position verticale de la souris (secours, analogique aussi)

    >>> POINT D'INTEGRATION POULIE <<<
    Le jour ou le capteur de poulie est pret, ajouter un mode "poulie" ici
    et renvoyer force = charge_lue / charge_max. Rien d'autre a changer.
    """

    def __init__(self):
        self.mode = "mouse"
        self.joy = None
        self.axis = None
        self.rest = -1.0
        self.full = 1.0

    def detect_pad(self):
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            self.joy = pygame.joystick.Joystick(0)
            self.joy.init()
            return self.joy.get_name()
        return None

    def axis_values(self):
        if not self.joy:
            return []
        return [self.joy.get_axis(i) for i in range(self.joy.get_numaxes())]

    def read(self):
        if self.mode == "pad" and self.joy is not None and self.axis is not None:
            raw = self.joy.get_axis(self.axis)
            span = (self.full - self.rest)
            if abs(span) < 0.2:
                return 0.0
            f = (raw - self.rest) / span
            return max(0.0, min(1.0, f))
        # secours souris : haut de l'ecran = 0, bas = 1
        _, my = pygame.mouse.get_pos()
        return max(0.0, min(1.0, my / float(H)))


# ------------------------------------------------------------- EVALUATION ---
class RepEvaluator:
    """
    Analyse une repetition complete et rend une note.

    Une rep = monter la force jusque dans la bande cible, la TENIR
    le temps demande, puis relacher.

    Criteres (tous regles par la config kine) :
      - tempo de montee     -> a-coup si trop rapide, mou si trop lent
      - regularite (jerk)   -> variation de la vitesse de traction
      - stabilite en bande  -> ecart moyen au centre de la bande
      - depassement         -> tire beaucoup trop fort
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self.reset()

    def reset(self):
        self.samples = []          # (t, force)
        self.band_samples = []     # (temps_de_tenue_cumule, force)
        self.in_band_time = 0.0
        self.ascent_time = None
        self.t = 0.0
        self.max_force = 0.0

    def feed(self, force, dt):
        self.t += dt
        self.samples.append((self.t, force))
        self.max_force = max(self.max_force, force)
        lo, hi = self.cfg.band()
        if lo <= force <= hi:
            self.in_band_time += dt
            self.band_samples.append((self.in_band_time, force))
            if self.ascent_time is None:
                self.ascent_time = self.t

    def grade(self):
        cfg = self.cfg
        lo, hi = cfg.band()
        center = (lo + hi) / 2.0

        # regularite : ecart-type de la vitesse de variation de la force
        speeds = []
        for i in range(1, len(self.samples)):
            dt = self.samples[i][0] - self.samples[i - 1][0]
            if dt > 0:
                speeds.append((self.samples[i][1] - self.samples[i - 1][1]) / dt)
        if speeds:
            mean = sum(speeds) / len(speeds)
            var = sum((s - mean) ** 2 for s in speeds) / len(speeds)
            jerk = math.sqrt(var)
        else:
            jerk = 0.0

        # Stabilite : on ne juge QUE la fin de la tenue.
        # La phase d'approche (le patient monte vers la zone) ne doit pas
        # etre comptee comme de l'instabilite - sinon un mouvement lent
        # mais parfaitement controle serait puni a tort.
        # On mesure le TREMBLEMENT (ecart a sa propre moyenne), pas la
        # precision a la cible : etre dans la bande suffit deja pour la
        # precision. Sinon un patient lent mais parfaitement stable serait
        # puni juste parce qu'il n'a pas encore atteint le centre.
        if self.band_samples:
            cutoff = self.in_band_time * 0.4
            hold_pts = [f for tt, f in self.band_samples if tt >= cutoff]
            if not hold_pts:
                hold_pts = [f for _, f in self.band_samples]
            moy = sum(hold_pts) / len(hold_pts)
            drift = sum(abs(f - moy) for f in hold_pts) / len(hold_pts)
        else:
            drift = 1.0

        asc = self.ascent_time if self.ascent_time is not None else 99.0
        tol = cfg.tolerance()

        faults = []
        trop_vite = asc < cfg.ascent_min() * (1 / tol)
        if trop_vite:
            faults.append(("acoup", "Trop brusque - monte progressivement."))
        if asc > cfg.ascent_max() * tol:
            faults.append(("lent", "Un peu plus de rythme sur la montee."))
        # Une montee brusque cree forcement de l'irregularite : c'est le
        # MEME geste. On ne le compte pas deux fois, sinon un simple a-coup
        # ferait tomber directement en "mauvais".
        if jerk > 0.95 * tol and not trop_vite:
            faults.append(("irregulier", "Plus regulier, sans a-coup."))
        if self.max_force > hi + 0.16 * tol:
            faults.append(("fort", "Tu tires trop fort - reste dans la zone."))
        if drift > 0.040 * tol:
            faults.append(("instable", "Stabilise ta traction dans la zone."))

        # "Parfait" doit rester rare : c'est lui qui rend la progression
        # lisible d'une seance a l'autre. Le critere dominant est la
        # stabilite de la tenue, qui est ce qui compte cliniquement.
        perfect = (
            not faults
            and jerk <= 0.30 * tol
            and drift <= 0.010 * tol
            and abs(asc - (cfg.ascent_min() + cfg.ascent_max()) / 2) <= 0.25 * tol
        )

        if perfect:
            return "parfait", 10, "Parfait - la foule s'enflamme !"
        if not faults:
            return "bon", 7, "Bon mouvement, continue !"
        if len(faults) == 1:
            return "acceptable", 3, faults[0][1]
        return "mauvais", 1, "Attention, plus regulier ! Cerbere resiste."


# ----------------------------------------------------------- CONFIG KINE ----
class KineConfig:
    """Reglages du kine. Pilotent directement la difficulte du QTE."""

    def __init__(self):
        self.mouvement = "Face-Pull"
        self.charge = 8              # kg
        self.series = 3
        self.reps = 10
        self.difficulte = 1          # 0 facile / 1 normal / 2 exigeant
        self.douleur_epaule = True

    # --- derives ---
    def band(self):
        """Bande de force cible (min, max), en fraction de la force max."""
        center = 0.32 + (self.charge / 20.0) * 0.42
        half = [0.15, 0.11, 0.075][self.difficulte]
        if self.douleur_epaule:
            half *= 1.35
        return max(0.05, center - half), min(0.98, center + half)

    def tolerance(self):
        t = [1.35, 1.0, 0.78][self.difficulte]
        if self.douleur_epaule:
            t *= 1.3
        return t

    def hold_required(self):
        h = 1.25 + (self.charge - 8) * 0.03
        if self.douleur_epaule:
            h *= 0.8
        return max(0.6, h)

    def ascent_min(self):
        return 0.45

    def ascent_max(self):
        return 1.5

    def label_diff(self):
        return ["FACILE", "NORMAL", "EXIGEANT"][self.difficulte]


# ------------------------------------------------------------- TRANSITION ---
class SlashWipe:
    """Transition diagonale facon anime : le sabre coupe l'ecran."""

    def __init__(self):
        self.t = 1.0
        self.pending = None

    def start(self, callback):
        self.t = 0.0
        self.pending = callback

    def active(self):
        return self.t < 1.0

    def update(self, dt):
        if self.t >= 1.0:
            return
        self.t = min(1.0, self.t + dt * 1.7)
        if self.t >= 0.5 and self.pending:
            self.pending()
            self.pending = None

    def draw(self, surf):
        if self.t >= 1.0:
            return
        # 0 -> 0.5 : les bandes recouvrent ; 0.5 -> 1 : elles se retirent
        p = self.t * 2 if self.t < 0.5 else (1.0 - self.t) * 2
        p = max(0.0, min(1.0, p))
        skew = 260
        bands = 3
        bh = H // bands
        for i in range(bands):
            direction = 1 if i % 2 == 0 else -1
            width = int((W + skew) * p)
            x = -skew + (0 if direction > 0 else (W + skew) - width)
            pts = [
                (x, i * bh),
                (x + width, i * bh),
                (x + width - skew, (i + 1) * bh),
                (x - skew, (i + 1) * bh),
            ]
            pygame.draw.polygon(surf, INK, pts)
        if 0.42 < self.t < 0.62:
            pygame.draw.line(surf, GOLD, (0, H), (W, 0), 6)


# ------------------------------------------------------------- NARRATION ----
# Le QTE reste un exercice clinique : c'est la VOIX qui le rend narratif.
# Chaque note declenche une replique differente, et on evite de repeter la
# derniere pour que la seance ne sonne pas comme un automate.
BEATS = {
    "parfait": [
        ("HERCULE", "Il recule ! Encore une comme celle-la !"),
        ("LE NARRATEUR", "Geste parfait. Les trois gueules hesitent."),
        ("HERCULE", "Je le sens ceder sous la chaine."),
        ("LE NARRATEUR", "Meme les Enfers retiennent leur souffle."),
    ],
    "bon": [
        ("HERCULE", "Bien. Le meme, encore."),
        ("LE NARRATEUR", "La chaine tient. Cerbere perd du terrain."),
        ("HERCULE", "Regulier. C'est comme ca qu'on gagne."),
    ],
    "acceptable": [
        ("LE NARRATEUR", "La prise glisse un peu. Reprends ton rythme."),
        ("HERCULE", "Pas assez net. Recommence proprement."),
    ],
    "mauvais": [
        ("LE NARRATEUR", "Cerbere sent la faille et reprend un pas."),
        ("HERCULE", "Trop brutal ! La force seule ne suffit pas."),
        ("LE NARRATEUR", "Trois gorges grondent. Reprends le controle."),
    ],
}

# Repliques declenchees quand la jauge franchit un seuil, une seule fois
# par serie : ce sont les temps forts du recit.
MILESTONES = [
    (45, ("LE NARRATEUR", "Une des gueules baisse la garde.")),
    (72, ("HERCULE", "Encore un effort et il passe le seuil !")),
    (95, ("LE NARRATEUR", "Le gardien recule vers la lumiere du monde.")),
]


# ------------------------------------------------------------------ JEU -----
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Gym Of Legends")
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()

        # Deux familles : un display condense pour les chiffres et les
        # titres, un serif pour tout ce qui releve du recit.
        self.f_huge = A.font(A.FAM_DISPLAY, 96)
        self.f_big = A.font(A.FAM_DISPLAY, 64)
        self.f_mid = A.font(A.FAM_DISPLAY, 34)
        self.f_line = A.font(A.FAM_TITLE, 27)
        self.f_small = A.font(A.FAM_BODY, 20)
        self.f_tiny = A.font(A.FAM_DISPLAY, 17)

        self.inp = InputSource()
        self.pad_name = self.inp.detect_pad()
        self.cfg = KineConfig()
        self.wipe = SlashWipe()

        # --- decor et acteurs ---
        self.gate = A.HellGate(W, H)
        self.cerb = A.Cerberus()
        self.herc = A.Hercules()
        self.cine = Cinematic(W, H, self.gate, self.cerb, self.herc)
        self.tuto = Tutorial(W, H, self.cfg)
        self.clock_t = 0.0
        self._bands = {}

        self.state = "calib" if self.pad_name else "intro"
        self.calib_step = 0
        self.calib_rest = []

        self.reset_session()

        # feedback / effets
        self.msg = "Hercule, retiens Cerbere. Tire, et surtout : tiens."
        self.msg_color = WHITE
        self.speaker = "LE NARRATEUR"
        self.flash = 0.0
        self.shake = 0.0
        self.floats = []          # (texte, x, y, vie, couleur)
        self.speedlines = 0.0
        self.ring = 0.0           # onde de choc sur un mouvement parfait
        self.roar = 0.0           # Cerbere rugit : gueules grandes ouvertes

        self.force = 0.0
        self.rep_active = False
        self.ev = RepEvaluator(self.cfg)
        self.countdown = 0.0

        self.running = True

    # ------------------------------------------------------------ session --
    def reset_session(self):
        self.serie = 0
        self.rep = 0
        self.score = 0
        self.combo = 0
        self.jauge = 20.0          # % Cerbere repousse
        self.serie_scores = []
        self.grades = []
        self.serie_score = 0
        self.said = set()          # temps forts deja joues dans la serie
        self.last_beat = None

    def say(self, who, txt, color=None):
        self.speaker = who
        self.msg = txt
        self.msg_color = color or WHITE

    def beat(self, grade):
        """Choisit une replique du registre, en evitant celle d'avant."""
        pool = [b for b in BEATS[grade] if b != self.last_beat] or BEATS[grade]
        b = random.choice(pool)
        self.last_beat = b
        return b

    # -------------------------------------------------------------- boucle --
    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self.events()
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()

    # -------------------------------------------------------------- events --
    def events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    # pendant la cinematique, ECHAP la passe au lieu de
                    # quitter : personne ne veut relire l'intro dix fois
                    if self.state == "intro":
                        self.cine.skip_all()
                    else:
                        self.running = False
                else:
                    self.key(e.key)
            elif e.type == pygame.JOYBUTTONDOWN:
                self.key(pygame.K_RETURN)

    def key(self, k):
        if self.wipe.active():
            return

        if self.state == "intro":
            if k in (pygame.K_RETURN, pygame.K_SPACE):
                self.cine.skip_line()
            return

        if self.state == "tuto":
            if k in (pygame.K_RETURN, pygame.K_SPACE):
                self.wipe.start(lambda: setattr(self, "state", "config"))
            return

        if self.state == "calib":
            if k in (pygame.K_RETURN, pygame.K_SPACE):
                self.calib_next()
            elif k == pygame.K_s:
                self.inp.mode = "mouse"
                self.state = "intro"

        elif self.state == "config":
            if k in (pygame.K_RETURN, pygame.K_SPACE):
                self.start_session()
            elif k == pygame.K_LEFT:
                self.cfg.charge = max(2, self.cfg.charge - 1)
            elif k == pygame.K_RIGHT:
                self.cfg.charge = min(20, self.cfg.charge + 1)
            elif k == pygame.K_UP:
                self.cfg.reps = min(15, self.cfg.reps + 1)
            elif k == pygame.K_DOWN:
                self.cfg.reps = max(4, self.cfg.reps - 1)
            elif k == pygame.K_d:
                self.cfg.difficulte = (self.cfg.difficulte + 1) % 3
            elif k == pygame.K_e:
                self.cfg.douleur_epaule = not self.cfg.douleur_epaule
            elif k == pygame.K_s:
                self.cfg.series = (self.cfg.series % 5) + 1

        elif self.state == "serie_end":
            if k in (pygame.K_RETURN, pygame.K_SPACE):
                self.next_serie()

        elif self.state == "session_end":
            if k in (pygame.K_RETURN, pygame.K_SPACE):
                self.wipe.start(lambda: setattr(self, "state", "config"))
            elif k == pygame.K_x:
                self.export_recap()

    # --------------------------------------------------------- calibration --
    def calib_next(self):
        vals = self.inp.axis_values()
        if not vals:
            self.inp.mode = "mouse"
            self.state = "config"
            return

        if self.calib_step == 0:
            self.calib_rest = vals[:]
            self.calib_step = 1
        else:
            # l'axe qui a le plus bouge = la gachette
            deltas = [abs(v - r) for v, r in zip(vals, self.calib_rest)]
            best = max(range(len(deltas)), key=lambda i: deltas[i])
            if deltas[best] < 0.35:
                self.msg = "Presse bien R2 a fond, puis valide."
                return
            self.inp.axis = best
            self.inp.rest = self.calib_rest[best]
            self.inp.full = vals[best]
            self.inp.mode = "pad"
            self.wipe.start(lambda: setattr(self, "state", "config"))

    # ------------------------------------------------------------ sequence --
    def start_session(self):
        self.reset_session()
        self.ev = RepEvaluator(self.cfg)
        self.say("HERCULE", "Trois gueules, une chaine. Commencons.")
        self.wipe.start(self.begin_count)

    def begin_count(self):
        self.state = "count"
        self.countdown = 3.0

    def next_serie(self):
        if self.serie + 1 >= self.cfg.series:
            self.wipe.start(lambda: setattr(self, "state", "session_end"))
            return
        self.serie += 1
        self.rep = 0
        self.serie_score = 0
        self.jauge = 20.0
        self.combo = 0
        self.said = set()
        self.say("LE NARRATEUR", "Cerbere reprend sa position. Serie suivante.")
        self.wipe.start(self.begin_count)

    def end_serie(self):
        self.serie_scores.append(self.serie_score)
        self.wipe.start(lambda: setattr(self, "state", "serie_end"))

    # -------------------------------------------------------------- update --
    def update(self, dt):
        self.clock_t += dt
        self.wipe.update(dt)
        self.flash = max(0.0, self.flash - dt * 3.2)
        self.shake = max(0.0, self.shake - dt * 3.5)
        self.speedlines = max(0.0, self.speedlines - dt * 2.4)
        self.roar = max(0.0, self.roar - dt * 1.6)
        if self.ring > 0:
            self.ring = min(1.2, self.ring + dt * 1.9)
        self.floats = [(t, x, y - 70 * dt, life - dt, c)
                       for (t, x, y, life, c) in self.floats if life > 0]

        self.force = self.inp.read()

        if self.state == "intro":
            self.cine.update(dt)
            # sans le garde-fou sur wipe.active(), la transition serait
            # relancee a chaque image et n'atteindrait jamais son milieu,
            # ou se declenche le changement d'ecran
            if self.cine.done and not self.wipe.active():
                self.wipe.start(lambda: setattr(self, "state", "tuto"))
            return

        # le decor continue de vivre dans tous les autres ecrans
        self.gate.update(dt, self.clock_t)

        if self.state == "tuto":
            self.tuto.update(dt)

        elif self.state == "count":
            self.countdown -= dt
            if self.countdown <= 0:
                self.state = "play"
                self.ev.reset()
                self.rep_active = False

        elif self.state == "play" and not self.wipe.active():
            self.update_play(dt)

    def update_play(self, dt):
        f = self.force
        lo, hi = self.cfg.band()

        if not self.rep_active:
            # on demarre une rep des que le patient commence a tirer
            if f > DEADZONE:
                self.rep_active = True
                self.ev.reset()
                self.ev.feed(f, dt)
        else:
            self.ev.feed(f, dt)

            if self.ev.in_band_time >= self.cfg.hold_required():
                self.finish_rep()
            elif f <= DEADZONE * 0.7 and self.ev.t > 0.35:
                # relache trop tot : pas de rep comptee, pas de sanction
                self.rep_active = False
                self.say("LE NARRATEUR",
                         "Traction relachee trop tot. Tiens la zone.", GREY)

        # Cerbere revient doucement si le patient ne tire pas
        if f < DEADZONE:
            self.jauge = max(0.0, self.jauge - dt * 1.6)

    def finish_rep(self):
        grade, pts, msg = self.ev.grade()
        self.rep_active = False
        self.ev.reset()

        if grade in ("parfait", "bon"):
            self.combo += 1
        else:
            self.combo = 0

        mult = 1 + min(self.combo, 5) * 0.08
        gained = int(round(pts * mult))
        self.score += gained
        self.serie_score += gained
        self.grades.append(grade)

        delta = {"parfait": 12, "bon": 8, "acceptable": 3, "mauvais": -5}[grade]
        self.jauge = max(0.0, min(100.0, self.jauge + delta))

        color = {"parfait": GOLD, "bon": GREEN,
                 "acceptable": WHITE, "mauvais": RED}[grade]

        # Sur un mouvement fautif, le conseil clinique prime sur la mise en
        # scene : le patient doit savoir QUOI corriger. Sinon, on raconte.
        if grade in ("acceptable", "mauvais"):
            self.say("LE COACH", msg, color)
        else:
            who, line = self.beat(grade)
            self.say(who, line, color)

        # le gain apparait sur la bete : c'est elle qui encaisse
        self.floats.append(("+%d" % gained, 640 + random.randint(-40, 40),
                            H // 2 - 60, 0.9, color))

        if grade == "parfait":
            self.flash = 1.0
            self.speedlines = 1.0
            self.ring = 0.01
            self.roar = 1.0
        elif grade == "mauvais":
            self.shake = 1.0
            self.roar = 1.0

        # temps forts : une seule fois chacun par serie
        for seuil, (who, line) in MILESTONES:
            if self.jauge >= seuil and seuil not in self.said:
                self.said.add(seuil)
                self.say(who, line, GOLD)
                self.roar = 1.0

        self.rep += 1
        if self.rep >= self.cfg.reps:
            self.end_serie()

    # -------------------------------------------------------------- export --
    def export_recap(self):
        total = len(self.grades)
        perf = self.grades.count("parfait")
        qual = (sum({"parfait": 10, "bon": 7, "acceptable": 3, "mauvais": 1}[g]
                    for g in self.grades) / total) if total else 0
        data = {
            "outil": "Gym Of Legends",
            "scenario": "Hercule vs Cerbere",
            "date": datetime.now().isoformat(timespec="seconds"),
            "config": {
                "mouvement": self.cfg.mouvement, "charge_kg": self.cfg.charge,
                "series": self.cfg.series, "reps": self.cfg.reps,
                "difficulte": self.cfg.label_diff(),
                "douleur_epaule": self.cfg.douleur_epaule,
            },
            "resultats": {
                "score_total": self.score,
                "score_par_serie": self.serie_scores,
                "reps_total": total,
                "pct_parfaits": round(perf / total * 100) if total else 0,
                "indice_qualite_sur_10": round(qual, 1),
            },
        }
        with open("recap_seance_kine.json", "w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2, ensure_ascii=False)
        self.msg = "Recap exporte -> recap_seance_kine.json"
        self.msg_color = GREEN

    # ---------------------------------------------------------------- draw --
    def txt(self, surf, text, font, color, x, y, center=False, right=False,
            glow=None):
        anchor = "center" if center else ("right" if right else "left")
        return A.text(surf, text, font, color, x, y, anchor=anchor, glow=glow)

    def draw(self):
        sc = self.screen

        if self.state == "intro":
            self.cine.draw(sc)
            self.wipe.draw(sc)
            return

        ox = int(math.sin(pygame.time.get_ticks() * 0.05) * 13 * self.shake)
        oy = int(math.cos(pygame.time.get_ticks() * 0.07) * 9 * self.shake)

        if self.state == "tuto":
            self.tuto.draw(sc, self.gate, self.clock_t)
        elif self.state == "calib":
            self.draw_calib(sc)
        elif self.state == "config":
            self.draw_config(sc)
        elif self.state in ("play", "count"):
            self.draw_arena(sc, ox, oy)
        elif self.state == "serie_end":
            self.draw_serie_end(sc)
        elif self.state == "session_end":
            self.draw_session_end(sc)

        if self.flash > 0:
            A.color_grade(sc, (255, 246, 226), 0.42 * self.flash)

        self.wipe.draw(sc)

    # ---- fond commun aux ecrans hors arene : le decor, mis en retrait ----
    def draw_backdrop(self, sc, dim=0.68):
        self.gate.draw(sc, self.clock_t)
        A.color_grade(sc, (6, 5, 9), dim)

    def panel(self, sc, rect, alpha=185):
        """Cartouche sombre : rend le texte lisible par-dessus le decor."""
        s = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        s.fill((6, 5, 9, alpha))
        sc.blit(s, rect.topleft)
        pygame.draw.rect(sc, GREY_DARK, rect, 2, border_radius=6)
        pygame.draw.line(sc, GOLD, (rect.x, rect.y), (rect.x, rect.y + 46), 4)

    # ---------------------------------------------------------- calibration --
    def draw_calib(self, sc):
        self.draw_backdrop(sc, 0.74)
        self.txt(sc, "CALIBRATION", self.f_big, GOLD, W // 2, 116,
                 center=True, glow=A.GOLD_DIM)
        self.txt(sc, "Manette detectee : %s" % (self.pad_name or "aucune"),
                 self.f_small, GREY, W // 2, 162, center=True)

        instr = ("1 / 2   -   RELACHE completement R2, puis valide"
                 if self.calib_step == 0 else
                 "2 / 2   -   PRESSE R2 A FOND et garde, puis valide")
        self.txt(sc, instr, self.f_mid, WHITE, W // 2, 226, center=True)

        # barres live de tous les axes : on voit lequel bouge
        vals = self.inp.axis_values()
        bx, by = W // 2 - 260, 292
        for i, v in enumerate(vals[:8]):
            y = by + i * 32
            pygame.draw.rect(sc, GREY_DARK, (bx, y, 520, 17), border_radius=8)
            fill = int((v + 1) / 2 * 520)
            moved = self.calib_step == 1 and self.calib_rest and \
                i < len(self.calib_rest) and abs(v - self.calib_rest[i]) > 0.35
            pygame.draw.rect(sc, ORANGE if moved else GREY,
                             (bx, y, max(2, fill), 17), border_radius=8)
            self.txt(sc, "axe %d" % i, self.f_tiny, GREY, bx - 14, y + 8, right=True)

        self.txt(sc, "[ENTREE] valider     [S] jouer a la souris     [ECHAP] quitter",
                 self.f_small, GREY, W // 2, H - 54, center=True)

    # --------------------------------------------------------------- config --
    def draw_config(self, sc):
        self.draw_backdrop(sc, 0.72)
        lo, hi = self.cfg.band()

        self.txt(sc, "POSTE KINE", self.f_big, GOLD, 88, 92, glow=A.GOLD_DIM)
        self.txt(sc, "Ecran masque au patient - regle la seance",
                 self.f_small, GREY, 92, 138)
        pygame.draw.line(sc, A.GOLD_DIM, (88, 162), (560, 162), 2)

        rows = [
            ("Mouvement", self.cfg.mouvement, "", WHITE),
            ("Charge", "%d kg" % self.cfg.charge, "[<-] [->]", WHITE),
            ("Series", "%d" % self.cfg.series, "[S]", WHITE),
            ("Repetitions / serie", "%d" % self.cfg.reps, "[HAUT] [BAS]", WHITE),
            ("Difficulte", self.cfg.label_diff(), "[D]", GOLD),
            ("Douleur d'epaule", "OUI" if self.cfg.douleur_epaule else "NON",
             "[E]", RED if self.cfg.douleur_epaule else GREY),
        ]
        y = 214
        for label, val, hint, col in rows:
            self.txt(sc, label, self.f_small, GREY, 92, y)
            self.txt(sc, val, self.f_mid, col, 430, y)
            if hint:
                self.txt(sc, hint, self.f_tiny, GREY_DARK, 640, y)
            y += 54

        # apercu direct de ce que la config produit
        box = pygame.Rect(W - 470, 214, 380, 300)
        self.panel(sc, box)
        self.txt(sc, "CE QUE LE PATIENT AURA", self.f_tiny, GOLD, box.x + 22,
                 box.y + 26)
        A.force_gauge(sc, box.x + 42, box.y + 82, 40, 178,
                      (lo + hi) / 2, lo, hi)
        info = [("Zone cible", "%d %% -> %d %%" % (lo * 100, hi * 100)),
                ("Tenue requise", "%.1f s" % self.cfg.hold_required()),
                ("Tolerance", "x%.2f" % self.cfg.tolerance())]
        yy = box.y + 88
        for k, v in info:
            self.txt(sc, k, self.f_small, GREY, box.x + 150, yy)
            self.txt(sc, v, self.f_mid, WHITE, box.x + 150, yy + 26)
            yy += 68

        mode = "R2 (manette)" if self.inp.mode == "pad" else "SOURIS (secours)"
        self.txt(sc, "Controle : %s" % mode, self.f_small, ORANGE, 92, y + 16)

        label = "[ENTREE]   LANCER LA QUETE"
        btn = pygame.Rect(88, H - 118, self.f_mid.size(label)[0] + 58, 60)
        pygame.draw.rect(sc, GOLD, btn, border_radius=6)
        self.txt(sc, label, self.f_mid, INK, btn.x + 28, btn.centery)

    # ---------------------------------------------------------------- arene --
    def draw_arena(self, sc, ox, oy):
        lo, hi = self.cfg.band()
        f = self.force
        gy = self.gate.ground_y

        # --- decor ---
        self.gate.draw(sc, self.clock_t, shake=(ox, oy))

        # --- acteurs ---
        # La jauge pousse Cerbere vers le portail : sa position EST le score.
        # Ils se tiennent au-dessus de gate.ground_y pour que les pattes
        # restent visibles au-dessus du cartouche de dialogue.
        cerb_x = 778 + (self.jauge / 100.0) * 172 + ox
        tension = max(0.0, min(1.0, f / max(0.15, hi)))
        aggro = 0.45 + 0.45 * (1.0 - self.jauge / 100.0) + 0.2 * self.roar
        jaws = 0.35 + 0.45 * tension + 0.35 * self.roar

        # Echelle 1.0 pour les deux : toute autre valeur impose un
        # redimensionnement lisse du calque a chaque recomposition, ce qui
        # est le poste le plus cher du rendu. La taille relative se regle
        # par la geometrie, pas par un facteur d'echelle.
        grip = self.herc.draw(sc, 252 + ox, gy - 12 + oy, 1.0, self.clock_t,
                              pull=tension)
        self.cerb.draw(sc, cerb_x, gy + oy, 1.0, self.clock_t,
                       aggro=min(1.0, aggro), strain=tension,
                       jaws=min(1.0, jaws))
        # la chaine s'accroche au collier, pas dans le vide devant la bete
        collar = (cerb_x - 72, gy - 172 + oy)
        A.chain(sc, grip, collar, tension=tension, s=1.0, t=self.clock_t)

        # --- ponctuations ---
        if self.speedlines > 0:
            A.speed_lines(sc, W // 2, H // 2 - 40, self.speedlines, A.WHITE, 30)
        if 0 < self.ring < 1.0:
            A.impact_ring(sc, cerb_x - 200, gy - 160, self.ring)
        elif self.ring >= 1.0:
            self.ring = 0.0

        # (le vignettage est deja cuit dans le decor : rien a recoller ici)

        # --- jauge de force : le coeur du retour visuel ---
        hold = (self.ev.in_band_time / self.cfg.hold_required()
                if self.rep_active else 0.0)
        A.force_gauge(sc, 52, 168, 48, 316, f, lo, hi,
                      hold=hold if self.rep_active else None)

        self.draw_hud(sc)
        self.draw_voice(sc)

        # --- decompte ---
        if self.state == "count":
            A.color_grade(sc, (6, 5, 9), 0.62)
            n = int(math.ceil(self.countdown))
            k = 1.0 - (self.countdown - int(self.countdown))
            sz = int(96 + 40 * (1 - k))
            fnt = A.font(A.FAM_DISPLAY, sz)
            self.txt(sc, str(max(1, n)), fnt, GOLD, W // 2, H // 2 - 20,
                     center=True, glow=A.GOLD_DIM)
            self.txt(sc, "PRENDS LA CHAINE", self.f_mid, WHITE, W // 2,
                     H // 2 + 56, center=True)

    # ------------------------------------------------------------------ HUD --
    def band(self, w, h, alpha):
        """Bandeau semi-opaque reutilisable (ils sont recolles a chaque image)."""
        key = (w, h, alpha)
        s = self._bands.get(key)
        if s is None:
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            s.fill((5, 4, 8, alpha))
            self._bands[key] = s
        return s

    def draw_hud(self, sc):
        sc.blit(self.band(W, 96, 150), (0, 0))

        self.txt(sc, "SERIE", self.f_tiny, GREY, 84, 34)
        self.txt(sc, "%d/%d" % (self.serie + 1, self.cfg.series),
                 self.f_mid, WHITE, 84, 62)
        self.txt(sc, "REPETITION", self.f_tiny, GREY, 208, 34)
        self.txt(sc, "%d/%d" % (self.rep, self.cfg.reps),
                 self.f_mid, WHITE, 208, 62)

        self.txt(sc, str(self.score), self.f_big, GOLD, W - 84, 54,
                 right=True, glow=A.GOLD_DIM)
        self.txt(sc, "SCORE", self.f_tiny, GREY, W - 84, 88, right=True)
        if self.combo > 1:
            c = GOLD if self.combo >= 5 else GREEN
            self.txt(sc, "COMBO x%d" % self.combo, self.f_mid, c,
                     W - 210, 62, right=True)

        # barre de progression : jusqu'ou Cerbere a recule
        bx, bw = W // 2 - 210, 420
        self.txt(sc, "CERBERE REPOUSSE", self.f_tiny, GREY, W // 2, 30,
                 center=True)
        pygame.draw.rect(sc, (0, 0, 0), (bx - 3, 45, bw + 6, 16),
                         border_radius=8)
        pygame.draw.rect(sc, GREY_DARK, (bx, 48, bw, 10), border_radius=5)
        fw = int(bw * self.jauge / 100.0)
        if fw > 2:
            pygame.draw.rect(sc, ORANGE, (bx, 48, fw, 10), border_radius=5)
            A.glow(sc, bx + fw, 53, 26, ORANGE, 150)
        for seuil, _ in MILESTONES:
            mx = bx + int(bw * seuil / 100.0)
            pygame.draw.line(sc, GOLD if seuil in self.said else GREY_DARK,
                             (mx, 42), (mx, 64), 2)

        # points flottants
        for t, x, y, life, c in self.floats:
            img = self.f_mid.render(t, True, c)
            img.set_alpha(int(255 * min(1.0, life * 1.6)))
            sc.blit(img, img.get_rect(center=(int(x), int(y))))

    # ------------------------------------------------------------- voix off --
    def draw_voice(self, sc):
        """Cartouche de dialogue : c'est lui qui porte le recit pendant le QTE."""
        h = 92
        sc.blit(self.band(W, h, 214), (0, H - h))
        pygame.draw.line(sc, GREY_DARK, (0, H - h), (W, H - h), 2)
        pygame.draw.line(sc, GOLD, (0, H - h), (150, H - h), 3)

        if self.speaker:
            self.txt(sc, self.speaker, self.f_tiny, GOLD, 60, H - h + 22)
        self.txt(sc, self.msg, self.f_line, self.msg_color, 60, H - h + 58)

    # ------------------------------------------------------------ fin serie --
    def draw_serie_end(self, sc):
        self.draw_backdrop(sc, 0.7)
        last = self.serie_scores[-1] if self.serie_scores else 0
        prev = self.serie_scores[-2] if len(self.serie_scores) > 1 else None

        self.txt(sc, "SERIE %d TERMINEE" % len(self.serie_scores),
                 self.f_tiny, GREY, W // 2, 172, center=True)
        self.txt(sc, str(last), self.f_huge, GOLD, W // 2, 240, center=True,
                 glow=A.GOLD_DIM)
        self.txt(sc, "POINTS", self.f_mid, GREY, W // 2, 300, center=True)

        if prev is not None:
            d = last - prev
            col = GREEN if d >= 0 else RED
            self.txt(sc, "%+d vs serie precedente" % d, self.f_mid, col,
                     W // 2, 356, center=True)
        else:
            self.txt(sc, "Cerbere a recule. Ne relache pas.", self.f_line,
                     WHITE, W // 2, 356, center=True)

        # detail des notes de la serie
        n = self.cfg.reps
        recent = self.grades[-n:]
        counts = [("PARFAIT", recent.count("parfait"), GOLD),
                  ("BON", recent.count("bon"), GREEN),
                  ("PASSABLE", recent.count("acceptable"), WHITE),
                  ("RATE", recent.count("mauvais"), RED)]
        x = W // 2 - 330
        for lab, c, col in counts:
            self.txt(sc, str(c), self.f_big, col, x + 78, 442, center=True)
            self.txt(sc, lab, self.f_tiny, GREY, x + 78, 486, center=True)
            x += 176

        nxt = ("VOIR LE RECAP KINE" if self.serie + 1 >= self.cfg.series
               else "SERIE SUIVANTE")
        self.txt(sc, "[ENTREE]  %s" % nxt, self.f_mid, GOLD, W // 2, H - 92,
                 center=True, glow=A.GOLD_DIM)

    # ---------------------------------------------------------- fin seance --
    def draw_session_end(self, sc):
        self.draw_backdrop(sc, 0.76)
        total = len(self.grades)
        perf = self.grades.count("parfait")
        pct = round(perf / total * 100) if total else 0

        self.txt(sc, "RECAP KINE", self.f_big, GOLD, 88, 88, glow=A.GOLD_DIM)
        self.txt(sc, "%s  -  %d kg  -  %d series  -  %s" %
                 (self.cfg.mouvement, self.cfg.charge, self.cfg.series,
                  self.cfg.label_diff()),
                 self.f_small, GREY, 92, 134)
        pygame.draw.line(sc, A.GOLD_DIM, (88, 158), (700, 158), 2)

        stats = [("SCORE TOTAL", str(self.score), GOLD),
                 ("REPETITIONS", str(total), WHITE),
                 ("MOUVEMENTS PARFAITS", "%d %%" % pct, GREEN)]
        for i, (lab, val, col) in enumerate(stats):
            x = 92 + i * 330
            self.txt(sc, lab, self.f_tiny, GREY, x, 208)
            self.txt(sc, val, self.f_huge, col, x, 262, glow=A.GOLD_DIM
                     if col is GOLD else None)

        self.txt(sc, "SCORE PAR SERIE", self.f_tiny, GREY, 92, 358)
        mx = max(self.serie_scores) if self.serie_scores else 1
        for i, s in enumerate(self.serie_scores):
            y = 396 + i * 42
            self.txt(sc, "S%d" % (i + 1), self.f_small, GREY, 92, y + 10)
            pygame.draw.rect(sc, GREY_DARK, (148, y, 620, 20), border_radius=10)
            wd = int(620 * s / max(1, mx))
            if wd > 3:
                pygame.draw.rect(sc, GOLD, (148, y, wd, 20), border_radius=10)
            self.txt(sc, str(s), self.f_mid, GOLD, 800, y + 10)

        self.txt(sc, "[X] exporter le recap JSON        [ENTREE] nouvelle seance",
                 self.f_small, GREY, 92, H - 84)
        if "Recap" in self.msg:
            self.txt(sc, self.msg, self.f_small, GREEN, 92, H - 52)



if __name__ == "__main__":
    Game().run()
