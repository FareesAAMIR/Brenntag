# Indicateur de couverture – application Streamlit

Données brutes → nettoyage → KPI → TCD → dashboard. Voir `ANALYSE_FICHIER.md` pour l'analyse du classeur Excel d'origine.

## Installation et lancement
```bash
pip install -r requirements.txt
streamlit run app.py
```
Streamlit ≥ 1.50 requis (`width="stretch"`, `height="content"`). `python-calamine` est facultatif mais accélère
la lecture des gros onglets.

## Comportement : rien sans fichier
L'application n'affiche **aucun chiffre** tant qu'aucun fichier n'a été déposé — pas de données de démonstration
chargées par défaut. La page **Format des données** (dernière page du menu) reste consultable sans fichier : elle
explique quels fichiers déposer et la structure de colonnes attendue pour chacun.

## Structure de l'interface
Rendu « outil BI d'entreprise » : sidebar bleu nuit à fort contraste, contenu principal clair, cartes KPI,
titres de section, police et grille cohérents sur toutes les pages (voir le bloc CSS en tête de `app.py`).
Chaque widget de la sidebar qui garde nativement un fond clair (boutons, dépôt de fichiers, champs de saisie,
sélecteurs) est explicitement recoloré pour rester lisible sur fond sombre. Aucun emoji dans l'interface.

Navigation en **haut de la barre latérale gauche** (section « NAVIGATION », avant « Données » et « Filtres »),
7 pages : Synthèse · Daily View PM · Daily View Appro · Daily View France · Analyse · Analyse dépôt ·
Format des données. La page active a un fond vert plein + une barre d'accent à gauche.

- Toutes les dates s'affichent en **JJ/MM/AAAA**, sans heure (KPI, tableaux, graphiques, tooltips).
- Chaque page met en avant, avant les tableaux détaillés, un ou deux graphiques répondant à une question métier
  précise plutôt que des graphiques génériques ou décoratifs.
- **Synthèse** s'ouvre sur une rangée de cartes KPI avec variation par rapport à la semaine précédente.
- Dans **Analyse**, les deux graphiques sur les articles sous stock de sécurité sont tout en haut de la page.
- Un bouton « Faire une recommandation » en bas de la barre latérale renvoie vers `FEEDBACK_FORM_URL` (constante
  en tête de `app.py`, à remplacer par votre formulaire interne).
- La barre latérale rappelle qu'il faut importer les données en déposant le fichier (onglet **BASE** obligatoire).
- Les filtres reprennent ceux des TCD Excel (Code ABC, BES/BSP, fenêtre « A PRENDRE » de 30 jours, schéma contingent).

## Utilisation hebdomadaire
1. Onglet **Format des données** : vérifier la structure attendue si besoin.
2. Déposer dans la barre latérale **l'extraction BASE** (obligatoire) et, si vous en avez un, l'onglet
   **Suivi évolution** (pour les tendances). Un classeur complet ou des fichiers séparés (.xlsx/.csv) fonctionnent :
   les onglets bruts sont détectés automatiquement, les onglets de résultats sont ignorés.
3. Menu **Historique & export** : télécharger l'historique mis à jour (à redéposer la semaine suivante — rien
   n'est conservé automatiquement d'une session à l'autre), ou exporter toutes les analyses en classeur Excel.

Les tables PM / Gest. embarquées (`data/ref_*.csv`) sont une copie du cache de `FR_TABLES.xlsx` ; déposez le vrai
fichier pour les remplacer.

## Structure du code
```
app.py                    interface (7 pages)
couverture/config.py      constantes métier, alias d'en-têtes, palette
couverture/loaders.py     détection des onglets bruts, lecture, nettoyage des nombres
couverture/logic.py       BASE enrichie (ETAT, ETAT2, mappings), instantané « TCD aide »
couverture/history.py     historique : normalisation, ajout, fenêtre « A PRENDRE »
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
