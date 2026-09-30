"""Indicateur de couverture – application Streamlit (rendu outil BI d'entreprise).

Mêmes 6 pages d'analyse que le classeur Excel + une page d'aide, naviguables depuis le haut
de la barre latérale gauche : Synthèse, Daily View PM, Daily View Appro, Daily View France,
Analyse, Analyse dépôt, Comment ça marche ?
Toutes les dates s'affichent au format JJ/MM/AAAA, sans heure. Lancer : streamlit run app.py
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

# URL du formulaire externe de feedback / recommandation — à remplacer par votre lien interne.
FEEDBACK_FORM_URL = "https://forms.office.com/r/VOTRE-FORMULAIRE"

GRANDE_FENETRE = 100_000   # « toutes les dates » pour les tendances longues (Synthèse, Analyse)
PAGES = ["Synthèse", "Daily View PM", "Daily View Appro", "Daily View France", "Analyse", "Analyse dépôt"]

st.set_page_config(page_title="Indicateur de couverture", layout="wide")

# ----------------------------------------------------------------- design corporate ---
# Sidebar sombre (bleu nuit) à fort contraste : chaque widget qui garde une zone claire par
# défaut (boutons, dépôt de fichier, champs de saisie, sélecteurs) est explicitement re-coloré
# pour rester lisible — on ne se contente jamais de forcer un texte clair sans fixer son fond.
st.markdown(f"""
<style>
:root {{
  --primary: {C.PRIMARY}; --accent: {C.ACCENT}; --warn: {C.WARNING}; --danger: {C.DANGER};
  --muted: {C.MUTED}; --border: {C.BORDER}; --bg: {C.BACKGROUND}; --card: {C.CARD};
  --sb-bg: #0B2545; --sb-bg-2: #12315C; --sb-text: #EDF2F9; --sb-text-dim: #A9B8CE;
  --sb-line: rgba(255,255,255,0.14); --sb-fill: rgba(255,255,255,0.07); --sb-fill-hover: rgba(255,255,255,0.13);
}}
html, body, [class*="css"] {{ font-family: {C.FONT_FAMILY}; }}
#MainMenu, footer {{ visibility: hidden; }}
.block-container {{ padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1420px; }}
h1, h2, h3 {{ color: var(--primary); }}

/* ===== Sidebar : fond sombre + texte clair partout, avec fonds de widgets re-colorés ===== */
section[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, var(--sb-bg) 0%, var(--sb-bg-2) 100%);
  border-right: 1px solid rgba(0,0,0,0.25);
}}
section[data-testid="stSidebar"] * {{ color: var(--sb-text); }}
section[data-testid="stSidebar"] label p, section[data-testid="stSidebar"] label span {{ color: var(--sb-text) !important; }}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
section[data-testid="stSidebar"] small {{ color: var(--sb-text-dim) !important; }}
section[data-testid="stSidebar"] hr {{ border-color: var(--sb-line); margin: 14px 0; }}

/* Titres de section (NAVIGATION / DONNÉES / FILTRES) */
.sidebar-brand {{
  display: flex; align-items: center; gap: 10px; padding: 4px 2px 16px 2px;
  border-bottom: 1px solid var(--sb-line); margin-bottom: 12px;
}}
.sidebar-brand .icon {{ font-size: 1.7rem; }}
.sidebar-brand .text {{ font-size: 1.02rem; font-weight: 700; line-height: 1.15; color: #fff !important; }}
.sidebar-section {{
  font-size: 0.72rem; font-weight: 800; text-transform: uppercase; letter-spacing: .09em;
  color: var(--sb-text-dim) !important; margin: 18px 2px 6px 2px;
}}
.sidebar-section.first {{ margin-top: 2px; }}

/* Navigation : boutons pleine largeur, alignés à gauche, état actif très visible */
section[data-testid="stSidebar"] div[data-testid="stButton"] {{ margin-bottom: 3px; }}
section[data-testid="stSidebar"] div[data-testid="stButton"] > button {{
  width: 100%; text-align: left; justify-content: flex-start; font-size: 0.94rem;
  padding: 9px 12px; border-radius: 8px; transition: background 0.12s ease;
}}
section[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="secondary"] {{
  background: transparent; border: 1px solid transparent; color: var(--sb-text) !important; font-weight: 500;
}}
section[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="secondary"]:hover {{
  background: var(--sb-fill); border-color: var(--sb-line); color: #fff !important;
}}
section[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="primary"] {{
  background: var(--accent) !important; border: none; color: #fff !important; font-weight: 700;
  box-shadow: inset 4px 0 0 0 rgba(255,255,255,0.55);
}}
section[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="primary"]:hover {{
  background: var(--accent) !important; color: #fff !important;
}}

/* Boutons secondaires "utilitaires" (enregistrer, télécharger, exporter, recommandation) */
section[data-testid="stSidebar"] div[data-testid="stDownloadButton"] > button,
section[data-testid="stSidebar"] div[data-testid="stLinkButton"] > a {{
  width: 100%; background: var(--sb-fill) !important; border: 1px solid var(--sb-line) !important;
  color: var(--sb-text) !important; font-weight: 600; border-radius: 8px; text-align: center; justify-content: center;
}}
section[data-testid="stSidebar"] div[data-testid="stDownloadButton"] > button:hover,
section[data-testid="stSidebar"] div[data-testid="stLinkButton"] > a:hover {{
  background: var(--sb-fill-hover) !important; color: #fff !important;
}}

/* Champs de saisie (date, nombre, texte) : fond légèrement clair sur la sidebar, texte foncé lisible */
section[data-testid="stSidebar"] input {{
  background: #FFFFFF !important; color: #16233A !important; border-radius: 6px;
}}
section[data-testid="stSidebar"] [data-testid="stNumberInput"] button {{ background: #EEF2F7 !important; color: #16233A !important; }}

/* Sélecteurs (multiselect / selectbox) : fond translucide, texte clair, tags bien contrastés */
section[data-testid="stSidebar"] div[data-baseweb="select"] > div {{
  background: var(--sb-fill) !important; border-color: var(--sb-line) !important; color: var(--sb-text) !important;
}}
section[data-testid="stSidebar"] div[data-baseweb="select"] svg {{ fill: var(--sb-text) !important; }}
section[data-testid="stSidebar"] span[data-baseweb="tag"] {{ background: var(--accent) !important; color: #fff !important; }}

/* Dépôt de fichiers : zone et bouton "Browse files" re-colorés (sinon texte clair sur fond blanc) */
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {{
  background: var(--sb-fill) !important; border: 1px dashed var(--sb-line) !important; border-radius: 10px;
}}
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button {{
  background: rgba(255,255,255,0.16) !important; border: 1px solid var(--sb-line) !important; color: #fff !important;
}}
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] small {{ color: var(--sb-text-dim) !important; }}
section[data-testid="stSidebar"] [data-testid="stFileUploaderFile"] {{
  background: var(--sb-fill) !important; border-radius: 6px; color: var(--sb-text) !important;
}}

/* Cases à cocher et expanders */
section[data-testid="stSidebar"] [data-testid="stExpander"] {{
  background: var(--sb-fill); border: 1px solid var(--sb-line); border-radius: 8px;
}}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary {{ color: var(--sb-text) !important; }}

.page-header {{ padding-bottom: 14px; margin-bottom: 20px; border-bottom: 1px solid var(--border); }}
.page-header h1 {{ font-size: 1.55rem; font-weight: 700; margin: 0; color: var(--primary); }}
.page-header p {{ color: var(--muted); margin: 4px 0 0 0; font-size: 0.92rem; }}

.section-title {{ font-size: 1.05rem; font-weight: 700; color: var(--primary);
  margin: 1.7rem 0 0.7rem 0; padding-bottom: 0.4rem; border-bottom: 2px solid var(--border); }}

.kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 14px; margin-bottom: 0.6rem; }}
.kpi-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px;
  padding: 16px 18px; box-shadow: 0 1px 3px rgba(11,37,69,0.05); }}
.kpi-label {{ font-size: 0.76rem; color: var(--muted); text-transform: uppercase;
  letter-spacing: .04em; margin-bottom: 6px; }}
.kpi-value {{ font-size: 1.7rem; font-weight: 700; color: var(--primary); line-height: 1.1; }}
.kpi-delta {{ font-size: 0.83rem; margin-top: 6px; font-weight: 600; }}
.kpi-delta.up {{ color: var(--accent); }}
.kpi-delta.down {{ color: var(--danger); }}
.kpi-delta.flat {{ color: var(--muted); }}

.info-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px;
  padding: 18px 20px; margin-bottom: 14px; }}
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------- utilitaires ---
def page_header(title: str, subtitle: str | None = None):
    sub = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(f'<div class="page-header"><h1>{title}</h1>{sub}</div>', unsafe_allow_html=True)


def section(title: str):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)


def kpi_row(items: list[dict]):
    """items: [{label, value, delta (optionnel), positive (bool, optionnel)}]"""
    cards = []
    for i in items:
        delta_html = ""
        if i.get("delta"):
            cls = "up" if i.get("positive") else ("down" if i.get("positive") is False else "flat")
            delta_html = f'<div class="kpi-delta {cls}">{i["delta"]}</div>'
        cards.append(f'<div class="kpi-card"><div class="kpi-label">{i["label"]}</div>'
                     f'<div class="kpi-value">{i["value"]}</div>{delta_html}</div>')
    st.markdown(f'<div class="kpi-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def prep_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Toute date affichée devient un texte JJ/MM/AAAA : ni Timestamp, ni heure."""
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        def lvl(x):
            if isinstance(x, pd.Timestamp):
                return x.strftime(C.DATE_FMT)
            return C.CAT_LABELS.get(x, x)
        df.columns = [" — ".join(str(lvl(x)) for x in tup) for tup in df.columns]
    else:
        df.columns = [c.strftime(C.DATE_FMT) if isinstance(c, pd.Timestamp) else c for c in df.columns]
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].dt.strftime(C.DATE_FMT)
    return df


def show(df: pd.DataFrame | None, height: int | str | None = None, key: str | None = None):
    if df is None or len(df) == 0:
        st.caption("Aucune donnée pour ce périmètre.")
        return
    height = height if height is not None else "content"   # Streamlit >=1.5x n'accepte plus None
    df = prep_dates(df)
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


def fmt_date(d) -> str:
    return pd.Timestamp(d).strftime(C.DATE_FMT)


def delta_pts(cur, prev) -> tuple[str, bool | None]:
    if cur is None or prev is None or pd.isna(cur) or pd.isna(prev):
        return "", None
    diff = (cur - prev) * 100
    return f"{diff:+.1f} pt vs semaine préc.", diff >= 0


def delta_count(cur, prev, bon_si_baisse: bool = True) -> tuple[str, bool | None]:
    if cur is None or prev is None:
        return "", None
    diff = cur - prev
    positive = (diff <= 0) if bon_si_baisse else (diff >= 0)
    return f"{diff:+d} vs semaine préc.", positive


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
st.sidebar.markdown('<div class="sidebar-brand"><span class="text">Indicateur de couverture</span></div>',
                    unsafe_allow_html=True)

if "page" not in st.session_state or st.session_state["page"] not in PAGES:
    st.session_state["page"] = PAGES[0]

st.sidebar.markdown('<div class="sidebar-section first">Navigation</div>', unsafe_allow_html=True)
for nom in PAGES:
    actif = st.session_state["page"] == nom
    if st.sidebar.button(nom, key=f"nav_{nom}", type="primary" if actif else "secondary"):
        st.session_state["page"] = nom
        st.rerun()
onglet = st.session_state["page"]

st.sidebar.markdown('<div class="sidebar-section">Données</div>', unsafe_allow_html=True)
st.sidebar.caption("Il faut importer les données en déposant le fichier ci-dessous.")
uploads = st.sidebar.file_uploader(
    "Fichiers sources (.xlsx / .csv)", type=["xlsx", "xlsm", "csv"], accept_multiple_files=True,
    help="Déposez l'onglet BASE (obligatoire) et, si vous en avez un, l'onglet Suivi évolution. "
         "Les onglets de résultats du classeur Excel sont ignorés.")

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

st.sidebar.markdown('<div class="sidebar-section">Filtres</div>', unsafe_allow_html=True)
snap_date = st.sidebar.date_input(
    "Date de l'extraction BASE", value=L.date_from_filename(base_filename) or dt.date.today(),
    format="DD/MM/YYYY")
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

hist_f = hist[hist["BES/BSP"].isin(bes_bsp)] if (hist is not None and bes_bsp) else hist

with st.sidebar.expander("Historique & export"):
    if hist is not None and len(hist):
        st.caption(f"{hist['Date'].nunique()} dates, du {fmt_date(hist['Date'].min())} au {fmt_date(hist['Date'].max())}")
        c1, c2 = st.columns(2)
        if c1.button("Enregistrer", help="Écrit data/historique.csv.gz."):
            try:
                H.save_history(hist)
                st.success("Enregistré.")
            except OSError as e:
                st.warning(f"Écriture impossible ({e}).")
        c2.download_button("Télécharger", hist.to_csv(index=False, sep=";").encode("utf-8-sig"),
                           f"historique_{pd.Timestamp(snap_date):%Y_%m_%d}.csv", "text/csv")
    if base is not None:
        if st.button("Préparer l'export Excel"):
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
            st.download_button("Télécharger l'export", st.session_state["xlsx"],
                               f"Indicateur_couverture_{pd.Timestamp(snap_date):%Y_%m_%d}.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.sidebar.markdown("<hr/>", unsafe_allow_html=True)
st.sidebar.link_button("Faire une recommandation", FEEDBACK_FORM_URL, width="stretch")

# ---------------------------------------------------------------- garde-fous ------
if base is None and hist is None:
    page_header(onglet)
    st.info("Chargez le classeur Excel (ou l'onglet brut **BASE**) dans le menu latéral.")
    st.stop()

if report and (report["pm_non_mappes"] or report["gest_non_mappes"] or report["erreurs_conversion_stock_secu"]):
    with st.expander("Contrôles qualité des données"):
        if report["pm_non_mappes"]:
            st.warning("PM non trouvés dans la table PM : " + ", ".join(report["pm_non_mappes"]))
        if report["gest_non_mappes"]:
            st.warning("Gestionnaires non trouvés dans la table Gest. : " + ", ".join(report["gest_non_mappes"]))
        if report["erreurs_conversion_stock_secu"]:
            st.info(f"{report['erreurs_conversion_stock_secu']} ligne(s) en erreur de conversion (#VALEUR!).")

# ============================================================ 1. Synthèse =========
if onglet == "Synthèse":
    page_header("Synthèse", f"Vue de pilotage — situation au {fmt_date(snap_date)}")

    if hist is not None:
        th = A.taux_hebdo(hist)
        last, prev = th.iloc[-1], th.iloc[-2] if len(th) > 1 else th.iloc[-1]
        ev_all = A.evolution_france(hist_f if hist_f is not None else hist, GRANDE_FENETRE, None, abc)
        cur_tot = ev_all["Total non OK"].iloc[-1] if len(ev_all) else None
        prev_tot = ev_all["Total non OK"].iloc[-2] if len(ev_all) > 1 else None
        cur_rupt = ev_all[C.CAT_RUPTURE].iloc[-1] if len(ev_all) else None
        prev_rupt = ev_all[C.CAT_RUPTURE].iloc[-2] if len(ev_all) > 1 else None
        d_taux, p_taux = delta_pts(last["France"], prev["France"])
        d_tot, p_tot = delta_count(cur_tot, prev_tot)
        d_rupt, p_rupt = delta_count(cur_rupt, prev_rupt)
        articles_mts = A.kpi_headline(base)["France"]["articles_mts"] if base is not None else None
        kpi_row([
            {"label": "Taux de couverture France", "value": pct(last["France"]), "delta": d_taux, "positive": p_taux},
            {"label": "Articles sous stock de sécurité", "value": f"{int(cur_tot):,}".replace(",", " ") if cur_tot is not None else "–",
             "delta": d_tot, "positive": p_tot},
            {"label": "Articles en rupture", "value": f"{int(cur_rupt):,}".replace(",", " ") if cur_rupt is not None else "–",
             "delta": d_rupt, "positive": p_rupt},
            {"label": "Articles MTS suivis", "value": f"{articles_mts:,}".replace(",", " ") if articles_mts is not None else "–"},
        ])
        section("Évolution du taux de couverture")
        st.caption(f"Semaine de référence : {fmt_date(th.index[-1])} · {len(th)} dernières semaines")
        plot(CH.fig_taux_hebdo(th), "taux_hebdo")
    else:
        st.caption("Chargez l'historique (Suivi évolution) pour la tendance du taux de couverture.")

    if base is not None:
        p = G.perimetre(base, exclure_contingent)
        if abc:
            p = p[p["Code ABC"].isin(abc)]
        if bes_bsp:
            p = p[p["BES/BSP"].isin(bes_bsp)]

        section("Où en est-on aujourd'hui ?")
        g1, g2 = st.columns(2)
        with g1:
            plot(CH.fig_repartition_categories(A.repartition_categories(p),
                                               f"Répartition des articles au {fmt_date(snap_date)}"), "rep_cat")
        with g2:
            if hist_f is not None:
                ev_tot = A.evolution_france(hist_f, GRANDE_FENETRE, None, abc)
                plot(CH.fig_tendance_totale(ev_tot, "Évolution des articles sous stock de sécurité"), "ev_syn")
            else:
                st.caption("Historique requis pour la tendance.")

        section("Répartition par dépôt")
        pdep = A.par_depot(base, bes_bsp)
        plot(CH.fig_repartition_depot(pdep, "Articles sous stock de sécurité par dépôt (top 10)"), "dep_syn")

        section("Points d'attention")
        s_pm = A.synthese_par_pm(p)
        alerte = s_pm[s_pm["Total"] >= 5].nsmallest(5, "Taux de couverture")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**PM les plus en difficulté** (≥ 5 articles)")
            show(alerte[["BES/BSP", "PM Nom", C.CAT_RUPTURE, C.CAT_0_50, C.CAT_51_99, "Taux de couverture"]])
        with c2:
            st.markdown("**Dépôts les plus en difficulté**")
            show(pdep.nsmallest(5, "Taux de couverture")[["Dépôt", C.CAT_RUPTURE, C.CAT_0_50, C.CAT_51_99, "Taux de couverture"]])
    else:
        st.caption("Chargez BASE pour la photo du jour et les points d'attention.")

# ============================================================ 2. Daily View PM ====
elif onglet == "Daily View PM":
    page_header("Daily View PM", f"Suivi par Product Manager — fenêtre de {jours} jours")
    if hist is None:
        st.caption("Historique requis (onglet « Suivi évolution »).")
    else:
        top, date_ref = A.top_par_dimension(hist, "PM Nom", abc, n=10)
        if len(top):
            section("Qui concentre le plus d'articles sous stock de sécurité ?")
            plot(CH.fig_top_offenders(top, "PM Nom", "PM les plus concernés par un manque de stock", date_ref), "top_pm")
        tx = A.taux_par_date(hist, ["PM Nom"], jours, None, abc)
        if len(tx):
            section("Évolution du taux de couverture par PM")
            plot(CH.fig_heatmap_taux(tx, "Taux de couverture par PM et par semaine"), "hm_pm")
        section("Détail : nombre d'articles non OK (semaine × catégorie)")
        show(A.evolution_comptes(hist, ["PM Nom"], jours, None, abc).reset_index(), height=420)

# ============================================================ 3. Daily View Appro =
elif onglet == "Daily View Appro":
    page_header("Daily View Appro", f"Suivi par gestionnaire / approvisionneur — fenêtre de {jours} jours")
    if hist is None:
        st.caption("Historique requis.")
    else:
        top, date_ref = A.top_par_dimension(hist, "Gestionnaire nom", abc, n=10)
        if len(top):
            section("Qui concentre le plus d'articles sous stock de sécurité ?")
            plot(CH.fig_top_offenders(top, "Gestionnaire nom", "Gestionnaires les plus concernés par un manque de stock", date_ref), "top_gest")
        tx = A.taux_par_date(hist, ["Code gestionnaire", "Gestionnaire nom"], jours, None, abc)
        if len(tx):
            tx.index = [" – ".join(map(str, i)) for i in tx.index]
            section("Évolution du taux de couverture par gestionnaire")
            plot(CH.fig_heatmap_taux(tx, "Taux de couverture par gestionnaire et par semaine"), "hm_appro")
        section("Détail : nombre d'articles non OK (semaine × catégorie)")
        show(A.evolution_comptes(hist, ["Code gestionnaire", "Gestionnaire nom"], jours, None, abc).reset_index(), height=420)

# ============================================================ 4. Daily View France =
elif onglet == "Daily View France":
    page_header("Daily View France", f"Vue nationale — fenêtre de {jours} jours")
    if hist is None:
        st.caption("Historique requis.")
    else:
        ev = A.evolution_france(hist, jours, None, abc)
        section("Évolution nationale des articles sous stock de sécurité")
        plot(CH.fig_evolution_sous_stock(ev, "Ruptures et sous stock de sécurité par semaine"), "ev_fr")
        top, date_ref = A.top_par_dimension(hist, "TYPE", abc, n=10)
        if len(top):
            section("Quelles familles de produits sont les plus concernées ?")
            plot(CH.fig_top_offenders(top, "TYPE", "Répartition par TYPE (dernière semaine)", date_ref), "top_type")
        section("Détail : BES/BSP × TYPE × semaine × catégorie")
        show(A.evolution_par_type(hist, jours, None, abc).reset_index(), height=380)

# ============================================================ 5. Analyse ==========
elif onglet == "Analyse":
    page_header("Analyse", f"Articles sous stock de sécurité — situation au {fmt_date(snap_date)}")
    if base is None:
        st.caption("BASE requis.")
    else:
        g1, g2 = st.columns(2)
        with g1:
            if hist_f is not None:
                h = hist_f
                if abc:
                    h = h[h["Code ABC"].isin(abc)]
                ev = A.evolution_france(h, GRANDE_FENETRE, None, None)
                plot(CH.fig_tendance_totale(ev, "Évolution du nombre total d'articles sous stock de sécurité"), "tend_an")
            else:
                st.caption("Historique requis pour la tendance.")
        with g2:
            p0 = G.perimetre(base, exclure_contingent)
            if abc:
                p0 = p0[p0["Code ABC"].isin(abc)]
            if bes_bsp:
                p0 = p0[p0["BES/BSP"].isin(bes_bsp)]
            plot(CH.fig_repartition_categories(A.repartition_categories(p0), f"Répartition au {fmt_date(snap_date)}"), "rep_an")

        section("Où se situent les problèmes ?")
        g3, g4 = st.columns(2)
        with g3:
            ag = A.analyse_gestionnaire(base, abc, bes_bsp)
            plot(CH.fig_barres_cat(ag, "Gestionnaire nom", "Par gestionnaire"), "bar_gest")
        with g4:
            pt = A.analyse_pm_type(base, abc, bes_bsp)
            plot(CH.fig_barres_cat(pt, "PM Nom", "Par PM"), "bar_pm")
        t1, t2 = st.columns(2)
        with t1:
            show(ag, height=320)
        with t2:
            show(pt, height=320)

        if hist is not None:
            section("Historique par gestionnaire (toutes dates, hors OK)")
            show(A.historique_gestionnaire(hist).reset_index(), height=420)

# ============================================================ 6. Analyse dépôt ====
elif onglet == "Analyse dépôt":
    page_header("Analyse dépôt", f"Répartition géographique — situation au {fmt_date(snap_date)}")
    if base is None:
        st.caption("BASE requis.")
    else:
        pdep = A.par_depot(base, bes_bsp)
        section("Articles sous stock de sécurité par dépôt")
        g1, g2 = st.columns(2)
        with g1:
            plot(CH.fig_repartition_depot(pdep, "Volume par dépôt (top 10)"), "dep_bar")
        with g2:
            plot(CH.fig_taux_par_dim(pdep, "Dépôt", "Taux de couverture par dépôt"), "dep_taux")

        section("Détail : QUI appro × Dépôt × Code ABC × ETAT2")
        dep = A.analyse_depot(base, bes_bsp)
        show(A.total_general(dep, "Total général", ["QUI appro", "Dépôt", "Code ABC"]), height=440)
