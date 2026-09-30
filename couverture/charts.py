"""Graphiques Plotly : versions agrandies et orientées métier des visuels du classeur Excel.

Toutes les dates affichées sont au format JJ/MM/AAAA, sans heure.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from . import config as C


def _dates(d) -> pd.Series:
    """Dates -> texte JJ/MM/AAAA (jamais un datetime brut, jamais d'heure)."""
    return pd.to_datetime(d).dt.strftime(C.DATE_FMT)


def _fmt(fig, titre: str, hauteur: int = 460, y_pct: bool = False):
    fig.update_layout(template=C.PLOTLY_TEMPLATE, title=dict(text=titre, font=dict(size=17, color=C.PRIMARY)),
                      height=hauteur, margin=dict(l=10, r=10, t=55, b=10),
                      legend=dict(orientation="h", y=-0.22, title=None),
                      font=dict(size=13, family=C.FONT_FAMILY, color="#2B2F36"),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    fig.update_xaxes(gridcolor=C.BORDER, zerolinecolor=C.BORDER)
    fig.update_yaxes(gridcolor=C.BORDER, zerolinecolor=C.BORDER)
    if y_pct:
        fig.update_yaxes(tickformat=".0%")
    return fig


def _libelles(series: pd.Series) -> pd.Series:
    return series.map(C.CAT_LABELS).fillna(series)


# ------------------------------------------------------------ taux de couverture --
def fig_taux_hebdo(t: pd.DataFrame, titre: str = "Évolution du taux de couverture"):
    """Grand graphique de tendance (Synthese!C5:L8) — une semaine = un point, très lisible."""
    d = t.reset_index()
    d["Date"] = _dates(d["Date"])
    d = d.melt("Date", var_name="Périmètre", value_name="Taux")
    fig = px.line(d, x="Date", y="Taux", color="Périmètre", markers=True,
                 color_discrete_map={"France": C.PRIMARY, "BES": C.ACCENT, "BSP": C.WARNING})
    fig.update_traces(line=dict(width=5), marker=dict(size=13, line=dict(width=2, color="white")),
                      hovertemplate="%{x}<br>%{y:.1%}<extra>%{fullData.name}</extra>")
    fig.update_yaxes(tickformat=".0%", title="Taux de couverture", rangemode="tozero")
    fig.update_xaxes(title="Semaine (date d'extraction)", type="category", tickangle=-35)
    return _fmt(fig, titre, 540)


def fig_repartition_categories(df: pd.DataFrame, titre: str = "Répartition des articles"):
    """Donut OK / sous stock sécu / rupture (« combien d'articles sont sous stock de sécurité »)."""
    d = df.copy()
    d["Libellé"] = _libelles(d["ETAT2"])
    fig = px.pie(d, names="Libellé", values="Articles", hole=0.55,
                color="ETAT2", color_discrete_map=C.COULEURS)
    total = int(d["Articles"].sum())
    ok = int(d.loc[d["ETAT2"] == C.CAT_OK, "Articles"].sum())
    fig.update_traces(textinfo="percent+label", textfont_size=13, sort=False)
    fig.update_layout(annotations=[dict(text=f"{ok / total:.0%}<br>OK" if total else "–", x=0.5, y=0.5,
                                        font_size=20, showarrow=False)])
    return _fmt(fig, titre, 420)


def fig_evolution_sous_stock(t: pd.DataFrame, titre: str = "Évolution des articles sous stock de sécurité"):
    """Barres empilées RUPTURE / Inf SS par date + courbe du total (Daily VIEW FRANCE)."""
    cats = [c for c in C.CATS_NON_OK if c in t.columns]
    d = t[cats].copy()
    d.index = _dates(pd.Series(d.index))
    dm = d.reset_index(names="Date").melt("Date", var_name="ETAT2", value_name="Articles")
    dm["Catégorie"] = _libelles(dm["ETAT2"])
    peu_de_points = len(d) <= 12
    fig = px.bar(dm, x="Date", y="Articles", color="ETAT2", color_discrete_map=C.COULEURS,
                category_orders={"ETAT2": C.CATS_NON_OK[::-1]}, text="Articles" if peu_de_points else None,
                hover_data={"ETAT2": False, "Catégorie": True})
    fig.for_each_trace(lambda tr: tr.update(name=C.CAT_LABELS.get(tr.name, tr.name)))
    if "Total non OK" in t.columns:
        fig.add_scatter(x=d.index, y=t["Total non OK"].values,
                        mode="lines+markers+text" if peu_de_points else "lines+markers",
                        text=t["Total non OK"].values if peu_de_points else None, textposition="top center",
                        name="Total non OK", line=dict(color=C.PRIMARY, width=3.5, dash="dot"))
    fig.update_xaxes(type="category", title="Semaine", tickangle=-35)
    fig.update_yaxes(title="Nombre d'articles")
    return _fmt(fig, titre, 460)


def fig_tendance_totale(t: pd.DataFrame, titre: str = "Évolution du nombre d'articles non OK",
                        colonne: str = "Total non OK"):
    """Courbe de tendance agrandie : lisible aussi bien sur quelques semaines que sur tout l'historique."""
    d = t.reset_index()
    d["Date"] = _dates(d["Date"] if "Date" in d else d.iloc[:, 0])
    peu_de_points = len(d) <= 15
    fig = px.area(d, x="Date", y=colonne, markers=peu_de_points)
    fig.update_traces(line=dict(width=3.5, color=C.PRIMARY), fillcolor="rgba(11,37,69,0.10)",
                      marker=dict(size=9, color=C.PRIMARY),
                      hovertemplate="%{x}<br>%{y} articles<extra></extra>")
    if len(d):
        fig.add_annotation(x=d["Date"].iloc[-1], y=d[colonne].iloc[-1], text=f"{int(d[colonne].iloc[-1])}",
                           showarrow=True, arrowhead=2, ay=-30, font=dict(size=13, color=C.PRIMARY))
    fig.update_xaxes(type="category", tickangle=-35, title=None,
                     nticks=min(len(d), 12) if not peu_de_points else None)
    fig.update_yaxes(title="Articles")
    return _fmt(fig, titre, 360)


# ---------------------------------------------------------------- dimensions ------
def fig_heatmap_taux(t: pd.DataFrame, titre: str = "Taux de couverture par ligne et par semaine"):
    """Carte de chaleur (lignes × dates) — vue d'ensemble rapide, une couleur = un niveau de risque."""
    t = t.copy()
    t.columns = [pd.Timestamp(c).strftime(C.DATE_FMT) for c in t.columns]
    fig = px.imshow(t, aspect="auto", color_continuous_scale="RdYlGn", zmin=0.5, zmax=1,
                    labels=dict(color="Taux"), text_auto=".0%")
    fig.update_xaxes(tickangle=-35, side="bottom")
    fig.update_traces(hovertemplate="%{y}<br>%{x} : %{z:.1%}<extra></extra>")
    return _fmt(fig, titre, max(380, 26 * len(t) + 140))


def fig_top_offenders(t: pd.DataFrame, axe: str, titre: str, date_ref=None, top: int = 10):
    """Barres horizontales empilées : qui/quoi concentre le plus d'articles sous stock de sécurité (dernière date)."""
    cats = [c for c in C.CATS_NON_OK if c in t.columns]
    d = t.assign(_tot=t[cats].sum(axis=1)).sort_values("_tot").tail(top)
    dm = d.melt(id_vars=[axe], value_vars=cats, var_name="ETAT2", value_name="Articles")
    dm["Catégorie"] = _libelles(dm["ETAT2"])
    fig = px.bar(dm, y=axe, x="Articles", color="ETAT2", orientation="h", color_discrete_map=C.COULEURS,
                category_orders={"ETAT2": C.CATS_NON_OK}, hover_data={"ETAT2": False, "Catégorie": True})
    fig.for_each_trace(lambda tr: tr.update(name=C.CAT_LABELS.get(tr.name, tr.name)))
    sous_titre = f" — situation au {pd.Timestamp(date_ref).strftime(C.DATE_FMT)}" if date_ref is not None else ""
    fig.update_yaxes(title=None)
    fig.update_xaxes(title="Nombre d'articles sous stock de sécurité")
    return _fmt(fig, titre + sous_titre, max(340, 32 * len(d) + 130))


def fig_barres_cat(t: pd.DataFrame, axe: str, titre: str, horizontal: bool = True, top: int = 25):
    """Barres empilées par catégorie de couverture pour une dimension (photo du jour, périmètre BASE)."""
    cats = [c for c in C.CATS_NON_OK if c in t.columns]
    d = t.assign(_tot=t[cats].sum(axis=1)).nlargest(top, "_tot")
    dm = d.melt(id_vars=[axe], value_vars=cats, var_name="ETAT2", value_name="Articles")
    dm["Catégorie"] = _libelles(dm["ETAT2"])
    fig = px.bar(dm, y=axe if horizontal else "Articles", x="Articles" if horizontal else axe, color="ETAT2",
                orientation="h" if horizontal else "v", color_discrete_map=C.COULEURS,
                category_orders={"ETAT2": C.CATS_NON_OK}, hover_data={"ETAT2": False, "Catégorie": True})
    fig.for_each_trace(lambda tr: tr.update(name=C.CAT_LABELS.get(tr.name, tr.name)))
    if horizontal:
        fig.update_yaxes(autorange="reversed", title=None)
        fig.update_xaxes(title="Nombre d'articles")
    else:
        fig.update_xaxes(title=None)
        fig.update_yaxes(title="Nombre d'articles")
    return _fmt(fig, titre, max(360, 28 * min(top, len(d[axe].unique())) + 130))


def fig_taux_par_dim(t: pd.DataFrame, axe: str, titre: str):
    d = t.sort_values("Taux de couverture")
    couleurs = d["Taux de couverture"].map(lambda x: C.DANGER if x < 0.7 else (C.WARNING if x < 0.85 else C.ACCENT))
    fig = go.Figure(go.Bar(y=d[axe], x=d["Taux de couverture"], orientation="h",
                           marker_color=couleurs, text=d["Taux de couverture"].map("{:.0%}".format),
                           textposition="outside"))
    fig.update_xaxes(tickformat=".0%", range=[0, 1.05], title="Taux de couverture")
    fig.update_yaxes(title=None)
    return _fmt(fig, titre, max(360, 28 * len(d) + 130))


def fig_repartition_depot(t: pd.DataFrame, titre: str = "Répartition par dépôt", top: int = 10):
    """Barres verticales simples : volume d'articles non conformes par dépôt (les plus importants d'abord)."""
    cats = [c for c in C.CATS_NON_OK if c in t.columns]
    d = t.assign(_tot=t[cats].sum(axis=1)).nlargest(top, "_tot").drop(columns="_tot")
    dm = d.melt(id_vars=["Dépôt"], value_vars=cats, var_name="ETAT2", value_name="Articles")
    dm["Catégorie"] = _libelles(dm["ETAT2"])
    fig = px.bar(dm, x="Dépôt", y="Articles", color="ETAT2", color_discrete_map=C.COULEURS,
                category_orders={"ETAT2": C.CATS_NON_OK}, hover_data={"ETAT2": False, "Catégorie": True})
    fig.for_each_trace(lambda tr: tr.update(name=C.CAT_LABELS.get(tr.name, tr.name)))
    fig.update_xaxes(title=None, tickangle=-35)
    fig.update_yaxes(title="Nombre d'articles")
    return _fmt(fig, titre, 420)
