"""Tests unitaires sur données synthétiques (lancer : python -m unittest discover tests)."""
import sys, unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from couverture import analyses as A, config as C, history as H, loaders as L, logic as G   # noqa: E402


def mini_base():
    rows = [  # PM, ABC, stock sécu SAP (E), stock libre, division, article, schéma, gest
        ("FRLNOEL",  "A", 100, 0,    "FR07", "1", "#", "OP7"),          # RUPTURE
        ("FRLNOEL",  "A", 100, 30,   "FR07", "2", "#", "OP7"),          # 0-50
        ("FRLNOEL",  "B", 100, 50,   "FR07", "3", "#", "OP7"),          # <=0.5 -> 0-50 (borne incluse)
        ("FRLNOEL",  "B", 100, 99,   "FR07", "4", "#", "OP7"),          # 51-99
        ("FRLNOEL",  "C", 100, 100,  "FR07", "5", "#", "OP7"),          # OK (borne incluse)
        ("FRLNOEL",  "C", 0,   500,  "FR07", "6", "#", "OP7"),          # MTO
        ("FRLNOEL",  "C", "630,00 M", 2130, "FR07", "7", "#", "OP7"),   # unité M
        ("FRLNOEL",  "C", "1.000,00 KG", 900, "FR07", "8", "#", "OP7"), # 900/1000 -> 51-99
        ("FRLNOEL",  "C", 100, 10,   "FR07", "9", "SCHÉMA1 CONTINGENT", "OP7"),   # exclu par défaut
        ("FRINCONNU", "C", 100, 200, "FR07", "10", "#", "ZZZ"),         # PM / gest non mappés
        ("FRLNOEL",  "C", 100, -5,   "FR07", "11", "#", "OP7"),         # négatif -> 0-50 (comme Excel)
    ]
    return pd.DataFrame(rows, columns=["PM Nom", "Code ABC", "Stok initia", "Qté stock libre", "Division", "Article",
                                       "Schéma contigent.", "Gestionnaire"]).assign(
        **{"Divison Nom": "Dépôt X", "Grpe planif.": "ZORI", "Gestionnaire nom": "OP FR07"})


PM = pd.DataFrame({"NOM PM": ["FRLNOEL"], "Niveau 1": ["Spé"], "Niveau 2": ["SOLVANT"], "Manager": ["L. Noel"], "BES/BSP": ["BES"]})
GE = pd.DataFrame({"Code Gest.": ["OP7"], "Gestionnaire": ["OP FR07"], "Approvisionneur": ["Gianni ROY"]})


class TestBase(unittest.TestCase):
    def setUp(self):
        self.pm, self.ge = L.load_reference(PM, GE)

    def test_categories_et_bornes(self):
        b, _ = G.prepare_base(mini_base(), self.pm, self.ge, strict_excel=True)
        e = dict(zip(b["Article"], b["ETAT2"]))
        self.assertEqual(e["1"], C.CAT_RUPTURE)
        self.assertEqual(e["2"], C.CAT_0_50)
        self.assertEqual(e["3"], C.CAT_0_50)      # 0.5 inclus dans 0-50 %
        self.assertEqual(e["4"], C.CAT_51_99)
        self.assertEqual(e["5"], C.CAT_OK)        # 1.0 = OK
        self.assertTrue(pd.isna(e["6"]))          # MTO : pas de catégorie
        self.assertEqual(e["11"], C.CAT_0_50)     # ratio négatif, comme la formule Excel
        self.assertEqual(dict(zip(b["Article"], b["ETAT"]))["6"], C.MTO)

    def test_mode_strict_vs_nettoyage(self):
        s, rs = G.prepare_base(mini_base(), self.pm, self.ge, strict_excel=True)
        n, rn = G.prepare_base(mini_base(), self.pm, self.ge, strict_excel=False)
        self.assertEqual(rs["erreurs_conversion_stock_secu"], 1)
        self.assertEqual(rn["erreurs_conversion_stock_secu"], 0)
        self.assertEqual(s.set_index("Article").loc["7", "ETAT2"], C.CAT_ERREUR)
        self.assertEqual(n.set_index("Article").loc["7", "ETAT2"], C.CAT_OK)          # 2130/630
        self.assertEqual(n.set_index("Article").loc["8", "ETAT2"], C.CAT_51_99)      # "1.000,00 KG" -> 1000

    def test_references_et_non_mappes(self):
        b, rep = G.prepare_base(mini_base(), self.pm, self.ge)
        r = b.set_index("Article")
        self.assertEqual(r.loc["1", "BES/BSP"], "BES")
        self.assertEqual(r.loc["1", "QUI appro"], "Gianni ROY")
        self.assertEqual(rep["pm_non_mappes"], ["FRINCONNU"])
        self.assertEqual(rep["gest_non_mappes"], ["ZZZ"])

    def test_snapshot_perimetre(self):
        b, _ = G.prepare_base(mini_base(), self.pm, self.ge)
        s = G.build_snapshot(b, "2026-08-12")
        # MTS hors contingent : articles 1,2,3,4,5,7,8,10,11 = 9
        self.assertEqual(s["Nombre de Article"].sum(), 9)
        self.assertTrue((s["Date"] == pd.Timestamp("2026-08-12")).all())
        s_all = G.build_snapshot(b, "2026-08-12", exclure_contingent=False)
        self.assertEqual(s_all["Nombre de Article"].sum(), 10)

    def test_taux_couverture(self):
        b, _ = G.prepare_base(mini_base(), self.pm, self.ge)
        k = A.kpi_headline(b)["France"]
        # 9 MTS hors contingent ; OK = articles 5, 7 (2130/630) et 10 (200/100) -> 3
        self.assertEqual(k["ok"], 3)
        self.assertAlmostEqual(k["taux"], 3 / 9)


class TestHistorique(unittest.TestCase):
    def test_normalisation_et_ajout(self):
        h = pd.DataFrame({"Date": ["2026-08-05"] * 2, "QUI appro": ["A", "A"], "PMF BM": ["x", "x"], "PM Nom": ["P", "P"],
                          "Code ABC": ["A", "A"], "Code gestionnaire": ["G", "G"], "Gestionnaire nom": ["g", "g"],
                          "ETAT2": ["OK", "#VALUE!"], "BES/BSP": ["BES", "BES"], "TYPE": ["FOOD", "CROSS SELLING"],
                          "Nombre de Article": [3, 1]})
        n = H.normalize_history(h, ["Food", "B&S/Cross selling"])
        self.assertEqual(sorted(n["TYPE"]), ["B&S/Cross selling", "Food"])
        self.assertIn(C.CAT_ERREUR, n["ETAT2"].tolist())
        snap = n.assign(Date=pd.Timestamp("2026-08-05"), **{"Nombre de Article": 7})
        out = H.append_snapshot(n, snap)          # même date -> remplacée, pas dupliquée
        self.assertEqual(out["Nombre de Article"].sum(), 14)
        snap2 = snap.assign(Date=pd.Timestamp("2026-08-12"))
        self.assertEqual(H.append_snapshot(out, snap2)["Date"].nunique(), 2)

    def test_taux_hebdo_et_fenetre(self):
        rows = []
        for d, ok, ko in [("2026-07-01", 8, 2), ("2026-07-08", 9, 1), ("2026-08-12", 5, 5)]:
            rows += [(d, "OK", ok), (d, "RUPTURE", ko)]
        h = pd.DataFrame(rows, columns=["Date", "ETAT2", "Nombre de Article"]).assign(
            **{"QUI appro": "A", "PMF BM": "x", "PM Nom": "P", "Code ABC": "A", "Code gestionnaire": "G",
               "Gestionnaire nom": "g", "BES/BSP": "BES", "TYPE": "Food"})
        h["Date"] = pd.to_datetime(h["Date"])
        t = A.taux_hebdo(h, n=9)
        self.assertAlmostEqual(t.loc[pd.Timestamp("2026-08-12"), "France"], 0.5)
        f = H.fenetre(h, 30)                       # référence = 12/08 -> exclut le 01/07 et le 08/07 (> 30 j)
        self.assertEqual(f["Date"].nunique(), 1)


if __name__ == "__main__":
    unittest.main()
