# Analyse du classeur « Indicateur de couverture » (Weekly 2026-08-12)

Classeur de 20 Mo : 13 onglets, 13 tableaux croisés dynamiques (TCD) sur 4 caches, 3 graphiques, 1 lien externe
(`…\ANALYSIS\FR_TABLES.xlsx`). L'analyse a été faite sur les XML du fichier (formules, définitions de TCD, caches).

## 1. Onglets : données brutes vs résultats

| Onglet | Nature | Détail | Dans l'appli |
|---|---|---|---|
| **BASE** (10 614 lignes) | **Brut** | Extraction SAP « Zsupply » en colonnes B→AI (constantes). Colonnes A et AJ→AQ = formules (VLOOKUP / IF), AR = commentaire PM saisi à la main. | À charger |
| **Suivi évolution** (175 208 lignes, 299 dates) | **Brut / mémoire** | Historique hebdomadaire *agrégé* (une ligne = un groupe PM × gestionnaire × ABC × ETAT2 × TYPE… avec `Nombre de Article`). Colonnes A→M constantes ; N « A PRENDRE » et O = formules. **Non reconstructible** : les anciennes BASE n'existent plus, c'est une mémoire. | À charger une fois, puis l'appli l'alimente |
| **PM** et **Gest.** de `FR_TABLES.xlsx` (lien externe) | **Référentiels bruts** — absents de votre liste initiale | Table PM (NOM PM → Niveau 1, Niveau 2 = TYPE, Manager = PMF BM, BES/BSP) et table Gest. (Code → Approvisionneur = QUI appro). Utilisées par les VLOOKUP de BASE. Une copie partielle est dans l'onglet **T**. | Copie embarquée dans `data/` ; remplaçable en chargeant `FR_TABLES.xlsx` |
| **TCD aide** | **Résultat** (pas une donnée brute) | TCD sur BASE, filtré `ETAT = MTS` et `Schéma contingent = # / vides`. C'est la « photo » de la semaine, collée à la main dans Suivi évolution avec la date du jour (procédure décrite dans l'onglet *Paramètres*). | Recalculé (`build_snapshot`) |
| Synthese, Daily VIEW PM / Appro / FRANCE, Analyse, Analyse DEPOT, KPI Achats (masqué) | **Résultats** | TCD + formules SOMME.SI.ENS sur Suivi évolution + graphiques | Recalculés |
| Paramètres (masqué), T, Reunion FH 14112023 (masqué) | Auxiliaires | Mode opératoire ; copie de tables de correspondance ; onglet ancien sans formule | Non repris |

**Conclusion sur votre hypothèse** : BASE et Suivi évolution sont bien les sources. **TCD aide n'en est pas une** (c'est un
TCD de BASE) et il manque les deux tables de correspondance PM / Gest.

## 2. Colonnes nécessaires

**BASE — indispensables** : `PM Nom`, `Code ABC`, `Stok initia` (col. E), `Qté stock libre`, `Article`, `Division`,
`Divison Nom`, `Schéma contigent.`, `Grpe planif.`, `Gestionnaire`, `Gestionnaire nom`.
**BASE — utilisées pour les extensions** : `Stock Sécu Form.`, `Stock Moyen`, `PMP`, `Unité prix de PMP`, `Valeur stock du jour €`,
`Impact FI si stk moyen`, `Artcile nom`, `Commentaire PM`. Les autres colonnes SAP (conso, lead time, MOQ, cuves…) ne
servent à aucun calcul du classeur ; elles sont acceptées et ignorées.
**Suivi évolution** : `Date`, `QUI appro`, `PMF BM`, `PM Nom`, `Code ABC`, `Code gestionnaire`, `Gestionnaire nom`, `ETAT2`,
`BES/BSP`, `TYPE`, `Nombre de Article` (les colonnes `ETAT` = toujours « MTS » et `Schéma` = toujours « # » sont constantes).

## 3. Relations entre onglets

```
FR_TABLES (PM, Gest.) ──VLOOKUP──▶ BASE ──TCD aide (MTS, hors contingent)──▶ [collage manuel + date] ──▶ Suivi évolution
                                     │                                                                     │
        Synthese (L34:R78, A15:H77) ◀┤                                                Synthese D5:L8, Daily VIEW PM/Appro/FRANCE,
        Analyse (A8:M42), Analyse DEPOT, KPI Achats                                    Analyse!A49 (SOMME.SI.ENS / TCD / graphiques)
```

## 4. Logique métier retrouvée

| Notion | Règle (formule Excel → Python) |
|---|---|
| **ETAT** (col. AK) | `Stok initia ≠ 0` → **MTS**, sinon **MTO** |
| **% couverture** (AM) | `Qté stock libre / Stok initia` (le stock de sécurité SAP – interprétation à confirmer par vous) |
| **ETAT2** (AN, catégories) | MTO → aucune. MTS : ratio = 0 → **RUPTURE** ; ≤ 0,5 → **Inf SS 0-50%** ; < 1 → **Inf SS 51-99%** ; sinon **OK** (un ratio négatif tombe donc dans 0-50 %, comme Excel) |
| **Sous stock de sécu formulaire** (AL) | `Qté stock libre ≤ Stock Sécu Form.` (MTS + MTO) |
| **PMF BM, BES/BSP, TYPE** (A, AO, AP) | VLOOKUP de `PM Nom` dans la table PM (Manager, BES/BSP, Niveau 2) |
| **QUI appro** (AJ) | VLOOKUP de `Gestionnaire` dans la table Gest. |
| **Taux de couverture** | `OK / (OK + Inf SS 51-99% + Inf SS 0-50% + RUPTURE)` — périmètre MTS, hors `SCHÉMA1 CONTINGENT` |
| **Valeur de stock** | `Qté libre × PMP / Unité prix` (recalculée = colonne SAP, contrôle OK) |
| **Impact FI si stock moyen** | `(Stock moyen − Qté libre) × PMP / Unité prix` (idem) |
| **A PRENDRE** | `AUJOURDHUI() − Date ≤ 30` → fenêtre glissante des vues « Daily » |
| **Trend Synthese D5:L8** | 9 dernières dates ; taux = Σ(OK) / Σ(toutes lignes) par date et BES/BSP |
| **Nettoyage de la colonne E** | commentaire de la cellule E1 : retirer `KG`, `PC`, `L`, `.` |

## 5. Correspondance onglet Excel → application

L'application reprend les 6 onglets du classeur (mêmes noms, même ordre) ; les autres onglets Excel
(Paramètres, T, KPI Achats masqué) sont des auxiliaires sans équivalent visible.

| Excel | Onglet Streamlit | Fonctions |
|---|---|---|
| Synthese (taux, PM, TYPE × Grpe planif.) | **Synthèse** | `taux_hebdo`, `synthese_par_pm`, `synthese_par_type_planif` |
| Daily VIEW PM | **Daily View PM** | `evolution_comptes`, `taux_par_date` |
| Daily VIEW Appro | **Daily View Appro** | `evolution_comptes`, `taux_par_date` |
| Daily VIEW FRANCE | **Daily View France** | `evolution_france`, `evolution_par_type` |
| Analyse (gestionnaire, PM × TYPE, historique) | **Analyse** | `analyse_gestionnaire`, `analyse_pm_type`, `historique_gestionnaire` |
| Analyse DEPOT | **Analyse dépôt** | `analyse_depot` |
| TCD aide | *(recalculé en arrière-plan)* | `build_snapshot` |
| KPI Achats (masqué) | export Excel uniquement | `kpi_achats` |

L'historique (enregistrer / télécharger) et l'export Excel sont dans des menus de la barre latérale, pas des onglets
supplémentaires, pour rester proche de la navigation Excel.

## 6. Validation (script `tools/valider_avec_excel.py`)

Comparaison aux valeurs mises en cache dans votre classeur : ETAT et ETAT2 identiques sur **10 614 / 10 614** lignes ;
taux Synthese D6:L8 identiques (écart 0) sur 9 dates ; TCD Synthese par PM, Analyse par gestionnaire, Analyse DEPOT et
Daily VIEW FRANCE identiques ; instantané du jour = dernière date de Suivi évolution, à l'attribut *PMF BM* près (voir ci-dessous).

## 7. Points d'attention relevés dans le fichier

1. **3 articles en `#VALEUR!`** : `Stok initia` contient « … M » (unité non listée dans la règle de nettoyage). Case « Reproduire les erreurs Excel » pour retrouver ce comportement ; décochée, l'unité est retirée.
2. **Deux dénominateurs différents** : les formules de Synthese (D6:L8) comptent aussi les lignes `#VALEUR!` (40 sur tout l'historique), les TCD non. Les deux sont reproduits.
3. **PMF BM de FRLBOUYA** : vide dans le classeur (cache du VLOOKUP), « C. Stella » dans la copie de FR_TABLES embarquée → 3 groupes diffèrent d'un article. Sans importance sur les taux ; à régler en fournissant votre `FR_TABLES.xlsx` à jour.
4. **Historique hétérogène** : 38 libellés `TYPE` dont des variantes de casse (FOOD/Food, CROSS SELLING/B&S/Cross selling…) → normalisés (28 libellés restants, dont d'anciennes catégories : F&S, OIL GAS, SOURCING…).
5. **Retraitement manuel** dans Suivi évolution (75 commentaires : suppression de lignes « NA », accord CDG 26/07/24) : l'historique est une mémoire, pas un calcul reproductible.
6. **Filtres masqués dans les TCD** : Analyse DEPOT n'affiche que BBS / Gianni ROY / Yacine BEN ZINA ; KPI Achats une sélection de PM et les ABC A/E ; ils sont ici des filtres à cocher (tout est affiché par défaut).
7. **Valeur de stock et impact FI** : présents dans BASE, mais **aucun TCD d'origine ne les exploite** ; l'onglet 💶 est donc une extension, pas une reproduction.
8. **`AUJOURDHUI()`** rend les vues Daily instables (elles changent chaque jour) ; l'appli prend par défaut la dernière date de l'historique comme référence.
