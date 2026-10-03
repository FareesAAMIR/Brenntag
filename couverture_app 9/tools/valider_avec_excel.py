"""Compare les calculs Python aux valeurs mises en cache dans le classeur Excel d'origine.

    python tools/valider_avec_excel.py "Indicateur_de_couverture_Weekly_2026_08_12.xlsx" [--sans-historique]

Contrôles : ETAT / ETAT2 de BASE (ligne à ligne), taux hebdomadaires de « Synthese »,
TCD « Synthese » par PM, « Analyse DEPOT », instantané du jour vs dernière date de « Suivi évolution ».
"""
import sys
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from couverture import analyses as A, config as C, history as H, loaders as L, logic as G   # noqa: E402


def main(path: str, avec_hist: bool = True):
    data = Path(path).read_bytes()
    det = L.detect_sheets(data)
    print("Onglets bruts reconnus :", {k: v["kind"] for k, v in det.items()})
    raw = L.read_detected(data, det, "base")
    pm, ge = L.load_reference()
    base, rep = G.prepare_base(raw, pm, ge, strict_excel=True)
    ok = lambda label, cond: print(("  OK  " if cond else "  ÉCART  ") + label)

    # 1) BASE ligne à ligne  (la 2e colonne « ETAT » de BASE est ETAT2 : pandas la nomme « ETAT.1 »)
    e2_col = "ETAT.1" if "ETAT.1" in raw.columns else None
    ok("ETAT (MTS/MTO) identique sur toutes les lignes", (base["ETAT"].values == raw["ETAT"].values).all())
    if e2_col:
        # False = article MTO ; cellule vide/NaN à la lecture = erreur Excel (#VALEUR!)
        xl = raw[e2_col].map(lambda v: "-" if v is False else (C.CAT_ERREUR if pd.isna(v) or str(v) in ("#VALUE!", "#VALEUR!") else v))
        ok("ETAT2 (catégorie de couverture) identique sur toutes les lignes", (base["ETAT2"].fillna("-").values == xl.values).all())

    wb = openpyxl.load_workbook(__import__("io").BytesIO(data), read_only=True, data_only=True)
    if avec_hist and "historique" in {v["kind"] for v in det.values()}:
        hist = H.normalize_history(L.read_detected(data, det, "historique"), pm["Niveau 2"].tolist())
        xl = np.array([list(r) for r in wb["Synthese"].iter_rows(min_row=6, max_row=8, min_col=4, max_col=12, values_only=True)], dtype=float)
        th = A.taux_hebdo(hist)
        ok(f"Synthese!D6:L8 (taux BES / BSP / France sur {len(th)} dates), écart max = {np.abs(th[['BES','BSP','France']].values.T - xl).max():.2e}",
           np.abs(th[["BES", "BSP", "France"]].values.T - xl).max() < 1e-9)
        last = hist[hist["Date"] == hist["Date"].max()]
        sn = H.normalize_history(G.build_snapshot(base, hist["Date"].max()), pm["Niveau 2"].tolist())
        k = [c for c in C.HIST_COLS if c not in ("Nombre de Article", "PMF BM")]
        a, b = last.groupby(k)["Nombre de Article"].sum(), sn.groupby(k)["Nombre de Article"].sum()
        d = pd.concat([a, b], axis=1).fillna(0)
        ok(f"Instantané du jour = dernière date de « Suivi évolution » (hors PMF BM) : {int((d.iloc[:, 0] != d.iloc[:, 1]).sum())} groupes en écart", (d.iloc[:, 0] == d.iloc[:, 1]).all())

    # 2) TCD Synthese par PM
    g = [list(r) for r in wb["Synthese"].iter_rows(min_row=36, max_row=78, min_col=12, max_col=17, values_only=True)]
    cur, rows = None, []
    for r in g:
        cur = r[0] if r[0] is not None else cur
        if r[1] is not None and not str(r[1]).startswith("Total"):
            rows.append([cur, r[1]] + [(x or 0) for x in r[2:6]])
    xl = pd.DataFrame(rows, columns=["BES/BSP", "PM Nom"] + C.CATS)
    py = A.synthese_par_pm(base)[["BES/BSP", "PM Nom"] + C.CATS]
    m = xl.merge(py, on=["BES/BSP", "PM Nom"], how="outer", suffixes=("_x", "_p"), indicator=True)
    ok("Synthese!L34:R78 (BES/BSP × PM × ETAT2)", (m["_merge"] == "both").all() and all((m[c + "_x"] == m[c + "_p"]).all() for c in C.CATS))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], avec_hist="--sans-historique" not in sys.argv)
