from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

import pandas as pd

from smart_schema import (
    corr_top_pairs,
    infer_schema,
    missingness_summary,
    pick_best_date_col,
    pick_best_money_col,
    safe_numeric,
    summarize_numeric,
    to_datetime_series,
)


def _fmt_money(x: float) -> str:
    try:
        x = float(x)
    except Exception:  # noqa: BLE001
        return "0"
    return f"{x:,.0f}".replace(",", ".")


def _safe_head_table(df: pd.DataFrame, cols: list[str], n: int = 5) -> pd.DataFrame:
    use = [c for c in cols if c in df.columns]
    if not use:
        return pd.DataFrame()
    out = df[use].copy()
    return out.head(n)


def build_context(df: pd.DataFrame, overview: dict[str, float]) -> str:
    """
    Create a compact Vietnamese context string to send to the LLM.
    """
    lines: list[str] = []
    lines.append("Bạn là trợ lý phân tích cho sân bóng King Arena.")
    lines.append("Chỉ trả lời dựa trên số liệu trong ngữ cảnh. Không bịa số.")
    lines.append("")
    lines.append("=== TÓM TẮT KPI ===")
    lines.append(f"Lượt đặt: {int(overview.get('bookings', 0))}")
    lines.append(f"Doanh thu: {_fmt_money(overview.get('revenue', 0.0))}")
    lines.append(f"Lợi nhuận (nếu có): {_fmt_money(overview.get('profit', 0.0))}")
    lines.append(f"Công nợ: {_fmt_money(overview.get('due', 0.0))}")
    lines.append(f"Tổng giảm giá: {_fmt_money(overview.get('discount', 0.0))}")
    lines.append(f"Giờ đã bán: {overview.get('hours_sold', 0.0):.1f}")
    lines.append("")

    if df is None or df.empty:
        lines.append("Dữ liệu sau lọc: rỗng.")
        return "\n".join(lines)

    schema = infer_schema(df)
    lines.append("=== SCHEMA (tự nhận diện) ===")
    lines.append(f"Số dòng: {len(df)} | Số cột: {df.shape[1]}")
    if schema.date_cols:
        lines.append(f"Cột thời gian: {', '.join(schema.date_cols[:6])}")
    if schema.money_cols:
        lines.append(f"Cột tiền/tổng: {', '.join(schema.money_cols[:8])}")
    if schema.categorical_cols:
        lines.append(f"Cột nhóm: {', '.join(schema.categorical_cols[:8])}")
    if schema.numeric_cols:
        lines.append(f"Cột số: {', '.join(schema.numeric_cols[:10])}")
    if schema.text_cols:
        lines.append(f"Cột text: {', '.join(schema.text_cols[:6])}")

    if "year" in df.columns:
        years = sorted(set(pd.to_numeric(df["year"], errors="coerce").dropna().astype(int).tolist()))
        if years:
            lines.append(f"Năm trong dữ liệu sau lọc: {', '.join(map(str, years))}")

    # Auto date summary even if year/month columns are not present
    best_date = pick_best_date_col(schema)
    if best_date:
        dt = to_datetime_series(df, best_date)
        if dt.notna().any():
            lines.append(f"Khoảng thời gian ({best_date}): {dt.min().date()} → {dt.max().date()}")

    # Missingness warnings
    miss = missingness_summary(df, top_k=8)
    if not miss.empty and float(miss.iloc[0]["missing_pct"]) >= 30:
        lines.append("")
        lines.append("=== CẢNH BÁO CHẤT LƯỢNG DỮ LIỆU ===")
        for _, r in miss.head(5).iterrows():
            lines.append(f"- {r['col']}: thiếu {float(r['missing_pct']):.1f}% ({int(r['missing_count'])} ô)")

    # Year summary
    lines.append("")
    lines.append("=== THEO NĂM (tổng hợp) ===")
    if "year" in df.columns and "revenue" in df.columns:
        y = (
            df.assign(revenue_num=pd.to_numeric(df["revenue"], errors="coerce").fillna(0.0))
            .groupby("year", dropna=False)
            .agg(bookings=("revenue_num", "size"), revenue=("revenue_num", "sum"))
            .reset_index()
            .sort_values("year")
        )
        for _, r in y.tail(6).iterrows():
            lines.append(f"- {int(r['year'])}: bookings={int(r['bookings'])}, revenue={_fmt_money(r['revenue'])}")
    else:
        lines.append("- (Không đủ cột year/revenue)")

    # Numeric quick stats (top money cols)
    lines.append("")
    lines.append("=== THỐNG KÊ NHANH (cột số) ===")
    best_money = pick_best_money_col(schema)
    num_focus = ([best_money] if best_money else []) + [c for c in (schema.money_cols[:6] if schema.money_cols else schema.numeric_cols[:6]) if c != best_money]
    if num_focus:
        for c in num_focus:
            if c in df.columns:
                s = summarize_numeric(df, c)
                lines.append(f"- {c}: sum={_fmt_money(s['sum'])}, mean={_fmt_money(s['mean'])}, min={_fmt_money(s['min'])}, max={_fmt_money(s['max'])}")
    else:
        lines.append("- (Không đủ cột số)")

    # Top correlations
    lines.append("")
    lines.append("=== TƯƠNG QUAN (top) ===")
    pairs = corr_top_pairs(df, schema.numeric_cols[:12], top_k=6)
    if pairs:
        for a, b, v in pairs:
            lines.append(f"- corr({a}, {b}) = {v:.3f}")
    else:
        lines.append("- (Không đủ cột số để tính tương quan)")

    # Auto top group by best money
    if best_money and schema.categorical_cols:
        gcol = schema.categorical_cols[0]
        try:
            tmp = df.copy()
            tmp["_g"] = tmp[gcol].astype(str)
            tmp["_m"] = safe_numeric(df, best_money)
            topg = tmp.groupby("_g")["_m"].sum().sort_values(ascending=False).head(5)
            lines.append("")
            lines.append(f"=== TOP {gcol} theo tổng {best_money} ===")
            for k, v in topg.items():
                lines.append(f"- {k}: {_fmt_money(v)}")
        except Exception:  # noqa: BLE001
            pass

    # Top services by revenue
    lines.append("")
    lines.append("=== TOP DỊCH VỤ/GÓI (doanh thu) ===")
    service_col = "service_type" if "service_type" in df.columns else ("package_type" if "package_type" in df.columns else None)
    if service_col and "revenue" in df.columns:
        s = (
            df.assign(revenue_num=pd.to_numeric(df["revenue"], errors="coerce").fillna(0.0))
            .groupby(service_col, dropna=False)["revenue_num"]
            .sum()
            .sort_values(ascending=False)
            .head(8)
        )
        for k, v in s.items():
            lines.append(f"- {k}: {_fmt_money(v)}")
    else:
        lines.append("- (Không đủ cột dịch vụ/gói hoặc revenue)")

    # Top fields
    lines.append("")
    lines.append("=== TOP SÂN (doanh thu) ===")
    if "field_name" in df.columns and "revenue" in df.columns:
        f = (
            df.assign(revenue_num=pd.to_numeric(df["revenue"], errors="coerce").fillna(0.0))
            .groupby("field_name", dropna=False)["revenue_num"]
            .sum()
            .sort_values(ascending=False)
            .head(8)
        )
        for k, v in f.items():
            lines.append(f"- {k}: {_fmt_money(v)}")
    else:
        lines.append("- (Không đủ cột field_name/revenue)")

    # Data dictionary snapshot (for user questions)
    lines.append("")
    lines.append("=== MẪU DÒNG DỮ LIỆU (5 dòng đầu) ===")
    sample = _safe_head_table(
        df,
        cols=[
            "booking_date",
            "year_month",
            "field_name",
            service_col or "",
            "time_slot",
            "revenue",
            "discount",
            "due",
            "payment_method",
            "booking_status",
        ],
        n=5,
    )
    if not sample.empty:
        lines.append(sample.to_csv(index=False))
    else:
        lines.append("(Không có)")

    return "\n".join(lines)


def context_hash(context: str) -> str:
    return hashlib.md5(context.encode("utf-8")).hexdigest()  # noqa: S324


@dataclass
class GeminiConfig:
    api_key: str
    model: str | None = None


def _get_gemini_config() -> GeminiConfig | None:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        try:
            import streamlit as st  # type: ignore

            api_key = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
        except Exception:  # noqa: BLE001
            api_key = ""
    if not api_key:
        return None
    model = os.getenv("GEMINI_MODEL", "").strip() or None
    if model is None:
        try:
            import streamlit as st  # type: ignore

            model = str(st.secrets.get("GEMINI_MODEL", "")).strip() or None
        except Exception:  # noqa: BLE001
            model = None
    return GeminiConfig(api_key=api_key, model=model)


def _model_candidates(preferred: str | None) -> list[str]:
    # Keep a small, robust fallback list (Google sometimes changes model names).
    base = [
        m
        for m in [
            preferred,
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-2.5-flash",
            "gemini-1.5-flash",
        ]
        if m
    ]
    # keep unique in order
    out: list[str] = []
    for m in base:
        if m not in out:
            out.append(m)
    return out


def reset_model() -> None:
    # Compatibility no-op (streamlit session state manages history)
    return None


def chat_once(system_context: str, user_question: str) -> str:
    """
    Sends one question with a system context. Keeps the answer short & grounded.
    Raises RuntimeError if Gemini is unavailable.
    """
    cfg = _get_gemini_config()
    if cfg is None:
        raise RuntimeError("Missing GEMINI_API_KEY")

    try:
        import google.generativeai as genai  # type: ignore
    except Exception as e:  # noqa: BLE001
        raise RuntimeError("google-generativeai not installed") from e

    genai.configure(api_key=cfg.api_key)

    system_instruction = (
        "Bạn là trợ lý phân tích dữ liệu cho sân bóng King Arena. "
        "Trả lời ngắn gọn bằng tiếng Việt, dựa trên số liệu trong ngữ cảnh. "
        "Nếu không đủ dữ liệu trong ngữ cảnh để kết luận, hãy nói rõ và đề xuất cách kiểm tra."
    )

    errors: list[str] = []
    tried: list[str] = []
    for model_name in _model_candidates(cfg.model):
        tried.append(model_name)
        try:
            model = genai.GenerativeModel(model_name=model_name, system_instruction=system_instruction)
            resp = model.generate_content([f"NGỮ CẢNH:\n{system_context}\n\nCÂU HỎI:\n{user_question}"])
            text = getattr(resp, "text", None) or ""
            text = text.strip()
            if not text:
                raise RuntimeError("Empty response")
            return text
        except Exception as e:  # noqa: BLE001
            errors.append(f"- {model_name}: {type(e).__name__}: {e}")
            continue

    detail = "\n".join(errors[-6:]) if errors else "(không có chi tiết lỗi)"
    raise RuntimeError(
        "Gemini call failed. Nguyên nhân thường gặp: thiếu/sai `GEMINI_API_KEY`, hết quota, model không tồn tại (404), hoặc bị chặn quyền (403).\n\n"
        f"Models đã thử: {', '.join(tried) if tried else '(none)'}\n"
        f"Lỗi chi tiết:\n{detail}"
    )

