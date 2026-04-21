from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd


_MONEY_HINTS = ("revenue", "doanh_thu", "amount", "total", "paid", "price", "cost", "profit", "due", "debt", "discount")
_DATE_HINTS = ("date", "day", "ngay", "time", "datetime", "timestamp")


def _slug(s: str) -> str:
    s = str(s).strip().lower()
    s = re.sub(r"[^\w]+", "_", s, flags=re.UNICODE)
    s = re.sub(r"__+", "_", s).strip("_")
    return s


@dataclass(frozen=True)
class Schema:
    date_cols: list[str]
    numeric_cols: list[str]
    categorical_cols: list[str]
    id_cols: list[str]
    money_cols: list[str]
    text_cols: list[str]


def infer_schema(df: pd.DataFrame, max_unique_for_cat: int = 50) -> Schema:
    if df is None or df.empty:
        return Schema(date_cols=[], numeric_cols=[], categorical_cols=[], id_cols=[], money_cols=[], text_cols=[])

    date_cols: list[str] = []
    numeric_cols: list[str] = []
    categorical_cols: list[str] = []
    id_cols: list[str] = []
    money_cols: list[str] = []
    text_cols: list[str] = []

    n = len(df)
    for col in df.columns:
        s = df[col]
        col_slug = _slug(col)

        # ID-like
        nunique = int(s.nunique(dropna=True)) if n else 0
        if nunique >= max(1, int(n * 0.85)) and nunique > 1:
            if any(k in col_slug for k in ("id", "ma_", "code", "uuid", "key")):
                id_cols.append(col)

        # Date-like: try parsing a sample
        if s.dtype.kind in {"M"}:
            date_cols.append(col)
        else:
            if any(h in col_slug for h in _DATE_HINTS):
                parsed = pd.to_datetime(s, errors="coerce")
                if parsed.notna().mean() >= 0.5:
                    date_cols.append(col)

        # Numeric-like
        if pd.api.types.is_numeric_dtype(s):
            numeric_cols.append(col)
        else:
            sn = pd.to_numeric(s, errors="coerce")
            if sn.notna().mean() >= 0.7:
                numeric_cols.append(col)

        # Money hints
        if any(h in col_slug for h in _MONEY_HINTS):
            money_cols.append(col)

    # Categorical: object cols with limited unique values
    for col in df.columns:
        if col in numeric_cols or col in date_cols:
            continue
        s = df[col]
        nunique = int(s.astype(str).nunique(dropna=True)) if len(s) else 0
        if 2 <= nunique <= max_unique_for_cat:
            categorical_cols.append(col)
        else:
            # Text-like: many unique values but not ID-ish
            if nunique > max_unique_for_cat and col not in id_cols:
                text_cols.append(col)

    # De-dup keep original order
    def _uniq(xs: list[str]) -> list[str]:
        out: list[str] = []
        for x in xs:
            if x not in out:
                out.append(x)
        return out

    return Schema(
        date_cols=_uniq([c for c in df.columns if c in date_cols]),
        numeric_cols=_uniq([c for c in df.columns if c in numeric_cols]),
        categorical_cols=_uniq([c for c in df.columns if c in categorical_cols]),
        id_cols=_uniq([c for c in df.columns if c in id_cols]),
        money_cols=_uniq([c for c in df.columns if c in money_cols]),
        text_cols=_uniq([c for c in df.columns if c in text_cols]),
    )


def pick_best_date_col(schema: Schema, prefer: tuple[str, ...] = ("booking_date", "date", "ngay")) -> str | None:
    if not schema.date_cols:
        return None
    for p in prefer:
        for c in schema.date_cols:
            if p in _slug(c):
                return c
    return schema.date_cols[0]


def pick_best_money_col(schema: Schema, prefer: tuple[str, ...] = ("revenue", "doanh_thu", "total", "amount", "profit")) -> str | None:
    if schema.money_cols:
        for p in prefer:
            for c in schema.money_cols:
                if p in _slug(c):
                    return c
        return schema.money_cols[0]
    if schema.numeric_cols:
        for p in prefer:
            for c in schema.numeric_cols:
                if p in _slug(c):
                    return c
    return schema.numeric_cols[0] if schema.numeric_cols else None


def missingness_summary(df: pd.DataFrame, top_k: int = 12) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["col", "missing_pct", "missing_count"])
    miss = df.isna().mean().sort_values(ascending=False)
    out = pd.DataFrame(
        {
            "col": miss.index.astype(str),
            "missing_pct": (miss.values * 100.0),
            "missing_count": df.isna().sum().reindex(miss.index).values,
        }
    )
    return out.head(top_k)


def to_datetime_series(df: pd.DataFrame, col: str) -> pd.Series:
    s = df[col]
    if pd.api.types.is_datetime64_any_dtype(s):
        return s
    return pd.to_datetime(s, errors="coerce")


def safe_numeric(df: pd.DataFrame, col: str) -> pd.Series:
    s = df[col] if col in df.columns else pd.Series(0.0, index=df.index)
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def summarize_numeric(df: pd.DataFrame, col: str) -> dict[str, float]:
    s = safe_numeric(df, col)
    if s.empty:
        return {"sum": 0.0, "mean": 0.0, "min": 0.0, "max": 0.0}
    return {
        "sum": float(s.sum()),
        "mean": float(s.mean()),
        "min": float(s.min()),
        "max": float(s.max()),
    }


def corr_top_pairs(df: pd.DataFrame, numeric_cols: list[str], top_k: int = 8) -> list[tuple[str, str, float]]:
    cols = [c for c in numeric_cols if c in df.columns]
    if len(cols) < 2:
        return []
    mat = df[cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    corr = mat.corr(numeric_only=True)
    pairs: list[tuple[str, str, float]] = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            a, b = cols[i], cols[j]
            v = float(corr.loc[a, b])
            if math.isfinite(v):
                pairs.append((a, b, v))
    pairs.sort(key=lambda t: abs(t[2]), reverse=True)
    return pairs[:top_k]

