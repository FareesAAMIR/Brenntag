"""Indicateur de couverture – application Streamlit.

Même structure que le classeur Excel : 6 onglets (Synthèse, Daily View PM, Daily View Appro,
Daily View France, Analyse, Analyse dépôt), mêmes filtres, mêmes tableaux — recalculés à partir
des seules données brutes (BASE, Suivi évolution). Lancer :  streamlit run app.py
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from couverture import analyses as A
from couverture import charts as CH
from couverture import config as C
from couverture import export as X
from couverture import history as H
from couverture import loaders as L
from couverture import logic as G

st.set_page_config(page_title="Indicateur de couverture", page_icon="📦", layout="wide")


# ----------------------------------------------------------------- utilitaires ---
def show(df: pd.DataFrame | None, height: int | None = None, key: str | None = None):
    if df is None or len(df) == 0:
        st.caption("Aucune donnée pour ce périmètre.")
        return
    fmt = {c: "{:.1%}" for c in df.columns
           if isinstance(c, str) and ("taux" in c.lower() or c.startswith("% "))}
    try:
        st.dataframe(df.style.format(fmt, na_rep=""), width="stretch", height=height, hide_index=True, key=key)
    except Exception:
        st.dataframe(df, width="stretch", height=height, key=key)


def plot(fig, key: str | None = None):
    st.plotly_chart(fig, width="stretch", key=key)


def pct(x) -> str:
    return "–" if x is None or pd.isna(x) else f"{x:.1%}"


@st.cache_data(show_spinner="Analyse des onglets du classeur…")
def cached_detect(data: bytes):
    return L.detect_sheets(data)


@st.cache_data(show_spinner="Lecture de l'onglet brut…")
def cached_read(data: bytes, sheet: str, header_row: int):
    return L._read_sheet(data, sheet, header_row)


@st.cache_data(show_spinner="Lecture du CSV…")
def cached_csv(data: bytes):
    return L.read_csv_bytes(data)


# ------------------------------------------------------------------- sidebar -----
st.sidebar.title("📦 Indicateur de couverture")
st.sidebar.caption("Chargez uniquement les données brutes : le reste est recalculé, comme dans Excel.")

uploads = st.sidebar.file_uploader(
    "Fichiers sources (.xlsx / .csv)", type=["xlsx", "xlsm", "csv"], accept_multiple_files=True,
    help="Le classeur complet ou des onglets séparés : BASE, Suivi évolution, et éventuellement "
         "les tables PM / Gest. de FR_TABLES.xlsx. Les onglets de résultats sont ignorés.")

sources: dict[str, pd.DataFrame] = {}
base_filename = None
for f in uploads or []:
    data = f.getvalue()
    if f.name.lower().endswith(".csv"):
        df = cached_csv(data)
        kind = L.kind_from_header(list(df.columns))
        if kind:
            sources[kind] = df
            if kind == "base":
                base_filename = f.name
        continue
    for sheet, info in cached_detect(data).items():
        sources[info["kind"]] = cached_read(data, sheet, info["header_row"])
        if info["kind"] == "base":
            base_filename = f.name

st.sidebar.divider()
snap_date = st.sidebar.date_input(
    "Date de l'extraction BASE", value=L.date_from_filename(base_filename) or dt.date.today())
jours = st.sidebar.number_input("Fenêtre « A PRENDRE » (jours)", 7, 365, 30,
                                help="Comme dans Excel : Date ≥ aujourd'hui − 30 j.")
abc_sel = st.sidebar.multiselect("Code ABC", ["A", "B", "C", "E", "#"], default=[],
                                 help="Filtre de page des onglets Analyse (Code ABC = Tous par défaut).")
bes_bsp_sel = st.sidebar.multiselect("BES/BSP", ["BES", "BSP"], default=[])
abc = abc_sel or None
bes_bsp = bes_bsp_sel or None

with st.sidebar.expander("Paramètres avancés"):
    exclure_contingent = st.checkbox("Exclure le schéma contingent", value=True,
                                     help="Filtre « # et (Vides) » de tous les TCD Excel.")
    strict_excel = st.checkbox("Reproduire les erreurs Excel (#VALEUR!)", value=False)
    include_today = st.checkbox("Intégrer l'extraction du jour à l'historique", value=True)

# ---------------------------------------------------------------- données --------
ref_pm, ref_gest = L.load_reference(sources.get("ref_pm"), sources.get("ref_gest"))
types_canon = ref_pm["Niveau 2"].dropna().unique().tolist()

base = report = snap = None
if "base" in sources:
    try:
        base, report = G.prepare_base(sources["base"], ref_pm, ref_gest, strict_excel)
        snap = G.build_snapshot(base, snap_date, exclure_contingent)
    except ValueError as e:
        st.error(str(e))

hist_src = None
if "historique" in sources:
    hist_src = H.normalize_history(sources["historique"], types_canon)
elif "instantane" in sources:
    t = sources["instantane"].copy()
    cols = {C.norm(c): c for c in t.columns}
    if "etat" in cols:
        t = t[t[cols["etat"]].astype(str).str.upper().eq(C.MTS)]
    sc = next((cols[k] for k in ("schema contigent.", "schema contingent") if k in cols), None)
    if sc:
        t = t[~t[sc].astype(str).str.upper().eq(C.SCHEMA_CONTINGENT)]
    t["Date"] = pd.Timestamp(snap_date)
    hist_src = H.normalize_history(t, types_canon)
elif (saved := H.load_saved_history()) is not None:
    hist_src = saved

hist = hist_src
if snap is not None and include_today:
    hist = H.append_snapshot(hist_src, snap, types_canon)

with st.sidebar.expander("Historique & export"):
    if hist is not None and len(hist):
        st.caption(f"{hist['Date'].nunique()} dates, du {hist['Date'].min():%d/%m/%Y} au {hist['Date'].max():%d/%m/%Y}")
        c1, c2 = st.columns(2)
        if c1.button("💾 Enregistrer", help="Écrit data/historique.csv.gz."):
            try:
                H.save_history(hist)
                st.success("Enregistré.")
            except OSError as e:
                st.warning(f"Écriture impossible ({e}).")
        c2.download_button("⬇️ Télécharger", hist.to_csv(index=False, sep=";").encode("utf-8-sig"),
                           f"historique_{pd.Timestamp(snap_date):%Y_%m_%d}.csv", "text/csv")
    if base is not None:
        if st.button("📤 Préparer l'export Excel"):
            tables = {
                "Taux hebdo": A.taux_hebdo(hist).reset_index() if hist is not None else None,
                "Synthese PM": A.synthese_par_pm(base), "Synthese TYPE": A.synthese_par_type_planif(base),
                "Daily PM": A.evolution_comptes(hist, ["PM Nom"], jours, None, abc) if hist is not None else None,
                "Daily Appro": A.evolution_comptes(hist, ["Code gestionnaire", "Gestionnaire nom"], jours, None, abc) if hist is not None else None,
                "Daily France": A.evolution_france(hist, jours, None, abc).reset_index() if hist is not None else None,
                "Analyse gest": A.analyse_gestionnaire(base, abc, bes_bsp), "Analyse PM-TYPE": A.analyse_pm_type(base, abc, bes_bsp),
                "Analyse DEPOT": A.total_general(A.analyse_depot(base, bes_bsp), "Total général", ["QUI appro", "Dépôt", "Code ABC"]),
                "TCD aide": snap,
            }
            st.session_state["xlsx"] = X.to_excel_bytes({k: v for k, v in tables.items() if v is not None})
        if "xlsx" in st.session_state:
            st.download_button("⬇️ Télécharger l'export", st.session_state["xlsx"],
                               f"Indicateur_couverture_{pd.Timestamp(snap_date):%Y_%m_%d}.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ---------------------------------------------------------------- en-tête ---------
st.title("📦 Indicateur de couverture")
if base is None and hist is None:
    st.info("👈 Chargez le classeur Excel (ou ses onglets bruts **BASE** et **Suivi évolution**) dans la barre latérale.")
    st.stop()
if report and (report["pm_non_mappes"] or report["gest_non_mappes"] or report["erreurs_conversion_stock_secu"]):
    with st.expander("⚠️ Contrôles qualité", expanded=False):
        if report["pm_non_mappes"]:
            st.warning("PM non trouvés dans la table PM : " + ", ".join(report["pm_non_mappes"]))
        if report["gest_non_mappes"]:
            st.warning("Gestionnaires non trouvés dans la table Gest. : " + ", ".join(report["gest_non_mappes"]))
        if report["erreurs_conversion_stock_secu"]:
            st.info(f"{report['erreurs_conversion_stock_secu']} ligne(s) en erreur de conversion (#VALEUR!).")

tab_syn, tab_pm, tab_appro, tab_fr, tab_an, tab_dep = st.tabs(
    ["Synthèse", "Daily View PM", "Daily View Appro", "Daily View France", "Analyse", "Analyse dépôt"])

# ============================================================ 1. Synthèse =========
with tab_syn:
    if hist is not None:
        th = A.taux_hebdo(hist)
        last, prev = th.iloc[-1], th.iloc[-2] if len(th) > 1 else th.iloc[-1]
        c1, c2, c3 = st.columns(3)
        for col, k in zip((c1, c2, c3), ["BES", "BSP", "France"]):
            col.metric(f"Taux de couverture {k}", pct(last[k]), f"{(last[k] - prev[k]) * 100:+.1f} pt")
        plot(CH.fig_taux_hebdo(th), "taux_hebdo")
    else:
        st.caption("Chargez l'historique (Suivi évolution) pour la tendance du taux de couverture.")

    if base is not None:
        st.subheader("Taux de couverture par PM")
        s_pm = A.synthese_par_pm(base)
        g1, g2 = st.columns([2, 3])
        with g1:
            show(s_pm, height=420)
        with g2:
            plot(CH.fig_taux_par_dim(s_pm[s_pm["Total"] >= 5], "PM Nom", "PM avec ≥ 5 articles"), "taux_pm")

        st.subheader("BES/BSP × TYPE × Grpe planif.")
        show(A.synthese_par_type_planif(base), height=380)
    else:
        st.caption("Chargez BASE pour les tableaux par PM et par TYPE.")

# ============================================================ 2. Daily View PM ====
with tab_pm:
    if hist is None:
        st.caption("Historique requis (onglet « Suivi évolution »).")
    else:
        st.markdown(f"Articles sous le stock de sécurité par PM, sur les {jours} derniers jours.")
        tx = A.taux_par_date(hist, ["PM Nom"], jours, None, abc)
        if len(tx):
            plot(CH.fig_heatmap_taux(tx, "Taux de couverture par PM"), "hm_pm")
        st.subheader("Nombre d'articles non OK (Date × ETAT2)")
        show(A.evolution_comptes(hist, ["PM Nom"], jours, None, abc).reset_index(), height=420)

# ============================================================ 3. Daily View Appro =
with tab_appro:
    if hist is None:
        st.caption("Historique requis.")
    else:
        st.markdown(f"Articles sous le stock de sécurité par gestionnaire, sur les {jours} derniers jours.")
        tx = A.taux_par_date(hist, ["Code gestionnaire", "Gestionnaire nom"], jours, None, abc)
        if len(tx):
            tx.index = [" – ".join(map(str, i)) for i in tx.index]
            plot(CH.fig_heatmap_taux(tx, "Taux de couverture par gestionnaire"), "hm_appro")
        st.subheader("Nombre d'articles non OK (Date × ETAT2)")
        show(A.evolution_comptes(hist, ["Code gestionnaire", "Gestionnaire nom"], jours, None, abc).reset_index(), height=420)

# ============================================================ 4. Daily View France =
with tab_fr:
    if hist is None:
        st.caption("Historique requis.")
    else:
        ev = A.evolution_france(hist, jours, None, abc)
        c1, c2 = st.columns(2)
        with c1:
            plot(CH.fig_evolution_non_ok(ev), "ev_fr")
        with c2:
            plot(CH.fig_courbe_total(ev), "tot_fr")
        show(ev.reset_index())
        st.subheader("BES/BSP × TYPE × Date × ETAT2")
        show(A.evolution_par_type(hist, jours, None, abc).reset_index(), height=380)

# ============================================================ 5. Analyse ==========
with tab_an:
    if base is None:
        st.caption("BASE requis.")
    else:
        st.caption("Filtres de page Excel : ETAT = MTS, Schéma contingent = # (appliqués), Code ABC et BES/BSP (barre latérale).")
        g1, g2 = st.columns(2)
        with g1:
            st.subheader("Par gestionnaire (hors OK)")
            ag = A.analyse_gestionnaire(base, abc, bes_bsp)
            show(ag, height=380)
            plot(CH.fig_barres_cat(ag, "Gestionnaire nom", "Articles sous stock de sécurité par gestionnaire"), "bar_gest")
        with g2:
            st.subheader("Par PM × TYPE (hors OK)")
            pt = A.analyse_pm_type(base, abc, bes_bsp)
            show(pt, height=380)
            plot(CH.fig_barres_cat(pt, "PM Nom", "Articles sous stock de sécurité par PM"), "bar_pm")

        if hist is not None:
            st.subheader("Historique par gestionnaire (toutes dates, hors OK)")
            hg = A.historique_gestionnaire(hist)
            show(hg.reset_index().rename(columns=lambda c: c.strftime("%d/%m/%Y") if isinstance(c, pd.Timestamp) else c), height=420)

# ============================================================ 6. Analyse dépôt ====
with tab_dep:
    if base is None:
        st.caption("BASE requis.")
    else:
        dep = A.analyse_depot(base, bes_bsp)
        st.subheader("QUI appro × Dépôt × Code ABC × ETAT2")
        show(A.total_general(dep, "Total général", ["QUI appro", "Dépôt", "Code ABC"]), height=460)

        par_dep = dep.groupby("Dépôt")[[C.CAT_OK] + C.CATS_NON_OK].sum().reset_index()
        par_dep["Total"] = par_dep[[C.CAT_OK] + C.CATS_NON_OK].sum(axis=1)
        par_dep["Taux de couverture"] = par_dep[C.CAT_OK] / par_dep["Total"]
        c1, c2 = st.columns(2)
        with c1:
            plot(CH.fig_barres_cat(par_dep, "Dépôt", "Articles sous stock de sécurité par dépôt"), "bar_dep")
        with c2:
            plot(CH.fig_taux_par_dim(par_dep, "Dépôt", "Taux de couverture par dépôt"), "taux_dep")
