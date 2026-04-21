from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import dashboard_sections as sections
from config import APP_ICON, APP_TITLE
from data_loader import Filters, apply_filters, compute_overview, load_data, load_data_from_upload
from ui_components import inject_css


def _csv_download(df: pd.DataFrame) -> bytes:
    if df is None:
        return b""
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def main() -> None:
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)

    st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="wide")
    inject_css()

    st.title(f"{APP_ICON} {APP_TITLE}")

    # Sidebar filters
    with st.sidebar:
        st.header("Nguồn dữ liệu")
        up = st.file_uploader("Tải file Excel (.xlsx) để xem dashboard", type=["xlsx"])
        st.caption("Nếu không tải lên, app sẽ thử tự dò file theo `EXCEL_CANDIDATES` trong `config.py`.")
        st.divider()

    if up is not None:
        try:
            df_raw, data_path = load_data_from_upload(up.name, up.getvalue())
        except Exception as e:  # noqa: BLE001
            df_raw, data_path = pd.DataFrame(), None
            st.error(
                "Không đọc được file bạn tải lên.\n\n"
                f"- Chi tiết: `{type(e).__name__}: {e}`\n"
                "- Gợi ý: hãy đảm bảo file là `.xlsx` chuẩn (không password), thử **Save As** lại từ Excel, "
                "hoặc thử export lại nếu lấy từ Google Sheets."
            )
    else:
        df_raw, data_path = load_data()

    sections.render_status_bar(df_raw, data_path)

    with st.sidebar:
        st.header("Bộ lọc")

        years = sorted(set(pd.to_numeric(df_raw.get("year", pd.Series([], dtype="float64")), errors="coerce").dropna().astype(int).tolist()))
        months = sorted(set(pd.to_numeric(df_raw.get("month", pd.Series([], dtype="float64")), errors="coerce").dropna().astype(int).tolist()))
        fields = sorted(set(df_raw.get("field_name", pd.Series([], dtype="object")).dropna().astype(str).tolist()))
        time_slots = sorted(set(df_raw.get("time_slot", pd.Series([], dtype="object")).dropna().astype(str).tolist()))
        payment_methods = sorted(set(df_raw.get("payment_method", pd.Series([], dtype="object")).dropna().astype(str).tolist()))
        statuses = sorted(set(df_raw.get("booking_status", pd.Series([], dtype="object")).dropna().astype(str).tolist()))

        sel_years = st.multiselect("Năm", options=years, default=years[-1:] if years else [])
        sel_months = st.multiselect("Tháng", options=months, default=[])
        sel_fields = st.multiselect("Sân", options=fields, default=[])
        sel_time_slots = st.multiselect("Khung giờ", options=time_slots, default=[])
        sel_pay = st.multiselect("Thanh toán", options=payment_methods, default=[])
        sel_status = st.multiselect("Trạng thái", options=statuses, default=[])

        f = Filters(
            years=sel_years or None,
            months=sel_months or None,
            fields=sel_fields or None,
            time_slots=sel_time_slots or None,
            payment_methods=sel_pay or None,
            statuses=sel_status or None,
        )

        df = apply_filters(df_raw, f)

        st.divider()
        st.download_button(
            "Xuất CSV đã lọc",
            data=_csv_download(df),
            file_name="kingarena_filtered.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=(df is None or df.empty),
        )

        if df is not None and not df.empty:
            st.caption(f"Sau lọc: {len(df)} bản ghi")
        else:
            st.caption("Sau lọc: 0 bản ghi")

    overview = compute_overview(df)

    tab_overview, tab_customer, tab_fields, tab_disc, tab_decision, tab_assistant = st.tabs(
        ["Tổng quan", "Khách hàng & dịch vụ", "Sân & thanh toán", "Giảm giá & công nợ", "Decision Lab", "Trợ lý phân tích"]
    )

    with tab_overview:
        sections.render_tab_overview(df, overview)
    with tab_customer:
        sections.render_tab_customer_service(df)
    with tab_fields:
        sections.render_tab_fields_payment(df)
    with tab_disc:
        sections.render_tab_discount_due(df)
    with tab_decision:
        sections.render_tab_decision_lab()
    with tab_assistant:
        sections.render_tab_assistant(df, overview)


if __name__ == "__main__":
    main()

