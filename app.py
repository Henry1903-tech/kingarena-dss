from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import dashboard_sections as sections
from config import APP_ICON, APP_TITLE
from data_loader import (
    Filters,
    apply_filters,
    build_dataset_from_raw,
    compute_overview,
    list_sheets_from_upload,
    load_data,
    read_excel_raw_from_upload,
)
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

    with st.sidebar:
        st.header("Nguồn dữ liệu")
        up = st.file_uploader("Tải file Excel (.xlsx) để xem dashboard", type=["xlsx"])
        st.caption("Nếu không tải lên, app sẽ thử tự dò file theo `EXCEL_CANDIDATES` trong `config.py`.")
        st.divider()

        mapping: dict[str, str] = {}
        sheet_choice = None
        skiprows = 0

        if up is not None:
            file_bytes = up.getvalue()
            sheets = list_sheets_from_upload(file_bytes)
            if sheets:
                sheet_choice = st.selectbox("Chọn sheet", options=sheets, index=0)
            skiprows = int(st.number_input("Bỏ qua số dòng đầu (skiprows)", min_value=0, max_value=50, value=0, step=1))
            st.caption("Nếu cột bị lệch header, thử tăng skiprows (1, 2, 3…).")

            try:
                raw_preview = read_excel_raw_from_upload(up.name, file_bytes, sheet_name=sheet_choice, skiprows=skiprows)
            except Exception as e:  # noqa: BLE001
                raw_preview = pd.DataFrame()
                st.error(f"Không đọc được file để preview: `{type(e).__name__}: {e}`")

            if raw_preview is not None and not raw_preview.empty:
                st.markdown("**Preview (5 dòng)**")
                st.dataframe(raw_preview.head(5), use_container_width=True, hide_index=True)

                cols = [str(c) for c in raw_preview.columns]
                with st.expander("Map cột (nếu file đặt tên cột khác)", expanded=False):
                    st.caption("Chọn cột tương ứng để app hiểu đúng dữ liệu. Có thể bỏ trống nếu không có.")
                    mapping["booking_date"] = st.selectbox("Cột ngày đặt (booking_date)", options=[""] + cols, index=0)
                    mapping["start_time"] = st.selectbox("Cột giờ bắt đầu (start_time)", options=[""] + cols, index=0)
                    mapping["end_time"] = st.selectbox("Cột giờ kết thúc (end_time)", options=[""] + cols, index=0)
                    mapping["duration_hours"] = st.selectbox("Cột số giờ (duration_hours)", options=[""] + cols, index=0)
                    mapping["field_name"] = st.selectbox("Cột tên sân (field_name)", options=[""] + cols, index=0)
                    mapping["service_type"] = st.selectbox("Cột dịch vụ/gói (service_type)", options=[""] + cols, index=0)
                    mapping["package_type"] = st.selectbox("Cột gói (package_type)", options=[""] + cols, index=0)
                    mapping["payment_method"] = st.selectbox("Cột phương thức TT (payment_method)", options=[""] + cols, index=0)
                    mapping["list_price"] = st.selectbox("Cột giá gốc (list_price)", options=[""] + cols, index=0)
                    mapping["discount"] = st.selectbox("Cột giảm giá (discount)", options=[""] + cols, index=0)
                    mapping["final_price"] = st.selectbox("Cột giá sau giảm (final_price)", options=[""] + cols, index=0)
                    mapping["total_paid"] = st.selectbox("Cột đã thanh toán (total_paid)", options=[""] + cols, index=0)
                    mapping["due"] = st.selectbox("Cột còn nợ (due)", options=[""] + cols, index=0)
                    mapping["revenue"] = st.selectbox("Cột doanh thu (revenue)", options=[""] + cols, index=0)
                    mapping["cost"] = st.selectbox("Cột chi phí (cost)", options=[""] + cols, index=0)
                    mapping["profit"] = st.selectbox("Cột lợi nhuận (profit)", options=[""] + cols, index=0)
                    mapping["booking_status"] = st.selectbox("Cột trạng thái (booking_status)", options=[""] + cols, index=0)
        else:
            raw_preview = None

        st.header("Bộ lọc")

        # Build dataset
        if up is not None:
            try:
                raw_df = read_excel_raw_from_upload(up.name, up.getvalue(), sheet_name=sheet_choice, skiprows=skiprows)
                mapping_clean = {k: v for k, v in mapping.items() if v}
                df_raw = build_dataset_from_raw(raw_df, mapping=mapping_clean)
                data_path = f"{up.name} (sheet={sheet_choice}, skiprows={skiprows})"
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

        # Show status bar (after build)
    sections.render_status_bar(df_raw, data_path)

    with st.sidebar:
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

