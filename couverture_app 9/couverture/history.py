"""Historique hebdomadaire (onglet « Suivi évolution ») : normalisation, ajout, persistance."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config as C
from . import loaders as L

HISTORY_FILE = L.DATA_DIR / "historique.csv.gz"


def normalize_history(df: pd.DataFrame, types_canoniques=()) -> pd.DataFrame:
    """Uniformise l'historique (le classeur mélange « FOOD »/« Food », « CROSS SELLING »/« B&S/Cross selling »,
    « #VALUE! »/« #VALEUR! », « #N/A »…). Les colonnes ETAT/Schéma constantes (MTS / #) sont supprimées."""
    h = L.standardize(df, C.HIST_ALIASES)
    absent = [c for c in C.HIST_COLS if c not in h.columns]
    if absent:
        raise ValueError("Colonnes absentes de l'historique : " + ", ".join(absent))
    h = h[C.HIST_COLS].dropna(subset=["Date"]).copy()
    h["Date"] = pd.to_datetime(h["Date"], errors="coerce").dt.normalize()
    h = h.dropna(subset=["Date"])
    h["Nombre de Article"] = pd.to_numeric(h["Nombre de Article"], errors="coerce").fillna(0).astype(int)
    for c in ["QUI appro", "PMF BM", "PM Nom", "Code ABC", "Code gestionnaire", "Gestionnaire nom", "ETAT2", "BES/BSP", "TYPE"]:
        h[c] = h[c].astype("object").where(h[c].notna(), C.NON_MAPPE).map(lambda v: str(v).strip())
    h["ETAT2"] = h["ETAT2"].replace({"#VALUE!": C.CAT_ERREUR, "#N/A": C.CAT_ERREUR})
    for c in ("BES/BSP", "TYPE", "PMF BM", "QUI appro"):
        h[c] = h[c].replace({"#N/A": C.NON_MAPPE, "(vide)": C.NON_MAPPE})
    canon = {C.norm(t): t for t in types_canoniques}
    canon.update({k: v for k, v in C.TYPE_ALIAS.items()})
    h["TYPE"] = h["TYPE"].map(lambda t: canon.get(C.norm(t), t))
    return (h.groupby([c for c in C.HIST_COLS if c != "Nombre de Article"], dropna=False, sort=True)
              ["Nombre de Article"].sum().reset_index())


def append_snapshot(hist: pd.DataFrame | None, snap: pd.DataFrame, types_canoniques=()) -> pd.DataFrame:
    """Ajoute l'instantané du jour ; une date déjà présente est remplacée (pas de doublon)."""
    snap = normalize_history(snap, types_canoniques)
    if hist is None or hist.empty:
        return snap
    hist = hist[~hist["Date"].isin(snap["Date"].unique())]
    return pd.concat([hist, snap], ignore_index=True).sort_values("Date", kind="stable").reset_index(drop=True)


def save_history(hist: pd.DataFrame, path: Path = HISTORY_FILE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    hist.to_csv(path, index=False, compression="gzip")
    return path


def load_saved_history(path: Path = HISTORY_FILE) -> pd.DataFrame | None:
    if not Path(path).exists():
        return None
    h = pd.read_csv(path, compression="gzip", parse_dates=["Date"], dtype={"Nombre de Article": int})
    return h


def dates_disponibles(hist: pd.DataFrame) -> list[pd.Timestamp]:
    return sorted(pd.to_datetime(hist["Date"]).unique())


def fenetre(hist: pd.DataFrame, jours: int = 30, reference=None) -> pd.DataFrame:
    """Équivalent de la colonne « A PRENDRE » (=SI(AUJOURDHUI()-Date<=30;"OUI";"NON")).
    La référence est par défaut la dernière date de l'historique (et non AUJOURDHUI(), plus stable)."""
    ref = pd.Timestamp(reference) if reference is not None else hist["Date"].max()
    return hist[(ref - hist["Date"]).dt.days <= jours]
