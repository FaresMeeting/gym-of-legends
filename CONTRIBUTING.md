# Travailler à deux sur Gym Of Legends

Le projet tient dans trois gros fichiers Python. C'est pratique à lire, mais
ça veut dire qu'à deux, **vous allez vous marcher dessus si vous éditez le
même fichier en même temps**. Tout ce qui suit sert à éviter ça.

---

## La règle qui évite 90 % des conflits

**Répartissez-vous par fichier, pas par tâche.**

| Fichier | Ce qu'on y touche |
|---|---|
| `gol_art.py` | Personnages, décor, lumière, effets |
| `gol_cinematic.py` | Cinématique, écran d'explication |
| `gym_of_legends.py` | Règles, évaluation du geste, HUD, écrans de bilan |

Si vous devez tous les deux toucher `gol_art.py`, dites-le-vous **avant** de
commencer, et faites des branches courtes.

---

## Le cycle de travail

### Une seule fois, au début

```bash
git clone https://github.com/<compte>/gym-of-legends.git
cd gym-of-legends
pip install -r requirements.txt
```

Puis dis à git qui tu es (à faire par chacun, sur sa machine) :

```bash
git config user.name "Ton Prénom"
```

```bash
git config user.email "ton@email.com"
```

### À chaque fois que tu commences à travailler

```bash
git checkout main && git pull
```

Puis crée une branche pour ce que tu vas faire :

```bash
git checkout -b art/nouvelle-tete-cerbere
```

Nomme la branche `art/…`, `jeu/…`, `cine/…` ou `fix/…` — on voit tout de suite
qui touche à quoi.

### Pendant

Commite souvent, par petites étapes qui marchent :

```bash
git add -A && git commit -m "Cerbere : museau plus long et crocs irreguliers"
```

Un bon message dit **ce qui change et pourquoi**, pas « maj » ni « fix ».

### Quand c'est prêt

```bash
git push -u origin art/nouvelle-tete-cerbere
```

Puis ouvre une **Pull Request** sur GitHub. L'autre la relit, puis on fusionne.
Même à deux, la PR vaut le coup : c'est le seul moment où quelqu'un d'autre
regarde le code, et ça garde un historique lisible de *pourquoi* les choses
ont changé.

---

## Avant de pousser : la checklist

1. **Le jeu se lance et va jusqu'au bout.**
   Cinématique → explication → poste kiné → une série → bilan.

2. **Le framerate n'a pas chuté.**
   C'est le piège nº 1 de ce projet. Ajoute temporairement dans la boucle
   `Game.run()` :

   ```python
   print(round(self.clock.get_fps()))
   ```

   Dans l'arène, on doit rester **au-dessus de 60**. Si tu es descendu,
   relis la section « contrainte de performance » du README : le coupable
   est presque toujours une surface créée dans la boucle de rendu, ou un
   halo dont l'intensité varie en continu sans quantification.

3. **Aucun asset externe n'est entré dans le projet.**
   Pas d'image, pas de police, pas de son téléchargé. C'est ce qui garantit
   que le projet reste libre de droits.

4. **`recap_seance_kine.json` n'est pas dans le commit.**
   Il est déjà dans `.gitignore` — vérifie avec `git status` qu'il n'apparaît
   pas. Ce sont des données de séance, elles n'ont rien à faire sur GitHub.

---

## Quand ça coince

**« Mon `git push` est refusé »** — l'autre a poussé avant toi :

```bash
git pull --rebase origin main
```

Règle les éventuels conflits, puis repousse.

**« J'ai un conflit dans un fichier »** — git marque les zones avec
`<<<<<<<`, `=======`, `>>>>>>>`. Garde ce qu'il faut, efface les marqueurs,
puis `git add` le fichier et `git rebase --continue`.

**« J'ai tout cassé et je veux revenir en arrière »** — tant que tu n'as pas
poussé, ta branche ne concerne que toi :

```bash
git checkout . && git checkout main
```

Attention : cette commande **jette tes modifications non commitées**. Si tu
veux les garder de côté plutôt que les perdre, utilise `git stash -u` avant.

**« Le jeu ne se lance plus après un pull »** — vérifie d'abord que pygame est
installé dans le Python que tu utilises :

```bash
python -m pip install -r requirements.txt
```
