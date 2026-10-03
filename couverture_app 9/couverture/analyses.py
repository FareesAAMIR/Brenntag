"""Équivalents Python de tous les TCD / tableaux du classeur Excel.

Chaque fonction renvoie un DataFrame prêt à afficher ou à exporter.
Sources : `base` = BASE enrichie (logic.prepare_base) ; `hist` = historique normalisé (history.py).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from . import logic as G


# ---------------------------------------------------------------- briques ----
def taux(ok, total):
    return np.where(total > 0, ok / np.where(total > 0, total, 1), np.nan)


def croiser(df: pd.DataFrame, lignes: list[str], valeur: str | None = None, colonne: str = "ETAT2",
            categories: list[str] | None = None, avec_taux: bool = True, avec_erreurs: bool = False) -> pd.DataFrame:
    """TCD générique : lignes × catégories de couverture (+ total + taux de couverture).

    `valeur=None` -> nombre de lignes (NB article) ; sinon somme de la colonne (historique).
    Taux = OK / (OK + Inf SS 51-99% + Inf SS 0-50% + RUPTURE), comme dans les TCD Excel.
    """
    cats = categories or (C.CATS_AVEC_ERREUR if avec_erreurs else C.CATS)
    d = df[df[colonne].isin(cats)]
    if valeur is None:
        t = d.groupby(lignes + [colonne], dropna=False).size()
    else:
        t = d.groupby(lignes + [colonne], dropna=False)[valeur].sum()
    t = t.unstack(colonne, fill_value=0).reindex(columns=cats, fill_value=0)
    if avec_taux:
        cols4 = [c for c in C.CATS if c in t.columns]
        tot = t[cols4].sum(axis=1)
        t["Total"] = tot
        t["Taux de couverture"] = taux(t.get(C.CAT_OK, 0), tot)
    return t.reset_index()


def ajouter_sous_totaux(t: pd.DataFrame, niveau: str, autres: list[str]) -> pd.DataFrame:
    """Ajoute des lignes « Total <niveau> » (comme les sous-totaux des TCD)."""
    num = [c for c in t.columns if c not in autres + [niveau, "Taux de couverture"]]
    out = []
    for keys, g in t.groupby(autres, sort=False):
        out.append(g)
        s = g[num].sum()
        row = {**dict(zip(autres, keys if isinstance(keys, tuple) else (keys,))), niveau: "Total " + str(g.iloc[0][niveau] if niveau in g else "")}
        row.update(s.to_dict())
        row["Taux de couverture"] = float(taux(s.get(C.CAT_OK, 0), s.get("Total", 0)))
        out.append(pd.DataFrame([row]))
    return pd.concat(out, ignore_index=True)


def total_general(t: pd.DataFrame, libelle: str, colonnes_lignes: list[str]) -> pd.DataFrame:
    num = [c for c in t.columns if c not in colonnes_lignes + ["Taux de couverture"]]
    s = t[num].sum()
    row = {c: "" for c in colonnes_lignes}
    row[colonnes_lignes[0]] = libelle
    row.update(s.to_dict())
    col_total = "Total" if "Total" in s.index else "Total général"
    row["Taux de couverture"] = float(taux(s.get(C.CAT_OK, 0), s.get(col_total, 0)))
    return pd.concat([t, pd.DataFrame([row])], ignore_index=True)


# ------------------------------------------------------- onglet « Synthese » ----
def dates_synthese(hist: pd.DataFrame, n: int = 9) -> list[pd.Timestamp]:
    """Dernière date + les n-1 précédentes (formules MAXIFS(Date; Date < date suivante) de Synthese!D5:L5)."""
    d = sorted(pd.to_datetime(hist["Date"]).unique())
    return [pd.Timestamp(x) for x in d[-n:]]


def taux_hebdo(hist: pd.DataFrame, n: int = 9, inclure_erreurs_au_denominateur: bool = True) -> pd.DataFrame:
    """Synthese!C6:L8 – taux de couverture par date : BES, BSP, France.

    Formule Excel : SOMME.SI.ENS(Nb; ETAT2="OK"; Date; BES/BSP) / SOMME.SI.ENS(Nb; Date; BES/BSP)
    -> le dénominateur contient toutes les lignes du suivi (y compris #VALEUR!). Réglable ici.
    """
    ds = dates_synthese(hist, n)
    h = hist[hist["Date"].isin(ds)]
    if not inclure_erreurs_au_denominateur:
        h = h[h["ETAT2"].isin(C.CATS)]
    rows = []
    for label, sub in (("BES", h[h["BES/BSP"] == "BES"]), ("BSP", h[h["BES/BSP"] == "BSP"]), ("France", h)):
        ok = sub[sub["ETAT2"] == C.CAT_OK].groupby("Date")["Nombre de Article"].sum()
        tot = sub.groupby("Date")["Nombre de Article"].sum()
        r = (ok.reindex(tot.index, fill_value=0) / tot).rename(label)
        rows.append(r)
    out = pd.concat(rows, axis=1).reindex(ds)
    out.index.name = "Date"
    return out


def synthese_par_pm(base: pd.DataFrame) -> pd.DataFrame:
    """Synthese!L34:R78 – BES/BSP × PM Nom × ETAT2 (MTS, hors schéma contingent) + taux."""
    p = G.perimetre(base)
    t = croiser(p, ["BES/BSP", "PM Nom"])
    return t


def synthese_par_type_planif(base: pd.DataFrame) -> pd.DataFrame:
    """Synthese!A15:H77 – BES/BSP × TYPE × Grpe planif. × ETAT2 avec sous-totaux par TYPE."""
    p = G.perimetre(base)
    t = croiser(p, ["BES/BSP", "TYPE", "Grpe planif."]).sort_values(["BES/BSP", "TYPE", "Grpe planif."])
    parts = []
    for (bb, ty), g in t.groupby(["BES/BSP", "TYPE"], sort=False):
        parts.append(g)
        num = [c for c in g.columns if c not in ("BES/BSP", "TYPE", "Grpe planif.", "Taux de couverture")]
        s = g[num].sum()
        parts.append(pd.DataFrame([{"BES/BSP": bb, "TYPE": f"Total {ty}", "Grpe planif.": "", **s.to_dict(),
                                    "Taux de couverture": float(taux(s[C.CAT_OK], s["Total"]))}]))
    return pd.concat(parts, ignore_index=True)


def kpi_headline(base: pd.DataFrame) -> dict:
    """Chiffres clés du jour (périmètre MTS hors contingent)."""
    p = G.perimetre(base)
    res = {}
    for label, sub in (("France", p), ("BES", p[p["BES/BSP"] == "BES"]), ("BSP", p[p["BES/BSP"] == "BSP"])):
        vc = sub["ETAT2"].value_counts()
        tot = int(sum(vc.get(c, 0) for c in C.CATS))
        res[label] = {"articles_mts": int(len(sub)), "ok": int(vc.get(C.CAT_OK, 0)), "total_4_cat": tot,
                      "taux": float(vc.get(C.CAT_OK, 0) / tot) if tot else np.nan,
                      **{c: int(vc.get(c, 0)) for c in C.CATS_NON_OK}, "erreurs": int(vc.get(C.CAT_ERREUR, 0))}
    return res


# ------------------------------------------------- onglets « Daily VIEW … » ----
def evolution_comptes(hist: pd.DataFrame, lignes: list[str], jours: int = 30, reference=None,
                      abc: list[str] | None = None, categories: list[str] | None = None) -> pd.DataFrame:
    """Daily VIEW PM / Appro / FRANCE – nombre d'articles non OK par ligne × Date × ETAT2.
    Colonnes : MultiIndex (Date, ETAT2). Filtre « A PRENDRE = OUI » = fenêtre glissante de `jours`."""
    from .history import fenetre
    h = fenetre(hist, jours, reference)
    if abc:
        h = h[h["Code ABC"].isin(abc)]
    cats = categories or C.CATS_NON_OK
    h = h[h["ETAT2"].isin(cats)]
    t = h.pivot_table(index=lignes, columns=["Date", "ETAT2"], values="Nombre de Article",
                      aggfunc="sum", fill_value=0)
    ordre = [(d, c) for d in sorted(h["Date"].unique()) for c in cats if (d, c) in t.columns]
    return t.reindex(columns=pd.MultiIndex.from_tuples(ordre, names=["Date", "ETAT2"]))


def taux_par_date(hist: pd.DataFrame, lignes: list[str] | None = None, jours: int = 30, reference=None,
                  abc: list[str] | None = None, dates: list | None = None) -> pd.DataFrame:
    """Daily VIEW PM!A68:… – taux de couverture par PM (ou autre dimension) et par date.
    Sans `lignes` : taux France par date."""
    from .history import fenetre
    h = fenetre(hist, jours, reference) if dates is None else hist[hist["Date"].isin(dates)]
    if abc:
        h = h[h["Code ABC"].isin(abc)]
    h = h[h["ETAT2"].isin(C.CATS)]
    keys = (lignes or []) + ["Date"]
    tot = h.groupby(keys)["Nombre de Article"].sum()
    ok = h[h["ETAT2"] == C.CAT_OK].groupby(keys)["Nombre de Article"].sum().reindex(tot.index, fill_value=0)
    r = (ok / tot).rename("Taux")
    if lignes:
        return r.unstack("Date")
    return r.to_frame()


def evolution_france(hist: pd.DataFrame, jours: int = 30, reference=None, abc: list[str] | None = None) -> pd.DataFrame:
    """Daily VIEW FRANCE (T35:U41, Y34:AB41) – par date : nb d'articles Inf SS 51-99% / 0-50% / RUPTURE, total non OK."""
    from .history import fenetre
    h = fenetre(hist, jours, reference)
    if abc:
        h = h[h["Code ABC"].isin(abc)]
    h = h[h["ETAT2"].isin(C.CATS_NON_OK)]
    t = h.pivot_table(index="Date", columns="ETAT2", values="Nombre de Article", aggfunc="sum", fill_value=0)
    t = t.reindex(columns=C.CATS_NON_OK, fill_value=0)
    t["Total non OK"] = t.sum(axis=1)
    return t


def evolution_par_type(hist: pd.DataFrame, jours: int = 30, reference=None, abc: list[str] | None = None) -> pd.DataFrame:
    """Daily VIEW FRANCE!A4:V25 – BES/BSP × TYPE × Date × ETAT2 (non OK)."""
    return evolution_comptes(hist, ["BES/BSP", "TYPE"], jours, reference, abc)


# ------------------------------------------------------ onglet « Analyse » ----
def analyse_gestionnaire(base: pd.DataFrame, abc: list[str] | None = None, bes_bsp: list[str] | None = None) -> pd.DataFrame:
    """Analyse!A8:F41 – Gestionnaire × Gestionnaire nom × ETAT2 (hors OK), MTS hors contingent."""
    p = G.perimetre(base)
    if abc:
        p = p[p["Code ABC"].isin(abc)]
    if bes_bsp:
        p = p[p["BES/BSP"].isin(bes_bsp)]
    t = croiser(p, ["Gestionnaire", "Gestionnaire nom"], categories=C.CATS_NON_OK, avec_taux=False)
    t["Total non OK"] = t[C.CATS_NON_OK].sum(axis=1)
    return t.sort_values("Total non OK", ascending=False, ignore_index=True)


def analyse_pm_type(base: pd.DataFrame, abc: list[str] | None = None, bes_bsp: list[str] | None = None) -> pd.DataFrame:
    """Analyse!H8:M42 – PM Nom × TYPE × ETAT2 (hors OK)."""
    p = G.perimetre(base)
    if abc:
        p = p[p["Code ABC"].isin(abc)]
    if bes_bsp:
        p = p[p["BES/BSP"].isin(bes_bsp)]
    t = croiser(p, ["PM Nom", "TYPE"], categories=C.CATS_NON_OK, avec_taux=False)
    t["Total non OK"] = t[C.CATS_NON_OK].sum(axis=1)
    return t.sort_values("Total non OK", ascending=False, ignore_index=True)


def historique_gestionnaire(hist: pd.DataFrame) -> pd.DataFrame:
    """Analyse!A49:KP279 – Code gestionnaire × Gestionnaire nom × ETAT2 × Date (toutes dates, non OK)."""
    h = hist[hist["ETAT2"].isin(C.CATS_NON_OK)]
    t = h.pivot_table(index=["Code gestionnaire", "Gestionnaire nom", "ETAT2"], columns="Date",
                      values="Nombre de Article", aggfunc="sum", fill_value=0)
    return t


def top_par_dimension(hist: pd.DataFrame, dim: str, abc: list[str] | None = None,
                      bes_bsp: list[str] | None = None, n: int = 10) -> tuple[pd.DataFrame, pd.Timestamp | None]:
    """Répartition (catégories non OK) sur la dernière date disponible, pour les `n` lignes les plus en difficulté.
    Réponses à « où se situent principalement les problèmes ? »."""
    d = hist[hist["ETAT2"].isin(C.CATS_NON_OK)]
    if abc:
        d = d[d["Code ABC"].isin(abc)]
    if bes_bsp:
        d = d[d["BES/BSP"].isin(bes_bsp)]
    if not len(d):
        return pd.DataFrame(), None
    date_ref = d["Date"].max()
    last = d[d["Date"] == date_ref]
    t = last.pivot_table(index=dim, columns="ETAT2", values="Nombre de Article", aggfunc="sum", fill_value=0)
    t = t.reindex(columns=C.CATS_NON_OK, fill_value=0)
    t["_total"] = t.sum(axis=1)
    t = t[t["_total"] > 0].sort_values("_total", ascending=False).head(n).drop(columns="_total").reset_index()
    return t, date_ref


def par_depot(base: pd.DataFrame, bes_bsp: list[str] | None = None) -> pd.DataFrame:
    """Total par dépôt (MTS hors contingent) : OK / non OK + taux — utilisé en Synthèse et en Analyse dépôt."""
    dep = analyse_depot(base, bes_bsp)
    t = dep.groupby("Dépôt")[[C.CAT_OK] + C.CATS_NON_OK].sum().reset_index()
    t["Total"] = t[[C.CAT_OK] + C.CATS_NON_OK].sum(axis=1)
    t["Taux de couverture"] = taux(t[C.CAT_OK], t["Total"])
    return t.sort_values("Total", ascending=False, ignore_index=True)


def repartition_categories(df: pd.DataFrame, colonne: str = "ETAT2") -> pd.DataFrame:
    """Nombre d'articles par catégorie de couverture (pour un donut de répartition globale)."""
    vc = df[df[colonne].isin(C.CATS)][colonne].value_counts().reindex(C.CATS, fill_value=0)
    return vc.rename("Articles").rename_axis("ETAT2").reset_index()


# --------------------------------------------------- onglet « Analyse DEPOT » ----
def analyse_depot(base: pd.DataFrame, bes_bsp: list[str] | None = None, acheteurs: list[str] | None = None) -> pd.DataFrame:
    """Analyse DEPOT!A5:H78 – QUI appro × Dépôt × Code ABC × ETAT2 (avec OK) + Total général."""
    p = G.perimetre(base)
    if bes_bsp:
        p = p[p["BES/BSP"].isin(bes_bsp)]
    if acheteurs:
        p = p[p["QUI appro"].isin(acheteurs)]
    cats = [C.CAT_OK, C.CAT_0_50, C.CAT_RUPTURE, C.CAT_51_99]         # ordre des colonnes du TCD Excel
    t = croiser(p, ["QUI appro", "Dépôt", "Code ABC"], categories=cats, avec_taux=False)
    t["Total général"] = t[cats].sum(axis=1)
    t["Taux de couverture"] = taux(t[C.CAT_OK], t["Total général"])
    return t


# ------------------------------------------- onglet « KPI Achats » (masqué) ----
def kpi_achats(base: pd.DataFrame, abc: list[str] | None = None) -> pd.DataFrame:
    """KPI Achats!A3:G17 – Code ABC × PM Nom × ETAT2 (nombre d'articles)."""
    p = G.perimetre(base)
    if abc:
        p = p[p["Code ABC"].isin(abc)]
    return croiser(p, ["Code ABC", "PM Nom"])


# ------------------------------------------------------- analyses transverses ----
def par_abc(base: pd.DataFrame) -> pd.DataFrame:
    return croiser(G.perimetre(base), ["Code ABC"])


def mts_mto(base: pd.DataFrame, exclure_contingent: bool = True) -> pd.DataFrame:
    """Répartition MTS / MTO (ETAT) par BES/BSP, avec valeur de stock."""
    b = base[~base["Contingent"]] if exclure_contingent else base
    g = b.groupby(["ETAT", "BES/BSP"], dropna=False).agg(
        articles=("Article", "size"), valeur_stock=("Valeur stock €", "sum") if "Valeur stock €" in b else ("Article", "size"))
    return g.reset_index()


def sous_stock_secu_formulaire(base: pd.DataFrame, par: list[str]) -> pd.DataFrame:
    """Colonne AL de BASE : articles dont le stock libre est <= stock de sécurité « formulaire » (MTS + MTO)."""
    col = "Stock réel <= stock sécu formulaire"
    if col not in base.columns:
        return pd.DataFrame()
    g = base.groupby(par, dropna=False).agg(articles=("Article", "size"), sous_stock_secu=(col, "sum"))
    g["% sous stock sécu"] = g["sous_stock_secu"] / g["articles"]
    return g.reset_index().sort_values("sous_stock_secu", ascending=False, ignore_index=True)


def valeur_stock(base: pd.DataFrame, par: list[str]) -> pd.DataFrame:
    """Valeur de stock (Qté libre × PMP) et impact financier si retour au stock moyen, par dimension.
    Extension : ces colonnes existent dans BASE mais ne sont exploitées par aucun TCD du classeur."""
    if "Valeur stock €" not in base:
        return pd.DataFrame()
    cols = {"articles": ("Article", "size"), "valeur_stock": ("Valeur stock €", "sum")}
    if "Impact FI si stock moyen €" in base:
        cols["impact_fi_stock_moyen"] = ("Impact FI si stock moyen €", "sum")
    g = base.groupby(par, dropna=False).agg(**cols).reset_index()
    for c in par:
        g[c] = g[c].astype(object).where(g[c].notna(), "(vide)")
    return g.sort_values("valeur_stock", ascending=False, ignore_index=True)


def articles_a_traiter(base: pd.DataFrame, categories: list[str] | None = None) -> pd.DataFrame:
    """Liste opérationnelle : articles MTS en RUPTURE / sous stock de sécurité, triés par criticité."""
    cats = categories or C.CATS_NON_OK
    p = G.perimetre(base)
    p = p[p["ETAT2"].isin(cats)]
    cols = [c for c in ["Division", "Dépôt", "Article", "Désignation", "Code ABC", "PM Nom", "PMF BM", "BES/BSP", "TYPE",
                        "Gestionnaire", "Gestionnaire nom", "QUI appro", "Stock sécu SAP", "Qté stock libre",
                        "% couverture stock sécu", "ETAT2", "Valeur stock €", "Commentaire PM"] if c in p.columns]
    return p[cols].sort_values(["ETAT2", "% couverture stock sécu"], key=lambda s: s.map({C.CAT_RUPTURE: 0, C.CAT_0_50: 1, C.CAT_51_99: 2}) if s.name == "ETAT2" else s,
                               ignore_index=True)
