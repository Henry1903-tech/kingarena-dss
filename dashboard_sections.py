from __future__ import annotations

import math

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import analytics
import decision_models as dm
import insights
from config import DEFAULTS, PALETTE
from ui_components import info_line, insight_box, kpi_card
from chatbot import build_context, chat_once, context_hash, reset_model


def _fmt_money(x: float) -> str:
    try:
        x = float(x)
    except Exception:  # noqa: BLE001
        return "0"
    return f"{x:,.0f}".replace(",", ".")


def _pct(x: float) -> str:
    if not math.isfinite(float(x)):
        return "0%"
    return f"{float(x)*100:.1f}%"


def render_status_bar(df_raw: pd.DataFrame, data_path: str | None) -> None:
    cols = st.columns([1.5, 1, 1, 1])
    with cols[0]:
        if data_path:
            info_line(f"File dữ liệu: `{data_path}`")
        else:
            st.warning("Chưa tìm thấy file Excel. Hãy đặt file vào thư mục `project_new/` (xem `EXCEL_CANDIDATES` trong `config.py`).")
    with cols[1]:
        info_line(f"Số bản ghi tải: **{len(df_raw) if df_raw is not None else 0}**")
    with cols[2]:
        if df_raw is None or df_raw.empty:
            info_line("Trạng thái: **chưa có dữ liệu**")
        else:
            info_line("Trạng thái: **ok**")
    with cols[3]:
        if df_raw is not None and not df_raw.empty and df_raw.isna().mean(numeric_only=False).mean() > 0.5:
            info_line("Gợi ý: dữ liệu có nhiều ô trống, nên kiểm tra lại file.")


def render_tab_overview(df: pd.DataFrame, overview: dict[str, float]) -> None:
    st.subheader("Tổng quan")
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1:
        kpi_card("Lượt đặt", f"{int(overview['bookings']):,}".replace(",", "."), PALETTE["bookings"])
    with k2:
        kpi_card("Doanh thu", _fmt_money(overview["revenue"]), PALETTE["revenue"])
    with k3:
        kpi_card("Lợi nhuận", _fmt_money(overview["profit"]), PALETTE["profit"], sub="(nếu có cột cost/profit)")
    with k4:
        kpi_card("Công nợ", _fmt_money(overview["due"]), PALETTE["due"], sub=f"Tỷ lệ nợ: {_pct(overview['due_rate'])}")
    with k5:
        kpi_card("Giảm giá", _fmt_money(overview["discount"]), PALETTE["discount"], sub=f"Tỷ lệ giảm: {_pct(overview['discount_rate'])}")
    with k6:
        kpi_card("TB/đơn", _fmt_money(overview["avg_revenue_per_booking"]), PALETTE["occupancy"], sub=f"Giờ bán: {overview['hours_sold']:.1f}")

    st.divider()
    m = analytics.monthly_series(df)
    if m.empty:
        st.info("Chưa có đủ dữ liệu theo tháng (thiếu cột `booking_date` hoặc không có bản ghi).")
        return

    c1, c2 = st.columns([1.6, 1])
    with c1:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=m["year_month"], y=m["revenue"], name="Doanh thu", marker_color=PALETTE["revenue"]))
        fig.add_trace(go.Bar(x=m["year_month"], y=m["profit"], name="Lợi nhuận", marker_color=PALETTE["profit"]))
        fig.update_layout(barmode="group", height=380, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        fig2 = px.line(m, x="year_month", y="bookings", markers=True, title="Lượt đặt theo tháng")
        fig2.update_layout(height=380, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig2, use_container_width=True)

    c3, c4 = st.columns([1.2, 1])
    with c3:
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=m["year_month"], y=m["revenue"], name="Doanh thu", yaxis="y1", line=dict(color=PALETTE["revenue"])))
        fig3.add_trace(go.Scatter(x=m["year_month"], y=m["due"], name="Công nợ", yaxis="y2", line=dict(color=PALETTE["due"])))
        fig3.update_layout(
            height=360,
            margin=dict(l=10, r=10, t=40, b=10),
            yaxis=dict(title="Doanh thu"),
            yaxis2=dict(title="Công nợ", overlaying="y", side="right"),
            legend=dict(orientation="h"),
        )
        st.plotly_chart(fig3, use_container_width=True)
    with c4:
        yoy = analytics.yoy_table(df)
        st.markdown("**YoY theo năm**")
        st.dataframe(yoy, use_container_width=True, hide_index=True)

    st.divider()
    insight_box("Insight nhanh", insights.build_overview_insights(df))


def render_tab_customer_service(df: pd.DataFrame) -> None:
    st.subheader("Khách hàng & dịch vụ")
    if df is None or df.empty:
        st.info("Chưa có dữ liệu sau bộ lọc.")
        return

    left, right = st.columns([1.1, 1])
    with left:
        if "customer_group" in df.columns:
            cg = df["customer_group"].astype(str).value_counts().reset_index()
            cg.columns = ["customer_group", "bookings"]
            fig = px.pie(cg, names="customer_group", values="bookings", title="Phân bố nhóm khách")
            fig.update_layout(height=360, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Không có cột `customer_group` để vẽ phân bố nhóm khách.")

    with right:
        ts = analytics.time_slot_distribution(df)
        if not ts.empty:
            fig = px.bar(ts, x="time_slot", y="bookings", title="Phân bố khung giờ", text_auto=True)
            fig.update_layout(height=360, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Không có cột `time_slot` để vẽ phân bố khung giờ.")

    st.divider()
    top = analytics.top_services(df, n=12)
    c1, c2 = st.columns([1, 1])
    with c1:
        if not top.empty:
            fig = px.bar(top.sort_values("bookings", ascending=True), x="bookings", y="service", orientation="h", title="Top dịch vụ/gói theo lượt")
            fig.update_layout(height=420, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Không có cột `service_type`/`package_type` để thống kê top dịch vụ/gói.")

    with c2:
        col = "service_type" if "service_type" in df.columns else ("package_type" if "package_type" in df.columns else None)
        if col and "revenue" in df.columns:
            tmp = df.copy()
            tmp["revenue"] = pd.to_numeric(tmp["revenue"], errors="coerce").fillna(0.0)
            tmp["profit"] = pd.to_numeric(tmp.get("profit", 0.0), errors="coerce").fillna(0.0)
            g = tmp.groupby(col, dropna=False).agg(revenue=("revenue", "sum"), profit=("profit", "sum")).reset_index()
            g[col] = g[col].astype(str)
            fig = px.treemap(g, path=[col], values="revenue", color="profit", color_continuous_scale="RdYlGn", title="Treemap doanh thu (màu theo lợi nhuận)")
            fig.update_layout(height=420, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Thiếu cột để vẽ treemap doanh thu theo dịch vụ/gói.")

    st.divider()
    col = "service_type" if "service_type" in df.columns else ("package_type" if "package_type" in df.columns else None)
    if col:
        t = df.copy()
        for c in ("revenue", "profit", "discount", "due"):
            if c in t.columns:
                t[c] = pd.to_numeric(t[c], errors="coerce").fillna(0.0)
        g = (
            t.groupby(col, dropna=False)
            .agg(
                bookings=(col, "size"),
                revenue=("revenue", "sum") if "revenue" in t.columns else (col, "size"),
                profit=("profit", "sum") if "profit" in t.columns else (col, "size"),
                discount=("discount", "sum") if "discount" in t.columns else (col, "size"),
                due=("due", "sum") if "due" in t.columns else (col, "size"),
            )
            .reset_index()
        )
        g["avg_per_booking"] = g.apply(lambda r: r["revenue"] / r["bookings"] if r["bookings"] > 0 else 0.0, axis=1)
        g = g.rename(columns={col: "service_type"})
        st.markdown("**Bảng tổng hợp theo dịch vụ/gói**")
        st.dataframe(g.sort_values("revenue", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("Không có `service_type`/`package_type` để tạo bảng tổng hợp.")

    st.divider()
    insight_box("Insight", insights.build_service_insights(df))


def render_tab_fields_payment(df: pd.DataFrame) -> None:
    st.subheader("Sân & thanh toán")
    if df is None or df.empty:
        st.info("Chưa có dữ liệu sau bộ lọc.")
        return

    fs = analytics.field_summary(df)
    left, right = st.columns([1.2, 1])
    with left:
        if not fs.empty:
            fig = px.bar(fs, x="field_name", y="revenue", title="Doanh thu theo sân", text_auto=True)
            fig.update_layout(height=380, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Thiếu cột `field_name` để tổng hợp theo sân.")

    with right:
        if not fs.empty:
            fig2 = px.scatter(
                fs,
                x="hours_sold",
                y="avg_revenue_per_hour",
                size="revenue",
                hover_name="field_name",
                title="Giờ bán vs doanh thu TB/giờ",
            )
            fig2.update_layout(height=380, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    pay = analytics.payment_distribution(df)
    if not pay.empty:
        fig3 = px.pie(pay, names="payment_method", values="revenue", title="Cơ cấu doanh thu theo phương thức thanh toán")
        fig3.update_layout(height=360, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("Không có cột `payment_method` để vẽ phương thức thanh toán.")

    st.markdown("**Bảng theo sân**")
    if not fs.empty:
        st.dataframe(fs, use_container_width=True, hide_index=True)


def render_tab_discount_due(df: pd.DataFrame) -> None:
    st.subheader("Giảm giá & công nợ")
    if df is None or df.empty:
        st.info("Chưa có dữ liệu sau bộ lọc.")
        return

    disc_count = int(df.get("has_discount", pd.Series([False] * len(df))).sum()) if len(df) else 0
    due_count = int(df.get("has_due", pd.Series([False] * len(df))).sum()) if len(df) else 0
    disc_sum = float(pd.to_numeric(df.get("discount", 0.0), errors="coerce").fillna(0.0).sum())
    due_sum = float(pd.to_numeric(df.get("due", 0.0), errors="coerce").fillna(0.0).sum())

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Hồ sơ giảm giá", f"{disc_count:,}".replace(",", "."), PALETTE["discount"])
    with c2:
        kpi_card("Tổng giảm", _fmt_money(disc_sum), PALETTE["discount"])
    with c3:
        kpi_card("Hồ sơ còn nợ", f"{due_count:,}".replace(",", "."), PALETTE["due"])
    with c4:
        kpi_card("Tổng công nợ", _fmt_money(due_sum), PALETTE["due"])

    st.divider()
    m = analytics.monthly_series(df)
    if not m.empty:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=m["year_month"], y=m["discount"], name="Giảm giá", marker_color=PALETTE["discount"]))
        fig.add_trace(go.Bar(x=m["year_month"], y=m["due"], name="Công nợ", marker_color=PALETTE["due"]))
        fig.update_layout(barmode="group", height=380, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    key = "customer_id" if "customer_id" in df.columns else None
    if key:
        p = analytics.pareto_due(df, key=key, n=20)
        if not p.empty:
            figp = go.Figure()
            figp.add_trace(go.Bar(x=p[key].astype(str), y=p["due"], name="Công nợ"))
            figp.add_trace(go.Scatter(x=p[key].astype(str), y=p["cum_pct"], yaxis="y2", name="Lũy kế %", mode="lines+markers"))
            figp.update_layout(
                height=420,
                margin=dict(l=10, r=10, t=40, b=10),
                yaxis=dict(title="Công nợ"),
                yaxis2=dict(title="Lũy kế %", overlaying="y", side="right", range=[0, 100]),
                title="Pareto công nợ theo khách hàng",
            )
            st.plotly_chart(figp, use_container_width=True)
        else:
            st.info("Không có công nợ để vẽ Pareto.")
    else:
        st.info("Thiếu cột `customer_id` để vẽ Pareto công nợ.")

    st.divider()
    insight_box("Insight", insights.build_discount_due_insights(df))


def render_tab_decision_lab() -> None:
    st.subheader("Decision Lab")
    st.caption("Các mô hình ở tab này **độc lập với dữ liệu Excel** (phục vụ mô phỏng kịch bản).")

    with st.expander("6.1 Conversion Planner (upsell gói)", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            base_count = st.number_input("Số lượt/giao dịch gói cơ bản", min_value=0, value=DEFAULTS.base_count, step=50)
            base_price = st.number_input("Giá gói cơ bản", min_value=0.0, value=float(DEFAULTS.base_price), step=10_000.0)
            base_cost = st.number_input("Chi phí/đơn (cơ bản)", min_value=0.0, value=float(DEFAULTS.base_cost), step=10_000.0)
        with c2:
            high_price = st.number_input("Giá gói giá trị cao", min_value=0.0, value=float(DEFAULTS.high_price), step=10_000.0)
            high_cost = st.number_input("Chi phí/đơn (giá trị cao)", min_value=0.0, value=float(DEFAULTS.high_cost), step=10_000.0)
            current_rate = st.slider("Tỷ lệ chuyển đổi hiện tại", min_value=0.0, max_value=0.5, value=float(DEFAULTS.current_conversion_rate), step=0.01)
        with c3:
            st.write("**Kịch bản so sánh**")
            r5 = 0.05
            r30 = 0.30

        res = dm.conversion_model(
            base_count=int(base_count),
            base_price=float(base_price),
            base_cost=float(base_cost),
            high_price=float(high_price),
            high_cost=float(high_cost),
            conversion_rate=float(current_rate),
        )
        st.markdown(
            f"- Chuyển đổi: **{res.converted}** / {int(base_count)}\n"
            f"- Doanh thu: **{_fmt_money(res.revenue)}** (delta {_fmt_money(res.delta_revenue)})\n"
            f"- Lợi nhuận: **{_fmt_money(res.profit)}** (delta {_fmt_money(res.delta_profit)})"
        )

        xs = [x / 100 for x in range(5, 31)]
        ys = [
            dm.conversion_model(int(base_count), float(base_price), float(base_cost), float(high_price), float(high_cost), x).profit
            for x in xs
        ]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[x * 100 for x in xs], y=ys, mode="lines+markers", name="Lợi nhuận"))
        fig.add_vline(x=r5 * 100, line_dash="dot", line_color="#94A3B8")
        fig.add_vline(x=current_rate * 100, line_dash="dash", line_color=PALETTE["revenue"])
        fig.add_vline(x=r30 * 100, line_dash="dot", line_color="#94A3B8")
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10), xaxis_title="Tỷ lệ chuyển đổi (%)", yaxis_title="Lợi nhuận")
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("6.2 Discount Simulator (lấp đầy giờ trống)", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            baseline_bookings = st.number_input("Lượt đặt baseline", min_value=0, value=DEFAULTS.baseline_bookings, step=50)
            baseline_price = st.number_input("Giá baseline", min_value=0.0, value=float(DEFAULTS.baseline_price), step=10_000.0)
        with c2:
            unit_cost = st.number_input("Chi phí biến đổi/đơn", min_value=0.0, value=float(DEFAULTS.unit_cost), step=10_000.0)
            lift = st.number_input("Hệ số lift mỗi 1% giảm (VD 0.03 = +3%)", min_value=0.0, value=float(DEFAULTS.lift_per_1pct), step=0.01)
        with c3:
            marketing = st.number_input("Chi phí marketing /đơn/ mỗi 1% giảm", min_value=0.0, value=float(DEFAULTS.marketing_cost_per_1pct), step=500.0)
            target = st.number_input("Mục tiêu lợi nhuận", min_value=0.0, value=float(DEFAULTS.profit_target), step=1_000_000.0)

        ds = [d / 100 for d in range(0, 51)]
        sim = [
            dm.discount_fill_profit(
                discount_pct=d,
                baseline_bookings=float(baseline_bookings),
                baseline_price=float(baseline_price),
                unit_cost=float(unit_cost),
                lift_per_1pct=float(lift),
                marketing_cost_per_1pct=float(marketing),
            )
            for d in ds
        ]
        profits = [r.profit for r in sim]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[d * 100 for d in ds], y=profits, mode="lines", name="Lợi nhuận"))
        fig.add_hline(y=float(target), line_dash="dash", line_color=PALETTE["due"])

        maxr = dm.find_max_discount(
            profit_target=float(target),
            baseline_bookings=float(baseline_bookings),
            baseline_price=float(baseline_price),
            unit_cost=float(unit_cost),
            lift_per_1pct=float(lift),
            marketing_cost_per_1pct=float(marketing),
            step_pct=0.5,
        )
        fig.add_vline(x=maxr.discount_pct * 100, line_dash="dot", line_color=PALETTE["revenue"])
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10), xaxis_title="% giảm giá", yaxis_title="Lợi nhuận")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown(
            f"- Kết quả quét: **{'ĐẠT' if maxr.ok else 'KHÔNG ĐẠT'}** mục tiêu\n"
            f"- Mức giảm đề xuất: **{maxr.discount_pct*100:.1f}%**\n"
            f"- Lợi nhuận tại điểm này: **{_fmt_money(maxr.best_profit)}** (gap {_fmt_money(maxr.best_gap)})"
        )

    with st.expander("6.3 Time Allocation Optimizer (phân bổ giờ bán)", expanded=False):
        total_hours = st.number_input("Tổng giờ khả dụng", min_value=0.0, value=float(DEFAULTS.total_hours), step=10.0)
        st.write("Thiết lập các 'offer' (lợi nhuận/đơn vị, giờ/đơn vị, trần cầu):")

        offers: list[tuple[str, float, float, float]] = []
        for i, (name, p, h, ub) in enumerate(DEFAULTS.offers):
            c1, c2, c3, c4 = st.columns([1.4, 1, 1, 1])
            with c1:
                nname = st.text_input(f"Offer {i+1}", value=str(name), key=f"offer_name_{i}")
            with c2:
                pp = st.number_input("Lợi nhuận/đv", value=float(p), step=10_000.0, key=f"offer_p_{i}")
            with c3:
                hh = st.number_input("Giờ/đv", value=float(h), step=0.5, key=f"offer_h_{i}")
            with c4:
                uub = st.number_input("Trần (đv)", value=float(ub), step=10.0, key=f"offer_ub_{i}")
            offers.append((nname, float(pp), float(hh), float(uub)))

        res = dm.optimize_time_allocation(offers=offers, total_hours=float(total_hours))
        st.markdown(f"**Trạng thái**: `{res.status}`  |  **Giờ dùng**: {res.used_hours:.1f} / {float(total_hours):.1f}  |  **Tổng lợi nhuận**: {_fmt_money(res.total_profit)}")

        if res.x:
            out = pd.DataFrame({"offer": list(res.x.keys()), "units": list(res.x.values())})
            fig = px.bar(out, x="offer", y="units", title="Phân bổ đơn vị theo offer", text_auto=True)
            fig.update_layout(height=340, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(out, use_container_width=True, hide_index=True)


def render_tab_assistant(df: pd.DataFrame, overview: dict[str, float]) -> None:
    st.subheader("Trợ lý phân tích (Gemini)")
    st.caption("Tab này chỉ hoạt động khi có `GEMINI_API_KEY`. Nếu chưa có khóa, app vẫn chạy bình thường.")

    ctx = build_context(df, overview)
    ctx_md5 = context_hash(ctx)

    if "assistant_ctx_md5" not in st.session_state:
        st.session_state.assistant_ctx_md5 = None
    if "assistant_history" not in st.session_state:
        st.session_state.assistant_history = []
    if "pending_q" not in st.session_state:
        st.session_state.pending_q = None
    if "_assistant_inflight_q" not in st.session_state:
        st.session_state._assistant_inflight_q = None

    # Reset history when context changes
    if st.session_state.assistant_ctx_md5 != ctx_md5:
        st.session_state.assistant_ctx_md5 = ctx_md5
        st.session_state.assistant_history = []
        st.session_state.pending_q = None
        st.session_state._assistant_inflight_q = None
        reset_model()

    # Show status
    if not (st.secrets.get("GEMINI_API_KEY", None) or st.session_state.get("GEMINI_API_KEY") or st.session_state.get("gemini_api_key") or True):
        # No reliable way to check secrets here; we rely on exception handling below.
        pass

    with st.expander("Ngữ cảnh gửi cho mô hình (rút gọn)", expanded=False):
        st.text(ctx[:6000])

    quick = st.columns(3)
    if quick[0].button("Doanh thu tăng/giảm thế nào?"):
        st.session_state.pending_q = "Doanh thu đang tăng hay giảm? Nêu 2-3 điểm chính theo năm/tháng."
    if quick[1].button("Giờ nào là giờ đỉnh?"):
        st.session_state.pending_q = "Khung giờ nào có nhiều lượt đặt nhất? Có gợi ý gì để tăng giờ thấp điểm?"
    if quick[2].button("Rủi ro công nợ?"):
        st.session_state.pending_q = "Công nợ đang ở mức nào? Có đối tượng nào chiếm tỷ trọng công nợ lớn không?"

    for msg in st.session_state.assistant_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_in = st.chat_input("Nhập câu hỏi về dữ liệu đang xem…")
    if user_in:
        st.session_state.pending_q = user_in

    if st.session_state.pending_q and st.session_state._assistant_inflight_q is None:
        st.session_state._assistant_inflight_q = st.session_state.pending_q
        st.session_state.pending_q = None
        st.rerun()

    inflight = st.session_state._assistant_inflight_q
    if inflight:
        st.session_state.assistant_history.append({"role": "user", "content": inflight})
        with st.chat_message("user"):
            st.markdown(inflight)

        with st.chat_message("assistant"):
            with st.spinner("Đang gọi Gemini…"):
                try:
                    ans = chat_once(ctx, inflight)
                except Exception as e:  # noqa: BLE001
                    ans = (
                        "Tab trợ lý chưa kích hoạt hoặc gọi Gemini lỗi.\n\n"
                        "- Cần `pip install -r requirements.txt`\n"
                        "- Cần đặt `GEMINI_API_KEY` trong biến môi trường hoặc file `.env`\n\n"
                        f"Chi tiết lỗi: `{type(e).__name__}: {e}`"
                    )
            st.markdown(ans)
        st.session_state.assistant_history.append({"role": "assistant", "content": ans})
        st.session_state._assistant_inflight_q = None
        st.rerun()

