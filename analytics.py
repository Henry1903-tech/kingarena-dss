from __future__ import annotations

import pandas as pd


def monthly_series(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns monthly aggregated metrics:
    year_month, bookings, revenue, profit, due, discount, hours_sold
    """
    if df is None or df.empty or "year_month" not in df.columns:
        return pd.DataFrame(
            columns=["year_month", "bookings", "revenue", "profit", "due", "discount", "hours_sold"]
        )

    g = df.groupby("year_month", dropna=False)
    out = pd.DataFrame(
        {
            "year_month": g.size().index.astype(str),
            "bookings": g.size().values,
            "revenue": g["revenue"].sum(min_count=1) if "revenue" in df.columns else 0,
            "profit": g["profit"].sum(min_count=1) if "profit" in df.columns else 0,
            "due": g["due"].sum(min_count=1) if "due" in df.columns else 0,
            "discount": g["discount"].sum(min_count=1) if "discount" in df.columns else 0,
            "hours_sold": g["duration_hours"].sum(min_count=1) if "duration_hours" in df.columns else 0,
        }
    )
    for c in ("revenue", "profit", "due", "discount", "hours_sold"):
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0)
    return out.sort_values("year_month")


def yoy_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a YoY summary by year: bookings, revenue, profit, due, discount, hours_sold.
    """
    if df is None or df.empty or "year" not in df.columns:
        return pd.DataFrame(columns=["year", "bookings", "revenue", "profit", "due", "discount", "hours_sold"])

    g = df.groupby("year", dropna=False)
    out = pd.DataFrame(
        {
            "year": g.size().index.astype("Int64"),
            "bookings": g.size().values,
            "revenue": g["revenue"].sum(min_count=1) if "revenue" in df.columns else 0,
            "profit": g["profit"].sum(min_count=1) if "profit" in df.columns else 0,
            "due": g["due"].sum(min_count=1) if "due" in df.columns else 0,
            "discount": g["discount"].sum(min_count=1) if "discount" in df.columns else 0,
            "hours_sold": g["duration_hours"].sum(min_count=1) if "duration_hours" in df.columns else 0,
        }
    )
    for c in ("revenue", "profit", "due", "discount", "hours_sold"):
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0)
    return out.sort_values("year")


def top_services(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    col = "service_type" if "service_type" in (df.columns if df is not None else []) else ("package_type" if "package_type" in (df.columns if df is not None else []) else None)
    if df is None or df.empty or not col:
        return pd.DataFrame(columns=["service", "bookings", "revenue", "profit"])

    g = df.groupby(col, dropna=False)
    out = pd.DataFrame(
        {
            "service": g.size().index.astype(str),
            "bookings": g.size().values,
            "revenue": g["revenue"].sum(min_count=1) if "revenue" in df.columns else 0,
            "profit": g["profit"].sum(min_count=1) if "profit" in df.columns else 0,
        }
    )
    out["revenue"] = pd.to_numeric(out["revenue"], errors="coerce").fillna(0.0)
    out["profit"] = pd.to_numeric(out["profit"], errors="coerce").fillna(0.0)
    return out.sort_values(["bookings", "revenue"], ascending=False).head(n)


def time_slot_distribution(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "time_slot" not in df.columns:
        return pd.DataFrame(columns=["time_slot", "bookings"])
    g = df.groupby("time_slot", dropna=False).size().reset_index(name="bookings")
    g["time_slot"] = g["time_slot"].astype(str)
    return g.sort_values("bookings", ascending=False)


def field_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "field_name" not in df.columns:
        return pd.DataFrame(columns=["field_name", "bookings", "hours_sold", "revenue", "profit", "due"])

    g = df.groupby("field_name", dropna=False)
    out = pd.DataFrame(
        {
            "field_name": g.size().index.astype(str),
            "bookings": g.size().values,
            "hours_sold": g["duration_hours"].sum(min_count=1) if "duration_hours" in df.columns else 0,
            "revenue": g["revenue"].sum(min_count=1) if "revenue" in df.columns else 0,
            "profit": g["profit"].sum(min_count=1) if "profit" in df.columns else 0,
            "due": g["due"].sum(min_count=1) if "due" in df.columns else 0,
        }
    )
    for c in ("hours_sold", "revenue", "profit", "due"):
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0)
    out["avg_revenue_per_hour"] = out.apply(lambda r: r["revenue"] / r["hours_sold"] if r["hours_sold"] > 0 else 0.0, axis=1)
    out["due_rate"] = out.apply(lambda r: r["due"] / r["revenue"] if r["revenue"] > 0 else 0.0, axis=1)
    return out.sort_values("revenue", ascending=False)


def payment_distribution(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "payment_method" not in df.columns:
        return pd.DataFrame(columns=["payment_method", "bookings", "revenue"])
    g = df.groupby("payment_method", dropna=False)
    out = pd.DataFrame(
        {
            "payment_method": g.size().index.astype(str),
            "bookings": g.size().values,
            "revenue": g["revenue"].sum(min_count=1) if "revenue" in df.columns else 0,
        }
    )
    out["revenue"] = pd.to_numeric(out["revenue"], errors="coerce").fillna(0.0)
    return out.sort_values("revenue", ascending=False)


def pareto_due(df: pd.DataFrame, key: str = "customer_id", n: int = 20) -> pd.DataFrame:
    if df is None or df.empty or "due" not in df.columns or key not in df.columns:
        return pd.DataFrame(columns=[key, "due", "cum_pct"])

    tmp = df[[key, "due"]].copy()
    tmp["due"] = pd.to_numeric(tmp["due"], errors="coerce").fillna(0.0)
    g = tmp.groupby(key, dropna=False)["due"].sum().sort_values(ascending=False).reset_index()
    total = float(g["due"].sum())
    g["cum_due"] = g["due"].cumsum()
    g["cum_pct"] = g["cum_due"].apply(lambda x: (x / total) * 100 if total > 0 else 0.0)
    return g.head(n)

