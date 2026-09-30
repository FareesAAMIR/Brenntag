"""Export Excel de toutes les tables calculées."""
from __future__ import annotations

import io

import pandas as pd


def _flat(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = [" | ".join(pd.Timestamp(x).strftime("%d/%m/%Y") if isinstance(x, pd.Timestamp) else str(x) for x in c)
                     for c in d.columns]
    if not isinstance(d.index, pd.RangeIndex):
        d = d.reset_index()
    d.columns = [c.strftime("%d/%m/%Y") if isinstance(c, pd.Timestamp) else str(c) for c in d.columns]
    if d.columns.duplicated().any():
        d.columns = pd.io.common.dedup_names(list(d.columns), is_potential_multiindex=False)
    return d


def to_excel_bytes(tables: dict[str, pd.DataFrame]) -> bytes:
    """Un onglet par table ; en-têtes figés, filtres, colonnes de taux formatées en %."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter", datetime_format="dd/mm/yyyy") as xw:
        wb = xw.book
        head = wb.add_format({"bold": True, "bg_color": "#1F3864", "font_color": "white", "border": 1})
        pct = wb.add_format({"num_format": "0.0%"})
        for name, df in tables.items():
            if df is None or len(df) == 0:
                continue
            d = _flat(df)
            sheet = name[:31]
            d.to_excel(xw, sheet_name=sheet, index=False)
            ws = xw.sheets[sheet]
            for j, col in enumerate(d.columns):
                ws.write(0, j, str(col), head)
                q = d.iloc[:, j].astype(str).str.len().quantile(0.9)
                width = min(45, max(10, (int(q) if pd.notna(q) else 10) + 2, len(str(col)) + 2))
                is_pct = "taux" in str(col).lower() or str(col).startswith("%")
                ws.set_column(j, j, width, pct if is_pct else None)
            ws.freeze_panes(1, 0)
            ws.autofilter(0, 0, len(d), len(d.columns) - 1)
    return buf.getvalue()
