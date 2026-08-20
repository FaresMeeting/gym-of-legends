# Gym Of Legends

QTE narratif de rééducation. Le patient exécute un **Face-Pull** ; dans le jeu,
Hercule retient Cerbère au bout d'une chaîne. La qualité du geste — pas la
force brute — décide de tout.

Prototype conçu pour être branché plus tard sur une **poulie instrumentée**.

---

## Lancer le jeu

Double-cliquer sur `Lancer-Gym-Of-Legends.bat`, ou :

```bash
python gym_of_legends.py
```

**Prérequis** : Python 3.9+ et pygame.

```bash
pip install -r requirements.txt
```

## Contrôles

| Entrée | Effet |
|---|---|
| Gâchette **R2** (manette) | La pression = la force de traction |
| **Souris** (secours) | Plus le curseur est bas dans la fenêtre, plus on tire fort |
| `Entrée` | Valider / avancer |
| `Échap` | Passer la cinématique, puis quitter |

Au poste kiné : `←` `→` la charge, `↑` `↓` les répétitions, `D` la difficulté,
`S` le nombre de séries, `E` la douleur d'épaule.

## Le geste

1. **Tirer** — monter progressivement, sans à-coup, jusqu'à la zone verte.
2. **Tenir** — se stabiliser *dans* la zone le temps que l'anneau se remplisse.
3. **Relâcher** — doucement. Cerbère recule d'un pas.

---

## Architecture

Trois modules, une responsabilité chacun :

| Fichier | Rôle |
|---|---|
| `gym_of_legends.py` | Machine à états, évaluation clinique du geste, HUD, export |
| `gol_art.py` | Décor, personnages, éclairage, particules, post-traitement |
| `gol_cinematic.py` | Cinématique d'ouverture et écran d'explication |

### Deux points à connaître avant de toucher au code

**1. Le visuel est entièrement généré par le code.** Aucune image, aucun asset
externe : uniquement des polygones, des dégradés et des particules. C'est un
choix délibéré — il garantit que le projet est libre de droits (voir plus bas)
et qu'il tient dans trois fichiers texte, faciles à fusionner à deux.

**2. Le rendu est sous contrainte de performance.** Une version naïve tournait
à 5 images/seconde. Quatre mécanismes la maintiennent aujourd'hui à ~80 :

- les halos et taches douces sont **mis en cache avec une quantification
  agressive** du rayon et de l'intensité (`glow`, `soft_blob`) ;
- les personnages sont **composés en sprites rafraîchis à 18 ips**, comme dans
  un jeu de combat 2D — seule leur *position* bouge à 60 ips (`SpriteCache`) ;
- le décor animé est **mis en cache à 30 ips** (`HellGate.FRAME_RATE`) ;
- l'éclairage des personnages utilise `BLEND_MULT` / `BLEND_ADD`, qui ne
  touchent pas le canal alpha et **évitent donc un masque** (`soft_shade`).

Si tu ajoutes un effet, mesure avant/après. Un `pygame.Surface(...)` créé dans
une boucle de rendu, ou un halo dont l'intensité varie en continu sans
quantification, suffit à faire chuter le framerate de moitié.

### Point d'intégration de la poulie

Tout passe par `InputSource.read()` dans `gym_of_legends.py`, qui renvoie une
force normalisée `0.0 → 1.0`. Le jour où le capteur est prêt, ajouter un mode
`"poulie"` qui renvoie `charge_lue / charge_max`. **Rien d'autre ne change.**

---

## Droits d'auteur

Le visuel est une création originale, générée par le code : aucune image,
aucun asset téléchargé, aucun tracé d'une œuvre existante.

Cerbère est une figure de la **mythologie grecque**, donc du domaine public.
Ce sont les *représentations* particulières (illustrations d'artistes,
personnages de jeux) qui sont protégées, et le projet n'en reproduit aucune.
Les attributs utilisés — trois têtes, queue de serpent, chien massif, portail
des Enfers — sont des éléments mythologiques génériques, non appropriables.

**Règle à tenir** : ne jamais ajouter d'image, de police ou de son téléchargé
sans en vérifier la licence. Le projet perdrait sa principale garantie.

---

## Travailler à deux

Voir [CONTRIBUTING.md](CONTRIBUTING.md).
