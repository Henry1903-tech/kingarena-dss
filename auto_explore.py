from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from smart_schema import (
    corr_top_pairs,
    infer_schema,
    missingness_summary,
    pick_best_date_col,
    pick_best_money_col,
    safe_numeric,
    to_datetime_series,
)


def render_auto_explore(df: pd.DataFrame) -> None:
    st.subheader("Khám phá dữ liệu (tự động)")
    st.caption("Tab này tự nhận diện cột và sinh biểu đồ theo file Excel bạn upload.")

    if df is None or df.empty:
        st.info("Chưa có dữ liệu sau bộ lọc.")
        return

    schema = infer_schema(df)

    with st.expander("Tóm tắt schema & chất lượng dữ liệu", expanded=False):
        st.write(
            {
                "rows": int(len(df)),
                "cols": int(df.shape[1]),
                "date_cols": schema.date_cols,
                "numeric_cols": schema.numeric_cols,
                "categorical_cols": schema.categorical_cols,
                "text_cols": schema.text_cols[:10],
            }
        )
        miss = missingness_summary(df, top_k=12)
        if not miss.empty:
            st.markdown("**Top cột thiếu dữ liệu**")
            st.dataframe(miss, use_container_width=True, hide_index=True)
        st.markdown("**Preview (10 dòng)**")
        st.dataframe(df.head(10), use_container_width=True, hide_index=True)

    # Choose columns interactively
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        date_col_default = pick_best_date_col(schema)
        date_col = st.selectbox("Cột thời gian", options=["(không)"] + schema.date_cols, index=(schema.date_cols.index(date_col_default) + 1) if date_col_default else 0)
        date_col = None if date_col == "(không)" else date_col
    with c2:
        y_default = pick_best_money_col(schema)
        y_num = st.selectbox(
            "Cột số (để vẽ trend / top / scatter)",
            options=["(không)"] + schema.numeric_cols,
            index=(schema.numeric_cols.index(y_default) + 1) if y_default in schema.numeric_cols else 0,
        )
        y_num = None if y_num == "(không)" else y_num
    with c3:
        group_col = st.selectbox("Nhóm (categorical)", options=["(không)"] + schema.categorical_cols, index=0)
        group_col = None if group_col == "(không)" else group_col

    st.divider()

    # 1) Time trend
    if date_col and y_num:
        dt = to_datetime_series(df, date_col)
        tmp = df.copy()
        tmp["_dt"] = dt
        tmp["_y"] = safe_numeric(df, y_num)
        tmp = tmp[tmp["_dt"].notna()].copy()
        if not tmp.empty:
            freq = st.radio("Gộp theo", options=["Ngày", "Tuần", "Tháng"], horizontal=True, index=2)
            if freq == "Ngày":
                tmp["_bucket"] = tmp["_dt"].dt.date.astype(str)
            elif freq == "Tuần":
                tmp["_bucket"] = tmp["_dt"].dt.to_period("W").astype(str)
            else:
                tmp["_bucket"] = tmp["_dt"].dt.to_period("M").astype(str)

            g = tmp.groupby("_bucket", dropna=False)["_y"].sum().reset_index()
            fig = px.line(g, x="_bucket", y="_y", markers=True, title=f"Xu hướng {y_num} theo {freq.lower()}")
            fig.update_layout(height=380, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Không có đủ dữ liệu thời gian để vẽ trend.")
    else:
        st.info("Chọn cột thời gian và cột số để xem biểu đồ xu hướng.")

    st.divider()

    # 2) Distribution for numeric
    if schema.numeric_cols:
        col = st.selectbox("Phân bố cột số", options=schema.numeric_cols, index=0)
        s = safe_numeric(df, col)
        fig = px.histogram(s, nbins=30, title=f"Phân bố: {col}")
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)
        # Outlier view
        figb = px.box(s, title=f"Boxplot (outlier): {col}")
        figb.update_layout(height=240, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(figb, use_container_width=True)

    # 3) Top categories by numeric
    if y_num:
        auto_group = group_col
        if auto_group is None and schema.categorical_cols:
            auto_group = schema.categorical_cols[0]
        if auto_group:
            tmp = df.copy()
            tmp["_g"] = tmp[auto_group].astype(str)
            tmp["_y"] = safe_numeric(df, y_num)
            g = tmp.groupby("_g")["_y"].sum().sort_values(ascending=False).head(15).reset_index()
            fig = px.bar(
                g.sort_values("_y", ascending=True),
                x="_y",
                y="_g",
                orientation="h",
                title=f"Top {auto_group} theo tổng {y_num}",
            )
            fig.update_layout(height=420, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # 4) Correlation heatmap (numeric)
    if len(schema.numeric_cols) >= 2:
        num_cols = st.multiselect("Chọn cột để xem tương quan", options=schema.numeric_cols, default=schema.numeric_cols[: min(8, len(schema.numeric_cols))])
        if len(num_cols) >= 2:
            mat = df[num_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
            corr = mat.corr(numeric_only=True)
            fig = px.imshow(corr, text_auto=True, aspect="auto", title="Ma trận tương quan (numeric)")
            fig.update_layout(height=420, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)

            pairs = corr_top_pairs(df, num_cols, top_k=8)
            if pairs:
                st.markdown("**Top cặp tương quan mạnh**")
                st.write([{"a": a, "b": b, "corr": round(v, 3)} for a, b, v in pairs])
    else:
        st.info("Chưa đủ cột số để tính tương quan.")

    st.divider()

    # 5) Scatter explorer
    if len(schema.numeric_cols) >= 2:
        st.markdown("**Scatter (khám phá quan hệ 2 biến số)**")
        cc1, cc2 = st.columns(2)
        with cc1:
            xcol = st.selectbox("Trục X", options=schema.numeric_cols, index=0, key="scatter_x")
        with cc2:
            ycol = st.selectbox("Trục Y", options=schema.numeric_cols, index=1, key="scatter_y")
        color_col = None
        if schema.categorical_cols:
            color_col = st.selectbox("Màu theo (nhóm)", options=["(không)"] + schema.categorical_cols, index=0, key="scatter_color")
            color_col = None if color_col == "(không)" else color_col

        tmp = df.copy()
        tmp["_x"] = safe_numeric(df, xcol)
        tmp["_y"] = safe_numeric(df, ycol)
        fig = px.scatter(tmp, x="_x", y="_y", color=tmp[color_col].astype(str) if color_col else None, title=f"{ycol} vs {xcol}")
        fig.update_layout(height=420, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

