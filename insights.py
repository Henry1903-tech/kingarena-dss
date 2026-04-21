from __future__ import annotations

import math

import pandas as pd

from analytics import monthly_series, pareto_due, top_services, yoy_table


def _fmt_money(x: float) -> str:
    try:
        x = float(x)
    except Exception:  # noqa: BLE001
        return "0"
    return f"{x:,.0f}".replace(",", ".")


def _pct(x: float) -> str:
    if not math.isfinite(x):
        return "0%"
    return f"{x*100:.1f}%"


def build_overview_insights(df: pd.DataFrame) -> list[str]:
    if df is None or df.empty:
        return ["Chưa có dữ liệu sau bộ lọc."]

    def _num(col: str) -> pd.Series:
        s = df[col] if col in df.columns else pd.Series(0.0, index=df.index)
        return pd.to_numeric(s, errors="coerce").fillna(0.0)

    bullets: list[str] = []

    yoy = yoy_table(df)
    if len(yoy) >= 2:
        last = yoy.iloc[-1]
        prev = yoy.iloc[-2]
        rev_growth = (last["revenue"] - prev["revenue"]) / prev["revenue"] if prev["revenue"] > 0 else 0.0
        b_growth = (last["bookings"] - prev["bookings"]) / prev["bookings"] if prev["bookings"] > 0 else 0.0
        bullets.append(
            f"So với năm trước, **doanh thu** thay đổi {_pct(rev_growth)} và **lượt đặt** thay đổi {_pct(b_growth)}."
        )

    m = monthly_series(df)
    if not m.empty:
        idx = m["revenue"].idxmax() if "revenue" in m.columns else None
        if idx is not None and idx == idx:
            ym = m.loc[idx, "year_month"]
            bullets.append(f"Tháng doanh thu cao nhất: **{ym}** (≈ {_fmt_money(m.loc[idx,'revenue'])}).")

        if "due" in m.columns and m["due"].max() > 0:
            idd = m["due"].idxmax()
            bullets.append(f"Tháng công nợ cao nhất: **{m.loc[idd,'year_month']}** (≈ {_fmt_money(m.loc[idd,'due'])}).")

    due = float(_num("due").sum())
    rev = float(_num("revenue").sum())
    if rev > 0:
        bullets.append(f"Tỷ lệ còn nợ trên doanh thu: **{_pct(due/rev)}**.")

    if "time_slot" in df.columns:
        peak = df["time_slot"].astype(str).value_counts().head(1)
        if not peak.empty:
            bullets.append(f"Khung giờ có nhiều lượt đặt nhất: **{peak.index[0]}** (≈ {int(peak.iloc[0])} lượt).")

    return bullets[:6]


def build_service_insights(df: pd.DataFrame) -> list[str]:
    if df is None or df.empty:
        return ["Chưa có dữ liệu sau bộ lọc."]

    bullets: list[str] = []
    top = top_services(df, n=8)
    if not top.empty:
        bullets.append(f"Dịch vụ/gói nhiều lượt nhất: **{top.iloc[0]['service']}** (≈ {int(top.iloc[0]['bookings'])} lượt).")
        best_profit = top.sort_values("profit", ascending=False).iloc[0]
        if float(best_profit.get("profit", 0.0)) != 0.0:
            bullets.append(
                f"Dịch vụ/gói lợi nhuận cao nhất (trong top): **{best_profit['service']}** (≈ {_fmt_money(best_profit['profit'])})."
            )

        top = top.copy()
        top["avg_per_booking"] = top.apply(
            lambda r: float(r["revenue"]) / float(r["bookings"]) if float(r["bookings"]) > 0 else 0.0, axis=1
        )
        hi = top.sort_values("avg_per_booking", ascending=False).iloc[0]
        lo = top.sort_values("avg_per_booking", ascending=True).iloc[0]
        bullets.append(f"TB/đơn cao nhất: **{hi['service']}** (≈ {_fmt_money(hi['avg_per_booking'])}/đơn).")
        bullets.append(f"TB/đơn thấp nhất: **{lo['service']}** (≈ {_fmt_money(lo['avg_per_booking'])}/đơn).")

    if "booking_status" in df.columns:
        s = df["booking_status"].astype(str).str.lower()
        cancel_rate = (s.isin({"cancel", "cancelled", "huy", "hủy", "no_show", "noshow"}).mean()) if len(s) else 0.0
        if cancel_rate > 0:
            bullets.append(f"Tỷ lệ hủy/no-show (ước tính theo cột trạng thái): **{_pct(cancel_rate)}**.")

    return bullets[:6]


def build_discount_due_insights(df: pd.DataFrame) -> list[str]:
    if df is None or df.empty:
        return ["Chưa có dữ liệu sau bộ lọc."]

    bullets: list[str] = []

    m = monthly_series(df)
    if not m.empty and "discount" in m.columns and m["discount"].max() > 0:
        i = m["discount"].idxmax()
        bullets.append(f"Tháng giảm giá nhiều nhất: **{m.loc[i,'year_month']}** (≈ {_fmt_money(m.loc[i,'discount'])}).")

    if not m.empty and "due" in m.columns and m["due"].max() > 0:
        i = m["due"].idxmax()
        bullets.append(f"Tháng công nợ cao nhất: **{m.loc[i,'year_month']}** (≈ {_fmt_money(m.loc[i,'due'])}).")

    # Abnormal due rate by service
    if "due" in df.columns and "revenue" in df.columns:
        col = "service_type" if "service_type" in df.columns else ("package_type" if "package_type" in df.columns else None)
        if col:
            tmp = df[[col, "due", "revenue"]].copy()
            tmp["due"] = pd.to_numeric(tmp["due"], errors="coerce").fillna(0.0)
            tmp["revenue"] = pd.to_numeric(tmp["revenue"], errors="coerce").fillna(0.0)
            g = tmp.groupby(col).sum(numeric_only=True)
            g["due_rate"] = g.apply(lambda r: (r["due"] / r["revenue"]) if r["revenue"] > 0 else 0.0, axis=1)
            g = g.sort_values("due_rate", ascending=False)
            if not g.empty and g.iloc[0]["due_rate"] >= 0.25 and g.iloc[0]["due"] > 0:
                bullets.append(f"Dịch vụ/gói có tỷ lệ nợ cao bất thường: **{g.index[0]}** (≈ {_pct(g.iloc[0]['due_rate'])}).")

    # Pareto due by customer or team
    key = "customer_id" if "customer_id" in df.columns else None
    if key and "due" in df.columns:
        p = pareto_due(df, key=key, n=5)
        if not p.empty and float(p["due"].sum()) > 0:
            bullets.append(f"Top {len(p)} khách chiếm ≈ **{p.iloc[-1]['cum_pct']:.1f}%** tổng công nợ.")

    return bullets[:6]

