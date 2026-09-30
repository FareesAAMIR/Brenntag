# Indicateur de couverture – application Streamlit

Données brutes → nettoyage → KPI → TCD → dashboard. Voir `ANALYSE_FICHIER.md` pour l'analyse du classeur Excel.

## Installation et lancement
```bash
pip install -r requirements.txt
streamlit run app.py
```
Streamlit ≥ 1.50 requis (`width="stretch"`). `python-calamine` est facultatif mais divise le temps de lecture du classeur.

## Utilisation hebdomadaire
1. Déposer dans la barre latérale **l'extraction BASE** (le classeur complet, l'onglet seul en .xlsx ou un .csv). Les onglets bruts sont reconnus automatiquement ; les onglets de résultats sont ignorés.
2. Vérifier la **date** (déduite du nom de fichier `…AAAA_MM_JJ…`).
3. Onglet **📈 Historique** → *Enregistrer* (écrit `data/historique.csv.gz`) ou *Télécharger* l'historique mis à jour. C'est l'équivalent du collage du « TCD aide » dans « Suivi évolution ».

L'historique de départ (`data/historique.csv.gz`, 299 dates jusqu'au 12/08/2026) est déjà extrait de votre classeur : il est chargé automatiquement si aucun historique n'est déposé.
Les tables PM / Gest. embarquées (`data/ref_*.csv`) sont une copie du cache de `FR_TABLES.xlsx` ; déposez le vrai fichier pour les remplacer.
> Sur un hébergement au disque éphémère (ex. Streamlit Community Cloud), l'enregistrement local ne persiste pas : utilisez le téléchargement et rechargez le CSV la semaine suivante.

## Structure de l'interface
Rendu « outil BI d'entreprise » : sidebar bleu nuit à fort contraste, contenu principal clair, cartes KPI,
titres de section, police et grille cohérents sur toutes les pages (voir le bloc CSS en tête de `app.py`).
Chaque widget de la sidebar qui garde nativement un fond clair (boutons, dépôt de fichiers, champs de saisie,
sélecteurs) est explicitement recoloré pour rester lisible sur fond sombre.

Navigation en **haut de la barre latérale gauche** (section « NAVIGATION », avant « Données » et « Filtres »),
6 pages dans l'ordre du classeur Excel : Synthèse · Daily View PM · Daily View Appro · Daily View France ·
Analyse · Analyse dépôt. La page active a un fond vert plein + une barre d'accent à gauche (pas seulement un
texte plus foncé). Aucun emoji dans l'interface.

- Toutes les dates s'affichent en **JJ/MM/AAAA**, sans heure (KPI, tableaux, graphiques, tooltips).
- Le graphique du taux de couverture hebdomadaire est volontairement grand (lignes très épaisses, gros marqueurs,
  un point = une semaine, aucun chevauchement des dates).
- Chaque page met en avant, avant les tableaux détaillés, un ou deux graphiques répondant à une question métier précise
  (combien d'articles posent problème, où, quelle évolution) plutôt que des graphiques génériques ou décoratifs.
- **Synthèse** s'ouvre sur une rangée de cartes KPI (taux de couverture, articles sous stock de sécurité, ruptures,
  articles suivis) avec variation par rapport à la semaine précédente.
- Dans **Analyse**, les deux graphiques sur les articles sous stock de sécurité (évolution + répartition) sont tout en haut de la page.
- Un bouton « Faire une recommandation » en bas de la barre latérale renvoie vers `FEEDBACK_FORM_URL` (constante en tête
  de `app.py`, à remplacer par votre formulaire interne).
- La barre latérale rappelle qu'il faut importer les données en déposant le fichier (onglet **BASE** obligatoire).
- Les filtres de la barre latérale reprennent ceux des TCD Excel (Code ABC, BES/BSP, fenêtre « A PRENDRE » de 30 jours,
  schéma contingent). L'historique et l'export Excel restent dans des menus déroulants de la barre latérale, pas des pages.

## Structure du code
```
app.py                    interface (6 onglets)
couverture/config.py      constantes métier, alias d'en-têtes
couverture/loaders.py     détection des onglets bruts, lecture, nettoyage des nombres
couverture/logic.py       BASE enrichie (ETAT, ETAT2, mappings), instantané « TCD aide »
couverture/history.py     historique : normalisation, ajout, persistance, fenêtre « A PRENDRE »
couverture/analyses.py    équivalents de tous les TCD / tableaux Excel + analyses ajoutées
couverture/charts.py      graphiques Plotly     couverture/export.py   export Excel
tests/                    tests unitaires       tools/valider_avec_excel.py   rapprochement avec Excel
```
Le moteur (`couverture/`) ne dépend pas de Streamlit : réutilisable en script ou en notebook.

## Tests
```bash
python -m unittest discover tests
python tools/valider_avec_excel.py "Indicateur_de_couverture_Weekly_2026_08_12.xlsx"
```
