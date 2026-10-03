"""Lecture des classeurs Excel : détection automatique des onglets bruts et normalisation."""
from __future__ import annotations

import io
import itertools
import re
from datetime import date
from pathlib import Path

import pandas as pd

from . import config as C

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ------------------------------------------------------------------ détection --
def _match_columns(columns, aliases: dict[str, list[str]]) -> dict[str, str]:
    """Renvoie {nom interne: nom réel de la colonne} (première occurrence)."""
    normed = {}
    for col in columns:
        normed.setdefault(C.norm(col), col)
    found = {}
    for internal, variants in aliases.items():
        for v in variants:
            if v in normed:
                found[internal] = normed[v]
                break
    return found


def _kind_from_header(cells) -> str | None:
    names = {C.norm(c) for c in cells if c is not None}
    if {"article", "qte stock libre"} <= names and names & set(C.BASE_ALIASES["Stock sécu SAP"]):
        return "base"
    if {"nombre de article", "etat2", "pm nom"} <= names:
        return "historique" if "date" in names else "instantane"
    if {"nom pm", "bes/bsp"} <= names and "niveau 2" in names:
        return "ref_pm"
    if {"code gest.", "approvisionneur"} <= names or {"code gest", "approvisionneur"} <= names:
        return "ref_gest"
    return None


def detect_sheets(file_bytes: bytes) -> dict[str, dict]:
    """Analyse un classeur : {onglet: {'kind': ..., 'header_row': n}} pour les onglets bruts reconnus.

    Les onglets de résultats (TCD, Synthèse, Daily VIEW…) ne sont pas reconnus : ils sont recalculés.
    Seules les 10 premières lignes de chaque onglet sont lues (rapide même sur un fichier de 100 Mo).
    """
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    out = {}
    try:
        for ws in wb.worksheets:
            head = list(itertools.islice(ws.iter_rows(values_only=True), 10))
            for i, row in enumerate(head):
                kind = _kind_from_header(row)
                if kind:
                    out[ws.title] = {"kind": kind, "header_row": i}
                    break
    finally:
        wb.close()
    return out


def _read_sheet(file_bytes: bytes, sheet: str, header_row: int) -> pd.DataFrame:
    try:
        import python_calamine  # noqa: F401
        engine = "calamine"
    except ImportError:
        engine = "openpyxl"
    return pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet, header=header_row,
                         engine=engine, dtype=object)


def read_detected(file_bytes: bytes, detected: dict[str, dict], kind: str) -> pd.DataFrame | None:
    for sheet, info in detected.items():
        if info["kind"] == kind:
            return _read_sheet(file_bytes, sheet, info["header_row"])
    return None


def read_csv_bytes(data: bytes) -> pd.DataFrame:
    """CSV exporté d'Excel (séparateur « ; » ou « , », encodage UTF-8/latin-1)."""
    sep = ";" if data[:4000].count(b";") > data[:4000].count(b",") else ","
    try:
        return pd.read_csv(io.BytesIO(data), sep=sep, dtype=object, encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(io.BytesIO(data), sep=sep, dtype=object, encoding="latin-1")


# ------------------------------------------------------------------ nettoyage --
def standardize(df: pd.DataFrame, aliases: dict[str, list[str]]) -> pd.DataFrame:
    mapping = _match_columns(df.columns, aliases)
    out = df[list(mapping.values())].copy()
    out.columns = list(mapping.keys())
    return out


def clean_number(s: pd.Series, strict_excel: bool = False) -> tuple[pd.Series, pd.Series]:
    """Convertit une colonne SAP en nombres. Renvoie (valeurs, indicateur d'erreur de conversion).

    Règle du classeur (commentaire de la cellule E1 de BASE) : retirer « KG », « PC », « L » et « . »
    de la colonne E. Ici on retire aussi toute autre unité (ex. « M ») sauf en mode strict Excel,
    où ces valeurs restent en erreur (#VALEUR!) comme dans le classeur.
    """
    if pd.api.types.is_numeric_dtype(s):
        return s.astype(float), pd.Series(False, index=s.index)
    txt = s.astype(object).where(s.notna(), None)

    def conv(v):
        if v is None:
            return (None, False)
        if isinstance(v, (int, float)):
            return (float(v), False)
        t = str(v).strip()
        if t == "":
            return (None, False)
        t = t.replace("\xa0", " ")
        if strict_excel:
            t = re.sub(r"(?i)\b(kg|pc|l)\b|(?<=\d)(kg|pc|l)\b", "", t)
        else:
            t = re.sub(r"[A-Za-z]+", "", t)
        t = t.replace(".", "").replace(" ", "").replace(",", ".")
        try:
            return (float(t), False)
        except ValueError:
            return (None, True)

    res = [conv(v) for v in txt]
    vals = pd.Series([r[0] for r in res], index=s.index, dtype="float64")
    err = pd.Series([r[1] for r in res], index=s.index)
    return vals, err


# ------------------------------------------------------------ tables de référence --
def load_reference(pm_df: pd.DataFrame | None = None, gest_df: pd.DataFrame | None = None):
    """Tables PM / Gestionnaire : celles fournies, sinon la copie embarquée dans data/."""
    if pm_df is None:
        pm_df = pd.read_csv(DATA_DIR / "ref_pm.csv", dtype=str)
    if gest_df is None:
        gest_df = pd.read_csv(DATA_DIR / "ref_gest.csv", dtype=str)
    pm = standardize(pm_df, C.PM_ALIASES)
    ge = standardize(gest_df, C.GEST_ALIASES)
    for d, key in ((pm, "NOM PM"), (ge, "Code Gest.")):
        d[key] = d[key].astype(str).str.strip()
        d.dropna(subset=[key], inplace=True)
        d.drop_duplicates(subset=[key], keep="first", inplace=True)   # VLOOKUP = 1re occurrence
    return pm, ge


def date_from_filename(name: str) -> date | None:
    """« Indicateur_de_couverture_Weekly_2026_08_12.xlsx » -> 2026-08-12."""
    m = re.search(r"(20\d{2})[_\-.]?(\d{2})[_\-.]?(\d{2})", name or "")
    if not m:
        return None
    try:
        return date(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:
        return None


def to_datetime(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")


kind_from_header = _kind_from_header   # API publique
