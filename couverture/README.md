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
6 onglets, mêmes noms et le même ordre que le classeur Excel :
Synthèse · Daily View PM · Daily View Appro · Daily View France · Analyse · Analyse dépôt.
Les filtres de la barre latérale reprennent ceux des TCD Excel (Code ABC, BES/BSP, fenêtre « A PRENDRE » de 30 jours,
schéma contingent). L'historique et l'export Excel sont dans des menus déroulants de la barre latérale, pas des onglets.

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
