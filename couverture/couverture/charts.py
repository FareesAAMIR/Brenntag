"""Graphiques Plotly (équivalents des graphiques du classeur + visualisations complémentaires)."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from . import config as C


def _fmt(fig, titre: str, hauteur: int = 420):
    fig.update_layout(title=titre, height=hauteur, margin=dict(l=10, r=10, t=50, b=10),
                      legend=dict(orientation="h", y=-0.2))
    return fig


def fig_taux_hebdo(t: pd.DataFrame):
    """Courbes du taux de couverture BES / BSP / France (Synthese!C5:L8)."""
    d = t.reset_index().melt("Date", var_name="Périmètre", value_name="Taux")
    fig = px.line(d, x="Date", y="Taux", color="Périmètre", markers=True)
    fig.update_yaxes(tickformat=".0%")
    fig.update_xaxes(tickformat="%d/%m", type="category" if len(t) < 15 else "date")
    return _fmt(fig, "Taux de couverture hebdomadaire")


def fig_evolution_non_ok(t: pd.DataFrame):
    """Barres empilées RUPTURE / Inf SS par date (Daily VIEW FRANCE!Y34:AB41)."""
    d = t.drop(columns=["Total non OK"], errors="ignore").reset_index().melt("Date", var_name="ETAT2", value_name="Articles")
    fig = px.bar(d, x="Date", y="Articles", color="ETAT2", color_discrete_map=C.COULEURS,
                 category_orders={"ETAT2": C.CATS_NON_OK[::-1]}, text_auto=True)
    fig.update_xaxes(type="category", tickformat="%d/%m")
    return _fmt(fig, "Articles sous stock de sécurité par date")


def fig_courbe_total(t: pd.DataFrame):
    fig = px.line(t.reset_index(), x="Date", y="Total non OK", markers=True)
    fig.update_xaxes(type="category", tickformat="%d/%m")
    return _fmt(fig, "Total d'articles non OK", 320)


def fig_heatmap_taux(t: pd.DataFrame, titre="Taux de couverture par ligne et par date"):
    """Carte de chaleur (lignes × dates) – Daily VIEW PM!A68:…"""
    t = t.copy()
    t.columns = [pd.Timestamp(c).strftime("%d/%m/%Y") for c in t.columns]
    fig = px.imshow(t, aspect="auto", color_continuous_scale="RdYlGn", zmin=0.5, zmax=1,
                    labels=dict(color="Taux"))
    return _fmt(fig, titre, max(380, 22 * len(t) + 120))


def fig_lignes_taux(t: pd.DataFrame, titre="Évolution du taux de couverture"):
    d = t.T
    d.index = pd.to_datetime(d.index)
    d.index.name = "Date"
    d = d.reset_index().melt("Date", var_name="Ligne", value_name="Taux")
    d["Ligne"] = d["Ligne"].astype(str)
    fig = px.line(d, x="Date", y="Taux", color="Ligne", markers=True)
    fig.update_yaxes(tickformat=".0%")
    return _fmt(fig, titre, 460)


def fig_barres_cat(t: pd.DataFrame, axe: str, titre: str, horizontal=True, top: int = 25):
    """Barres empilées par catégorie de couverture pour une dimension (PM, gestionnaire, dépôt…)."""
    cats = [c for c in C.CATS_NON_OK if c in t.columns]
    d = t.assign(_tot=t[cats].sum(axis=1)).nlargest(top, "_tot")
    d = d.melt(id_vars=[axe], value_vars=cats, var_name="ETAT2", value_name="Articles")
    fig = px.bar(d, y=axe if horizontal else "Articles", x="Articles" if horizontal else axe, color="ETAT2",
                 orientation="h" if horizontal else "v", color_discrete_map=C.COULEURS,
                 category_orders={"ETAT2": C.CATS_NON_OK})
    if horizontal:
        fig.update_yaxes(autorange="reversed")
    return _fmt(fig, titre, max(360, 24 * min(top, len(d[axe].unique())) + 120))


def fig_taux_par_dim(t: pd.DataFrame, axe: str, titre: str):
    d = t.sort_values("Taux de couverture")
    fig = px.bar(d, x="Taux de couverture", y=axe, orientation="h", text=d["Taux de couverture"].map("{:.0%}".format))
    fig.update_xaxes(tickformat=".0%", range=[0, 1])
    return _fmt(fig, titre, max(360, 24 * len(d) + 120))


def fig_repartition(df: pd.DataFrame, noms: str, valeurs: str, titre: str):
    fig = px.pie(df, names=noms, values=valeurs, hole=0.45)
    return _fmt(fig, titre, 340)


def fig_treemap(df: pd.DataFrame, chemin: list[str], valeur: str, titre: str):
    d = df[df[valeur] > 0]
    fig = px.treemap(d, path=chemin, values=valeur)
    return _fmt(fig, titre, 480)


def fig_jauge(taux: float, titre: str):
    fig = go.Figure(go.Indicator(mode="gauge+number", value=taux * 100,
                                 number={"suffix": " %", "valueformat": ".1f"},
                                 gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#2E9E5B"},
                                        "steps": [{"range": [0, 70], "color": "#f7d6d6"},
                                                  {"range": [70, 85], "color": "#fbe9c6"},
                                                  {"range": [85, 100], "color": "#d9efe2"}]}))
    return _fmt(fig, titre, 240)
