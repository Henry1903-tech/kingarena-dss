from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from io import BytesIO

import numpy as np
import pandas as pd

from config import EXCEL_CANDIDATES, TIME_SLOT_BINS, TIME_SLOT_LABELS


CANON_COLS = {
    # identifiers
    "booking_id",
    "customer_id",
    # time
    "booking_date",
    "start_time",
    "end_time",
    "duration_hours",
    "weekday",
    "time_slot",
    "year",
    "month",
    "year_month",
    # field / offer
    "field_name",
    "field_type",
    "package_type",
    "service_type",
    # payment / finance
    "list_price",
    "discount",
    "final_price",
    "total_paid",
    "due",
    "revenue",
    "cost",
    "profit",
    "payment_method",
    # status
    "booking_status",
}


def _slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^\w]+", "_", s, flags=re.UNICODE)
    s = re.sub(r"__+", "_", s)
    return s.strip("_")


def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename: dict[str, str] = {}
    for c in df.columns:
        sc = _slug(str(c))
        rename[c] = sc
    df = df.rename(columns=rename)

    # Ensure unique column names after slugify (Excel often has near-duplicate headers)
    cols = list(df.columns)
    seen: dict[str, int] = {}
    uniq: list[str] = []
    for c in cols:
        k = str(c)
        if k not in seen:
            seen[k] = 1
            uniq.append(k)
        else:
            seen[k] += 1
            uniq.append(f"{k}_{seen[k]}")
    df.columns = uniq

    # alias map (expand as you meet real King Arena excel)
    alias = {
        "date": "booking_date",
        "ngay": "booking_date",
        "ngay_dat": "booking_date",
        "ngay_dat_san": "booking_date",
        "bookingdate": "booking_date",
        "start": "start_time",
        "gio_bat_dau": "start_time",
        "start_time": "start_time",
        "end": "end_time",
        "gio_ket_thuc": "end_time",
        "end_time": "end_time",
        "san": "field_name",
        "ten_san": "field_name",
        "field": "field_name",
        "court": "field_name",
        "loai_san": "field_type",
        "kich_thuoc_san": "field_type",
        "khach_hang": "customer_id",
        "ma_khach": "customer_id",
        "customer": "customer_id",
        "ten_khach": "customer_name",
        "nhom_khach": "customer_group",
        "doi_bong": "customer_group",
        "goi": "package_type",
        "package": "package_type",
        "dich_vu": "service_type",
        "service": "service_type",
        "phuong_thuc_tt": "payment_method",
        "payment": "payment_method",
        "thanh_toan": "payment_method",
        "tien_mat": "payment_method",
        "gia_goc": "list_price",
        "list_price": "list_price",
        "giam_gia": "discount",
        "discount": "discount",
        "gia_sau_giam": "final_price",
        "final_price": "final_price",
        "da_thu": "total_paid",
        "tien_thu": "total_paid",
        "total_paid": "total_paid",
        "con_no": "due",
        "due": "due",
        "doanh_thu": "revenue",
        "revenue": "revenue",
        "chi_phi": "cost",
        "cost": "cost",
        "loi_nhuan": "profit",
        "profit": "profit",
        "trang_thai": "booking_status",
        "status": "booking_status",
    }

    for src, dst in alias.items():
        if src in df.columns and dst not in df.columns:
            df = df.rename(columns={src: dst})

    return df


def _to_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce").dt.date


def _to_time(s: pd.Series) -> pd.Series:
    # Accept: "18:00", "18:00:00", Excel time, datetime
    t = pd.to_datetime(s, errors="coerce").dt.time
    return t


def _compute_duration_hours(df: pd.DataFrame) -> pd.Series:
    if "duration_hours" in df.columns:
        dur = pd.to_numeric(df["duration_hours"], errors="coerce")
        if dur.notna().any():
            return dur

    if "start_time" in df.columns and "end_time" in df.columns:
        st = pd.to_datetime(df["start_time"], errors="coerce")
        en = pd.to_datetime(df["end_time"], errors="coerce")
        dur = (en - st).dt.total_seconds() / 3600.0
        # Handle cases where start/end are plain times without dates: try parsing as time
        if dur.isna().all():
            st2 = pd.to_datetime(df["start_time"].astype(str), errors="coerce")
            en2 = pd.to_datetime(df["end_time"].astype(str), errors="coerce")
            dur = (en2 - st2).dt.total_seconds() / 3600.0
        return dur

    return pd.Series([np.nan] * len(df), index=df.index, dtype="float64")


def _derive_finance(df: pd.DataFrame) -> pd.DataFrame:
    for c in ("list_price", "discount", "final_price", "total_paid", "due", "revenue", "cost", "profit"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "final_price" not in df.columns:
        if "list_price" in df.columns:
            disc = df["discount"] if "discount" in df.columns else 0.0
            df["final_price"] = df["list_price"].fillna(0.0) - pd.to_numeric(disc, errors="coerce").fillna(0.0)
        elif "total_paid" in df.columns:
            df["final_price"] = df["total_paid"]

    if "revenue" not in df.columns:
        # keep revenue definition simple: final_price preferred, else total_paid
        if "final_price" in df.columns:
            df["revenue"] = df["final_price"]
        elif "total_paid" in df.columns:
            df["revenue"] = df["total_paid"]

    if "total_paid" not in df.columns and "revenue" in df.columns:
        df["total_paid"] = df["revenue"]

    if "due" not in df.columns and "final_price" in df.columns and "total_paid" in df.columns:
        df["due"] = (df["final_price"].fillna(0.0) - df["total_paid"].fillna(0.0)).clip(lower=0.0)

    if "discount" not in df.columns and "list_price" in df.columns and "final_price" in df.columns:
        df["discount"] = (df["list_price"].fillna(0.0) - df["final_price"].fillna(0.0)).clip(lower=0.0)

    if "profit" not in df.columns and "revenue" in df.columns:
        if "cost" in df.columns:
            df["profit"] = df["revenue"].fillna(0.0) - df["cost"].fillna(0.0)
        else:
            df["profit"] = np.nan

    # df.get(col, 0.0) may return a float -> always normalize to a Series
    discount_s = df["discount"] if "discount" in df.columns else pd.Series(0.0, index=df.index)
    due_s = df["due"] if "due" in df.columns else pd.Series(0.0, index=df.index)
    df["has_discount"] = pd.to_numeric(discount_s, errors="coerce").fillna(0.0) > 0
    df["has_due"] = pd.to_numeric(due_s, errors="coerce").fillna(0.0) > 0
    return df


def _derive_time(df: pd.DataFrame) -> pd.DataFrame:
    if "booking_date" in df.columns:
        dt = pd.to_datetime(df["booking_date"], errors="coerce")
        df["year"] = dt.dt.year
        df["month"] = dt.dt.month
        df["year_month"] = dt.dt.to_period("M").astype(str)
        df["weekday"] = dt.dt.day_name()

    if "start_time" in df.columns:
        t = pd.to_datetime(df["start_time"], errors="coerce")
        hour = t.dt.hour
        if hour.isna().all():
            # maybe time strings only
            t2 = pd.to_datetime(df["start_time"].astype(str), errors="coerce")
            hour = t2.dt.hour
        df["start_hour"] = hour
        df["time_slot"] = pd.cut(
            hour,
            bins=TIME_SLOT_BINS,
            labels=TIME_SLOT_LABELS,
            right=False,
            include_lowest=True,
        )

    df["duration_hours"] = _compute_duration_hours(df)
    return df


def empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=sorted(CANON_COLS))

def apply_column_mapping(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """
    mapping: {canonical_col: existing_col_in_df}
    If mapping points to a missing column, it's ignored.
    """
    if df is None or df.empty or not mapping:
        return df
    rename: dict[str, str] = {}
    for canon, src in mapping.items():
        if not canon or not src:
            continue
        if src in df.columns and canon not in df.columns:
            rename[src] = canon
    return df.rename(columns=rename) if rename else df


def list_sheets_from_upload(file_bytes: bytes) -> list[str]:
    try:
        import openpyxl  # type: ignore

        wb = openpyxl.load_workbook(BytesIO(file_bytes), read_only=True, data_only=True)
        return list(wb.sheetnames)
    except Exception:  # noqa: BLE001
        return []


def read_excel_raw_from_upload(
    file_name: str,
    file_bytes: bytes,
    sheet_name: str | int | None = None,
    skiprows: int = 0,
) -> pd.DataFrame:
    """
    Read raw excel (no standardize/derive) for preview + mapping UI.
    """
    df = pd.read_excel(BytesIO(file_bytes), engine="openpyxl", sheet_name=sheet_name, skiprows=skiprows)
    if isinstance(df, dict):
        # when sheet_name=None
        for _, sdf in df.items():
            if sdf is not None and not sdf.empty:
                return sdf
        return pd.DataFrame()
    return df if df is not None else pd.DataFrame()


def _read_excel_any(source, label: str) -> pd.DataFrame:
    last_err: Exception | None = None
    for skip in (2, 1, 0):
        try:
            # Read all sheets to be robust with files that have an empty first sheet
            sheets = pd.read_excel(source, engine="openpyxl", skiprows=skip, sheet_name=None)
            if isinstance(sheets, dict):
                # pick the first non-empty sheet
                df = None
                for _, sdf in sheets.items():
                    if sdf is not None and not sdf.empty:
                        df = sdf
                        break
                if df is None:
                    continue
            else:
                df = sheets
                if df is None or df.empty:
                    continue

            df = _standardize_columns(df)
            if "booking_date" in df.columns:
                df["booking_date"] = pd.to_datetime(df["booking_date"], errors="coerce")
            df = _derive_time(df)
            df = _derive_finance(df)
            return df
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
    detail = f"{type(last_err).__name__}: {last_err}" if last_err else "unknown"
    raise RuntimeError(f"Không đọc được Excel: {label}. Lỗi gốc: {detail}") from last_err


def load_data(base_dir: str | Path | None = None, candidates: Iterable[str] = EXCEL_CANDIDATES) -> tuple[pd.DataFrame, str | None]:
    base = Path(base_dir) if base_dir else Path(__file__).resolve().parent
    path: Path | None = None
    for name in candidates:
        p = base / name
        if p.exists() and p.is_file():
            path = p
            break
    if path is None:
        return empty_df(), None

    df = _read_excel_any(path, label=path.name)
    return df, str(path)


def load_data_from_upload(file_name: str, file_bytes: bytes) -> tuple[pd.DataFrame, str]:
    df = _read_excel_any(BytesIO(file_bytes), label=file_name)
    return df, file_name


def build_dataset_from_raw(df_raw: pd.DataFrame, mapping: dict[str, str] | None = None) -> pd.DataFrame:
    """
    Take a raw dataframe, standardize column names, apply optional mapping,
    then derive time + finance fields.
    """
    if df_raw is None or df_raw.empty:
        return empty_df()
    df = df_raw.copy()
    df = _standardize_columns(df)
    if mapping:
        df = apply_column_mapping(df, mapping)
    if "booking_date" in df.columns:
        df["booking_date"] = pd.to_datetime(df["booking_date"], errors="coerce")
    df = _derive_time(df)
    df = _derive_finance(df)
    return df


@dataclass(frozen=True)
class Filters:
    years: list[int] | None = None
    months: list[int] | None = None
    fields: list[str] | None = None
    time_slots: list[str] | None = None
    payment_methods: list[str] | None = None
    statuses: list[str] | None = None


def apply_filters(df: pd.DataFrame, f: Filters) -> pd.DataFrame:
    if df is None or df.empty:
        return df.copy()

    out = df.copy()

    if f.years:
        out = out[out.get("year").isin(f.years)]
    if f.months:
        out = out[out.get("month").isin(f.months)]
    if f.fields and "field_name" in out.columns:
        out = out[out["field_name"].astype(str).isin(f.fields)]
    if f.time_slots and "time_slot" in out.columns:
        out = out[out["time_slot"].astype(str).isin(f.time_slots)]
    if f.payment_methods and "payment_method" in out.columns:
        out = out[out["payment_method"].astype(str).isin(f.payment_methods)]
    if f.statuses and "booking_status" in out.columns:
        out = out[out["booking_status"].astype(str).isin(f.statuses)]

    return out


def compute_overview(df: pd.DataFrame) -> dict[str, float]:
    if df is None or df.empty:
        return {
            "bookings": 0.0,
            "revenue": 0.0,
            "profit": 0.0,
            "due": 0.0,
            "discount": 0.0,
            "discount_rate": 0.0,
            "due_rate": 0.0,
            "avg_revenue_per_booking": 0.0,
            "avg_profit_per_booking": 0.0,
            "hours_sold": 0.0,
        }

    def _num_series(col: str) -> pd.Series:
        s = df[col] if col in df.columns else pd.Series(0.0, index=df.index)
        return pd.to_numeric(s, errors="coerce").fillna(0.0)

    bookings = float(len(df))
    revenue = float(_num_series("revenue").sum())
    profit = float(_num_series("profit").sum())
    due = float(_num_series("due").sum())
    discount = float(_num_series("discount").sum())

    list_price_sum = float(_num_series("list_price").sum())
    discount_rate = float(discount / list_price_sum) if list_price_sum > 0 else (float(discount / revenue) if revenue > 0 else 0.0)
    due_rate = float(due / revenue) if revenue > 0 else 0.0

    avg_rev = float(revenue / bookings) if bookings > 0 else 0.0
    avg_profit = float(profit / bookings) if bookings > 0 else 0.0
    hours_sold = float(_num_series("duration_hours").sum())

    return {
        "bookings": bookings,
        "revenue": revenue,
        "profit": profit,
        "due": due,
        "discount": discount,
        "discount_rate": discount_rate,
        "due_rate": due_rate,
        "avg_revenue_per_booking": avg_rev,
        "avg_profit_per_booking": avg_profit,
        "hours_sold": hours_sold,
    }

