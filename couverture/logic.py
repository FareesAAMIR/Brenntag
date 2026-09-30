"""Reproduction de la logique de l'onglet BASE, du « TCD aide » et du suivi d'évolution."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from . import loaders as L


# ------------------------------------------------------------------ BASE ------
def prepare_base(raw: pd.DataFrame, ref_pm: pd.DataFrame, ref_gest: pd.DataFrame,
                 strict_excel: bool = False) -> tuple[pd.DataFrame, dict]:
    """Nettoie l'extraction SAP et recalcule toutes les colonnes calculées de BASE.

    Colonnes recalculées (équivalents Excel) :
      PMF BM (A), QUI appro (AJ), ETAT (AK), STOCK REEL<STOCK SECU form (AL), %tage Couv Ssecu (AM),
      ETAT2 (AN), BES/BSP (AO), TYPE (AP), CC (AQ).
    Renvoie (dataframe enrichi, rapport de qualité).
    """
    df = L.standardize(raw, C.BASE_ALIASES)
    missing = [c for c in C.BASE_REQUIRED if c not in df.columns]
    if missing:
        raise ValueError("Colonnes indispensables absentes de BASE : " + ", ".join(missing))
    df = df.dropna(how="all").copy()
    report: dict = {"lignes": len(df)}

    # 1) chiffres
    err_secu = pd.Series(False, index=df.index)
    for col in C.BASE_NUMERIC + ["Stock sécu SAP"]:
        if col in df.columns:
            vals, err = L.clean_number(df[col], strict_excel)
            df[col] = vals
            if col == "Stock sécu SAP":
                err_secu = err
    report["erreurs_conversion_stock_secu"] = int(err_secu.sum())

    # 2) libellés
    for col in ["PM Nom", "Gestionnaire", "Code ABC", "Schéma contingent", "Article", "Division"]:
        df[col] = df[col].astype("object").where(df[col].notna(), None)
        df[col] = df[col].map(lambda v: str(v).strip() if v is not None else None)

    # 3) références (VLOOKUP FR_TABLES) -> PMF BM / BES/BSP / TYPE / QUI appro
    pm = ref_pm.assign(_k=ref_pm["NOM PM"].str.upper()).set_index("_k")
    ge = ref_gest.assign(_k=ref_gest["Code Gest."].str.upper()).set_index("_k")
    kpm = df["PM Nom"].str.upper()
    kge = df["Gestionnaire"].str.upper()
    df["PMF BM"] = kpm.map(pm["Manager"])
    df["BES/BSP"] = kpm.map(pm["BES/BSP"])
    df["TYPE"] = kpm.map(pm["Niveau 2"])
    df["QUI appro"] = kge.map(ge["Approvisionneur"])
    for internal, fallback in (("PMF BM", "PMF BM (fichier)"), ("BES/BSP", "BES/BSP (fichier)"),
                               ("TYPE", "TYPE (fichier)"), ("QUI appro", "QUI appro (fichier)")):
        if fallback in df.columns:
            df[internal] = df[internal].fillna(df[fallback].where(~df[fallback].astype(str).str.startswith("#")))
    report["pm_non_mappes"] = sorted(df.loc[df["BES/BSP"].isna(), "PM Nom"].dropna().unique().tolist())
    report["gest_non_mappes"] = sorted(df.loc[df["QUI appro"].isna(), "Gestionnaire"].dropna().unique().tolist())
    report["lignes_sans_pm"] = int(df["PM Nom"].isna().sum())

    # 4) ETAT (MTS / MTO) et ETAT2 (catégorie de couverture)
    secu = df["Stock sécu SAP"]
    libre = df["Qté stock libre"].fillna(0.0)
    est_mts = (secu.fillna(0) != 0) | err_secu
    df["ETAT"] = np.where(est_mts, C.MTS, C.MTO)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = libre / secu.where(secu.fillna(0) != 0)
    df["% couverture stock sécu"] = ratio
    etat2 = pd.Series(pd.NA, index=df.index, dtype="object")
    valide = est_mts & ~err_secu
    etat2[valide & (ratio == 0)] = C.CAT_RUPTURE
    etat2[valide & (ratio != 0) & (ratio <= C.SEUIL_BAS)] = C.CAT_0_50        # y compris ratios négatifs (comme Excel)
    etat2[valide & (ratio > C.SEUIL_BAS) & (ratio < C.SEUIL_OK)] = C.CAT_51_99
    etat2[valide & (ratio >= C.SEUIL_OK)] = C.CAT_OK
    etat2[est_mts & err_secu] = C.CAT_ERREUR
    df["ETAT2"] = etat2

    # 5) indicateurs complémentaires présents dans BASE
    if "Stock sécu formulaire" in df.columns:
        df["Stock réel <= stock sécu formulaire"] = libre <= df["Stock sécu formulaire"].fillna(0)
    df["CC"] = df["Division"].fillna("") + df["Article"].fillna("")
    df["Contingent"] = df["Schéma contingent"].fillna("#").str.strip().str.upper().eq(C.SCHEMA_CONTINGENT)

    # 6) valeurs financières recalculées (égales aux colonnes SAP : contrôle)
    if {"PMP", "Unité prix PMP"} <= set(df.columns):
        unite = df["Unité prix PMP"].replace(0, np.nan).fillna(1.0)
        df["Valeur stock €"] = libre * df["PMP"].fillna(0) / unite
        if "Stock moyen" in df.columns:
            df["Impact FI si stock moyen €"] = (df["Stock moyen"].fillna(0) - libre) * df["PMP"].fillna(0) / unite
    return df.reset_index(drop=True), report


def perimetre(df: pd.DataFrame, exclure_contingent: bool = True, seulement_mts: bool = True) -> pd.DataFrame:
    """Filtres de page communs aux TCD : ETAT = MTS et Schéma contingent = « # » (et vides)."""
    m = pd.Series(True, index=df.index)
    if seulement_mts:
        m &= df["ETAT"].eq(C.MTS)
    if exclure_contingent:
        m &= ~df["Contingent"]
    return df[m]


# ------------------------------------------------------------ TCD aide / instantané --
SNAP_KEYS = ["QUI appro", "PMF BM", "PM Nom", "Code ABC", "Code gestionnaire",
             "Gestionnaire nom", "ETAT2", "BES/BSP", "TYPE"]


def build_snapshot(base: pd.DataFrame, snap_date, exclure_contingent: bool = True) -> pd.DataFrame:
    """Équivalent du « TCD aide » collé chaque semaine dans « Suivi évolution » avec la date du jour."""
    p = perimetre(base, exclure_contingent, seulement_mts=True)
    g = p.rename(columns={"Gestionnaire": "Code gestionnaire"})
    g = g.assign(**{c: g[c].fillna(C.NON_MAPPE) if c in ("BES/BSP", "TYPE", "QUI appro", "PMF BM") else g[c]
                    for c in SNAP_KEYS})
    out = (g.groupby(SNAP_KEYS, dropna=False, sort=True).size()
             .rename("Nombre de Article").reset_index())
    out.insert(0, "Date", pd.Timestamp(snap_date).normalize())
    return out
