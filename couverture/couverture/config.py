"""Constantes métier reprises du classeur Excel « Indicateur de couverture »."""
import re
import unicodedata

# --- Catégories de couverture (colonne « ETAT2 » de l'onglet BASE) ----------------
CAT_OK = "OK"
CAT_51_99 = "Inf SS 51-99%"
CAT_0_50 = "Inf SS 0-50%"
CAT_RUPTURE = "RUPTURE"
CAT_ERREUR = "#VALEUR!"

CATS_NON_OK = [CAT_51_99, CAT_0_50, CAT_RUPTURE]          # ordre des colonnes des TCD Excel
CATS = [CAT_OK] + CATS_NON_OK
CATS_AVEC_ERREUR = CATS + [CAT_ERREUR]

# Seuils de la formule ETAT2 :  ratio = Qté stock libre / Stock sécu SAP (col. E « Stok initia »)
#   ratio = 0 -> RUPTURE ; 0 < ratio <= 0.5 -> Inf SS 0-50% ; 0.5 < ratio < 1 -> Inf SS 51-99% ; >= 1 -> OK
SEUIL_BAS = 0.5
SEUIL_OK = 1.0

MTS, MTO = "MTS", "MTO"
SCHEMA_CONTINGENT = "SCHÉMA1 CONTINGENT"     # valeur exclue par le filtre « # et (Vides) »
NON_MAPPE = "Non mappé"

COULEURS = {
    CAT_OK: "#2E9E5B", CAT_51_99: "#F2C14E", CAT_0_50: "#F08A24",
    CAT_RUPTURE: "#D64545", CAT_ERREUR: "#8C8C8C",
}


def norm(txt) -> str:
    """Normalise un en-tête : sans accents, minuscule, espaces/retours ligne réduits."""
    if txt is None:
        return ""
    s = unicodedata.normalize("NFKD", str(txt))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("\xa0", " ").lower()
    return re.sub(r"\s+", " ", s).strip()


# --- Colonnes de l'onglet BASE : nom interne -> variantes d'en-têtes acceptées ---
BASE_ALIASES = {
    "PM Nom": ["pm nom"],
    "Code ABC": ["code abc"],
    "Stock sécu SAP": ["stok initia", "stock initia", "stock initial", "stock secu sap"],
    "Division": ["division"],
    "Dépôt": ["divison nom", "division nom", "depot"],
    "Article": ["article"],
    "Désignation": ["artcile nom", "article nom"],
    "Schéma contingent": ["schema contigent.", "schema contigent", "schema contingent"],
    "Grpe planif.": ["grpe planif.", "grpe planif"],
    "Gestionnaire": ["gestionnaire"],
    "Gestionnaire nom": ["gestionnaire nom"],
    "Type appro": ["type appro"],
    "Unité base": ["unite qte base"],
    "Qté stock libre": ["qte stock libre"],
    "Stock sécu formulaire": ["stock secu form.", "stock secu form"],
    "ROP formulaire": ["rop form.", "rop form"],
    "Stock moyen": ["stock moyen"],
    "PMP": ["pmp"],
    "Unité prix PMP": ["unite prix de pmp"],
    "Valeur stock € (SAP)": ["valeur stock du jour €", "valeur stock du jour"],
    "Impact FI (SAP)": ["impact fi si stk moyen"],
    "Conso max 6 mois": ["conso max 6 dern. mois"],
    "Conso moyenne": ["conso moyenne"],
    "Lead time achats (jours)": ["lead time achats jo"],
    "Lead time achats (qté)": ["lead time achats qte"],
    "MOQ": ["moq"],
    "Commentaire PM": ["commentaire pm"],
    # colonnes éventuellement déjà résolues par Excel (VLOOKUP sur FR_TABLES) – simple repli
    "PMF BM (fichier)": ["pmf bm"],
    "QUI appro (fichier)": ["qui appro"],
    "BES/BSP (fichier)": ["bes/bsp"],
    "TYPE (fichier)": ["type"],
}
BASE_REQUIRED = ["PM Nom", "Code ABC", "Stock sécu SAP", "Division", "Dépôt", "Article",
                 "Schéma contingent", "Grpe planif.", "Gestionnaire", "Gestionnaire nom",
                 "Qté stock libre"]
BASE_NUMERIC = ["Qté stock libre", "Stock sécu formulaire", "ROP formulaire", "Stock moyen", "PMP",
                "Unité prix PMP", "Valeur stock € (SAP)", "Impact FI (SAP)", "Conso max 6 mois",
                "Conso moyenne", "Lead time achats (jours)", "Lead time achats (qté)", "MOQ"]

# --- Historique (onglet « Suivi évolution ») -------------------------------------
HIST_COLS = ["Date", "QUI appro", "PMF BM", "PM Nom", "Code ABC", "Code gestionnaire",
             "Gestionnaire nom", "ETAT2", "BES/BSP", "TYPE", "Nombre de Article"]
HIST_ALIASES = {
    "Date": ["date"], "QUI appro": ["qui appro"], "PMF BM": ["pmf bm"], "PM Nom": ["pm nom"],
    "Code ABC": ["code abc"], "Code gestionnaire": ["code gestionnaire", "gestionnaire"],
    "Gestionnaire nom": ["gestionnaire nom"], "ETAT2": ["etat2"], "BES/BSP": ["bes/bsp"],
    "TYPE": ["type"], "Nombre de Article": ["nombre de article"],
}

# --- Tables de référence (FR_TABLES.xlsx : onglets « PM » et « Gest. ») ----------
PM_ALIASES = {"NOM PM": ["nom pm"], "Niveau 1": ["niveau 1"], "Niveau 2": ["niveau 2"],
              "Manager": ["manager"], "BES/BSP": ["bes/bsp"]}
GEST_ALIASES = {"Code Gest.": ["code gest.", "code gest"], "Gestionnaire": ["gestionnaire"],
                "Approvisionneur": ["approvisionneur"]}

# Alias historiques de libellés TYPE (le suivi contient des variantes de casse / d'écriture)
TYPE_ALIAS = {"cross selling": "B&S/Cross selling", "polymer": "Polymers",
              "coating & construction": "Coating&Construction"}
